"""
Dashboard-facing graph analytics helpers.

Produces aggregated component metrics, doc issue snapshots, dependency edges,
and KPI-ready rollups for the Neo4j-backed activity graph.
"""

from __future__ import annotations

import os
import threading
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

from .metrics_kpis import build_graph_kpis, count_overdue_components
from .schema import NodeLabels, RelationshipTypes
from .service import GraphService
from .fixtures import empty_graph_payload, fixture_graph_payload

try:  # pragma: no cover - optional neo4j dependency
    from neo4j.graph import Node as Neo4jNode
    from neo4j.graph import Relationship as Neo4jRelationship
except Exception:  # pragma: no cover - neo4j not installed during some tests
    Neo4jNode = Any  # type: ignore
    Neo4jRelationship = Any  # type: ignore


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _days_between(then: Optional[str]) -> Optional[float]:
    dt = _parse_datetime(then)
    if not dt:
        return None
    delta = datetime.now(timezone.utc) - dt
    return round(delta.total_seconds() / 86400.0, 2)


def _datetime_to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_epoch(value: Union[int, float]) -> float:
    """Normalize epoch values that may be expressed in seconds or milliseconds."""
    if value > 10_000_000_000:  # assume milliseconds
        return value / 1000.0
    return float(value)


def _normalize_timestamp_value(value: Any) -> Tuple[Optional[str], Optional[datetime]]:
    if value is None:
        return None, None
    dt: Optional[datetime] = None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        try:
            dt = datetime.fromtimestamp(_coerce_epoch(value), tz=timezone.utc)
        except (OSError, ValueError):
            dt = None
    elif isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None, None
        if candidate.isdigit():
            try:
                dt = datetime.fromtimestamp(_coerce_epoch(float(candidate)), tz=timezone.utc)
            except (OSError, ValueError):
                dt = None
        else:
            dt = _parse_datetime(candidate)
    if not dt:
        return None, None
    return _datetime_to_iso(dt), dt


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return _datetime_to_iso(value)
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, set):
        return [_json_ready(item) for item in sorted(value)]
    if isinstance(value, dict):
        return {str(key): _json_ready(val) for key, val in value.items()}
    return value


def _entity_properties(entity: Union[Neo4jNode, Neo4jRelationship, Dict[str, Any], None]) -> Dict[str, Any]:
    if entity is None:
        return {}
    if isinstance(entity, dict):
        return dict(entity)
    if hasattr(entity, "items"):
        try:
            return dict(entity.items())
        except Exception:  # pragma: no cover - fallback to private attrs
            pass
    if hasattr(entity, "_properties"):
        return dict(getattr(entity, "_properties") or {})
    return {}


def _entity_labels(entity: Union[Neo4jNode, Dict[str, Any], None]) -> List[str]:
    if entity is None:
        return []
    if hasattr(entity, "labels"):
        return list(getattr(entity, "labels") or [])
    props = _entity_properties(entity)
    labels = props.get("labels")
    if isinstance(labels, list):
        return labels
    return []


def _node_identifier(entity: Union[Neo4jNode, Dict[str, Any], None], props: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if props is None:
        props = _entity_properties(entity)
    node_id = props.get("id") or props.get("node_id")
    if node_id:
        return str(node_id)
    if entity is not None:
        element_id = getattr(entity, "element_id", None)
        if element_id:
            return str(element_id)
        internal_id = getattr(entity, "id", None)
        if internal_id is not None:
            return str(internal_id)
    return None


def _preferred_title(props: Dict[str, Any]) -> Optional[str]:
    for key in GRAPH_EXPLORER_PRIMARY_KEYS:
        value = props.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key in GRAPH_EXPLORER_SECONDARY_KEYS:
        value = props.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _modality_for_node(labels: List[str], props: Dict[str, Any]) -> Optional[str]:
    modality = props.get("modality") or props.get("source_type") or props.get("sourceType")
    if isinstance(modality, str) and modality.strip():
        return modality.strip().lower()
    for label in labels:
        mapped = GRAPH_EXPLORER_MODALITY_MAP.get(label)
        if mapped:
            return mapped
    return None


def _first_available(props: Dict[str, Any], keys: List[str]) -> Any:
    for key in keys:
        if key in props and props[key] not in (None, ""):
            return props[key]
    return None


@dataclass
class _ComponentState:
    data: Dict[str, Any]
    issues: List[Dict[str, Any]]
    signals: List[Dict[str, Any]]


GRAPH_EXPLORER_CORE_LABELS = [
    NodeLabels.COMPONENT.value,
    NodeLabels.SERVICE.value,
    NodeLabels.API_ENDPOINT.value,
    NodeLabels.DOC.value,
    NodeLabels.ISSUE.value,
    NodeLabels.PR.value,
    NodeLabels.SLACK_THREAD.value,
    NodeLabels.SLACK_EVENT.value,
    NodeLabels.SLACK_CONVERSATION.value,
    NodeLabels.GIT_EVENT.value,
    NodeLabels.REPOSITORY.value,
    NodeLabels.SUPPORT_CASE.value,
]

GRAPH_EXPLORER_AUX_LABELS = [
    NodeLabels.CODE_ARTIFACT.value,
    NodeLabels.SOURCE.value,
    NodeLabels.CHUNK.value,
    NodeLabels.IMPACT_EVENT.value,
    NodeLabels.ACTIVITY_SIGNAL.value,
]

GRAPH_EXPLORER_MODALITY_MAP = {
    NodeLabels.COMPONENT.value: "component",
    NodeLabels.SERVICE.value: "service",
    NodeLabels.API_ENDPOINT.value: "api",
    NodeLabels.DOC.value: "doc",
    NodeLabels.ISSUE.value: "issue",
    NodeLabels.PR.value: "git",
    NodeLabels.GIT_EVENT.value: "git",
    NodeLabels.SLACK_THREAD.value: "slack",
    NodeLabels.SLACK_EVENT.value: "slack",
    NodeLabels.SLACK_CONVERSATION.value: "slack",
    NodeLabels.ACTIVITY_SIGNAL.value: "signal",
    NodeLabels.SUPPORT_CASE.value: "support",
    NodeLabels.IMPACT_EVENT.value: "impact",
    NodeLabels.REPOSITORY.value: "repo",
}

GRAPH_EXPLORER_PRIMARY_KEYS = ["name", "title", "display_name", "summary", "id"]
GRAPH_EXPLORER_SECONDARY_KEYS = ["component_id", "service_id", "doc_id", "api_id", "channel", "repo", "path"]
GRAPH_TIMESTAMP_KEYS = [
    "created_at",
    "createdAt",
    "first_seen_at",
    "firstSeenAt",
    "detected_at",
    "timestamp",
]
GRAPH_UPDATED_KEYS = ["updated_at", "updatedAt", "last_seen_at", "lastSeenAt", "modified_at"]
GRAPH_NODE_LIMIT_MIN = 25
GRAPH_NODE_LIMIT_MAX = 1200
GRAPH_EDGE_LIMIT = 2000
GRAPH_ISSUE_DEPTH_MAX = 4


RELATIONSHIP_DEMO_EVENT_LABELS = [
    NodeLabels.SLACK_EVENT.value,
    NodeLabels.SLACK_THREAD.value,
    NodeLabels.GIT_EVENT.value,
    NodeLabels.PR.value,
]

RELATIONSHIP_DEMO_REL_TYPES = [
    RelationshipTypes.ABOUT_COMPONENT.value,
]


@dataclass
class GraphExplorerFilters:
    mode: str = "universe"
    root_id: Optional[str] = None
    depth: int = 2
    modalities: Optional[List[str]] = None
    limit: int = 400
    snapshot_raw: Optional[str] = None
    from_raw: Optional[str] = None
    to_raw: Optional[str] = None
    snapshot_dt: Optional[datetime] = None
    from_dt: Optional[datetime] = None
    to_dt: Optional[datetime] = None
    project_id: Optional[str] = None

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "mode": self.mode,
            "limit": self.limit,
            "rootId": self.root_id,
            "depth": self.depth,
            "projectId": self.project_id,
            "snapshotAt": self.snapshot_raw,
        }
        if self.modalities:
            payload["modalities"] = self.modalities
        if self.from_raw or self.to_raw:
            payload["timeRange"] = {"from": self.from_raw, "to": self.to_raw}
        return {key: value for key, value in payload.items() if value is not None}


class GraphDashboardService:
    """High-level facade that exposes dashboard-ready graph state."""

    def __init__(
        self,
        config: Dict[str, Any],
        *,
        graph_service: Optional[GraphService] = None,
    ):
        self.graph_service = graph_service or GraphService(config)
        dashboard_cfg = (config.get("graph_dashboard") or {}).get("cache", {})
        ttl_env = os.getenv("GRAPH_SNAPSHOT_CACHE_TTL")
        ttl_value = ttl_env or dashboard_cfg.get("ttl_seconds") or dashboard_cfg.get("snapshot_ttl_seconds") or 30
        try:
            ttl_parsed = int(ttl_value)
        except (TypeError, ValueError):
            ttl_parsed = 30
        self._cache_ttl_seconds = max(0, ttl_parsed)
        self._snapshot_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._metrics_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._graph_explorer_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._cache_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def is_available(self) -> bool:
        return self.graph_service.is_available()

    def get_snapshot(
        self,
        *,
        project_id: Optional[str] = None,
        window_hours: int = 168,
        component_limit: int = 150,
    ) -> Dict[str, Any]:
        cache_key = self._cache_key("snapshot", project_id, window_hours, component_limit)
        cached = self._cache_get(self._snapshot_cache, cache_key)
        if cached is not None:
            return cached

        components = self._query_components(window_hours, component_limit)
        component_map = {component.data["id"]: component for component in components}
        dependencies = self._build_dependencies(component_map)

        coverage_counts = defaultdict(int)
        for component in component_map.values():
            coverage_counts[component.data["docCoverage"]["state"]] += 1

        doc_issues = self._flatten_doc_issues(component_map.values())
        signals = self._flatten_signals(component_map.values())

        payload = {
            "generatedAt": _utc_now_iso(),
            "windowHours": window_hours,
            "componentCount": len(component_map),
            "docCoverage": coverage_counts,
            "components": [component.data for component in component_map.values()],
            "docIssues": doc_issues,
            "signals": signals,
            "dependencies": dependencies,
        }
        self._cache_set(self._snapshot_cache, cache_key, payload)
        return payload

    def get_metrics(
        self,
        *,
        project_id: Optional[str] = None,
        window_hours: int = 168,
        component_limit: int = 200,
        timeline_days: int = 14,
    ) -> Dict[str, Any]:
        cache_key = self._cache_key("metrics", project_id, window_hours, component_limit, timeline_days)
        cached = self._cache_get(self._metrics_cache, cache_key)
        if cached is not None:
            return cached

        components = self._query_components(window_hours, component_limit)
        current_state = [component.data for component in components]
        previous_state: Optional[List[Dict[str, Any]]] = None
        if window_hours > 0:
            previous_components = self._query_components(window_hours * 2, component_limit)
            previous_state = [component.data for component in previous_components]

        issue_totals = self._query_issue_totals()
        issue_timeline = self._query_issue_timeline(timeline_days)
        resolution_stats = self._query_issue_resolution_stats()

        metrics = self._build_metrics_payload(
            current_state,
            issue_totals,
            issue_timeline,
            resolution_stats,
            previous_state,
        )
        metrics["generatedAt"] = _utc_now_iso()
        metrics["windowHours"] = window_hours
        metrics["timelineDays"] = timeline_days
        self._cache_set(self._metrics_cache, cache_key, metrics)
        return metrics

    def get_universe_snapshot(
        self,
        *,
        modalities: Optional[List[str]] = None,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
        limit: int = 200,
    ) -> Dict[str, Any]:
        return self.get_graph_explorer_snapshot(
            mode="universe",
            modalities=modalities,
            from_ts=from_ts,
            to_ts=to_ts,
            limit=limit,
        )

    def get_about_component_relationships(
        self,
        *,
        component_ids: Optional[List[str]] = None,
        modalities: Optional[List[str]] = None,
        limit: int = 50,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Lightweight relationships slice: ABOUT_COMPONENT edges between Components and
        Slack/Git events, suitable for a fast, stationary demo view.
        """
        # Reuse existing normalization + payload wiring but keep the graph tiny.
        filters = GraphExplorerFilters(
            mode="universe",
            root_id=None,
            depth=1,
            modalities=modalities,
            limit=max(GRAPH_NODE_LIMIT_MIN, min(limit, 50)),
            snapshot_raw=None,
            from_raw=None,
            to_raw=None,
            snapshot_dt=None,
            from_dt=None,
            to_dt=None,
            project_id=project_id.strip() if isinstance(project_id, str) and project_id.strip() else None,
        )
        if not self.graph_service.is_available():
            return self._empty_graph_payload(filters)

        raw_nodes, raw_relationships = self._query_about_component_graph(filters, component_ids)
        return self._build_graph_explorer_payload(raw_nodes, raw_relationships, filters)

    def get_graph_explorer_snapshot(
        self,
        *,
        mode: str = "universe",
        root_id: Optional[str] = None,
        depth: int = 2,
        modalities: Optional[List[str]] = None,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
        snapshot_at: Optional[str] = None,
        limit: int = 400,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Test fixture override for deterministic UI tests.
        fixture_mode = os.getenv("BRAIN_GRAPH_FIXTURE")
        if fixture_mode:
            mode_lower = fixture_mode.lower()
            if mode_lower == "deterministic":
                return fixture_graph_payload(modalities=modalities, snapshot_at=snapshot_at)
            if mode_lower == "empty":
                return empty_graph_payload()

        filters = self._build_graph_filters(
            mode=mode,
            root_id=root_id,
            depth=depth,
            modalities=modalities,
            from_ts=from_ts,
            to_ts=to_ts,
            snapshot_at=snapshot_at,
            limit=limit,
            project_id=project_id,
        )
        if not self.graph_service.is_available():
            return self._empty_graph_payload(filters)

        cache_key = self._cache_key(
            "graph_explorer",
            filters.project_id,
            filters.mode,
            filters.root_id or "none",
            filters.depth,
            ",".join(filters.modalities or []) or "*",
            filters.limit,
            filters.snapshot_raw or "live",
            filters.from_raw or "none",
            filters.to_raw or "none",
        )
        cached_payload = self._cache_get(self._graph_explorer_cache, cache_key)
        if cached_payload:
            return cached_payload

        effective_mode = filters.mode
        if effective_mode == "issue" and not filters.root_id:
            effective_mode = "universe"
            filters.mode = "universe"

        if effective_mode == "issue":
            raw_nodes, raw_relationships = self._query_issue_graph(filters)
        elif effective_mode == "neo4j_default":
            raw_nodes, raw_relationships = self._query_neo4j_default_graph(filters)
        else:
            raw_nodes, raw_relationships = self._query_universe_graph(filters)

        payload = self._build_graph_explorer_payload(raw_nodes, raw_relationships, filters)
        self._cache_set(self._graph_explorer_cache, cache_key, payload)
        return payload

    def _build_graph_filters(
        self,
        *,
        mode: str,
        root_id: Optional[str],
        depth: int,
        modalities: Optional[List[str]],
        from_ts: Optional[str],
        to_ts: Optional[str],
        snapshot_at: Optional[str],
        limit: int,
        project_id: Optional[str],
    ) -> GraphExplorerFilters:
        normalized_mode = (mode or "universe").strip().lower()
        if normalized_mode not in {"universe", "issue", "neo4j_default"}:
            normalized_mode = "universe"

        cleaned_modalities: Optional[List[str]] = None
        if modalities:
            cleaned = sorted({m.strip().lower() for m in modalities if isinstance(m, str) and m.strip()})
            if cleaned:
                cleaned_modalities = cleaned

        sanitized_limit = max(GRAPH_NODE_LIMIT_MIN, min(limit or GRAPH_NODE_LIMIT_MIN, GRAPH_NODE_LIMIT_MAX))
        sanitized_depth = max(1, min(depth or 1, GRAPH_ISSUE_DEPTH_MAX))

        snapshot_dt = _parse_datetime(snapshot_at)
        from_raw = from_ts
        to_raw = to_ts
        from_dt = _parse_datetime(from_ts) if not snapshot_dt else None
        to_dt = _parse_datetime(to_ts) if not snapshot_dt else None
        if snapshot_dt:
            from_raw = None
            to_raw = None

        normalized_root = root_id.strip() if isinstance(root_id, str) and root_id.strip() else None
        normalized_project = project_id.strip() if isinstance(project_id, str) and project_id.strip() else None

        return GraphExplorerFilters(
            mode=normalized_mode,
            root_id=normalized_root,
            depth=sanitized_depth,
            modalities=cleaned_modalities,
            limit=sanitized_limit,
            snapshot_raw=snapshot_at,
            from_raw=from_raw,
            to_raw=to_raw,
            snapshot_dt=snapshot_dt,
            from_dt=from_dt,
            to_dt=to_dt,
            project_id=normalized_project,
        )

    def _empty_graph_payload(self, filters: GraphExplorerFilters) -> Dict[str, Any]:
        return {
            "generatedAt": _utc_now_iso(),
            "nodes": [],
            "edges": [],
            "filters": filters.to_payload(),
            "meta": {
                "nodeLabelCounts": {},
                "relTypeCounts": {},
                "propertyKeys": [],
                "modalityCounts": {},
                "missingTimestampLabels": [],
                "minTimestamp": None,
                "maxTimestamp": None,
            },
        }

    def _query_universe_graph(self, filters: GraphExplorerFilters) -> Tuple[List[Any], List[Any]]:
        aux_limit = max(25, filters.limit // 2)
        neighbor_limit = min(filters.limit * 2, GRAPH_NODE_LIMIT_MAX)
        params = {
            "core_labels": GRAPH_EXPLORER_CORE_LABELS,
            "aux_labels": GRAPH_EXPLORER_AUX_LABELS,
            "node_limit": filters.limit,
            "aux_limit": aux_limit,
            "neighbor_limit": neighbor_limit,
        }
        query = """
        MATCH (core)
        WHERE any(label IN labels(core) WHERE label IN $core_labels)
        WITH core
        ORDER BY coalesce(
            core.updated_at,
            core.updatedAt,
            core.created_at,
            core.createdAt,
            core.first_seen_at,
            core.firstSeenAt,
            datetime()
        ) DESC
        LIMIT $node_limit
        WITH collect(core) AS seed_nodes
        UNWIND seed_nodes AS seed
        OPTIONAL MATCH (seed)-[core_rel]-(neighbor)
        WHERE any(label IN labels(neighbor) WHERE label IN $core_labels)
        WITH seed_nodes, collect(DISTINCT neighbor)[0..$neighbor_limit] AS neighbor_nodes
        WITH seed_nodes + neighbor_nodes AS expanded_core_nodes
        UNWIND expanded_core_nodes AS c
        OPTIONAL MATCH (c)-[aux_rel]-(aux)
        WHERE any(label IN labels(aux) WHERE label IN $aux_labels)
        WITH collect(DISTINCT c) AS dedup_core_nodes, collect(DISTINCT aux) AS raw_aux_nodes
        WITH dedup_core_nodes,
             [node IN raw_aux_nodes WHERE node IS NOT NULL][0..$aux_limit] AS aux_nodes
        WITH dedup_core_nodes + aux_nodes AS nodes
        UNWIND nodes AS source
        OPTIONAL MATCH (source)-[rel]-(target)
        WHERE target IN nodes
        RETURN source AS node, rel, target
        """
        rows = self.graph_service.run_query(query, params) or []
        nodes: List[Any] = []
        relationships: List[Any] = []
        for row in rows:
            source = row.get("node") or row.get("source")
            target = row.get("target")
            rel = row.get("rel")
            if source:
                nodes.append(source)
            if target:
                nodes.append(target)
            if rel:
                relationships.append(rel)
        return nodes, relationships

    def _query_neo4j_default_graph(self, filters: GraphExplorerFilters) -> Tuple[List[Any], List[Any]]:
        label_weights = {
            "APIEndpoint": 4,
            "ActivitySignal": 3,
            "Channel": 2,
            "Chunk": 2,
            "CodeArtifact": 2,
            "Component": 8,
            "Doc": 6,
            "GitEvent": 8,
            "ImpactEvent": 3,
            "Issue": 4,
            "PR": 4,
            "Playlist": 1,
            "Repository": 3,
            "Service": 4,
            "SlackEvent": 5,
            "SlackThread": 4,
            "Source": 2,
            "SupportCase": 3,
            "TranscriptChunk": 2,
            "Video": 1,
        }
        relationship_types = [
            "HAS_COMPONENT",
            "EXPOSES_ENDPOINT",
            "DESCRIBES_ENDPOINT",
            "DOC_DOCUMENTS_COMPONENT",
            "DOC_DOCUMENTS_API",
            "DESCRIBES_COMPONENT",
            "TOUCHES_COMPONENT",
            "MODIFIES_COMPONENT",
            "MODIFIES_API",
            "ABOUT_COMPONENT",
            "AFFECTS_COMPONENT",
            "SUPPORTS_COMPONENT",
            "SIGNALS_COMPONENT",
            "REFERENCES_DOC",
            "ATTACHED_TO",
            "BELONGS_TO",
            "BELONGS_TO_CHANNEL",
            "COMPLAINS_ABOUT_API",
            "DEPENDS_ON",
            "DERIVED_FROM",
            "HAS_CHUNK",
            "IMPACTS_COMPONENT",
            "IMPACTS_DOC",
            "IMPACTS_SERVICE",
            "OWNS_CODE",
            "PART_OF_PLAYLIST",
            "REPO_OWNS_COMPONENT",
        ]

        node_budget = max(GRAPH_NODE_LIMIT_MIN, min(filters.limit, 250))
        edge_budget = max(25, min(node_budget * 2, 400))
        total_weight = max(1, sum(label_weights.values()))
        scale = node_budget / total_weight if total_weight else 1

        label_configs: List[Dict[str, Any]] = []
        for label, weight in label_weights.items():
            raw_limit = max(1, int(round(weight * scale)))
            label_configs.append(
                {
                    "label": label,
                    "limit": min(node_budget, raw_limit),
                }
            )

        node_seed_query = """
        WITH $label_configs AS label_configs
        UNWIND label_configs AS cfg
        CALL {
            WITH cfg
            MATCH (n)
            WHERE cfg.label IN labels(n)
            WITH
                cfg,
                n,
                coalesce(
                    n.updated_at,
                    n.updatedAt,
                    n.timestamp,
                    n.created_at,
                    n.createdAt,
                    datetime()
                ) AS sort_key
            ORDER BY sort_key DESC, id(n) ASC
            WITH cfg, collect(n)[0..cfg.limit] AS label_nodes
            RETURN label_nodes
        }
        UNWIND label_nodes AS candidate
        WITH DISTINCT candidate
        WITH collect(candidate) AS nodes
        RETURN nodes
        """
        node_rows = self.graph_service.run_query(
            node_seed_query,
            {"label_configs": label_configs},
        ) or []
        seeded_nodes: List[Any] = []
        if node_rows:
            seeded_nodes = node_rows[0].get("nodes") or []

        nodes: List[Any] = []
        seen_id_list: List[str] = []
        seen_ids: Set[str] = set()

        def append_node(entity: Any) -> None:
            if not entity or len(nodes) >= node_budget:
                return
            node_id = _node_identifier(entity)
            if node_id:
                if node_id in seen_ids:
                    return
                seen_ids.add(node_id)
                seen_id_list.append(node_id)
            nodes.append(entity)

        for entity in seeded_nodes[:node_budget]:
            append_node(entity)
            if len(nodes) >= node_budget:
                break

        shortage = max(0, node_budget - len(nodes))
        if shortage > 0:
            fallback_query = """
            MATCH (n)
            WHERE NOT coalesce(n.id, n.node_id, elementId(n)) IN $exclude_ids
            WITH
                n,
                coalesce(
                    n.updated_at,
                    n.updatedAt,
                    n.timestamp,
                    n.created_at,
                    n.createdAt,
                    datetime()
                ) AS sort_key
            ORDER BY sort_key DESC, id(n) ASC
            RETURN n AS node
            LIMIT toInteger($limit)
            """
            fallback_rows = self.graph_service.run_query(
                fallback_query,
                {"exclude_ids": seen_id_list, "limit": shortage},
            ) or []
            for row in fallback_rows:
                append_node(row.get("node"))
                if len(nodes) >= node_budget:
                    break

        relationships: List[Any] = []
        if seen_id_list:
            relationship_query = """
            MATCH (source)-[rel]-(target)
            WHERE
                coalesce(source.id, source.node_id, elementId(source)) IN $node_ids
                AND coalesce(target.id, target.node_id, elementId(target)) IN $node_ids
                AND ($relationship_types = [] OR type(rel) IN $relationship_types)
            WITH
                rel,
                coalesce(source.id, source.node_id, elementId(source)) AS source_id,
                coalesce(target.id, target.node_id, elementId(target)) AS target_id
            ORDER BY coalesce(rel.timestamp, rel.updated_at, rel.created_at, datetime()) DESC, type(rel) ASC
            RETURN {
                id: coalesce(rel.id, elementId(rel)),
                type: type(rel),
                from: source_id,
                to: target_id,
                created_at: coalesce(rel.timestamp, rel.updated_at, rel.created_at),
                props: properties(rel)
            } AS rel_payload
            LIMIT toInteger($edge_limit)
            """
            rel_rows = self.graph_service.run_query(
                relationship_query,
                {
                    "node_ids": seen_id_list,
                    "relationship_types": relationship_types,
                    "edge_limit": edge_budget,
                },
            ) or []
            for row in rel_rows:
                rel = row.get("rel_payload")
                if rel and rel.get("from") and rel.get("to"):
                    relationships.append(rel)

        return nodes, relationships

    def _query_about_component_graph(
        self,
        filters: GraphExplorerFilters,
        component_ids: Optional[List[str]] = None,
    ) -> Tuple[List[Any], List[Any]]:
        """
        Return a tiny neighborhood of ABOUT_COMPONENT relationships suitable for a
        fast relationships diagram. This intentionally ignores most modalities and
        focuses on Components plus Slack/Git events.
        """
        params = {
            "component_ids": component_ids,
            "event_labels": RELATIONSHIP_DEMO_EVENT_LABELS,
            "node_limit": max(25, min(filters.limit, 50)),
        }
        query = """
        MATCH (c:Component)
        WHERE $component_ids IS NULL OR c.id IN $component_ids
        WITH c
        ORDER BY c.name ASC, c.id ASC
        LIMIT CASE WHEN $component_ids IS NULL THEN 3 ELSE size($component_ids) END
        WITH collect(c) AS components

        UNWIND components AS chosen
        OPTIONAL MATCH (event)-[rel:ABOUT_COMPONENT]->(chosen)
        WHERE any(label IN labels(event) WHERE label IN $event_labels)
        WITH
          components,
          chosen,
          event,
          rel,
          coalesce(
            rel.created_at,
            rel.createdAt,
            event.created_at,
            event.createdAt,
            datetime()
          ) AS rel_order
        ORDER BY chosen.name ASC, rel_order DESC
        WITH
          components,
          [event IN collect(event) WHERE event IS NOT NULL][0..$node_limit] AS ordered_events,
          [rel IN collect(rel) WHERE rel IS NOT NULL][0..$node_limit] AS ordered_relationships

        WITH components + ordered_events AS nodes, ordered_relationships AS relationships
        UNWIND nodes AS source
        OPTIONAL MATCH (source)-[rel]-(target)
        WHERE rel IN relationships AND target IN nodes
        RETURN source AS node, rel, target
        """
        rows = self.graph_service.run_query(query, params) or []
        nodes: List[Any] = []
        relationships: List[Any] = []
        for row in rows:
            source = row.get("node") or row.get("source")
            target = row.get("target")
            rel = row.get("rel")
            if source:
                nodes.append(source)
            if target:
                nodes.append(target)
            if rel:
                relationships.append(rel)
        return nodes, relationships

    def _query_issue_graph(self, filters: GraphExplorerFilters) -> Tuple[List[Any], List[Any]]:
        if not filters.root_id:
            return [], []
        params = {
            "root_id": filters.root_id,
            "node_limit": filters.limit,
            "max_depth": filters.depth,
        }
        query = f"""
        MATCH (root {{id: $root_id}})
        OPTIONAL MATCH path=(root)-[*..{GRAPH_ISSUE_DEPTH_MAX}]-(neighbor)
        WHERE neighbor IS NOT NULL AND length(path) <= $max_depth
        WITH root, [n IN collect(DISTINCT neighbor) WHERE n IS NOT NULL][0..$node_limit] AS neighbor_nodes
        WITH ([root] + neighbor_nodes)[0..$node_limit] AS nodes
        UNWIND nodes AS source
        OPTIONAL MATCH (source)-[rel]-(target)
        WHERE target IN nodes
        RETURN source AS node, rel, target
        """
        rows = self.graph_service.run_query(query, params) or []
        nodes: List[Any] = []
        relationships: List[Any] = []
        for row in rows:
            source = row.get("node") or row.get("source")
            target = row.get("target")
            rel = row.get("rel")
            if source:
                nodes.append(source)
            if target:
                nodes.append(target)
            if rel:
                relationships.append(rel)
        return nodes, relationships

    def _build_graph_explorer_payload(
        self,
        raw_nodes: Sequence[Any],
        raw_relationships: Sequence[Any],
        filters: GraphExplorerFilters,
    ) -> Dict[str, Any]:
        node_store: Dict[str, Dict[str, Any]] = {}
        node_timestamps: Dict[str, Optional[datetime]] = {}
        label_counts: Counter = Counter()
        modality_counts: Counter = Counter()
        property_keys: Set[str] = set()
        missing_timestamp_labels: Set[str] = set()
        min_ts: Optional[datetime] = None
        max_ts: Optional[datetime] = None

        for entity in raw_nodes:
            node_payload, created_dt = self._normalize_graph_node(entity, filters)
            if not node_payload:
                continue
            node_id = node_payload["id"]
            if node_id in node_store:
                continue
            node_store[node_id] = node_payload
            node_timestamps[node_id] = created_dt
            property_keys.update(node_payload["props"].keys())
            label_counts[node_payload["label"]] += 1
            modality = node_payload.get("modality")
            if modality:
                modality_counts[modality] += 1
            if created_dt:
                if not min_ts or created_dt < min_ts:
                    min_ts = created_dt
                if not max_ts or created_dt > max_ts:
                    max_ts = created_dt
            else:
                missing_timestamp_labels.add(node_payload["label"])

        edges: List[Dict[str, Any]] = []
        rel_type_counts: Counter = Counter()
        seen_relationships: Set[str] = set()
        for rel in raw_relationships:
            edge_payload = self._normalize_graph_edge(rel, node_store, node_timestamps, filters)
            if not edge_payload:
                continue
            edge_id = edge_payload["id"]
            if edge_id in seen_relationships:
                continue
            seen_relationships.add(edge_id)
            property_keys.update(edge_payload["props"].keys())
            rel_type_counts[edge_payload["type"]] += 1
            edges.append(edge_payload)
            if len(edges) >= GRAPH_EDGE_LIMIT:
                break

        nodes = list(node_store.values())
        meta = {
            "nodeLabelCounts": dict(label_counts),
            "relTypeCounts": dict(rel_type_counts),
            "propertyKeys": sorted(property_keys),
            "modalityCounts": dict(modality_counts),
            "missingTimestampLabels": sorted(missing_timestamp_labels),
            "minTimestamp": _datetime_to_iso(min_ts) if min_ts else None,
            "maxTimestamp": _datetime_to_iso(max_ts) if max_ts else None,
        }
        return {
            "generatedAt": _utc_now_iso(),
            "nodes": nodes,
            "edges": edges,
            "filters": filters.to_payload(),
            "meta": meta,
        }

    def _normalize_graph_node(
        self,
        entity: Union[Neo4jNode, Dict[str, Any]],
        filters: GraphExplorerFilters,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[datetime]]:
        props = _entity_properties(entity)
        node_id = _node_identifier(entity, props)
        if not node_id:
            return None, None
        labels = _entity_labels(entity)
        primary_label = labels[0] if labels else "Node"
        modality = _modality_for_node(labels, props)
        if not self._modalities_match(modality, filters):
            return None, None

        created_value = _first_available(props, GRAPH_TIMESTAMP_KEYS)
        created_iso, created_dt = _normalize_timestamp_value(created_value)
        if not self._timestamp_in_range(created_dt, filters):
            return None, None
        updated_iso, _ = _normalize_timestamp_value(_first_available(props, GRAPH_UPDATED_KEYS))

        sanitized_props = {key: _json_ready(value) for key, value in props.items() if key not in {"x", "y", "z"}}
        coords = self._stable_coords(node_id)
        node_payload: Dict[str, Any] = {
            "id": node_id,
            "label": primary_label,
            "labels": labels or None,
            "title": _preferred_title(props) or node_id,
            "modality": modality,
            "createdAt": created_iso,
            "updatedAt": updated_iso,
            "props": sanitized_props,
            "x": coords.get("x"),
            "y": coords.get("y"),
        }
        if "z" in coords:
            node_payload["z"] = coords["z"]
        if node_payload["labels"] is None:
            node_payload.pop("labels", None)
        if node_payload.get("modality") is None:
            node_payload.pop("modality", None)
        if node_payload.get("createdAt") is None:
            node_payload.pop("createdAt", None)
        if node_payload.get("updatedAt") is None:
            node_payload.pop("updatedAt", None)
        return node_payload, created_dt

    def _normalize_graph_edge(
        self,
        relationship: Union[Neo4jRelationship, Dict[str, Any]],
        node_store: Dict[str, Dict[str, Any]],
        node_timestamps: Dict[str, Optional[datetime]],
        filters: GraphExplorerFilters,
    ) -> Optional[Dict[str, Any]]:
        if relationship is None:
            return None
        props = _entity_properties(relationship)
        rel_id = props.get("id") or getattr(relationship, "element_id", None) or getattr(relationship, "id", None)
        rel_type = getattr(relationship, "type", None) or props.get("type") or "RELATED"

        start_node = getattr(relationship, "start_node", None)
        end_node = getattr(relationship, "end_node", None)
        if not start_node and hasattr(relationship, "nodes"):
            nodes = getattr(relationship, "nodes")
            if isinstance(nodes, (list, tuple)) and len(nodes) >= 2:
                start_node, end_node = nodes[0], nodes[1]

        start_id = _node_identifier(start_node)
        end_id = _node_identifier(end_node)
        if not start_id or not end_id:
            start_id = props.get("from") or props.get("source")
            end_id = props.get("to") or props.get("target")
        if not start_id or not end_id:
            return None
        if start_id not in node_store or end_id not in node_store:
            return None

        created_value = _first_available(props, GRAPH_TIMESTAMP_KEYS)
        created_iso, created_dt = _normalize_timestamp_value(created_value)
        if not created_dt:
            neighbor_times = [ts for ts in (node_timestamps.get(start_id), node_timestamps.get(end_id)) if ts]
            if neighbor_times:
                created_dt = max(neighbor_times)
                created_iso = _datetime_to_iso(created_dt)
        if created_dt and not self._timestamp_in_range(created_dt, filters):
            return None

        sanitized_props = {key: _json_ready(value) for key, value in props.items()}
        return {
            "id": str(rel_id or f"rel:{start_id}->{end_id}"),
            "source": start_id,
            "target": end_id,
            "type": str(rel_type),
            "createdAt": created_iso,
            "props": sanitized_props,
        }

    @staticmethod
    def _modalities_match(modality: Optional[str], filters: GraphExplorerFilters) -> bool:
        if not filters.modalities:
            return True
        if not modality:
            return False
        return modality.lower() in filters.modalities

    @staticmethod
    def _timestamp_in_range(timestamp: Optional[datetime], filters: GraphExplorerFilters) -> bool:
        if filters.snapshot_dt:
            if timestamp is None:
                return True
            return timestamp <= filters.snapshot_dt
        if filters.from_dt and timestamp and timestamp < filters.from_dt:
            return False
        if filters.to_dt and timestamp and timestamp > filters.to_dt:
            return False
        return True

    def get_trace_graph(self, chunk_ids: List[str]) -> Dict[str, Any]:
        cleaned_ids = [cid for cid in chunk_ids if cid]
        if not cleaned_ids or not self.graph_service.is_available():
            return {"nodes": [], "edges": []}
        query = """
        MATCH (chunk:Chunk)-[:BELONGS_TO]->(source:Source)
        WHERE chunk.id IN $chunk_ids
        RETURN chunk, source
        """
        records = self.graph_service.run_query(query, {"chunk_ids": cleaned_ids}) or []
        return self._build_universe_payload(records, {"modalities": [], "from_ts": None, "to_ts": None, "limit": len(cleaned_ids)})

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def _query_components(
        self,
        window_hours: int,
        component_limit: int,
        *,
        issue_limit: int = 6,
        signal_limit: int = 4,
    ) -> List[_ComponentState]:
        if not self.graph_service.is_available():
            return []

        cutoff = max(0, window_hours)
        params = {
            "cutoff": cutoff,
            "component_limit": max(1, component_limit),
            "issue_limit": max(1, issue_limit),
            "signal_limit": max(1, signal_limit),
        }
        query = """
        WITH CASE WHEN $cutoff > 0 THEN datetime() - duration({hours: $cutoff}) ELSE NULL END AS cutoff
        MATCH (c:Component)
        CALL {
            WITH c
            OPTIONAL MATCH (doc:Doc)-[:DESCRIBES_COMPONENT]->(c)
            RETURN count(doc) AS doc_count
        }
        CALL {
            WITH c
            OPTIONAL MATCH (issue:Issue)-[:AFFECTS_COMPONENT]->(c)
            WITH issue
            ORDER BY issue.updated_at DESC
            RETURN
                count(issue) AS issue_count,
                sum(CASE WHEN coalesce(issue.state, 'open') IN ['open', 'active'] THEN 1 ELSE 0 END) AS open_issue_count,
                sum(
                    CASE issue.severity
                        WHEN 'critical' THEN 80
                        WHEN 'high' THEN 60
                        WHEN 'medium' THEN 40
                        WHEN 'low' THEN 20
                        ELSE 10
                    END
                ) AS issue_severity_score,
                collect(
                    issue {
                        .id,
                        .doc_id,
                        .doc_title,
                        .doc_url,
                        .severity,
                        .state,
                        .summary,
                        .updated_at,
                        .created_at,
                        .source,
                        .linked_change
                    }
                )[0..$issue_limit] AS top_issues,
                max(issue.updated_at) AS last_issue_updated
        }
        CALL {
            WITH c, cutoff
            OPTIONAL MATCH (sig:ActivitySignal)-[rel:SIGNALS_COMPONENT]->(c)
            WHERE cutoff IS NULL OR rel.last_seen IS NULL OR datetime(rel.last_seen) >= cutoff
            RETURN
                sum(CASE WHEN sig.source STARTS WITH 'github' THEN coalesce(rel.signal_weight, 1.0) ELSE 0 END) AS git_weight,
                sum(CASE WHEN sig.source = 'slack' THEN coalesce(rel.signal_weight, 1.0) ELSE 0 END) AS slack_weight,
                collect(
                    CASE
                        WHEN sig.source IN ['slack', 'tickets', 'support']
                        THEN sig {
                            .id,
                            .source,
                            .title,
                            .summary,
                            weight: coalesce(rel.signal_weight, 1.0),
                            last_seen: rel.last_seen
                        }
                        ELSE NULL
                    END
                )[0..$signal_limit] AS raw_signals
        }
        CALL {
            WITH c, cutoff
            OPTIONAL MATCH (support:SupportCase)-[rel:SUPPORTS_COMPONENT]->(c)
            WHERE cutoff IS NULL OR rel.last_seen IS NULL OR datetime(rel.last_seen) >= cutoff
            RETURN
                sum(coalesce(rel.signal_weight, 1.0)) AS support_weight,
                collect(
                    support {
                        .id,
                        .source,
                        .title,
                        .summary,
                        weight: coalesce(rel.signal_weight, 1.0),
                        last_seen: rel.last_seen
                    }
                )[0..$signal_limit] AS support_signals
        }
        RETURN
            c.id AS component_id,
            c.name AS component_name,
            c.repo AS repo_id,
            c.horizon AS horizon,
            c.tags AS tags,
            doc_count,
            issue_count,
            open_issue_count,
            issue_severity_score,
            last_issue_updated,
            git_weight,
            slack_weight,
            support_weight,
            top_issues,
            raw_signals,
            support_signals
        ORDER BY issue_severity_score DESC, component_id ASC
        LIMIT $component_limit
        """
        records = self.graph_service.run_query(query, params) or []
        states: List[_ComponentState] = []
        for row in records:
            component = self._build_component_state(row)
            states.append(component)
        return states

    def _build_dependencies(self, component_map: Dict[str, _ComponentState]) -> List[Dict[str, Any]]:
        if not component_map or not self.graph_service.is_available():
            for component in component_map.values():
                component.data["blastRadius"] = 0
            return []

        query = """
        MATCH (source:Component)-[rel:COMPONENT_USES_COMPONENT]->(target:Component)
        RETURN source.id AS source_id,
               target.id AS target_id,
               rel.reason AS reason
        """
        records = self.graph_service.run_query(query) or []
        incoming_counts: Dict[str, int] = defaultdict(int)
        dependencies: List[Dict[str, Any]] = []
        for row in records:
            source_id = row.get("source_id")
            target_id = row.get("target_id")
            if source_id not in component_map or target_id not in component_map:
                continue
            incoming_counts[target_id] += 1
            source_state = component_map[source_id].data
            target_state = component_map[target_id].data
            impact_weight = self._edge_weight(source_state, target_state)
            dependencies.append(
                {
                    "id": f"edge:{source_id}->{target_id}",
                    "source": source_id,
                    "target": target_id,
                    "reason": row.get("reason"),
                    "impactWeight": impact_weight,
                    "dominantSignal": target_state.get("dominantSignal"),
                }
            )

        for component_id, component in component_map.items():
            component.data["blastRadius"] = incoming_counts.get(component_id, 0)

        return dependencies

    def _query_issue_totals(self) -> Dict[str, int]:
        if not self.graph_service.is_available():
            return {"open": 0, "critical_open": 0, "closed": 0}
        query = """
        MATCH (issue:Issue)
        RETURN
            sum(CASE WHEN coalesce(issue.state, 'open') IN ['open', 'active'] THEN 1 ELSE 0 END) AS open_issues,
            sum(CASE WHEN coalesce(issue.state, 'open') IN ['open', 'active'] AND issue.severity = 'critical' THEN 1 ELSE 0 END) AS critical_open,
            sum(CASE WHEN coalesce(issue.state, 'open') IN ['resolved', 'closed'] THEN 1 ELSE 0 END) AS closed_issues
        """
        record = (self.graph_service.run_query(query) or [{}])[0]
        return {
            "open": int(record.get("open_issues", 0) or 0),
            "critical_open": int(record.get("critical_open", 0) or 0),
            "closed": int(record.get("closed_issues", 0) or 0),
        }

    def _query_issue_timeline(self, timeline_days: int) -> List[Dict[str, Any]]:
        if not self.graph_service.is_available():
            return []
        params = {"days": max(1, timeline_days)}
        query = """
        WITH date(datetime()) AS today
        UNWIND range(0, $days - 1) AS offset
        WITH (today - duration({days: offset})) AS day
        CALL {
            WITH day
            MATCH (issue:Issue)
            WHERE issue.created_at IS NOT NULL AND date(datetime(issue.created_at)) = day
            RETURN count(issue) AS opened
        }
        CALL {
            WITH day
            MATCH (issue:Issue)
            WHERE issue.updated_at IS NOT NULL
              AND coalesce(issue.state, 'open') IN ['resolved', 'closed']
              AND date(datetime(issue.updated_at)) = day
            RETURN count(issue) AS resolved
        }
        RETURN day AS date, opened, resolved
        ORDER BY day ASC
        """
        records = self.graph_service.run_query(query, params) or []
        timeline: List[Dict[str, Any]] = []
        for row in records:
            date_value = row.get("date")
            if hasattr(date_value, "to_native"):  # neo4j.Date
                date_value = date_value.to_native()
            if hasattr(date_value, "isoformat"):
                date_str = date_value.isoformat()
            else:
                date_str = str(date_value)
            timeline.append(
                {
                    "date": date_str,
                    "opened": int(row.get("opened", 0) or 0),
                    "resolved": int(row.get("resolved", 0) or 0),
                }
            )
        return timeline

    def _query_issue_resolution_stats(self) -> Dict[str, Optional[float]]:
        if not self.graph_service.is_available():
            return {"mttr_hours": None}
        query = """
        MATCH (issue:Issue)
        WHERE issue.created_at IS NOT NULL
          AND issue.updated_at IS NOT NULL
          AND coalesce(issue.state, 'open') IN ['resolved', 'closed']
        WITH duration.between(datetime(issue.created_at), datetime(issue.updated_at)) AS delta
        RETURN avg(delta.hours) AS avg_hours
        """
        record = (self.graph_service.run_query(query) or [{}])[0]
        avg_hours = record.get("avg_hours")
        if avg_hours is None:
            return {"mttr_hours": None}
        try:
            return {"mttr_hours": round(float(avg_hours), 2)}
        except (TypeError, ValueError):
            return {"mttr_hours": None}

    # ------------------------------------------------------------------
    # Universe helpers
    # ------------------------------------------------------------------
    def _build_universe_payload(
        self,
        records: List[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []
        modality_counts: Dict[str, int] = defaultdict(int)
        for row in records:
            chunk = row.get("chunk") or {}
            source = row.get("source") or {}
            chunk_id = chunk.get("id")
            source_id = source.get("id")
            if not chunk_id or not source_id:
                continue

            chunk_node_id = chunk_id
            if chunk_node_id not in nodes:
                nodes[chunk_node_id] = {
                    "id": chunk_node_id,
                    "type": "chunk",
                    "source_type": chunk.get("source_type"),
                    "entity_id": chunk.get("entity_id"),
                    "workspace_id": chunk.get("workspace_id"),
                    "start_offset": chunk.get("start_offset"),
                    "end_offset": chunk.get("end_offset"),
                    "url": chunk.get("url"),
                    "text_preview": chunk.get("text_preview"),
                }
                nodes[chunk_node_id].update(self._stable_coords(chunk_node_id))
            chunk_source_type = chunk.get("source_type")
            if chunk_source_type:
                modality_counts[chunk_source_type] += 1

            source_node_id = f"source:{source_id}"
            if source_node_id not in nodes:
                nodes[source_node_id] = {
                    "id": source_node_id,
                    "type": "source",
                    "source_type": source.get("source_type"),
                    "source_id": source_id,
                    "display_name": source.get("display_name"),
                    "path": source.get("path"),
                    "workspace_id": source.get("workspace_id"),
                }
                nodes[source_node_id].update(self._stable_coords(source_node_id))

            edge_id = f"edge:{chunk_node_id}->{source_node_id}"
            edges.append(
                {
                    "id": edge_id,
                    "from": chunk_node_id,
                    "to": source_node_id,
                    "type": "BELONGS_TO",
                }
            )

        modality_meta = [
            {"source_type": source_type, "count": count}
            for source_type, count in sorted(modality_counts.items(), key=lambda item: (-item[1], item[0]))
        ]

        return {
            "generatedAt": _utc_now_iso(),
            "nodes": list(nodes.values()),
            "edges": edges,
            "filters": params,
            "meta": {"modalities": modality_meta},
        }

    @staticmethod
    def _stable_coords(identifier: str) -> Dict[str, float]:
        digest = hashlib.sha1(identifier.encode("utf-8")).digest()
        coords = []
        for offset in range(3):
            value = digest[offset]
            coords.append((value / 255.0) * 2 - 1)
        return {"x": coords[0], "y": coords[1], "z": coords[2]}

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------
    def _cache_key(self, prefix: str, project_id: Optional[str], *args: Any) -> str:
        project_key = project_id or "default"
        arg_key = ":".join(str(arg) for arg in args)
        return f"{prefix}::{project_key}::{arg_key}"

    def _cache_get(
        self,
        cache: Dict[str, Tuple[float, Dict[str, Any]]],
        key: str,
    ) -> Optional[Dict[str, Any]]:
        if self._cache_ttl_seconds <= 0:
            return None
        with self._cache_lock:
            entry = cache.get(key)
            if not entry:
                return None
            expires_at, payload = entry
            if expires_at < monotonic():
                cache.pop(key, None)
                return None
            return payload

    def _cache_set(
        self,
        cache: Dict[str, Tuple[float, Dict[str, Any]]],
        key: str,
        payload: Dict[str, Any],
    ) -> None:
        if self._cache_ttl_seconds <= 0:
            return
        expires_at = monotonic() + self._cache_ttl_seconds
        with self._cache_lock:
            cache[key] = (expires_at, payload)

    # ------------------------------------------------------------------
    # Payload builders
    # ------------------------------------------------------------------
    def _build_component_state(self, row: Dict[str, Any]) -> _ComponentState:
        component_id = row.get("component_id")
        name = row.get("component_name") or component_id
        doc_count = int(row.get("doc_count", 0) or 0)
        issue_count = int(row.get("issue_count", 0) or 0)
        open_issue_count = int(row.get("open_issue_count", 0) or 0)
        issue_severity_score = float(row.get("issue_severity_score", 0.0) or 0.0)
        git_weight = float(row.get("git_weight", 0.0) or 0.0)
        slack_weight = float(row.get("slack_weight", 0.0) or 0.0)
        support_weight = float(row.get("support_weight", 0.0) or 0.0)
        last_issue_updated = row.get("last_issue_updated")

        issue_norm = min(70.0, issue_severity_score * 0.6)
        support_norm = min(20.0, support_weight * 4.0)
        slack_norm = min(10.0, slack_weight * 4.0)
        drift_score = round(min(100.0, issue_norm + support_norm + slack_norm), 2)

        git_norm = min(60.0, git_weight * 6.0)
        slack_activity_norm = min(40.0, slack_weight * 5.0)
        activity_score = round(min(100.0, git_norm + slack_activity_norm), 2)

        doc_state = self._doc_coverage_state(doc_count)
        freshness_days = _days_between(last_issue_updated)

        issues = self._normalize_issue_list(component_id, row.get("top_issues") or [])
        signals = self._normalize_signals(component_id, row.get("raw_signals") or [], row.get("support_signals") or [])

        signal_mix = {
            "git": round(git_weight, 4),
            "slack": round(slack_weight, 4),
            "tickets": round(issue_severity_score / 80.0, 4),
            "support": round(support_weight, 4),
        }
        dominant_signal = max(signal_mix.items(), key=lambda item: item[1])[0] if any(signal_mix.values()) else None

        component_data = {
            "id": component_id,
            "name": name,
            "repoId": row.get("repo_id"),
            "horizon": row.get("horizon"),
            "tags": row.get("tags") or [],
            "docCoverage": {"state": doc_state, "count": doc_count},
            "docFreshnessDays": freshness_days,
            "issueCount": issue_count,
            "openIssues": open_issue_count,
            "driftScore": drift_score,
            "activityScore": activity_score,
            "changeVelocity": round(git_weight, 4),
            "supportPressure": round(support_weight, 4),
            "signalMix": signal_mix,
            "dominantSignal": dominant_signal,
            "issueHeat": min(1.0, open_issue_count / 5.0) if issue_count else 0.0,
            "recentSummary": issues[0]["summary"] if issues else None,
            "blastRadius": 0,
        }
        component_state = _ComponentState(component_data, issues, signals)
        component_state.data["issues"] = issues
        component_state.data["signals"] = signals
        return component_state

    def _flatten_doc_issues(self, components: Iterable[_ComponentState]) -> List[Dict[str, Any]]:
        doc_issues: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for component in components:
            for issue in component.issues:
                issue_id = issue.get("id")
                if not issue_id or issue_id in seen:
                    continue
                seen.add(issue_id)
                doc_issues.append(issue)
        return doc_issues

    def _flatten_signals(self, components: Iterable[_ComponentState]) -> List[Dict[str, Any]]:
        signals: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for component in components:
            for signal in component.signals:
                signal_id = signal.get("id")
                if not signal_id or signal_id in seen:
                    continue
                seen.add(signal_id)
                signals.append(signal)
        return signals

    def _build_metrics_payload(
        self,
        components: Sequence[Dict[str, Any]],
        issue_totals: Dict[str, int],
        issue_timeline: Sequence[Dict[str, Any]],
        resolution_stats: Dict[str, Optional[float]],
        previous_components: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        component_count = max(len(components), 1)
        drift_index = sum(component.get("driftScore", 0.0) for component in components) / component_count
        drift_index = round(drift_index, 2)

        previous_index = None
        if previous_components:
            prev_count = max(len(previous_components), 1)
            previous_index = sum(component.get("driftScore", 0.0) for component in previous_components) / prev_count
            previous_index = round(previous_index, 2)

        delta = None
        if previous_index is not None:
            delta = round(drift_index - previous_index, 2)

        red_zone_components = sum(
            1
            for component in components
            if component.get("driftScore", 0.0) >= 60 and component.get("blastRadius", 0) >= 2
        )

        coverage_counts = defaultdict(int)
        for component in components:
            coverage_counts[component["docCoverage"]["state"]] += 1

        overdue_components = count_overdue_components(components)

        on_track_components = len(components) - overdue_components

        risk_quadrant = [
            {
                "componentId": component["id"],
                "componentName": component["name"],
                "driftScore": component.get("driftScore", 0.0),
                "changeVelocity": component.get("changeVelocity", 0.0),
                "blastRadius": component.get("blastRadius", 0),
            }
            for component in components
        ]

        top_risks = sorted(
            components,
            key=lambda item: (
                item.get("driftScore", 0.0) * 0.6
                + item.get("supportPressure", 0.0) * 10
                + item.get("blastRadius", 0) * 3
            ),
            reverse=True,
        )[:8]
        top_risk_payload = [
            {
                "componentId": comp["id"],
                "componentName": comp["name"],
                "driftScore": comp.get("driftScore", 0.0),
                "changeVelocity": comp.get("changeVelocity", 0.0),
                "supportPressure": comp.get("supportPressure", 0.0),
                "blastRadius": comp.get("blastRadius", 0),
                "riskScore": round(
                    comp.get("driftScore", 0.0) * 0.6
                    + comp.get("supportPressure", 0.0) * 10
                    + comp.get("blastRadius", 0) * 3,
                    2,
                ),
            }
            for comp in top_risks
        ]

        source_mix = {
            "git": round(sum(comp["signalMix"]["git"] for comp in components), 2),
            "slack": round(sum(comp["signalMix"]["slack"] for comp in components), 2),
            "tickets": round(sum(comp["signalMix"]["tickets"] for comp in components), 2),
            "support": round(sum(comp["signalMix"]["support"] for comp in components), 2),
        }

        volatility = sorted(
            components,
            key=lambda comp: comp.get("changeVelocity", 0.0) * comp.get("blastRadius", 0),
            reverse=True,
        )[:5]
        volatility_payload = [
            {
                "componentId": comp["id"],
                "componentName": comp["name"],
                "changeVelocity": comp.get("changeVelocity", 0.0),
                "blastRadius": comp.get("blastRadius", 0),
            }
            for comp in volatility
        ]

        mttr_hours = resolution_stats.get("mttr_hours")

        summary = f"{issue_totals.get('critical_open', 0)} critical doc issues open; {red_zone_components} components in red."
        kpis = build_graph_kpis(
            components,
            previous_components=previous_components,
        )

        return {
            "docDriftIndex": drift_index,
            "docDriftChange": delta,
            "openDocIssues": issue_totals.get("open", 0),
            "criticalDocIssues": issue_totals.get("critical_open", 0),
            "redZoneComponents": red_zone_components,
            "summary": summary,
            "riskQuadrant": risk_quadrant,
            "topRisks": top_risk_payload,
            "sourceMix": source_mix,
            "issueTimeline": issue_timeline,
            "coverage": coverage_counts,
            "sla": {"overdue": overdue_components, "onTrack": on_track_components},
            "volatility": volatility_payload,
            "mttrHours": mttr_hours,
            "kpis": kpis,
        }

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _doc_coverage_state(doc_count: int) -> str:
        if doc_count >= 2:
            return "good"
        if doc_count == 1:
            return "partial"
        return "missing"

    @staticmethod
    def _normalize_issue_list(component_id: str, issues: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for issue in issues:
            issue_id = issue.get("id")
            if not issue_id:
                continue
            normalized.append(
                {
                    "id": issue_id,
                    "componentId": component_id,
                    "docId": issue.get("doc_id"),
                    "docTitle": issue.get("doc_title"),
                    "docUrl": issue.get("doc_url"),
                    "severity": (issue.get("severity") or "medium").lower(),
                    "state": (issue.get("state") or "open").lower(),
                    "summary": issue.get("summary"),
                    "updatedAt": issue.get("updated_at"),
                    "createdAt": issue.get("created_at"),
                    "source": issue.get("source"),
                    "linkedChange": issue.get("linked_change"),
                    "ageDays": _days_between(issue.get("created_at")),
                }
            )
        return normalized

    @staticmethod
    def _normalize_signals(
        component_id: str,
        activity_signals: Sequence[Dict[str, Any]],
        support_signals: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for signal in list(activity_signals) + list(support_signals):
            if not signal:
                continue
            source = (signal.get("source") or "slack").lower()
            if source not in {"slack", "tickets", "support"}:
                source = "slack"
            normalized.append(
                {
                    "id": signal.get("id"),
                    "componentId": component_id,
                    "source": source,
                    "title": signal.get("title") or signal.get("summary"),
                    "summary": signal.get("summary"),
                    "weight": round(float(signal.get("weight", 0.0) or 0.0), 4),
                    "lastSeen": signal.get("last_seen"),
                }
            )
        return normalized

    @staticmethod
    def _edge_weight(source: Dict[str, Any], target: Dict[str, Any]) -> float:
        source_activity = source.get("activityScore", 0.0)
        target_drift = target.get("driftScore", 0.0)
        weight = (source_activity * 0.4 + target_drift * 0.6) / 10.0
        return round(max(weight, 0.1), 2)


__all__ = ["GraphDashboardService"]

