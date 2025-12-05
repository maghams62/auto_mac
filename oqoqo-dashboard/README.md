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
| `npm run build`     | production build                                        |
| `npm run start`     | serve the production build                              |
| `npm run lint`      | `eslint . --max-warnings=0`                             |
| `npm run typecheck` | `tsc --noEmit` for CI type safety                       |

## Information Architecture

| Route | Purpose |
| ----- | ------- |
| `/projects` | Workspace to add/edit monitored projects, repos, branches, doc paths, and linked systems (Linear, Slack, Support). |
| `/projects/:id` | DocDrift-style overview with severity filters, issue list, and contextual sheet detail. |
| `/projects/:id/components` | Activity-graph list of components with activity/drift/dissatisfaction scores. |
| `/projects/:id/components/:componentId` | Component signal drill-down with timeline, tabs, and connected nodes. |
| `/projects/:id/impact` | Cross-system dependency map + change impact cards for toy multi-repo scenarios. |
| `/projects/:id/configuration` | Structured, exportable configuration Cerebros can ingest later. |
| `/projects/:id/issues/:issueId` | Deep-linkable issue view for Cerebros hand-offs. |

Each view has a shareable URL so Cerebros can deep-link (e.g. `/projects/atlas/components/comp_atlas_core`).

## Mock Data Model

`src/lib/mock-data.ts` houses realistic sample data:

- `projects`: doc health, repo matrix, linked systems, change impacts.
- `components`: activity graph scores + timeline points for activity/drift/dissatisfaction.
- `docIssues`: severity, linked code paths, cross-signal counts.
- `dependencies` & `changeImpacts`: toy upstream/downstream edges showing how Service A affects docs in Services B/C.
- `useDashboardStore`: Zustand store that seeds mock data, tracks filters, and serializes monitored-source config for future Cerebros ingestion.

### Hydration stability

- The synthetic dataset reads a single clock from `NEXT_PUBLIC_MOCK_SNAPSHOT_EPOCH` (or `MOCK_SNAPSHOT_EPOCH`) so that server-rendered HTML matches the client bundle byte-for-byte. Set this env var in `.env.local` if you want to preview a different snapshot; otherwise it defaults to `2025-01-15T00:00:00.000Z`.
- `/src/tests/hydration.mock-data.test.ts` reloads the mock data module twice to ensure the snapshot stays identical; run `npm run test -- src/tests/hydration.mock-data.test.ts` after tweaking fixtures.
- `HydrationDiagnostics` (`src/components/system/hydration-diagnostics.tsx`) remains mounted globally and emits `hydration.clean` or `hydration.extension-attrs` events so we can detect browser extensions or stray attributes that might break React hydration.
- Some browser extensions (notably ones that add `bis_skin_checked` or `bis_register` attributes) mutate the DOM between SSR and hydration; the root layout now strips those attributes both immediately and via a short `MutationObserver`, but if the warning reappears, re-launch the dashboard in an extension-free profile to confirm before filing an issue.

## UI primitives & layout

- `src/components/layout/app-shell.tsx` now centralizes global chrome:
  - `SidebarNav`: consolidates workspace + per-project navigation and owns the single `ProjectSwitcher`.
  - `LiveStatusWidget`: merges the ingest-mode pill and live-status badge into one compact status chip.
- `src/app/(dashboard)/projects/page.tsx` exposes reusable building blocks:
  - `HeroMetricsRow`: renders the four key KPIs in a consistent grid.
  - `ContextPills`: lists monitored repos alongside the Slack signal count.
  - `PrimaryActions`: bundles all primary CTA buttons (overview, impact, components) without repeating copy inline.
- `src/app/(dashboard)/projects/[projectId]/graph/page.tsx` ships a `GraphToolbar` that groups the provider badge, node/issue tabs, severity filters, and a legend popover so the visualization stays above the fold.

## Future Cerebros Integration

- **Config export**: `/projects/:id/configuration` exposes an “Export JSON” button that writes the monitored repos/branches/doc paths exactly how a Cerebros agent would read them.
- **Deep links**: URLs cover projects, components, issues, and impact views so Cerebros can route operators back into the dashboard.
- **Graph hooks**: UI nodes (components, docs, tickets, chat channels) map cleanly to graph nodes/edges; adding real data simply requires swapping the mock store for API calls.

## Getting Started

```bash
npm install
./oq_start.sh
```

Open `http://localhost:3100/projects` and explore the toy data set. Update `src/lib/mock-data.ts` or the `useDashboardStore` hydration logic to plug in real signals. Run `npm run dev:3000` if you temporarily need the legacy port.
