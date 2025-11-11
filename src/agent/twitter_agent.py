"""
Twitter Agent - Summarize list activity via official APIs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Dict, Any, List, Optional

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from ..utils import load_config
from ..integrations.twitter_client import TwitterAPIClient, isoformat, TwitterAPIError


logger = logging.getLogger(__name__)


def _score_tweet(metrics: Dict[str, Any]) -> float:
    if not metrics:
        return 0.0
    likes = metrics.get("like_count", 0)
    retweets = metrics.get("retweet_count", 0)
    replies = metrics.get("reply_count", 0)
    quotes = metrics.get("quote_count", 0)
    return likes + (retweets * 2) + (replies * 1.5) + (quotes * 1.5)


def _build_tweet_url(username: str, tweet_id: str) -> str:
    return f"https://twitter.com/{username}/status/{tweet_id}"


def _format_summary_prompt(items: List[Dict[str, Any]]) -> str:
    lines = []
    for idx, item in enumerate(items, start=1):
        lines.append(
            f"[{idx}] {item['author_name']} (@{item['author_handle']}) on {item['created_at']}: "
            f"{item['text']}\nURL: {item['url']}"
        )
    return "\n\n".join(lines)


def _summarize_with_llm(config: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
    if not items:
        return "No tweets were available to summarize."

    openai_config = config.get("openai", {})
    llm = ChatOpenAI(
        model=openai_config.get("model", "gpt-4o"),
        temperature=0.2,
        max_tokens=700,
        api_key=openai_config.get("api_key")
    )
    prompt = _format_summary_prompt(items)
    system_text = (
        "You are a helpful assistant that summarizes Twitter list activity. "
        "Produce a concise narrative followed by bullet takeaways referencing tweet numbers."
    )
    human_text = (
        "Summarize the most important points from the tweets below. "
        "Output markdown with:\n"
        "1. A short paragraph overview.\n"
        "2. A bullet list of key insights (include tweet references like [1], [2]).\n"
        "3. A 'Links' section listing tweet URLs with brief labels.\n\n"
        f"TWEETS:\n{prompt}"
    )

    response = llm.invoke([
        SystemMessage(content=system_text),
        HumanMessage(content=human_text),
    ])
    return response.content


def _gather_thread_text(client: TwitterAPIClient, tweet: Dict[str, Any], start_time_iso: str) -> str:
    conversation_id = tweet.get("conversation_id")
    if not conversation_id or conversation_id == tweet.get("id"):
        return tweet.get("text", "")

    try:
        convo = client.fetch_conversation(conversation_id, start_time_iso)
    except TwitterAPIError:
        return tweet.get("text", "")

    data = convo.get("data", [])
    if not data:
        return tweet.get("text", "")

    combined = sorted(data, key=lambda t: t.get("created_at", ""))
    return "\n".join(part.get("text", "") for part in combined)


@tool
def summarize_list_activity(
    list_name: Optional[str] = None,
    lookback_hours: Optional[int] = None,
    max_items: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Summarize top tweets/threads from a configured Twitter List.

    Args:
        list_name: Logical list key defined in config.yaml -> twitter.lists
            (defaults to twitter.default_list when omitted).
        lookback_hours: Time window to inspect (defaults to twitter.default_lookback_hours or 24).
        max_items: Maximum tweets/threads to highlight (defaults to twitter.max_summary_items or 5, max 10 overall).
    """
    try:
        config = load_config()
    except Exception as exc:
        return {
            "error": True,
            "error_type": "ConfigError",
            "error_message": f"Unable to load configuration: {exc}",
            "retry_possible": False,
        }

    twitter_cfg = config.get("twitter") or {}
    lists_map = twitter_cfg.get("lists") or {}
    default_list = twitter_cfg.get("default_list")

    effective_list = list_name or default_list

    if not effective_list:
        return {
            "error": True,
            "error_type": "ListNotFound",
            "error_message": "No Twitter list specified and twitter.default_list is not configured.",
            "retry_possible": False,
        }

    target_list_id = lists_map.get(effective_list)

    if not target_list_id:
        return {
            "error": True,
            "error_type": "ListNotFound",
            "error_message": f"Twitter list '{effective_list}' is not defined in config.yaml",
            "retry_possible": False,
        }

    default_lookback = twitter_cfg.get("default_lookback_hours", 24)
    requested_lookback = lookback_hours if lookback_hours is not None else default_lookback
    lookback = max(1, min(requested_lookback, 168))

    default_max_items = twitter_cfg.get("max_summary_items", 5)
    requested_max_items = max_items if max_items is not None else default_max_items
    effective_max_items = max(1, min(requested_max_items, 10))

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=lookback)
    start_time_iso = isoformat(start_time)

    try:
        client = TwitterAPIClient()
        # NOTE: Lists API doesn't support start_time parameter
        # We fetch recent tweets and filter client-side below (line 188)
        raw = client.fetch_list_tweets(target_list_id, start_time_iso)
    except TwitterAPIError as exc:
        return {
            "error": True,
            "error_type": "TwitterAPIError",
            "error_message": str(exc),
            "retry_possible": True,
        }
    except Exception as exc:
        logger.exception("Unexpected error initializing TwitterAPIClient")
        return {
            "error": True,
            "error_type": "TwitterClientError",
            "error_message": str(exc),
            "retry_possible": False,
        }

    tweets = raw.get("data", [])
    users = {u["id"]: u for u in raw.get("includes", {}).get("users", [])}
    if not tweets:
        return {
            "summary": "No tweets were posted in the requested window.",
            "items": [],
            "time_window": {"hours": lookback, "start": start_time_iso},
        }

    enriched: List[Dict[str, Any]] = []
    for tweet in tweets:
        created_at = tweet.get("created_at")
        # CLIENT-SIDE TIME FILTERING (Lists API doesn't support start_time parameter)
        if created_at and datetime.fromisoformat(created_at.replace("Z", "+00:00")) < start_time:
            continue

        author = users.get(tweet.get("author_id"), {})
        username = author.get("username", "unknown")
        author_name = author.get("name", username)
        thread_text = _gather_thread_text(client, tweet, start_time_iso)

        enriched.append({
            "id": tweet.get("id"),
            "text": thread_text or tweet.get("text", ""),
            "created_at": created_at,
            "score": _score_tweet(tweet.get("public_metrics", {})),
            "author_name": author_name,
            "author_handle": username,
            "url": _build_tweet_url(username, tweet.get("id", "")),
        })

    if not enriched:
        return {
            "summary": "No tweets were posted in the requested window.",
            "items": [],
            "time_window": {"hours": lookback, "start": start_time_iso},
        }

    enriched.sort(key=lambda item: (item["score"], item.get("created_at", "")), reverse=True)
    top_items = enriched[:effective_max_items]

    summary_text = _summarize_with_llm(config, top_items)

    return {
        "summary": summary_text,
        "items": top_items,
        "time_window": {
            "hours": lookback,
            "start": start_time_iso,
            "end": isoformat(now),
        },
        "list_name": effective_list,
    }


@tool
def tweet_message(message: str) -> Dict[str, Any]:
    """
    Publish a tweet with the provided message (must fit Twitter limits).
    """
    if not message or not message.strip():
        return {
            "error": True,
            "error_type": "InvalidInput",
            "error_message": "Tweet message cannot be empty.",
            "retry_possible": False,
        }

    trimmed = message.strip()
    if len(trimmed) > 280:
        return {
            "error": True,
            "error_type": "InvalidInput",
            "error_message": "Tweet message exceeds the 280 character limit.",
            "retry_possible": False,
        }

    try:
        client = TwitterAPIClient()
    except TwitterAPIError as exc:
        return {
            "error": True,
            "error_type": "TwitterAuthError",
            "error_message": str(exc),
            "retry_possible": False,
        }

    try:
        response = client.post_tweet(trimmed)
    except TwitterAPIError as exc:
        return {
            "error": True,
            "error_type": "TwitterAPIError",
            "error_message": str(exc),
            "retry_possible": True,
        }

    data = response.get("data", {})
    tweet_id = data.get("id")
    tweet_text = data.get("text", trimmed)
    tweet_url = None
    if tweet_id:
        # Posting endpoint returns author_id only on some tiers; construct URL when possible
        # We don't have the username, so link to tweet by ID if available.
        tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"

    return {
        "success": True,
        "tweet_id": tweet_id,
        "tweet_text": tweet_text,
        "tweet_url": tweet_url,
        "message": "Tweet posted successfully." if tweet_id else "Tweet request acknowledged.",
    }


TWITTER_AGENT_TOOLS = [
    summarize_list_activity,
    tweet_message,
]

TWITTER_AGENT_HIERARCHY = """
Twitter Agent Hierarchy:
=======================

LEVEL 1: List Summaries
└─ summarize_list_activity(list_name=None, lookback_hours=24, max_items=5)
     → Uses twitter.default_list when list_name omitted; fetches via API, expands threads, ranks, and summarizes with LLM.

LEVEL 2: Posting
└─ tweet_message(message) → Publish a tweet using configured user credentials.
"""


class TwitterAgent:
    """
    Twitter Agent - orchestrates Twitter list summarization operations.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in TWITTER_AGENT_TOOLS}
        logger.info(f"[TWITTER AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        return TWITTER_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        return TWITTER_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Twitter agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys()),
            }

        tool = self.tools[tool_name]
        try:
            return tool.invoke(inputs)
        except Exception as exc:
            logger.exception("Twitter agent execution error")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(exc),
                "retry_possible": False,
            }
