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
from ..utils.message_personality import get_bluesky_post_message
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

    from ..utils import get_llm_params

    # Get LLM parameters that work with both gpt-4o and o4-mini
    llm_params = get_llm_params(config, default_temperature=0.2, max_tokens=700)
    llm = ChatOpenAI(**llm_params)

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
def get_bluesky_author_feed(actor: Optional[str] = None, max_posts: int = 10) -> Dict[str, Any]:
    """
    Get posts from a specific Bluesky author/handle. If actor is None, gets posts from authenticated user.

    Args:
        actor: Bluesky handle (e.g., "username.bsky.social") or None for authenticated user.
        max_posts: Maximum number of posts to return (default 10, max 100).
    """
    limit = max(1, min(max_posts or 10, 100))

    try:
        client = BlueskyAPIClient()
        raw = client.get_author_feed(actor=actor, limit=limit)
    except BlueskyAPIError as exc:
        return {
            "error": True,
            "error_type": "BlueskyAPIError",
            "error_message": str(exc),
            "retry_possible": True,
        }
    except Exception as exc:
        logger.exception("Unexpected Bluesky author feed error")
        return {
            "error": True,
            "error_type": "BlueskyClientError",
            "error_message": str(exc),
            "retry_possible": False,
        }

    # Author feed returns {"feed": [{"post": {...}, "reply": {...}, ...}]}
    # We need to extract the "post" from each feed item
    feed_items = raw.get("feed", [])
    posts = []
    actor_handle = actor
    
    for feed_item in feed_items:
        # Feed items have structure: {"post": {...}, "reply": {...}, ...}
        post_data = feed_item.get("post", feed_item)  # Fallback to feed_item if no "post" key
        normalized = _normalize_post(post_data)
        posts.append(normalized)
        # Extract actor handle from first post if not provided
        if not actor_handle and normalized.get("author_handle"):
            actor_handle = normalized.get("author_handle")

    return {
        "actor": actor_handle or "authenticated user",
        "count": len(posts),
        "posts": posts,
    }


@tool
def summarize_bluesky_posts(
    query: str,
    lookback_hours: Optional[int] = None,
    max_items: Optional[int] = None,
    actor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Summarize top Bluesky posts for a search query or from a specific author within an optional time window.
    If query contains patterns like "last N tweets" or "my tweets", fetches from authenticated user's feed.

    Args:
        query: Search keywords or phrase to focus on, or patterns like "last 3 tweets", "my tweets".
        lookback_hours: Time window to filter posts (defaults to bluesky.default_lookback_hours or 24).
        max_items: Maximum number of highlights to summarize (defaults to bluesky.max_summary_items or 5).
        actor: Optional Bluesky handle to get posts from specific user instead of searching.
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

    # Detect if query is asking for author feed (e.g., "last 3 tweets", "my tweets", "tweets on bluesky")
    query_lower = query.lower().strip()
    use_author_feed = False
    target_actor = actor
    disable_time_filter = False  # For "last N tweets", don't filter by time
    
    # Patterns that indicate author feed request
    author_feed_patterns = [
        "last",
        "my tweets",
        "my posts",
        "tweets on bluesky",
        "posts on bluesky",
        "recent tweets",
        "recent posts",
    ]
    
    # Check if query matches author feed patterns
    if any(pattern in query_lower for pattern in author_feed_patterns):
        use_author_feed = True
        # Extract number if present (e.g., "last 3 tweets" -> 3)
        import re
        num_match = re.search(r'(\d+)', query_lower)
        if num_match:
            max_highlights = min(int(num_match.group(1)), max_highlights)
        # For "last N tweets" queries, disable time filtering
        if "last" in query_lower:
            disable_time_filter = True

    try:
        client = BlueskyAPIClient()
        
        if use_author_feed or target_actor is not None:
            # Get posts from author feed
            raw = client.get_author_feed(actor=target_actor, limit=max_highlights * 2)
            # Author feed returns {"feed": [{"post": {...}, ...}]}
            feed_items = raw.get("feed", [])
            posts = []
            for feed_item in feed_items:
                post_data = feed_item.get("post", feed_item)  # Fallback to feed_item if no "post" key
                posts.append(_normalize_post(post_data))
        else:
            # Search posts
            raw = client.search_posts(query.strip(), limit=max_highlights * 5)
            posts = [_normalize_post(post) for post in raw.get("posts", [])]
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

    # Apply time filter only if not disabled (e.g., for "last N tweets" queries)
    if lookback and not disable_time_filter:
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

    # Sort by creation date (most recent first) for author feeds, by score for search
    if use_author_feed or target_actor is not None:
        posts.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    else:
        posts.sort(key=lambda item: (item["score"], item.get("created_at", "")), reverse=True)
    
    # Extract exact count if user requested "last N tweets"
    requested_count = None
    if use_author_feed and "last" in query_lower:
        import re
        num_match = re.search(r'(\d+)', query_lower)
        if num_match:
            requested_count = int(num_match.group(1))
            # Ensure we return EXACTLY the requested count
            highlights = posts[:requested_count]
            logger.info(f"[BLUESKY AGENT] User requested last {requested_count} tweets, returning exactly {len(highlights)} posts")
        else:
            highlights = posts[:max_highlights]
    else:
        highlights = posts[:max_highlights]
    
    # Validate count accuracy for "last N tweets" queries
    if requested_count is not None:
        if len(highlights) != requested_count:
            logger.warning(f"[BLUESKY AGENT] ⚠️  Count mismatch: requested {requested_count}, got {len(highlights)}")
            # Try to get more posts if we don't have enough
            if len(highlights) < requested_count and len(posts) >= requested_count:
                highlights = posts[:requested_count]
                logger.info(f"[BLUESKY AGENT] Expanded highlights to match requested count: {len(highlights)}")
            elif len(highlights) < requested_count:
                logger.warning(f"[BLUESKY AGENT] ⚠️  Only {len(highlights)} posts available, requested {requested_count}")
    
    # Validate chronological order (most recent first)
    if highlights:
        timestamps = [item.get("created_at", "") for item in highlights if item.get("created_at")]
        if len(timestamps) > 1:
            # Check if sorted descending (most recent first)
            try:
                parsed_times = [datetime.fromisoformat(ts.replace("Z", "+00:00")) for ts in timestamps]
                is_descending = all(parsed_times[i] >= parsed_times[i+1] for i in range(len(parsed_times)-1))
                if not is_descending:
                    logger.warning(f"[BLUESKY AGENT] ⚠️  Posts not in chronological order (most recent first)")
            except Exception as e:
                logger.warning(f"[BLUESKY AGENT] Could not validate chronological order: {e}")

    summary_text = _summarize_posts(config, highlights)

    return {
        "summary": summary_text,
        "items": highlights,
        "count": len(highlights),
        "requested_count": requested_count,
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

        uri = (response.get("uri") or response.get("record", {}).get("uri") or "")
        cid = (response.get("cid") or response.get("record", {}).get("cid") or "")

        # Prefer the authenticated handle, but fall back gracefully.
        handle = ""
        if hasattr(client, "get_my_handle"):
            try:
                handle = client.get_my_handle() or ""
            except Exception:
                handle = ""
        if not handle:
            handle = getattr(client, "handle", None) or getattr(client, "identifier", "") or ""

        url = _post_url(handle, uri) if uri and handle else ""
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

    return {
        "success": True,
        "uri": uri,
        "cid": cid,
        "url": url,
        "message": get_bluesky_post_message(),
    }


BLUESKY_AGENT_TOOLS = [
    search_bluesky_posts,
    get_bluesky_author_feed,
    summarize_bluesky_posts,
    post_bluesky_update,
]

BLUESKY_AGENT_HIERARCHY = """
Bluesky Agent Hierarchy:
=======================

LEVEL 1: Discovery
└─ search_bluesky_posts(query, max_posts=10) → Search public posts for a query
└─ get_bluesky_author_feed(actor=None, max_posts=10) → Get posts from specific author or authenticated user

LEVEL 2: Summaries
└─ summarize_bluesky_posts(query, lookback_hours=24, max_items=5, actor=None) → Gather + summarize top posts or author feed

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
