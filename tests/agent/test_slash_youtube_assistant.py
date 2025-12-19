from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.agent.slash_youtube_assistant import SlashYouTubeAssistant
from src.youtube.models import TranscriptChunk, VideoContext
from src.vector.context_chunk import ContextChunk
from src.youtube.transcript_cache import YouTubeTranscriptCache
from src.services.youtube_context_service import YouTubeContextService


class DummyRegistry:
    def __init__(self):
        self.calls = []
        self.payload_text = "Detailed answer describing the clip."

    def execute_tool(self, tool_name, params, session_id=None):
        self.calls.append((tool_name, params, session_id))
        return {
            "message": "Synthesized 1 source into 42 words.",
            "summary": "Detailed answer describing the clip.",
            "synthesized_content": self.payload_text,
        }


class FakeSessionMemory:
    def __init__(self):
        self.shared_context = {}

    def set_context(self, key, value):
        self.shared_context[key] = value

    def get_context(self, key, default=None):
        return self.shared_context.get(key, default)


class FakeSessionManager:
    def __init__(self):
        self.memory = FakeSessionMemory()

    def get_or_create_session(self, session_id=None, user_id=None):
        return self.memory

    # Support trace store injection path if needed
    def get_session_id(self):
        return "sess-trace"


class StubHistoryStore:
    def __init__(self):
        self.recorded = []

    def record(self, entry):
        self.recorded.append(entry)

    def get_suggestions(self, *_, **__):
        return {"recent": [], "clipboard": []}


class StubMetadataClient:
    def fetch_metadata(self, video_id, url=None):
        return {
            "title": "Mixture-of-Experts AMA",
            "channel_title": "Cerebros",
            "duration_seconds": 600,
        }


class StubTranscriptService:
    def __init__(self):
        self.calls = []

    def fetch_transcript(self, video_id):
        self.calls.append(video_id)
        return {
            "segments": [
                {"text": "Intro to mixtures", "start": 0.0, "duration": 5.0},
                {"text": "Routing discussion", "start": 30.0, "duration": 8.0},
            ],
            "language": "en",
        }


class StubVectorIndexer:
    def __init__(self):
        self.index_calls = 0
        self.vector_service = None

    def index_transcript(self, *args, **kwargs):
        self.index_calls += 1
        return True

    def build_context_chunks(self, video, chunks, *, session_id, workspace_id):
        context_chunks = []
        for chunk in chunks:
            context_chunks.append(
                ContextChunk(
                    chunk_id=ContextChunk.generate_chunk_id(),
                    entity_id=f"{video.video_id}:{chunk.index}",
                    source_type="youtube",
                    text=chunk.text,
                    tags=["youtube"],
                    metadata={
                        "source_id": video.video_id,
                        "workspace_id": workspace_id,
                        "session_id": session_id,
                    },
                )
            )
        return context_chunks


class StubRetriever:
    def __init__(self):
        self.semantic_calls = 0
        self.timestamp_calls = 0
        self.last_timestamp = None
        self.force_empty = False

    def retrieve_semantic(self, context: VideoContext, question: str, top_k: int = 4):
        self.semantic_calls += 1
        if self.force_empty:
            return []
        return [
            TranscriptChunk(
                video_id=context.video_id,
                index=0,
                start_seconds=0,
                end_seconds=30,
                text="Intro to mixtures",
            )
        ]

    def retrieve_by_timestamp(self, context: VideoContext, seconds: float, window: float = 25.0):
        self.timestamp_calls += 1
        self.last_timestamp = seconds
        if self.force_empty:
            return []
        return context.chunks or self.retrieve_semantic(context, "")


def build_assistant():
    config = {
        "youtube": {
            "history_path": "tests/data/tmp_history.json",
            "vectordb": {"collection": "youtube_embeddings"},
        }
    }
    registry = DummyRegistry()
    session_manager = FakeSessionManager()
    history_store = StubHistoryStore()
    context_service = YouTubeContextService(session_manager, history_store, config)
    transcript = StubTranscriptService()
    vector_indexer = StubVectorIndexer()
    retriever = StubRetriever()
    cache_path = Path("tests/data/tmp_youtube_cache")
    cache_path.mkdir(parents=True, exist_ok=True)
    assistant = SlashYouTubeAssistant(
        registry,
        session_manager,
        config,
        context_service=context_service,
        history_store=history_store,
        metadata_client=StubMetadataClient(),
        transcript_service=transcript,
        vector_indexer=vector_indexer,
        retriever=retriever,
        transcript_cache=YouTubeTranscriptCache(cache_path),
    )
    try:
        from src.search.query_trace import QueryTraceStore
        assistant.query_trace_store = QueryTraceStore("tests/data/tmp_trace.jsonl")
    except Exception:
        pass
    return assistant, registry, context_service, retriever


def test_attach_and_answer_question():
    assistant, registry, context_service, _ = build_assistant()
    response = assistant.handle("https://youtu.be/dQw4w9WgXcQ What happens?", session_id="sess-1")

    assert response["type"] == "youtube_summary"
    assert response["status"] == "success"
    assert response["message"] == "Detailed answer describing the clip."
    assert "Synthesized 1 source" in response.get("details", "")
    assert "Intro to mixtures" in response.get("details", "")
    assert response["data"].get("evidence"), "Evidence snippets should be present"
    assert response["sources"], "Expected timestamped sources"
    assert response["data"]["sources"], "Sources should be mirrored in payload"
    # Trace URL should be present when trace store is attached
    assert response["data"].get("trace_url") is not None
    assert registry.calls
    videos = context_service.list_contexts("sess-1")
    assert len(videos) == 1
    assert videos[0].video_id == "dQw4w9WgXcQ"


def test_title_recall_routes_to_existing_video():
    assistant, _, context_service, retriever = build_assistant()
    assistant.handle("https://youtu.be/dQw4w9WgXcQ Explain intro", session_id="sess-2")

    alias = context_service.list_contexts("sess-2")[0].alias
    response = assistant.handle(f"@{alias} Summarize routing", session_id="sess-2")

    assert response["type"] == "youtube_summary"
    assert response["status"] == "success"
    assert retriever.semantic_calls >= 2


def test_timestamp_question_invokes_timestamp_retriever():
    assistant, _, context_service, retriever = build_assistant()
    assistant.handle("https://youtu.be/dQw4w9WgXcQ Explain intro", session_id="sess-3")
    alias = context_service.list_contexts("sess-3")[0].alias

    assistant.handle(f"@{alias} What happens at 0:30?", session_id="sess-3")

    assert retriever.timestamp_calls == 1
    assert retriever.last_timestamp == 30


def test_structured_answer_renders_sections():
    assistant, registry, _, _ = build_assistant()
    registry.payload_text = json.dumps(
        {
            "gist": "Hosts are Alice and Bob discussing sparse gating.",
            "sections": [
                {"title": "High-level concept", "body": "Focuses on mixture-of-experts routing."},
                {"title": "Answer to your specific question", "body": "They walk through the host format."},
            ],
            "hosts": ["Alice", "Bob"],
            "key_moments": [{"timestamp": "0:30", "summary": "Intro from Alice."}],
            "key_concepts": [
                {"name": "Sparse gating", "summary": "Router picks a few experts.", "timestamp": "1:00", "example": "Top-2 gating"}
            ],
            "channel_notes": "Cerebros shares research breakdowns for practitioners.",
            "related_context": ["Connects to Cerebros MoE Git history."],
            "extra_context": ["Recorded on the Cerebros channel."],
        }
    )

    response = assistant.handle("https://youtu.be/dQw4w9WgXcQ Who is hosting?", session_id="sess-struct")

    assert response["status"] == "success"
    assert "Hosts & speakers" in response["message"]
    assert "Alice" in response["message"]
    assert "Key concepts" in response["message"]


def test_metadata_fallback_when_no_segments():
    assistant, _, _, retriever = build_assistant()
    retriever.force_empty = True

    response = assistant.handle("https://youtu.be/dQw4w9WgXcQ Who presents this?", session_id="sess-empty")

    assert response["status"] == "success"
    assert "metadata" in response["message"].lower()
    assert response["data"]["segments"] == []
    assert response["sources"] == []

