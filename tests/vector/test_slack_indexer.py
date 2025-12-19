import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.vector.canonical_ids import CanonicalIdRegistry
from src.vector.indexers.slack_indexer import SlackVectorIndexer
from src.vector.local_vector_store import LocalVectorStore


class FakeEmbeddingProvider:
    def __init__(self):
        self.calls = 0

    def embed_batch(self, texts, batch_size=32):
        vectors = []
        for idx, _ in enumerate(texts):
            # Deterministic embedding (unit vector)
            vectors.append([1.0 + idx, 0.0, 0.0])
        self.calls += 1
        return vectors

    def embed(self, text: str):
        return [1.0, 0.0, 0.0]


@pytest.fixture()
def tmp_store(tmp_path):
    return LocalVectorStore(tmp_path / "slack_index.json")


def _write_synthetic_slack(tmp_path: Path) -> Path:
    payload = [
        {
            "id": "slack_message:#docs:123",
            "source_type": "slack_message",
            "workspace": "acme",
            "channel": "#docs",
            "channel_id": "C123DOCS",
            "message_ts": "1764152400.00000",
            "timestamp": datetime(2025, 11, 26, 10, 20, tzinfo=timezone.utc).isoformat(),
            "text_raw": "Docs alert about payments API missing vat_code.",
            "service_ids": ["docs-portal"],
            "component_ids": ["docs.payments"],
            "related_apis": ["/v1/payments/create"],
            "labels": ["doc_drift"],
        },
        {
            "id": "slack_message:#notifications:124",
            "source_type": "slack_message",
            "workspace": "acme",
            "channel": "#notifications",
            "channel_id": "C123NOTIFY",
            "message_ts": "1764157200.00000",
            "timestamp": datetime(2025, 11, 26, 11, 40, tzinfo=timezone.utc).isoformat(),
            "text_raw": "Docs alert for /v1/notifications/send template_version.",
            "service_ids": ["docs-portal", "notifications-service"],
            "component_ids": ["docs.notifications", "notifications.dispatch"],
            "related_apis": ["/v1/notifications/send"],
            "labels": ["doc_drift"],
        },
    ]
    path = tmp_path / "slack_events.json"
    path.write_text(json.dumps(payload, indent=2))
    return path


def test_slack_indexer_builds_local_index(tmp_path):
    slack_path = _write_synthetic_slack(tmp_path)
    config = {"openai": {"embedding_model": "text-embedding-3-small"}}
    embedding_provider = FakeEmbeddingProvider()
    store_path = tmp_path / "vector_index.json"
    vector_store = LocalVectorStore(store_path)
    registry = CanonicalIdRegistry.from_file()

    indexer = SlackVectorIndexer(
        config,
        data_path=slack_path,
        output_path=store_path,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        canonical_registry=registry,
    )

    result = indexer.build()
    assert result["indexed"] == 2
    records = json.loads(store_path.read_text())
    assert len(records) == 2
    assert records[0]["service_ids"][0] in registry.services
    assert records[0]["embedding"][0] == pytest.approx(1.0)


def test_local_store_search_filters(tmp_path):
    slack_path = _write_synthetic_slack(tmp_path)
    config = {"openai": {"embedding_model": "text-embedding-3-small"}}
    store_path = tmp_path / "vector_index.json"
    vector_store = LocalVectorStore(store_path)
    registry = CanonicalIdRegistry.from_file()
    embedding_provider = FakeEmbeddingProvider()

    indexer = SlackVectorIndexer(
        config,
        data_path=slack_path,
        output_path=store_path,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        canonical_registry=registry,
    )
    indexer.build()

    results = vector_store.search(
        "template version alert",
        embedding_provider=embedding_provider,
        filters={"apis": ["/v1/notifications/send"]},
        top_k=1,
    )
    assert len(results) == 1
    record = results[0]["record"]
    assert "/v1/notifications/send" in record["apis"]

