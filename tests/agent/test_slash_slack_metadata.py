from typing import Optional

from src.orchestrator.slash_slack.orchestrator import SlashSlackOrchestrator


class StubSlackTooling:
    def __init__(self):
        self.channels = {
            "backend": ("C123", "backend"),
            "core-api": ("C456", "core-api"),
        }

    def resolve_channel_id(self, channel_name: Optional[str]) -> Optional[str]:
        if not channel_name:
            return None
        normalized = channel_name.strip().lstrip("#").lower()
        match = self.channels.get(normalized)
        return match[0] if match else None

    def suggest_channels(self, prefix: str, limit: int = 5):
        normalized = (prefix or "").strip().lower()
        matches = []
        for label in self.channels:
            if not normalized or label.startswith(normalized):
                matches.append(label)
        return matches[:limit]

    # The orchestrator should raise before fetching messages for invalid channels.
    def fetch_channel_messages(self, *args, **kwargs):
        raise AssertionError("fetch_channel_messages should not be called for invalid channels")


def test_slack_orchestrator_returns_channel_suggestions():
    config = {
        "slack": {"default_channel_id": None},
        "slash_slack": {"graph_emit": False, "doc_drift_reasoner": False},
    }
    tooling = StubSlackTooling()
    orchestrator = SlashSlackOrchestrator(config=config, tooling=tooling, llm_formatter=None)

    result = orchestrator.handle("summarize #core last 24h")

    assert result.get("error") is True
    assert "Did you mean" in (result.get("message") or "")
    assert "#core-api" in result["message"]

