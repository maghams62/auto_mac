from datetime import datetime, timezone

from src.graph.universal_nodes import UniversalNodeWriter
from src.vector.context_chunk import ContextChunk


class FakeGraphService:
    def __init__(self):
        self.writes = []

    def is_available(self) -> bool:
        return True

    def run_write(self, query, params=None):
        self.writes.append({"query": query, "params": params})


def _build_chunk(source_type: str, source_id: str, chunk_id: str = "chunk-1", **metadata_overrides) -> ContextChunk:
    return ContextChunk(
        chunk_id=chunk_id,
        entity_id=source_id,
        source_type=source_type,
        text=f"{source_type} content preview",
        component=None,
        service=None,
        tags=[source_type],
        metadata={
            "source_id": source_id,
            "display_name": f"{source_type.title()} Node",
            "path": f"/{source_type}/path",
            "workspace_id": "acme",
            **metadata_overrides,
        },
        timestamp=datetime.now(timezone.utc),
    )


def test_universal_node_writer_emits_chunk_and_source():
    graph_service = FakeGraphService()
    writer = UniversalNodeWriter(graph_service)
    chunks = [
        _build_chunk("slack", "slack:C123"),
        _build_chunk("file", "file:/docs/readme", chunk_id="chunk-2"),
    ]

    writer.ingest_chunks(chunks)

    assert len(graph_service.writes) == 2
    for entry, chunk in zip(graph_service.writes, chunks):
        params = entry["params"]
        assert params["chunk_id"] == chunk.chunk_id
        assert params["source_id"] == chunk.metadata["source_id"]
        assert params["chunk_props"]["source_type"] == chunk.source_type


def test_universal_node_writer_noop_without_graph():
    writer = UniversalNodeWriter(None)
    writer.ingest_chunks([_build_chunk("slack", "slack:C123")])
    # Should not raise and nothing to assert (no graph service).


def test_universal_node_writer_populates_optional_fields():
    graph_service = FakeGraphService()
    writer = UniversalNodeWriter(graph_service)
    chunk = ContextChunk(
        chunk_id="chunk-youtube-1",
        entity_id="youtube:video123",
        source_type="youtube",
        text="Segment text " * 50,
        metadata={
            "source_id": "youtube:video123",
            "display_name": "Deep Learning Talk",
            "path": "/videos/deep-learning",
            "parent_id": "channel:dl",
            "workspace_id": "brain",
            "url": "https://youtu.be/video123",
            "start_offset": 30.0,
            "end_offset": 60.0,
        },
    )

    writer.ingest_chunks([chunk])

    params = graph_service.writes[0]["params"]
    assert params["source_props"]["display_name"] == "Deep Learning Talk"
    assert params["source_props"]["parent_id"] == "channel:dl"
    assert params["chunk_props"]["start_offset"] == 30.0
    assert params["chunk_props"]["end_offset"] == 60.0
    assert params["chunk_props"]["url"] == "https://youtu.be/video123"

