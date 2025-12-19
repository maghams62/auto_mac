#!/usr/bin/env python3
"""
Cross-system context query for an API path (Option 2 demo).
"""

from __future__ import annotations

import argparse
import os
from collections import Counter, defaultdict

from neo4j import GraphDatabase

from scripts.ingest_events_to_vector import embed_text_batch


def fetch_api_events(driver, api_path: str):
    cypher = """
    MATCH (a:APIEndpoint {path: $api_path})<-[:ABOUT_API]-(e:Event)
    OPTIONAL MATCH (e)-[:ABOUT_SERVICE]->(s:Service)
    OPTIONAL MATCH (e)-[:ABOUT_COMPONENT]->(c:Component)
    RETURN e.id AS id,
           e.source_type AS source_type,
           e.timestamp AS timestamp,
           e.labels AS labels,
           collect(DISTINCT s.id) AS services,
           collect(DISTINCT c.id) AS components
    ORDER BY e.timestamp DESC
    """
    with driver.session() as session:
        result = session.run(cypher, api_path=api_path)
        return list(result)


def summarize(records):
    per_service = defaultdict(Counter)
    for rec in records:
        services = rec["services"] or ["(unknown)"]
        for service in services:
            per_service[service].update(rec["labels"] or [])
    return per_service


def vector_search(api_path: str, collection: str, url: str, api_key: str | None):
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        print("qdrant-client not installed; skipping vector search.")
        return

    client = QdrantClient(url=url, api_key=api_key)
    query = f"feedback about {api_path}"
    vector = embed_text_batch([query])[0]
    results = client.search(
        collection_name=collection,
        query_vector=vector,
        limit=5,
        query_filter={
            "must": [
                {
                    "key": "apis",
                    "match": {"keyword": api_path},
                }
            ]
        },
    )
    print("\nVector search samples:")
    for res in results:
        labels = ", ".join(res.payload.get("labels", []))
        components = ", ".join(res.payload.get("component_ids", []))
        print(f"- {res.payload.get('source_type')} {res.id} [{labels}] comps={components}")


def main() -> None:
    parser = argparse.ArgumentParser(description="API impact query.")
    parser.add_argument("api_path", help="API path, e.g., /v1/payments/create")
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USERNAME", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", "neo4j"))
    parser.add_argument("--qdrant-collection", help="Optional Qdrant collection for semantic samples.")
    parser.add_argument("--qdrant-url", default=os.getenv("QDRANT_URL", "http://localhost:6333"))
    parser.add_argument("--qdrant-key", default=os.getenv("QDRANT_API_KEY"))
    args = parser.parse_args()

    driver = GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password))
    records = fetch_api_events(driver, args.api_path)
    driver.close()

    if not records:
        print(f"No events reference {args.api_path}.")
        return

    print(f"API: {args.api_path}")
    print(f"Events referencing API: {len(records)}")

    service_label_summary = summarize(records)
    for service, counter in service_label_summary.items():
        print(f"- Service {service}: {dict(counter)}")

    print("\nRecent events:")
    for rec in records[:5]:
        ts = rec["timestamp"].isoformat()
        services = ", ".join(rec["services"] or [])
        components = ", ".join(rec["components"] or [])
        labels = ", ".join(rec["labels"] or [])
        print(f"{ts} {rec['source_type']} {rec['id']} | services={services} components={components} labels={labels}")

    if args.qdrant_collection:
        vector_search(args.api_path, args.qdrant_collection, args.qdrant_url, args.qdrant_key)


if __name__ == "__main__":
    main()

