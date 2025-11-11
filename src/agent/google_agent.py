"""
Google Agent - Google search integration (no API key required).

This agent provides access to Google search via googlesearch-python:
- Web scraping-based Google searches
- No API key required
- Fast and reliable
- Rich metadata (snippets, links, titles)

Uses: https://pypi.org/project/googlesearch-python/
"""

from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
import logging
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from ..utils import load_config

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 8
MAX_SNIPPET_CHARS = 400


@tool
def google_search(
    query: str,
    num_results: int = 5,
    search_type: str = "web"
) -> Dict[str, Any]:
    """
    Search Google using googlesearch-python (no API key required).

    GOOGLE AGENT - LEVEL 1: Web Search
    Fast, reliable Google searches without browser automation or API keys.

    This tool uses googlesearch-python library which provides:
    - Web scraping-based Google searches
    - No API key required
    - Fast response times
    - Rich metadata (snippets, links, titles)

    Args:
        query: Search query string
        num_results: Number of results to return (default: 5, max: 100)
        search_type: Type of search - "web" (default) or "image"

    Returns:
        Dictionary with:
        - results: List of search results
        - total_results: Number of results found
        - query: The search query
        - num_results: Number of results returned

        Each result contains:
        - title: Page title
        - link: URL
        - snippet: Text snippet/description
        - display_link: Domain name (extracted from URL)

    Requirements:
        - googlesearch-python library (pip install googlesearch-python)
        - No API keys needed!

    Example:
        google_search("Python async programming", num_results=10)
    """
    logger.info(f"[GOOGLE AGENT] Tool: google_search(query='{query}', num={num_results}, type={search_type})")

    try:
        # Import googlesearch library
        try:
            from googlesearch import search
        except ImportError:
            search = None

        # Validate parameters
        num_results = max(1, min(100, num_results))  # Clamp to 1-100

        # Note: googlesearch-python doesn't support image search directly
        # For image search, we'll use regular search (limitation of the library)
        if search_type == "image":
            logger.warning("[GOOGLE AGENT] Image search not fully supported, using web search")

        logger.info(f"[GOOGLE AGENT] Executing Google search: {query}")

        # Use advanced search to get title, url, and description
        # According to googlesearch-python docs, advanced=True returns SearchResult objects
        # Add sleep_interval and other parameters to improve reliability
        results: List[Dict[str, str]] = []

        if search:
            try:
                results = _run_primary_search(search, query, num_results)
            except Exception as search_error:
                logger.warning(f"[GOOGLE AGENT] Primary googlesearch failed: {search_error}")

        if not results:
            logger.info("[GOOGLE AGENT] Falling back to direct Google scraping")
            results = _fallback_google_scrape(query, num_results)

        if not results:
            logger.warning("[GOOGLE AGENT] No results found after fallback")
            return {
                "results": [],
                "total_results": 0,
                "query": query,
                "num_results": 0,
                "search_type": search_type,
                "source": "google_scrape",
                "summary": "No Google results found for the query.",
                "message": "No Google results found for the query."
            }

        # Enrich snippets when missing
        results = _ensure_snippets(results)

        # Generate LLM summary
        summary = _summarize_results(query, results)

        logger.info(f"[GOOGLE AGENT] Found {len(results)} results")

        return {
            "results": results,
            "total_results": len(results),
            "query": query,
            "num_results": len(results),
            "search_type": search_type,
            "source": "googlesearch_python" if search else "google_scrape",
            "summary": summary,
            "message": summary
        }

    except Exception as e:
        logger.error(f"[GOOGLE AGENT] Error in google_search: {e}", exc_info=True)
        return {
            "error": True,
            "error_type": "SearchError",
            "error_message": str(e),
            "retry_possible": True
        }


@tool
def google_search_images(
    query: str,
    num_results: int = 5
) -> Dict[str, Any]:
    """
    Search Google Images (limited support).

    GOOGLE AGENT - LEVEL 2: Image Search
    Note: googlesearch-python has limited image search support.
    This will perform a regular web search with image-related query.

    Args:
        query: Image search query
        num_results: Number of results to return (default: 5)

    Returns:
        Dictionary with search results (may include image-related pages)
    """
    logger.info(f"[GOOGLE AGENT] Tool: google_search_images(query='{query}')")
    logger.warning("[GOOGLE AGENT] Image search uses web search (library limitation)")

    # Use image-related query modification
    image_query = f"{query} images"
    return google_search(query=image_query, num_results=num_results, search_type="web")


@tool
def google_search_site(
    query: str,
    site: str,
    num_results: int = 5
) -> Dict[str, Any]:
    """
    Search within a specific website using Google.

    GOOGLE AGENT - LEVEL 3: Site-Specific Search
    Limit search to a specific domain or website.

    This adds "site:domain.com" to the query for site-restricted searches.
    Useful for searching documentation, specific blogs, or corporate sites.

    Args:
        query: Search query
        site: Domain to search within (e.g., "stackoverflow.com", "github.com")
        num_results: Number of results (1-10, default: 5)

    Returns:
        Search results limited to the specified site

    Examples:
        - google_search_site("python async", "stackoverflow.com")
        - google_search_site("machine learning", "github.com")
        - google_search_site("API docs", "openai.com")
    """
    logger.info(f"[GOOGLE AGENT] Tool: google_search_site(query='{query}', site='{site}')")

    # Add site restriction to query
    site_query = f"site:{site} {query}"

    return google_search(query=site_query, num_results=num_results, search_type="web")


def _run_primary_search(search_func, query: str, num_results: int) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    max_attempts = 3

    for attempt in range(max_attempts):
        try:
            sleep_interval = 2 + attempt  # 2s, 3s, 4s
            logger.info(
                "[GOOGLE AGENT] googlesearch attempt %s/%s (sleep_interval=%ss)",
                attempt + 1,
                max_attempts,
                sleep_interval,
            )
            raw_results = list(
                search_func(
                    query,
                    num_results=num_results,
                    advanced=True,
                    sleep_interval=sleep_interval,
                    lang="en",
                )
            )
            results = _normalize_search_objects(raw_results)
            if results:
                break
        except Exception as error:
            logger.warning("[GOOGLE AGENT] googlesearch attempt failed: %s", error)
        if attempt < max_attempts - 1:
            import time
            time.sleep(2)

    return results


def _normalize_search_objects(raw_results: List[Any]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for item in raw_results:
        url = getattr(item, "url", None) or str(item)
        title = getattr(item, "title", "") or ""
        description = getattr(item, "description", "") or ""
        normalized.append(
            {
                "title": title or "No title",
                "link": url,
                "snippet": description,
                "display_link": _display_link(url),
            }
        )
    return normalized


def _fallback_google_scrape(query: str, limit: int) -> List[Dict[str, str]]:
    headers = {"User-Agent": USER_AGENT}
    params = {"q": query, "num": min(limit, 10), "hl": "en"}
    try:
        response = requests.get(
            "https://www.google.com/search",
            params=params,
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
    except Exception as error:
        logger.warning("[GOOGLE AGENT] Fallback scrape failed: %s", error)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    results: List[Dict[str, str]] = []

    for result_block in soup.select("div.g"):
        link_tag = result_block.find("a", href=True)
        title_tag = result_block.find("h3")
        snippet_tag = result_block.select_one("div.VwiC3b span")

        if not link_tag or not title_tag:
            continue

        url = link_tag["href"]
        title = title_tag.get_text(strip=True)
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""
        results.append(
            {
                "title": title or "No title",
                "link": url,
                "snippet": snippet,
                "display_link": _display_link(url),
            }
        )
        if len(results) >= limit:
            break

    return results


def _display_link(url: str) -> str:
    try:
        parsed = urlparse(url)
        return parsed.netloc or url
    except Exception:
        return url


def _ensure_snippets(results: List[Dict[str, str]]) -> List[Dict[str, str]]:
    enriched: List[Dict[str, str]] = []
    for result in results:
        snippet = result.get("snippet", "") or ""
        if len(snippet) < 40:
            fetched = _fetch_page_snippet(result["link"])
            if fetched:
                snippet = fetched
        enriched.append({**result, "snippet": snippet})
    return enriched


def _fetch_page_snippet(url: str) -> str:
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.extract()
        text = " ".join(soup.stripped_strings)
        return text[:MAX_SNIPPET_CHARS] if text else ""
    except Exception as error:
        logger.debug("[GOOGLE AGENT] Failed to fetch snippet for %s: %s", url, error)
        return ""


def _summarize_results(query: str, results: List[Dict[str, str]]) -> str:
    if not results:
        return "No Google results found for the query."

    try:
        config = load_config()
        openai_cfg = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_cfg.get("model", "gpt-4o"),
            temperature=0.2,
            max_tokens=600,
            api_key=openai_cfg.get("api_key"),
        )

        bullet_lines = []
        for idx, item in enumerate(results[:5], start=1):
            bullet_lines.append(
                f"{idx}. {item['title']} ({item['display_link']}): {item['snippet']}"
            )
        bullet_text = "\n".join(bullet_lines)

        messages = [
            SystemMessage(
                content=(
                    "You summarize Google search results into a concise set of takeaways. "
                    "Use bullet points, reference result numbers when helpful, "
                    "and mention emerging themes or consensus."
                )
            ),
            HumanMessage(
                content=(
                    f"Query: {query}\n\n"
                    f"Results:\n{bullet_text}\n\n"
                    "Summarize the main findings in 3-5 bullet points."
                )
            ),
        ]

        response = llm.invoke(messages)
        summary = response.content.strip()
        if summary:
            return summary
    except Exception as error:
        logger.warning("[GOOGLE AGENT] LLM summary failed: %s", error)

    fallback = [f"- {item['title']} ({item['display_link']})" for item in results[:5]]
    return "Key findings:\n" + "\n".join(fallback)


# Google Agent Tool Registry
GOOGLE_AGENT_TOOLS = [
    google_search,
    google_search_images,
    google_search_site,
]


# Google Agent Hierarchy
GOOGLE_AGENT_HIERARCHY = """
Google Agent Hierarchy:
======================

LEVEL 1: Web Search
└─ google_search → Search Google via official API

LEVEL 2: Image Search
└─ google_search_images → Search Google Images

LEVEL 3: Site-Specific Search
└─ google_search_site → Search within specific domain

Typical Workflow:
1. google_search(query) → Get web results
2. google_search_images(query) → Get image results
3. google_search_site(query, site) → Search specific site

Key Features:
- googlesearch-python library (no API key required)
- Web scraping-based searches
- Fast and reliable
- Rich metadata (snippets, links, titles)
- No API setup needed!

Setup Required:
- pip install googlesearch-python
- That's it! No API keys needed.
"""


class GoogleAgent:
    """
    Google Agent - Google search integration (no API key required).

    Responsibilities:
    - Web search via googlesearch-python
    - Image search (limited support)
    - Site-specific searches
    - Structured result parsing

    This agent uses googlesearch-python library for web scraping.
    No API keys required - just install the library!
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in GOOGLE_AGENT_TOOLS}
        logger.info(f"[GOOGLE AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        """Get all Google agent tools."""
        return GOOGLE_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get Google agent hierarchy documentation."""
        return GOOGLE_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Google agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Google agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[GOOGLE AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[GOOGLE AGENT] Execution error: {e}", exc_info=True)
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }
