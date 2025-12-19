"""
Background workers for chat persistence.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress
from typing import Optional

from src.memory.local_chat_cache import LocalChatCache
from src.services.chat_storage import MongoChatStorage

logger = logging.getLogger(__name__)


class ChatPersistenceWorker:
    """Flushes cached chat messages to MongoDB in the background."""

    def __init__(
        self,
        cache: LocalChatCache,
        storage: MongoChatStorage,
        flush_interval: float = 1.0,
        batch_size: int = 100,
    ) -> None:
        self._cache = cache
        self._storage = storage
        self._interval = flush_interval
        self._batch_size = batch_size
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._flush_event = asyncio.Event()

    async def start(self) -> None:
        if not self._storage.enabled:
            logger.info("[CHAT WORKER] Storage disabled; worker not started.")
            return
        if self._task:
            return
        await self._storage.ensure_indexes()
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="chat_persistence_worker")
        logger.info("[CHAT WORKER] Chat persistence worker started.")

    async def stop(self) -> None:
        if not self._task:
            return
        self._stop_event.set()
        self._flush_event.set()
        await self._task
        self._task = None
        logger.info("[CHAT WORKER] Chat persistence worker stopped.")

    def notify_new_message(self) -> None:
        """Signal the worker that new data is ready to flush."""
        if self._storage.enabled:
            self._flush_event.set()

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            await self._wait_for_signal()
            self._flush_event.clear()
            if self._stop_event.is_set():
                break
            await self._flush_once()
            await asyncio.sleep(self._interval)
        # Final drain on shutdown
        await self._flush_once()

    async def _wait_for_signal(self) -> None:
        """
        Wait for either flush or stop events without leaking orphaned awaitables.
        """
        if self._flush_event.is_set() or self._stop_event.is_set():
            return

        waiters = {
            asyncio.create_task(self._flush_event.wait()),
            asyncio.create_task(self._stop_event.wait()),
        }
        done, pending = await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)

        for task in pending:
            task.cancel()

        # Ensure cancelled tasks finish cleanly to avoid warnings.
        await asyncio.gather(*pending, return_exceptions=True)

        for task in done:
            with suppress(asyncio.CancelledError):
                task.result()

    async def _flush_once(self) -> None:
        if not self._storage.enabled:
            return
        drained = self._cache.pop_flush_batch(self._batch_size)
        if not drained:
            return
        start = time.perf_counter()
        inserted = await self._storage.insert_messages(drained)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "[CHAT WORKER] Flushed %s/%s chat messages to Mongo (%.1f ms).",
            inserted,
            len(drained),
            elapsed_ms,
        )

