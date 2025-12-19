#!/usr/bin/env python3
"""
Summarize recent activity around a component (Option 1 demo).
"""

from __future__ import annotations

import argparse
import os
from collections import Counter

from neo4j import GraphDatabase

from scripts.ingest_events_to_vector import embed_text_batch  # reuse stub


def fetch_component_events(driver, component_id: str, lookback_days: int):
    cypher = """
    MATCH (c:Component {id: $component_id})<-[:ABOUT_COMPONENT]-(e:Event)
    WHERE e.timestamp >= datetime() - duration({days: $days})
    OPTIONAL MATCH (e)-[:ABOUT_SERVICE]->(s:Service)
    RETURN e.id AS id,
           e.source_type AS source_type,
           e.timestamp AS timestamp,
           e.labels AS labels,
           collect(DISTINCT s.id) AS services
    ORDER BY e.timestamp DESC
    """
    with driver.session() as session:
        result = session.run(cypher, component_id=component_id, days=lookback_days)
        return list(result)


def vector_search(component_id: str, collection: str, url: str, api_key: str | None):
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        print("qdrant-client not installed; skipping vector search.")
        return

    client = QdrantClient(url=url, api_key=api_key)
    query = f"recent issues around {component_id}"
    vector = embed_text_batch([query])[0]
    results = client.search(
        collection_name=collection,
        query_vector=vector,
        limit=5,
        query_filter={
            "must": [
                {
                    "key": "component_ids",
                    "match": {"keyword": component_id},
                }
            ]
        },
    )
    print("\nVector search samples:")
    for res in results:
        label_list = ", ".join(res.payload.get("labels", []))
        print(f"- {res.payload.get('source_type')} {res.id} (labels={label_list})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Component activity summary.")
    parser.add_argument("component_id", help="Component identifier (e.g., billing.checkout)")
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USERNAME", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", "neo4j"))
    parser.add_argument("--qdrant-collection", help="Optional Qdrant collection to sample events from.")
    parser.add_argument("--qdrant-url", default=os.getenv("QDRANT_URL", "http://localhost:6333"))
    parser.add_argument("--qdrant-key", default=os.getenv("QDRANT_API_KEY"))
    args = parser.parse_args()

    driver = GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password))
    records = fetch_component_events(driver, args.component_id, args.lookback_days)
    driver.close()

    if not records:
        print(f"No events found for component {args.component_id} in the last {args.lookback_days} days.")
        return

    source_counts = Counter(rec["source_type"] for rec in records)
    label_counts = Counter(label for rec in records for label in rec["labels"] or [])
    services = Counter(
        service for rec in records for service in (rec["services"] or [])
    )

    print(f"Component: {args.component_id}")
    print(f"Events (last {args.lookback_days} days): {len(records)}")
    print("By source:", dict(source_counts))
    print("Top labels:", label_counts.most_common(5))
    print("Services involved:", dict(services))
    print("\nRecent events:")
    for rec in records[:5]:
        ts = rec["timestamp"].isoformat()
        labels = ", ".join(rec["labels"] or [])
        print(f"- {ts} {rec['source_type']} {rec['id']} [{labels}]")

    if args.qdrant_collection:
        vector_search(args.component_id, args.qdrant_collection, args.qdrant_url, args.qdrant_key)


if __name__ == "__main__":
    main()

