from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from src.commands.cerebros_command import CerebrosCommand
from src.search import build_search_system
from src.search.query_trace import QueryTraceStore


class FakeVectorService:
    def __init__(self):
        self.chunks = []

    def index_chunks(self, chunks):
        self.chunks.extend(chunks)
        return True

    def semantic_search(self, query: str, options: Optional[Any] = None):
        query_lower = (query or "").lower()
        results = []
        tokens = [token for token in query_lower.split() if token]
        for chunk in self.chunks:
            if options and options.source_types and chunk.source_type not in options.source_types:
                continue
            text = chunk.text.lower()
            if not tokens:
                results.append(chunk)
            elif any(token in text for token in tokens):
                results.append(chunk)
        return results


class FakeMetadataClient:
    def fetch_metadata(self, video_id: str, url: Optional[str]) -> Dict[str, Any]:
        return {
            "video_id": video_id,
            "title": "Diffusion Models 101",
            "channel_title": "Test Channel",
            "duration_seconds": 600,
        }


class FakeTranscriptService:
    def fetch_transcript(self, video_id: str) -> Dict[str, Any]:
        return {
            "segments": [
                {"text": "Diffusion models introduce noise schedules", "start": 0.0, "duration": 10.0},
                {"text": "They are powerful generative models", "start": 10.0, "duration": 10.0},
            ],
            "language": "en",
        }


VIDEO_ID = "abc123xyz09"


class StubGraphService:
    def __init__(self, *args, **kwargs):
        self.writes: List[Dict[str, Any]] = []

    def is_available(self) -> bool:
        return True

    def run_write(self, query, params=None):
        self.writes.append({"query": query, "params": params})


class RecordingGraphWriter:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def ingest_video(
        self,
        video,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        chunks: Optional[List[Any]] = None,
        workspace_id: Optional[str] = None,
    ) -> bool:
        self.calls.append({"video_id": video.video_id, "chunks": len(chunks or [])})
        return True


def _app_config(cache_path: Optional[str] = None):
    youtube_cfg: Dict[str, Any] = {}
    if cache_path:
        youtube_cfg["transcript_cache"] = {"path": cache_path}
    return {
        "youtube": youtube_cfg,
        "search": {
            "enabled": True,
            "workspace_id": "test-workspace",
            "modalities": {
                "youtube": {
                    "enabled": True,
                    "video_ids": [VIDEO_ID],
                }
            },
        }
    }


def test_youtube_ingest_and_search(tmp_path, monkeypatch: pytest.MonkeyPatch):
    vector_service = FakeVectorService()
    stub_graph = StubGraphService()
    monkeypatch.setattr("src.search.modalities.youtube.GraphService", lambda *args, **kwargs: stub_graph)
    cache_dir = tmp_path / "youtube_cache"
    config, registry = build_search_system(_app_config(str(cache_dir)), vector_service=vector_service)
    youtube_handler = registry.get_handler("youtube")
    assert youtube_handler is not None
    assert youtube_handler.graph_service is stub_graph

    recording_writer = RecordingGraphWriter()
    youtube_handler.graph_writer = recording_writer
    youtube_handler.ingestion_pipeline.graph_writer = recording_writer
    assert youtube_handler.ingestion_pipeline.graph_writer is recording_writer

    youtube_handler.metadata_client = FakeMetadataClient()
    youtube_handler.transcript_service = FakeTranscriptService()
    youtube_handler.ingestion_pipeline.metadata_client = youtube_handler.metadata_client
    youtube_handler.ingestion_pipeline.transcript_service = youtube_handler.transcript_service

    ingest_result = youtube_handler.ingest()
    assert ingest_result["indexed"] == 1
    assert recording_writer.calls, "Expected graph writer to receive ingest calls"

    trace_store = QueryTraceStore(tmp_path / "traces.jsonl")
    cerebros = CerebrosCommand(registry, trace_store=trace_store)
    payload = cerebros.search("noise schedules in diffusion models")
    results = payload["data"]["results"]
    assert any(result["source_type"] == "youtube" for result in results)

