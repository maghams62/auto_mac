import os
import sys
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.bluesky_agent import (
    search_bluesky_posts,
    summarize_bluesky_posts,
    post_bluesky_update,
)


@pytest.fixture(autouse=True)
def bluesky_env(monkeypatch):
    monkeypatch.setenv("BLUESKY_USERNAME", "tester@example.com")
    monkeypatch.setenv("BLUESKY_PASSWORD", "app-password")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def _install_bluesky_stubs(monkeypatch, *, config, posts=None):
    """Helper to stub config, API client, and LLM interactions."""
    monkeypatch.setattr("src.agent.bluesky_agent.load_config", lambda: config)

    posts = posts or [
        {
            "uri": "at://did:plc:test/app.bsky.feed.post/1",
            "cid": "cid1",
            "author": {"handle": "builder", "displayName": "Builder"},
            "record": {
                "text": "Shipping the automation assistant.",
                "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            "likeCount": 10,
            "repostCount": 2,
            "replyCount": 1,
            "quoteCount": 0,
        },
        {
            "uri": "at://did:plc:test/app.bsky.feed.post/2",
            "cid": "cid2",
            "author": {"handle": "researcher", "displayName": "Researcher"},
            "record": {
                "text": "Deep dive on Bluesky APIs.",
                "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            "likeCount": 5,
            "repostCount": 1,
            "replyCount": 0,
            "quoteCount": 0,
        },
    ]

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def search_posts(self, query, limit=10, cursor=None):
            return {"posts": posts[:limit]}

        def create_post(self, text):
            return {
                "uri": "at://did:plc:test/app.bsky.feed.post/xyz",
                "cid": "mock-cid",
                "handle": "tester",
            }

    class DummyLLM:
        def __init__(self, *args, **kwargs):
            pass

        def invoke(self, messages):
            return SimpleNamespace(content="Summary\n\n- Highlight [1]\n\nLinks:\n- https://bsky.app/profile/builder/post/1")

    monkeypatch.setattr("src.agent.bluesky_agent.BlueskyAPIClient", DummyClient)
    monkeypatch.setattr("src.agent.bluesky_agent.ChatOpenAI", DummyLLM)


def test_search_bluesky_posts(monkeypatch):
    config = {
        "openai": {"model": "gpt-4o"},
        "bluesky": {
            "default_lookback_hours": 24,
            "max_summary_items": 5,
            "default_search_limit": 10,
        },
    }

    _install_bluesky_stubs(monkeypatch, config=config)

    result = search_bluesky_posts.invoke({"query": "automation", "max_posts": 2})
    assert result["count"] == 2
    assert result["posts"][0]["author_handle"] == "builder"
    assert result["posts"][0]["url"].startswith("https://bsky.app/profile/")


def test_summarize_bluesky_posts(monkeypatch):
    config = {
        "openai": {"model": "gpt-4o"},
        "bluesky": {
            "default_lookback_hours": 24,
            "max_summary_items": 5,
            "default_search_limit": 10,
        },
    }

    _install_bluesky_stubs(monkeypatch, config=config)

    result = summarize_bluesky_posts.invoke({"query": "automation", "lookback_hours": 12, "max_items": 2})
    assert "Summary" in result["summary"]
    assert len(result["items"]) <= 2
    assert result["items"][0]["author_handle"] == "builder"
    assert result["time_window"]["hours"] == 12


def test_post_bluesky_update(monkeypatch):
    config = {
        "openai": {"model": "gpt-4o"},
        "bluesky": {},
    }

    _install_bluesky_stubs(monkeypatch, config=config)

    result = post_bluesky_update.invoke({"message": "Hello Bluesky!"})
    assert result["success"] is True
    assert result["uri"].startswith("at://")
