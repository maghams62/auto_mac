import copy
import json
import os
from types import SimpleNamespace

import pytest

from src.demo.vector_retriever import VectorRetriever
from src.reasoners import DocDriftReasoner


class _DeterministicEmbeddingProvider:
    """Simple embedding stub that avoids external API calls."""

    def embed(self, text: str):
        if not text:
            return []
        seed = (sum(ord(ch) for ch in text) % 10) + 1
        return [float(seed)] * 16


class _FakeLLM:
    """LLM stub that returns deterministic JSON for known scenarios."""

    def __init__(self):
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        prompt = kwargs["messages"][-1]["content"]
        api = self._extract_live_api(prompt)
        question = self._extract_user_question(prompt)
        lowered_question = (question or "").lower()

        if api == "/v1/notifications/send" or "notification" in lowered_question:
            payload = self._notifications_payload()
        else:
            payload = self._payments_payload()
        content = json.dumps(payload)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=content)),
            ]
        )

    @staticmethod
    def _payments_payload():
        return {
            "summary": "VAT drift: core-api requires vat_code but billing + docs still omit it.",
            "sections": [
                {
                    "title": "Code requires vat_code",
                    "body": "PR 2041 makes vat_code mandatory for /v1/payments/create.",
                    "importance": "high",
                    "evidence_ids": ["git_commit:core-api:2041"],
                },
                {
                    "title": "Slack reports 400s",
                    "body": "Incidents channel shares missing vat_code errors for EU merchants.",
                    "importance": "high",
                    "evidence_ids": ["slack_message:#incidents:1764147600.00000"],
                },
            ],
            "impacted_entities": [
                {"type": "api", "name": "/v1/payments/create", "severity": "high"},
                {"type": "service", "name": "billing-service", "severity": "high"},
                {"type": "doc", "name": "docs/payments_api.md", "severity": "high"},
            ],
            "doc_drift_facts": [
                {
                    "id": "vat_code_required_docs_stale",
                    "doc": "docs/payments_api.md",
                    "description": "Docs still list vat_code as optional.",
                    "evidence_ids": ["doc:docs/payments_api.md#request-fields"],
                }
            ],
            "evidence": [
                {"id": "git_commit:core-api:2041", "source": "git", "snippet": "feat: require vat_code"},
                {"id": "slack_message:#incidents:1764147600.00000", "source": "slack", "snippet": "400s missing vat_code"},
            ],
            "debug_metadata": {"scenario": "payments_vat", "confidence": "high"},
            "next_steps": ["Update billing payload", "Refresh docs/payments_api.md"],
        }

    @staticmethod
    def _notifications_payload():
        return {
            "summary": "template_version drift: notifications-service rejects payloads without version numbers.",
            "sections": [
                {
                    "title": "PR 142 enforces template_version",
                    "body": "Notifications service now requires template_version in /v1/notifications/send.",
                    "importance": "high",
                    "evidence_ids": ["git_pr:notifications-service:142"],
                }
            ],
            "impacted_entities": [
                {"type": "api", "name": "/v1/notifications/send", "severity": "high"},
                {"type": "doc", "name": "docs/notification_playbook.md", "severity": "medium"},
            ],
            "doc_drift_facts": [
                {
                    "id": "template_version_missing_docs",
                    "doc": "docs/notification_playbook.md",
                    "description": "Docs omit template_version although code enforces it.",
                    "evidence_ids": ["doc:docs/notification_playbook.md#payload"],
                }
            ],
            "evidence": [
                {"id": "git_pr:notifications-service:142", "source": "git", "snippet": "require template_version"},
                {"id": "doc:docs/notification_playbook.md#payload", "source": "doc", "snippet": "Example lacks template_version"},
            ],
            "debug_metadata": {"scenario": "notifications_template_version", "confidence": "medium"},
        }

    @staticmethod
    def _extract_live_api(prompt: str) -> str:
        if "## Live Inputs" not in prompt:
            return ""
        live_section = prompt.split("## Live Inputs", 1)[1]
        for line in live_section.splitlines():
            if line.strip().startswith("Scenario:"):
                if "(API" in line:
                    start = line.find("(API") + len("(API")
                    end = line.find(")", start)
                    return line[start:end].strip()
        return ""

    @staticmethod
    def _extract_user_question(prompt: str) -> str:
        marker = "## User Question"
        if marker not in prompt:
            return ""
        remainder = prompt.split(marker, 1)[1]
        if "##" in remainder:
            remainder = remainder.split("##", 1)[0]
        return remainder.strip()


def _build_reasoner(test_config):
    cfg = copy.deepcopy(test_config or {})
    cfg.setdefault("graph", {})
    cfg["graph"]["enabled"] = False
    cfg.setdefault("openai", {})
    cfg["openai"].setdefault("api_key", "")
    cfg["openai"].setdefault("model", "gpt-4o-mini")
    os.environ["VECTOR_BACKEND"] = "local"

    embedding_provider = _DeterministicEmbeddingProvider()
    vector_retriever = VectorRetriever(cfg, embedding_provider=embedding_provider)
    llm_client = _FakeLLM()
    return DocDriftReasoner(cfg, vector_retriever=vector_retriever, llm_client=llm_client)


@pytest.mark.unit
def test_doc_drift_reasoner_handles_payments_story(test_config):
    reasoner = _build_reasoner(test_config)
    answer = reasoner.answer_question("/slack what's going on with payments?", source="slack")

    assert "vat" in answer.summary.lower()
    assert answer.structured_sections, "Expected structured sections from template-driven prompt."
    assert "/v1/payments/create" in answer.impacted["apis"]
    assert any(entity["type"] == "doc" for entity in answer.impacted_entities)
    assert answer.doc_drift_facts, "Doc drift facts should be populated from the schema."
    assert answer.reasoner_evidence, "Reasoner evidence from the LLM output should be captured."
    assert answer.evidence, "Vector retrieval should provide supporting snippets."
    assert "Source command: /slack" in (answer.prompt or "")


@pytest.mark.unit
def test_doc_drift_reasoner_handles_notifications_story(test_config):
    reasoner = _build_reasoner(test_config)
    answer = reasoner.answer_question("/git summarize drift around notifications", source="git")

    assert "template_version" in answer.summary.lower()
    assert "/v1/notifications/send" in answer.impacted["apis"]
    assert answer.impacted_entities, "Impacted entities should include API + doc entries."
    assert answer.doc_drift, "Doc drift entries should mirror doc_drift_facts."
    assert answer.debug_metadata.get("scenario") == "notifications_template_version"
    assert "Source command: /git" in (answer.prompt or "")

