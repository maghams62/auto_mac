from __future__ import annotations

import json
from pathlib import Path

from src.memory.local_chat_cache import LocalChatCache


def _make_message(text: str, session: str = "s", role: str = "user", idx: int = 0):
    return {
        "session_id": session,
        "role": role,
        "text": text,
        "created_at": f"2025-11-28T00:00:{idx:02d}+00:00",
    }


def test_append_trims_per_session_limit(tmp_path):
    cache = LocalChatCache(max_messages_per_session=2, disk_path=str(tmp_path))
    cache.append_message(_make_message("one", idx=1))
    cache.append_message(_make_message("two", idx=2))
    cache.append_message(_make_message("three", idx=3))

    recent = cache.list_recent("s", limit=5)
    assert len(recent) == 2
    assert [msg["text"] for msg in recent] == ["two", "three"]


def test_pop_flush_batch_returns_fifo(tmp_path):
    cache = LocalChatCache(max_messages_per_session=5, disk_path=str(tmp_path))
    cache.append_message(_make_message("one", idx=1))
    cache.append_message(_make_message("two", idx=2))
    cache.append_message(_make_message("three", idx=3))

    batch = cache.pop_flush_batch(batch_size=2)
    assert [msg["text"] for msg in batch] == ["one", "two"]

    batch = cache.pop_flush_batch(batch_size=2)
    assert [msg["text"] for msg in batch] == ["three"]


def test_disk_persistence_creates_jsonl(tmp_path):
    cache = LocalChatCache(max_messages_per_session=2, disk_path=str(tmp_path))
    cache.append_message(_make_message("persist", session="disk", idx=1))

    log_path = Path(tmp_path) / "disk.jsonl"
    assert log_path.exists()
    contents = log_path.read_text().strip().splitlines()
    assert len(contents) == 1
    payload = json.loads(contents[0])
    assert payload["text"] == "persist"
    assert payload["session_id"] == "disk"

