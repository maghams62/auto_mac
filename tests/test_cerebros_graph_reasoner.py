from typing import Any, Dict, List

import pytest

from src.cerebros.graph_reasoner import run_cerebros_reasoner
from src.agent.multi_source_reasoner import MultiSourceReasoner as _RealMultiSourceReasoner


class _StubTool:
    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def invoke(self, _: Dict[str, Any]) -> Dict[str, Any]:
        return self._payload


_REASONER_STATE: Dict[str, Any] = {
    "summary": "Docs are lagging behind code.",
    "custom_evidence": None,
    "last_sources": None,
}

_NARRATIVE_STATE: Dict[str, Any] = {
    "context": None,
}


class _StubReasoner:
    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    def query(self, query: str, sources: List[str]):
        assert query
        assert sources
        _REASONER_STATE["last_sources"] = list(sources)
        evidence = (
            list(_REASONER_STATE["custom_evidence"])
            if _REASONER_STATE["custom_evidence"] is not None
            else [
                {
                    "source_type": source,
                    "source_name": f"{source} entry",
                    "url": f"https://example.com/{source}",
                    "metadata": {"source": source},
                }
                for source in sources
            ]
        )
        return {
            "summary": _REASONER_STATE["summary"],
            "sources_queried": sources,
            "evidence": {"evidence": evidence},
        }

    @staticmethod
    def determine_enabled_sources(config: Dict[str, Any]) -> List[str]:
        return _RealMultiSourceReasoner.determine_enabled_sources(config)


@pytest.fixture(autouse=True)
def reset_reasoner_state(monkeypatch):
    _REASONER_STATE["summary"] = "Docs are lagging behind code."
    _REASONER_STATE["custom_evidence"] = None
    _REASONER_STATE["last_sources"] = None
    monkeypatch.setattr("src.cerebros.graph_reasoner.MultiSourceReasoner", _StubReasoner)
    monkeypatch.setattr(
        "src.cerebros.graph_reasoner.resolve_component_id_tool",
        _StubTool({"component_id": "comp:core-api"}),
    )
    monkeypatch.setattr(
        "src.cerebros.graph_reasoner.get_component_activity_tool",
        _StubTool(
            {
                "component_id": "comp:core-api",
                "component_name": "Core API",
                "git_events": 5,
                "slack_conversations": 2,
                "slack_complaints": 1,
                "open_doc_issues": 2,
                "recent_slack_events": [
                    {
                        "channel_name": "#core-api",
                        "text": "Is the rollout doc updated for the new flags?",
                        "permalink": "https://slack.example.com/archives/C123/p2",
                    }
                ],
            }
        ),
    )
    monkeypatch.setattr(
        "src.cerebros.graph_reasoner.list_doc_issues_tool",
        _StubTool(
            {
                "doc_issues": [
                    {
                        "doc_id": "doc:core-api-runbook",
                        "doc_title": "Core API Runbook",
                        "severity": "high",
                        "impact_level": "high",
                        "confidence": 0.9,
                        "doc_url": "https://docs.example.com/core-api",
                        "component_ids": ["comp:core-api"],
                        "summary": "Runbook still references v1 rollout flags.",
                        "change_title": "Rename FREE_TIER flags",
                        "doc_update_hint": "Refresh Core API Runbook to describe the new FREE_TIER flags.",
                        "change_context": {
                            "source_kind": "git",
                            "title": "Rename FREE_TIER flags",
                            "identifier": "core-api@abc123",
                            "repo": "core-api",
                        },
                        "slack_context": {
                            "channel": "#core-api",
                            "text": "Docs still say to flip FREE_TIER_V1 which no longer exists.",
                            "permalink": "https://slack.example.com/archives/C123/p1",
                        },
                        "labels": ["free-tier", "runbook"],
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        "src.cerebros.graph_reasoner.get_context_impacts_tool",
        _StubTool({"error": "context disabled"}),
    )
    from src.cerebros.graph_reasoner import Option1NarrativeGenerator as _RealNarrative

    original_generate = _RealNarrative.generate

    def spy_generate(self, query: str, context: Dict[str, Any]) -> str:
        _NARRATIVE_STATE["context"] = context
        return original_generate(self, query=query, context=context)

    monkeypatch.setattr(
        "src.cerebros.graph_reasoner.Option1NarrativeGenerator.generate",
        spy_generate,
    )
    _NARRATIVE_STATE["context"] = None

    yield


def test_run_cerebros_reasoner_builds_answer_with_priorities():
    config = {
        "graph": {"enabled": True},
        "activity_graph": {"enabled": True},
        "activity_signals": {"weights": {"git": 3, "issues": 2, "support": 1, "slack": 1, "docs": 1}},
    }

    result = run_cerebros_reasoner(
        config=config,
        query="which docs should we update first for core-api?",
        graph_params={"componentId": "comp:core-api"},
    )

    assert result.cerebros_answer["option"] == "activity_graph"
    assert result.doc_insights is not None
    assert result.doc_insights.get("doc_priorities")
    assert result.cerebros_answer.get("doc_priorities")
    answer = result.cerebros_answer
    assert answer.get("root_cause_explanation")
    assert answer.get("activity_signals") and answer["activity_signals"].get("git_events") == 5
    assert answer.get("resolution_plan")
    assert answer.get("activity_score") is not None
    assert answer.get("dissatisfaction_score") is not None
    candidate = result.response_payload.get("incident_candidate") or {}
    assert candidate.get("brainTraceUrl")
    assert candidate.get("brainUniverseUrl")
    entities = candidate.get("incident_entities")
    assert entities and any(row.get("entityType") == "doc" for row in entities)



def test_run_cerebros_reasoner_emits_option1_sources_and_answer(monkeypatch):
    config = {
        "graph": {"enabled": True},
        "activity_graph": {"enabled": True},
    }
    _REASONER_STATE["summary"] = "Core API Runbook needs updates due to recent changes."
    _REASONER_STATE["custom_evidence"] = [
        {
            "source_type": "doc",
            "source_name": "Core API Runbook",
            "url": "https://docs.example.com/core-api",
            "metadata": {"component": "comp:core-api"},
        },
        {
            "source_type": "slack",
            "source_name": "#core-api thread",
            "url": "https://slack.test/thread",
            "metadata": {"channel_name": "#core-api"},
        },
    ]

    result = run_cerebros_reasoner(
        config=config,
        query="Which docs should we update first for core-api?",
        graph_params={"componentId": "comp:core-api"},
    )

    answer = result.cerebros_answer
    assert answer["option"] == "activity_graph"
    assert any(src["type"] == "doc" for src in answer["sources"])
    assert any(src["type"] == "slack" for src in answer["sources"])
    assert "Summary" in answer["answer"]
    assert "What’s drifting" in answer["answer"]


def test_run_cerebros_reasoner_includes_doc_issue_sources():
    config = {
        "graph": {"enabled": True},
        "activity_graph": {"enabled": True},
        "search": {
            "modalities": {
                "doc_issues": {"enabled": True},
            }
        },
    }
    _REASONER_STATE["custom_evidence"] = [
        {
            "source_type": "doc_issue",
            "source_name": "Core API Runbook drift",
            "url": "https://docs.example.com/core-api",
            "metadata": {"doc_issue_id": "docissue-1", "severity": "high"},
        }
    ]

    result = run_cerebros_reasoner(
        config=config,
        query="Which doc issues should we tackle for comp:core-api?",
        graph_params={"componentId": "comp:core-api"},
    )

    answer = result.cerebros_answer
    assert any(src["type"] == "doc_issue" for src in answer["sources"])
    assert any(src.get("severity") == "high" for src in answer["sources"] if src["type"] == "doc_issue")


def test_run_cerebros_reasoner_handles_option2_dependencies(monkeypatch):
    config = {
        "graph": {"enabled": True},
        "activity_graph": {"enabled": True},
        "activity_signals": {"weights": {"git": 2, "issues": 1, "support": 1, "slack": 1, "docs": 1}},
    }
    _REASONER_STATE["summary"] = "Service A change impacts Service B and Service C docs."
    _REASONER_STATE["custom_evidence"] = [
        {
            "source_type": "git",
            "source_name": "Service A breaking change",
            "url": "https://git.example.com/service-a/pr/1",
            "metadata": {"component": "service-a"},
        },
        {
            "source_type": "doc",
            "source_name": "Service B API guide",
            "url": "https://docs.example.com/service-b",
            "metadata": {"component": "service-b"},
        },
    ]
    monkeypatch.setattr(
        "src.cerebros.graph_reasoner.get_context_impacts_tool",
        _StubTool(
            {
                "impacts": [
                    {"component_id": "service-b", "docs_to_update": ["doc:service-b-guide"]},
                    {"component_id": "service-c", "docs_to_update": ["doc:service-c-guide"]},
                ]
            }
        ),
    )
    monkeypatch.setattr(
        "src.cerebros.graph_reasoner.list_doc_issues_tool",
        _StubTool(
            {
                "doc_issues": [
                    {
                        "doc_id": "doc:service-a-guide",
                        "doc_title": "Service A Guide",
                        "severity": "medium",
                        "impact_level": "medium",
                        "confidence": 0.8,
                        "doc_url": "https://docs.example.com/service-a",
                        "component_ids": ["service-a"],
                        "doc_update_hint": "Update Service A Guide for the new downstream contract.",
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        "src.cerebros.graph_reasoner.resolve_component_id_tool",
        _StubTool({"component_id": "service-a"}),
    )

    result = run_cerebros_reasoner(
        config=config,
        query="Service A changed its API; who is impacted?",
        graph_params={"componentId": "service-a"},
    )

    answer = result.cerebros_answer
    assert answer["option"] == "cross_system_context"
    assert set(answer["components"]) == {"service-a", "service-b", "service-c"}
    assert any(src["type"] == "git" for src in answer["sources"])
    assert any(src["type"] == "doc" for src in answer["sources"])
    assert answer.get("dependency_impact")
    assert answer.get("impact_summary")


def test_cross_repo_drift_surfaces_all_modalities(monkeypatch):
    config = {
        "graph": {"enabled": True},
        "activity_graph": {"enabled": True},
        "activity_signals": {"weights": {"git": 3, "docs": 2, "slack": 1}},
    }
    _REASONER_STATE["summary"] = "Core API quota change is breaking billing checkout docs."
    _REASONER_STATE["custom_evidence"] = [
        {
            "source_type": "git",
            "source_name": "core-api quota patch",
            "url": "https://git.example.com/core-api/commit/abc",
            "metadata": {"component_id": "comp:core-api", "repo": "core-api"},
        },
        {
            "source_type": "slack",
            "source_name": "#billing-checkout thread",
            "url": "https://slack.example.com/archives/C1/p1",
            "metadata": {"component_id": "comp:billing-service", "channel": "#billing-checkout"},
        },
        {
            "source_type": "doc",
            "source_name": "Docs portal pricing guide",
            "url": "https://docs.example.com/pricing",
            "metadata": {"component_id": "comp:docs-portal"},
            "entity_id": "doc:docs-portal-free-tier",
        },
    ]
    monkeypatch.setattr(
        "src.cerebros.graph_reasoner.get_context_impacts_tool",
        _StubTool(
            {
                "impacts": [
                    {"component_id": "comp:billing-service", "docs_to_update": ["doc:billing-plan-config"]},
                    {"component_id": "comp:docs-portal", "docs_to_update": ["doc:docs-portal-free-tier"]},
                ]
            }
        ),
    )
    monkeypatch.setattr(
        "src.cerebros.graph_reasoner.list_doc_issues_tool",
        _StubTool(
            {
                "doc_issues": [
                    {
                        "doc_id": "doc:billing-plan-config",
                        "doc_title": "Billing Plan Config Reference",
                        "severity": "high",
                        "impact_level": "high",
                        "confidence": 0.85,
                        "doc_url": "https://docs.example.com/billing-plan",
                        "component_ids": ["comp:billing-service"],
                        "doc_update_hint": "Document the 300 request quota in billing plan reference.",
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        "src.cerebros.graph_reasoner.resolve_component_id_tool",
        _StubTool({"component_id": "comp:core-api"}),
    )

    result = run_cerebros_reasoner(
        config=config,
        query="What is the downstream impact of the core-api quota change on billing checkout?",
        graph_params={"componentId": "comp:core-api"},
    )

    answer = result.cerebros_answer
    assert answer["option"] == "cross_system_context"
    assert {
        "comp:core-api",
        "comp:billing-service",
        "comp:docs-portal",
    }.issubset(set(answer["components"]))
    source_types = {src["type"] for src in answer["sources"]}
    assert {"git", "slack", "doc"}.issubset(source_types)


def test_reasoner_respects_enabled_modalities():
    config = {
        "graph": {"enabled": True},
        "activity_graph": {"enabled": True},
        "search": {
            "modalities": {
                "slack": {"enabled": True},
                "git": {"enabled": True},
                "docs": {"enabled": True},
                "issues": {"enabled": True},
            }
        },
    }

    result = run_cerebros_reasoner(
        config=config,
        query="show me multi-modal context",
        graph_params={"componentId": "comp:core-api"},
    )

    assert "slack" in _REASONER_STATE["last_sources"]
    assert "git" in _REASONER_STATE["last_sources"]
    assert set(result.sources_queried) == set(_REASONER_STATE["last_sources"])


def test_reasoner_disables_slack_when_configured():
    config = {
        "graph": {"enabled": True},
        "activity_graph": {"enabled": True},
        "search": {
            "modalities": {
                "slack": {"enabled": False},
                "git": {"enabled": True},
                "docs": {"enabled": True},
                "issues": {"enabled": True},
            }
        },
    }

    result = run_cerebros_reasoner(
        config=config,
        query="summarize git + docs only",
        graph_params={"componentId": "comp:core-api"},
    )

    assert "slack" not in _REASONER_STATE["last_sources"]
    assert all(src["type"] != "slack" for src in result.cerebros_answer["sources"])


def test_doc_priorities_used_as_sources_when_evidence_missing():
    config = {
        "graph": {"enabled": True},
        "activity_graph": {"enabled": True},
    }
    _REASONER_STATE["summary"] = "No evidence found to answer this query."
    _REASONER_STATE["custom_evidence"] = []

    result = run_cerebros_reasoner(
        config=config,
        query="Which docs should we update first for core-api?",
        graph_params={"componentId": "comp:core-api"},
    )

    answer = result.cerebros_answer
    sources = answer["sources"]
    assert any(src["type"] == "doc" for src in sources)
    assert "What to change now" in answer["answer"]


def test_reasoner_guesses_component_from_query(monkeypatch):
    config = {
        "graph": {"enabled": True},
        "activity_graph": {"enabled": True},
    }
    _REASONER_STATE["summary"] = "No evidence found to answer this query."
    _REASONER_STATE["custom_evidence"] = []

    result = run_cerebros_reasoner(
        config=config,
        query="Which docs should we update first for core-api rollouts?",
        graph_params={},
    )

    assert result.component_ids == ["comp:core-api"]
    assert any(src["type"] == "doc" for src in result.cerebros_answer["sources"])
    assert "Summary" in result.cerebros_answer["answer"]


def test_option1_context_passed_to_narrative_generator():
    config = {
        "graph": {"enabled": True},
        "activity_graph": {"enabled": True},
    }

    run_cerebros_reasoner(
        config=config,
        query="Which docs should we update first for core-api?",
        graph_params={"componentId": "comp:core-api"},
    )

    context = _NARRATIVE_STATE["context"]
    assert context is not None
    assert context["focus_doc"]["doc_id"] == "doc:core-api-runbook"
    assert len(context["git_changes"]) >= 1
    assert len(context["slack_threads"]) >= 1

