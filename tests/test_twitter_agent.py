import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.twitter_agent import summarize_list_activity, tweet_message


@pytest.fixture(autouse=True)
def twitter_env(monkeypatch):
    monkeypatch.setenv("TWITTER_BEARER_TOKEN", "dummy-token")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("TWITTER_API_KEY", "dummy-api-key")
    monkeypatch.setenv("TWITTER_API_SECRET", "dummy-api-secret")
    monkeypatch.setenv("TWITTER_ACCESS_TOKEN", "dummy-access-token")
    monkeypatch.setenv("TWITTER_ACCESS_SECRET", "dummy-access-secret")


def _install_twitter_stubs(monkeypatch, *, config):
    """Helper to stub config, API client, and LLM for deterministic tests."""
    monkeypatch.setattr("src.agent.twitter_agent.load_config", lambda: config)

    def fake_fetch_list_tweets(self, list_id, start_time_iso):
        now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return {
            "data": [
                {
                    "id": "1",
                    "text": "Launch details.",
                    "author_id": "42",
                    "created_at": now_iso,
                    "conversation_id": "1",
                    "public_metrics": {"like_count": 10, "retweet_count": 2, "reply_count": 1, "quote_count": 0},
                }
            ],
            "includes": {
                "users": [
                    {"id": "42", "username": "maker", "name": "Builder"}
                ]
            }
        }

    def fake_fetch_conversation(self, conversation_id, start_time_iso, max_results=100):
        return {"data": []}

    class DummyLLM:
        def __init__(self, *args, **kwargs):
            pass

        def invoke(self, messages):
            return SimpleNamespace(content="Summary\n\n- Highlight [1]\n\nLinks:\n- https://twitter.com/maker/status/1")

    monkeypatch.setattr("src.agent.twitter_agent.TwitterAPIClient.fetch_list_tweets", fake_fetch_list_tweets)
    monkeypatch.setattr("src.agent.twitter_agent.TwitterAPIClient.fetch_conversation", fake_fetch_conversation)
    monkeypatch.setattr("src.agent.twitter_agent.ChatOpenAI", DummyLLM)


def test_summarize_list_activity(monkeypatch):
    config = {
        "openai": {"model": "gpt-4o"},
        "twitter": {
            "default_list": "product_watch",
            "default_lookback_hours": 24,
            "max_summary_items": 5,
            "lists": {"product_watch": "123"},
        },
    }

    _install_twitter_stubs(monkeypatch, config=config)

    result = summarize_list_activity.invoke({"list_name": "product_watch", "lookback_hours": 6, "max_items": 3})

    assert result["items"][0]["author_handle"] == "maker"
    assert "Summary" in result["summary"]
    assert result["list_name"] == "product_watch"
    assert result["time_window"]["hours"] == 6


def test_summarize_list_activity_defaults(monkeypatch):
    config = {
        "openai": {"model": "gpt-4o"},
        "twitter": {
            "default_list": "product_watch",
            "default_lookback_hours": 24,
            "max_summary_items": 4,
            "lists": {"product_watch": "123"},
        },
    }

    _install_twitter_stubs(monkeypatch, config=config)

    # Invoke without parameters; should fall back to config defaults
    result = summarize_list_activity.invoke({})

    assert result["list_name"] == "product_watch"
    assert result["time_window"]["hours"] == 24
    assert len(result["items"]) <= 4
    assert "Summary" in result["summary"]


def test_tweet_message(monkeypatch):
    config = {
        "openai": {"model": "gpt-4o"},
        "twitter": {
            "default_list": "product_watch",
            "lists": {"product_watch": "123"},
        },
    }

    monkeypatch.setattr("src.agent.twitter_agent.load_config", lambda: config)

    captured = {}

    def fake_post_tweet(self, text):
        captured["text"] = text
        return {"data": {"id": "999", "text": text}}

    monkeypatch.setattr("src.agent.twitter_agent.TwitterAPIClient.post_tweet", fake_post_tweet)

    result = tweet_message.invoke({"message": "Hello world!"})

    assert result["success"] is True
    assert result["tweet_id"] == "999"
    assert captured["text"] == "Hello world!"


def test_tweet_message_too_long():
    overlong = "a" * 281
    result = tweet_message.invoke({"message": overlong})
    assert result.get("error") is True
    assert result["error_type"] == "InvalidInput"
