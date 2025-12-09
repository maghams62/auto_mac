from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
import types
from typing import Any, Dict, List, Optional, Tuple

import pytest

from tests.fixtures.slash_command_helpers import create_slash_handler
from src.orchestrator.slash_slack.orchestrator import SlashSlackMetadataSingleton
from src.integrations import slack_client as slack_client_module
from src.utils import load_config
from src.ui.slash_commands import SlashCommandHandler


SLACK_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "synthetic_slack" / "slack_events.json"
)


def _load_slack_fixture() -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, str], Dict[str, Dict[str, Any]]]:
    raw_events = json.loads(SLACK_FIXTURE_PATH.read_text(encoding="utf-8"))
    channels: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    channel_labels: Dict[str, str] = {}
    users: Dict[str, Dict[str, Any]] = {}

    for event in raw_events:
        if event.get("source_type") != "slack_message":
            continue
        channel_id = event.get("channel_id")
        if not channel_id:
            continue
        channel_name = (event.get("channel") or event.get("channel_name") or channel_id).lstrip("#")
        channel_labels[channel_id] = channel_name
        ts = str(event.get("message_ts") or event.get("ts") or event.get("timestamp") or "")
        if not ts:
            continue
        text = event.get("text_raw") or event.get("text") or ""
        user_id = event.get("user") or event.get("username") or "anon"
        users.setdefault(
            user_id,
            {
                "id": user_id,
                "name": user_id,
                "profile": {
                    "display_name": user_id,
                    "real_name": user_id,
                },
            },
        )
        channels[channel_id].append(
            {
                "id": event.get("id") or f"{channel_id}:{ts}",
                "text": text,
                "ts": ts,
                "user": user_id,
                "thread_ts": event.get("thread_ts"),
                "reactions": event.get("reactions") or [],
                "files": event.get("files") or [],
                "permalink": event.get("permalink")
                or f"https://synthetic.slack.com/archives/{channel_id}/p{ts.replace('.', '')}",
            }
        )

    return channels, channel_labels, users


SLACK_CHANNELS, SLACK_CHANNEL_LABELS, SLACK_USERS = _load_slack_fixture()


class SyntheticSlackClient:
    """Drop-in replacement for SlackAPIClient backed by synthetic fixtures."""

    def __init__(self, *args, **kwargs):
        self.channels = SLACK_CHANNELS
        self.channel_labels = SLACK_CHANNEL_LABELS
        self.users = SLACK_USERS

    def fetch_messages(self, channel: str, limit: int = 200, oldest: Optional[str] = None, latest: Optional[str] = None):
        messages = list(self.channels.get(channel, []))
        filtered = self._apply_time_bounds(messages, oldest, latest)
        return {"messages": filtered[:limit], "has_more": len(filtered) > limit}

    def fetch_thread(self, channel: str, thread_ts: str, limit: int = 200):
        messages = [
            msg for msg in self.channels.get(channel, []) if msg.get("thread_ts") == thread_ts or msg["ts"] == thread_ts
        ]
        if not messages:
            messages = self.channels.get(channel, [])[:limit]
        return {"messages": messages[:limit], "has_more": len(messages) > limit, "channel": {"id": channel, "name": self.channel_labels.get(channel, channel)}}

    def search_messages(self, query: str, channel: Optional[str] = None, limit: int = 50):
        tokens = [token for token in query.lower().split() if token]
        matches = []
        channels = [channel] if channel else self.channels.keys()
        for channel_id in channels:
            for msg in self.channels.get(channel_id, []):
                text_lower = msg["text"].lower()
                if all(token in text_lower for token in tokens):
                    matches.append(
                        {
                            "text": msg["text"],
                            "timestamp": msg["ts"],
                            "permalink": msg["permalink"],
                            "user": msg["user"],
                            "channel": {
                                "id": channel_id,
                                "name": self.channel_labels.get(channel_id, channel_id),
                            },
                        }
                    )
        matches = matches[:limit]
        return {"messages": {"matches": matches, "total": len(matches)}}

    def list_channels(self, limit: int = 1000, **kwargs):
        channels = [
            {
                "id": channel_id,
                "name": name,
                "is_private": False,
                "is_archived": False,
                "num_members": 42,
            }
            for channel_id, name in self.channel_labels.items()
        ]
        return {"channels": channels[:limit], "has_more": len(channels) > limit}

    def get_channel_info(self, channel: str):
        name = self.channel_labels.get(channel, channel)
        return {"channel": {"id": channel, "name": name, "is_private": False, "is_archived": False}}

    def list_users(self, limit: int = 100, **kwargs):
        members = [
            {
                "id": user_id,
                "name": payload["name"],
                "profile": payload.get("profile", {}),
            }
            for user_id, payload in self.users.items()
        ]
        return {"members": members[:limit], "has_more": len(members) > limit}

    def get_user_info(self, user: str):
        payload = self.users.get(user) or next(iter(self.users.values()))
        return {"user": {"id": payload["id"], "name": payload["name"], "real_name": payload["profile"]["real_name"], "profile": payload["profile"]}}

    @staticmethod
    def _apply_time_bounds(messages: List[Dict[str, Any]], oldest: Optional[str], latest: Optional[str]) -> List[Dict[str, Any]]:
        def _within(ts: str) -> bool:
            value = float(ts)
            if oldest and value < float(oldest):
                return False
            if latest and value > float(latest):
                return False
            return True

        return [msg for msg in messages if _within(msg["ts"])]


@pytest.fixture()
def slash_handler(monkeypatch):
    # Patch Slack API client globally so metadata + tooling use the synthetic dataset.
    monkeypatch.setattr(slack_client_module, "SlackAPIClient", SyntheticSlackClient, raising=False)
    SlashSlackMetadataSingleton._instance = None

    config = load_config()
    config.setdefault("slash_git", {})["use_live_data"] = False
    config.setdefault("slash_slack", {}).setdefault("workspace_url", "https://synthetic.slack.com")
    handler = create_slash_handler(config=config)
    yield handler
    SlashSlackMetadataSingleton._instance = None


def _dispatch(handler, command: str):
    is_cmd, result = handler.handle(command)
    assert is_cmd, f"{command} should be treated as slash command"
    assert result["type"] == "result", result
    return result


THREAD_LINK = "https://slack.com/archives/C123INCIDENTS/p1764147600000000"

SLACK_CASES = [
    (
        "channel_recap_incidents",
        "/slack what's the latest in #incidents?",
        lambda payload: (
            _assert_summary_contains(payload, "incidents"),
            _assert_preview(payload),
        ),
    ),
    (
        "channel_search_support",
        "/slack summarize billing complaints in #support",
        lambda payload: (
            _assert_summary_contains(payload, "billing"),
            _assert_topics(payload),
        ),
    ),
    (
        "thread_recap_incidents",
        f"/slack summarize the thread {THREAD_LINK}",
        lambda payload: (
            _assert_context_field(payload, "thread_ts", "1764147600.00000"),
            _assert_preview(payload),
        ),
    ),
    (
        "decision_items",
        "/slack list action items about atlas billing last 48h",
        lambda payload: _assert_context_field(payload, "mode", "task"),
    ),
    (
        "cross_channel_search",
        "/slack search incidents mentioning \"vat_code\" across channels",
        lambda payload: _assert_summary_contains(payload, "vat_code"),
    ),
    (
        "quota_support_recap",
        "/slack summarize free tier quota complaints in #support",
        lambda payload: (
            _assert_context_field(payload, "channel_label", "#support"),
            _assert_quota_numbers(payload),
        ),
    ),
    (
        "quota_free_tier_search",
        "/slack search messages mentioning \"free tier quota\" across channels",
        lambda payload: _assert_summary_contains(payload, "free tier"),
    ),
]


GIT_CASES = [
    (
        "repo_summary_billing",
        "/git what changed recently in the billing-service repo?",
        lambda payload: (
            _assert_summary_contains(payload, "billing"),
            _assert_snapshot_commits(payload),
        ),
    ),
    (
        "doc_drift_billing_docs",
        "/git doc drift around Atlas billing docs?",
        lambda payload: (
            _assert_doc_drift(payload),
            _assert_sources(payload),
        ),
    ),
    (
        "core_api_release_compare",
        "/git what changed in core-api since release/2024.10",
        lambda payload: _assert_summary_contains(payload, "core-api"),
    ),
    (
        "pr_compare_billing",
        "/git list closed PRs targeting main",
        lambda payload: _assert_pr_listing(payload),
    ),
    (
        "commit_keyword_search",
        "/git show commits mentioning checkout last 2 days",
        lambda payload: _assert_commit_list(payload),
    ),
    (
        "quota_doc_drift",
        "/git doc drift around free tier quotas?",
        lambda payload: (
            _assert_doc_drift(payload),
            _assert_summary_contains(payload, "free tier"),
        ),
    ),
]


def _assert_summary_contains(payload: Dict[str, Any], keyword: str) -> None:
    def _normalize(text: str) -> str:
        return text.lower().replace("_", "").replace(" ", "")

    message = _normalize(payload.get("message") or "")
    assert _normalize(keyword) in message, f"Expected summary to mention '{keyword}'"


def _assert_preview(payload: Dict[str, Any]) -> None:
    preview = payload.get("messages_preview") or []
    assert preview, "Expected non-empty Slack preview"


def _assert_topics(payload: Dict[str, Any]) -> None:
    topics = (payload.get("sections") or {}).get("topics") or []
    assert topics, "Expected Slack topics in sections"


def _assert_section_count(payload: Dict[str, Any], section: str) -> None:
    entries = (payload.get("sections") or {}).get(section) or []
    assert entries, f"Expected {section} entries"


def _assert_context_field(payload: Dict[str, Any], field: str, expected: Any) -> None:
    value = (payload.get("context") or {}).get(field)
    if field == "thread_ts":
        def _normalize(val: Any) -> Any:
            text = str(val)
            return text.rstrip("0").rstrip(".") if "." in text else text

        assert _normalize(value) == _normalize(expected), f"Expected context[{field}] == {expected}, got {value}"
        return
    assert value == expected, f"Expected context[{field}] == {expected}, got {value}"


def _assert_snapshot_commits(payload: Dict[str, Any]) -> None:
    snapshot = payload.get("data", {}).get("snapshot")
    commits = snapshot.get("commits") if snapshot else None
    assert commits, "Expected commits in snapshot"


def _assert_commit_list(payload: Dict[str, Any]) -> None:
    commits = payload.get("data", {}).get("commits")
    assert commits, "Expected commit list in payload"


def _assert_doc_drift(payload: Dict[str, Any]) -> None:
    data = payload.get("data", {})
    doc_drift = data.get("doc_drift") or payload.get("doc_drift")
    assert doc_drift, "Expected doc drift metadata"


def _assert_sources(payload: Dict[str, Any]) -> None:
    sources = payload.get("sources") or []
    assert sources, "Expected sources list"
    assert any((source or {}).get("url") for source in sources), "Expected at least one source with URL"


def _assert_pr_listing(payload: Dict[str, Any]) -> None:
    prs = payload.get("data", {}).get("prs")
    assert prs, "Expected PR listing data"


def _assert_quota_numbers(payload: Dict[str, Any]) -> None:
    message = (payload.get("message") or "").replace(",", "")
    lower = message.lower()
    assert "300" in lower and "1000" in lower, f"Expected quota numbers in summary, got: {payload.get('message')}"


def _assert_doc_drift_paths(payload: Dict[str, Any], expected_fragments: List[str]) -> None:
    data = payload.get("data", {})
    entries = data.get("doc_drift") or payload.get("doc_drift") or []
    doc_paths = {entry.get("doc_path") or "" for entry in entries}
    for fragment in expected_fragments:
        assert any(fragment in path for path in doc_paths), f"Expected doc path containing '{fragment}'"


@pytest.mark.parametrize(
    "case_name, command, validator",
    SLACK_CASES,
    ids=[case[0] for case in SLACK_CASES],
)
def test_slack_scenarios(slash_handler, case_name, command, validator):
    if case_name == "thread_recap_incidents":
        _install_thread_fixture(slash_handler)
    elif case_name == "decision_items":
        _install_search_fixture(
            slash_handler,
            include_vat="vat_code" in command.lower(),
            include_tasks=True,
        )
    elif case_name == "quota_free_tier_search":
        _install_search_fixture(
            slash_handler,
            include_vat=False,
            include_tasks=False,
            include_quota=True,
        )
    elif case_name == "quota_support_recap":
        _install_search_fixture(
            slash_handler,
            include_vat=False,
            include_tasks=False,
            include_quota=True,
        )
    result = _dispatch(slash_handler, command)
    payload = result["result"]
    if case_name == "decision_items":
        assert getattr(
            slash_handler.slash_slack.tooling,
            "_test_search_invoked",
            False,
        ), "Expected synthetic search fixture to run"
    assert payload.get("type") == "slash_slack_summary"
    validator(payload)
    assert payload.get("metadata", {}).get("slash_route") == "slash_slack_assistant"


@pytest.mark.parametrize(
    "case_name, command, validator",
    GIT_CASES,
    ids=[case[0] for case in GIT_CASES],
)
def test_git_scenarios(slash_handler, case_name, command, validator):
    if case_name == "pr_compare_billing":
        _install_git_tool_fixture(
            slash_handler,
            {
                "list_branch_pull_requests": lambda params: {
                    "prs": [
                        {
                            "number": 118,
                            "author": "bob",
                            "title": "Fix 400 errors by adding vat_code",
                            "head_branch": "feature/vat-code",
                        }
                    ],
                    "branch": params.get("branch") or "main",
                    "state": params.get("state", "open"),
                }
            },
        )
    elif case_name == "commit_keyword_search":
        _install_git_tool_fixture(
            slash_handler,
            {
                "search_branch_commits": lambda params: {
                    "commits": [
                        {
                            "sha": "7c4ca1b24e4a8edf03bfd1db5dd6f90eeaaa7bd9",
                            "message": "feat!: require vat_code for EU",
                            "author": "alice",
                            "date": "2025-11-25T10:15:00Z",
                        }
                    ]
                }
            },
        )
    result = _dispatch(slash_handler, command)
    payload = result["result"]
    assert payload.get("type") == "slash_git_summary"
    validator(payload)
    assert payload.get("metadata", {}).get("slash_route") == "slash_git_assistant"


def _install_thread_fixture(handler: SlashCommandHandler) -> None:
    def fake_fetch_thread(self, channel_id: str, thread_ts: str, limit: int = 200):
        cannon = [
            msg
            for msg in SLACK_CHANNELS.get(channel_id, [])
            if msg.get("thread_ts") == thread_ts or msg.get("ts") == thread_ts
        ]
        messages = cannon or SLACK_CHANNELS.get(channel_id, [])[:limit]
        return {
            "channel_id": channel_id,
            "channel_name": SLACK_CHANNEL_LABELS.get(channel_id, channel_id),
            "messages": messages,
        }

    handler.slash_slack.tooling.fetch_thread = types.MethodType(
        fake_fetch_thread,
        handler.slash_slack.tooling,
    )


def _install_search_fixture(
    handler: SlashCommandHandler,
    *,
    include_vat: bool,
    include_tasks: bool,
    include_quota: bool = False,
) -> None:
    def fake_search_messages(self, query: str, channel: Optional[str] = None, limit: int = 50):
        self._test_search_invoked = True
        messages: List[Dict[str, Any]] = []
        if include_tasks:
            task_message = _synthetic_message(
                "C123SUPPORT",
                "Action item: @bob update atlas billing docs + send TODO list.",
                "1764156000.00000",
            )
            task_message["mentions"] = [{"display": "bob", "user_id": "U_BOB"}]
            messages.append(task_message)
        if include_vat:
            messages.append(
                _synthetic_message(
                    "C123INCIDENTS",
                    "Reminder: vat_code spec drift still unresolved for EU merchants.",
                    "1764149600.00000",
                )
            )
        if include_quota:
            messages.append(
                _synthetic_message(
                    "C123SUPPORT",
                    "Quota drift: customers hit throttling at 300 calls but docs + dashboard still promise 1000.",
                    "1764163200.00000",
                )
            )
        if not messages:
            messages.append(
                _synthetic_message(
                    "C123INCIDENTS",
                    "General update: atlas billing chatter remains active.",
                    "1764149700.00000",
                )
            )
        return {
            "query": query,
            "channel": channel,
            "messages": messages[:limit],
            "total": len(messages),
        }

    handler.slash_slack.tooling.search_messages = types.MethodType(
        fake_search_messages,
        handler.slash_slack.tooling,
    )


def _install_git_tool_fixture(
    handler: SlashCommandHandler,
    overrides: Dict[str, Any],
) -> None:
    original_execute = handler.git_assistant._execute_git_tool

    def patched_execute(self, tool_name: str, params: Dict[str, Any], session_id: Optional[str]):
        if tool_name in overrides:
            override = overrides[tool_name]
            return override(params)
        return original_execute(tool_name, params, session_id)

    handler.git_assistant._execute_git_tool = types.MethodType(
        patched_execute,
        handler.git_assistant,
    )


def _synthetic_message(channel_id: str, text: str, ts: str) -> Dict[str, Any]:
    label = SLACK_CHANNEL_LABELS.get(channel_id, channel_id)
    permalink = f"https://synthetic.slack.com/archives/{channel_id}/p{ts.replace('.', '')}"
    return {
        "id": f"{channel_id}:{ts}",
        "channel_id": channel_id,
        "channel_name": label,
        "text": text,
        "text_raw": text,
        "ts": ts,
        "user": "synthetic",
        "user_id": "U_SYNTH",
        "user_name": "Synthetic User",
        "thread_ts": None,
        "permalink": permalink,
        "reactions": [],
        "files": [],
        "mentions": [],
        "references": [],
    }

