#!/usr/bin/env python3
"""
Replay Mongo-stored chat transcripts into Qdrant for retroactive indexing.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorCollection

from src.config_manager import get_config
from src.services.chat_storage import MongoChatStorage
from src.vector import ContextChunk, get_vector_search_service


async def _stream_messages(
    collection: AsyncIOMotorCollection,
    batch_size: int,
    resume_after: Optional[str],
    session_id: Optional[str],
) -> AsyncIterator[List[Dict[str, Any]]]:
    query: Dict[str, Any] = {}
    if resume_after:
        query["created_at"] = {"$gt": resume_after}
    if session_id:
        query["session_id"] = session_id

    cursor = collection.find(query).sort("created_at", 1)
    batch: List[Dict[str, Any]] = []
    async for doc in cursor:
        batch.append(doc)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        cleaned = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(cleaned)
        except ValueError:
            return None
    return None


def _build_chunk(doc: Dict[str, Any], collection_name: Optional[str]) -> Optional[ContextChunk]:
    text = (doc.get("text") or "").strip()
    if not text:
        return None

    session_id = doc.get("session_id") or "unknown_session"
    role = doc.get("role") or "unknown"
    created_at = _parse_timestamp(doc.get("created_at"))
    entity_id = f"chat:{session_id}:{doc.get('_id')}"
    chunk_text = "\n".join(
        [
            f"{role.capitalize()} message from session {session_id}",
            f"Timestamp: {created_at.isoformat() if created_at else 'unknown'}",
            "",
            text,
        ]
    )

    metadata = {
        "session_id": session_id,
        "role": role,
        "vector_ids": doc.get("vector_ids") or [],
    }

    return ContextChunk(
        chunk_id=ContextChunk.generate_chunk_id(),
        entity_id=entity_id,
        source_type="chat",
        text=chunk_text,
        component=None,
        service=None,
        timestamp=created_at,
        tags=["chat", role],
        metadata=metadata,
        collection=collection_name,
    )


async def backfill_chats(args) -> int:
    config = get_config()
    storage = MongoChatStorage(config)
    if not storage.enabled or not storage.collection:
        print("[ERROR] Mongo chat storage is disabled or not reachable.")
        return 2

    vector_service = get_vector_search_service(config)
    if not vector_service:
        print("[ERROR] Vector service is not configured.")
        return 3

    collection = storage.collection
    total_docs = 0
    total_chunks = 0
    indexed_chunks = 0
    resume_after = _load_resume_token(args.resume_after, args.resume_file)
    start_time = time.perf_counter()
    last_checkpoint = resume_after

    async for batch in _stream_messages(collection, args.batch_size, resume_after, args.session_id):
        total_docs += len(batch)
        chunks: List[ContextChunk] = []
        for doc in batch:
            chunk = _build_chunk(doc, getattr(vector_service, "collection", None))
            if chunk:
                chunks.append(chunk)
        total_chunks += len(chunks)

        if not chunks:
            continue

        last_created = str(batch[-1].get("created_at"))
        elapsed = max(time.perf_counter() - start_time, 1e-6)
        docs_per_sec = total_docs / elapsed

        if args.dry_run:
            print(
                f"[DRY RUN] Prepared {len(chunks)} chunks "
                f"(docs_in_batch={len(batch)} last_created={last_created} "
                f"throughput={docs_per_sec:.2f} docs/s)"
            )
            _persist_resume_token(args.resume_file, last_created)
            continue

        success = vector_service.index_chunks(chunks)
        if success:
            indexed_chunks += len(chunks)
            print(
                "[OK] Indexed %s chat chunks (running_total=%s, last_created=%s, throughput=%.2f docs/s)"
                % (len(chunks), indexed_chunks, last_created, docs_per_sec)
            )
            _persist_resume_token(args.resume_file, last_created)
            last_checkpoint = last_created
        else:
            print("[WARN] Vector indexing failed for current batch; stopping.")
            _persist_resume_token(args.resume_file, last_created)
            return 4

    print(
        f"[DONE] Scanned {total_docs} mongo docs, prepared {total_chunks} chunks, indexed {indexed_chunks}."
    )
    if args.resume_file and last_checkpoint:
        print(f"[INFO] Resume cursor saved to {args.resume_file} ({last_checkpoint})")
    return 0 if (args.dry_run or indexed_chunks > 0 or total_chunks == 0) else 5


def parse_args():
    parser = argparse.ArgumentParser(description="Backfill chat transcripts into Qdrant.")
    parser.add_argument("--batch-size", type=int, default=100, help="Number of messages to process per batch.")
    parser.add_argument("--resume-after", type=str, help="ISO timestamp to resume after (created_at field).")
    parser.add_argument("--session-id", type=str, help="Limit backfill to a single session identifier.")
    parser.add_argument("--dry-run", action="store_true", help="Prepare chunks without writing to Qdrant.")
    parser.add_argument(
        "--resume-file",
        type=str,
        help="Optional file used to persist the last processed created_at timestamp between runs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(backfill_chats(args))


if __name__ == "__main__":
    raise SystemExit(main())


def _load_resume_token(resume_after: Optional[str], resume_file: Optional[str]) -> Optional[str]:
    if resume_after:
        return resume_after
    if resume_file:
        path = Path(resume_file)
        if path.exists():
            token = path.read_text().strip()
            if token:
                print(f"[INFO] Loaded resume cursor {token} from {resume_file}")
                return token
    return None


def _persist_resume_token(resume_file: Optional[str], token: Optional[str]) -> None:
    if not resume_file or not token:
        return
    path = Path(resume_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(token))

