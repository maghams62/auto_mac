#!/usr/bin/env python3
"""
Embed activity events and upsert them into a vector database (Qdrant).
"""

from __future__ import annotations

import argparse
import hashlib
import os
from typing import Iterable, List, Sequence

from activity_ingest.events_loader import ActivityEvent, load_all_events


def embed_text_batch(texts: Sequence[str], dimensions: int = 64) -> List[List[float]]:
    """
    Deterministic embedding stub based on SHA256.
    Replace with a real embedding provider (OpenAI/Qdrant FastEmbed/etc).
    """

    vectors: List[List[float]] = []
    for text in texts:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # Expand digest to requested dimensions by repeating bytes
        raw = list(digest) * (dimensions // len(digest) + 1)
        vector = [float(raw[i]) / 255.0 for i in range(dimensions)]
        vectors.append(vector[:dimensions])
    return vectors


def ensure_collection(client, collection: str, vector_size: int) -> None:
    from qdrant_client.http.models import Distance, VectorParams

    if collection in [col.name for col in client.get_collections().collections]:
        return

    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def upsert_events(
    client,
    collection: str,
    events: Sequence[ActivityEvent],
    vector_size: int,
) -> None:
    batch_size = 32
    for i in range(0, len(events), batch_size):
        batch = events[i : i + batch_size]
        embeddings = embed_text_batch([event.text_raw for event in batch], vector_size)
        payloads = []
        ids = []
        for event in batch:
            payloads.append(
                {
                    "source_type": event.source_type,
                    "timestamp": event.timestamp.isoformat(),
                    "service_ids": event.service_ids,
                    "component_ids": event.component_ids,
                    "apis": event.apis,
                    "labels": event.labels,
                    "repo": event.repo,
                    "branch": event.branch,
                    "channel": event.channel,
                    "channel_id": event.channel_id,
                }
            )
            ids.append(event.id)

        client.upsert(
            collection_name=collection,
            points=[
                {"id": pid, "vector": vec, "payload": payload}
                for pid, vec, payload in zip(ids, embeddings, payloads, strict=True)
            ],
        )


def run_smoke_query(client, collection: str, vector_size: int) -> None:
    query = "vat_code 400 error billing checkout"
    vector = embed_text_batch([query], vector_size)[0]
    results = client.search(
        collection_name=collection,
        query_vector=vector,
        limit=5,
        query_filter={
            "must": [
                {
                    "key": "component_ids",
                    "match": {"keyword": "billing.checkout"},
                }
            ]
        },
    )

    print("\nSample search results for 'vat_code 400 error':")
    for res in results:
        print(f"- {res.payload.get('source_type')} {res.id} (score={res.score:.3f})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest events into a vector store.")
    parser.add_argument("--slack", default="data/synthetic_slack/slack_events.json")
    parser.add_argument("--git", default="data/synthetic_git/git_events.json")
    parser.add_argument("--collection", default="activity_events")
    parser.add_argument("--vector-size", type=int, default=64)
    parser.add_argument("--qdrant-url", default=os.getenv("QDRANT_URL", "http://localhost:6333"))
    parser.add_argument("--qdrant-key", default=os.getenv("QDRANT_API_KEY"))
    parser.add_argument("--skip-search", action="store_true")
    args = parser.parse_args()

    events = load_all_events(args.slack, args.git)
    if not events:
        raise SystemExit("No events to ingest.")

    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise SystemExit("qdrant-client is required. Install with `pip install qdrant-client`.") from exc

    client = QdrantClient(url=args.qdrant_url, api_key=args.qdrant_key)
    ensure_collection(client, args.collection, args.vector_size)
    upsert_events(client, args.collection, events, args.vector_size)

    print(f"Ingested {len(events)} events into collection '{args.collection}'.")

    if not args.skip_search:
        run_smoke_query(client, args.collection, args.vector_size)


if __name__ == "__main__":
    main()

