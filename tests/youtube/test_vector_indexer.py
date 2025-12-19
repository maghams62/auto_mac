from src.youtube.models import TranscriptChunk, VideoContext
from src.youtube.vector_indexer import YouTubeVectorIndexer


class StubVectorService:
    def __init__(self):
        self.chunks = []
        self.collection = "youtube_embeddings"

    def index_chunks(self, chunks):
        self.chunks.extend(chunks)
        return True


def test_vector_indexer_generates_universal_payload():
    config = {
        "youtube": {
            "vectordb": {"collection": "youtube_embeddings"},
        }
    }
    stub_service = StubVectorService()
    indexer = YouTubeVectorIndexer(config, vector_service=stub_service)

    context = VideoContext.from_metadata(
        "vid123",
        "https://youtu.be/vid123",
        "demo-alias",
        metadata={"title": "Demo Talk", "channel_title": "Cerebros", "duration_seconds": 120},
    )
    chunk = TranscriptChunk(
        video_id="vid123",
        index=0,
        start_seconds=10,
        end_seconds=40,
        text="Transformers are powerful.",
        token_count=6,
    )

    success = indexer.index_transcript(context, [chunk], session_id="sess-1", workspace_id="workspace-1")

    assert success is True
    assert len(stub_service.chunks) == 1
    stored = stub_service.chunks[0]
    assert stored.source_type == "youtube"
    assert stored.metadata["source_id"] == "vid123"
    assert stored.metadata["workspace_id"] == "workspace-1"
    assert stored.metadata["start_offset"] == 10
    assert "youtube" in stored.tags

