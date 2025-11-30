from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .service import GraphService


def _cutoff_iso(window_days: int) -> Optional[str]:
    if window_days <= 0:
        return None
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=window_days)
    return cutoff_dt.isoformat()


def _format_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class ActivityService:
    """High-level helper that surfaces component-level activity metrics."""

    def __init__(
        self,
        config,
        *,
        graph_service: Optional[GraphService] = None,
    ):
        self.graph_service = graph_service or GraphService(config)

    def is_available(self) -> bool:
        return self.graph_service.is_available()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_activity_for_component(self, component_id: str, *, window_days: int = 14) -> Dict[str, Any]:
        if not self.is_available():
            return {
                "component_id": component_id,
                "window_days": window_days,
                "git_events": 0,
                "slack_events": 0,
                "doc_drift_events": 0,
                "activity_score": 0.0,
                "last_event_at": None,
            }

        cutoff = _cutoff_iso(window_days)
        query = """
        WITH CASE WHEN $cutoff IS NULL THEN NULL ELSE datetime($cutoff) END AS cutoff
        MATCH (c:Component {id: $component_id})
        WITH c, cutoff
        CALL {
            WITH c, cutoff
            OPTIONAL MATCH (ge:GitEvent)-[:TOUCHES_COMPONENT]->(c)
            WHERE cutoff IS NULL OR ge.timestamp IS NULL OR datetime(ge.timestamp) >= cutoff
            RETURN
                count(DISTINCT ge) AS git_events,
                max(CASE WHEN ge.timestamp IS NULL THEN NULL ELSE datetime(ge.timestamp) END) AS git_last
        }
        CALL {
            WITH c, cutoff
            OPTIONAL MATCH (se:SlackEvent)-[:ABOUT_COMPONENT]->(c)
            WHERE cutoff IS NULL OR se.timestamp IS NULL OR datetime(se.timestamp) >= cutoff
            RETURN
                count(DISTINCT se) AS slack_component_events,
                sum(CASE WHEN 'doc_drift' IN coalesce(se.labels, []) THEN 1 ELSE 0 END) AS slack_component_doc_drift,
                max(CASE WHEN se.timestamp IS NULL THEN NULL ELSE datetime(se.timestamp) END) AS slack_component_last
        }
        CALL {
            WITH c, cutoff
            OPTIONAL MATCH (c)-[:EXPOSES_ENDPOINT]->(:APIEndpoint)<-[:COMPLAINS_ABOUT_API]-(se_api:SlackEvent)
            WHERE cutoff IS NULL OR se_api.timestamp IS NULL OR datetime(se_api.timestamp) >= cutoff
            RETURN
                count(DISTINCT se_api) AS slack_api_events,
                sum(CASE WHEN 'doc_drift' IN coalesce(se_api.labels, []) THEN 1 ELSE 0 END) AS slack_api_doc_drift,
                max(CASE WHEN se_api.timestamp IS NULL THEN NULL ELSE datetime(se_api.timestamp) END) AS slack_api_last
        }
        RETURN
            $component_id AS component_id,
            git_events,
            git_last,
            (slack_component_events + slack_api_events) AS slack_events,
            (slack_component_doc_drift + slack_api_doc_drift) AS doc_drift_events,
            CASE
                WHEN slack_component_last IS NULL THEN slack_api_last
                WHEN slack_api_last IS NULL THEN slack_component_last
                WHEN slack_component_last >= slack_api_last THEN slack_component_last
                ELSE slack_api_last
            END AS slack_last
        """

        records = self.graph_service.run_query(
            query,
            {"component_id": component_id, "cutoff": cutoff},
        )
        if not records:
            return {
                "component_id": component_id,
                "window_days": window_days,
                "git_events": 0,
                "slack_events": 0,
                "doc_drift_events": 0,
                "activity_score": 0.0,
                "last_event_at": None,
            }

        row = records[0]
        git_events = row.get("git_events", 0) or 0
        slack_events = row.get("slack_events", 0) or 0
        doc_drift_events = row.get("doc_drift_events", 0) or 0
        git_last = row.get("git_last")
        slack_last = row.get("slack_last")
        last_event_at = self._latest_timestamp(git_last, slack_last)

        return {
            "component_id": component_id,
            "window_days": window_days,
            "git_events": git_events,
            "slack_events": slack_events,
            "doc_drift_events": doc_drift_events,
            "activity_score": self._compute_score(git_events, slack_events, doc_drift_events),
            "last_event_at": last_event_at,
        }

    def get_top_components_by_doc_drift(
        self,
        *,
        limit: int = 5,
        window_days: int = 14,
    ) -> List[Dict[str, Any]]:
        if not self.is_available():
            return []

        limit = max(1, min(limit, 50))
        cutoff = _cutoff_iso(window_days)
        query = """
        WITH CASE WHEN $cutoff IS NULL THEN NULL ELSE datetime($cutoff) END AS cutoff
        MATCH (c:Component)
        CALL {
            WITH c, cutoff
            OPTIONAL MATCH (se:SlackEvent)-[:ABOUT_COMPONENT]->(c)
            WHERE cutoff IS NULL OR se.timestamp IS NULL OR datetime(se.timestamp) >= cutoff
            RETURN
                count(DISTINCT se) AS slack_component_events,
                sum(CASE WHEN 'doc_drift' IN coalesce(se.labels, []) THEN 1 ELSE 0 END) AS slack_component_doc_drift
        }
        CALL {
            WITH c, cutoff
            OPTIONAL MATCH (c)-[:EXPOSES_ENDPOINT]->(:APIEndpoint)<-[:COMPLAINS_ABOUT_API]-(se_api:SlackEvent)
            WHERE cutoff IS NULL OR se_api.timestamp IS NULL OR datetime(se_api.timestamp) >= cutoff
            RETURN
                count(DISTINCT se_api) AS slack_api_events,
                sum(CASE WHEN 'doc_drift' IN coalesce(se_api.labels, []) THEN 1 ELSE 0 END) AS slack_api_doc_drift
        }
        CALL {
            WITH c, cutoff
            OPTIONAL MATCH (ge:GitEvent)-[:TOUCHES_COMPONENT]->(c)
            WHERE cutoff IS NULL OR ge.timestamp IS NULL OR datetime(ge.timestamp) >= cutoff
            RETURN count(DISTINCT ge) AS git_events
        }
        CALL {
            WITH c
            OPTIONAL MATCH (doc:Doc)-[:DESCRIBES_COMPONENT]->(c)
            RETURN count(DISTINCT doc) AS doc_count
        }
        WITH
            c,
            slack_component_events + slack_api_events AS slack_events,
            slack_component_doc_drift + slack_api_doc_drift AS doc_drift_events,
            git_events,
            doc_count
        WHERE slack_events > 0 OR git_events > 0
        RETURN
            c.id AS component_id,
            slack_events,
            doc_drift_events,
            git_events,
            doc_count
        ORDER BY (doc_drift_events * 2.0 + slack_events * 0.5 + git_events * 0.3) DESC,
                 component_id ASC
        LIMIT $limit
        """

        records = self.graph_service.run_query(query, {"cutoff": cutoff, "limit": limit})
        results: List[Dict[str, Any]] = []
        for row in records or []:
            git_events = row.get("git_events", 0) or 0
            slack_events = row.get("slack_events", 0) or 0
            doc_drift_events = row.get("doc_drift_events", 0) or 0
            doc_count = row.get("doc_count", 0) or 0
            results.append(
                {
                    "component_id": row.get("component_id"),
                    "git_events": git_events,
                    "slack_events": slack_events,
                    "doc_drift_events": doc_drift_events,
                    "doc_count": doc_count,
                    "activity_score": self._compute_score(git_events, slack_events, doc_drift_events),
                }
            )
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_score(git_events: int, slack_events: int, doc_drift_events: int) -> float:
        score = (git_events * 0.05) + (slack_events * 0.04) + (doc_drift_events * 0.1)
        return round(min(score, 1.0), 4)

    @staticmethod
    def _latest_timestamp(*candidates: Any) -> Optional[str]:
        parsed: List[datetime] = []
        for value in candidates:
            if value is None:
                continue
            if isinstance(value, datetime):
                parsed.append(value)
            else:
                try:
                    parsed.append(datetime.fromisoformat(str(value)))
                except ValueError:
                    continue
        if not parsed:
            return None
        latest = max(parsed)
        return _format_datetime(latest)

