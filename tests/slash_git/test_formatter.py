from types import SimpleNamespace

from src.slash_git.formatter import SlashGitLLMFormatter
from src.slash_git.models import GitQueryMode, GitQueryPlan, TimeWindow


class FakeLLM:
    def __init__(self, content: str):
        self.content = content

    def invoke(self, messages):
        return SimpleNamespace(content=self.content)


def _build_plan():
    return GitQueryPlan(
        mode=GitQueryMode.REPO_ACTIVITY,
        repo=None,
        component=None,
        time_window=TimeWindow(label="last 7 days"),
        user_query="/git repo info",
    )


def _build_snapshot():
    return {
        "commits": [
            {"sha": "abc123", "author": "alice", "timestamp": "2025-11-26T00:00:00Z", "title": "feat", "files_changed": []}
        ],
        "prs": [],
        "issues": [],
        "meta": {},
    }


def test_formatter_returns_parsed_json():
    llm = FakeLLM(
        content=json_payload(
            {
                "summary": "ok",
                "sections": [],
                "notable_prs": [],
                "breaking_changes": [],
                "next_actions": [],
                "references": [],
                "debug_metadata": {},
            }
        )
    )
    formatter = SlashGitLLMFormatter({}, llm_client=llm)
    result, error = formatter.generate(_build_plan(), _build_snapshot())
    assert error is None
    assert result["summary"] == "ok"


def test_formatter_validates_schema():
    llm = FakeLLM(content='{"sections": []}')
    formatter = SlashGitLLMFormatter({}, llm_client=llm)
    result, error = formatter.generate(_build_plan(), _build_snapshot())
    assert result is None
    assert "Missing keys" in error


def json_payload(obj):
    import json

    return json.dumps(obj)

