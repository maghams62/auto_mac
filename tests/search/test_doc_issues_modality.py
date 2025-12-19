import json

from src.search.config import ModalityConfig
from src.search.modalities.doc_issues import DocIssuesModalityHandler


def test_doc_issues_modality_returns_results(tmp_path):
    doc_issue_path = tmp_path / "doc_issues.json"
    doc_issue_path.write_text(
        json.dumps(
            [
                {
                    "id": "issue-42",
                    "doc_title": "Billing FAQ",
                    "summary": "Still references legacy quota.",
                    "severity": "medium",
                    "doc_path": "docs/billing_faq.md",
                    "doc_url": "https://docs.example.com/billing",
                    "component_ids": ["comp:billing-service"],
                    "updated_at": "2025-12-05T00:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )

    modality_cfg = ModalityConfig(
        modality_id="doc_issues",
        enabled=True,
        scope={"path": str(doc_issue_path)},
        weight=1.0,
        timeout_ms=2000,
        max_results=3,
        fallback_only=False,
    )
    handler = DocIssuesModalityHandler(
        modality_cfg,
        {"activity_graph": {"doc_issues_path": str(doc_issue_path)}},
    )

    results = handler.query("billing quota doc issue", limit=1)
    assert len(results) == 1
    first = results[0]
    assert first["source_type"] == "doc_issue"
    assert first["metadata"]["doc_issue_id"] == "issue-42"

