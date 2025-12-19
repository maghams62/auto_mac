"""
Graph analytics helpers for activity scoring and dissatisfaction ranking.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .service import GraphService

logger = logging.getLogger(__name__)


class GraphAnalyticsService:
    """
    Provides higher-level analytics queries on top of the activity graph.
    """

    def __init__(self, graph_service: GraphService):
        self.graph_service = graph_service

    def is_available(self) -> bool:
        return self.graph_service.is_available()

    def get_component_activity(
        self,
        component_id: str,
        window_hours: int = 168,
        limit: int = 15,
    ) -> Dict[str, Any]:
        """
        Return aggregated activity score plus recent signals for a component.
        """
        if not self.is_available():
            return {
                "component_id": component_id,
                "activity_score": 0.0,
                "signals": [],
                "docs": [],
                "doc_count": 0,
                "dissatisfaction_score": 0.0,
            }

        cutoff = self._cutoff_iso(window_hours)
        query = """
        MATCH (c:Component {id: $component_id})
        OPTIONAL MATCH (signal:ActivitySignal)-[rel:SIGNALS_COMPONENT]->(c)
        WHERE $cutoff IS NULL OR rel.last_seen IS NULL OR datetime(rel.last_seen) >= datetime($cutoff)
        WITH c, signal, rel
        ORDER BY rel.last_seen DESC
        WITH
            c,
            sum(coalesce(rel.signal_weight, 1.0)) AS total_weight,
            [s IN collect(
                CASE
                    WHEN signal IS NULL THEN NULL
                    ELSE {
                        id: signal.id,
                        source: signal.source,
                        weight: coalesce(rel.signal_weight, 1.0),
                        last_seen: rel.last_seen
                    }
                END
            ) WHERE s IS NOT NULL] AS signals
        OPTIONAL MATCH (doc:Doc)-[:DESCRIBES_COMPONENT]->(c)
        WITH
            c,
            total_weight,
            signals[0..$signal_limit] AS limited_signals,
            collect(DISTINCT doc.id) AS all_docs
        WITH
            c,
            total_weight,
            limited_signals,
            all_docs[0..$doc_limit] AS docs,
            size(all_docs) AS doc_count
        OPTIONAL MATCH (case:SupportCase)-[support:SUPPORTS_COMPONENT]->(c)
        WHERE $cutoff IS NULL OR support.last_seen IS NULL OR datetime(support.last_seen) >= datetime($cutoff)
        RETURN
            c.id AS component_id,
            total_weight AS activity_score,
            limited_signals AS signals,
            docs AS docs,
            doc_count AS doc_count,
            coalesce(sum(coalesce(support.signal_weight, 1.0)), 0.0) AS dissatisfaction_score
        """

        records = self.graph_service.run_query(
            query,
            {
                "component_id": component_id,
                "cutoff": cutoff,
                "signal_limit": max(1, limit),
                "doc_limit": max(1, limit),
            },
        )
        if not records:
            return {
                "component_id": component_id,
                "activity_score": 0.0,
                "signals": [],
                "docs": [],
                "doc_count": 0,
                "dissatisfaction_score": 0.0,
            }

        record = records[0]
        return {
            "component_id": record.get("component_id", component_id),
            "activity_score": round(float(record.get("activity_score") or 0.0), 4),
            "signals": record.get("signals", []),
            "docs": record.get("docs", []),
            "doc_count": int(record.get("doc_count", 0) or 0),
            "dissatisfaction_score": round(float(record.get("dissatisfaction_score") or 0.0), 4),
        }

    def get_dissatisfaction_leaderboard(
        self,
        window_hours: int = 168,
        limit: int = 5,
        components: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return top components ranked by customer dissatisfaction signals.
        """
        if not self.is_available():
            return []

        cutoff = self._cutoff_iso(window_hours)
        component_filter = components or []

        query = """
        MATCH (c:Component)
        WHERE size($components) = 0 OR c.id IN $components
        OPTIONAL MATCH (case:SupportCase)-[rel:SUPPORTS_COMPONENT]->(c)
        WHERE $cutoff IS NULL OR rel.last_seen IS NULL OR datetime(rel.last_seen) >= datetime($cutoff)
        WITH c,
             sum(coalesce(rel.signal_weight, 1.0)) AS support_weight
        OPTIONAL MATCH (issue:Issue)-[:AFFECTS_COMPONENT]->(c)
        WHERE $cutoff IS NULL OR issue.updated_at IS NULL OR datetime(issue.updated_at) >= datetime($cutoff)
        WITH c, support_weight, count(issue) AS issue_count
        WITH c,
             support_weight + issue_count * $issue_weight AS dissatisfaction_score,
             support_weight,
             issue_count
        WHERE dissatisfaction_score > 0
        RETURN
            c.id AS component_id,
            round(dissatisfaction_score, 4) AS total_score,
            round(support_weight, 4) AS support_score,
            issue_count AS issue_count
        ORDER BY total_score DESC, component_id ASC
        LIMIT $limit
        """

        records = self.graph_service.run_query(
            query,
            {
                "cutoff": cutoff,
                "limit": max(1, limit),
                "components": component_filter,
                "issue_weight": 0.5,
            },
        )
        return records or []

    @staticmethod
    def _cutoff_iso(window_hours: int) -> Optional[str]:
        if window_hours <= 0:
            return None
        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        return cutoff_dt.isoformat()

