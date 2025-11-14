"""
Browser Agent - Handles all web browsing operations.

This agent is responsible for:
- URL navigation
- Content extraction with langextract
- Screenshot capture
- Browser resource management

NOTE: For Google search, use Google Agent's google_search tool instead (faster, no browser overhead)

Acts as a mini-orchestrator for browser-related operations.
"""

from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
from pathlib import Path
import logging

from src.config import get_config_context
from src.config_validator import ConfigValidationError

logger = logging.getLogger(__name__)


# Lazy initialization of browser instance
_browser_instance = None
_browser_runtime_cache: Optional[Dict[str, Any]] = None


def _load_browser_runtime():
    """Load config, accessor, and browser settings."""
    context = get_config_context()
    accessor = context.accessor
    browser_settings = accessor.get_browser_config()
    return {
        "config": context.data,
        "accessor": accessor,
        "settings": browser_settings,
    }


def _reset_browser_instance(reason: str = ""):
    """Close and clear the cached browser instance."""
    global _browser_instance
    if _browser_instance is None:
        return

    try:
        logger.info(f"[BROWSER AGENT] Resetting browser instance ({reason})")
        _browser_instance.close()
    except Exception as exc:
        logger.warning(f"[BROWSER AGENT] Error while closing browser instance: {exc}")
    finally:
        _browser_instance = None


def get_browser():
    """Get or create browser instance."""
    global _browser_instance, _browser_runtime_cache
    if _browser_runtime_cache is None:
        _browser_runtime_cache = _load_browser_runtime()

    runtime = _browser_runtime_cache
    config = runtime["config"]
    settings = runtime["settings"]

    if _browser_instance is None:
        from ..automation.web_browser import SyncWebBrowser
        _browser_instance = SyncWebBrowser(config, headless=settings.headless)

    return _browser_instance


@tool
def google_search(query: str, num_results: int = 5) -> Dict[str, Any]:
    """
    Search Google and extract results.

    This is the PRIMARY web search tool. Use this when you need to:
    - Find information on the web
    - Search for documentation
    - Discover websites related to a topic
    - Get quick answers from search results

    Args:
        query: Search query (natural language)
        num_results: Number of results to return (default: 5)

    Returns:
        Dictionary with search results containing titles, links, and snippets

    Example:
        google_search("LangChain documentation", num_results=3)
    """
    logger.info(f"[BROWSER AGENT] Tool: google_search(query='{query}', num_results={num_results})")

    try:
        runtime = _load_browser_runtime()
    except ConfigValidationError as exc:
        return {
            "error": True,
            "error_type": "ConfigurationError",
            "error_message": str(exc),
            "retry_possible": False
        }

    config = runtime["config"]
    settings = runtime["settings"]

    try:
        use_unique_session = settings.unique_session_search
        headless = settings.headless
    except AttributeError:
        use_unique_session = True
        headless = False

    close_after = False
    if use_unique_session:
        from ..automation.web_browser import SyncWebBrowser
        browser = SyncWebBrowser(config, headless=headless, unique_session=True)
        close_after = True
    else:
        browser = get_browser()

    try:
        result = browser.google_search(query=query, num_results=num_results)
    finally:
        if close_after:
            browser.close()

    if result.get("success"):
        return {
            "query": result["query"],
            "results": result["results"],
            "num_results": result["num_results"],
            "message": f"Found {result['num_results']} results for '{query}'"
        }
    else:
        return {
            "error": True,
            "error_type": "SearchError",
            "error_message": result.get("error", "Google search failed"),
            "retry_possible": True
        }


@tool
def navigate_to_url(url: str, wait_until: str = "domcontentloaded") -> Dict[str, Any]:
    """
    Navigate to a specific URL and get page information.

    Use this when you need to:
    - Visit a specific website
    - Open a webpage by URL
    - Check if a website is accessible

    Args:
        url: Full URL to navigate to (must include http:// or https://)
        wait_until: When to consider navigation complete ("load", "domcontentloaded", "networkidle")

    Returns:
        Dictionary with page URL, title, and status

    Example:
        navigate_to_url("https://docs.python.org/3/")
    """
    logger.info(f"[BROWSER AGENT] Tool: navigate_to_url(url='{url}')")

    max_attempts = 2

    for attempt in range(1, max_attempts + 1):
        try:
            browser = get_browser()
            result = browser.navigate(url=url, wait_until=wait_until)
        except Exception as exc:
            logger.error(f"[BROWSER AGENT] Error in navigate_to_url: {exc}")
            result = {
                "success": False,
                "error": str(exc),
                "error_type": "NavigationError",
            }

        if result.get("success"):
            return {
                "url": result["url"],
                "title": result["title"],
                "status": result["status"],
                "message": f"Successfully navigated to {result['url']}"
            }

        # Handle specific Playwright loop mismatch errors by resetting browser and retrying once
        error_text = str(result.get("error_message") or result.get("error") or "").lower()
        if "future belongs to a different loop" in error_text or "event loop is closed" in error_text:
            if attempt < max_attempts:
                logger.warning(
                    "[BROWSER AGENT] Detected Playwright loop mismatch during navigation; "
                    "resetting browser and retrying"
                )
                _reset_browser_instance("loop mismatch during navigation")
                continue

        return {
            "error": True,
            "error_type": result.get("error_type", "NavigationError"),
            "error_message": result.get("error_message") or result.get("error", "Failed to navigate"),
            "retry_possible": True
        }

    # If all attempts exhausted
    return {
        "error": True,
        "error_type": "NavigationError",
        "error_message": "Failed to navigate after retrying with a fresh browser session",
        "retry_possible": True
    }


@tool
def extract_page_content(url: str = None) -> Dict[str, Any]:
    """
    Extract clean text content from the current page or a specific URL.

    Uses langextract for intelligent content extraction that:
    - Removes navigation, headers, footers
    - Extracts main article/content text
    - Filters out ads and boilerplate
    - Returns clean, readable text suitable for LLM processing

    Use this when you need to:
    - Read the main content of a webpage
    - Extract article text for analysis
    - Get clean text from documentation pages
    - Prepare web content for LLM disambiguation

    Args:
        url: Optional URL to navigate to first (if None, extracts from current page)

    Returns:
        Dictionary with extracted content, title, URL, and metadata

    Example:
        extract_page_content("https://en.wikipedia.org/wiki/Python_(programming_language)")
    """
    logger.info(f"[BROWSER AGENT] Tool: extract_page_content(url={url})")

    try:
        browser = get_browser()

        # Navigate to URL if provided
        if url:
            nav_result = browser.navigate(url=url)
            if not nav_result.get("success"):
                return {
                    "error": True,
                    "error_type": "NavigationError",
                    "error_message": f"Failed to navigate to {url}",
                    "retry_possible": True
                }

        # Extract content
        result = browser.extract_content()

        if result.get("success"):
            return {
                "url": result["url"],
                "title": result["title"],
                "content": result["content"],
                "word_count": result["metadata"]["word_count"],
                "extraction_method": result["metadata"]["method"],
                "message": f"Extracted {result['metadata']['word_count']} words from {result['title']}"
            }
        else:
            return {
                "error": True,
                "error_type": "ExtractionError",
                "error_message": result.get("error", "Content extraction failed"),
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"[BROWSER AGENT] Error in extract_page_content: {e}")
        return {
            "error": True,
            "error_type": "ExtractionError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def take_web_screenshot(url: str = None, full_page: bool = False) -> Dict[str, Any]:
    """
    Capture a screenshot of a webpage.

    Use this when you need to:
    - Capture visual proof of webpage content
    - Document the appearance of a website
    - Save a snapshot of dynamic content
    - Create visual references

    Args:
        url: Optional URL to navigate to first (if None, captures current page)
        full_page: If True, capture entire scrollable page; if False, capture viewport only

    Returns:
        Dictionary with screenshot path and URL

    Example:
        take_web_screenshot("https://example.com", full_page=True)
    """
    logger.info(f"[BROWSER AGENT] Tool: take_web_screenshot(url={url}, full_page={full_page})")

    try:
        browser = get_browser()

        # Navigate to URL if provided
        if url:
            nav_result = browser.navigate(url=url)
            if not nav_result.get("success"):
                return {
                    "error": True,
                    "error_type": "NavigationError",
                    "error_message": f"Failed to navigate to {url}",
                    "retry_possible": True
                }

        # Take screenshot
        result = browser.take_screenshot(full_page=full_page)

        if result.get("success"):
            return {
                "screenshot_path": result["screenshot_path"],
                "url": result["url"],
                "full_page": result["full_page"],
                "message": f"Screenshot saved to {result['screenshot_path']}"
            }
        else:
            return {
                "error": True,
                "error_type": "ScreenshotError",
                "error_message": result.get("error", "Screenshot capture failed"),
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"[BROWSER AGENT] Error in take_web_screenshot: {e}")
        return {
            "error": True,
            "error_type": "ScreenshotError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def close_browser() -> Dict[str, Any]:
    """
    Close the browser and clean up resources.

    Use this when you're done with all web browsing tasks to:
    - Free up system resources
    - Close browser windows
    - Clean up temporary files

    This should typically be called at the end of web browsing sessions.

    Returns:
        Dictionary with status message
    """
    logger.info("Tool: close_browser()")

    try:
        global _browser_instance
        if _browser_instance:
            _browser_instance.close()
            _browser_instance = None
            return {
                "message": "Browser closed successfully"
            }
        else:
            return {
                "message": "No browser instance to close"
            }

    except Exception as e:
        logger.error(f"Error closing browser: {e}")
        return {
            "error": True,
            "error_type": "BrowserError",
            "error_message": str(e),
            "retry_possible": False
        }


# Browser Agent Tool Registry
BROWSER_AGENT_TOOLS = [
    # google_search removed - use Google Agent's google_search instead (faster, no browser)
    navigate_to_url,
    extract_page_content,
    take_web_screenshot,
    close_browser,
]

# Backwards compatibility
BROWSER_TOOLS = BROWSER_AGENT_TOOLS


# Browser Agent Hierarchy
BROWSER_AGENT_HIERARCHY = """
Browser Agent Hierarchy:
=======================

NOTE: For Google search, use Google Agent's google_search tool (faster, no browser overhead)

LEVEL 1: Navigation & Content Extraction
├─ navigate_to_url → Go to a specific webpage
└─ extract_page_content → Get clean text from webpage (uses langextract)

LEVEL 2: Visual Capture
└─ take_web_screenshot → Capture webpage as image

LEVEL 3: Cleanup
└─ close_browser → Close browser and free resources

Typical Workflow:
1. Use Google Agent's google_search("topic") → Find relevant URLs
2. navigate_to_url(url) → Visit specific page
3. extract_page_content() → Get page content
4. [Use LLM to analyze extracted content]
5. close_browser() → Clean up
"""

# Backwards compatibility
BROWSER_TOOL_HIERARCHY = BROWSER_AGENT_HIERARCHY


class BrowserAgent:
    """
    Browser Agent - Mini-orchestrator for web browsing operations.

    Responsibilities:
    - Searching the web (Google)
    - Navigating to URLs
    - Extracting page content with langextract
    - Capturing screenshots
    - Resource management

    This agent acts as a sub-orchestrator that handles all browser-related tasks.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in BROWSER_AGENT_TOOLS}
        logger.info(f"[BROWSER AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        """Get all browser agent tools."""
        return BROWSER_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get browser agent hierarchy documentation."""
        return BROWSER_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a browser agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Browser agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[BROWSER AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[BROWSER AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }
