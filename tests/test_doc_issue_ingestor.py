import json
from pathlib import Path
from typing import Any, Dict, List

from src.ingestion.doc_issue_ingestor import DocIssueIngestor


class _StubGraphService:
    def is_available(self) -> bool:  # pragma: no cover - simple stub
        return True

    def close(self) -> None:  # pragma: no cover - simple stub
        pass


def test_doc_issue_ingestor_skips_when_disabled(tmp_path):
    ingestor = DocIssueIngestor(
        {"activity_ingest": {"doc_issues": {"enabled": False, "path": str(tmp_path / "missing.json")}}},
        graph_service=_StubGraphService(),
    )
    result = ingestor.ingest()
    assert result == {"issues": 0}


def test_doc_issue_ingestor_upserts_issue_and_support(monkeypatch, tmp_path):
    doc_issue_path = tmp_path / "doc_issues.json"
    sample_issue = {
        "id": "impact:doc:payments-guide:PR-42",
        "doc_id": "doc:payments-guide",
        "doc_title": "Payments Integration Guide",
        "doc_url": "/docs/payments",
        "doc_path": "docs/payments.md",
        "component_ids": ["comp:payments"],
        "severity": "high",
        "state": "open",
        "summary": "Payments docs missing payoutId parameter",
        "linked_change": "PR-42",
        "updated_at": "2025-12-01T00:42:30.296730+00:00",
    }
    doc_issue_path.write_text(json.dumps([sample_issue]), encoding="utf-8")

    captured_issues: List[Dict[str, Any]] = []
    captured_support: List[Dict[str, Any]] = []

    class _FakeGraphIngestor:
        def __init__(self, *_args, **_kwargs):
            pass

        def available(self) -> bool:
            return True

        def upsert_issue(self, **kwargs):
            captured_issues.append(kwargs)

        def upsert_support_case(self, **kwargs):
            captured_support.append(kwargs)

    monkeypatch.setattr(
        "src.ingestion.doc_issue_ingestor.GraphIngestor",
        _FakeGraphIngestor,
    )

    ingestor = DocIssueIngestor(
        {"activity_ingest": {"doc_issues": {"enabled": True, "path": str(doc_issue_path)}}},
        graph_service=_StubGraphService(),
    )
    result = ingestor.ingest()

    assert result == {"issues": 1}
    assert len(captured_issues) == 1
    assert captured_issues[0]["doc_ids"] == ["doc:payments-guide"]
    assert captured_issues[0]["component_ids"] == ["comp:payments"]

    assert len(captured_support) == 1
    support_props = captured_support[0]["properties"]
    assert support_props["source"] == "doc_issue"
    assert captured_support[0]["sentiment_weight"] >= 3

