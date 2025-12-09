import uuid

from fastapi.testclient import TestClient

import api_server
from src.search.query_trace import ChunkRef, QueryTrace, QueryTraceStore


def _build_client():
    return TestClient(api_server.app, raise_server_exceptions=False)


class FakeBrainGraphService:
    def __init__(self):
        self.last_chunk_ids = None

    def get_trace_graph(self, chunk_ids):
        self.last_chunk_ids = chunk_ids
        return {
            "nodes": [
                {"id": chunk_ids[0], "type": "chunk"},
                {"id": "source:abc", "type": "source"},
            ],
            "edges": [
                {"id": f"edge:{chunk_ids[0]}->source:abc", "from": chunk_ids[0], "to": "source:abc", "type": "BELONGS_TO"},
            ],
        }

    def get_universe_snapshot(self, **kwargs):  # pragma: no cover - unused here
        return {"nodes": [], "edges": []}


def test_brain_trace_endpoint_returns_trace(tmp_path, monkeypatch):
    api_server.query_trace_store = QueryTraceStore(tmp_path / "traces.jsonl")
    trace = QueryTrace(
        query_id=str(uuid.uuid4()),
        question="Why is billing broken?",
        modalities_used=["slack"],
        retrieved_chunks=[
            ChunkRef(
                chunk_id="chunk-1",
                source_type="slack",
                source_id="slack:C1:123",
                modality="slack",
                title="billing status",
                score=0.9,
                url="https://example.com",
            )
        ],
        chosen_chunks=[
            ChunkRef(
                chunk_id="chunk-1",
                source_type="slack",
                source_id="slack:C1:123",
                modality="slack",
                title="billing status",
                score=0.9,
            )
        ],
    )
    api_server.query_trace_store.append(trace)
    fake_graph = FakeBrainGraphService()
    monkeypatch.setattr(api_server, "graph_dashboard_service", fake_graph)

    client = _build_client()
    response = client.get(f"/api/brain/trace/{trace.query_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["question"] == "Why is billing broken?"
    assert payload["modalities_used"] == ["slack"]
    assert payload["retrieved_chunks"][0]["chunk_id"] == "chunk-1"
    graph = payload["graph"]
    assert any(node["type"] == "query" for node in graph["nodes"])
    assert any(edge["type"] == "RETRIEVED" for edge in graph["edges"])
    assert fake_graph.last_chunk_ids == ["chunk-1"]


def test_brain_trace_endpoint_returns_404(tmp_path):
    api_server.query_trace_store = QueryTraceStore(tmp_path / "traces.jsonl")
    client = _build_client()
    response = client.get(f"/api/brain/trace/{uuid.uuid4()}")
    assert response.status_code == 404

