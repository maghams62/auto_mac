# Option 1 – Activity Graph

## Overview
The Activity Graph turns live Slack conversations, Git events, and DocIssues into a single, queryable signal about the health of every component. When `/activity-graph/*` or `/activity/snapshot` is called, `ActivityGraphService` (`src/activity_graph/service.py`) loads the canonical component catalog produced by `GitQueryPlanner`, hydrates recent Slack + Git + DocIssue signals, and emits weighted scores. Slack signals arrive via the slash command pipeline, Git signals arrive via `/slash_git` or live GitHub, and DocIssues are produced by the Option 2 impact pipeline. Because all three feeds resolve to the same component IDs, reviewers can answer “Where should we spend our next documentation hour?” without chasing multiple dashboards.

## Quickstart (fixtures + slash cerebros)
- Run `python scripts/seed_activity_graph.py --impact-limit 20` to replay the bundled Slack/Git/doc fixtures into the JSONL logs and DocIssue store. Pass `--skip-impact` only if you truly want to omit DocIssues.
- Confirm data freshness via `python scripts/cerebros.py status activity-graph`; it prints counts + timestamps for `slack_graph.jsonl`, `git_graph.jsonl`, and `doc_issues.json`.
- With those stores populated, `/cerebros summarize cross-system signals for billing checkout` surfaces a multi-modal payload (Git PR #118, Slack #billing-checkout complaints, doc:billing-plan-config). The UI renders three source pills (Git/Slack/Doc) because the Activity Graph provided each modality’s evidence.
- Re-run the seeding script whenever you tweak `data/synthetic_*` fixtures—the command is idempotent and safe while Neo4j/Qdrant are running locally.

## Seeded multi-modal scenarios
The investigations store (`data/live/investigations.jsonl`) now ships with four ready-to-demo incidents so Option 1 answers have real evidence and structured fields. You can verify coverage by running:

```
pytest tests/api/test_seed_incidents.py
```

Key scenarios surfaced by `/api/incidents` and `/cerebros`:

- **High activity, low dissatisfaction – Core API rollout.** Summary “Core API rollout is hot but still healthy.” `activity_score ≈ 72`, multiple Git/Slack evidence entries, but `dissatisfaction_score < 10`. Hit `GET /api/incidents?component_id=comp:core-api&limit=5` or ask `/cerebros why is core-api so active without complaints?`.
- **High dissatisfaction – Billing support spike.** Summary “Billing service complaints tied to stale quota copy.” `dissatisfaction_score > 90` with support + Slack evidence and DocPriority pointing at `docs/billing_flows.md`.
- **Cross-system break – payments-edge schema drift.** Summary “Payments edge schema change broke billing dependencies.” Includes a populated `dependencyImpact` block and `graph_query.downstreamBlast` so the dashboard’s Cypher panel renders immediately.
- **Doc drift only – docs portal pricing copy.** Summary “Docs portal drift: pricing copy still old.” Activity score < 25 but DocPriorities populated so Option 1 can still recommend fixes even when Git/Slack are quiet.

Each seeded incident already contains `activity_signals`, `dissatisfaction_signals`, `activity_score`, `dissatisfaction_score`, doc priorities, and multi-source evidence, so the Option 1 panels render without additional manual seeding.

## Schema design & rationale
- **Components & services.** Canonical metadata lives in `configs/dependency_map.yaml`. Each `component` declares `repo`, `artifacts`, `docs`, endpoints, and dependency edges (e.g., `comp:payments` depends on `comp:auth`). These records fuel the planner/catalog that `ActivityGraphService` relies on when it normalizes identifiers or traverses downstream edges.
- **Docs.** Every doc node references both its repo path and the APIs/components it documents. When the impact pipeline flags drift, `DocIssueSignalsExtractor` can immediately project the issue back to the owning component because the relationships are already in the map.
- **Signals.** Slack and Git ingestion write JSONL lines via `SignalLogWriter` (`src/ingestion/loggers.py`). Each record captures `component_ids`, timestamps, and type-specific metadata (`event_type`, `properties`). This lightweight schema matches exactly what `GitSignalsExtractor` and `SlackSignalsExtractor` expect, so Activity Graph reads can tail logs without hitting GitHub or Slack again.
- **Edges & usefulness.** The schema explicitly links Conversations → Components, GitEvents → Components/APIs, Docs → Components/APIs, and Components → DocIssues. That structure lets Activity Graph explain why a component is noisy (“25 Git events plus 60 unresolved DocIssues in FastAPI Core”) and gives the dashboard direct links back to the underlying evidence.

See:
- `configs/dependency_map.yaml` (component/service/doc definitions and dependency edges)
- `src/ingestion/loggers.py` (JSONL schema enforced by `SignalLogWriter`)
- `src/activity_graph/service.py` (scoring, caching, quadrant math)

## Scoring model (Option 1)
- **Slack signals.** Each conversation mapped to a component contributes `0.4` activity points, while messages classified as complaints contribute `0.9` dissatisfaction points. Both values live under `activity_graph.scoring.slack` in `config.yaml`, so ops teams can up/down-weight chatter versus verified complaints per workspace.
- **Git signals.** Commits default to `0.8` activity points and PRs land at `1.2`, reflecting their higher blast radius. These weights (under `activity_graph.scoring.git`) stack with the Git event counts returned by `GitSignalsExtractor`.
- **DocIssues.** The dissatisfaction channel with the highest leverage. The severity ladder maps `critical/high/medium/low` issues → `3.0/2.0/1.2/0.5` multipliers, so an unresolved critical DocIssue will dominate the dissatisfaction score until it is resolved.
- **Time decay.** The scoring layer applies a recency multiplier before summing the signals: `<1h = 1.0`, `<24h = 0.7`, `<7d = 0.4`, `<30d = 0.15`, `>30d = 0.1`. This keeps `/activity/snapshot` and the Cerebros reasoner focused on what is happening now, while still allowing older issues to influence the baseline.
- **Trend delta.** After computing the current window score, ActivityGraphService replays the same formula against the prior window (default `7d`) and exposes `trend_delta = current_activity - previous_activity`. A positive delta means the component is heating up; negative means the team has cooled things down.

## Signal ingestion & storage
1. **Slack ingest → JSONL.** `activity_graph.slack_graph_path` in `config.yaml` defaults to `data/logs/slash/slack_graph.jsonl`. Whenever `/slash_slack` runs with `graph_emit_enabled`, it appends Conversation nodes + component IDs to that file. `SlackSignalsExtractor` simply scans this JSONL within the requested `TimeWindow`.
2. **Git ingest → JSONL.** `/slash_git` and the Git auto-ingest flow share the same schema. `activity_graph.git_graph_path` (default `data/logs/slash/git_graph.jsonl`) receives one line per commit/PR, including `event_type` (`commit`/`pr`), repo, and normalized `component_ids`. `GitSignalsExtractor` first attempts to satisfy a query from this log before falling back to live GitHub (`LiveGitDataSource`) if a cache miss occurs.
3. **DocIssues from Impact Pipeline.** Option 2 writes structured DocIssues to the file configured via `activity_graph.doc_issues_path` (resolved from either `activity_graph.doc_issues_path` or `activity_ingest.doc_issues.path`, defaulting to `data/live/doc_issues.json`). `DocIssueSignalsExtractor` converts those per-component issue lists into severity-weighted dissatisfaction scores that show up immediately in `/activity-graph/*` responses.

All three stores are append-only JSON/JSONL blobs, so they can be archived, replayed, or tailed by other jobs without coupling to a database.

## Query interface (examples)

### “What’s the current activity level around component X?”
Request:
```
GET http://localhost:8000/activity-graph/component?component_id=comp:fastapi-core&window=7d&debug=1
```

Response (from the live FastAPI Core snapshot):
```json
{
  "component_id": "comp:fastapi-core",
  "component_name": "FastAPI Core",
  "activity_score": 25.0,
  "dissatisfaction_score": 63.0,
  "trend_delta": 2.5,
  "git_events": 25,
  "slack_conversations": 0,
  "slack_complaints": 0,
  "open_doc_issues": 60,
  "time_window_label": "last 7 days",
  "debug_breakdown": {
    "git_commits_score": 25.0,
    "git_prs_score": 0.0,
    "slack_conversations_score": 0.0,
    "slack_complaints_score": 0.0,
    "doc_issues_score": 63.0
  }
}
```
`debug=1` exposes the exact contribution from each signal so that weight tuning in `config.yaml` is data-driven.

### “Which features are seeing the most dissatisfaction?”
Request:
```
GET http://localhost:8000/activity-graph/top-dissatisfied?limit=3&window=7d
```

Response (trimmed to the top three items):
```json
{
  "time_window": "last 7 days",
  "limit": 3,
  "results": [
    {
      "component_id": "comp:fastapi-core",
      "dissatisfaction_score": 63.0,
      "git_events": 25,
      "open_doc_issues": 60
    },
    {
      "component_id": "docs.payments",
      "dissatisfaction_score": 28.0,
      "git_events": 4,
      "open_doc_issues": 38
    },
    {
      "component_id": "docs.notifications",
      "dissatisfaction_score": 28.0,
      "git_events": 4,
      "open_doc_issues": 38
    }
  ]
}
```
Any result can be inspected further by calling `/activity-graph/component` with the returned `component_id`. Frontend panels (e.g., `ActivityGraphPanel` in `oqoqo-dashboard`) call the same endpoints, so CLI, UI, and Cerebros share identical data.

## Multi-repo view of the same scenario

When you run the Option 2 example (`core-api → billing-service → docs-portal`), Activity Graph immediately reflects the DocIssues emitted by ImpactPipeline. The canonical curl output looks like this:

```bash
curl "$CEREBROS_API_BASE/activity-graph/top-dissatisfied?limit=5"
```

```json
{
  "time_window": "last 7 days",
  "limit": 5,
  "results": [
    {
      "component_id": "core.payments",
      "component_name": "Core API Contracts",
      "activity_score": 12.0,
      "dissatisfaction_score": 18.5,
      "git_events": 6,
      "open_doc_issues": 9
    },
    {
      "component_id": "billing.checkout",
      "component_name": "Billing Service",
      "activity_score": 8.4,
      "dissatisfaction_score": 11.0,
      "git_events": 3,
      "open_doc_issues": 6
    },
    {
      "component_id": "docs.payments",
      "component_name": "Docs Portal – Payments",
      "activity_score": 2.0,
      "dissatisfaction_score": 7.5,
      "git_events": 0,
      "open_doc_issues": 5
    }
  ]
}
```

The snapshot endpoint highlights the same trio with formatted cards that the dashboard reuses:

```bash
curl "$CEREBROS_API_BASE/activity/snapshot?limit=5"
```

```json
{
  "git": [
    {"repo": "core-api", "title": "6 git events", "message": "core-api touched the payment contract.", "id": "activity-git-core.payments"},
    {"repo": "billing-service", "title": "3 git events", "message": "billing-service updated its client.", "id": "activity-git-billing.checkout"}
  ],
  "slack": [
    {"channel": "#impact-alerts", "text": "5 doc issues + 0 slack complaints for docs.payments", "matchedComponents": ["Docs Portal – Payments"]}
  ],
  "timeWindow": "last 7 days"
}
```

Because `/activity-graph/*` and `/activity/snapshot` both pull from the same JSONL signal logs plus the live DocIssue store, you can trust that the dashboard and CLI agree on which components heated up after the synthetic change.

## Scalability discussion
- **JSONL-first persistence.** Because Slack/Git logs are raw JSONL, it is easy to batch-move older windows into `data/archives/` or S3 while leaving a hot working set on disk. `SignalLogWriter` already normalizes component IDs, so historical backfills can be replayed verbatim.
- **Snapshots vs. recomputation.** `ActivityGraphCache` caches `ComponentActivity` keyed by component + window, which keeps `/activity-graph/component` low-latency even when GitHub is slow. Batch jobs (e.g., nightly cron) can warm those caches or write periodic snapshots to disk for offline analytics.
- **Scaling ingestion sources.** Adding more repos/channels is configuration-only: extend `activity_ingest.git.repos` or `activity_ingest.slack.channels`, and the same JSONL schema absorbs the traffic. If logs outgrow local storage, point `activity_graph.slack_graph_path`/`git_graph_path` at a mounted object store or pipe through Fluent Bit.
- **Graph-store expansion.** When Neo4j or another graph DB is enabled, the same component/doc nodes are ingested via `GraphIngestor`, so teams can migrate from JSONL to a clustered graph without rewriting Activity Graph logic.
- **BFS depth limit.** `ImpactAnalyzer` still enforces `impact.default_max_depth`, so even with dozens of repos the downstream BFS remains bounded; Activity Graph simply consumes the resulting DocIssues. Adding repos increases the number of component IDs in the JSONL logs, not the complexity of each `/activity-graph/*` call.

