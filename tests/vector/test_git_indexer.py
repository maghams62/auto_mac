import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.vector.canonical_ids import CanonicalIdRegistry
from src.vector.indexers.git_indexer import GitVectorIndexer
from src.vector.local_vector_store import LocalVectorStore


class FakeEmbeddingProvider:
    def embed_batch(self, texts, batch_size=32):
        vectors = []
        for idx, _ in enumerate(texts):
            vectors.append([1.0 + (idx * 0.1), 0.0, 0.0])
        return vectors

    def embed(self, text: str):
        return [1.0, 0.0, 0.0]


@pytest.fixture()
def canonical_registry():
    return CanonicalIdRegistry.from_file()


def _write_git_files(tmp_path: Path):
    events = [
        {
            "id": "git_commit:core-api:123",
            "source_type": "git_commit",
            "repo": "core-api",
            "branch": "main",
            "commit_sha": "1234567",
            "author": "alice",
            "timestamp": datetime(2025, 11, 25, 10, 15, tzinfo=timezone.utc).isoformat(),
            "message": "feat!: require vat_code for EU",
            "text_for_embedding": "Breaking change requiring vat_code for EU customers on /v1/payments/create.",
            "files_changed": ["src/payments.py", "openapi/payments.yaml"],
            "service_ids": ["core-api-service"],
            "component_ids": ["core.payments"],
            "changed_apis": ["/v1/payments/create"],
            "labels": ["breaking_change"],
        }
    ]

    prs = [
        {
            "id": "git_pr:notifications-service:142",
            "source_type": "git_pr",
            "repo": "notifications-service",
            "branch": "main",
            "pr_number": 142,
            "author": "dave",
            "timestamp": datetime(2025, 11, 26, 12, 0, tzinfo=timezone.utc).isoformat(),
            "title": "Require template_version for /v1/notifications/send",
            "body": "Compliance requested template_version logging.",
            "text_for_embedding": "Adds template_version argument to send_notification.",
            "files_changed": ["src/notifications.py", "docs/notification_playbook.md"],
            "service_ids": ["notifications-service"],
            "component_ids": ["notifications.dispatch"],
            "changed_apis": ["/v1/notifications/send"],
            "labels": ["api_contract", "doc_drift"],
        }
    ]

    events_path = tmp_path / "git_events.json"
    prs_path = tmp_path / "git_prs.json"
    events_path.write_text(json.dumps(events, indent=2))
    prs_path.write_text(json.dumps(prs, indent=2))
    return events_path, prs_path


def test_git_indexer_builds_records(tmp_path, canonical_registry):
    events_path, prs_path = _write_git_files(tmp_path)
    store_path = tmp_path / "git_index.json"
    indexer = GitVectorIndexer(
        config={"openai": {"embedding_model": "text-embedding-3-small"}},
        events_path=events_path,
        prs_path=prs_path,
        output_path=store_path,
        embedding_provider=FakeEmbeddingProvider(),
        vector_store=LocalVectorStore(store_path),
        canonical_registry=canonical_registry,
    )

    result = indexer.build()
    assert result["indexed"] == 2
    records = json.loads(store_path.read_text())
    assert len(records) == 2
    assert records[0]["service_ids"][0] in canonical_registry.services


def test_git_indexer_search_by_api(tmp_path, canonical_registry):
    events_path, prs_path = _write_git_files(tmp_path)
    store_path = tmp_path / "git_index.json"
    store = LocalVectorStore(store_path)

    indexer = GitVectorIndexer(
        config={"openai": {"embedding_model": "text-embedding-3-small"}},
        events_path=events_path,
        prs_path=prs_path,
        output_path=store_path,
        embedding_provider=FakeEmbeddingProvider(),
        vector_store=store,
        canonical_registry=canonical_registry,
    )
    indexer.build()

    results = store.search(
        "template version receipts",
        embedding_provider=FakeEmbeddingProvider(),
        filters={"apis": ["/v1/notifications/send"]},
        top_k=1,
    )
    assert len(results) == 1
    assert "/v1/notifications/send" in results[0]["record"]["apis"]

