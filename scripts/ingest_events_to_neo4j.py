#!/usr/bin/env python3
"""
Ingest normalized events into Neo4j (services/components/apis/events graph).
"""

from __future__ import annotations

import argparse
import os
from typing import Iterable, List, Set, Tuple

from neo4j import GraphDatabase

from activity_ingest.events_loader import ActivityEvent, load_all_events


def merge_simple(tx, label: str, ids: Iterable[str]) -> None:
    tx.run(
        f"""
        UNWIND $ids AS node_id
        MERGE (n:{label} {{id: node_id}})
        ON CREATE SET n.name = node_id
        """,
        ids=list(ids),
    )


def merge_api_endpoints(tx, apis: Iterable[str]) -> None:
    tx.run(
        """
        UNWIND $paths AS path
        MERGE (a:APIEndpoint {path: path})
        """,
        paths=list(apis),
    )


def ingest_events(tx, events: List[ActivityEvent]) -> None:
    for event in events:
        tx.run(
            """
            MERGE (e:Event {id: $id})
            SET e.source_type = $source_type,
                e.timestamp = datetime($timestamp),
                e.labels = $labels,
                e.text_raw = $text_raw
            """,
            id=event.id,
            source_type=event.source_type,
            timestamp=event.timestamp.isoformat(),
            labels=event.labels,
            text_raw=event.text_raw,
        )

        for service_id in event.service_ids:
            tx.run(
                """
                MATCH (e:Event {id: $event_id})
                MERGE (s:Service {id: $service_id})
                ON CREATE SET s.name = $service_id
                MERGE (e)-[:ABOUT_SERVICE]->(s)
                """,
                event_id=event.id,
                service_id=service_id,
            )

        for component_id in event.component_ids:
            tx.run(
                """
                MATCH (e:Event {id: $event_id})
                MERGE (c:Component {id: $component_id})
                ON CREATE SET c.name = $component_id
                MERGE (e)-[:ABOUT_COMPONENT]->(c)
                """,
                event_id=event.id,
                component_id=component_id,
            )

        for api in event.apis:
            tx.run(
                """
                MATCH (e:Event {id: $event_id})
                MERGE (a:APIEndpoint {path: $api})
                MERGE (e)-[:ABOUT_API]->(a)
                """,
                event_id=event.id,
                api=api,
            )


def link_component_service(tx, links: Iterable[Tuple[str, str]]) -> None:
    tx.run(
        """
        UNWIND $pairs AS pair
        MATCH (c:Component {id: pair.component_id})
        MATCH (s:Service {id: pair.service_id})
        MERGE (c)-[:BELONGS_TO]->(s)
        """,
        pairs=[{"component_id": comp, "service_id": serv} for comp, serv in links],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest events into Neo4j.")
    parser.add_argument("--slack", default="data/synthetic_slack/slack_events.json")
    parser.add_argument("--git", default="data/synthetic_git/git_events.json")
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USERNAME", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", "neo4j"))
    args = parser.parse_args()

    events = load_all_events(args.slack, args.git)
    if not events:
        raise SystemExit("No events to ingest.")

    services: Set[str] = set()
    components: Set[str] = set()
    apis: Set[str] = set()
    comp_service_links: Set[Tuple[str, str]] = set()

    for event in events:
        services.update(event.service_ids)
        components.update(event.component_ids)
        apis.update(event.apis)
        for component_id in event.component_ids:
            for service_id in event.service_ids:
                comp_service_links.add((component_id, service_id))

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))

    with driver.session() as session:
        if services:
            session.execute_write(merge_simple, "Service", list(services))
        if components:
            session.execute_write(merge_simple, "Component", list(components))
        if apis:
            session.execute_write(merge_api_endpoints, list(apis))
        if comp_service_links:
            session.execute_write(link_component_service, list(comp_service_links))
        session.execute_write(ingest_events, events)

    driver.close()
    print(f"Ingested {len(events)} events into Neo4j at {args.uri}")


if __name__ == "__main__":
    main()

