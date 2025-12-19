from fastapi.testclient import TestClient

import api_server
from src.traceability import TraceabilityStore
from src.impact.doc_issues import DocIssueService


def test_traceability_golden_path(tmp_path, monkeypatch):
    store_path = tmp_path / "investigations.json"
    doc_issue_path = tmp_path / "doc_issues.json"
    trace_store = TraceabilityStore(store_path, max_entries=10, retention_days=7)
    doc_issue_service = DocIssueService(doc_issue_path)

    monkeypatch.setattr(api_server, "traceability_store", trace_store)
    monkeypatch.setattr(api_server, "_traceability_env_enabled", True)
    cfg_copy = dict(api_server._traceability_cfg)
    cfg_copy["enabled"] = True
    monkeypatch.setattr(api_server, "_traceability_cfg", cfg_copy)
    monkeypatch.setattr(api_server.impact_service, "doc_issue_service", doc_issue_service)

    client = TestClient(api_server.app, raise_server_exceptions=False)

    investigation_id = api_server._maybe_record_investigation(
        session_id="test-session",
        user_message="What changed in core-api docs?",
        response_message="Investigated /slack docdrift",
        result_dict={"goal": "doc drift triage", "component_ids": ["component.core-api"]},
        result_status="completed",
        evidence=[
            {
                "evidence_id": "git:core-api:42",
                "source": "git",
                "title": "core-api PR #42",
                "url": "https://github.com/acme/core-api/pull/42",
            }
        ],
        tool_runs=[
            {
                "step_id": "step-1",
                "tool": "slash_git_summary",
                "status": "completed",
                "output_preview": "Summarized core-api PR #42",
            }
        ],
        files_attached=False,
        completion_event=None,
    )

    assert investigation_id, "Investigation should be recorded"

    resp = client.get("/traceability/investigations?limit=5")
    assert resp.status_code == 200
    payload = resp.json()
    assert any(item["id"] == investigation_id for item in payload["investigations"])

    resp = client.post(
        "/traceability/doc-issues",
        json={
            "title": "Docs drift for payments",
            "summary": "Docs missing new VAT field",
            "severity": "medium",
            "doc_path": "docs/payments_api.md",
            "component_ids": ["component.core-api"],
            "repo_id": "core-api",
            "origin_investigation_id": investigation_id,
            "evidence_ids": ["git:core-api:42"],
        },
    )
    assert resp.status_code == 200
    issue_payload = resp.json()
    assert issue_payload["origin_investigation_id"] == investigation_id
    assert issue_payload["doc_path"] == "docs/payments_api.md"

    stored_issues = doc_issue_service.list()
    assert len(stored_issues) == 1
    assert stored_issues[0]["origin_investigation_id"] == investigation_id

