"""
Lightweight validation/telemetry helpers for the activity graph.
"""

from __future__ import annotations

from typing import Any, Dict

from .service import GraphService


class GraphValidator:
    """
    Runs a series of consistency checks against Neo4j.
    """

    def __init__(self, graph_service: GraphService):
        self.graph_service = graph_service

    def is_available(self) -> bool:
        return self.graph_service.is_available()

    def run_checks(self) -> Dict[str, Any]:
        if not self.is_available():
            return {"available": False}

        checks = {
            "available": True,
            "missing_signal_weights": self._count(
                """
                MATCH (:ActivitySignal)-[rel:SIGNALS_COMPONENT]->(:Component)
                WHERE rel.signal_weight IS NULL
                RETURN count(rel) AS count
                """
            ),
            "orphan_code_artifacts": self._count(
                """
                MATCH (a:CodeArtifact)
                WHERE NOT EXISTS {
                    MATCH (:Component)-[:OWNS_CODE]->(a)
                }
                RETURN count(a) AS count
                """
            ),
            "components_without_docs": self._count(
                """
                MATCH (c:Component)
                WHERE NOT EXISTS {
                    MATCH (:Doc)-[:DESCRIBES_COMPONENT]->(c)
                }
                RETURN count(c) AS count
                """
            ),
        }
        return checks

    def _count(self, query: str) -> int:
        rows = self.graph_service.run_query(query)
        if not rows:
            return 0
        return int(rows[0].get("count", 0))

