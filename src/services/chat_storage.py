"""
Mongo-backed chat persistence with async helpers.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ImportError:  # pragma: no cover - motor installed via requirements
    AsyncIOMotorClient = None  # type: ignore

logger = logging.getLogger(__name__)


class MongoChatStorage:
    """
    Lightweight wrapper around MongoDB for persisting chat conversations.

    Designed to be called from async contexts; writes should be batched via
    LocalChatCache/ChatPersistenceWorker to keep UI interactions snappy.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        client: Optional[AsyncIOMotorClient] = None,
    ) -> None:
        mongo_cfg = (config or {}).get("mongo", {})
        self.enabled = bool(mongo_cfg.get("enabled", False))
        self._uri = mongo_cfg.get("uri", "mongodb://127.0.0.1:27017")
        self._database = mongo_cfg.get("database", "oqoqo")
        self._collection_name = mongo_cfg.get("chat_collection", "chat_messages")
        self._ttl_days = max(0, int(mongo_cfg.get("ttl_days", 30)))

        self._client: Optional[AsyncIOMotorClient] = None
        self._collection = None
        self._index_lock = asyncio.Lock()

        if not self.enabled:
            logger.info("[CHAT STORAGE] Mongo persistence disabled via config.")
            return

        if client:
            self._client = client
        elif AsyncIOMotorClient is None:
            logger.warning(
                "[CHAT STORAGE] motor is not installed. Falling back to disabled mode."
            )
            self.enabled = False
            return
        else:
            self._client = AsyncIOMotorClient(
                self._uri, serverSelectionTimeoutMS=5000, uuidRepresentation="standard"
            )

        self._collection = self._client[self._database][self._collection_name]
        logger.info(
            "[CHAT STORAGE] Initialized MongoChatStorage (db=%s collection=%s)",
            self._database,
            self._collection_name,
        )

    async def ensure_indexes(self) -> None:
        """Create TTL/indexes if Mongo is available."""
        if not self.enabled or not self._collection:
            return
        async with self._index_lock:
            indexes = await self._collection.index_information()
            if "session_ts_idx" not in indexes:
                await self._collection.create_index(
                    [("session_id", 1), ("created_at", -1)], name="session_ts_idx"
                )
            if self._ttl_days > 0 and "expires_at_idx" not in indexes:
                await self._collection.create_index(
                    "expires_at",
                    expireAfterSeconds=0,
                    name="expires_at_idx",
                )

    async def insert_messages(self, messages: List[Dict[str, Any]]) -> int:
        """Bulk insert chat messages."""
        if not self.enabled or not self._collection or not messages:
            return 0

        docs = [self._normalize_document(msg) for msg in messages]
        try:
            result = await self._collection.insert_many(docs)
            inserted = len(result.inserted_ids)
            logger.debug("[CHAT STORAGE] Inserted %s chat messages", inserted)
            return inserted
        except Exception as exc:
            logger.error("[CHAT STORAGE] Failed to insert messages: %s", exc, exc_info=True)
            return 0

    async def insert_message(self, message: Dict[str, Any]) -> bool:
        """Insert a single chat message."""
        return await self.insert_messages([message]) == 1

    async def fetch_recent(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch most recent messages for a session from Mongo."""
        if not self.enabled or not self._collection:
            return []
        cursor = (
            self._collection.find({"session_id": session_id})
            .sort("created_at", -1)
            .limit(max(1, limit))
        )
        results = await cursor.to_list(length=limit)
        return list(reversed(results))

    async def health(self) -> Dict[str, Any]:
        """Return connectivity details suitable for health endpoints."""
        if not self.enabled or not self._collection:
            return {"enabled": False, "status": "disabled"}
        try:
            await self._client.admin.command("ping")  # type: ignore[union-attr]
            return {
                "enabled": True,
                "status": "ok",
                "database": self._database,
                "collection": self._collection_name,
            }
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("[CHAT STORAGE] Health check failed: %s", exc)
            return {
                "enabled": True,
                "status": "error",
                "error": str(exc),
            }

    def _normalize_document(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure mandatory fields exist for Mongo persistence."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=self._ttl_days or 365)
        return {
            "session_id": payload.get("session_id"),
            "role": payload.get("role"),
            "text": payload.get("text"),
            "metadata": payload.get("metadata") or {},
            "vector_ids": payload.get("vector_ids") or [],
            "created_at": payload.get("created_at") or now.isoformat(),
            "expires_at": payload.get("expires_at") or expires_at,
        }

    @property
    def collection(self):
        """Expose the underlying Motor collection (primarily for tooling / backfills)."""
        return self._collection

