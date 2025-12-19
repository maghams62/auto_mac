"""
GraphService - thin Neo4j client used for structural reasoning.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

try:
    from neo4j import GraphDatabase, Driver  # type: ignore
except Exception:  # pragma: no cover - optional dependency until installed
    GraphDatabase = None  # type: ignore
    Driver = None  # type: ignore

from .schema import (
    GraphApiImpactSummary,
    GraphComponentSummary,
)

logger = logging.getLogger(__name__)


class GraphService:
    """Wrapper around the Neo4j Python driver with high-level queries."""

    def __init__(self, config: Dict[str, Any]):
        graph_cfg = dict(config.get("graph", {}) or {})
        env_enabled = os.getenv("NEO4J_ENABLED")
        if env_enabled is not None:
            graph_cfg["enabled"] = env_enabled.lower() == "true"

        env_uri = os.getenv("NEO4J_URI")
        env_username = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME")
        env_password = os.getenv("NEO4J_PASSWORD")
        env_database = os.getenv("NEO4J_DATABASE")

        if env_uri:
            graph_cfg["uri"] = env_uri
        if env_username:
            graph_cfg["username"] = env_username
        if env_password:
            graph_cfg["password"] = env_password
        if env_database:
            graph_cfg["database"] = env_database

        self.enabled: bool = bool(graph_cfg.get("enabled"))
        self.uri: Optional[str] = graph_cfg.get("uri")
        self.username: Optional[str] = graph_cfg.get("username")
        self.password: Optional[str] = graph_cfg.get("password")
        self.database: Optional[str] = graph_cfg.get("database")

        self._driver: Optional[Driver] = None
        self._last_query: Optional[Dict[str, Any]] = None
        if self.is_available():
            self._connect()

    def _connect(self) -> None:
        if not GraphDatabase:
            logger.warning("[GRAPH] neo4j driver not installed; graph disabled")
            self.enabled = False
            return
        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username or "", self.password or ""),
            )
            logger.info("[GRAPH] Connected to Neo4j at %s", self.uri)
        except Exception as exc:
            logger.error("[GRAPH] Failed to connect to Neo4j: %s", exc)
            self.enabled = False

    def close(self) -> None:
        if self._driver:
            try:
                self._driver.close()
            except Exception:
                pass
            finally:
                self._driver = None

    def is_available(self) -> bool:
        return bool(
            self.enabled
            and self.uri
            and self.username is not None
            and self.password is not None
        )

    # ------------------------------------------------------------------
    # Query APIs

    def get_component_neighborhood(self, component_id: str) -> GraphComponentSummary:
        """
        Return docs, issues, PRs, APIs, and Slack threads linked to a component.
        """
        if not (self._driver and self.is_available()):
            return GraphComponentSummary(component_id=component_id)

        query = """
        MATCH (c:Component {id: $component_id})
        OPTIONAL MATCH (c)<-[:DESCRIBES_COMPONENT]-(doc:Doc)
        OPTIONAL MATCH (c)<-[:AFFECTS_COMPONENT]-(issue:Issue)
        OPTIONAL MATCH (c)<-[:MODIFIES_COMPONENT]-(pr:PR)
        OPTIONAL MATCH (c)<-[:DISCUSSES_COMPONENT]-(thread:SlackThread)
        OPTIONAL MATCH (c)-[:EXPOSES_ENDPOINT]->(api:APIEndpoint)
        RETURN
            collect(DISTINCT doc.id) AS docs,
            collect(DISTINCT issue.id) AS issues,
            collect(DISTINCT pr.id) AS prs,
            collect(DISTINCT thread.id) AS slack_threads,
            collect(DISTINCT api.id) AS apis
        """

        records = self.run_query(query, {"component_id": component_id})
        if not records:
            return GraphComponentSummary(component_id=component_id)

        record = records[0]
        return GraphComponentSummary(
            component_id=component_id,
            docs=list(filter(None, record.get("docs", []))),
            issues=list(filter(None, record.get("issues", []))),
            pull_requests=list(filter(None, record.get("prs", []))),
            slack_threads=list(filter(None, record.get("slack_threads", []))),
            api_endpoints=list(filter(None, record.get("apis", []))),
        )

    def get_api_impact(self, api_id: str) -> GraphApiImpactSummary:
        """
        Return services, docs, issues, and PRs connected to an API endpoint.
        """
        if not (self._driver and self.is_available()):
            return GraphApiImpactSummary(api_id=api_id)

        query = """
        MATCH (api:APIEndpoint {id: $api_id})
        OPTIONAL MATCH (svc:Service)-[:CALLS_ENDPOINT]->(api)
        OPTIONAL MATCH (api)<-[:DESCRIBES_ENDPOINT]-(doc:Doc)
        OPTIONAL MATCH (api)<-[:REFERENCES_ENDPOINT]-(issue:Issue)
        OPTIONAL MATCH (api)<-[:MODIFIES_ENDPOINT]-(pr:PR)
        RETURN
            collect(DISTINCT svc.id) AS services,
            collect(DISTINCT doc.id) AS docs,
            collect(DISTINCT issue.id) AS issues,
            collect(DISTINCT pr.id) AS prs
        """

        records = self.run_query(query, {"api_id": api_id})
        if not records:
            return GraphApiImpactSummary(api_id=api_id)

        record = records[0]
        return GraphApiImpactSummary(
            api_id=api_id,
            services=list(filter(None, record.get("services", []))),
            docs=list(filter(None, record.get("docs", []))),
            issues=list(filter(None, record.get("issues", []))),
            pull_requests=list(filter(None, record.get("prs", []))),
        )

    # ------------------------------------------------------------------
    # Internal helpers

    def run_query(self, query: str, params: Optional[Dict[str, Any]] = None):
        if not self._driver:
            self._record_query_metadata(query, params, error="driver_unavailable")
            return []
        try:
            with self._driver.session(database=self.database or None) as session:
                result = session.run(query, params or {})
                rows = []
                for record in result:
                    row = {key: record[key] for key in record.keys()}
                    rows.append(row)
                self._record_query_metadata(query, params, row_count=len(rows))
                return rows
        except Exception as exc:
            logger.error("[GRAPH] Query failed: %s", exc)
            self._record_query_metadata(query, params, error=str(exc))
            return []

    def run_write(self, query: str, params: Optional[Dict[str, Any]] = None):
        if not self._driver:
            self._record_query_metadata(query, params, error="driver_unavailable")
            return None
        try:
            with self._driver.session(database=self.database or None) as session:
                result = session.run(query, params or {})
                summary = result.consume()
                counters = getattr(summary, "counters", None)
                row_count = None
                if counters is not None:
                    row_count = getattr(counters, "nodes_created", None)
                self._record_query_metadata(query, params, row_count=row_count)
                return summary
        except Exception as exc:
            logger.error("[GRAPH] Write query failed: %s", exc)
            self._record_query_metadata(query, params, error=str(exc))
            return None

    def last_query_metadata(self) -> Optional[Dict[str, Any]]:
        if not self._last_query:
            return None
        return dict(self._last_query)

    def _record_query_metadata(
        self,
        query: str,
        params: Optional[Dict[str, Any]],
        *,
        row_count: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        self._last_query = {
            "cypher": query.strip() if isinstance(query, str) else query,
            "params": params or {},
            "database": self.database or None,
            "row_count": row_count,
            "error": error,
        }
