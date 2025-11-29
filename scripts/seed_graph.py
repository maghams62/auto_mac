#!/usr/bin/env python3
"""
Neo4j Graph Seed Script - Phase 2

This script seeds Neo4j with graph data from either:
1. YAML fixtures (tests/fixtures/graph/) - use --fixtures flag
2. OpenAPI specs (tests/fixtures/swagger/) - use --swagger flag
3. Hardcoded sample data (default)

Usage:
    python scripts/seed_graph.py                    # Hardcoded sample data
    python scripts/seed_graph.py --fixtures         # Load from YAML fixtures
    python scripts/seed_graph.py --swagger          # Load from OpenAPI specs
    python scripts/seed_graph.py --fixtures --swagger  # Both fixtures and swagger

Prerequisites:
    1. Neo4j running locally (or accessible via configured URI)
    2. graph.enabled: true in config.yaml
    3. NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD environment variables set
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config_manager import get_config
from src.graph import GraphService, GraphIngestor

# Fixture paths
FIXTURES_DIR = project_root / "tests" / "fixtures" / "graph"
SWAGGER_DIR = project_root / "tests" / "fixtures" / "swagger"


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


# =============================================================================
# Fixture Loading Functions
# =============================================================================

def load_yaml_file(path: Path) -> Dict[str, Any]:
    """Load a YAML file and return its contents."""
    if not path.exists():
        print(f"  ⚠️  File not found: {path}")
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def load_fixtures() -> Dict[str, List[Dict]]:
    """
    Load all YAML fixtures from tests/fixtures/graph/.
    
    Returns:
        Dictionary with keys: components, services, pull_requests, issues, slack_threads
    """
    fixtures = {}
    
    # Load each fixture file
    files = {
        "components": FIXTURES_DIR / "components.yaml",
        "services": FIXTURES_DIR / "services.yaml",
        "pull_requests": FIXTURES_DIR / "commits_prs.yaml",
        "issues": FIXTURES_DIR / "issues.yaml",
        "slack_threads": FIXTURES_DIR / "slack_threads.yaml",
    }
    
    for key, path in files.items():
        data = load_yaml_file(path)
        # Handle both top-level list and nested structure
        if key in data:
            fixtures[key] = data[key]
        elif isinstance(data, list):
            fixtures[key] = data
        else:
            fixtures[key] = []
    
    return fixtures


def seed_from_fixtures(ingestor: GraphIngestor, fixtures: Dict[str, List[Dict]]) -> Dict[str, int]:
    """
    Seed graph from loaded fixtures.
    
    Returns:
        Dictionary with counts of seeded entities per type.
    """
    counts = {
        "components": 0,
        "services": 0,
        "api_endpoints": 0,
        "docs": 0,
        "issues": 0,
        "pull_requests": 0,
        "slack_threads": 0,
    }
    
    # Seed components
    for comp in fixtures.get("components", []):
        ingestor.upsert_component(
            comp["id"],
            properties={k: v for k, v in comp.items() if k not in ("id", "tags")}
        )
        counts["components"] += 1
    
    # Seed services and their endpoint relationships
    for svc in fixtures.get("services", []):
        ingestor.upsert_service(
            svc["id"],
            properties={k: v for k, v in svc.items() if k not in ("id", "calls_endpoints")}
        )
        counts["services"] += 1
        
        # Create CALLS_ENDPOINT relationships
        for endpoint_id in svc.get("calls_endpoints", []):
            # First ensure the endpoint exists (will be created if not)
            ingestor.upsert_api_endpoint(endpoint_id)
            # Then create the relationship via direct query
            if ingestor.graph_service.is_available():
                query = """
                MERGE (svc:Service {id: $svc_id})
                MERGE (api:APIEndpoint {id: $api_id})
                MERGE (svc)-[:CALLS_ENDPOINT]->(api)
                """
                ingestor.graph_service.run_write(query, {"svc_id": svc["id"], "api_id": endpoint_id})
    
    # Seed pull requests
    for pr in fixtures.get("pull_requests", []):
        ingestor.upsert_pr(
            pr["id"],
            component_ids=pr.get("component_ids", []),
            endpoint_ids=pr.get("endpoint_ids", []),
            properties={
                k: str(v) for k, v in pr.items()
                if k not in ("id", "component_ids", "endpoint_ids", "files_changed")
            }
        )
        counts["pull_requests"] += 1
    
    # Seed issues
    for issue in fixtures.get("issues", []):
        ingestor.upsert_issue(
            issue["id"],
            component_ids=issue.get("component_ids", []),
            endpoint_ids=issue.get("endpoint_ids", []),
            properties={
                k: str(v) for k, v in issue.items()
                if k not in ("id", "component_ids", "endpoint_ids")
            }
        )
        counts["issues"] += 1
    
    # Seed slack threads
    for thread in fixtures.get("slack_threads", []):
        ingestor.upsert_slack_thread(
            thread["id"],
            component_ids=thread.get("component_ids", []),
            issue_ids=thread.get("issue_ids", []),
            properties={
                k: str(v) if not isinstance(v, list) else ",".join(v)
                for k, v in thread.items()
                if k not in ("id", "component_ids", "issue_ids")
            }
        )
        counts["slack_threads"] += 1
    
    return counts


# =============================================================================
# OpenAPI/Swagger Parsing Functions
# =============================================================================

def parse_openapi_spec(spec_path: Path) -> Dict[str, Any]:
    """
    Parse an OpenAPI spec file and extract API endpoints.
    
    Returns:
        Dictionary with service_id, component_id, and list of endpoints.
    """
    spec = load_yaml_file(spec_path)
    if not spec:
        return {"endpoints": []}
    
    info = spec.get("info", {})
    service_id = info.get("x-service", f"svc:{spec_path.stem}")
    component_id = info.get("x-component", f"comp:{spec_path.stem}")
    version = info.get("version", "1.0.0")
    
    endpoints = []
    paths = spec.get("paths", {})
    
    for path, methods in paths.items():
        for method, details in methods.items():
            if method in ("get", "post", "put", "patch", "delete"):
                endpoint_id = f"api:{component_id.replace('comp:', '')}:{path}"
                endpoints.append({
                    "id": endpoint_id,
                    "method": method.upper(),
                    "path": path,
                    "operation_id": details.get("operationId", ""),
                    "summary": details.get("summary", ""),
                    "component_id": details.get("x-component", component_id),
                    "version": version,
                })
    
    return {
        "service_id": service_id,
        "component_id": component_id,
        "version": version,
        "title": info.get("title", "Unknown Service"),
        "endpoints": endpoints,
        "spec_path": str(spec_path),
    }


def seed_from_swagger(ingestor: GraphIngestor, spec_path: Path) -> Dict[str, int]:
    """
    Seed graph from an OpenAPI spec file.
    
    Returns:
        Dictionary with counts of seeded entities.
    """
    counts = {"services": 0, "components": 0, "api_endpoints": 0, "docs": 0}
    
    parsed = parse_openapi_spec(spec_path)
    if not parsed.get("endpoints"):
        return counts
    
    # Create service node
    ingestor.upsert_service(
        parsed["service_id"],
        properties={"name": parsed["title"], "version": parsed["version"]}
    )
    counts["services"] += 1
    
    # Ensure component exists
    ingestor.upsert_component(
        parsed["component_id"],
        properties={"name": parsed["component_id"].replace("comp:", "").title()}
    )
    counts["components"] += 1
    
    # Create API endpoint nodes
    for endpoint in parsed["endpoints"]:
        ingestor.upsert_api_endpoint(
            endpoint["id"],
            component_id=endpoint["component_id"],
            properties={
                "method": endpoint["method"],
                "path": endpoint["path"],
                "operation_id": endpoint["operation_id"],
                "summary": endpoint["summary"],
                "version": endpoint["version"],
            }
        )
        counts["api_endpoints"] += 1
        
        # Create service -> endpoint relationship
        if ingestor.graph_service.is_available():
            query = """
            MERGE (svc:Service {id: $svc_id})
            MERGE (api:APIEndpoint {id: $api_id})
            MERGE (svc)-[:CALLS_ENDPOINT]->(api)
            """
            ingestor.graph_service.run_write(
                query,
                {"svc_id": parsed["service_id"], "api_id": endpoint["id"]}
            )
    
    # Create a Doc node for the spec itself
    doc_id = f"doc:swagger:{spec_path.stem}"
    endpoint_ids = [e["id"] for e in parsed["endpoints"]]
    ingestor.upsert_doc(
        doc_id,
        component_ids=[parsed["component_id"]],
        endpoint_ids=endpoint_ids,
        properties={
            "title": f"{parsed['title']} OpenAPI Spec",
            "url": parsed["spec_path"],
            "version": parsed["version"],
            "type": "openapi",
        }
    )
    counts["docs"] += 1
    
    return counts


def seed_all_swagger_specs(ingestor: GraphIngestor) -> Dict[str, int]:
    """
    Seed graph from all OpenAPI specs in tests/fixtures/swagger/.
    
    Returns:
        Aggregated counts of seeded entities.
    """
    total_counts = {"services": 0, "components": 0, "api_endpoints": 0, "docs": 0}
    
    if not SWAGGER_DIR.exists():
        print(f"  ⚠️  Swagger directory not found: {SWAGGER_DIR}")
        return total_counts
    
    spec_files = list(SWAGGER_DIR.glob("*.yaml")) + list(SWAGGER_DIR.glob("*.yml"))
    
    for spec_path in spec_files:
        print(f"  Processing: {spec_path.name}")
        counts = seed_from_swagger(ingestor, spec_path)
        for key, value in counts.items():
            total_counts[key] += value
    
    return total_counts


# =============================================================================
# Legacy Hardcoded Sample Data (Phase 1 compatibility)
# =============================================================================

def seed_sample_data(ingestor: GraphIngestor) -> None:
    """Seed sample nodes and relationships matching the v1 schema (hardcoded)."""
    
    print_section("Seeding Hardcoded Sample Data")
    
    # --- Components ---
    print("Creating components...")
    ingestor.upsert_component("comp:payments", {"name": "Payments"})
    ingestor.upsert_component("comp:auth", {"name": "Authentication"})
    ingestor.upsert_component("comp:billing", {"name": "Billing"})
    print("  ✓ Created: comp:payments, comp:auth, comp:billing")
    
    # --- Services ---
    print("Creating services...")
    ingestor.upsert_service("svc:billing", {"name": "billing-service"})
    ingestor.upsert_service("svc:gateway", {"name": "api-gateway"})
    ingestor.upsert_service("svc:auth", {"name": "auth-service"})
    print("  ✓ Created: svc:billing, svc:gateway, svc:auth")
    
    # --- API Endpoints ---
    print("Creating API endpoints...")
    ingestor.upsert_api_endpoint(
        "api:payments:/charge",
        component_id="comp:payments",
        properties={"method": "POST", "path": "/v1/payments/charge"}
    )
    ingestor.upsert_api_endpoint(
        "api:payments:/refund",
        component_id="comp:payments",
        properties={"method": "POST", "path": "/v1/payments/refund"}
    )
    ingestor.upsert_api_endpoint(
        "api:auth:/login",
        component_id="comp:auth",
        properties={"method": "POST", "path": "/v1/auth/login"}
    )
    ingestor.upsert_api_endpoint(
        "api:auth:/logout",
        component_id="comp:auth",
        properties={"method": "POST", "path": "/v1/auth/logout"}
    )
    print("  ✓ Created: api:payments:/charge, api:payments:/refund, api:auth:/login, api:auth:/logout")
    
    # --- Documents ---
    print("Creating documents...")
    ingestor.upsert_doc(
        "doc:payments-guide",
        component_ids=["comp:payments"],
        endpoint_ids=["api:payments:/charge", "api:payments:/refund"],
        properties={"title": "Payments Integration Guide", "url": "/docs/payments"}
    )
    ingestor.upsert_doc(
        "doc:auth-overview",
        component_ids=["comp:auth"],
        endpoint_ids=["api:auth:/login"],
        properties={"title": "Authentication Overview", "url": "/docs/auth"}
    )
    print("  ✓ Created: doc:payments-guide, doc:auth-overview")
    
    # --- Issues ---
    print("Creating issues...")
    ingestor.upsert_issue(
        "issue:123",
        component_ids=["comp:payments"],
        endpoint_ids=["api:payments:/charge"],
        properties={"title": "Charge endpoint timeout", "status": "open", "severity": "high"}
    )
    ingestor.upsert_issue(
        "issue:124",
        component_ids=["comp:auth"],
        properties={"title": "Login rate limiting", "status": "closed", "severity": "medium"}
    )
    print("  ✓ Created: issue:123, issue:124")
    
    # --- Pull Requests ---
    print("Creating pull requests...")
    ingestor.upsert_pr(
        "pr:456",
        component_ids=["comp:payments"],
        endpoint_ids=["api:payments:/charge"],
        properties={"title": "Fix charge timeout handling", "state": "merged", "number": "456"}
    )
    ingestor.upsert_pr(
        "pr:457",
        component_ids=["comp:auth", "comp:billing"],
        properties={"title": "Add billing auth integration", "state": "open", "number": "457"}
    )
    print("  ✓ Created: pr:456, pr:457")
    
    # --- Slack Threads ---
    print("Creating Slack threads...")
    ingestor.upsert_slack_thread(
        "slack:C0123:1234567890.000001",
        component_ids=["comp:payments"],
        issue_ids=["issue:123"],
        properties={"channel": "C0123", "topic": "Payment timeout discussion"}
    )
    ingestor.upsert_slack_thread(
        "slack:C0456:1234567891.000002",
        component_ids=["comp:auth"],
        properties={"channel": "C0456", "topic": "Auth refactor planning"}
    )
    print("  ✓ Created: slack:C0123:1234567890.000001, slack:C0456:1234567891.000002")
    
    print("\n✅ Hardcoded sample data seeding complete!")


# =============================================================================
# Verification Functions
# =============================================================================

def verify_queries(service: GraphService) -> bool:
    """Run verification queries to ensure data was seeded correctly."""
    
    print_section("Verifying Queries")
    
    all_pass = True
    
    # Test 1: Component Neighborhood
    print("Query 1: get_component_neighborhood('comp:payments')")
    print("-" * 50)
    result = service.get_component_neighborhood("comp:payments")
    print(f"  Component ID: {result.component_id}")
    print(f"  Docs: {result.docs}")
    print(f"  Issues: {result.issues}")
    print(f"  PRs: {result.pull_requests}")
    print(f"  Slack Threads: {result.slack_threads}")
    print(f"  API Endpoints: {result.api_endpoints}")
    
    payments_ok = len(result.docs) > 0 or len(result.api_endpoints) > 0
    print(f"\n  {'✅ PASS' if payments_ok else '❌ FAIL'}: Component neighborhood query")
    all_pass = all_pass and payments_ok
    
    # Test 2: API Impact (try multiple possible endpoint IDs)
    api_ids_to_try = [
        "api:payments:/v1/payments/charge",
        "api:payments:/charge",
        "api:payments:/payments/charge",
    ]
    
    api_ok = False
    for api_id in api_ids_to_try:
        result = service.get_api_impact(api_id)
        if result.docs or result.issues or result.pull_requests or result.services:
            print(f"\nQuery 2: get_api_impact('{api_id}')")
            print("-" * 50)
            print(f"  API ID: {result.api_id}")
            print(f"  Services: {result.services}")
            print(f"  Docs: {result.docs}")
            print(f"  Issues: {result.issues}")
            print(f"  PRs: {result.pull_requests}")
            api_ok = True
            break
    
    print(f"\n  {'✅ PASS' if api_ok else '⚠️  PARTIAL'}: API impact query")
    
    # Test 3: Auth component
    print("\nQuery 3: get_component_neighborhood('comp:auth')")
    print("-" * 50)
    result = service.get_component_neighborhood("comp:auth")
    print(f"  Component ID: {result.component_id}")
    print(f"  Docs: {result.docs}")
    print(f"  Issues: {result.issues}")
    print(f"  PRs: {result.pull_requests}")
    print(f"  Slack Threads: {result.slack_threads}")
    print(f"  API Endpoints: {result.api_endpoints}")
    
    auth_ok = len(result.docs) > 0 or len(result.api_endpoints) > 0
    print(f"\n  {'✅ PASS' if auth_ok else '❌ FAIL'}: Auth component query")
    all_pass = all_pass and auth_ok
    
    # Summary
    print_section("Verification Summary")
    if all_pass:
        print("✅ All verification queries passed!")
        print("\nThe graph layer is working correctly.")
    else:
        print("⚠️  Some verification queries returned empty results.")
        print("\nThis may be expected if using --swagger only mode.")
    
    return all_pass


# =============================================================================
# Main Entry Point
# =============================================================================

def main() -> int:
    """Main entry point."""
    
    parser = argparse.ArgumentParser(
        description="Seed Neo4j graph with test data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--fixtures",
        action="store_true",
        help="Load data from YAML fixtures (tests/fixtures/graph/)"
    )
    parser.add_argument(
        "--swagger",
        action="store_true",
        help="Load data from OpenAPI specs (tests/fixtures/swagger/)"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only run verification queries, don't seed data"
    )
    args = parser.parse_args()
    
    print_section("Neo4j Graph Seed Script - Phase 2")
    
    # Load configuration
    print("Loading configuration...")
    config = get_config()
    
    graph_config = config.get("graph", {})
    print(f"  graph.enabled: {graph_config.get('enabled', False)}")
    print(f"  graph.uri: {graph_config.get('uri', 'not set')}")
    print(f"  graph.database: {graph_config.get('database', 'neo4j')}")
    
    # Initialize GraphService
    print("\nInitializing GraphService...")
    service = GraphService(config)
    
    if not service.is_available():
        print("\n❌ GraphService is not available!")
        print("\nPossible causes:")
        print("  1. graph.enabled is false in config.yaml")
        print("  2. Neo4j is not running")
        print("  3. Connection credentials are incorrect")
        print("  4. neo4j Python driver is not installed")
        print("\nTo enable the graph layer:")
        print("  1. Set graph.enabled: true in config.yaml")
        print("  2. Set NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD in .env")
        print("  3. Ensure Neo4j is running and accessible")
        return 1
    
    print("  ✓ GraphService connected successfully")
    
    # Initialize GraphIngestor
    ingestor = GraphIngestor(service)
    print("  ✓ GraphIngestor initialized")
    
    try:
        if not args.verify_only:
            # Determine seeding mode
            if args.fixtures or args.swagger:
                if args.fixtures:
                    print_section("Seeding from YAML Fixtures")
                    fixtures = load_fixtures()
                    counts = seed_from_fixtures(ingestor, fixtures)
                    print(f"\n✅ Seeded from fixtures:")
                    for entity_type, count in counts.items():
                        if count > 0:
                            print(f"    {entity_type}: {count}")
                
                if args.swagger:
                    print_section("Seeding from OpenAPI Specs")
                    counts = seed_all_swagger_specs(ingestor)
                    print(f"\n✅ Seeded from swagger:")
                    for entity_type, count in counts.items():
                        if count > 0:
                            print(f"    {entity_type}: {count}")
            else:
                # Default: use hardcoded sample data
                seed_sample_data(ingestor)
        
        # Verify queries work
        verify_queries(service)
        
        return 0
        
    except Exception as exc:
        print(f"\n❌ Error during seeding/verification: {exc}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        # Clean up connection
        service.close()
        print("\n✓ GraphService connection closed")


if __name__ == "__main__":
    sys.exit(main())
