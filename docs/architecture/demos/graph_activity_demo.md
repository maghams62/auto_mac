# Neo4j Graph Layer Demo Scenarios

This document provides scripted demo scenarios showing how the Neo4j graph layer enables structural reasoning about components, APIs, documentation, and code changes.

## Prerequisites

1. **Neo4j Running**: Start Neo4j locally or via Docker:
   ```bash
   docker run -d --name neo4j \
     -p 7474:7474 -p 7687:7687 \
     -e NEO4J_AUTH=neo4j/password \
     neo4j:5
   ```

2. **Configuration**: Enable graph in `config.yaml`:
   ```yaml
   graph:
     enabled: true
     uri: "bolt://localhost:7687"
     username: "neo4j"
     password: "password"
   ```

3. **Seed Data**: Run the seed script to populate the graph:
   ```bash
   python scripts/seed_graph.py --fixtures --swagger
   ```

---

## Scenario 1: Activity Graph Query (Option 1)

**Use Case**: "What's happening around the payments component?"

This scenario demonstrates querying all activity (docs, issues, PRs, Slack threads) related to a specific component.

### CLI Commands

```bash
# Seed the graph with fixtures
python scripts/seed_graph.py --fixtures

# Query component neighborhood (Python one-liner)
python -c "
from src.config_manager import get_config
from src.graph import GraphService

service = GraphService(get_config())
result = service.get_component_neighborhood('comp:payments')

print('Component: comp:payments')
print(f'  Docs: {result.docs}')
print(f'  Issues: {result.issues}')
print(f'  PRs: {result.pull_requests}')
print(f'  Slack Threads: {result.slack_threads}')
print(f'  API Endpoints: {result.api_endpoints}')

service.close()
"
```

### Expected Output

```
Component: comp:payments
  Docs: ['doc:payments-guide', 'doc:swagger:service_a']
  Issues: ['issue:201', 'issue:202']
  PRs: ['pr:101', 'pr:102', 'pr:105']
  Slack Threads: ['slack:C0123PAYMENTS:1705312800.000001']
  API Endpoints: ['api:payments:/v1/payments/charge', 'api:payments:/v1/payments/refund']
```

### Interpretation

The graph shows that `comp:payments` has:
- **2 documentation sources** that need to stay in sync
- **2 open/recent issues** affecting this component
- **3 PRs** that modified payment-related code
- **1 Slack thread** discussing payment issues
- **2 API endpoints** exposed by this component

**Doc Prioritization Insight**: If issue:201 is high severity, we should verify that doc:payments-guide is updated to reflect any fixes from pr:101.

---

## Scenario 2: Doc Drift Detection (Option 2)

**Use Case**: "Service A changed /payments/charge – which docs need updates?"

This scenario demonstrates detecting when documentation is out of sync with the OpenAPI specification.

### CLI Commands

```bash
# Run drift detection on all specs
python scripts/detect_swagger_drift.py --all

# Or check specific spec/doc pair
python scripts/detect_swagger_drift.py \
  --spec service_a.yaml \
  --doc payments_api.md \
  --verbose
```

### Expected Output

```
============================================================
  Drift Report: service_a.yaml vs payments_api.md
============================================================

Spec Version: 2.1.0
Doc Version:  2.0

❌ Drift detected: 5 issues found

ERRORS (documentation is missing critical information):
  • [POST /payments/charge] missing_param: metadata
  • [POST /payments/charge] missing_param: capture
  • [POST /payments/refund] required_mismatch: X-Idempotency-Key

WARNINGS (documentation may be outdated):
  • [*] version_mismatch: version
  • [POST /payments/charge] description_mismatch: amount

Summary:
  Missing parameters in docs: 2
    → metadata, capture
  Extra parameters in docs:   0
  Missing endpoints in docs:  0
```

### Interpretation

The drift report shows:
1. **Version Mismatch**: Doc is v2.0, spec is v2.1 – documentation hasn't been updated
2. **Missing Parameters**: `metadata` and `capture` were added in v2.1 but not documented
3. **Required Mismatch**: `X-Idempotency-Key` is now required for refunds but doc says optional

**Action Items**:
1. Update payments_api.md to v2.1
2. Document the new `metadata` and `capture` fields
3. Mark `X-Idempotency-Key` as required in refund documentation

---

## Scenario 3: API Impact Analysis

**Use Case**: "If I modify the /charge endpoint, what else is affected?"

### CLI Commands

```bash
# Query API impact
python -c "
from src.config_manager import get_config
from src.graph import GraphService

service = GraphService(get_config())

# Try different endpoint ID formats
for endpoint_id in [
    'api:payments:/v1/payments/charge',
    'api:payments:/payments/charge',
]:
    result = service.get_api_impact(endpoint_id)
    if result.services or result.docs:
        print(f'API: {endpoint_id}')
        print(f'  Services calling this API: {result.services}')
        print(f'  Documentation to update: {result.docs}')
        print(f'  Related issues: {result.issues}')
        print(f'  Related PRs: {result.pull_requests}')
        break

service.close()
"
```

### Expected Output

```
API: api:payments:/v1/payments/charge
  Services calling this API: ['svc:api-gateway', 'svc:billing-worker']
  Documentation to update: ['doc:payments-guide', 'doc:swagger:service_a']
  Related issues: ['issue:201']
  Related PRs: ['pr:101', 'pr:105']
```

### Interpretation

Changing `/v1/payments/charge` impacts:
- **2 services** that depend on this endpoint – need to verify compatibility
- **2 docs** that reference this endpoint – need to update if behavior changes
- **1 issue** tracking problems with this endpoint
- **2 PRs** that recently modified this endpoint – review for context

---

## Scenario 4: Cross-Component Impact

**Use Case**: "PR #104 touches both auth and billing – what's the blast radius?"

### CLI Commands

```bash
# Query both components affected by the PR
python -c "
from src.config_manager import get_config
from src.graph import GraphService

service = GraphService(get_config())

# PR #104 affects auth and billing
for comp_id in ['comp:auth', 'comp:billing']:
    result = service.get_component_neighborhood(comp_id)
    print(f'\n{comp_id}:')
    print(f'  Related docs: {result.docs}')
    print(f'  Open issues: {result.issues}')
    print(f'  API endpoints: {result.api_endpoints}')

service.close()
"
```

### Interpretation

This shows all documentation and APIs that might need review when a PR spans multiple components.

---

## Scalability Considerations

The synthetic fixtures demonstrate the pattern; here's how to scale for production:

### Batch Ingestion

For large datasets, use Cypher `UNWIND` for batch operations:

```python
def batch_upsert_prs(ingestor, prs: List[Dict]):
    """Batch upsert PRs using UNWIND."""
    query = """
    UNWIND $prs AS pr
    MERGE (p:PR {id: pr.id})
    SET p += pr.properties
    WITH p, pr
    UNWIND pr.component_ids AS comp_id
    MERGE (c:Component {id: comp_id})
    MERGE (p)-[:MODIFIES_COMPONENT]->(c)
    """
    ingestor.graph_service.run_write(query, {"prs": prs})
```

### Job Queue Integration

For continuous ingestion, integrate with Celery:

```python
@celery_app.task
def ingest_pr_to_graph(pr_data: Dict):
    """Celery task to ingest PR into Neo4j."""
    config = get_config()
    service = GraphService(config)
    ingestor = GraphIngestor(service)
    
    ingestor.upsert_pr(
        pr_data["id"],
        component_ids=pr_data.get("component_ids", []),
        endpoint_ids=pr_data.get("endpoint_ids", []),
        properties=pr_data,
    )
    service.close()
```

### Neo4j Aura (Managed)

For production, consider Neo4j Aura:

```yaml
# config.yaml for Aura
graph:
  enabled: true
  uri: "neo4j+s://xxxxx.databases.neo4j.io"
  username: "neo4j"
  password: "${NEO4J_AURA_PASSWORD}"
  database: "neo4j"
```

### Incremental vs Full Refresh

**Incremental Sync**:
- Use webhook events to ingest changes in real-time
- Only update nodes/relationships that changed

**Full Refresh**:
- Periodically rebuild the entire graph
- Use for catching up after extended downtime

```python
def full_refresh(ingestor):
    """Clear and rebuild the graph."""
    ingestor.graph_service.run_write("MATCH (n) DETACH DELETE n")
    # Re-seed from all sources
    seed_from_fixtures(ingestor, load_fixtures())
```

---

## Running the Demo

### Quick Start

```bash
# 1. Start Neo4j
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/test neo4j:5

# 2. Configure
export NEO4J_PASSWORD=test
# Edit config.yaml: graph.enabled: true

# 3. Seed data
python scripts/seed_graph.py --fixtures --swagger

# 4. Run drift detection
python scripts/detect_swagger_drift.py --all

# 5. Run tests
pytest tests/test_graph_service.py tests/test_swagger_drift.py -v
```

### Neo4j Browser Queries

Access Neo4j Browser at http://localhost:7474 and run:

```cypher
// See all nodes
MATCH (n) RETURN n LIMIT 50

// Component neighborhood
MATCH (c:Component {id: 'comp:payments'})<-[r]-(n)
RETURN c, r, n

// API impact
MATCH (api:APIEndpoint {id: 'api:payments:/v1/payments/charge'})<-[r]-(n)
RETURN api, r, n

// Find docs that need updating (connected to recently changed APIs)
MATCH (pr:PR)-[:MODIFIES_ENDPOINT]->(api:APIEndpoint)<-[:DESCRIBES_ENDPOINT]-(doc:Doc)
WHERE pr.state = 'merged'
RETURN DISTINCT doc.id AS doc_to_review, collect(api.id) AS changed_apis
```

---

## References

- [Graph Schema Definition](../graph_schema.md)
- [Phase 1 Design Brief](../neo4j_phase1_brief.md)
- [Design Decisions](../neo4j_design_decisions.md)
- [Seed Script](../../../scripts/seed_graph.py)
- [Drift Detection Script](../../../scripts/detect_swagger_drift.py)

