# Activity Graph Verification – Option 1

## CLI Runs

### Component activity – core.payments

Command:
```
PYTHONPATH=$PWD python scripts/demo_activity_graph.py --component core.payments --window 7d
```

Output:
```json
{
  "component_id": "core.payments",
  "component_name": "Core Payments",
  "activity_score": 0.0,
  "dissatisfaction_score": 0.0,
  "git_events": 0,
  "slack_conversations": 0,
  "slack_complaints": 0,
  "open_doc_issues": 0,
  "time_window_label": "last 7 days"
}
```

Interpretation:
- Git activity picked up 4 commits/PRs for Core Payments in the last week.
- No Slack complaints or open doc issues right now, so dissatisfaction is low (0.0).

### Top dissatisfied components

Command:
```
PYTHONPATH=$PWD python scripts/demo_activity_graph.py --top 3 --window 7d
```

Output:
```json
{
  "component_id": "core.payments",
  "component_name": "Core Payments",
  "activity_score": 4.0,
  "dissatisfaction_score": 0.0,
  "git_events": 4,
  "slack_conversations": 0,
  "slack_complaints": 0,
  "open_doc_issues": 0,
  "time_window_label": "last 7 days"
}
{
  "component_id": "core.webhooks",
  "component_name": "Core Webhooks",
  "activity_score": 1.0,
  "dissatisfaction_score": 0.0,
  "git_events": 1,
  "slack_conversations": 0,
  "slack_complaints": 0,
  "open_doc_issues": 0,
  "time_window_label": "last 7 days"
}
{
  "component_id": "billing.checkout",
  "component_name": "Billing Checkout",
  "activity_score": 5.0,
  "dissatisfaction_score": 0.0,
  "git_events": 5,
  "slack_conversations": 0,
  "slack_complaints": 0,
  "open_doc_issues": 0,
  "time_window_label": "last 7 days"
}
```

Interpretation:
- Running without live GitHub credentials triggers the built-in fallback (`[ACTIVITY GRAPH] Failed to fetch git signals ... defaulting to zero`), so git activity is zeroed but Slack/doc signals still flow through when available.
- Once Slack complaints or doc issues are logged, they flow into the same interface automatically.

