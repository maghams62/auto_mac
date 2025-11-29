# Neo4j Graph Layer - Design Decisions

This document captures the design rationale, trade-offs, and known limitations for the Phase 1 Neo4j graph implementation.

## Why Neo4j?

### Requirements Driving the Choice

1. **Structural Queries**: The multi-source reasoner needs to answer questions like:
   - "What documentation describes the payments component?"
   - "Which PRs modified the `/charge` endpoint?"
   - "What issues are related to this Slack discussion?"

2. **Relationship Traversal**: These queries involve multi-hop traversals (Component → API → PR → Issue) that are inefficient in relational databases but native to graph databases.

3. **Schema Flexibility**: The v1 schema needed room to evolve as we discover new entity types and relationships without expensive migrations.

### Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **Neo4j** | Native graph traversal, Cypher language, mature ecosystem | Additional infrastructure, operational complexity | **Chosen** |
| PostgreSQL with recursive CTEs | No new infra, team familiarity | Complex multi-hop queries, poor performance at scale | Rejected |
| In-memory graph (NetworkX) | Simple, no infra | No persistence, memory limits, single-process | Rejected |
| Dgraph | GraphQL-native | Less mature, smaller ecosystem | Deferred consideration |

## Schema Design Rationale

### Entity ID Alignment

All graph nodes use the same `id` format as the vector layer and evidence system:

```
Component: comp:payments
Doc:       doc:payments-guide
Issue:     issue:123
PR:        pr:456
API:       api:payments:/charge
Slack:     slack:C123:1234567890.000001
```

**Rationale**: This alignment enables seamless cross-layer queries. When the multi-source reasoner retrieves `Evidence(entity_id="doc:payments-guide")` from the vector layer, it can directly query the graph for related entities using the same ID.

### Relationship Direction Conventions

Relationships flow from **artifact** to **structural entity**:

```
(:Doc)-[:DESCRIBES_COMPONENT]->(:Component)
(:Issue)-[:AFFECTS_COMPONENT]->(:Component)
(:PR)-[:MODIFIES_ENDPOINT]->(:APIEndpoint)
```

**Rationale**: This direction supports the primary query pattern: "Given an artifact (doc/issue/PR), what does it relate to?" The reverse query ("Given a component, what artifacts exist?") is equally efficient in Neo4j due to bidirectional index traversal.

### Node Properties vs. Relationships

We chose **relationships** over **property arrays** for connections:

```cypher
# Preferred: Relationship
(:Doc)-[:DESCRIBES_COMPONENT]->(:Component)

# Avoided: Property array
(:Doc {component_ids: ["comp:payments", "comp:auth"]})
```

**Rationale**: Relationships enable index-backed traversal and support relationship properties (e.g., confidence scores, timestamps) in the future.

## Implementation Decisions

### Optional Dependency Pattern

The `GraphService` gracefully handles missing Neo4j driver:

```python
try:
    from neo4j import GraphDatabase, Driver
except Exception:
    GraphDatabase = None
    Driver = None
```

**Rationale**: Neo4j is optional infrastructure. Teams without graph queries enabled should not face import errors or deployment blockers.

### Config-Driven Enable/Disable

The graph layer is controlled by `config.yaml`:

```yaml
graph:
  enabled: false  # Default: disabled
  uri: "${NEO4J_URI:-bolt://localhost:7687}"
```

**Rationale**: Allows gradual rollout. Development environments can test with `enabled: true` while production remains disabled until the layer is proven.

### MERGE-Based Upserts

All ingestion uses Cypher `MERGE`:

```cypher
MERGE (n:Component {id: $id})
SET n += $props
```

**Rationale**: Idempotent operations prevent duplicate nodes when the same entity is ingested multiple times (e.g., during re-indexing or event replay).

## Known Limitations (Phase 1)

### 1. Auto-Commit Transactions

**Current**: `run_write()` uses `session.run()` (auto-commit).

**Issue**: No automatic retry on transient failures (network blips, leader elections). Partial writes possible on multi-statement operations.

**Recommended Fix (Phase 2)**:
```python
def run_write(self, query, params=None):
    def _tx_fn(tx):
        return tx.run(query, params or {}).consume()
    with self._driver.session(...) as session:
        return session.execute_write(_tx_fn)
```

### 2. No Singleton/Factory Pattern

**Current**: Each `GraphService(config)` call creates a new driver instance.

**Issue**: Multiple driver instances = multiple connection pools, inefficient resource usage.

**Recommended Fix (Phase 2)**:
```python
_graph_service: Optional[GraphService] = None

def get_graph_service(config: Dict[str, Any]) -> GraphService:
    global _graph_service
    if _graph_service is None:
        _graph_service = GraphService(config)
    return _graph_service
```

### 3. Batch Size Config Unused

**Current**: `ingest_batch_size: 100` is defined but ingestion is one-at-a-time.

**Impact**: Lower throughput for bulk ingestion scenarios.

**Recommended Fix (Phase 2)**: Implement `upsert_batch()` methods that use `UNWIND` for bulk MERGE operations.

### 4. No Connection Health Check

**Current**: `_connect()` creates driver but doesn't verify reachability.

**Impact**: Failures surface only on first query, not at startup.

**Recommended Fix (Phase 2)**:
```python
def verify_connectivity(self) -> bool:
    try:
        self.run_query("RETURN 1")
        return True
    except Exception:
        return False
```

### 5. No Context Manager Support

**Current**: Driver lifecycle managed manually via `close()`.

**Impact**: Potential connection leaks if `close()` not called.

**Recommended Fix (Phase 2)**: Implement `__enter__`/`__exit__` for `with` statement support.

## Future Roadmap

### Phase 2: Integration

1. **GraphEvidenceRetriever**: Add retriever that uses `get_component_neighborhood()` and `get_api_impact()` to enrich multi-source reasoning.

2. **Ingestion Pipeline Wiring**: Hook into existing doc/issue/PR indexing to automatically populate graph.

3. **`/oq` Integration**: Add graph evidence to the reasoner's evidence collection.

### Phase 3: Advanced Queries

1. **Path Queries**: "How is component A connected to component B?"
2. **Impact Analysis**: "If I change API X, what docs need updating?"
3. **Drift Detection**: "Which docs reference APIs that have changed?"

### Phase 4: Operational Maturity

1. **Connection Pooling Tuning**: Configure pool size, timeouts
2. **Monitoring**: Expose metrics (query latency, connection health)
3. **Backup/Restore**: Document Neo4j backup procedures

## References

- [Neo4j Python Driver Documentation](https://neo4j.com/docs/python-manual/current/)
- [Cypher Query Language Reference](https://neo4j.com/docs/cypher-manual/current/)
- [Graph Schema Definition](./graph_schema.md)
- [Phase 1 Brief](./neo4j_phase1_brief.md)

