from src.services.context_resolution_service import (
    CONTEXT_IMPACTS_CYPHER_TEMPLATE,
    ContextResolutionService,
)


class _FakeGraphService:
    def __init__(self):
        self._metadata = None

    def is_available(self):
        return True

    def run_query(self, query, params):
        self._metadata = {
            "cypher": query.strip(),
            "params": params,
            "database": "neo4j",
            "row_count": 1,
            "error": None,
        }
        return [
            {
                "component_id": params.get("component_id"),
                "exposed_apis": ["api:test"],
                "dependents": ["comp:dependent"],
                "docs": ["docs/sample.md"],
                "services": ["svc:test"],
            }
        ]

    def last_query_metadata(self):
        return self._metadata


def test_context_impacts_graph_query_payload_matches_constant():
    service = ContextResolutionService(_FakeGraphService(), default_max_depth=2)
    payload = service.resolve_impacts(component_id="docs.payments")
    graph_query = payload["graph_query"]
    assert graph_query["cypher"] == CONTEXT_IMPACTS_CYPHER_TEMPLATE.replace("__DEPTH__", "2").strip()
    assert graph_query["params"] == {"api_id": None, "component_id": "docs.payments"}
    assert graph_query["rowCount"] == 1

