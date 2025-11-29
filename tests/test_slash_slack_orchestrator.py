from datetime import datetime, timezone

import pytest

from src.orchestrator.slash_slack.orchestrator import SlashSlackOrchestrator


class FakeSlashSlackAdapter:
    def __init__(self):
        base_ts = datetime.now(tz=timezone.utc).timestamp()
        self.messages = [
            {
                "text": "We decided to adopt option B for billing_service going forward.",
                "ts": f"{base_ts - 120:.6f}",
                "user_name": "alice",
                "user_id": "U1",
                "mentions": [],
                "references": [{"kind": "github", "url": "https://github.com/example/repo/pulls/42"}],
                "permalink": "https://example.slack.com/archives/C123/p1700000000000001",
            },
            {
                "text": "TODO: <@U2> will update the onboarding flow spec by Friday.",
                "ts": f"{base_ts - 60:.6f}",
                "user_name": "bob",
                "user_id": "U2",
                "mentions": [{"user_id": "U2", "display": "bob"}],
                "references": [],
                "permalink": "https://example.slack.com/archives/C123/p1700000500000001",
            },
            {
                "text": "Any blockers for auth rollout?",
                "ts": f"{base_ts - 30:.6f}",
                "user_name": "carol",
                "user_id": "U3",
                "mentions": [],
                "references": [],
                "permalink": "https://example.slack.com/archives/C123/p1700000600000001",
            },
        ]

    def fetch_channel_messages(self, channel_id, limit=200, oldest=None, latest=None):
        return {"channel_id": channel_id, "channel_name": "backend-dev", "messages": list(self.messages)}

    def fetch_thread(self, channel_id, thread_ts, limit=200):
        return {"channel_id": channel_id, "channel_name": "backend-dev", "messages": list(self.messages)}

    def search_messages(self, query, channel=None, limit=50):
        return {"query": query, "channel": channel, "messages": list(self.messages)}

    def resolve_channel_id(self, channel_name):
        return "C123" if channel_name == "backend" else None


@pytest.fixture()
def orchestrator():
    config = {
        "slack": {"default_channel_id": "C123"},
        "slash_slack": {"graph_emit": False},
    }
    return SlashSlackOrchestrator(config=config, tooling=FakeSlashSlackAdapter())


def test_handle_channel_recap_returns_sections(orchestrator):
    result = orchestrator.handle("summarize #backend last 24h")
    assert not result.get("error")
    sections = result.get("sections") or {}
    assert sections.get("decisions"), "Expected decisions to be extracted"
    assert sections.get("tasks"), "Expected tasks to be extracted"
    assert result.get("graph"), "Graph payload should be included"


def test_handle_decision_query(orchestrator):
    result = orchestrator.handle("decisions about billing_service last week")
    assert not result.get("error")
    sections = result.get("sections") or {}
    assert sections.get("decisions"), "Decision mode should surface decisions"


def test_handle_empty_command_returns_error(orchestrator):
    result = orchestrator.handle("")
    assert result.get("error")
    assert "Provide a Slack request" in result.get("message", "")

