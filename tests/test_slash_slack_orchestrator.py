from datetime import datetime, timezone

import pytest

from src.demo.graph_summary import GraphSummary
from src.demo.scenario_classifier import PAYMENTS_SCENARIO
from src.demo.vector_retriever import VectorRetrievalBundle
from src.orchestrator.slash_slack.orchestrator import SlashSlackOrchestrator
from src.services.slash_query_plan import SlashQueryPlanner
from src.reasoners import DocDriftAnswer


class FakeSlashSlackAdapter:
    def __init__(self):
        base_ts = datetime.now(tz=timezone.utc).timestamp()
        self.channel_map = {
            "backend": ("C123", "backend-dev"),
            "core-api": ("C456", "core-api"),
        }
        self.messages = [
            {
                "text": "We decided to adopt option B for billing_service going forward.",
                "ts": f"{base_ts - 120:.6f}",
                "user_name": "alice",
                "user_id": "U1",
                "mentions": [],
                "references": [{"kind": "github", "url": "https://github.com/example/repo/pulls/42"}],
                "permalink": "https://example.slack.com/archives/C123/p1700000000000001",
                "channel_id": "C123",
                "channel_name": "backend-dev",
            },
            {
                "text": "TODO: <@U2> will update the onboarding flow spec by Friday.",
                "ts": f"{base_ts - 60:.6f}",
                "user_name": "bob",
                "user_id": "U2",
                "mentions": [{"user_id": "U2", "display": "bob"}],
                "references": [],
                "permalink": "https://example.slack.com/archives/C123/p1700000500000001",
                "channel_id": "C123",
                "channel_name": "backend-dev",
            },
            {
                "text": "Any blockers for auth rollout?",
                "ts": f"{base_ts - 30:.6f}",
                "user_name": "carol",
                "user_id": "U3",
                "mentions": [],
                "references": [],
                "permalink": "https://example.slack.com/archives/C123/p1700000600000001",
                "channel_id": "C123",
                "channel_name": "backend-dev",
            },
        ]
        self.last_fetch_channel: str | None = None
        self.last_search_channel: str | None = None

        self.channel_labels = {}
        for _, (cid, label) in self.channel_map.items():
            self.channel_labels[cid] = label

    def fetch_channel_messages(self, channel_id, limit=200, oldest=None, latest=None):
        self.last_fetch_channel = channel_id
        channel_name = self.channel_labels.get(channel_id, "backend-dev")
        return {"channel_id": channel_id, "channel_name": channel_name, "messages": list(self.messages)}

    def fetch_thread(self, channel_id, thread_ts, limit=200):
        self.last_fetch_channel = channel_id
        channel_name = self.channel_labels.get(channel_id, "backend-dev")
        return {"channel_id": channel_id, "channel_name": channel_name, "messages": list(self.messages)}

    def search_messages(self, query, channel=None, limit=50):
        self.last_search_channel = channel
        return {"query": query, "channel": channel, "messages": list(self.messages), "warnings": []}

    def resolve_channel_id(self, channel_name):
        if not channel_name:
            return None
        normalized = channel_name.strip().lstrip("#").lower().replace(" ", "-")
        match = self.channel_map.get(normalized)
        return match[0] if match else None

    def suggest_channels(self, prefix, limit=5):
        normalized = (prefix or "").strip().lower()
        matches = []
        for _, label in self.channel_map.values():
            if not normalized or label.lower().startswith(normalized):
                matches.append(label)
        return matches[:limit]

    def suggest_channels(self, partial_name, limit=5):
        if not partial_name:
            return []
        needle = partial_name.strip().lstrip("#").lower().replace(" ", "-")
        suggestions = []
        for slug, (_, label) in self.channel_map.items():
            if needle in slug or needle in label:
                suggestions.append(slug)
        return suggestions[:limit]


class FakeLLMFormatter:
    def __init__(self):
        self.calls = 0

    def generate(self, *, query, context, sections, messages, graph=None):
        self.calls += 1
        topics = (sections or {}).get("topics", [])
        decisions = (sections or {}).get("decisions", [])
        tasks = (sections or {}).get("tasks", [])
        highlights = [topic.get("topic", "topic") for topic in topics[:2]] or ["General updates"]
        llm_sections = [
            {
                "title": "Highlights",
                "body": f"{context.get('channel_label', 'Slack')} summary",
                "bullets": highlights,
            }
        ]
        key_decisions = [
            {
                "text": decision.get("text", "decision"),
                "when": decision.get("timestamp"),
                "who": [decision.get("participant")] if decision.get("participant") else [],
                "permalink": decision.get("permalink"),
                "confidence": 0.8,
            }
            for decision in decisions[:1]
        ]
        next_actions = [
            {
                "text": task.get("description", "task"),
                "assignee": task.get("assignee"),
                "due_hint": "soon",
                "permalink": task.get("permalink"),
                "confidence": 0.7,
            }
            for task in tasks[:1]
        ]
        references = []
        if decisions:
            references.append(
                {
                    "kind": "slack",
                    "url": decisions[0].get("permalink", "https://example.slack.com/archives/C123"),
                    "label": decisions[0].get("text", "Slack reference"),
                }
            )
        return (
            {
                "summary": f"{context.get('channel_label', 'Slack')} summary",
                "sections": llm_sections,
                "key_decisions": key_decisions,
                "next_actions": next_actions,
                "open_questions": [],
                "references": references,
                "entities": [{"name": "billing_service", "type": "service"}],
                "debug_metadata": {
                    "mode": query.get("mode"),
                    "channel_name": context.get("channel_label"),
                    "time_window_label": context.get("time_window_label"),
                    "messages_used": len(messages),
                },
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
            sources=[
                {
                    "id": "slack-1",
                    "type": "slack",
                    "label": "#incidents",
                    "url": "https://example.slack.com/archives/C123/p1700000000",
                }
            ],
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
    sections = result.get("sections") or []
    assert isinstance(sections, list) and sections, "Expected sections list"
    assert result.get("key_decisions"), "Expected decisions to be extracted"
    assert result.get("next_actions"), "Expected tasks to be extracted"
    assert result.get("graph"), "Graph payload should be included"


def test_debug_block_does_not_pollute_summary(orchestrator):
    result = orchestrator.handle("summarize #backend last 24h")
    debug_block = result.get("debug")
    assert debug_block, "Debug block should remain attached for evidence viewing"
    assert "```json" not in result.get("message", ""), "Message should remain natural language"
    assert result.get("metadata", {}).get("debug_block") == debug_block
    sample = debug_block.get("sample_evidence")
    assert isinstance(sample, list)
    assert sample, "Sample evidence should include at least one snippet"


def test_handle_decision_query(orchestrator):
    result = orchestrator.handle("decisions about billing_service last week")
    assert not result.get("error")
    key_decisions = result.get("key_decisions") or []
    assert key_decisions, "Decision mode should surface decisions"


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


def test_slash_summary_surface_reference_links(orchestrator):
    result = orchestrator.handle("summarize #backend last 24h")
    assert result["type"] == "slash_slack_summary"
    references = result.get("references") or []
    assert references, "Expected reference links to be included"
    assert references[0]["url"].startswith("https://example.slack.com")


def test_channel_hint_infers_channel(orchestrator):
    result = orchestrator.handle("can you summarize the conversation in core-API this week?")
    assert not result.get("error")
    metadata = result.get("metadata") or {}
    assert metadata.get("channel_id") == "C456"
    assert orchestrator.tooling.last_fetch_channel == "C456"


def test_channel_recap_unknown_channel_errors(orchestrator):
    result = orchestrator.handle("summarize #unknown-channel last week")
    assert result.get("error")
    assert "not found" in result.get("message", "").lower()


def test_decision_mode_respects_channel_filter(orchestrator):
    orchestrator.handle("decisions about billing_service in core-API")
    assert orchestrator.tooling.last_search_channel == "C456"


def test_sources_include_channel_links(orchestrator):
    result = orchestrator.handle("summarize #backend last 24h")
    sources = result.get("sources") or []
    assert sources, "Sources list should not be empty"
    first = sources[0]
    assert first.get("channel", "").startswith("#")
    assert first.get("permalink", "").startswith("https://example.slack.com")
    metadata = result.get("metadata", {})
    assert metadata.get("channel_scope") == ["#backend-dev"], "Channel scope should be recorded"


def test_empty_scope_message_when_no_results(orchestrator):
    orchestrator.tooling.messages = []
    orchestrator.llm_formatter = None
    result = orchestrator.handle("summarize #backend last 24h")
    assert "couldn't find" in (result.get("message") or "").lower()
    assert result.get("sources") == []


class NoMessagesAdapter(FakeSlashSlackAdapter):
    def fetch_channel_messages(self, channel_id, limit=200, oldest=None, latest=None):
        self.last_fetch_channel = channel_id
        return {"channel_id": channel_id, "channel_name": self.channel_labels.get(channel_id, channel_id), "messages": []}

    def search_messages(self, query, channel=None, limit=50):
        self.last_search_channel = channel
        return {"query": query, "channel": channel, "messages": [], "warnings": ["synthetic search warning"]}


class StubContextService:
    def __init__(self, messages):
        self._messages = messages

    def search(self, plan, *, limit=40, channel_ids=None, channel_names=None):
        return list(self._messages)


def test_semantic_fallback_returns_summary():
    config = {
        "slack": {"default_channel_id": "C123"},
        "slash_slack": {"graph_emit": False, "doc_drift_reasoner": False},
    }
    adapter = NoMessagesAdapter()
    orchestrator = SlashSlackOrchestrator(
        config=config,
        tooling=adapter,
        llm_formatter=None,
    )
    orchestrator.context_service = StubContextService(
        [
            {
                "text": "Vector recall message for backend summary.",
                "ts": "123456.0",
                "channel_id": "C123VECTOR",
                "channel_name": "#backend",
                "permalink": "https://example.slack.com/archives/C123VECTOR/p123456000",
                "user": "alice",
            }
        ]
    )
    planner = SlashQueryPlanner(config)
    plan = planner.plan("summarize #backend last week", command="slack")
    result = orchestrator.handle("summarize #backend last week", plan=plan)
    assert result["type"] == "slash_slack_summary"
    assert result["sources"], "Semantic fallback should supply sources"
    assert "backend" in (result.get("message") or "").lower()
    metadata = result.get("metadata") or {}
    assert metadata.get("retrieval_warnings"), "Retrieval warnings should be surfaced when fallback search fails"

