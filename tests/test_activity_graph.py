from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock

from src.graph.analytics_service import GraphAnalyticsService
from src.ingestion.git_activity_ingestor import GitActivityIngestor


class DummyGraphService:
    """Minimal GraphService stub for ingestion tests."""

    def is_available(self) -> bool:
        return True

    def close(self) -> None:  # pragma: no cover - nothing to close in tests
        return None


class DummyVectorService:
    """Captures chunks sent to the vector index."""

    def __init__(self) -> None:
        self.chunks = []

    def index_chunks(self, chunks):
        self.chunks.extend(chunks)
        return True


def make_ingestor() -> GitActivityIngestor:
    config: Dict[str, Any] = {
        "activity_ingest": {
            "git": {
                "enabled": True,
                "default_components": ["comp:core"],
                "default_issue_components": ["comp:docs"],
                "repos": [
                    {
                        "owner": "example",
                        "name": "repo",
                        "include_prs": False,
                        "include_commits": False,
                    }
                ],
            }
        }
    }
    ingestor = GitActivityIngestor(
        config,
        graph_service=DummyGraphService(),
        vector_service=DummyVectorService(),
    )
    ingestor.graph_ingestor = MagicMock()
    ingestor.graph_ingestor.available.return_value = True
    return ingestor


def test_ingest_fixtures_indexes_pr_commit_and_issue():
    ingestor = make_ingestor()
    fixtures = {
        "pull_requests": [
            {
                "number": 42,
                "title": "Docs tweak",
                "state": "merged",
                "author": "bot",
                "merged_at": "2024-01-01T00:00:00Z",
                "url": "https://example/pr/42",
                "files": [
                    {"filename": "docs/en/docs/tutorial.md", "status": "modified", "additions": 5, "deletions": 1}
                ],
            }
        ],
        "commits": [
            {
                "sha": "abc123",
                "message": "Fix handler",
                "author": "dev",
                "date": "2024-01-01T01:00:00Z",
                "url": "https://example/commit/abc123",
                "files": [
                    {"filename": "fastapi/routing/core.py", "status": "modified", "additions": 10, "deletions": 2}
                ],
            }
        ],
        "issues": [
            {
                "number": 99,
                "title": "Docs unclear",
                "body": "Please improve the intro guide",
                "labels": ["documentation"],
                "comments": 2,
                "reactions": 1,
                "updated_at": "2024-01-02T00:00:00Z",
                "url": "https://example/issue/99",
                "author": "user",
            }
        ],
    }

    result = ingestor.ingest_fixtures(fixtures)

    assert result == {"prs": 1, "commits": 1, "issues": 1}
    assert ingestor.graph_ingestor.upsert_support_case.called
    assert len(ingestor.vector_service.chunks) == 3


def test_component_activity_includes_docs_and_dissatisfaction():
    graph_service = MagicMock()
    graph_service.is_available.return_value = True
    graph_service.run_query.return_value = [
        {
            "component_id": "comp:docs",
            "activity_score": 2.5,
            "signals": [{"id": "signal:1", "source": "github_pr", "weight": 1.5, "last_seen": "2024-01-01T00:00:00Z"}],
            "docs": ["doc:payments-guide"],
            "doc_count": 3,
            "dissatisfaction_score": 1.2,
        }
    ]

    analytics = GraphAnalyticsService(graph_service)
    result = analytics.get_component_activity("comp:docs")

    assert result["docs"] == ["doc:payments-guide"]
    assert result["doc_count"] == 3
    assert result["dissatisfaction_score"] == 1.2
    graph_service.run_query.assert_called_once()

