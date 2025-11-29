## Neo4j Graph Schema (v1)

This document locks down the initial schema that backs the multi-source reasoner’s structural view of the Oqoqo system. All IDs reuse the existing `entity_id` format (`comp:payments`, `doc:payments-guide`, `issue:123`, etc.) so vector/evidence/graph layers stay aligned.

### Node Labels & Required Properties

| Label         | Properties (required → optional)                                                | Notes                                                                 |
|---------------|---------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| `Component`   | `id`, `name`                                                                    | Logical product/component surfaces (e.g., `comp:payments`).           |
| `Service`     | `id`, `name`                                                                    | Microservices or higher-level programs (e.g., `svc:billing`).         |
| `APIEndpoint` | `id`, `service_id`, `method`, `path`, optional `version`, `component_id`        | Use IDs such as `api:payments:/charge`.                              |
| `Doc`         | `id`, `title`, `url`, optional `component`, `tags[]`, `last_updated`            | Maps to documentation pages/sections used in ContextChunks.          |
| `Issue`       | `id`, `title`, `status`, optional `severity`, `created_at`, `updated_at`        | Jira/Linear/GitHub issues.                                           |
| `PR`          | `id`, `number`, `title`, `state`, optional `merged_at`, `author`                | GitHub/GitLab pull requests.                                         |
| `SlackThread` | `id`, `channel`, `started_at`, optional `topic`, `participants[]`               | Thread-level abstraction; individual messages stay in Slack layer.   |

### Relationship Types

| Relationship                              | Description                                                                 |
|-------------------------------------------|-----------------------------------------------------------------------------|
| `(:Doc)-[:DESCRIBES_COMPONENT]->(:Component)` | Doc content belongs to one or more components.                             |
| `(:Doc)-[:DESCRIBES_ENDPOINT]->(:APIEndpoint)` | Doc references a specific API endpoint.                                    |
| `(:Issue)-[:AFFECTS_COMPONENT]->(:Component)`  | Issue is scoped to a component.                                            |
| `(:Issue)-[:REFERENCES_ENDPOINT]->(:APIEndpoint)` | Issue mentions a particular API.                                           |
| `(:PR)-[:MODIFIES_COMPONENT]->(:Component)`     | PR includes code touching a component.                                     |
| `(:PR)-[:MODIFIES_ENDPOINT]->(:APIEndpoint)`    | PR updates an API signature/behavior.                                      |
| `(:Service)-[:CALLS_ENDPOINT]->(:APIEndpoint)`  | Service invokes an endpoint (runtime topology).                            |
| `(:Component)-[:EXPOSES_ENDPOINT]->(:APIEndpoint)` | Component owns/exposes endpoints.                                          |
| `(:SlackThread)-[:DISCUSSES_COMPONENT]->(:Component)` | Slack thread discussion centers on a component.                            |
| `(:SlackThread)-[:DISCUSSES_ISSUE]->(:Issue)`       | Slack thread references an issue or ticket.                                |

### Identity & Alignment

* All nodes store an `id` property identical to the IDs used elsewhere:
  * Components → `comp:payments`
  * Docs → `doc:payments-guide`
  * Issues → `issue:123`
  * PRs → `pr:456`
  * API endpoints → `api:payments:/charge`
* This lets ContextChunks, Evidence objects, and graph nodes reference the same artifact without translation.

### GraphService API (Phase 1)

The service layer exposes a minimal number of high-level queries so `/oq` (or other callers) can pull structured graph evidence without writing Cypher:

1. `get_component_neighborhood(component_id: str) -> GraphComponentSummary`
   * Returns arrays of doc IDs, issue IDs, PR IDs, Slack thread IDs, and API endpoint IDs touching the component.
2. `get_api_impact(api_id: str) -> GraphApiImpactSummary`
   * Returns service IDs, doc IDs, issue IDs, and PR IDs referencing the given endpoint.

Internally, the service also:

* Provides `run_query`/`run_write` helpers for future extensions.
* Uses config (`graph.enabled`, `graph.uri`, etc.) so Neo4j remains optional.

### Ingestion Touchpoints

To keep v1 lightweight, data flows into Neo4j at the same time we already normalize/index other sources:

* **Docs** – when ContextChunks are generated for docs, also upsert:
  * `Doc` node (`id = doc:*`) with metadata (`title`, `url`).
  * `DESCRIBES_COMPONENT` edges based on document metadata or tagging.
  * `DESCRIBES_ENDPOINT` edges where API references are known (optional placeholders allowed).
* **Issues** – when issues are ingested/normalized for Evidence:
  * Upsert `Issue` node with status/severity.
  * Link to components/endpoints using the same heuristics used for tagging `entity_id`s.
* **PRs** – when Git retrievers normalize PRs:
  * Upsert `PR` node and attach `MODIFIES_*` relationships based on component/component tags already present in metadata.
* **API endpoints & components** – seeded via a small static map (or config) so docs/issues/PRs can attach to existing nodes. Additional enrichment can come from code analysis later.

Ingestion is handled by a `GraphIngestor` helper that exposes `upsert_doc`, `upsert_issue`, `upsert_pr`, `upsert_api_endpoint`, etc., wrapping standard `MERGE` operations against the Neo4j driver.

### Minimal Query Targets (Phase 1 Demo)

1. **API Impact**
   * Inputs: `APIEndpoint.id`
   * Returns: related services, docs, issues, PRs.
2. **Component Neighborhood**
   * Inputs: `Component.id`
   * Returns: docs, endpoints, issues, PRs, Slack threads around the component.

These two queries justify the schema and match the `/oq` reasoning stories (doc drift, impact analysis). Additional relationship types can be layered on later without breaking this foundation.
