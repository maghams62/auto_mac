# Dashboard clarity & hydration test run

This script keeps the dashboard demo-ready by exercising the decluttered UI, deterministic timestamps, and the stabilized graph/activity surfaces.

## 0. Pre-flight
- Install + build once: `npm install && npm run lint`
- Validate dataset reachability: `npm run check:data`
- Start the dev server: `npm run dev` (keep console open to watch hydration logs)

## 1. Overview hero
1. Load `/projects/project_atlas`
2. Confirm hero shows three stats (issues, components, signals) and the detail drawer defaults closed
3. Toggle “Show signal detail” and verify severity chips, filters, divergence alerts, and ingest warnings render without shifting layout
4. Fire the manual refresh button; ensure the toast appears once and the hero highlight fades

## 2. Live drift inbox
1. Visit `/projects/project_atlas/issues`
2. Toggle severity, source, and “Live only” filters; counts in the header must update instantly
3. Expand the “Signals breakdown” accordion for a few issues and open at least one deep-link token (Git/Slack/Tickets/Support)
4. Open an issue page via the secondary CTA and ensure the detail page timeline uses the deterministic timestamp style

## 3. Component explorer
1. Open `/projects/project_atlas/components/{componentId}` for a component with live signals
2. Verify the live issue pill + Cerebros activity card load without console warnings
3. Hover the timeline chart and confirm tooltip dates use the short format
4. Expand Git/Slack/Tickets/Support tabs to ensure each “Open source” link works

## 4. Graph view
1. Visit `/projects/project_atlas/graph`
2. Confirm the loading state appears briefly on first load (no red errors)
3. Ensure the provider banner reads `Graph source • Neo4j live` (or `synthetic demo` in fallback) and shows node/edge counts
4. Toggle node filters (components/issues) and severity badges; the focus should re-center automatically
5. Click several nodes and verify related issues + ticket/support satellites update; deep-link CTAs must open new routes
6. If the dataset exceeds 150 nodes, verify the banner displays the truncation note

## 5. Activity rankings
1. Navigate to `/projects/project_atlas/activity`
2. If Cerebros API is configured, watch the live table populate; if not, confirm the fallback ranking appears with the explanatory caption
3. Force an error (e.g., block the API in DevTools) and ensure the amber warning appears while the fallback data remains available

## 6. Context surfaces
1. Open `/projects/project_atlas/issues/{issueId}`
   - Toggle the “Semantic context” card open.
   - Verify at most 3 snippets render, each with a source badge + deep link + “Hide” action.
   - Confirm the provider badge (`Context source • Qdrant live` or `synthetic demo`) is visible inside the card.
2. Open `/projects/project_atlas/components/{componentId}` and switch to the `Context` tab.
   - Ensure snippets are grouped by source and the Cerebros CTA opens the external link.
3. From the graph page, select a node and confirm the one-line context summary appears along with the “Open context tab” link.

## 7. Diagnostics + hydration
1. Go to `/projects/project_atlas/configuration#live-inspector` and confirm ingest counts + dataset probes render without mismatch warnings
2. In DevTools console search for `hydration` messages—should read either `hydration.clean` or nothing
3. Run `npm run validate:live -- --project project_atlas` followed by the Nimbus variant to capture CLI proof

## 8. Regression sweep
- `npm run test` (unit/state)
- `npm run lint` (fast guard before commit)
- Record any anomalies in `docs/testing/dashboard-clarity.md` or file issues immediately

## 9. Backend/API smoke (no UI clicks)
1. Run `npm run test -- src/tests/api/backend.test.ts`
   - Confirms `/api/activity`, `/api/graph-snapshot`, `/api/context`, `/api/context/feedback`, `/api/issues` all return 200 with the expected shape.
   - Verifies provider fallbacks by temporarily setting `GRAPH_PROVIDER=neo4j`, `CONTEXT_PROVIDER=qdrant`, `ISSUE_PROVIDER=cerebros` (the test file toggles these automatically).
2. Run `npm run smoke:api -- --project project_atlas`
   - Quick sanity check across the same APIs.
   - Fails if component IDs drift between activity, graph, and issues.
   - See `docs/testing/api-smoke.md` for details and overrides.

## 10. UI smoke (post-backend)
Once the backend checks pass:
1. Load `/projects/:id` (hero should show live stats + inline source badges, no errors).
2. Navigate to `/projects/:id/issues` → open an issue. Confirm the Semantic Context card loads with provider badge + deep links.
3. Open `/projects/:id/components/:componentId` → check the Context tab + “View in Cerebros” CTA.
4. Visit `/projects/:id/graph` → ensure the provider banner matches the active graph provider, no console errors, and node selection links work.

Mark the run complete only when all surfaces above present consistent timestamps, no hydration warnings fire, deep links succeed end-to-end, and the backend smoke passes.

