"""
Reddit Agent - orchestrates subreddit scans + optional summaries.

This agent wraps the Playwright-based RedditScanner so planners can request
dynamic subreddit intelligence without touching low-level scraping logic.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Any, Optional, List

from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from src.utils import load_config
from src.automation.reddit_scanner import RedditScanner

logger = logging.getLogger(__name__)


def _get_scanner() -> RedditScanner:
    config = load_config()
    return RedditScanner(config)


def _summarize_posts(config: Dict[str, Any], instruction: str, payload: Dict[str, Any]) -> str:
    """Use the configured OpenAI model to summarize subreddit findings."""
    try:
        llm_config = config.get("openai", {})
        llm = ChatOpenAI(
            model=llm_config.get("model", "gpt-4o"),
            temperature=0.2,
            api_key=llm_config.get("api_key")
        )

        # Keep prompt compact: trim to top 6 posts / 2 comments each
        posts = payload.get("posts", [])[:6]
        slim_posts: List[Dict[str, Any]] = []
        for post in posts:
            entry = {
                "title": post.get("title"),
                "upvotes": post.get("upvotes"),
                "comments_count": post.get("comments_count"),
                "snippet": post.get("snippet"),
                "flair": post.get("flair"),
                "top_comments": [
                    {
                        "author": comment.get("author"),
                        "body": comment.get("body"),
                        "score": comment.get("score")
                    }
                    for comment in post.get("top_comments", [])[:2]
                ]
            }
            slim_posts.append(entry)

        system_prompt = (
            "You are a market research analyst. Use the provided Reddit scrape "
            "data to answer the user's instruction. Focus on concrete sentiments, "
            "pain points, and opportunities sourced from posts/comments."
        )

        human_prompt = (
            f"Instruction: {instruction}\n\n"
            f"Structured Reddit Data:\n{json.dumps(slim_posts, indent=2)}"
        )

        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])
        return response.content
    except Exception as exc:
        logger.error("[REDDIT AGENT] Summary generation failed: %s", exc)
        return f"Summary unavailable due to error: {exc}"


@tool
def scan_subreddit_posts(
    subreddit: str,
    instruction: Optional[str] = None,
    sort: str = "hot",
    limit_posts: int = 10,
    include_comments: bool = True,
    comments_limit: int = 5,
    comment_threads_limit: Optional[int] = None,
    headless: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Crawl a subreddit, returning structured post/comment data (and optional summary).

    Args:
        subreddit: Target subreddit (e.g., "startups", "SideProject")
        instruction: Optional natural-language question to summarize results
        sort: Reddit sort key ("hot", "new", "top", "rising", "controversial")
        limit_posts: Number of posts to return (default 10)
        include_comments: When True, fetch top-level comments for each post
        comments_limit: Max comments per post (default 5)
        comment_threads_limit: Limit how many posts include comment scraping
        headless: Override headless browser setting
    """
    logger.info("[REDDIT AGENT] scan_subreddit_posts(subreddit=%s, sort=%s)", subreddit, sort)

    scanner = _get_scanner()
    payload = scanner.scan_subreddit(
        subreddit=subreddit,
        sort=sort,
        limit_posts=limit_posts,
        include_comments=include_comments,
        comments_limit=comments_limit,
        comment_threads_limit=comment_threads_limit,
        headless=headless
    )

    if payload.get("error"):
        return payload

    if instruction:
        config = load_config()
        payload["analysis"] = _summarize_posts(config, instruction, payload)

    return payload


REDDIT_AGENT_TOOLS = [
    scan_subreddit_posts,
]


REDDIT_AGENT_HIERARCHY = """
Reddit Agent Hierarchy:
======================

LEVEL 1: Data Collection
└─ scan_subreddit_posts(subreddit, instruction?, sort?, limit_posts?, comments_limit?) → Playwright-powered scrape

Behavior:
- Navigates to the requested subreddit + sort view
- Scrolls to collect posts (title, author, upvotes, comment counts, snippet, flair)
- Optionally opens each post to grab top-level comments
- Returns structured JSON suitable for downstream analysis
- When "instruction" is provided, uses the configured OpenAI model to summarize findings
"""


class RedditAgent:
    """Mini-orchestrator for Reddit automation."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in REDDIT_AGENT_TOOLS}
        logger.info(f"[REDDIT AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        return REDDIT_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        return REDDIT_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Reddit agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[REDDIT AGENT] Executing tool: {tool_name}")

        try:
            return tool.invoke(inputs)
        except Exception as exc:
            logger.error(f"[REDDIT AGENT] Execution error: {exc}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(exc),
                "retry_possible": False
            }
