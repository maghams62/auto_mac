import json

from src.agent.evidence_retrievers import DocIssuesEvidenceRetriever


def test_doc_issues_retriever_returns_ranked_evidence(tmp_path):
    doc_issue_path = tmp_path / "doc_issues.json"
    doc_issue_path.write_text(
        json.dumps(
            [
                {
                    "id": "issue-1",
                    "doc_title": "Core API Runbook",
                    "summary": "Runbook references deprecated flags.",
                    "severity": "high",
                    "doc_path": "docs/runbook.md",
                    "doc_url": "https://docs.example.com/runbook",
                    "component_ids": ["comp:core-api"],
                    "updated_at": "2025-12-06T00:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )
    config = {
        "activity_graph": {"doc_issues_path": str(doc_issue_path)},
        "activity_ingest": {"doc_issues": {"enabled": True}},
    }

    retriever = DocIssuesEvidenceRetriever(config)
    collection = retriever.retrieve("core-api doc issue", limit=1)

    assert len(collection.evidence_list) == 1
    evidence = collection.evidence_list[0]
    assert evidence.source_type == "doc_issue"
    assert "Severity" in evidence.content
    assert evidence.metadata.get("doc_issue_id") == "issue-1"

