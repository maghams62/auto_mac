import uuid

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone

import api_server
from src.youtube.models import VideoContext
from src.youtube.history_store import HistoryEntry, YouTubeHistoryStore


@pytest.fixture()
def client():
    return TestClient(api_server.app, raise_server_exceptions=False)


def _clear_session(session_id: str):
    memory = api_server.session_manager.get_or_create_session(session_id)
    memory.set_context("slash_youtube_video_contexts", {"videos": [], "active_video_id": None})


def _seed_context(session_id: str, video_id: str = "abc123") -> VideoContext:
    context = VideoContext.from_metadata(
        video_id,
        f"https://youtu.be/{video_id}",
        "demo-video",
        metadata={"title": "Demo Video", "channel_title": "Test Channel"},
    )
    api_server.youtube_context_service.save_context(session_id, context, make_active=True)
    return context


def test_list_youtube_videos_endpoint_returns_contexts(client):
    session_id = f"test-session-{uuid.uuid4().hex}"
    _seed_context(session_id)

    response = client.get(f"/api/youtube/videos/{session_id}")
    payload = response.json()

    assert response.status_code == 200
    assert payload["session_id"] == session_id
    assert len(payload["videos"]) == 1

    _clear_session(session_id)


def test_youtube_suggestions_endpoint_includes_session_entries(client):
    session_id = f"test-session-{uuid.uuid4().hex}"
    _seed_context(session_id)

    response = client.get(f"/api/youtube/suggestions?session_id={session_id}")
    payload = response.json()

    assert response.status_code == 200
    assert payload["suggestions"]["session"]

    _clear_session(session_id)


def test_refresh_endpoint_reindexes_video(client, monkeypatch):
    session_id = f"test-session-{uuid.uuid4().hex}"
    context = _seed_context(session_id, video_id="refresh123")

    class DummyTranscriptService:
        def fetch_transcript(self, video_id):
            return {
                "segments": [{"text": "Hello world", "start": 0.0, "duration": 2.0}],
                "language": "en",
            }

    class DummyVectorIndexer:
        def __init__(self):
            self.vector_service = None
            self.calls = 0

        def index_transcript(self, *args, **kwargs):
            self.calls += 1
            return True

    dummy_transcript = DummyTranscriptService()
    dummy_indexer = DummyVectorIndexer()
    monkeypatch.setattr(api_server, "youtube_transcript_service", dummy_transcript)
    monkeypatch.setattr(api_server, "youtube_vector_indexer", dummy_indexer)

    response = client.post(f"/api/youtube/videos/{context.video_id}/refresh?session_id={session_id}")
    payload = response.json()

    assert response.status_code == 200
    assert payload["video"]["video_id"] == context.video_id
    assert dummy_indexer.calls == 1

    _clear_session(session_id)


def test_youtube_history_search_returns_matches(client, tmp_path, monkeypatch):
    temp_store = YouTubeHistoryStore(tmp_path / "history.json", clipboard_enabled=False)
    monkeypatch.setattr(api_server, "_youtube_history_store", temp_store)

    temp_store.record(
        HistoryEntry(
            url="https://youtu.be/demo",
            video_id="demo",
            title="Demo Video",
            channel_title="Cerebros",
            description="Launch overview",
            thumbnail_url=None,
            last_used_at=datetime.now(timezone.utc).isoformat(),
        )
    )

    response = client.get("/api/youtube/history/search?query=demo&limit=5")
    payload = response.json()

    assert response.status_code == 200
    assert payload["results"]
    assert payload["results"][0]["title"] == "Demo Video"

