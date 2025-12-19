# Oqoqo Drift Dashboard

DocDrift-inspired dashboard that lets Oqoqo teams configure monitored repos, visualize documentation drift, and explore cross-service dependencies before Cerebros automation is wired up.

## Vision & Intent

- **Multi-source intelligence:** Normalizes Git, docs, Slack, tickets, and support signals into a single activity graph so we can ask “what changed?” across every system, not just docs.
- **Component-centric truth:** Every repo, doc section, and ticket ultimately anchors to a component/API node so we can show drift, activity, dissatisfaction, and dependency impact per node.
- **Cross-system divergence:** Surfaces when sources disagree (e.g., Git vs docs vs Slack sentiment) via badges, prioritized drift issues, and impact views.
- **Independent yet integrable:** Ships as a standalone Next.js app on port `3100`, keeping Cerebros (port `3000`) untouched while still exposing deep links and config exports Cerebros can ingest later.

## Stack

- **Next.js 16 / App Router / TypeScript**
- **Tailwind CSS 3.4** with shadcn/ui primitives (buttons, dialogs, tabs, tables)
- **Zustand** store for mock data + filters
- **Recharts** mini timeline for component activity graph

## Scripts

| command             | description                                             |
| ------------------- | ------------------------------------------------------- |
| `npm run dev`       | local dev server on `http://localhost:3100` (default)   |
| `npm run dev:3000`  | optional server on `http://localhost:3000` if needed    |
| `./oq_start.sh`     | convenience script that runs `npm run dev` on port 3100 |
| `npm run build`     | production build (`next build`)                         |
| `npm run start`     | serve the production build                              |
| `npm run lint`      | `eslint . --max-warnings=0`                             |
| `npm run typecheck` | `tsc --noEmit` for CI type safety                       |
| `npm run smoke:api` | Backend/API smoke verifier (Neo4j/Cerebros alignment)   |
| `npm run smoke:pages` | Playwright smoke covering `/graph` + `/settings`     |

## Environment

- Create `.env.local` and set:
  - `NEXT_PUBLIC_CEREBROS_API_BASE` → FastAPI host (e.g. `http://localhost:8000`)
  - `NEXT_PUBLIC_CEREBROS_APP_BASE` → Cerebros web UI (required for “Open in Cerebros” deep links)
  - `SLACK_BOT_TOKEN` / `SLACK_TOKEN` → Required for live ingest + `npm run check:data` sanity checks
- `NEXT_PUBLIC_BRAIN_UNIVERSE_URL` → Brain view entry (defaults to `/brain/universe`, point at `http://localhost:3100/brain/neo4j/` if you run the Cerebros UI separately)
- When running in live mode, keep `NEXT_PUBLIC_OQOQO_MODE=atlas` so the dashboard fetches `/api/activity` instead of loading the synthetic fixtures.
- `INCIDENTS_DEMO_MODE=1` (optional) → enable local incident fallback when the Cerebros backend is unavailable. The API routes will read `../data/live/investigations.jsonl` so incidents promoted via Slash still appear even if `/api/incidents` times out.
- `INCIDENTS_DEMO_SOURCE=/absolute/or/relative/path.json` (optional) → override the file the fallback reads (handy if you export incidents to a different location).

## Information Architecture

| Route | Purpose |
| ----- | ------- |
| `/projects` | Workspace home with lightweight project cards, doc health snapshot, and entry to each project’s **Today** view. |
| `/projects/:id` | Today view summarizing doc health, top issues, and recent activity; other tabs (issues, graph, components, impact, configuration) stay accessible for deeper work. |
| `/projects/:id/components` | Activity-graph list of components with activity/drift/dissatisfaction scores. |
| `/projects/:id/components/:componentId` | Component signal drill-down with timeline, tabs, and connected nodes. |
| `/projects/:id/impact` | Cross-system dependency map + change impact cards for toy multi-repo scenarios. |
| `/projects/:id/configuration` | Sources table + repository matrix + export CTA, with dataset probes tucked behind Diagnostics. |
| `/projects/:id/issues/:issueId` | Deep-linkable issue view for Cerebros hand-offs. |

Each view has a shareable URL so Cerebros can deep-link (e.g. `/projects/atlas/components/comp:atlas-core`).

## Test matrix

Run the following before sending changes out (or simply `npm run verify:dashboard`):

1. `npm run lint`
2. `npm run typecheck`
3. `npm run test` (Vitest synthetic contract + component suites)
4. `npm run smoke:api -- --project project_atlas`
5. `npm run smoke:pages` (spins up the app in synthetic mode and drives `/projects/project_atlas/graph` + `/settings`)
6. `npm run build`

This keeps import mistakes (like missing UI primitives) and page-level regressions from slipping through.
<br />_First run only:_ `npx playwright install chromium` to download the browser binary used by the smoke tests.

## Mock Data Model

`src/lib/mock-data.ts` houses realistic sample data:

- `projects`: doc health, repo matrix, linked systems, change impacts, and optional `cerebrosProjectUrl` for deep links.
- `components`: activity graph scores + timeline points for activity/drift/dissatisfaction plus optional `defaultDocUrl` / `cerebrosComponentUrl`.
- `docIssues`: severity, linked code paths, cross-signal counts, and optional `cerebrosUrl` + `sourceLinks` (Git/Slack/Ticket/Docs deep links).
- `dependencies` & `changeImpacts`: toy upstream/downstream edges showing how Service A affects docs in Services B/C.
- `useDashboardStore`: Zustand store that seeds mock data, tracks filters, and serializes monitored-source config for future Cerebros ingestion.

### Hydration stability

- The synthetic dataset reads a single clock from `NEXT_PUBLIC_MOCK_SNAPSHOT_EPOCH` (or `MOCK_SNAPSHOT_EPOCH`) so that server-rendered HTML matches the client bundle byte-for-byte. Set this env var in `.env.local` if you want to preview a different snapshot; otherwise it defaults to `2025-01-15T00:00:00.000Z`.
- `/src/tests/hydration.mock-data.test.ts` reloads the mock data module twice to ensure the snapshot stays identical; run `npm run test -- src/tests/hydration.mock-data.test.ts` after tweaking fixtures.
- `HydrationDiagnostics` (`src/components/system/hydration-diagnostics.tsx`) remains mounted globally and emits `hydration.clean` or `hydration.extension-attrs` events so we can detect browser extensions or stray attributes that might break React hydration.
- Some browser extensions (notably ones that add `bis_skin_checked` or `bis_register` attributes) mutate the DOM between SSR and hydration; the root layout now strips those attributes both immediately and via a short `MutationObserver`, but if the warning reappears, re-launch the dashboard in an extension-free profile to confirm before filing an issue.

## UI primitives & layout

- `src/components/layout/app-shell.tsx` groups navigation into **Workspace / Projects (Today) / Systems & impact / Configuration & ops** and keeps the doc-health sidebar card minimal (name, score, last updated).
- `src/components/projects/project-card.tsx` renders the simplified project card (doc health, issue summary, last updated, optional “hot” component, and Ask Oqoqo / Cerebros CTA).
- `src/app/(dashboard)/projects/[projectId]/page.tsx` owns the **Today** view: header pills, “Top issues to fix first”, a 10-item activity timeline, and the existing issue detail sheet hook.
- `src/app/(dashboard)/projects/[projectId]/issues/page.tsx` shows compact issue cards (severity, status, component, signal summary, last activity) plus deep-link chips sourced from `sourceLinks`/`cerebrosUrl`.
- `src/app/(dashboard)/projects/[projectId]/graph/page.tsx` introduces a lighter component detail panel (doc health, open issues, last activity, top issue, Ask Cerebros) with advanced metrics hidden behind a collapsible section.
- `src/app/(dashboard)/projects/[projectId]/configuration/page.tsx` surfaces a sources table + export CTA up front and pushes dataset probes / snapshot preview into a Diagnostics accordion.

## Future Cerebros Integration

- **Config export**: `/projects/:id/configuration` exposes an “Export JSON” button that writes the monitored repos/branches/doc paths exactly how a Cerebros agent would read them.
- **Deep links**: URLs cover projects, components, issues, and impact views so Cerebros can route operators back into the dashboard.
- **Graph hooks**: UI nodes (components, docs, tickets, chat channels) map cleanly to graph nodes/edges; adding real data simply requires swapping the mock store for API calls.

## Getting Started

```bash
npm install
./oq_start.sh
```

Open `http://localhost:3100/projects` and explore the toy data set. The sidebar includes a **Brain** entry—clicking it should land you on `NEXT_PUBLIC_BRAIN_UNIVERSE_URL` (or `/brain/universe`, which now redirects to `http://localhost:3100/brain/neo4j/`). Update `src/lib/mock-data.ts` or the `useDashboardStore` hydration logic to plug in real signals. Run `npm run dev:3000` if you temporarily need the legacy port.
