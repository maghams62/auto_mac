# Foundation Validation – Live Snapshot Alignment

This note captures the current understanding of the dashboard schemas plus the manual validation steps for the live Atlas/Nimbus stories. It is intended to keep future graph/Neo4j work aligned with the existing model.

## Domain & Data Model Review

- `src/lib/types.ts` already defines the full contract for `Project`, `ComponentNode`, `DocIssue`, `DependencyEdge`, `ChangeImpact`, `SignalBundle`, etc. These are the only schemas we should extend.
- `ComponentNode.graphSignals` is the authoritative place for activity / drift / dissatisfaction scores. Any graph view should reuse these bundles rather than defining parallel metrics.
- `DocIssue` objects link back to `projectId`, `componentId`, `repoId`, include divergence sources, linked code, and suggested fixes. Future live issue generation must populate this exact shape.

## Ingest & Mapper Expectations

- `src/lib/ingest/index.ts` fetches Git + Slack snapshots (or reuses defaults) and feeds them into `mergeLiveActivity` (`src/lib/ingest/mapper.ts`).
- The mapper maps events to components strictly through repo associations (`component.repoIds`) and component names mentioned in Slack threads. It recalculates activity bundles, divergence insights, and source events without mutating schema definitions.
- Git-derived events feed the `activity` band of timelines, Slack-derived negative sentiment drives `dissatisfaction`, and overlap between the two produces provisional drift scores. Any live issue heuristics should read from the same enriched component objects.

## Synthetic Fixtures & Scenario Hooks

- `src/lib/mock-data.ts` remains the seed for repos, components, dependencies, and change impacts. Live snapshots layer on top but must continue to honor these IDs/relationships so that existing routes (overview, components, impact) stay consistent.
- Synthetic Git/Slack JSON references (see `datasetRefs` on each `Project`) describe the canonical Atlas/Nimbus narratives that we mirror while running real tests.

## Live Scenario Checklist

1. **Atlas VAT Drift**  
   - Push a commit or PR in a repo tied to the Atlas project that touches VAT/payment docs or APIs.  
   - Start/extend a Slack thread (e.g., `#atlas-drifts` or `#billing-eng`) complaining about VAT docs being outdated.  
   - Expected UI outcomes after refresh/polling:  
     - Project overview shows increased activity + divergence alerts for the Payments component.  
     - Component detail timeline includes the new Git commit and Slack thread.  
     - Issue list highlights a VAT-related drift item (currently mock; will shift to live heuristics in Step 2).  

2. **Nimbus Notifications Drift**  
   - Commit touching notification schemas/runbooks plus a Slack escalation in an `#nimbus-*` channel.  
   - Expect to see the same propagation across overview, component, and issue routes.  

Both scenarios were walked through manually using the existing polling flow; log output confirmed `/api/activity` hydration, and the live status pill reflected success/error states accordingly.

## Automated Test Evidence

The foundational ingest + store tests are still the guardrails:

```
npm run test   # executed 2025-11-30
```

Vitest passes (`src/lib/ingest/mapper.test.ts`, `src/lib/state/dashboard-store.test.ts`), confirming that schema alignment work did not regress existing behavior.

## Next Steps

- Use this document as the reference before implementing live-derived `DocIssue`s or the graph view.  
- When adding heuristics or node/edge builders, cite the sections above to ensure the code matches the reviewed schema.

