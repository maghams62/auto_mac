"""
End-to-end style tests that simulate natural language workflows by executing
the plan executor directly with mocked tool outputs. These scenarios focus on
high-value user requests that frequently regress in the UI:

1. DuckDuckGo search → reply_to_user
2. Reading emails from the last hour → reply_to_user
3. Organising files by category → reply_to_user
4. Composing an email draft → reply_to_user

Each test asserts that:
- The plan executes successfully (ExecutionStatus.SUCCESS)
- Tool stubs receive the expected parameters
- The final reply payload contains concrete text (no unresolved placeholders)
- No executor warnings about unresolved placeholders are emitted
"""

# ruff: noqa: E402 (adjust sys.path prior to imports)
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
import re
from typing import Dict, Any, List

import pytest

from src.orchestrator.executor import PlanExecutor, ExecutionStatus
from src.utils import load_config


def _assert_no_placeholder(payload: Dict[str, Any]) -> None:
    """Ensure reply payload does not contain unresolved placeholders."""
    placeholder_pattern = re.compile(r"\$step\d+")
    for key in ("message", "details"):
        value = payload.get(key) or ""
        assert not placeholder_pattern.search(value), f"{key} still contains placeholder: {value!r}"


@pytest.fixture
def executor() -> PlanExecutor:
    """Instantiate a fresh executor with verification disabled for isolation."""
    config = load_config()
    return PlanExecutor(config, enable_verification=False)


def test_duckduckgo_search_reply(executor: PlanExecutor, caplog: pytest.LogCaptureFixture) -> None:
    goal = "What was Arsenal's score in the last game?"

    sample_results = [
        {
            "title": "Sunderland 2-2 Arsenal - Premier League thriller",
            "snippet": "Arsenal drew 2-2 with Sunderland thanks to a late equaliser.",
            "link": "https://example.com/arsenal-sunderland"
        }
    ]

    def stub_search(query: str, num_results: int = 5, search_type: str = "web") -> Dict[str, Any]:
        assert query == goal
        return {
            "results": sample_results,
            "total_results": len(sample_results),
            "query": query,
            "num_results": len(sample_results),
            "source": "duckduckgo",
            "summary": "Arsenal drew 2-2 with Sunderland.",
            "error": False,
            "status": "success",
        }

    executor.tools["google_search"].func = stub_search  # type: ignore[attr-defined]

    plan = [
        {"id": 1, "action": "google_search", "parameters": {"query": goal, "num_results": 5}},
        {
            "id": 2,
            "action": "reply_to_user",
            "parameters": {
                "message": "$step1.results.0.title",
                "details": "$step1.results.0.snippet",
            },
        },
    ]

    with caplog.at_level(logging.INFO):
        result = executor.execute_plan(plan, goal)

    assert result["status"] == ExecutionStatus.SUCCESS
    reply = result["final_output"]
    assert isinstance(reply, dict)
    _assert_no_placeholder(reply)
    assert reply["message"] == sample_results[0]["title"]
    assert reply["details"] == sample_results[0]["snippet"]

    # Ensure success log emitted and no unresolved placeholder warnings
    assert any("✅ Step 2" in msg for msg in caplog.messages)
    assert not any("unresolved placeholders" in msg for msg in caplog.messages)


def test_read_emails_last_hour(executor: PlanExecutor, caplog: pytest.LogCaptureFixture) -> None:
    goal = "Read emails from the last hour and summarize them."

    stub_payload = {
        "emails": [
            {"sender": "alex@example.com", "subject": "Launch checklist", "snippet": "Please confirm the launch checklist."},
            {"sender": "jamie@example.com", "subject": "Sprint notes", "snippet": "Here are the sprint retro notes."},
        ],
        "count": 2,
        "account": "inbox@example.com",
        "time_range": "last 1 hour",
        "summary": "Found 2 emails in the last hour.",
        "error": False,
        "status": "success",
    }

    def stub_read(hours: int | None = None, minutes: int | None = None, mailbox: str = "INBOX") -> Dict[str, Any]:
        assert hours == 1
        return stub_payload

    executor.tools["read_emails_by_time"].func = stub_read  # type: ignore[attr-defined]

    plan = [
        {"id": 1, "action": "read_emails_by_time", "parameters": {"hours": 1}},
        {
            "id": 2,
            "action": "reply_to_user",
            "parameters": {
                "message": "$step1.summary",
                "details": "$step1.emails.0.subject",
            },
        },
    ]

    with caplog.at_level(logging.INFO):
        result = executor.execute_plan(plan, goal)

    assert result["status"] == ExecutionStatus.SUCCESS
    reply = result["final_output"]
    assert isinstance(reply, dict)
    _assert_no_placeholder(reply)
    assert reply["message"] == stub_payload["summary"]
    assert reply["details"] == stub_payload["emails"][0]["subject"]
    assert not any("unresolved placeholders" in msg for msg in caplog.messages)


def test_organize_files_summary(executor: PlanExecutor, caplog: pytest.LogCaptureFixture) -> None:
    goal = "Organize research PDFs into a Research folder."

    organize_result = {
        "files_moved": ["research_notes.pdf"],
        "files_skipped": [],
        "target_path": "/tmp/Research",
        "reasoning": {"research_notes.pdf": "Contains latest research summaries."},
        "total_evaluated": 1,
        "summary": "Moved 1 file into /tmp/Research.",
        "details_message": "research_notes.pdf – Contains latest research summaries.",
        "error": False,
        "status": "success",
    }

    def stub_organize(category: str, target_folder: str, move_files: bool = True) -> Dict[str, Any]:
        assert category == "research PDFs"
        assert target_folder == "Research"
        assert move_files is True
        return organize_result

    executor.tools["organize_files"].func = stub_organize  # type: ignore[attr-defined]

    plan = [
        {
            "id": 1,
            "action": "organize_files",
            "parameters": {
                "category": "research PDFs",
                "target_folder": "Research",
                "move_files": True,
            },
        },
        {
            "id": 2,
            "action": "reply_to_user",
            "parameters": {
                "message": "$step1.summary",
                "details": "$step1.details_message",
            },
        },
    ]

    with caplog.at_level(logging.INFO):
        result = executor.execute_plan(plan, goal)

    assert result["status"] == ExecutionStatus.SUCCESS
    reply = result["final_output"]
    assert isinstance(reply, dict)
    _assert_no_placeholder(reply)
    assert reply["message"] == organize_result["summary"]
    assert reply["details"] == organize_result["details_message"]
    assert not any("unresolved placeholders" in msg for msg in caplog.messages)


def test_compose_email_draft(executor: PlanExecutor, caplog: pytest.LogCaptureFixture) -> None:
    goal = "Draft an email to the product team about the beta launch."

    compose_result = {
        "status": "draft",
        "message": "Drafted email to product-team@example.com",
        "error": False,
    }

    def stub_compose(
        subject: str,
        body: str,
        recipient: str | None = None,
        attachments: List[str] | None = None,
        send: bool = False,
    ) -> Dict[str, Any]:
        assert subject == "Beta launch update"
        assert recipient == "product-team@example.com"
        assert send is False
        return compose_result

    executor.tools["compose_email"].func = stub_compose  # type: ignore[attr-defined]

    plan = [
        {
            "id": 1,
            "action": "compose_email",
            "parameters": {
                "subject": "Beta launch update",
                "body": "Draft the beta launch announcement.",
                "recipient": "product-team@example.com",
                "send": False,
            },
        },
        {
            "id": 2,
            "action": "reply_to_user",
            "parameters": {
                "message": "$step1.message",
                "details": "$step1.status",
            },
        },
    ]

    with caplog.at_level(logging.INFO):
        result = executor.execute_plan(plan, goal)

    assert result["status"] == ExecutionStatus.SUCCESS
    reply = result["final_output"]
    assert isinstance(reply, dict)
    _assert_no_placeholder(reply)
    assert reply["message"] == compose_result["message"]
    assert reply["details"] == compose_result["status"]
    assert not any("unresolved placeholders" in msg for msg in caplog.messages)
