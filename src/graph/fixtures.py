"""
Deterministic graph fixtures used by automated UI/Playwright tests.

These fixtures let us return a known, tiny graph snapshot without relying on a
live Neo4j instance. They are activated via the BRAIN_GRAPH_FIXTURE env var:

- BRAIN_GRAPH_FIXTURE=deterministic  -> returns the tiny 2-component graph
- BRAIN_GRAPH_FIXTURE=empty          -> returns an empty graph payload
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from datetime import datetime, timezone


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _compute_meta(nodes: Sequence[Dict[str, Any]], edges: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    label_counts: Dict[str, int] = {}
    modality_counts: Dict[str, int] = {}
    rel_type_counts: Dict[str, int] = {}
    property_keys = set()
    timestamps: List[datetime] = []
    for node in nodes:
        label = node.get("label")
        if label:
            label_counts[label] = label_counts.get(label, 0) + 1
        modality = node.get("modality")
        if modality:
            modality_counts[modality] = modality_counts.get(modality, 0) + 1
        props = node.get("props") or {}
        property_keys.update(props.keys())
        created = _parse_iso(props.get("created_at") or props.get("timestamp"))
        if created:
            timestamps.append(created)
    for edge in edges:
        etype = edge.get("type")
        if etype:
            rel_type_counts[etype] = rel_type_counts.get(etype, 0) + 1

    min_timestamp: Optional[str] = None
    max_timestamp: Optional[str] = None
    if timestamps:
        timestamps.sort()
        min_timestamp = timestamps[0].astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        max_timestamp = timestamps[-1].astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "nodeLabelCounts": label_counts,
        "relTypeCounts": rel_type_counts,
        "propertyKeys": sorted(property_keys),
        "modalityCounts": modality_counts,
        "missingTimestampLabels": [],
        "minTimestamp": min_timestamp,
        "maxTimestamp": max_timestamp,
    }


_FIXTURE_NODES: Tuple[Dict[str, Any], ...] = (
    {
        "id": "comp:core-api",
        "label": "Component",
        "title": "Core API",
        "modality": "component",
        "props": {
            "name": "core-api",
            "project_id": "project_atlas",
            "created_at": "2024-12-01T00:00:00Z",
            "timestamp": "2024-12-01T00:00:00Z",
        },
    },
    {
        "id": "comp:billing-service",
        "label": "Component",
        "title": "Billing Service",
        "modality": "component",
        "props": {
            "name": "billing-service",
            "project_id": "project_atlas",
            "created_at": "2024-12-01T00:00:00Z",
            "timestamp": "2024-12-01T00:00:00Z",
        },
    },
    {
        "id": "slack:core-api:msg1",
        "label": "SlackEvent",
        "title": "Slack: Core API outage",
        "modality": "slack",
        "props": {
            "channel": "#eng-core",
            "text": "Core API latency spike",
            "project_id": "project_atlas",
            "created_at": "2025-01-01T06:15:00Z",
            "timestamp": "2025-01-01T06:15:00Z",
        },
    },
    {
        "id": "git:billing:commit1",
        "label": "GitEvent",
        "title": "Git: billing fix",
        "modality": "git",
        "props": {
            "repo": "billing-service",
            "message": "Fix invoice rounding",
            "project_id": "project_atlas",
            "created_at": "2025-01-01T18:45:00Z",
            "timestamp": "2025-01-01T18:45:00Z",
        },
    },
    {
        "id": "repo:core-api",
        "label": "Repository",
        "title": "repo-core-api",
        "modality": "repo",
        "props": {
            "name": "core-api",
            "project_id": "project_atlas",
            "created_at": "2024-11-15T00:00:00Z",
            "timestamp": "2024-11-15T00:00:00Z",
        },
    },
    {
        "id": "repo:billing-service",
        "label": "Repository",
        "title": "repo-billing-service",
        "modality": "repo",
        "props": {
            "name": "billing-service",
            "project_id": "project_atlas",
            "created_at": "2024-11-16T00:00:00Z",
            "timestamp": "2024-11-16T00:00:00Z",
        },
    },
)

_FIXTURE_EDGES: Tuple[Dict[str, Any], ...] = (
    {
        "id": "edge:slack-msg1->core-api",
        "source": "slack:core-api:msg1",
        "target": "comp:core-api",
        "type": "SIGNALS_COMPONENT",
        "props": {},
    },
    {
        "id": "edge:git-commit1->billing",
        "source": "git:billing:commit1",
        "target": "comp:billing-service",
        "type": "SIGNALS_COMPONENT",
        "props": {},
    },
    {
        "id": "edge:repo-core->comp-core",
        "source": "repo:core-api",
        "target": "comp:core-api",
        "type": "HAS_COMPONENT",
        "props": {},
    },
    {
        "id": "edge:repo-billing->comp-billing",
        "source": "repo:billing-service",
        "target": "comp:billing-service",
        "type": "HAS_COMPONENT",
        "props": {},
    },
    {
        "id": "edge:repo-core->repo-billing",
        "source": "repo:core-api",
        "target": "repo:billing-service",
        "type": "DEPENDS_ON",
        "props": {},
    },
)

def _clone_nodes(nodes: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cloned: List[Dict[str, Any]] = []
    for node in nodes:
        props = dict(node.get("props") or {})
        cloned.append({**node, "props": props})
    return cloned


def _clone_edges(edges: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(edge) for edge in edges]


def _filter_by_modalities(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], modalities: Optional[Sequence[str]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not modalities:
        return nodes, edges
    modality_set = {value.lower() for value in modalities if value}
    if not modality_set:
        return nodes, edges

    selected_ids = {node["id"] for node in nodes if (node.get("modality") or node.get("label", "")).lower() in modality_set}
    if not selected_ids:
        return [], []

    neighbor_ids: set[str] = set()
    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src in selected_ids:
            neighbor_ids.add(tgt)
        if tgt in selected_ids:
            neighbor_ids.add(src)

    keep_ids = selected_ids | neighbor_ids
    filtered_nodes = [node for node in nodes if node["id"] in keep_ids]
    filtered_edges = [edge for edge in edges if edge.get("source") in keep_ids and edge.get("target") in keep_ids]
    return filtered_nodes, filtered_edges


def _filter_by_snapshot(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], snapshot_at: Optional[str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    snapshot_dt = _parse_iso(snapshot_at)
    if not snapshot_dt:
        return nodes, edges
    keep_ids: set[str] = set()
    for node in nodes:
        props = node.get("props") or {}
        timestamp = _parse_iso(props.get("timestamp") or props.get("created_at"))
        if not timestamp or timestamp <= snapshot_dt or node.get("label") == "Component":
            keep_ids.add(node["id"])
    filtered_nodes = [node for node in nodes if node["id"] in keep_ids]
    filtered_edges = [edge for edge in edges if edge.get("source") in keep_ids and edge.get("target") in keep_ids]
    return filtered_nodes, filtered_edges


def fixture_graph_payload(
    *,
    modalities: Optional[Sequence[str]] = None,
    snapshot_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Two components + slack/git signals with deterministic IDs."""
    nodes = _clone_nodes(_FIXTURE_NODES)
    edges = _clone_edges(_FIXTURE_EDGES)
    nodes, edges = _filter_by_modalities(nodes, edges, modalities)
    nodes, edges = _filter_by_snapshot(nodes, edges, snapshot_at)
    meta = _compute_meta(nodes, edges)
    return {
        "generatedAt": "2025-01-02T00:00:00Z",
        "nodes": nodes,
        "edges": edges,
        "filters": {
            "mode": "universe",
            "limit": 600,
            "modalities": modalities or [],
            "snapshotAt": snapshot_at,
        },
        "meta": meta,
    }


def empty_graph_payload() -> Dict[str, Any]:
    return {
        "generatedAt": "2025-01-01T00:00:00Z",
        "nodes": [],
        "edges": [],
        "filters": {"mode": "universe", "limit": 600},
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


