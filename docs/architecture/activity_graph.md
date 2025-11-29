## Activity Graph & Context Index

This document explains how the activity graph, ingestion pipelines, and analytics
APIs work together to prioritize documentation updates and reason about cross-team
context.

---

### 1. Schema Overview

* **Components** remain the central aggregation point (`Component` nodes).
* **ActivitySignal** nodes model normalized “work” (commits, PRs, Slack bursts),
  with weighted edges (`SIGNALS_COMPONENT`, `SIGNALS_ENDPOINT`) storing:
  * `signal_weight` – recency/severity score
  * `last_seen` – ISO timestamp for windowed analytics
* **SupportCase** nodes capture dissatisfaction from support/Discord/Jira.
* **CodeArtifact** nodes map files or modules to components with `OWNS_CODE`
  and inter-artifact `DEPENDS_ON` links (foundation for cross-repo analysis).

See `docs/architecture/activity_graph_schema.md` for exact labels and properties.

---

### 2. Ingestion Pipelines

#### Slack (`src/ingestion/slack_activity_ingestor.py`)
1. Configured via `activity_ingest.slack` block in `config.yaml`:
   * Channels (`id`, `components`, `endpoint_ids`, optional keywords).
   * Recency decay (`recency_half_life_hours`) and reaction weights.
2. Pulls channel history with `SlackAPIClient`, skipping system/bot messages.
3. For each message:
   * Emits a `ContextChunk` to the vector index (Qdrant) so `/oq` can quote context.
   * Creates an `ActivitySignal` edge with computed weight (keywords + reactions + decay).
4. Stores last processed timestamp under `data/state/activity_ingest/slack_<channel>.json`.

#### GitHub (`src/ingestion/git_activity_ingestor.py`)
1. Configured via `activity_ingest.git` block:
   * Repos with `owner/name`, `component_map`, file prefixes → components/endpoints.
2. Uses `GitHubPRService` for PRs + commits, fetching changed files.
3. Dual writes:
   * `ContextChunk`s summarizing PR/commit metadata + files touched.
   * Graph ingest:
     - `upsert_pr`, `upsert_code_artifact`, `upsert_activity_signal`.
4. Tracks cursors per repo (last PR update, last commit ISO) in `data/state/activity_ingest/`.

#### Dependency Mapping (Phase 2 foundation)
* Declared in `context_resolution.dependency_files` (see `configs/dependency_map.yaml`).
* `scripts/run_dependency_mapping.py` loads YAML to upsert components, artifacts,
  and cross-artifact `DEPENDS_ON` edges for multi-repo visibility.

### 2.1 Vector Layer Coordination

Slack and Git ingestion now dual-write richer `ContextChunk`s that capture the target
Qdrant collection plus payload clamping, so oversized messages cannot starve the index.
The Mongo-backed chat persistence (Agent 1) feeds the same chunk format through
`scripts/backfill_chats_to_vectordb.py`, ensuring historical conversations can be
replayed into the vector store without guessing schema.

When troubleshooting:

- Use `python scripts/run_checks.py --vectordb` to confirm Qdrant connectivity before
  running ingestion jobs.
- Structured logs from `SlackActivityIngestor` / `GitActivityIngestor` report when
  Qdrant writes are skipped (e.g., vector service unavailable) and how many chunks
  made it into the collection, giving parity with the graph upserts.

---

### 3. Analytics & APIs

#### Graph Analytics Service
* `src/graph/analytics_service.py` runs Cypher directly against Neo4j.
* `get_component_activity(component_id, window_hours, limit)`
  * Weighted sum of recent `ActivitySignal` edges.
  * Returns top `signals` for evidence.
* `get_dissatisfaction_leaderboard(window_hours, limit, components)`
  * Combines support-case weights + open issue counts per component.

#### REST Endpoints
* `GET /api/activity-graph/activity-level`
  * Query params: `component_id`, optional `window_hours` (default 168), `limit`.
  * Response: `{ component_id, activity_score, signals: [...] }`.
* `GET /api/activity-graph/dissatisfaction`
  * Params: `window_hours`, `limit`, optional repeated `components`.
  * Returns leaderboard entries with total/support/issue scores.
* Both endpoints require `graph.enabled: true` with valid Neo4j credentials.

#### Evidence Retriever Integration
* `ActivityAnalyticsRetriever` (source_type `activity_graph`) allows `/oq`
  to embed these summaries directly into planning/synthesis responses.

---

### 4. Example Usage

```bash
# Run ingestion (respecting config flags)
python scripts/run_activity_ingestion.py --sources slack git

# Query activity for a component
curl "http://localhost:8000/api/activity-graph/activity-level?component_id=comp:payments&window_hours=72"

# Query dissatisfaction leaderboard
curl "http://localhost:8000/api/activity-graph/dissatisfaction?window_hours=168&limit=5"
```

Sample response:

```json
{
  "component_id": "comp:payments",
  "activity_score": 8.35,
  "signals": [
    {
      "id": "signal:pr:tiangolo/fastapi:123",
      "source": "github_pr",
      "weight": 1.8,
      "last_seen": "2025-11-27T11:42:01+00:00"
    },
    {
      "id": "signal:slack:C0123:1732662026.289",
      "source": "slack",
      "weight": 1.15,
      "last_seen": "2025-11-27T10:55:04+00:00"
    }
  ]
}
```

---

### 5. Scalability & Operations

* **Batching & Cursoring** – Both Slack and Git ingestion honor `batch_limit`
  and persist cursors per channel/repo, so jobs can run continuously (cron/Celery).
* **Vector Dual-Writes** – Each signal emits a `ContextChunk`, enabling hybrid
  Graph + semantic retrieval for `/oq`.
* **Config-Driven Expansion** – Adding a new channel/repo is purely declarative in `config.yaml`.
* **Validation & Telemetry** – `scripts/run_graph_validation.py` (Phase 2)
  surfaces schema drift, missing weights, and orphaned artifacts. Future work
  can push these metrics into `/api/graph/validation` or Prometheus.
* **Blueprint for Phase 2** – The dependency mapper and upcoming context-resolution
  service build on the same schema, enabling transitive blast-radius analysis
  when APIs change across repositories.

---

### 6. Synthetic Testing & Slash Commands

Use fixtures whenever you need to exercise slash commands without real data:

```bash
# Seed synthetic git + slack activity
python scripts/seed_activity_fixtures.py \
  --git-fixture tests/fixtures/activity/git_activity.yaml \
  --slack-fixture tests/fixtures/activity/slack_activity.yaml \
  --repo-id fixtures:payments

# Validate graph state (optional)
python scripts/run_graph_validation.py
```

Once seeded:

1. Run `/git payments` or `/git comp:payments` – you should see the synthetic PR/commit
   summaries surfaced via the activity retriever.
2. Run `/slack payments` – expect the seeded dissatisfaction thread to appear.
3. Run `/oq what's happening around comp:payments?` – `/oq` now pulls the activity
   graph evidence to explain why the component is “hot”.

If a slash command fails to find the seeded data, double-check:
* `config.yaml` → `activity_ingest` channel/repo mappings include the IDs used
  in the fixture files.
* Neo4j/Qdrant are running with `graph.enabled: true`.
* The synthetic ingestion script logged `ingested > 0`.

