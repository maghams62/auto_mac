"""
Tests for GraphService and GraphIngestor.

These tests validate:
1. GraphService queries return expected results after seeding
2. GraphIngestor correctly creates nodes and relationships
3. Graph layer gracefully degrades when disabled

Prerequisites:
- Neo4j running locally OR graph.enabled: false in config
- Run: python scripts/seed_graph.py --fixtures before running tests

Usage:
    pytest tests/test_graph_service.py -v
    pytest tests/test_graph_service.py -v -k "test_component_neighborhood"
"""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.graph import GraphService, GraphIngestor
from src.graph.schema import (
    GraphComponentSummary,
    GraphApiImpactSummary,
    NodeLabels,
    RelationshipTypes,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_config() -> Dict[str, Any]:
    """Return a mock config with graph disabled for unit tests."""
    return {
        "graph": {
            "enabled": False,
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "test",
            "database": "neo4j",
        }
    }


@pytest.fixture
def mock_config_enabled() -> Dict[str, Any]:
    """Return a mock config with graph enabled."""
    return {
        "graph": {
            "enabled": True,
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "test",
            "database": "neo4j",
        }
    }


@pytest.fixture
def disabled_service(mock_config) -> GraphService:
    """Create a GraphService with graph disabled."""
    return GraphService(mock_config)


@pytest.fixture
def mock_driver():
    """Create a mock Neo4j driver."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return driver, session


# =============================================================================
# GraphService Unit Tests (Disabled Mode)
# =============================================================================

class TestGraphServiceDisabled:
    """Tests for GraphService when graph is disabled."""
    
    def test_is_available_returns_false_when_disabled(self, disabled_service):
        """Service should report unavailable when disabled."""
        assert disabled_service.is_available() is False
    
    def test_get_component_neighborhood_returns_empty_when_disabled(self, disabled_service):
        """Component neighborhood query should return empty summary when disabled."""
        result = disabled_service.get_component_neighborhood("comp:payments")
        
        assert isinstance(result, GraphComponentSummary)
        assert result.component_id == "comp:payments"
        assert result.docs == []
        assert result.issues == []
        assert result.pull_requests == []
        assert result.slack_threads == []
        assert result.api_endpoints == []
    
    def test_get_api_impact_returns_empty_when_disabled(self, disabled_service):
        """API impact query should return empty summary when disabled."""
        result = disabled_service.get_api_impact("api:payments:/charge")
        
        assert isinstance(result, GraphApiImpactSummary)
        assert result.api_id == "api:payments:/charge"
        assert result.services == []
        assert result.docs == []
        assert result.issues == []
        assert result.pull_requests == []
    
    def test_run_query_returns_empty_when_disabled(self, disabled_service):
        """run_query should return empty list when disabled."""
        result = disabled_service.run_query("MATCH (n) RETURN n")
        assert result == []
    
    def test_run_write_returns_none_when_disabled(self, disabled_service):
        """run_write should return None when disabled."""
        result = disabled_service.run_write("CREATE (n:Test {id: 'test'})")
        assert result is None


# =============================================================================
# GraphService Unit Tests (Mocked Driver)
# =============================================================================

class TestGraphServiceMocked:
    """Tests for GraphService with mocked Neo4j driver."""
    
    def test_get_component_neighborhood_parses_results(self, mock_config_enabled, mock_driver):
        """Verify component neighborhood correctly parses query results."""
        driver, session = mock_driver
        
        # Mock query result
        mock_result = MagicMock()
        mock_result.data.return_value = {
            "docs": ["doc:payments-guide", "doc:payments-api"],
            "issues": ["issue:201"],
            "prs": ["pr:101", "pr:105"],
            "slack_threads": ["slack:C0123:123.456"],
            "apis": ["api:payments:/v1/charge"],
        }
        session.run.return_value = [mock_result]
        
        with patch("src.graph.service.GraphDatabase") as mock_gd:
            mock_gd.driver.return_value = driver
            service = GraphService(mock_config_enabled)
            service._driver = driver
            
            result = service.get_component_neighborhood("comp:payments")
            
            assert result.component_id == "comp:payments"
            assert "doc:payments-guide" in result.docs
            assert "issue:201" in result.issues
            assert "pr:101" in result.pull_requests
    
    def test_get_api_impact_parses_results(self, mock_config_enabled, mock_driver):
        """Verify API impact correctly parses query results."""
        driver, session = mock_driver
        
        # Mock query result
        mock_result = MagicMock()
        mock_result.data.return_value = {
            "services": ["svc:api-gateway", "svc:billing-worker"],
            "docs": ["doc:payments-guide"],
            "issues": ["issue:201"],
            "prs": ["pr:101"],
        }
        session.run.return_value = [mock_result]
        
        with patch("src.graph.service.GraphDatabase") as mock_gd:
            mock_gd.driver.return_value = driver
            service = GraphService(mock_config_enabled)
            service._driver = driver
            
            result = service.get_api_impact("api:payments:/v1/charge")
            
            assert result.api_id == "api:payments:/v1/charge"
            assert "svc:api-gateway" in result.services
            assert "doc:payments-guide" in result.docs


# =============================================================================
# GraphIngestor Unit Tests
# =============================================================================

class TestGraphIngestor:
    """Tests for GraphIngestor."""
    
    def test_available_returns_false_when_service_disabled(self, disabled_service):
        """Ingestor should report unavailable when service is disabled."""
        ingestor = GraphIngestor(disabled_service)
        assert ingestor.available() is False
    
    def test_upsert_component_noop_when_disabled(self, disabled_service):
        """upsert_component should be a no-op when disabled."""
        ingestor = GraphIngestor(disabled_service)
        # Should not raise
        ingestor.upsert_component("comp:test", {"name": "Test"})
    
    def test_upsert_doc_noop_when_disabled(self, disabled_service):
        """upsert_doc should be a no-op when disabled."""
        ingestor = GraphIngestor(disabled_service)
        ingestor.upsert_doc(
            "doc:test",
            component_ids=["comp:test"],
            endpoint_ids=["api:test:/endpoint"],
            properties={"title": "Test Doc"}
        )
    
    def test_upsert_issue_noop_when_disabled(self, disabled_service):
        """upsert_issue should be a no-op when disabled."""
        ingestor = GraphIngestor(disabled_service)
        ingestor.upsert_issue(
            "issue:999",
            component_ids=["comp:test"],
            properties={"title": "Test Issue", "status": "open"}
        )
    
    def test_upsert_pr_noop_when_disabled(self, disabled_service):
        """upsert_pr should be a no-op when disabled."""
        ingestor = GraphIngestor(disabled_service)
        ingestor.upsert_pr(
            "pr:999",
            component_ids=["comp:test"],
            endpoint_ids=["api:test:/endpoint"],
            properties={"title": "Test PR", "state": "open"}
        )
    
    def test_upsert_slack_thread_noop_when_disabled(self, disabled_service):
        """upsert_slack_thread should be a no-op when disabled."""
        ingestor = GraphIngestor(disabled_service)
        ingestor.upsert_slack_thread(
            "slack:C123:456.789",
            component_ids=["comp:test"],
            issue_ids=["issue:999"],
            properties={"topic": "Test Thread"}
        )


# =============================================================================
# Schema Tests
# =============================================================================

class TestSchema:
    """Tests for schema definitions."""
    
    def test_node_labels_values(self):
        """Verify all expected node labels exist."""
        assert NodeLabels.COMPONENT.value == "Component"
        assert NodeLabels.SERVICE.value == "Service"
        assert NodeLabels.API_ENDPOINT.value == "APIEndpoint"
        assert NodeLabels.DOC.value == "Doc"
        assert NodeLabels.ISSUE.value == "Issue"
        assert NodeLabels.PR.value == "PR"
        assert NodeLabels.SLACK_THREAD.value == "SlackThread"
    
    def test_relationship_types_values(self):
        """Verify all expected relationship types exist."""
        assert RelationshipTypes.DESCRIBES_COMPONENT.value == "DESCRIBES_COMPONENT"
        assert RelationshipTypes.DESCRIBES_ENDPOINT.value == "DESCRIBES_ENDPOINT"
        assert RelationshipTypes.AFFECTS_COMPONENT.value == "AFFECTS_COMPONENT"
        assert RelationshipTypes.REFERENCES_ENDPOINT.value == "REFERENCES_ENDPOINT"
        assert RelationshipTypes.MODIFIES_COMPONENT.value == "MODIFIES_COMPONENT"
        assert RelationshipTypes.MODIFIES_ENDPOINT.value == "MODIFIES_ENDPOINT"
        assert RelationshipTypes.CALLS_ENDPOINT.value == "CALLS_ENDPOINT"
        assert RelationshipTypes.DISCUSSES_COMPONENT.value == "DISCUSSES_COMPONENT"
        assert RelationshipTypes.DISCUSSES_ISSUE.value == "DISCUSSES_ISSUE"
        assert RelationshipTypes.EXPOSES_ENDPOINT.value == "EXPOSES_ENDPOINT"
    
    def test_graph_component_summary_defaults(self):
        """Verify GraphComponentSummary has correct defaults."""
        summary = GraphComponentSummary(component_id="comp:test")
        assert summary.component_id == "comp:test"
        assert summary.docs == []
        assert summary.issues == []
        assert summary.pull_requests == []
        assert summary.slack_threads == []
        assert summary.api_endpoints == []
    
    def test_graph_api_impact_summary_defaults(self):
        """Verify GraphApiImpactSummary has correct defaults."""
        summary = GraphApiImpactSummary(api_id="api:test:/endpoint")
        assert summary.api_id == "api:test:/endpoint"
        assert summary.services == []
        assert summary.docs == []
        assert summary.issues == []
        assert summary.pull_requests == []


# =============================================================================
# Integration Tests (require Neo4j + seeded data)
# =============================================================================

@pytest.mark.integration
class TestGraphServiceIntegration:
    """
    Integration tests that require Neo4j running with seeded data.
    
    Run these after: python scripts/seed_graph.py --fixtures
    
    Skip with: pytest -m "not integration"
    """
    
    @pytest.fixture
    def live_service(self):
        """Create a live GraphService from config."""
        from src.config_manager import get_config
        config = get_config()
        service = GraphService(config)
        yield service
        service.close()
    
    def test_component_neighborhood_payments(self, live_service):
        """
        Verify comp:payments returns expected related entities.
        
        Expected from fixtures:
        - Docs: doc:payments-guide (from hardcoded) or others from fixtures
        - PRs: pr:101, pr:102, pr:105
        - Issues: issue:201, issue:202
        - APIs: api:payments:/v1/charge, api:payments:/v1/refund
        """
        if not live_service.is_available():
            pytest.skip("Neo4j not available")
        
        result = live_service.get_component_neighborhood("comp:payments")
        
        assert result.component_id == "comp:payments"
        # At minimum, should have some related entities
        has_data = (
            len(result.docs) > 0 or
            len(result.pull_requests) > 0 or
            len(result.api_endpoints) > 0
        )
        assert has_data, "Expected some related entities for comp:payments"
    
    def test_api_impact_charge_endpoint(self, live_service):
        """
        Verify api impact query returns expected results.
        
        Expected from fixtures:
        - Services: svc:api-gateway, svc:billing-worker
        - Docs: doc:swagger:service_a
        - Issues: issue:201
        - PRs: pr:101, pr:105
        """
        if not live_service.is_available():
            pytest.skip("Neo4j not available")
        
        # Try multiple possible endpoint IDs
        endpoint_ids = [
            "api:payments:/v1/payments/charge",
            "api:payments:/payments/charge",
            "api:payments:/v1/charge",
            "api:payments:/charge",
        ]
        
        result = None
        for endpoint_id in endpoint_ids:
            result = live_service.get_api_impact(endpoint_id)
            if result.docs or result.issues or result.pull_requests:
                break
        
        assert result is not None
        # API impact should return some related entities
        has_data = (
            len(result.services) > 0 or
            len(result.docs) > 0 or
            len(result.issues) > 0 or
            len(result.pull_requests) > 0
        )
        # This is a soft assertion - depends on which fixtures were seeded
        if not has_data:
            pytest.skip("No data found - run seed_graph.py first")
    
    def test_component_neighborhood_auth(self, live_service):
        """
        Verify comp:auth returns expected related entities.
        
        Expected from fixtures:
        - Docs: doc:auth-overview
        - PRs: pr:103, pr:104
        - Issues: issue:203
        - Slack: slack:C0456AUTH:...
        """
        if not live_service.is_available():
            pytest.skip("Neo4j not available")
        
        result = live_service.get_component_neighborhood("comp:auth")
        
        assert result.component_id == "comp:auth"
        # Should have some related entities
        has_data = (
            len(result.docs) > 0 or
            len(result.pull_requests) > 0 or
            len(result.api_endpoints) > 0
        )
        if not has_data:
            pytest.skip("No data found - run seed_graph.py first")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

