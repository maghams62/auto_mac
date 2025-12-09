import uuid

import pytest
from fastapi.testclient import TestClient

# Provide a lightweight stub for youtube_transcript_api so api_server imports succeed in CI
import sys
import types

if "youtube_transcript_api" not in sys.modules:
    yt_module = types.ModuleType("youtube_transcript_api")

    class _YTBaseError(Exception):
        pass

    class TooManyRequests(_YTBaseError):
        pass

    class TranscriptsDisabled(_YTBaseError):
        pass

    class VideoUnavailable(_YTBaseError):
        pass

    class NoTranscriptFound(_YTBaseError):
        pass

    class YouTubeTranscriptApi:
        @staticmethod
        def get_transcript(video_id: str, languages=None):
            return [
                {"text": f"Transcript for {video_id}", "language": (languages or ["en"])[0]},
            ]

    yt_module.YouTubeTranscriptApi = YouTubeTranscriptApi
    yt_module.NoTranscriptFound = NoTranscriptFound
    yt_module.TranscriptsDisabled = TranscriptsDisabled
    yt_module.VideoUnavailable = VideoUnavailable
    yt_module.TooManyRequests = TooManyRequests
    sys.modules["youtube_transcript_api"] = yt_module

import api_server


@pytest.fixture()
def client():
    return TestClient(api_server.app, raise_server_exceptions=False)


def test_conversation_history_empty_session(client):
    session_id = f"test-session-{uuid.uuid4()}"
    api_server.session_manager.delete_session(session_id)

    response = client.get(f"/api/conversation/history/{session_id}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["session_id"] == session_id
    assert payload["total_messages"] == 0
    assert payload["messages"] == []


def test_conversation_history_returns_interactions(client):
    session_id = f"history-session-{uuid.uuid4()}"
    memory = api_server.session_manager.get_or_create_session(session_id)
    memory.add_interaction(
        user_request="Ping the status board",
        agent_response={"message": "Status board refreshed"},
        plan=[{"id": 1, "action": "status_update"}],
        metadata={"source": "test"},
    )

    response = client.get(f"/api/conversation/history/{session_id}")
    api_server.session_manager.delete_session(session_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["total_messages"] == 1
    interaction = payload["messages"][0]
    assert interaction["user_request"] == "Ping the status board"
    assert interaction["agent_response"]["message"] == "Status board refreshed"
    assert interaction["plan"][0]["action"] == "status_update"
    assert interaction["metadata"]["source"] == "test"


def test_conversation_history_handles_malformed_id(client):
    response = client.get("/api/conversation/history/../../etc/passwd")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_messages"] == 0
    assert payload["messages"] == []


def test_websocket_chat_uses_provided_session_id(client):
    session_id = f"ws-session-{uuid.uuid4()}"
    with client.websocket_connect(f"/ws/chat?session_id={session_id}") as websocket:
        welcome = websocket.receive_json()
        assert welcome["type"] == "system"
        assert welcome["session_id"] == session_id
        assert welcome["session_status"] == "new"
        websocket.close()
    api_server.session_manager.delete_session(session_id)


def test_websocket_chat_marks_resumed_sessions(client):
    session_id = f"ws-resume-{uuid.uuid4()}"
    with client.websocket_connect(f"/ws/chat?session_id={session_id}") as first_ws:
        first_welcome = first_ws.receive_json()
        assert first_welcome["session_status"] == "new"
        first_ws.close()

    with client.websocket_connect(f"/ws/chat?session_id={session_id}") as websocket:
        welcome = websocket.receive_json()
        assert welcome["session_status"] == "resumed"
        websocket.close()

    api_server.session_manager.delete_session(session_id)

