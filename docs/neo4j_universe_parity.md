# Neo4j Universe Parity Findings

Date: 2025-12-07

## Current API slice (`/api/graph/relationships/about-component`)

Source: `GraphDashboardService.get_about_component_relationships()` in `src/graph/dashboard_service.py` (lines 399-430, 816-880).

Key constraints:
- Hard-codes `depth=1` and only traverses `ABOUT_COMPONENT` relationships.
- Limits to **<=3 components** when no explicit `componentId` list is given.
- Only pulls events whose label is in `RELATIONSHIP_DEMO_EVENT_LABELS` (SlackEvent, SlackThread).
- Applies a `node_limit` of 50 and truncates both events and relationships to that size.
- Ignores repositories, services, API endpoints, docs, PRs, etc.
- Omits relationship metadata beyond `ABOUT_COMPONENT`, so no additional activity edges appear in UI.

Effect in UI:
- `BrainUniverseView` hits this endpoint (see `frontend/components/BrainUniverseView.tsx`) and therefore only ever sees ~25 nodes (3 components + Slack/Git events) even when more exist in Neo4j.
- Modalities filter currently hard-coded to `all / slack / git` because other modalities never arrive from the server.

## Neo4j Browser baseline (`MATCH (n) RETURN n LIMIT 25`)

- Includes **all labels** present in the database (Components, Services, APIEndpoints, Docs, GitEvents, SlackEvents, SupportCase, Repository, etc.).
- Shows edges of multiple types: `HAS_COMPONENT`, `DOC_DOCUMENTS_COMPONENT`, `TOUCHES_COMPONENT`, `EXPOSES_ENDPOINT`, etc., resulting in richer “activity” context.
- Node limit is a simple 25 rows but edges are not aggressively truncated, so the visual graph shows far more relationships than the dashboard slice.

## Root Cause of Parity Gap

1. **API query scope** – current endpoint intentionally narrows to ABOUT_COMPONENT edges and Slack/Git modalities, so labels like Repository/Service never appear.
2. **Hard node/edge cap** – truncation at 3 components/50 events prevents results from matching `MATCH (n) LIMIT 25` counts.
3. **UI endpoint** – BrainUniverseView still calls the limited slice instead of the richer `neo4j_default` query that already exists in `_query_neo4j_default_graph`.
4. **Missing filters** – because the payload never contains repo/doc modalities, the UI lacks controls for them.

## Implications for Implementation Plan

- Need to expose the existing `neo4j_default` snapshot mode via API so the frontend can request the same node/edge pool as the browser.
- Update BrainUniverseView to point at the new endpoint and surface richer modalities (Slack, Git, Doc issues, Repos, etc.).
- Enhance edge rendering so activity relationships remain readable even with larger graphs.
- Add fixtures (option two) that include cross-repo edges to validate repo dependency storytelling.

These findings justify the subsequent steps in the attached implementation plan.

## Local environment wiring (Dec 2025 audit)

| Surface | Base URL | Controlling env | Source file(s) | Notes |
| --- | --- | --- | --- | --- |
| FastAPI (graph + APIs) | `http://127.0.0.1:8000` | `BACKEND_HOST`, `BACKEND_PORT`, `NEXT_PUBLIC_API_URL` | `master_start.sh`, `frontend/lib/apiConfig.ts` | `master_start.sh` defaults both the backend host/port and `NEXT_PUBLIC_API_URL`. `GraphExplorer`/`BrainUniverseView` call `getApiBaseDiagnostics()` which prefers `NEXT_PUBLIC_API_URL` but falls back to `http://localhost:${DEFAULT_API_PORT}` when the browser is served from 3000/3100. |
| Cerebros UI (Graph Explorer) | `http://localhost:3300` | `MASTER_PORT` / `FRONTEND_PORT` (defaults 3300) | `master_start.sh` | Running `bash master_start.sh` launches Next dev at 3300. `/brain/neo4j` renders `GraphExplorer` with `mode="neo4j_default"` and the API base resolved above. |
| Drift dashboard redirect | `http://localhost:3100/brain/universe` → `NEXT_PUBLIC_BRAIN_UNIVERSE_URL` | `NEXT_PUBLIC_BRAIN_UNIVERSE_URL` (redirect) and `NEXT_PUBLIC_BRAIN_GRAPH_URL` (iframe page) | `oqoqo-dashboard/src/app/brain/universe/page.tsx`, `.../brain/neo4j/page.tsx`, `oq_start.sh` | `oq_start.sh` defaults to port 3100 and auto-exports `NEXT_PUBLIC_CEREBROS_API_BASE`. Set `NEXT_PUBLIC_BRAIN_UNIVERSE_URL` and `NEXT_PUBLIC_BRAIN_GRAPH_URL` to `http://localhost:3300/brain/neo4j/` so both the redirect and embedded view land on the Cerebros UI. |
| Shared deep links | `NEXT_PUBLIC_CEREBROS_APP_BASE`, `NEXT_PUBLIC_CEREBROS_API_BASE` | `.env.local` for `oqoqo-dashboard` | `oqoqo-dashboard/README.md`, `oq_start.sh` | Deep-link buttons and project cards use these envs to point back to Cerebros; `oq_start.sh` guarantees the API base but the app base must be set manually when needed. |
| CORS allowlist | `http://localhost:3000/3100/3300`, `http://127.0.0.1:3000/3100/3300` (http+https) | `API_ALLOWED_ORIGINS` override (optional) | `api_server.py` lines ~158-187 | Default `allowed_origins` already include Cerebros (3300) and the dashboard (3100). Set `API_ALLOWED_ORIGINS` if testing from another host. |

### Graph fixture controls

- `BRAIN_GRAPH_FIXTURE` (default `live`) governs whether FastAPI responds with real Neo4j data or deterministic fixtures. It is passed from `master_start.sh` into the uvicorn invocation.
- Supported values (see `src/graph/fixtures.py`): `deterministic` (two components + Slack/Git/Repo edges), `empty`, and `live`.
- `ENABLE_TEST_FIXTURE_ENDPOINTS=1` exposes `/api/test/graph-fixture` so you can toggle fixtures without restarting.
- Frontend e2e tests set `NEXT_PUBLIC_GRAPH_TEST_HOOKS=1` to reveal extra diagnostics inside `GraphExplorer`.

### Recommended local matrix

1. Set envs (both `frontend/.env.local` and `oqoqo-dashboard/.env.local`):
   - `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`
   - `NEXT_PUBLIC_BRAIN_UNIVERSE_URL=http://localhost:3300/brain/neo4j/`
   - `NEXT_PUBLIC_BRAIN_GRAPH_URL=http://localhost:3300/brain/neo4j/`
   - `NEXT_PUBLIC_CEREBROS_API_BASE=http://127.0.0.1:8000`
2. Optionally export `BRAIN_GRAPH_FIXTURE=deterministic` before `master_start.sh` to guarantee sample data.
3. Run `MASTER_PORT=3300 bash master_start.sh` (serves backend on 8000 + Cerebros UI on 3300) and, in another shell, `cd oqoqo-dashboard && ./oq_start.sh` (dashboard on 3100).
4. Verify the wiring:
   - `curl http://127.0.0.1:8000/api/brain/universe/default?limit=25` → should return nodes/edges with `access-control-allow-origin: http://localhost:3300`.
   - Load `http://localhost:3300/brain/neo4j/` directly, then access `http://localhost:3100/brain/universe` to confirm the redirect lands on the same graph view.
   - Use DevTools → Network to ensure the browser issues `GET /api/brain/universe/default?mode=neo4j_default` and the payload matches the curl output.

Keeping this mapping handy prevents duplicate env definitions and explains which port each UI expects.

## Brain env catalog (Dec 2025)

| Env var | Default / source | Runtime consumer(s) | Notes |
| --- | --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `.env`, exported via `master_start.sh` | `frontend/lib/apiConfig.ts`, `frontend/app/brain/neo4j/page.tsx`, `shared/brain-graph-ui/GraphExplorer.tsx` | Preferred API origin for GraphExplorer. Falls back to `http://localhost:${NEXT_PUBLIC_API_PORT}` when unset. |
| `NEXT_PUBLIC_API_PORT` | `.env` (`8000`) | `frontend/lib/apiConfig.ts` | Guides the automatic fallback in `getApiBaseDiagnostics()`. |
| `NEXT_PUBLIC_GRAPH_TEST_HOOKS` | `master_start.sh` defaults to `0` | `shared/brain-graph-ui/GraphExplorer.tsx` | Enables request preview + diagnostics while developing the brain UI. |
| `BRAIN_GRAPH_FIXTURE` | Export before `master_start.sh` | `api_server.py` → `graph_dashboard_service` → `src/graph/fixtures.py` | `deterministic` guarantees a two-component slice with Slack, Git, and repo edges. |
| `ENABLE_TEST_FIXTURE_ENDPOINTS` | `master_start.sh` defaults to `1` | `/api/test/graph-fixture` | Lets operators toggle fixtures without restarts when `BRAIN_GRAPH_FIXTURE` is active. |
| `NEXT_PUBLIC_BRAIN_UNIVERSE_URL` | `oqoqo-dashboard/.env.local` | `oqoqo-dashboard/src/app/brain/universe/page.tsx`, `nav-data.ts` | Redirect target for the Drift dashboard brain entry; point it at `http://localhost:3300/brain/neo4j/`. |
| `NEXT_PUBLIC_BRAIN_GRAPH_URL` | `oqoqo-dashboard/.env.local` | `oqoqo-dashboard/src/app/brain/neo4j/page.tsx` | Allows `/brain/neo4j` in Drift to embed the Cerebros UI (also defaults to 3300). |
| `NEXT_PUBLIC_CEREBROS_API_BASE` | `.env.local` + exported inside `oq_start.sh` | `oqoqo-dashboard` API routes and issue cards | Keeps Drift’s API calls pointed at the same FastAPI instance as Cerebros. |
| `NEXT_PUBLIC_CEREBROS_APP_BASE` | `.env.local` when deep links are required | `oqoqo-dashboard` deep-link components | Not strictly required for the brain view but ensures “Open in Cerebros” buttons resolve to the same UI (`http://localhost:3300`). |

### UI → API → Neo4j flow

1. Drift (`oqoqo-dashboard`) reads `NEXT_PUBLIC_BRAIN_UNIVERSE_URL`/`NEXT_PUBLIC_BRAIN_GRAPH_URL` and redirects both `/brain/universe` and `/brain/neo4j` to `http://localhost:3300/brain/neo4j/`, so users always land on the Cerebros GraphExplorer surface.
2. `frontend/app/brain/neo4j/page.tsx` renders `GraphExplorer` with `mode="neo4j_default"` and obtains the API base via `getApiBaseDiagnostics()`, which prefers `NEXT_PUBLIC_API_URL` but gracefully falls back to `http://localhost:${NEXT_PUBLIC_API_PORT}` when the browser is already on a known dev port.
3. `GraphExplorer` builds requests to `/api/brain/universe/default` (endpoint path in `shared/brain-graph-ui/GraphExplorer.tsx`) and includes filters such as `limit`, `modalities`, and `snapshotAt`.
4. FastAPI receives the request in `api_server.py#get_brain_universe_default`, hard-sets `mode="neo4j_default"`, and forwards the call to `GraphDashboardService.get_graph_explorer_snapshot()`. When `BRAIN_GRAPH_FIXTURE=deterministic`, the service short-circuits into `src/graph/fixtures.py.fixture_graph_payload()`; otherwise it queries the live Neo4j slice via `_query_neo4j_default_graph`.
5. All responses inherit the project-wide CORS policy (`api_server.py` lines 158-189) so browsers served from `http://localhost:3100` or `3300` can hit the FastAPI origin without extra configuration.

## Fixture + service verification (2025-12-07)

- Exported `BRAIN_GRAPH_FIXTURE=deterministic` and `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` before running `MASTER_PORT=3300 bash master_start.sh`. The script reported backend PID `96221` (port 8000) and frontend PID `96505` (port 3300).
- Started Drift with `NEXT_PUBLIC_BRAIN_UNIVERSE_URL`, `NEXT_PUBLIC_BRAIN_GRAPH_URL`, and `NEXT_PUBLIC_CEREBROS_API_BASE` exported inline: `cd oqoqo-dashboard && NEXT_PUBLIC_BRAIN_UNIVERSE_URL=… ./oq_start.sh`. Next.js confirmed the dev server on `http://localhost:3100`.
- `curl http://127.0.0.1:8000/api/brain/universe/default?limit=25` returned the deterministic payload (6 nodes / 5 edges across Component, SlackEvent, GitEvent, Repository labels), proving the fixture contains meaningful data for the Neo4j default slice.
- `curl -s -D - -o /dev/null -H "Origin: http://localhost:3300" http://127.0.0.1:8000/api/brain/universe/default?limit=25` showed `access-control-allow-origin: http://localhost:3300`, aligning with the documented CORS defaults.
- `curl -I http://127.0.0.1:3300/brain/neo4j/` responded `200 OK`, and `curl -I http://127.0.0.1:3100/brain/universe` returned `307 Temporary Redirect` with `location: http://localhost:3300/brain/neo4j/`, confirming both Cerebros and Drift UIs observe the updated env wiring.
- The verified wiring (8000 API, 3300 Cerebros UI, 3100 dashboard) plus the deterministic fixture ensures `/api/brain/universe/default` consistently renders the nodes/edges required for Neo4j parity. Troubleshooting tip: if GraphExplorer throws “Unable to determine API base URL,” re-export `NEXT_PUBLIC_API_URL` or delete stale `.next` caches so the envs hot-reload.

