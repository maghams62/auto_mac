# Activity Graph – Option 1

## Overview
Cerebros now maintains an activity graph that links real Slack conversations, Git commits/PRs, documentation nodes, and doc issues to the canonical components defined in `config/slash_git_targets.yaml`. By aggregating signals from `/slack` and `/git`, we can answer:

- “What’s the current activity level around component X?”
- “Which components/features show the most dissatisfaction (complaints, open doc issues)?”

Cerebros remains the central orchestrator + LLM layer; the Oqoqo dashboard can consume the exposed CLI/HTTP outputs whenever needed.

## Schema

| Node | Description |
|------|-------------|
| `Component` | Canonical components (`core.payments`, `billing.checkout`, etc.). |
| `APIEndpoint` | Endpoints like `/v1/payments/create`. |
| `Doc` | Markdown guides / API docs. |
| `GitEvent` | Commits/PRs emitted by `/git` (live or synthetic). |
| `Conversation` | Slack conversations/topics emitted by `/slack`. |
| `DocIssue` | Outstanding documentation issues. |

Key edges:

- `GitEvent -[MODIFIES_API]-> APIEndpoint`
- `Doc -[DOCUMENTS_API]-> APIEndpoint`
- `Conversation -[DISCUSS|COMPLAINS_ABOUT]-> Component`
- `Component -[HAS_DOC_ISSUE]-> DocIssue`

The schema lets us correlate Slack complaints, Git churn, and doc gaps per component.

## Data ingestion

### Slash Slack (live source)
- `/slack` fetches real channels, and `SlashSlackOrchestrator` emits structured summaries + graph records (`data/logs/slash/slack_graph.jsonl`) whenever `graph_emit_enabled` is true.
- `SlackConversationAnalyzer` tags components, complaints, decisions, etc., so every emitted `Conversation` node is linked back to canonical components + APIs.

### Slash Git (live source)
- `/git` now supports live GitHub via `LiveGitDataSource` (`src/slash_git/data_source.py`). Each plan+snapshot optionally emits `CodeChange` / `ComponentImpact` nodes to `data/logs/slash/git_graph.jsonl`.
- The same resolver used by slash commands ensures commits/PRs are scoped to canonical components (path filters).

### Synthetic fixtures
- `data/synthetic_git/` and `data/synthetic_slack/` continue to seed the graph for demos/tests; the live signals simply layer on top using the same schema.

## Activity computation

See `src/activity_graph/service.py`.

- `ComponentActivity` captures raw counts + scores:
  - `git_events` = commits + PRs touching component paths in the time window.
  - `slack_conversations` = Slack graph entries referencing the component.
  - `slack_complaints` = subset of conversations labelled as complaints.
  - `open_doc_issues` = outstanding DocIssues referencing the component.
- Scores (tunable weights in `config.yaml`):
  ```yaml
  activity_graph:
    weights:
      activity:
        git_events: 1.0
        slack_conversations: 0.5
      dissatisfaction:
        slack_complaints: 1.0
        doc_issues: 0.7
  ```
  - `activity_score = git_events * weight.git_events + slack_conversations * weight.slack_conversations`
  - `dissatisfaction_score = slack_complaints * weight.slack_complaints + doc_issue_severity_weight * weight.doc_issues`
  - Pass `?debug=1` to any Activity Graph endpoint (or CLI flag) to see a `debug_breakdown` field with each weighted contribution, which is useful when tuning the config.

Functions:

```python
compute_component_activity(component_id: str, time_window: TimeWindow) -> ComponentActivity
top_dissatisfied_components(limit: int = 5, time_window: TimeWindow | None = None) -> list[ComponentActivity]
```

## Query surface

`scripts/demo_activity_graph.py` (Option A CLI) loads Cerebros config + the ActivityGraphService.

FastAPI endpoints (Option B):

```
GET /activity-graph/component?component_id=core.payments&window=7d
GET /activity-graph/top-dissatisfied?limit=3&window=7d
GET /activity-graph/metrics
```

Both endpoints use the same service + caching stack. The responses return the `ComponentActivity` schema (JSON dataclass).

Examples:

```
# Activity summary for Core Payments
python scripts/demo_activity_graph.py --component core.payments --days 7

# Top 3 dissatisfied components
python scripts/demo_activity_graph.py --top 3 --days 7
```

Sample outputs:

```json
{
  "component_id": "core.payments",
  "component_name": "Core Payments",
  "activity_score": 5.5,
  "dissatisfaction_score": 2.4,
  "git_events": 4,
  "slack_conversations": 3,
  "slack_complaints": 1,
  "open_doc_issues": 2,
  "time_window_label": "last 7 days",
  "debug_breakdown": {
    "git_events_score": 4.0,
    "slack_conversations_score": 1.5,
    "slack_complaints_score": 1.0,
    "doc_issues_score": 1.4
  }
}
```

Top dissatisfied list is the same dataclass list, sorted by `dissatisfaction_score`.

## Example run (Option 1 validation)

```
python scripts/demo_activity_graph.py --component core.payments
python scripts/demo_activity_graph.py --top 3
```

- Component activity highlights VAT-breaking work + doc gaps.
- Top dissatisfied list shows components with the most complaints/doc issues.

## Monitoring & Observability

- FastAPI endpoints log cache hits/misses and emit counters in-memory via `GET /activity-graph/metrics`:
  - `activity_graph_requests_total{route=...}`
  - `activity_graph_cache_hits_total`
  - `activity_graph_cache_misses_total`
  - Average latency per route.
- Logs include `[ACTIVITY GRAPH] component=...` entries so request traces are visible even without scraping metrics.
- Redis or in-memory TTL cache keeps recomputation low; use the metrics endpoint to check hit rates after deployments.

## Scalability

- **Continuous ingestion:** Instead of slash commands emitting graph entries, wire Slack events + GitHub webhooks to the same schema (already planned for long-term). The ActivityGraphService only depends on the canonical catalog + log/graph data.
- **Per-org graphs:** store `component_id` / `service_id` namespaced per workspace (config already supports polyrepo vs monorepo). Each org can have its own graph DB or JSONL partition.
- **Backend growth:**
  - Qdrant collections can shard by component/service for semantic lookups.
  - Neo4j can scale vertically (bigger box) or swap to a managed graph (Aura, Neptune). The schema keeps nodes/edges lean, so even tens of thousands of events stay manageable.
  - DocIssues and complaints are low cardinality; caching pre-aggregated scores per time window (hourly/daily) prevents repeated scanning as data grows.
  - `activity_graph.cache` toggles between in-memory TTL and Redis; cache hits/misses are logged so we can confirm effectiveness in production.

## Neo4j trace graph rollout

The new Investigation/Evidence nodes that link Cerebros questions → evidence → DocIssues will land in **v1.5** (right after the initial traceability launch). V1 ships JSONL persistence + dashboard links; once that stabilizes we will upsert the same investigations into Neo4j so the 3D graph can highlight “question ▸ evidence ▸ doc issue” trails without blocking the MVP.

### v1.5 scope

- Nodes: `Investigation`, `Evidence`, `DocIssue`, `Component`.
- Relationships:
  - `Investigation -[:EMITTED]-> Evidence`
  - `Evidence -[:SUPPORTS]-> DocIssue`
  - `DocIssue -[:AFFECTS]-> Component`
- Queries we plan to support on day one:
  1. `MATCH (d:DocIssue {id: $id})-[:SUPPORTED_BY*1..2]->(i:Investigation) RETURN ...` (trace path for a single doc issue).
  2. `MATCH (c:Component {id: $componentId})<-[:AFFECTS]-(:DocIssue)<-[:SUPPORTS]-(:Evidence)<-[:EMITTED]-(i:Investigation) RETURN i ORDER BY i.created_at DESC LIMIT $n` (recent investigations touching a component).
- Guarded by `traceability.neo4j.enabled`; ingestion job skips writes until the flag is flipped.

