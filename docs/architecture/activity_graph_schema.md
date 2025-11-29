## Activity Graph Schema (Phase 1 Refresh)

This document captures the Phase 1 schema extensions that unlock activity scoring
and dissatisfaction tracking across Slack + GitHub signals. It complements
`docs/architecture/graph_schema.md` by introducing the additional node/edge
types required by the unified Activity Graph plan.

### Node Labels

| Label | Purpose | Required Properties |
| --- | --- | --- |
| `Component` | Product surface to prioritize (existing) | `id`, `name` |
| `CodeArtifact` | File/module/service unit so we can reason about dependencies | `id`, optional `path`, `language`, `repo` |
| `ActivitySignal` | Normalized signal (commit, PR, Slack burst, deploy, etc.) | `id`, `source`, optional `type`, `started_at`, `metadata` |
| `SupportCase` | Customer-facing tickets (Discord, Support, Jira escalation) | `id`, `source`, optional `sentiment`, `severity`, `opened_at` |
| `APIEndpoint`, `Doc`, `Issue`, `PR`, `SlackThread`, `Service` | Unchanged from v1 | See `graph_schema.md` |

> Why `ActivitySignal`? It gives us a single abstraction for any “fresh work”
> touching a component, so the analytics layer can weight commits, PRs,
> Slack activity, and deploy alerts in the same Cypher query.

### Relationship Types & Properties

| Relationship | Description | Key Properties |
| --- | --- | --- |
| `(:Component)-[:OWNS_CODE]->(:CodeArtifact)` | Ties components to the code they own | none |
| `(:CodeArtifact)-[:DEPENDS_ON]->(:CodeArtifact)` | Dependency graph (reused in Phase 2) | none |
| `(:ActivitySignal)-[:SIGNALS_COMPONENT]->(:Component)` | Activity edges that feed prioritization | `signal_weight` (float), `last_seen` (datetime ISO) |
| `(:ActivitySignal)-[:SIGNALS_ENDPOINT]->(:APIEndpoint)` | Endpoint-level activity | same as above |
| `(:SupportCase)-[:SUPPORTS_COMPONENT]->(:Component)` | Negative user/customer sentiment | `signal_weight` (default 1.0 if unspecified), `last_seen` |
| `(:SupportCase)-[:SUPPORTS_ENDPOINT]->(:APIEndpoint)` | Endpoint-specific dissatisfaction | same as above |
| Existing edges (`DESCRIBES_COMPONENT`, `MODIFIES_COMPONENT`, etc.) | Unchanged | none |

The **weighted edges** let us compute recency-aware activity scores without
duplicating logic in every consumer:

```cypher
MATCH (:ActivitySignal {id: $signal})-[rel:SIGNALS_COMPONENT]->(c:Component)
RETURN rel.signal_weight, rel.last_seen;
```

Ingestion helpers enforce the property names (`signal_weight`, `last_seen`)
so downstream analytics can rely on consistent metadata.

### GraphIngestor Additions

New helpers available in `src/graph/ingestor.py`:

* `upsert_code_artifact()` — creates artifacts, links them to components, and
  records intra-artifact dependencies.
* `upsert_activity_signal()` — persists normalized signals and sets weighted
  `SIGNALS_*` relationships.
* `upsert_support_case()` — models dissatisfaction edges with optional weights.
* `_merge_relationship()` now accepts property dictionaries so we can update
  weights without bespoke Cypher in every ingestion script.

These APIs are used by the upcoming Slack + Git ingestion jobs to dual-write
into Neo4j and the Qdrant context index.

### Compatibility & Migration Notes

* All new nodes reuse the existing `id` convention (`code:repo:path`,
  `signal:slack:{channel}:{ts}`, `support:linear:{id}`, etc.) so they stay
  aligned with `ContextChunk.entity_id`.
* No breaking schema changes were introduced; existing ingestion scripts
  continue to function because relationship defaults remain empty objects.
* Downstream queries can start reading the weighted properties immediately,
  but should fall back to zero weight if missing to keep compatibility with
  older historical data.

### Next Steps

1. Wire Slack + Git ingestion jobs to emit `ActivitySignal` edges with weights
   derived from recency + severity.
2. Introduce dependency ingestion (Phase 2) that populates `DEPENDS_ON`.
3. Add SHACL-style validation once the Phase 2 topology is in place to protect
   against drift in large-scale deployments.

