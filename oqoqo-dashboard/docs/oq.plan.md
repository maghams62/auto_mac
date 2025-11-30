# Oqoqo Dashboard Roadmap

_Last updated: 2025-11-30_

## Current Snapshot

- **App footprint:** standalone Next.js 16 App Router app inside `oqoqo-dashboard/` with Zustand store, Tailwind/shadcn UI kit, and doc/export helpers already wired up (`/projects/:id` views, Ask-Oqoqo stubs, shareable URLs).
- **Ingest plumbing:** `src/lib/ingest/**` fetches GitHub commits/PRs plus Slack threads via tokens in the root `.env`, merges them through `mergeLiveActivity`, and synthesizes heuristic `DocIssue`s (`live_issue-<project>-<component>`) that propagate across the dashboard.
- **Validation assets:** `docs/foundation-validation.md` captures authoritative schema contracts (`Project`, `ComponentNode`, `DocIssue`, `DependencyEdge`, etc.) while `docs/live-scenarios.md` + `scripts/validate-live.mjs` document the Atlas/Nimbus drill path for Phase 1.
- **Phase 0 blocker:** `npm run check:data` currently fails because every URL in `scripts/data-sources.json` returns HTTP 404; without restoring the synthetic datasets, downstream phases have no signal to exercise.

---

## Phase 0 – Data Sources

**Purpose:** Restore deterministic synthetic datasets so ingest plumbing has material to parse before we point at live repos/Slack exports.

**Key workstreams**

- Re-host or fix every `scripts/data-sources.json` URL so `npm run check:data` returns HTTP 200 for Git + Slack fixtures.
- Keep `.env` hydrated with `GITHUB_TOKEN`, `GITHUB_ORG`, and `SLACK_TOKEN`, because the CLI validators expect authenticated calls even for synthetic mirrors.
- Snapshot working URLs inside `docs/phase0-status.md` so future contributors know which buckets are canonical.

**Exit criteria**

- `npm run check:data` completes green.
- `data/synthetic_git/**` and `data/synthetic_slack/**` contain the repos/channels referenced by the Atlas/Nimbus scenarios.

---

## Phase 1 – Live Scenario Validation

**Purpose:** Run the Atlas VAT and Nimbus notifications flows end-to-end so the dashboard shows realistic live drift.

**Key workstreams**

- Follow `docs/live-scenarios.md` to replay commits/PRs and Slack threads against the refreshed datasets.
- Run `npm run validate:live -- --project <id>` (Atlas or Nimbus) and confirm `DocIssue` counts plus timelines match expectations.
- Exercise `/projects/:id`, `/components`, `/issues/:issueId`, and `/impact` in the UI to confirm live signals replace the mock store without layout regressions.

**Exit criteria**

- Atlas + Nimbus validations produce the documented `DocIssue` IDs.
- Operators can point Cerebros to deep links that reflect live data rather than empty states.

---

## Phase 2 – Live Issue UX Surfacing

**Purpose:** Make the overview, issue list/detail, and component explorer emphasize live divergences rather than mock placeholders.

**Key workstreams**

- Highlight severity, freshness, and divergence-source chips in the Overview and Issues pages.
- Ensure `src/components/issues/**` reads from the same derived `DocIssue` store that ingest populates so filters stay in sync.
- Add empty-state + loading UX that explains when live signals are still warming up (re-using the heuristics documented in `foundation-validation.md`).

**Exit criteria**

- `/projects/:id` and `/projects/:id/issues` surfaces clearly labeled live issues with working filters and detail drawers.
- Ask-Oqoqo stub calls return context such as “live issue count” to prove data is flowing.

---

## Phase 3 – Operator Insight

**Purpose:** Provide inspectors so operators understand what data was ingested, when, and why drift was raised.

**Key workstreams**

- Build an ingest inspector that shows the last Git/Slack fetch per source plus sample payloads (leveraging `mergeLiveActivity` output).
- Add an activity echo/timeline so teams can correlate repo pushes, Slack chatter, and documentation edits by component.
- Pipe inspector data into `docs/foundation-validation.md` as canonical examples.

**Exit criteria**

- Operators can answer “what changed?” for any component without leaving the dashboard.
- Drift heuristics explain their inputs (Git path, Slack thread link, doc path) inline.

---

## Phase 4 – Graph View (Snapshot)

**Purpose:** Visualize component/API/doc/issue topology via an in-memory graph builder so we can swap in Neo4j later without redesigning the UI.

**Key workstreams**

- Use the existing `ComponentNode`, `DependencyEdge`, and `ChangeImpact` bundles to render nodes/edges inside `/projects/:id/impact` and future `/graph` routes.
- Keep graph data local (derived from current store snapshots) while matching the shapes we expect from Cerebros or Neo4j.
- Document how the graph builder consumes `graphSignals` so future data sources can drop in.

**Exit criteria**

- Graph renders mirror the dependencies described inside the mock data + live ingest results.
- UI affordances (legend, filters, node detail, deep links) assume a future backend swap.

---

## Phase 5 – Demo Polish

**Purpose:** Land the touches that make the dashboard demo-ready once live data flows.

**Key workstreams**

- Manual refresh / “new signals” prompts so operators can retrigger ingest without redeploying (ties back to Phase 0 tooling).
- Deep-link badges, breadcrumbs, and share buttons to keep Cerebros hand-offs crisp.
- Micro-interactions (loading shimmer, severity transitions, Ask-Oqoqo empty states) that celebrate key flows without adding logic debt.

**Exit criteria**

- Demo checklist (manual refresh, doc deep links, component transitions) is fully satisfied.
- The dashboard feels production-grade even before Cerebros automation lands.

---

## Phase 6 – Config Sync & Cerebros Handshake (Future)

**Purpose:** Treat the dashboard as the visual layer while Cerebros becomes the execution brain.

**Key workstreams**

- Reuse the existing configuration export (repos, channels, doc sources) so Cerebros agents can ingest the same JSON the dashboard writes today.
- Define a stable interface so Cerebros slash commands load `Project`/`ComponentNode` mappings directly from dashboard exports.
- Align on the `DocIssue` schema so drift issues generated by Cerebros match exactly what the dashboard already renders.
- Preserve stable URLs (already true) and document the deep-link contract so Cerebros bots can bounce operators into `/projects`, `/components`, `/issues`, and `/impact` views.

**Exit criteria**

- Exported dashboard configs can be consumed by Cerebros without manual translation.
- Cerebros-generated drift issues appear in the dashboard with no shape conversion.
- Architecture note describes the “visual layer ↔ brain” handshake for future agents.

---

## Phase 7 – Neo4j-Backed Graph (Swap-In)

**Purpose:** Swap the in-memory graph snapshot with a Neo4j-backed endpoint without changing the UI.

**Key workstreams**

- Stand up an API (internal or via Cerebros) that serves node/edge snapshots sourced from Neo4j using the same shapes as `ComponentNode` + `DependencyEdge`.
- Persist graph snapshots periodically (or on demand) so the dashboard can display time-travel views without rebuilding the layout.
- Document the ingestion pipeline from live signals → Neo4j → dashboard so future engineers know where each piece of logic lives.

**Exit criteria**

- Graph view reads from a Neo4j-powered endpoint while the UI code remains untouched.
- Multi-hop dependency exploration (component → API → doc → issue) leverages Neo4j queries rather than client-side derivations.
- Cerebros reasoning about cross-system drift can reference the same graph the dashboard uses.

---

## Phase 8 – Retrieval + Semantic Context (Qdrant Integration)

**Purpose:** Show how semantic retrieval enriches drift issues without forcing the dashboard to speak directly to Qdrant.

**Key workstreams**

- Extend the `DocIssue` detail view to render optional fields (code summaries, doc excerpts, discussion snippets) that Cerebros attaches after running retrieval.
- Ensure schema changes stay backward-compatible so the dashboard can display enriched issues alongside legacy ones.
- Capture the upstream expectation: Cerebros runs retrieval over Qdrant, attaches semantic context to each issue payload, and the dashboard simply renders the provided fields.

**Exit criteria**

- Drift issues can display semantic summaries when present while degrading gracefully otherwise.
- Documentation clarifies that Qdrant lives behind Cerebros; the dashboard never ships vector DB dependencies.
- Operators see exactly where retrieval data came from (e.g., “Qdrant snippet: docs/api/payments.md”).

---

## Phase 9 – Real-Time Mode (Streaming Events) _(optional premium)_

**Purpose:** Deliver wow-factor demos where Git and Slack signals appear instantly without manual refreshes.

**Key workstreams**

- Add long-polling/SSE/WebSocket support so ingest can push “new signals” events to the UI.
- Display tasteful “live update” toasts or badge pulses when new DocIssues or Slack threads arrive.
- Ensure fallback polling still works so real-time mode remains optional.

**Exit criteria**

- Slack threads and Git pushes appear in the dashboard within seconds when the stream is enabled.
- Operators can toggle real-time mode per environment without affecting base ingest logic.

---

## Roadmap Summary

```
Phase 0 – Data Sources               (fix dataset URLs → check:data passes)
Phase 1 – Live Scenario Validation   (Atlas + Nimbus end-to-end)
Phase 2 – Live Issue UX Surfacing    (overview/issues/components emphasize live issues)
Phase 3 – Operator Insight           (ingest inspector, activity echo)
Phase 4 – Graph View (Snapshot)      (in-memory graph, ready for Neo4j)
Phase 5 – Demo Polish                (manual refresh, deep links, micro-interactions)

--- Future / Advanced ---

Phase 6 – Config Sync w/ Cerebros    (shared config → shared DocIssues)
Phase 7 – Neo4j Graph Swap-In        (dashboard reads a real graph backend)
Phase 8 – Qdrant Semantic Enrichment (Cerebros retrieval; dashboard renders)
Phase 9 – Real-Time Mode             (live updates without polling)
```

