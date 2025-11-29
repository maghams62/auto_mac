from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List

import pytest

from src.vector import (
    ContextChunk,
    QdrantVectorSearchService,
    VectorSearchOptions,
    VectorSearchService,
)
from src.vector.service_factory import (
    VectorServiceConfigError,
    get_vector_search_service,
    validate_vectordb_config,
)


class DummyResponse:
    def __init__(self, status_code: int = 200, data: Dict[str, Any] | None = None):
        self.status_code = status_code
        self._data = data or {}

    def json(self) -> Dict[str, Any]:
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class DummyHTTPClient:
    def __init__(self):
        self.requests: List[Dict[str, Any]] = []

    def get(self, path: str):
        return DummyResponse(200, {"result": {}})

    def put(self, path: str, json: Dict[str, Any] | None = None, params: Dict[str, Any] | None = None):
        self.requests.append({"method": "PUT", "path": path, "json": json, "params": params})
        return DummyResponse(200, {"result": {}})

    def post(self, path: str, json: Dict[str, Any] | None = None):
        self.requests.append({"method": "POST", "path": path, "json": json})
        # Mimic search result payload
        return DummyResponse(
            200,
            {
                "result": [
                    {
                        "score": 0.9,
                        "id": "chunk-1",
                        "payload": {"chunk_id": "chunk-1", "entity_id": "chat:test:1", "text": "hello"},
                    }
                ]
            },
        )

    def delete(self, path: str, params: Dict[str, Any] | None = None):
        self.requests.append({"method": "DELETE", "path": path, "params": params})
        return DummyResponse(200, {"result": {}})

    def close(self):
        return None


class StubQdrantService(QdrantVectorSearchService):
    """Subclass that avoids real HTTP/OpenAI calls."""

    def __init__(self, config: Dict[str, Any]):
        VectorSearchService.__init__(self, config)
        vectordb_config = config.get("vectordb", {})
        self.enabled = True
        self.base_url = (vectordb_config.get("url") or "").rstrip("/")
        self.api_key = vectordb_config.get("api_key")
        self.collection = vectordb_config.get("collection", "test_collection")
        self.timeout = vectordb_config.get("timeout_seconds", 6.0)
        self.default_top_k = vectordb_config.get("default_top_k", 12)
        self.default_min_score = vectordb_config.get("min_score", 0.35)
        self.dimension = vectordb_config.get("dimension", 1536)
        self._http_client = DummyHTTPClient()
        self._collection_ready = True

    def _ensure_collection(self):
        self._collection_ready = True

    def _embed_text(self, text: str) -> List[float]:
        return [0.5, 0.5, 0.5, 0.5]


def test_validate_vectordb_config_legacy_env(monkeypatch):
    monkeypatch.setenv("VECTORDB_URL", "http://legacy:6333")
    monkeypatch.setenv("VECTORDB_API_KEY", "legacy-key")
    monkeypatch.delenv("QDRANT_URL", raising=False)
    config = {"vectordb": {"provider": "qdrant", "api_key": "", "collection": "test", "dimension": 4}}
    validated = validate_vectordb_config(config)
    assert validated["url"] == "http://legacy:6333"
    assert validated["collection"] == "test"


def test_validate_vectordb_config_requires_api_key_for_remote(monkeypatch):
    monkeypatch.delenv("QDRANT_URL", raising=False)
    cfg = {"vectordb": {"provider": "qdrant", "url": "https://example.com", "collection": "test"}}
    with pytest.raises(VectorServiceConfigError):
        validate_vectordb_config(cfg)


def test_index_chunks_clamps_payload_and_records_metrics(monkeypatch):
    config = {
        "vectordb": {
            "provider": "qdrant",
            "url": "http://localhost:6333",
            "collection": "test_collection",
            "api_key": "",
            "dimension": 4,
        }
    }
    service = StubQdrantService(config)
    long_text = "a" * 9000
    chunk = ContextChunk(
        chunk_id="chunk-1",
        entity_id="chat:test:1",
        source_type="chat",
        text=long_text,
        metadata={},
        collection="test_collection",
    )
    assert service.index_chunks([chunk]) is True
    # Ensure payload text was clamped and request recorded
    payload = service._http_client.requests[0]["json"]["points"][0]["payload"]
    assert len(payload["text"]) <= 8000
    assert payload["collection"] == "test_collection"


def test_get_vector_service_returns_none_when_disabled(monkeypatch):
    config = {"vectordb": {"enabled": False}}
    assert get_vector_search_service(config) is None


def test_get_vector_service_instantiates_stub(monkeypatch):
    captured = {}

    class StubService:
        def __init__(self, cfg):
            captured["config"] = cfg

        def is_configured(self):
            return True

    monkeypatch.setattr("src.vector.service_factory.QdrantVectorSearchService", StubService)
    config = {
        "vectordb": {
            "provider": "qdrant",
            "url": "http://localhost:6333",
            "collection": "test_collection",
            "api_key": "",
            "dimension": 4,
        }
    }
    service = get_vector_search_service(config)
    assert isinstance(service, StubService)
    assert captured["config"]["vectordb"]["collection"] == "test_collection"


@pytest.mark.integration
def test_qdrant_live_roundtrip(monkeypatch):
    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY", "")
    if not url:
        pytest.skip("QDRANT_URL not set")

    collection = f"test_vector_{uuid.uuid4().hex[:8]}"
    config = {
        "vectordb": {
            "provider": "qdrant",
            "url": url,
            "api_key": api_key,
            "collection": collection,
            "dimension": 4,
            "timeout_seconds": 10,
        }
    }

    class LiveService(QdrantVectorSearchService):
        def _embed_text(self, text: str) -> List[float]:
            return [0.25, 0.25, 0.25, 0.25]

    service = LiveService(config)
    chunk = ContextChunk(
        chunk_id=ContextChunk.generate_chunk_id(),
        entity_id=f"chat:integration:{collection}",
        source_type="chat",
        text="integration smoke test message",
        metadata={},
        collection=collection,
    )

    try:
        assert service.index_chunks([chunk]) is True
        results = service.semantic_search("integration smoke test message", VectorSearchOptions(top_k=1, min_score=0))
        assert results
        assert results[0].entity_id == chunk.entity_id
    finally:
        # Force-delete the temporary collection to keep the cluster clean
        import httpx

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["api-key"] = api_key
        client = httpx.Client(base_url=url.rstrip("/"), headers=headers, timeout=10)
        client.delete(f"/collections/{collection}", params={"force": "true"})
        client.close()

