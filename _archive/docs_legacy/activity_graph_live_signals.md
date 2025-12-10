# Activity Graph – Live Signals & Health Contracts

## Signal logging

- Slack ingest mirrors every channel run into the JSONL file configured by `activity_graph.slack_graph_path` (or per-channel overrides). Each record contains `component_ids`, complaint labels, timestamps, and channel metadata and is written via `SignalLogWriter`.
- Git ingest does the same for commits/PRs using `activity_graph.git_graph_path`, recording `event_type` (`commit`/`pr`), `component_ids`, repo name, and timestamps.
- Both writers normalize component identifiers to the canonical IDs defined in `configs/dependency_map.yaml` (e.g., `core.payments` aliases are stored as `comp:payments`). Synthetic fixtures continue to work, but any new surface should rely on the canonical IDs emitted here.
- Example Slack record (JSONL):

```json
{
  "component_ids": ["comp:fastapi-core"],
  "properties": {
    "timestamp": "2025-12-01T23:05:00Z",
    "channel_id": "CFASTAPI",
    "channel_name": "#fastapi-alerts",
    "labels": ["complaint"]
  }
}
```

- Example Git record (JSONL):

```json
{
  "component_ids": ["comp:fastapi-core"],
  "event_type": "pr",
  "timestamp": "2025-12-01T22:55:00Z",
  "repo": "tiangolo/fastapi",
  "properties": {
    "title": "Fix docs build",
    "pr_number": 12345
  }
}
```

## DocIssues as live input

- ImpactPipeline writes live DocIssues to the file specified by `activity_graph.doc_issues_path` (defaults to `data/live/doc_issues.json`).
- ActivityGraph’s `DocIssueSignalsExtractor` reads this file directly; enabling `impact.data_mode=synthetic` switches all paths back to the synthetic fixtures (`data/synthetic_git/**`).

## Health endpoints

- `/health/impact` now reports per-repo `{ lastRunStartedAt, lastRunCompletedAt, lastCursor, docIssuesOpen, lastError }` derived from the auto-ingest state file (`impact.auto_ingest_state_path`).
- `/activity/snapshot` first surfaces the top dissatisfied components; if no dissatisfaction is present it falls back to the most active components so the endpoint never returns `503` while live data exists.

## Packaging requirement

- The test/deploy environment needs `packaging>=24.0` (added to `requirements.txt`). Run `pip install -r requirements.txt` before executing `python3 -m pytest`.

