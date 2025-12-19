# Option 1 Demo Guide

## Run the API

```
uvicorn api_server:app --reload
```

Or with Python module syntax:
```
python3 -m uvicorn api_server:app --reload
```

The Activity Graph service is initialized inside the FastAPI app (using live `/slack` + `/git` signals and the new caching layer).

## Endpoints

### Component snapshot
```
curl "http://localhost:8000/activity-graph/component?component_id=core.payments&window=7d"
```
Returns the `ComponentActivity` JSON:

```json
{
  "component_id": "core.payments",
  "component_name": "Core Payments",
  "activity_score": 4.5,
  "dissatisfaction_score": 1.0,
  "git_events": 4,
  "slack_conversations": 1,
  "slack_complaints": 1,
  "open_doc_issues": 0,
  "time_window_label": "last 7 days"
}
```

### Top dissatisfied components
```
curl "http://localhost:8000/activity-graph/top-dissatisfied?limit=3&window=7d"
```
Returns:
```json
{
  "time_window": "last 7 days",
  "limit": 3,
  "results": [
    { "...": "ComponentActivity payload" }
  ]
}
```

## Optional CLI

`PYTHONPATH=$PWD python scripts/demo_activity_graph.py --component core.payments --window 7d`

`PYTHONPATH=$PWD python scripts/demo_activity_graph.py --top 3 --window 7d`

## End-to-End Activity Graph Demo

**Step 1 – introduce a signal spike**

- In Slack, post a quick complaint (or run `/slack docdrift core.payments "Checkout button broke again"`). This lands in `data/logs/slash/slack_graph.jsonl`.
- Optionally add a doc issue using your preferred seeder (or append one to `data/synthetic_git/doc_issues.json`) so dissatisfaction spikes too.

**Step 2 – run the CLI**

```
PYTHONPATH=$PWD python scripts/demo_activity_graph.py --component core.payments --window 7d --debug
```

You’ll see weighted scores plus the new `debug_breakdown`:

```json
{
  "component_id": "core.payments",
  "activity_score": 5.8,
  "dissatisfaction_score": 3.1,
  "debug_breakdown": {
    "git_events_score": 3.2,
    "slack_conversations_score": 1.6,
    "slack_complaints_score": 2.0,
    "doc_issues_score": 1.1
  }
}
```

**Step 3 – open the dashboard component view**

- Visit `http://localhost:3000/projects/<projectId>` and select `Core Payments` in the new Activity Graph pane.
- The panel mirrors the CLI data (activity/dissatisfaction, git/slack/doc counts). Add a screenshot or Loom and drop it here.

**Step 4 – show hotspots**

```
curl "http://localhost:8000/activity-graph/top-dissatisfied?limit=3&window=7d"
```

The same top-three list is now visible in the dashboard “View hotspots” list, with quick links to each component detail page.

## Notes

- `/slack` and `/git` are both live-data capable, so the Activity Graph pulls real signals.
- Cache hits/misses + metrics (`/activity-graph/metrics`) confirm warm caches and latency.
- Full design + scoring rationale lives in `docs/activity_graph.md`.

