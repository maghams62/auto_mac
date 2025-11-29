## Neo4j Phase 1 Implementation Brief

Goal: stand up the graph layer without changing `/slack`, `/git`, or `/oq` flows yet. Neo4j remains optional (config flag) but supports ingestion/query for the v1 schema.

### Scope

1. **Config & Dependencies**
   * Ensure `graph.enabled`, `graph.uri`, `graph.username`, `graph.password`, `graph.database` from `config.yaml` / `.env` drive the service.
   * Add `neo4j` Python driver dependency.

2. **GraphService**
   * Lives in `src/graph/service.py`.
   * Connects to Neo4j when enabled.
   * Exposes:
     * `get_component_neighborhood(component_id: str) -> GraphComponentSummary`
     * `get_api_impact(api_id: str) -> GraphApiImpactSummary`
     * `run_query(...)` / `run_write(...)` helpers for future use.
   * Handles connection failures gracefully (log + return empty summaries).

3. **GraphIngestor**
   * `src/graph/ingestor.py`.
   * Provides helper methods: `upsert_component`, `upsert_service`, `upsert_doc`, `upsert_issue`, `upsert_pr`, `upsert_api_endpoint`.
   * Each helper uses `MERGE` and the schema defined in `docs/architecture/graph_schema.md`.
   * Ingestion can be invoked from indexing pipelines (docs/issues/PRs) but **Phase 1 does not wire existing pipelines yet**—just ensure the API exists and is tested with basic samples.

4. **Documentation**
   * Schema + ingestion touchpoints already documented in `docs/architecture/graph_schema.md`.
   * Ensure README note and/or internal doc points contributors to the new config knobs.

5. **Out of Scope (Phase 1)**
   * `/oq` should not call GraphService yet.
   * No requirement to ingest historical data; manual scripts/CLI can be added later.
   * No advanced graph queries beyond the two summaries above.

### Acceptance Criteria

* With Neo4j running locally, a developer can:
  1. Enable `graph.enabled` and set credentials.
  2. Run a small script/notebook to call `GraphIngestor` to seed a few nodes/relationships.
  3. Call `GraphService.get_component_neighborhood` and `get_api_impact` and receive results matching the seeded data.
* When `graph.enabled = false` or driver import fails, the rest of the system continues functioning (queries return empty summaries, no exceptions leak).

This brief should give Claude (or any contributor) enough context to implement the initial graph layer without touching `/oq` logic or existing retrievers.
