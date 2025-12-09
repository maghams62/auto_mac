from datetime import datetime, timezone

from src.traceability.store import TraceabilityStore
from src.traceability.incidents import build_incident_candidate


def test_traceability_store_sets_incident_defaults(tmp_path):
    store = TraceabilityStore(tmp_path / "incidents.json", max_entries=10)
    stored = store.append(
        {
            "id": "abc",
            "question": "What is happening?",
        }
    )
    assert stored["type"] == "investigation"
    records = store.list(limit=1)
    assert records[0]["summary"] == "What is happening?"
    assert records[0]["severity"] is None
    assert records[0]["source_command"] is None


def test_build_incident_candidate_scores_sources():
    now = datetime.now(timezone.utc).isoformat()
    candidate = build_incident_candidate(
        query="payments spike",
        summary_text="Payments failing due to missing vat_code.",
        components=["core.payments"],
        doc_priorities=[
            {"doc_id": "docs/payments_api.md", "reason": "Missing new field", "updated_at": now},
        ],
        sources_queried=["slack", "git", "docs"],
        traceability_evidence=[
            {
                "evidence_id": "slack:1",
                "source": "slack",
                "title": "Slack complaint",
                "metadata": {"timestamp": now, "channel": "#incidents"},
            },
            {
                "evidence_id": "git:2041",
                "source": "git",
                "title": "Require vat_code PR",
                "metadata": {"timestamp": now, "repo": "core-api"},
            },
        ],
        investigation_id="inv-1",
        raw_trace_id="trace-1",
        source_command="slash_cerebros",
        llm_explanation="Explain incident",
        project_id="atlas",
        issue_id=None,
        structured_fields={
            "root_cause_explanation": "Docs out of date",
            "resolution_plan": ["Refresh docs/payments_api.md"],
        },
    )

    assert candidate["severity"] in {"medium", "high", "critical"}
    assert candidate["blast_radius_score"] > 0
    assert candidate["counts"]["components"] == 1
    assert candidate["counts"]["evidence"] == 2
    assert candidate["root_cause_explanation"] == "Docs out of date"
    assert candidate["resolution_plan"] == ["Refresh docs/payments_api.md"]
    entities = candidate.get("incident_entities")
    assert entities
    doc_entity = next((item for item in entities if item.get("entityType") == "doc"), None)
    assert doc_entity is not None
    assert doc_entity.get("suggestedAction") == "Refresh docs/payments_api.md"
    assert doc_entity.get("evidenceIds"), "doc entity should link to evidence"


def test_build_incident_candidate_includes_brain_links():
    candidate = build_incident_candidate(
        query="doc drift?",
        summary_text="Docs lag reality",
        components=[],
        doc_priorities=[],
        sources_queried=[],
        traceability_evidence=[],
        investigation_id="inv-1",
        raw_trace_id="trace-123",
        source_command="api_graph_query",
        brain_trace_url="/brain/trace/trace-123",
        brain_universe_url="/brain/universe",
    )

    assert candidate["brainTraceUrl"] == "/brain/trace/trace-123"
    assert candidate["brainUniverseUrl"] == "/brain/universe"

