# UX Inventory – March 2025

| Surface | Route | Owner | Primary purpose | Signals surfaced | Notes |
| --- | --- | --- | --- | --- | --- |
| Overview hero | `/projects/:id` | Dashboard Agent | At-a-glance drift severity + impacted components | Live DocIssues, signal totals, divergence alerts | Should remain concise; heavy ingest metrics moved to config page |
| Live Drift Inbox | `/projects/:id/issues` | Dashboard Agent | Prioritize DocIssues by severity/source/time | DocIssue list with filters + deep links | Shares filters with hero + component view |
| Component Explorer | `/projects/:id/components/:componentId` | Dashboard Agent | Drill into a component’s activity/drift/dissatisfaction | Git/Slack/Ticket/Support source events, live issues | ActivityService card optional (Cerebros) |
| Graph view | `/projects/:id/graph` | Dashboard Agent | Visualize dependencies + DocIssues | Component nodes, DocIssue nodes, ticket/support signals | Ready for Neo4j feed swap; instrumentation added |
| Operator diagnostics | `/projects/:id/configuration#live-inspector` | Operator Agent | Inspect ingest health, dataset reachability | Source counts, dataset status probes | Linked from overview hero |
| Configuration export | `/projects/:id/configuration` | Dashboard Agent | Produce canonical export for Cerebros | Project metadata, monitored sources | Mode + dataset refs now inline |
| Activity ranking | `/projects/:id/activity` | Cerebros Agent | Show top components by activity score | Cerebros ActivityService feed | Optional slash command CTA |
| Project switcher | `/projects` | Dashboard Agent | Choose workspace / add new project | Project cards summary | Should stay lightweight—future settings go to configuration |

### Overlaps & friction

- Live drift info appears in overview, inbox, component, and graph views. Filters now sync via store, but copy/states should stay consistent.
- Operator panels (ingest inspector, dataset probes) were duplicated; now centralized under configuration > diagnostics.
- Graph view, component detail, and activity ranking each link to external systems; deep-link badges should follow same token set.

### Opportunities

- Collapse hero metrics + inbox into a single “prioritize + triage” page for demos.
- Treat configuration + diagnostics as a single “sources” hub with action-driven layout.
- Keep graph + impact surfaces aligned with future Neo4j feed to avoid double-work.


