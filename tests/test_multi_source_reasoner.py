from typing import Any, Dict

import pytest

from src.agent.evidence import Evidence, EvidenceCollection
from src.agent.multi_source_reasoner import MultiSourceReasoner


def test_determine_enabled_sources_respects_search_modalities():
    config = {
        "search": {
            "modalities": {
                "git": {"enabled": True},
                "slack": {"enabled": True},
                "files": {"enabled": True},
                "issues": {"enabled": False},
            }
        },
        "activity_ingest": {"git": {"include_issues": False}},
        "graph": {"enabled": True},
        "activity_graph": {"signals": {"git": 1}},
    }

    enabled = MultiSourceReasoner.determine_enabled_sources(config)

    assert enabled == ["git", "slack", "docs", "activity_graph"]


def test_determine_enabled_sources_falls_back_to_defaults():
    config = {
        "graph": {"enabled": True},
        "activity_graph": {"weights": {"git": 1}},
    }
    enabled = MultiSourceReasoner.determine_enabled_sources(config)
    assert enabled == ["git", "slack", "docs", "issues", "activity_graph"]


class _FakeRetriever:
    def __init__(self, source: str):
        self.source = source

    def retrieve(self, query: str, **_: Any) -> EvidenceCollection:
        collection = EvidenceCollection(query=query)
        collection.add(
            Evidence(
                source=self.source,
                title=f"{self.source} evidence",
                text=f"{self.source} context for {query}",
            )
        )
        return collection


class _FakeLLM:
    def __init__(self):
        self.prompts = []

    def invoke(self, prompt: str):
        self.prompts.append(prompt)

        class _Resp:
            content = "Mock summary"

        return _Resp()


def test_infer_sources_defaults_include_docs(monkeypatch):
    def fake_get_retriever(source: str, _config: Dict[str, Any]):
        return _FakeRetriever(source)

    monkeypatch.setattr("src.agent.multi_source_reasoner.get_retriever", fake_get_retriever)

    config = {
        "search": {
            "modalities": {
                "git": {"enabled": True},
                "slack": {"enabled": True},
                "docs": {"enabled": True},
            }
        }
    }
    reasoner = MultiSourceReasoner(config, llm_client=_FakeLLM())

    sources = reasoner.infer_sources("summarize cross-system signals for billing checkout")

    assert "docs" in sources

