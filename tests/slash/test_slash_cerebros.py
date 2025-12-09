from __future__ import annotations

import json
from typing import Any, Dict

import pytest

from tests.fixtures.slash_command_helpers import create_slash_handler
from src.agent.cerebros_entrypoint import SLASH_DEFAULT_SOURCES, run_slash_cerebros_query
from src.cerebros.graph_reasoner import CerebrosReasonerResult
from src.ui.slash_commands import SlashCommandHandler
from src.services.slash_query_plan import SlashQueryIntent, SlashQueryPlan


@pytest.fixture
def slash_handler():
    handler = create_slash_handler()
    return handler


def test_cerebros_command_returns_slash_payload(monkeypatch, slash_handler):
    fake_payload: Dict[str, Any] = {
        "type": "slash_cerebros_summary",
        "status": "success",
        "message": "Checkout issues cross-system summary.",
        "context": {"modalities_used": ["slack", "git", "doc_issues"]},
        "analysis": {"modalities_used": ["slack", "git", "doc_issues"]},
        "sources": [
            {
                "id": "slack-1",
                "type": "slack",
                "label": "#support escalation",
                "url": "https://synthetic.slack.com/archives/C123/p1111",
                "snippet": "Customers reporting checkout failures.",
            },
            {
                "id": "git-1",
                "type": "git",
                "label": "PR #118",
                "url": "https://github.com/acme/billing-service/pull/118",
                "snippet": "Fix checkout VAT issue.",
            },
            {
                "id": "doc-1",
                "type": "doc",
                "label": "Docs portal guide",
                "url": "https://docs.example.com/billing",
                "snippet": "Guide still references legacy VAT flag.",
            },
            {
                "id": "docissue-1",
                "type": "doc_issue",
                "label": "Billing doc drift",
                "url": "https://docs.example.com/doc-issues/vat",
                "snippet": "Doc issue raised for VAT flag mismatch.",
            },
        ],
        "cerebros_answer": {"answer": "Checkout instability tied to PR #118"},
        "data": {"modalities_used": ["slack", "git", "doc_issues"]},
    }

    def fake_run_slash_cerebros_query(**_kwargs):
        return fake_payload

    monkeypatch.setattr(
        "src.agent.cerebros_entrypoint.run_slash_cerebros_query",
        fake_run_slash_cerebros_query,
    )
    monkeypatch.setattr(
        "src.ui.slash_commands.run_slash_cerebros_query",
        fake_run_slash_cerebros_query,
    )

    is_command, response = slash_handler.handle(
        "/cerebros summarize cross-system signals for billing checkout?", session_id="test-session"
    )
    assert is_command is True
    result = response["result"]
    assert result["type"] == "slash_cerebros_summary"
    assert len(result["sources"]) == 4
    urls = {source["url"] for source in result["sources"]}
    assert "https://synthetic.slack.com/archives/C123/p1111" in urls
    assert "https://github.com/acme/billing-service/pull/118" in urls
    assert "https://docs.example.com/billing" in urls
    assert "https://docs.example.com/doc-issues/vat" in urls
    assert any(source["type"] == "doc_issue" for source in result["sources"])


def test_run_slash_cerebros_query_serializes_query_plan(monkeypatch):
    fake_result = CerebrosReasonerResult(
        query="billing",
        summary="Checkout summary",
        response_payload={
            "modalities_used": ["slack"],
            "results": [],
            "graph_context": {},
        },
        evidence_payload={"evidence": []},
        doc_insights=None,
        cerebros_answer={"answer": "Checkout summary", "sources": []},
        sources_queried=["slack"],
        component_ids=None,
        issue_id=None,
        project_id=None,
    )

    monkeypatch.setattr(
        "src.agent.cerebros_entrypoint.run_cerebros_reasoner",
        lambda **_: fake_result,
    )

    plan = SlashQueryPlan(
        raw="billing checkout",
        command="cerebros",
        intent=SlashQueryIntent.SUMMARIZE,
    )

    payload = run_slash_cerebros_query(
        config={},
        query="billing checkout",
        query_plan=plan,
        sources=["slack"],
    )

    context_plan = payload["context"]["query_plan"]
    assert isinstance(context_plan, dict)
    assert context_plan["raw"] == "billing checkout"
    # Ensure the payload can be serialized to JSON without errors
    json.dumps(payload)


def test_run_slash_cerebros_query_requests_all_sources_by_default(monkeypatch):
    captured: Dict[str, Any] = {}

    fake_result = CerebrosReasonerResult(
        query="vat enforcement",
        summary="Summary",
        response_payload={"results": [], "graph_context": {}},
        evidence_payload={"evidence": []},
        doc_insights=None,
        cerebros_answer={"answer": "Summary", "sources": []},
        sources_queried=[],
        component_ids=None,
        issue_id=None,
        project_id=None,
    )

    def fake_run_cerebros_reasoner(**kwargs):
        captured["sources"] = kwargs.get("sources")
        return fake_result

    monkeypatch.setattr(
        "src.agent.cerebros_entrypoint.run_cerebros_reasoner",
        fake_run_cerebros_reasoner,
    )

    run_slash_cerebros_query(config={}, query="vat enforcement")
    assert captured["sources"] == SLASH_DEFAULT_SOURCES


def test_cerebros_fallback_still_returns_slash_payload(monkeypatch, slash_handler):
    """If the graph pipeline errors, ensure the legacy search output is normalized."""

    def fake_graph_failure(*_args, **_kwargs):
        return {"status": "error", "message": "Graph pipeline unavailable"}

    def fake_search(_task_text, plan=None):
        return {
            "status": "success",
            "message": 'Top matches for "vat billing?"',
            "data": {
                "results": [
                    {
                        "chunk_id": "docissue-coreapi-vat",
                        "modality": "doc_issues",
                        "title": "Payments API",
                        "score": 1.68,
                        "url": "https://docs.example.com/payments",
                        "metadata": {"source_type": "doc_issue"},
                    }
                ],
                "total": 1,
                "modalities_used": ["doc_issues"],
            },
        }

    monkeypatch.setattr(slash_handler, "_handle_cerebros_graph", fake_graph_failure)
    monkeypatch.setattr(slash_handler.cerebros_command, "search", fake_search)

    is_command, response = slash_handler.handle("/cerebros whats the issue with vat billing?")
    assert is_command is True
    result = response["result"]
    assert result["type"] == "slash_cerebros_summary"
    assert result["data"]["severity_score"] == 5
    assert any(source["label"] == "Payments API" for source in result["sources"])

