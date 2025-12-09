import os

from src.config_manager import ConfigManager
from src.graph.dashboard_service import GraphDashboardService


def test_brain_universe_fixture_snapshot(monkeypatch):
    monkeypatch.setenv("BRAIN_GRAPH_FIXTURE", "deterministic")
    service = GraphDashboardService(ConfigManager())
    snapshot = service.get_graph_explorer_snapshot()

    nodes = snapshot.get("nodes", [])
    edges = snapshot.get("edges", [])
    meta = snapshot.get("meta", {})

    assert len(nodes) == 4
    assert len(edges) == 2
    assert meta.get("nodeLabelCounts", {}).get("Component") == 2
    assert meta.get("modalityCounts", {}).get("slack") == 1
    assert meta.get("modalityCounts", {}).get("git") == 1


def test_brain_universe_empty_fixture(monkeypatch):
    monkeypatch.setenv("BRAIN_GRAPH_FIXTURE", "empty")
    service = GraphDashboardService(ConfigManager())
    snapshot = service.get_graph_explorer_snapshot()

    assert snapshot.get("nodes") == []
    assert snapshot.get("edges") == []
    assert snapshot.get("meta", {}).get("nodeLabelCounts") == {}


def test_brain_universe_fixture_modalities(monkeypatch):
    monkeypatch.setenv("BRAIN_GRAPH_FIXTURE", "deterministic")
    service = GraphDashboardService(ConfigManager())
    snapshot = service.get_graph_explorer_snapshot(modalities=["slack"])

    nodes = snapshot.get("nodes", [])
    ids = {node["id"] for node in nodes}

    assert "slack:core-api:msg1" in ids
    assert "comp:core-api" in ids  # neighbor preserved for context
    assert "git:billing:commit1" not in ids


def test_brain_universe_fixture_snapshot_at(monkeypatch):
    monkeypatch.setenv("BRAIN_GRAPH_FIXTURE", "deterministic")
    service = GraphDashboardService(ConfigManager())
    snapshot = service.get_graph_explorer_snapshot(snapshot_at="2025-01-01T12:00:00Z")

    ids = {node["id"] for node in snapshot.get("nodes", [])}

    assert "git:billing:commit1" not in ids
    assert "slack:core-api:msg1" in ids

