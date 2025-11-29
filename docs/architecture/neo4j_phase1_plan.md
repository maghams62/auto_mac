## Neo4j Phase 1 – Engineering Task Plan (For Claude)

This plan packages the schema + brief into concrete steps that Claude can execute. For schema details see `docs/architecture/graph_schema.md`; for contextual brief see `docs/architecture/neo4j_phase1_brief.md`.

### Task 0 – Environment Prep
1. Ensure `neo4j` driver is listed in `requirements.txt` (already added).
2. Verify `graph` block exists in `config.yaml` with `enabled`, `uri`, `username`, `password`, `database`, `ingest_batch_size`.
3. Update `.env.example` with `NEO4J_*` placeholders (already done).

### Task 1 – Implement GraphService
File: `src/graph/service.py`
1. Initialize Neo4j driver when `graph.enabled` is true; otherwise stay inert.
2. Provide methods:
   * `run_query(query, params=None)`
   * `run_write(query, params=None)`
   * `get_component_neighborhood(component_id) -> GraphComponentSummary`
   * `get_api_impact(api_id) -> GraphApiImpactSummary`
3. Use Cypher from `graph_schema.md` to fetch docs/issues/prs/slack/APIs/services.
4. Handle connection errors gracefully (log + return empty summary objects).

### Task 2 – Implement GraphIngestor
File: `src/graph/ingestor.py`
1. Wrap `GraphService.run_write` to upsert nodes/edges via `MERGE`.
2. Methods to provide (matching schema):
   * `upsert_component`, `upsert_service`
   * `upsert_api_endpoint`
   * `upsert_doc`, `upsert_issue`, `upsert_pr`
3. Each method should accept IDs + optional properties + related IDs to create the appropriate relationships (e.g., `DESCRIBES_COMPONENT`, `MODIFIES_ENDPOINT`).
4. Degrade to no-op when graph is disabled.

### Task 3 – Lightweight Smoke Script (optional but preferred)
File suggestion: `scripts/seed_graph.py`
1. Demonstrate using `GraphIngestor` to:
   * Create sample component/API/doc/issue/PR.
   * Call `GraphService.get_component_neighborhood` and `get_api_impact`.
2. Print results so developers can verify config quickly.

### Task 4 – Documentation Touch-Up
1. In `README.md` (or appropriate doc), add a short “Neo4j setup” section referencing:
   * `docs/architecture/graph_schema.md` for schema.
   * `docs/architecture/neo4j_phase1_brief.md` for design rationale.
   * Mention that graph is optional; enable via config to test.

### Deliverable Summary
* Working `GraphService` & `GraphIngestor` modules per schema.
* Optional seed script or notebook instructions demonstrating basic usage.
* No changes to `/oq` behavior yet; the service simply exists and can be manually exercised.
