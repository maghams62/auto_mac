"""
Search Agent - DuckDuckGo search integration (no API key required).

Note: the legacy tool name `google_search` is retained for backwards compatibility,
but the underlying implementation has always used DuckDuckGo's HTML endpoint.

This agent provides access to web search via DuckDuckGo's free interface:
- Free, no authentication required
- Fast and reliable
- Rich metadata (snippets, links, titles)
- No rate limits or anti-bot protection

Endpoint: https://html.duckduckgo.com/html/
"""

from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
import logging
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from ..utils import load_config, get_temperature_for_model

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
    Search the web using DuckDuckGo's free API (no API key required).

    SEARCH AGENT - LEVEL 1: Web Search
    Fast, reliable web searches using DuckDuckGo's free API.

    This tool uses DuckDuckGo's Instant Answer API which provides:
    - Free API-based searches (no authentication)
    - No rate limits or anti-bot protection
    - Fast response times
    - Rich metadata (snippets, links, titles)
    - Privacy-focused

    Args:
        query: Search query string
        num_results: Number of results to return (default: 5, max: 25)
        search_type: Type of search - "web" (default)

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
        - None! Just works out of the box.

    Example:
        google_search("Python async programming", num_results=10)
    """
    logger.info(f"[SEARCH AGENT] Tool: google_search (DuckDuckGo) query='{query}', num={num_results}, type={search_type}")

    try:
        # Validate parameters
        num_results = max(1, min(25, num_results))  # DuckDuckGo works best with <=25

        logger.info(f"[SEARCH AGENT] Executing DuckDuckGo search: {query}")

        # Use DuckDuckGo API (free, no auth required)
        results = _duckduckgo_search(query, num_results)

        if not results:
            logger.warning("[SEARCH AGENT] No results found from DuckDuckGo")
            return {
                "results": [],
                "total_results": 0,
                "query": query,
                "num_results": 0,
                "search_type": search_type,
                "source": "duckduckgo",
                "summary": "No search results found for the query.",
                "message": "No search results found for the query."
            }

        # Generate LLM summary
        summary = _summarize_results(query, results)

        logger.info(f"[SEARCH AGENT] Found {len(results)} results")

        return {
            "results": results,
            "total_results": len(results),
            "query": query,
            "num_results": len(results),
            "search_type": search_type,
            "source": "duckduckgo",
            "summary": summary,
            "message": summary
        }

    except Exception as e:
        logger.error(f"[SEARCH AGENT] Error in google_search: {e}", exc_info=True)
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
    Perform an image-oriented DuckDuckGo web search (query tweak only).

    SEARCH AGENT - LEVEL 2: Image-Oriented Search
    Note: DuckDuckGo HTML results do not provide direct image API access.
    This function simply biases the query toward images.

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
    Search within a specific website using DuckDuckGo's `site:` operator.

    SEARCH AGENT - LEVEL 3: Site-Specific Search
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


def _duckduckgo_search(query: str, num_results: int) -> List[Dict[str, str]]:
    """
    Search using DuckDuckGo's HTML interface (free, no API key).

    This uses the HTML version which is more reliable than the JSON API
    for getting multiple search results.
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    params = {"q": query, "kl": "us-en"}

    try:
        response = requests.post(
            "https://html.duckduckgo.com/html/",
            data=params,
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
    except Exception as error:
        logger.error(f"[SEARCH AGENT] DuckDuckGo request failed: {error}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    results: List[Dict[str, str]] = []

    # DuckDuckGo HTML results are in div.results_links
    for result_block in soup.select("div.result"):
        # Skip ads
        if "result--ad" in result_block.get("class", []):
            continue

        link_tag = result_block.select_one("a.result__a")
        title_tag = result_block.select_one("h2.result__title")
        snippet_tag = result_block.select_one("a.result__snippet")

        if not link_tag:
            continue

        url = link_tag.get("href", "")
        title = title_tag.get_text(strip=True) if title_tag else "No title"
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""

        # Skip if no valid URL
        if not url or not url.startswith("http"):
            continue

        results.append({
            "title": title,
            "link": url,
            "snippet": snippet,
            "display_link": _display_link(url),
        })

        if len(results) >= num_results:
            break

    logger.info(f"[SEARCH AGENT] DuckDuckGo returned {len(results)} results")
    return results


def _display_link(url: str) -> str:
    try:
        parsed = urlparse(url)
        return parsed.netloc or url
    except Exception:
        return url


def _summarize_results(query: str, results: List[Dict[str, str]]) -> str:
    if not results:
        return "No DuckDuckGo results found for the query."

    try:
        config = load_config()
        openai_cfg = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_cfg.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.2),
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
                    "You summarize DuckDuckGo search results into a concise set of takeaways. "
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


# DuckDuckGo Search Agent Tool Registry
GOOGLE_AGENT_TOOLS = [
    google_search,
    google_search_images,
    google_search_site,
]


# DuckDuckGo Search Agent Hierarchy
GOOGLE_AGENT_HIERARCHY = """
DuckDuckGo Search Agent Hierarchy:
=================================

LEVEL 1: Web Search
└─ google_search (DuckDuckGo) → Perform privacy-friendly web search

LEVEL 2: Image-Oriented Web Search
└─ google_search_images → Reuse web search with image-focused query

LEVEL 3: Site-Specific Search
└─ google_search_site → Constrain DuckDuckGo search to a specific domain

Typical Workflow:
1. google_search(query) → Gather web results from DuckDuckGo
2. google_search_images(query) → Fetch image-related pages via DuckDuckGo
3. google_search_site(query, site) → Search within a particular site

Key Features:
- No API keys required
- Fast, reliable DuckDuckGo HTML endpoint
- Rich metadata (snippets, links, titles)
- Privacy-focused results

Setup Required:
- `requests`
- `beautifulsoup4`
"""


class GoogleAgent:
    """
    DuckDuckGo-based search agent (legacy name retained for compatibility).

    Responsibilities:
    - Web search via DuckDuckGo HTML endpoint
    - Image-oriented searches by modifying the query
    - Site-specific searches
    - Structured result parsing

    No API keys required—uses `requests` + `BeautifulSoup` to parse results.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in GOOGLE_AGENT_TOOLS}
        logger.info(f"[GOOGLE AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        """Get all DuckDuckGo-backed search tools (legacy Google agent)."""
        return GOOGLE_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get DuckDuckGo search agent hierarchy documentation."""
        return GOOGLE_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a DuckDuckGo search agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Search agent tool '{tool_name}' not found",
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
