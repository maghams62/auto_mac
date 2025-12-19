from fastapi.testclient import TestClient

import api_server


class FakeBrainGraphService:
    def __init__(self):
        self.calls = []

    def get_graph_explorer_snapshot(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "nodes": [
                {"id": "component:1", "label": "Component", "title": "Billing Component", "props": {}, "x": 0.1, "y": 0.2}
            ],
            "edges": [],
            "filters": kwargs,
            "generatedAt": "2025-01-01T00:00:00Z",
            "meta": {
                "nodeLabelCounts": {"Component": 1},
                "relTypeCounts": {},
                "propertyKeys": [],
                "modalityCounts": {"component": 1},
                "missingTimestampLabels": [],
                "minTimestamp": None,
                "maxTimestamp": None,
            },
        }


def test_brain_universe_filters(monkeypatch):
    fake_service = FakeBrainGraphService()
    monkeypatch.setattr(api_server, "graph_dashboard_service", fake_service)
    client = TestClient(api_server.app, raise_server_exceptions=False)

    response = client.get(
        "/api/brain/universe",
        params={
            "mode": "issue",
            "rootId": "doc-123",
            "modalities": ["slack", "git"],
            "from": "2025-01-01T00:00:00",
            "to": "2025-01-05T00:00:00",
            "snapshotAt": "2025-01-06T00:00:00",
            "depth": 3,
            "limit": 300,
            "projectId": "core-api",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["nodes"][0]["id"] == "component:1"
    assert payload["meta"]["nodeLabelCounts"]["Component"] == 1
    assert len(fake_service.calls) == 1
    call = fake_service.calls[0]
    assert call["mode"] == "issue"
    assert call["root_id"] == "doc-123"
    assert call["modalities"] == ["slack", "git"]
    assert call["snapshot_at"] == "2025-01-06T00:00:00"
    assert call["depth"] == 3
    assert call["limit"] == 300
    assert call["project_id"] == "core-api"


def test_brain_universe_accepts_neo4j_default_mode(monkeypatch):
    fake_service = FakeBrainGraphService()
    monkeypatch.setattr(api_server, "graph_dashboard_service", fake_service)
    client = TestClient(api_server.app, raise_server_exceptions=False)

    response = client.get("/api/brain/universe", params={"mode": "neo4j_default", "limit": 150})
    assert response.status_code == 200
    assert fake_service.calls, "Expected get_graph_explorer_snapshot to be called"
    assert fake_service.calls[0]["mode"] == "neo4j_default"
    assert fake_service.calls[0]["limit"] == 150


def test_about_component_relationships_uses_dashboard_service(monkeypatch):
    class FakeRelationshipsService:
        def __init__(self):
            self.calls = []

        def get_about_component_relationships(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "nodes": [],
                "edges": [],
                "filters": kwargs,
                "generatedAt": "2025-01-01T00:00:00Z",
                "meta": {"nodeLabelCounts": {}, "relTypeCounts": {}, "propertyKeys": [], "modalityCounts": {}, "missingTimestampLabels": []},
            }

    fake_service = FakeRelationshipsService()
    monkeypatch.setattr(api_server, "graph_dashboard_service", fake_service)
    client = TestClient(api_server.app, raise_server_exceptions=False)

    response = client.get("/api/graph/relationships/about-component", params={"componentId": ["comp:core-api"]})
    assert response.status_code == 200
    assert fake_service.calls, "Expected get_about_component_relationships to be invoked"


def test_about_component_relationships_accepts_large_limit(monkeypatch):
    class FakeService:
        def __init__(self):
            self.calls = []

        def get_about_component_relationships(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "nodes": [],
                "edges": [],
                "filters": kwargs,
                "generatedAt": "2025-01-01T00:00:00Z",
                "meta": {"nodeLabelCounts": {}, "relTypeCounts": {}, "propertyKeys": [], "modalityCounts": {}, "missingTimestampLabels": []},
            }

    fake_service = FakeService()
    monkeypatch.setattr(api_server, "graph_dashboard_service", fake_service)
    client = TestClient(api_server.app, raise_server_exceptions=False)

    response = client.get("/api/graph/relationships/about-component", params={"limit": 600})
    assert response.status_code == 200
    assert fake_service.calls, "Expected get_about_component_relationships to be invoked"
    assert fake_service.calls[0]["limit"] == 600


def test_neo4j_default_endpoint_matches_raw_counts(monkeypatch):
    class ParityAwareService(FakeBrainGraphService):
        def __init__(self):
            super().__init__()
            self.expected_nodes = [
                {"id": "repo:core", "label": "Repository", "title": "repo-core", "props": {}, "x": 0.3, "y": -0.1},
                {"id": "comp:core", "label": "Component", "title": "Core API", "props": {}, "x": -0.2, "y": 0.4},
                {"id": "comp:billing", "label": "Component", "title": "Billing", "props": {}, "x": 0.5, "y": 0.4},
            ]
            self.expected_edges = [
                {"id": "edge:repo->core", "source": "repo:core", "target": "comp:core", "type": "HAS_COMPONENT", "props": {}},
                {"id": "edge:cross-repo", "source": "repo:core", "target": "comp:billing", "type": "DEPENDS_ON", "props": {}},
            ]

        def get_graph_explorer_snapshot(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "nodes": self.expected_nodes,
                "edges": self.expected_edges,
                "filters": kwargs,
                "generatedAt": "2025-01-01T00:00:00Z",
                "meta": {
                    "nodeLabelCounts": {"Repository": 1, "Component": 2},
                    "relTypeCounts": {"HAS_COMPONENT": 1, "DEPENDS_ON": 1},
                    "propertyKeys": [],
                    "modalityCounts": {"repo": 1, "component": 2},
                    "missingTimestampLabels": [],
                    "minTimestamp": None,
                    "maxTimestamp": None,
                },
            }

        def run_raw_match_query(self, limit: int):
            return self.expected_nodes[:limit], self.expected_edges[:limit]

    fake_service = ParityAwareService()
    monkeypatch.setattr(api_server, "graph_dashboard_service", fake_service)
    client = TestClient(api_server.app, raise_server_exceptions=False)

    response = client.get("/api/brain/universe/default", params={"limit": 200, "modalities": ["repo", "component"]})
    assert response.status_code == 200
    payload = response.json()
    raw_nodes, raw_edges = fake_service.run_raw_match_query(limit=200)
    assert len(payload["nodes"]) == len(raw_nodes)
    assert len(payload["edges"]) == len(raw_edges)
    assert fake_service.calls[0]["mode"] == "neo4j_default"

