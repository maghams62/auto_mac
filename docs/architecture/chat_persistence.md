# Chat Persistence Architecture

This document explains how Agent 1 added durable chat storage without slowing
down the Raycast-style UI. The solution combines a local in-memory cache for
instant UX with a MongoDB backend that keeps conversations recoverable across
sessions.

## Components

| Component | Path | Purpose |
|-----------|------|---------|
| `LocalChatCache` | `src/memory/local_chat_cache.py` | Keeps the most recent messages per session in RAM (and optional JSONL files) and exposes a flush queue. |
| `MongoChatStorage` | `src/services/chat_storage.py` | Async wrapper around MongoDB (via `motor`) that enforces TTL indexes and bulk-inserts chat messages. |
| `ChatPersistenceWorker` | `src/automation/background_jobs.py` | Async background worker that drains the cache’s flush queue and writes to Mongo with backoff. |
| API wiring | `api_server.py` | Records every user/assistant event (REST + WebSocket) and exposes `/api/storage/status`. |

## Data flow

1. Incoming user text is immediately cached through `record_chat_event`.
2. The cache adds the message to its per-session buffer and writes to a disk
   fallback (`data/cache/chat_sessions/*.jsonl`).
3. The cache also enqueues the message for persistence. The worker is signaled
   via `notify_new_message`.
4. The worker batches messages and calls `MongoChatStorage.insert_messages`.
5. Mongo stores ISO timestamps plus a TTL field (`expires_at`) so older chats
   roll off automatically without manual cleanup.

This keeps the UI responsive because user-facing code never waits on Mongo I/O.

## Configuration

`config.yaml` gained a new `mongo` block:

```yaml
mongo:
  enabled: false
  uri: "${MONGO_URI:-mongodb://127.0.0.1:27017}"
  database: "${MONGO_DB:-oqoqo}"
  chat_collection: "${MONGO_CHAT_COLLECTION:-chat_messages}"
  ttl_days: 30
  cache:
    max_messages_per_session: 75
    disk_path: "data/cache/chat_sessions"
```

Environment variables (`MONGO_URI`, `MONGO_DB`, `MONGO_CHAT_COLLECTION`) are
referenced but can remain unset until you are ready to supply credentials.

## Operations

- **Startup:** `startup_event` starts the persistence worker, which in turn
  creates Mongo indexes the first time it runs.
- **Shutdown:** the worker flushes any remaining messages before the app exits.
- **Health:** call `GET /api/storage/status` to see Mongo connectivity and cache
  parameters.

## Verification Checklist

Run this quick sequence whenever you need to verify the stack end-to-end:

1. **REST sanity check**
   ```bash
   curl -X POST http://localhost:8000/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message":"ping from rest","session_id":"verifier"}'
   ```
   Watch the API logs for `[CHAT CACHE]` entries and confirm Mongo receives a new
   document under `session_id=verifier`.
2. **WebSocket sanity check**
   - Connect via the launcher (or `wscat`) and send a short message.
   - Ensure the WebSocket welcome/status payloads appear in the UI and that the
     Mongo collection shows both `role="user"` and `role="assistant"` rows.
3. **Worker flush**
   - Tail the logs for `[CHAT WORKER] Flushed ...` to confirm background writes.
   - Inspect `data/cache/chat_sessions/<session>.jsonl` to make sure the disk
     fallback is receiving entries.
4. **Health endpoint**
   ```bash
   curl http://localhost:8000/api/storage/status | jq
   ```
   Verify `mongo.status == "ok"` and that the cache configuration matches
   expectations.

Documenting the results of this checklist inside a pull request makes it easy
for code reviewers to trust the persistence layer.

## History endpoint

`GET /api/chat/history?session_id=default&limit=50` returns the most recent
messages (cache first, Mongo fallback). Sample response:

```json
{
  "session_id": "default",
  "messages": [
    {
      "session_id": "default",
      "role": "user",
      "text": "ping",
      "created_at": "2025-11-28T01:23:45.123456+00:00",
      "metadata": {"transport": "websocket"},
      "source": "cache"
    },
    {
      "session_id": "default",
      "role": "assistant",
      "text": "pong!",
      "created_at": "2025-11-28T01:23:45.678901+00:00",
      "metadata": {"transport": "websocket", "status": "completed"},
      "source": "mongo"
    }
  ],
  "counts": {"cache": 1, "mongo": 1},
  "last_persisted_at": "2025-11-28T01:23:45.678901+00:00"
}
```

Use this endpoint from the launcher/web UI to hydrate conversations on load.

## Future work

- Plug Mongo-stored chats into the vector pipeline (Agent 2 owns backfill).
- Add metrics around flush latency and skipped writes.

