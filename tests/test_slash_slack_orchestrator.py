from datetime import datetime, timezone

import pytest

from src.demo.graph_summary import GraphSummary
from src.demo.scenario_classifier import PAYMENTS_SCENARIO
from src.demo.vector_retriever import VectorRetrievalBundle
from src.orchestrator.slash_slack.orchestrator import SlashSlackOrchestrator
from src.reasoners import DocDriftAnswer


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


class FakeLLMFormatter:
    def __init__(self):
        self.calls = 0

    def generate(self, *, query, context, sections, messages):
        self.calls += 1
        return (
            {
                "summary": f"{context.get('channel_label', 'Slack')} summary",
                "sections": sections or {},
                "entities": [{"name": "billing_service", "type": "service"}],
                "doc_drift": [],
                "evidence": [],
            },
            None,
        )


class FakeReasoner:
    def __init__(self, summary: str = "Doc drift summary"):
        self.summary = summary
        self.calls = 0

    def answer_question(self, question: str, source: str = "slack") -> DocDriftAnswer:
        self.calls += 1
        return DocDriftAnswer(
            question=question,
            scenario=PAYMENTS_SCENARIO,
            summary=self.summary,
            sections={
                "topics": [{"title": "VAT drift", "insight": "Docs lag behind VAT changes.", "evidence_ids": ["slack-1"]}],
                "decisions": [],
                "tasks": [],
                "open_questions": [],
                "references": [],
            },
            impacted={
                "apis": [PAYMENTS_SCENARIO.api],
                "services": ["core-api-service"],
                "components": ["core.payments"],
                "docs": ["docs/payments_api.md"],
            },
            evidence=[{"id": "slack-1", "source": "slack", "text": "VAT issue"}],
            graph_summary=GraphSummary(api=PAYMENTS_SCENARIO.api),
            vector_bundle=VectorRetrievalBundle(),
            doc_drift=[{"doc": "docs/payments_api.md", "issue": "VAT", "services": ["core-api-service"], "components": ["core.payments"], "apis": [PAYMENTS_SCENARIO.api], "labels": ["doc_drift"]}],
            next_steps=["Update docs"],
            metadata={"scenario": PAYMENTS_SCENARIO.name},
        )


@pytest.fixture()
def orchestrator():
    config = {
        "slack": {"default_channel_id": "C123"},
        "slash_slack": {"graph_emit": False, "doc_drift_reasoner": False},
    }
    return SlashSlackOrchestrator(
        config=config,
        tooling=FakeSlashSlackAdapter(),
        llm_formatter=FakeLLMFormatter(),
    )


@pytest.fixture()
def reasoner_orchestrator():
    config = {
        "slack": {"default_channel_id": "C123"},
        "slash_slack": {"graph_emit": False, "doc_drift_reasoner": True},
    }
    fake_reasoner = FakeReasoner()
    return SlashSlackOrchestrator(
        config=config,
        tooling=FakeSlashSlackAdapter(),
        llm_formatter=None,
        reasoner=fake_reasoner,
    )


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


def test_doc_drift_reasoner_short_circuit(reasoner_orchestrator):
    result = reasoner_orchestrator.handle("doc drift status for VAT payments?")
    assert result["type"] == "slash_slack_summary"
    assert result["message"] == "Doc drift summary"
    assert result["context"]["mode"] == "doc_drift"
    assert result["graph"]
    assert result["sections"]["tasks"], "Next steps should populate tasks"


def test_doc_drift_reasoner_includes_entities(reasoner_orchestrator):
    result = reasoner_orchestrator.handle("drift report for payments")
    entities = result.get("entities") or []
    assert any(entity.get("type") == "service" for entity in entities)
    evidence = result.get("evidence") or []
    assert evidence and evidence[0]["id"] == "slack-1"

