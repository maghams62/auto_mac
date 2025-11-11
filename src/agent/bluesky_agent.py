"""
Bluesky Agent - Search, summarize, and publish posts via AT Protocol.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from ..integrations.bluesky_client import BlueskyAPIClient, BlueskyAPIError
from ..utils import load_config

logger = logging.getLogger(__name__)


def _score_post(post: Dict[str, Any]) -> float:
    """Heuristic score combining reposts, likes, replies, and quotes."""
    reposts = post.get("repost_count", 0)
    likes = post.get("like_count", 0)
    replies = post.get("reply_count", 0)
    quotes = post.get("quote_count", 0)
    return (reposts * 2.0) + likes + (replies * 1.5) + (quotes * 1.5)


def _post_url(handle: str, uri: str) -> str:
    """Convert a AT Protocol URI into a public Bluesky URL."""
    if not uri:
        return ""
    post_id = uri.split("/")[-1]
    return f"https://bsky.app/profile/{handle}/post/{post_id}"


def _summarize_posts(config: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
    if not items:
        return "No posts were available to summarize."

    openai_config = config.get("openai") or {}
    llm = ChatOpenAI(
        model=openai_config.get("model", "gpt-4o"),
        temperature=0.2,
        max_tokens=700,
        api_key=openai_config.get("api_key"),
    )

    formatted = []
    for idx, item in enumerate(items, start=1):
        formatted.append(
            f"[{idx}] {item['author_name']} (@{item['author_handle']}) on {item['created_at']}: "
            f"{item['text']}\nURL: {item['url']}"
        )
    posts_block = "\n\n".join(formatted)

    system_text = (
        "You summarize Bluesky social posts. Produce concise narratives followed by actionable bullet points."
    )
    human_text = (
        "Summarize the most important insights from the Bluesky posts below.\n"
        "Output markdown with:\n"
        "1. A short paragraph overview referencing post numbers in brackets.\n"
        "2. A bullet list of key takeaways (each referencing post numbers like [1], [2]).\n"
        "3. A 'Links' section listing each URL with a short label.\n\n"
        f"POSTS:\n{posts_block}"
    )

    response = llm.invoke([
        SystemMessage(content=system_text),
        HumanMessage(content=human_text),
    ])
    return response.content


def _normalize_post(raw_post: Dict[str, Any]) -> Dict[str, Any]:
    author = raw_post.get("author", {}) or {}
    record = raw_post.get("record", {}) or {}

    created_at = record.get("createdAt") or raw_post.get("indexedAt")
    if created_at and created_at.endswith("Z"):
        created_at_fmt = created_at
    else:
        created_at_fmt = created_at or ""

    text = record.get("text", "").strip()
    handle = author.get("handle", "")
    data = {
        "uri": raw_post.get("uri"),
        "cid": raw_post.get("cid"),
        "text": text,
        "created_at": created_at_fmt,
        "author_handle": handle,
        "author_name": author.get("displayName") or handle,
        "like_count": raw_post.get("likeCount", 0),
        "repost_count": raw_post.get("repostCount", 0),
        "reply_count": raw_post.get("replyCount", 0),
        "quote_count": raw_post.get("quoteCount", 0),
    }
    data["score"] = _score_post(data)
    data["url"] = _post_url(handle, data["uri"] or "")
    return data


def _filter_by_time(posts: List[Dict[str, Any]], lookback_hours: int) -> List[Dict[str, Any]]:
    if lookback_hours <= 0:
        return posts

    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    filtered = []
    for post in posts:
        ts = post.get("created_at")
        if not ts:
            filtered.append(post)
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            filtered.append(post)
            continue
        if dt >= cutoff:
            filtered.append(post)
    return filtered


@tool
def search_bluesky_posts(query: str, max_posts: int = 10) -> Dict[str, Any]:
    """
    Search public Bluesky posts matching a query term.

    Args:
        query: Search keywords or phrase.
        max_posts: Maximum number of posts to return (default 10, max 50).
    """
    if not query or not query.strip():
        return {
            "error": True,
            "error_type": "InvalidInput",
            "error_message": "Search query cannot be empty.",
            "retry_possible": False,
        }

    limit = max(1, min(max_posts or 10, 50))

    try:
        client = BlueskyAPIClient()
        raw = client.search_posts(query.strip(), limit=limit)
    except BlueskyAPIError as exc:
        return {
            "error": True,
            "error_type": "BlueskyAPIError",
            "error_message": str(exc),
            "retry_possible": True,
        }
    except Exception as exc:
        logger.exception("Unexpected Bluesky search error")
        return {
            "error": True,
            "error_type": "BlueskyClientError",
            "error_message": str(exc),
            "retry_possible": False,
        }

    posts = [_normalize_post(post) for post in raw.get("posts", [])]

    return {
        "query": query.strip(),
        "count": len(posts),
        "posts": posts,
    }


@tool
def summarize_bluesky_posts(
    query: str,
    lookback_hours: Optional[int] = None,
    max_items: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Summarize top Bluesky posts for a search query within an optional time window.

    Args:
        query: Search keywords or phrase to focus on.
        lookback_hours: Time window to filter posts (defaults to bluesky.default_lookback_hours or 24).
        max_items: Maximum number of highlights to summarize (defaults to bluesky.max_summary_items or 5).
    """
    if not query or not query.strip():
        return {
            "error": True,
            "error_type": "InvalidInput",
            "error_message": "Summary query cannot be empty.",
            "retry_possible": False,
        }

    try:
        config = load_config()
    except Exception as exc:
        return {
            "error": True,
            "error_type": "ConfigError",
            "error_message": f"Unable to load configuration: {exc}",
            "retry_possible": False,
        }

    bluesky_cfg = config.get("bluesky") or {}
    default_lookback = bluesky_cfg.get("default_lookback_hours", 24)
    default_max_items = bluesky_cfg.get("max_summary_items", 5)

    lookback = lookback_hours if lookback_hours is not None else default_lookback
    lookback = max(0, min(lookback, 168))

    max_highlights = max_items if max_items is not None else default_max_items
    max_highlights = max(1, min(max_highlights, 10))

    try:
        client = BlueskyAPIClient()
        raw = client.search_posts(query.strip(), limit=max_highlights * 5)
    except BlueskyAPIError as exc:
        return {
            "error": True,
            "error_type": "BlueskyAPIError",
            "error_message": str(exc),
            "retry_possible": True,
        }
    except Exception as exc:
        logger.exception("Unexpected Bluesky summary error")
        return {
            "error": True,
            "error_type": "BlueskyClientError",
            "error_message": str(exc),
            "retry_possible": False,
        }

    posts = [_normalize_post(post) for post in raw.get("posts", [])]
    if lookback:
        posts = _filter_by_time(posts, lookback)

    if not posts:
        return {
            "summary": "No posts were found for the requested query and timeframe.",
            "items": [],
            "query": query.strip(),
            "time_window": {
                "hours": lookback,
            },
        }

    posts.sort(key=lambda item: (item["score"], item.get("created_at", "")), reverse=True)
    highlights = posts[:max_highlights]

    summary_text = _summarize_posts(config, highlights)

    return {
        "summary": summary_text,
        "items": highlights,
        "query": query.strip(),
        "time_window": {
            "hours": lookback,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
    }


@tool
def post_bluesky_update(message: str) -> Dict[str, Any]:
    """
    Publish a new Bluesky post on behalf of the configured account.

    Args:
        message: Post content (must be <= 300 characters).
    """
    if not message or not message.strip():
        return {
            "error": True,
            "error_type": "InvalidInput",
            "error_message": "Post message cannot be empty.",
            "retry_possible": False,
        }

    clean_text = message.strip()
    if len(clean_text) > 300:
        return {
            "error": True,
            "error_type": "InvalidInput",
            "error_message": "Bluesky posts cannot exceed 300 characters.",
            "retry_possible": False,
        }

    try:
        client = BlueskyAPIClient()
        response = client.create_post(clean_text)
    except BlueskyAPIError as exc:
        return {
            "error": True,
            "error_type": "BlueskyAPIError",
            "error_message": str(exc),
            "retry_possible": True,
        }
    except Exception as exc:
        logger.exception("Unexpected Bluesky post error")
        return {
            "error": True,
            "error_type": "BlueskyClientError",
            "error_message": str(exc),
            "retry_possible": False,
        }

    uri = (response.get("uri") or response.get("record", {}).get("uri") or "")
    cid = (response.get("cid") or response.get("record", {}).get("cid") or "")
    handle = response.get("handle")

    url = _post_url(handle or "", uri) if uri and handle else ""

    return {
        "success": True,
        "uri": uri,
        "cid": cid,
        "url": url,
        "message": "Bluesky post published successfully.",
    }


BLUESKY_AGENT_TOOLS = [
    search_bluesky_posts,
    summarize_bluesky_posts,
    post_bluesky_update,
]

BLUESKY_AGENT_HIERARCHY = """
Bluesky Agent Hierarchy:
=======================

LEVEL 1: Discovery
└─ search_bluesky_posts(query, max_posts=10) → Search public posts for a query

LEVEL 2: Summaries
└─ summarize_bluesky_posts(query, lookback_hours=24, max_items=5) → Gather + summarize top posts

LEVEL 3: Publishing
└─ post_bluesky_update(message) → Publish a post via AT Protocol
"""


class BlueskyAgent:
    """
    Orchestrates Bluesky search, summarization, and posting operations.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in BLUESKY_AGENT_TOOLS}
        logger.info(f"[BLUESKY AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        return BLUESKY_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        return BLUESKY_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Bluesky agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys()),
            }

        tool = self.tools[tool_name]
        try:
            return tool.invoke(inputs)
        except Exception as exc:
            logger.exception("Bluesky agent execution error")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(exc),
                "retry_possible": False,
            }
