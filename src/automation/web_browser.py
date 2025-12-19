"""
Web browser automation using Playwright.

Provides LLM-driven web browsing capabilities:
- Navigate to URLs
- Search Google
- Extract page content
- Click elements
- Fill forms
- Take screenshots
"""

import logging
import asyncio
import threading
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import random
import tempfile
import uuid


logger = logging.getLogger(__name__)


def _random_user_agent() -> str:
    """Generate a realistic desktop user-agent string to vary browser fingerprints."""
    chrome_major = random.randint(118, 130)
    safari_patch = random.randint(1, 40)
    mac_minor = random.randint(1, 6)
    template = random.choice([
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_{minor}) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/{chrome}.0.0.{patch} Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_{minor}_{patch}) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_{minor}_{patch}) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/{chrome}.0.{build}.0 Safari/537.36",
    ])
    return template.format(
        minor=mac_minor,
        patch=safari_patch,
        chrome=chrome_major,
        build=random.randint(4200, 6900)
    )


def _random_viewport() -> Dict[str, int]:
    """Return a random but reasonable desktop viewport size."""
    return {
        "width": random.randint(1200, 1440),
        "height": random.randint(720, 900)
    }


class WebBrowser:
    """
    Web browser automation using Playwright.

    Provides high-level browser operations that can be chained together
    for complex web automation tasks.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        headless: bool = True,
        unique_session: bool = False,
        session_id: Optional[str] = None
    ):
        """
        Initialize web browser.

        Args:
            config: Configuration dictionary
            headless: Run browser in headless mode (default: True)
            unique_session: If True, create an isolated browser profile per instance
            session_id: Optional identifier for session logging
        """
        self.config = config
        self.headless = headless
        self.unique_session = unique_session
        self.session_id = session_id or (f"session-{uuid.uuid4().hex}" if unique_session else None)
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self._session_tmp_dir = None

    async def initialize(self):
        """Initialize Playwright browser."""
        try:
            from playwright.async_api import async_playwright

            self.playwright = await async_playwright().start()
            browser_config = self.config.get("browser", {}) or {}

            # Let config override headless setting if provided
            headless = browser_config.get("headless", self.headless)
            launch_kwargs: Dict[str, Any] = {"headless": headless}

            if browser_config.get("proxy"):
                launch_kwargs["proxy"] = browser_config["proxy"]
            if browser_config.get("slow_mo"):
                launch_kwargs["slow_mo"] = browser_config["slow_mo"]

            context_kwargs: Dict[str, Any] = {}
            if browser_config.get("viewport"):
                context_kwargs["viewport"] = browser_config["viewport"]
            if browser_config.get("user_agent"):
                context_kwargs["user_agent"] = browser_config["user_agent"]
            if browser_config.get("locale"):
                context_kwargs["locale"] = browser_config["locale"]

            if self.unique_session:
                # Ensure every session has a fresh profile + randomized fingerprint
                context_kwargs.setdefault("user_agent", _random_user_agent())
                context_kwargs.setdefault("viewport", _random_viewport())
                context_kwargs.setdefault("locale", browser_config.get("locale", "en-US"))

                self._session_tmp_dir = tempfile.TemporaryDirectory(prefix="browser_session_")
                persistent_kwargs = {**launch_kwargs, **context_kwargs}

                self.context = await self.playwright.chromium.launch_persistent_context(
                    self._session_tmp_dir.name,
                    **persistent_kwargs
                )
                self.browser = None
            else:
                self.browser = await self.playwright.chromium.launch(**launch_kwargs)
                self.context = await self.browser.new_context(**context_kwargs)

            self.page = await self.context.new_page()

            logger.info("Playwright browser initialized")
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install")
            raise

    async def close(self):
        """Close browser."""
        if self.page:
            self.page = None
        if self.context:
            await self.context.close()
            self.context = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        if self._session_tmp_dir:
            self._session_tmp_dir.cleanup()
            self._session_tmp_dir = None
        logger.info("Browser closed")

    async def navigate(self, url: str, wait_until: str = "load", timeout: int = 30000) -> Dict[str, Any]:
        """
        Navigate to a URL.

        Args:
            url: URL to navigate to
            wait_until: When to consider navigation complete ("load", "domcontentloaded", "networkidle")
            timeout: Navigation timeout in milliseconds (default: 30000 = 30 seconds)

        Returns:
            Dictionary with navigation result
        """
        try:
            logger.info(f"Navigating to: {url}")

            if not self.page:
                await self.initialize()

            response = await self.page.goto(url, wait_until=wait_until, timeout=timeout)

            return {
                "success": True,
                "url": self.page.url,
                "title": await self.page.title(),
                "status": response.status if response else None
            }
        except Exception as e:
            logger.error(f"Navigation error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def google_search(self, query: str, num_results: int = 5) -> Dict[str, Any]:
        """
        Perform a Google search and extract results.

        Args:
            query: Search query
            num_results: Number of results to extract (default: 5)

        Returns:
            Dictionary with search results
        """
        try:
            logger.info(f"Searching Google for: '{query}'")

            if not self.page:
                await self.initialize()

            # Navigate to Google
            await self.page.goto("https://www.google.com")

            # Accept cookies if present
            try:
                accept_button = await self.page.wait_for_selector('button:has-text("Accept all")', timeout=2000)
                if accept_button:
                    await accept_button.click()
            except:
                pass  # Cookie dialog not present

            # Search
            search_box = await self.page.wait_for_selector('textarea[name="q"], input[name="q"]')
            await search_box.fill(query)
            await search_box.press("Enter")

            # Wait for results (try multiple selectors as Google changes structure)
            try:
                await self.page.wait_for_selector("div#search", timeout=5000)
            except:
                try:
                    await self.page.wait_for_selector("div#rso", timeout=5000)
                except:
                    # Just wait a bit and proceed
                    import asyncio
                    await asyncio.sleep(3)

            # Extract results
            results = []
            search_results = await self.page.query_selector_all("div.g")

            for i, result in enumerate(search_results[:num_results]):
                try:
                    # Extract title
                    title_elem = await result.query_selector("h3")
                    title = await title_elem.inner_text() if title_elem else "No title"

                    # Extract link
                    link_elem = await result.query_selector("a")
                    link = await link_elem.get_attribute("href") if link_elem else None

                    # Extract snippet
                    snippet_elem = await result.query_selector("div.VwiC3b, div[data-sncf]")
                    snippet = await snippet_elem.inner_text() if snippet_elem else ""

                    if link:
                        results.append({
                            "position": i + 1,
                            "title": title,
                            "link": link,
                            "snippet": snippet
                        })
                except Exception as e:
                    logger.warning(f"Error extracting result {i}: {e}")
                    continue

            logger.info(f"Extracted {len(results)} search results")

            return {
                "success": True,
                "query": query,
                "results": results,
                "num_results": len(results)
            }

        except Exception as e:
            logger.error(f"Google search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": []
            }

    async def extract_content(self, use_langextract: bool = True) -> Dict[str, Any]:
        """
        Extract text content from current page.

        Args:
            use_langextract: Use langextract for better content extraction (default: True)

        Returns:
            Dictionary with extracted content
        """
        try:
            if not self.page:
                return {"success": False, "error": "No page loaded"}

            url = self.page.url
            title = await self.page.title()

            if use_langextract:
                # Use langextract for better content extraction
                try:
                    from langextract import LangExtract

                    # Get page HTML
                    html_content = await self.page.content()

                    # Extract with langextract
                    extractor = LangExtract()
                    extracted = extractor.extract(html_content)

                    return {
                        "success": True,
                        "url": url,
                        "title": title,
                        "content": extracted.get("text", ""),
                        "metadata": {
                            "word_count": len(extracted.get("text", "").split()),
                            "language": extracted.get("language"),
                            "method": "langextract"
                        }
                    }
                except ImportError:
                    logger.warning("langextract not installed, falling back to basic extraction")
                    use_langextract = False

            if not use_langextract:
                # Fallback: Basic text extraction
                # Remove script and style elements
                await self.page.evaluate("""
                    () => {
                        const scripts = document.querySelectorAll('script, style, nav, header, footer');
                        scripts.forEach(el => el.remove());
                    }
                """)

                # Get main text content
                text_content = await self.page.evaluate("""
                    () => {
                        const article = document.querySelector('article, main, .content, #content');
                        if (article) {
                            return article.innerText;
                        }
                        return document.body.innerText;
                    }
                """)

                return {
                    "success": True,
                    "url": url,
                    "title": title,
                    "content": text_content,
                    "metadata": {
                        "word_count": len(text_content.split()),
                        "method": "basic"
                    }
                }

        except Exception as e:
            logger.error(f"Content extraction error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def take_screenshot(self, path: Optional[str] = None, full_page: bool = False) -> Dict[str, Any]:
        """
        Take a screenshot of current page.

        Args:
            path: Path to save screenshot (default: temp file)
            full_page: Capture full scrollable page (default: False)

        Returns:
            Dictionary with screenshot path
        """
        try:
            if not self.page:
                return {"success": False, "error": "No page loaded"}

            if not path:
                import tempfile
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                path = temp_file.name
                temp_file.close()

            await self.page.screenshot(path=path, full_page=full_page)

            logger.info(f"Screenshot saved to: {path}")

            return {
                "success": True,
                "screenshot_path": path,
                "url": self.page.url,
                "full_page": full_page
            }

        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def click_element(self, selector: str) -> Dict[str, Any]:
        """
        Click an element on the page.

        Args:
            selector: CSS selector for element to click

        Returns:
            Dictionary with click result
        """
        try:
            if not self.page:
                return {"success": False, "error": "No page loaded"}

            await self.page.click(selector)

            logger.info(f"Clicked element: {selector}")

            return {
                "success": True,
                "selector": selector,
                "url": self.page.url
            }

        except Exception as e:
            logger.error(f"Click error: {e}")
            return {
                "success": False,
                "error": str(e),
                "selector": selector
            }

    async def fill_form(self, fields: Dict[str, str]) -> Dict[str, Any]:
        """
        Fill form fields.

        Args:
            fields: Dictionary mapping CSS selectors to values

        Returns:
            Dictionary with form fill result
        """
        try:
            if not self.page:
                return {"success": False, "error": "No page loaded"}

            filled_fields = []
            for selector, value in fields.items():
                await self.page.fill(selector, value)
                filled_fields.append(selector)
                logger.info(f"Filled field: {selector}")

            return {
                "success": True,
                "fields_filled": filled_fields,
                "url": self.page.url
            }

        except Exception as e:
            logger.error(f"Form fill error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Synchronous wrapper functions for use in LangChain tools
def run_async(coro, loop: Optional[asyncio.AbstractEventLoop] = None):
    """
    Run async function synchronously.
    
    Args:
        coro: Coroutine to run
        loop: Optional event loop to use. If provided, uses this loop.
              If None, tries to get current loop or creates a new one.
    
    Returns:
        Result of the coroutine
    """
    if loop is not None:
        # Use provided loop - thread-safe execution via run_coroutine_threadsafe
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()
    
    # Fallback to original behavior for backward compatibility
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Loop is running, can't use run_until_complete
            # Create new loop in thread
            import threading
            result_container = []
            exception_container = []
            
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result_container.append(new_loop.run_until_complete(coro))
                except Exception as e:
                    exception_container.append(e)
                finally:
                    new_loop.close()
            
            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()
            
            if exception_container:
                raise exception_container[0]
            return result_container[0]
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


class SyncWebBrowser:
    """Synchronous wrapper for WebBrowser (for use in tools)."""

    def __init__(
        self,
        config: Dict[str, Any],
        headless: bool = True,
        unique_session: bool = False,
        session_id: Optional[str] = None
    ):
        self.browser = WebBrowser(
            config,
            headless,
            unique_session=unique_session,
            session_id=session_id
        )
        self._initialized = False
        
        # Create dedicated event loop in a background thread for Playwright operations
        # This ensures all Playwright operations use the same event loop,
        # preventing "future belongs to different loop" errors
        self._loop = None
        self._loop_thread = None
        self._loop_ready = threading.Event()
        self._create_dedicated_loop()

    def _create_dedicated_loop(self):
        """Create a dedicated event loop in a background thread for Playwright operations."""
        loop_container = []
        
        def run_loop():
            """Run the event loop in this thread."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop_container.append(loop)
            self._loop_ready.set()
            loop.run_forever()
        
        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()
        # Wait for loop to be ready
        if not self._loop_ready.wait(timeout=5.0):
            raise RuntimeError("Failed to create dedicated event loop for Playwright")
        # Now we can safely access the loop
        self._loop = loop_container[0]

    def _ensure_initialized(self):
        if not self._initialized:
            # Wait for loop to be ready before initializing
            self._loop_ready.wait()
            run_async(self.browser.initialize(), loop=self._loop)
            self._initialized = True

    def navigate(self, url: str, wait_until: str = "domcontentloaded") -> Dict[str, Any]:
        self._ensure_initialized()
        return run_async(self.browser.navigate(url, wait_until=wait_until), loop=self._loop)

    def google_search(self, query: str, num_results: int = 5) -> Dict[str, Any]:
        self._ensure_initialized()
        return run_async(self.browser.google_search(query, num_results), loop=self._loop)

    def extract_content(self) -> Dict[str, Any]:
        self._ensure_initialized()
        return run_async(self.browser.extract_content(), loop=self._loop)

    def take_screenshot(self, path: Optional[str] = None, full_page: bool = False) -> Dict[str, Any]:
        self._ensure_initialized()
        return run_async(self.browser.take_screenshot(path, full_page), loop=self._loop)

    def get_page_content(self) -> str:
        """Get the HTML content of the current page."""
        self._ensure_initialized()
        return run_async(self.browser.page.content(), loop=self._loop)

    def query_selector(self, selector: str):
        """Query selector on the page."""
        self._ensure_initialized()
        return run_async(self.browser.page.query_selector(selector), loop=self._loop)

    def query_selector_all(self, selector: str):
        """Query selector all on the page."""
        self._ensure_initialized()
        return run_async(self.browser.page.query_selector_all(selector), loop=self._loop)

    def evaluate(self, expression: str):
        """Evaluate JavaScript expression on the page."""
        self._ensure_initialized()
        return run_async(self.browser.page.evaluate(expression), loop=self._loop)

    def locator(self, selector: str):
        """Get a locator for the selector."""
        self._ensure_initialized()
        return self.browser.page.locator(selector)

    def get_url(self) -> str:
        """Get the current page URL."""
        self._ensure_initialized()
        return self.browser.page.url

    @property
    def page(self):
        """Access the underlying Playwright page object."""
        self._ensure_initialized()
        return self.browser.page

    def close(self):
        """Close browser and cleanup dedicated event loop."""
        if self._initialized:
            run_async(self.browser.close(), loop=self._loop)
            self._initialized = False
        
        # Cleanup dedicated event loop
        if self._loop is not None:
            # Schedule loop stop
            self._loop.call_soon_threadsafe(self._loop.stop)
            # Wait for thread to finish (with timeout)
            if self._loop_thread and self._loop_thread.is_alive():
                self._loop_thread.join(timeout=5.0)
            self._loop = None
            self._loop_thread = None
