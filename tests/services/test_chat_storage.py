from __future__ import annotations

import asyncio

from src.services.chat_storage import MongoChatStorage


class FakeInsertResult:
    def __init__(self, count: int):
        self.inserted_ids = list(range(count))


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)
        self._limit = None

    def sort(self, field, direction):
        reverse = direction < 0
        self._docs.sort(key=lambda doc: doc.get(field), reverse=reverse)
        return self

    def limit(self, limit):
        self._limit = limit
        return self

    async def to_list(self, length):
        limit = self._limit or length
        return list(self._docs[: min(limit, length)])


class FakeCollection:
    def __init__(self):
        self.docs = []
        self.indexes = {}

    async def insert_many(self, docs):
        self.docs.extend(docs)
        return FakeInsertResult(len(docs))

    def find(self, query):
        filtered = [doc for doc in self.docs if doc.get("session_id") == query.get("session_id")]
        return FakeCursor(filtered)

    async def index_information(self):
        return dict(self.indexes)

    async def create_index(self, *args, **kwargs):
        name = kwargs.get("name")
        if name:
            self.indexes[name] = kwargs


class FakeDatabase:
    def __init__(self, collection):
        self._collection = collection

    def __getitem__(self, _name):
        return self._collection


class FakeAdmin:
    async def command(self, *_args, **_kwargs):
        return {"ok": 1}


class FakeClient:
    def __init__(self, collection):
        self._collection = collection
        self.admin = FakeAdmin()

    def __getitem__(self, _name):
        return FakeDatabase(self._collection)


def make_storage(collection: FakeCollection):
    config = {
        "mongo": {
            "enabled": True,
            "uri": "mongodb://127.0.0.1:27017",
            "database": "test-db",
            "chat_collection": "chat_messages",
        }
    }
    return MongoChatStorage(config=config, client=FakeClient(collection))


def test_insert_messages_normalizes_payloads():
    collection = FakeCollection()
    storage = make_storage(collection)

    inserted = asyncio.run(
        storage.insert_messages(
        [
            {
                "session_id": "unit",
                "role": "user",
                "text": "hello",
                "metadata": {"transport": "rest"},
            }
        ]
    )
    )

    assert inserted == 1
    assert len(collection.docs) == 1
    doc = collection.docs[0]
    assert doc["session_id"] == "unit"
    assert doc["text"] == "hello"
    assert "created_at" in doc
    assert "expires_at" in doc


def test_fetch_recent_returns_sorted_chronologically():
    collection = FakeCollection()
    storage = make_storage(collection)

    collection.docs = [
        {"session_id": "s", "role": "user", "text": "older", "created_at": "2025-01-01T00:00:01+00:00"},
        {"session_id": "s", "role": "assistant", "text": "newer", "created_at": "2025-01-01T00:00:02+00:00"},
        {"session_id": "other", "role": "user", "text": "skip", "created_at": "2025-01-01T00:00:03+00:00"},
    ]

    rows = asyncio.run(storage.fetch_recent("s", limit=5))
    assert [row["text"] for row in rows] == ["older", "newer"]


def test_ensure_indexes_creates_missing():
    collection = FakeCollection()
    storage = make_storage(collection)

    asyncio.run(storage.ensure_indexes())
    assert "session_ts_idx" in collection.indexes
    assert "expires_at_idx" in collection.indexes

