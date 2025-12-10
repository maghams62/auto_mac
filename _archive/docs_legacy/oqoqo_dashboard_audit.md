# Oqoqo Dashboard Audit

## 1. Architecture Snapshot
- **Runtime** – Next.js `app/` project with API routes under `src/app/api/*`. These server actions proxy to Cerebros (`CEREBROS_API_BASE`), live ingest helpers (`lib/ingest/*`), and Neo4j/Doc Insights providers.
- **Data sources**
  - `src/lib/ingest/git.ts` & `slack.ts` fetch GitHub commits/PRs and Slack threads based on `.env` values validated in `src/lib/config.ts`.
  - `src/lib/issues/providers/*` wraps Doc issues (synthetic + Cerebros).
  - `src/lib/graph/providers/*` builds graph metrics, optionally from Neo4j.
- **Synthetic vs live** – `src/lib/mode.ts` controls “synthetic/atlas/hybrid” mode flags; `allowSyntheticFallback()` defaults to `false` unless env overrides, but API routes silently drop into synthetic mode when live calls fail.

## 2. Fragility Findings

### 2.1 Environment gating & dev ergonomics
- `getIngestionConfig()` (`src/lib/config.ts`) requires **all** Git + Slack env vars even when running in synthetic-only mode. Local `npm run dev` fails unless engineers invent dummy tokens. The API routes then log `Missing required .env values...` on every request, but the UI only shows that synthetic data is unavailable.
- There is no per-feature opt-out; e.g., the Activity route can’t skip Slack ingest while still fetching Doc Issues.

### 2.2 API route error handling
- `src/app/api/activity/route.ts` and `doc-issues/route.ts` never set fetch timeouts. If Cerebros is slow, the request hangs until Vercel’s default (edge) timeout and the client sees a 500 with no guidance.
- Synthetic fallback happens silently: when `/activity/snapshot` 502s, the route sets `mode="synthetic"` but does not include a `liveDown=true` flag in the JSON. Operators cannot tell whether they’re looking at real data or fixtures.
- `fetchGraphSnapshot` warns via `console.warn` on the server but still returns partial projects, which causes React components to render empty graphs without user-facing errors.

### 2.3 Ingest resilience
- `fetchGitEvents` makes unauthenticated GETs with `next: { revalidate: 60 }` but no retry/backoff. Hitting the GitHub rate limit returns `null` and the function simply logs a warning, so the dashboard quietly drops Git signals for that poll.
- Slack ingest (`fetchSlackThreads`) pulls the most recent 50 messages per channel with no pagination, no respect for `latest_reply`, and a naive keyword matcher. Rate limits or workspace misconfiguration merely produce `console.warn("Slack API error")`; the frontend still renders empty cards without labeling the data as stale.
- Neither ingest path sanitizes or redacts secrets before logging raw responses, so enabling debug logs risks leaking repo names or Slack text in server logs.

### 2.4 Mode & telemetry awareness
- Mode logic lives in `lib/mode.ts`, but API responses do not expose whether synthetic fallback occurred automatically. The React UI can’t display a “Synthetic fixture” banner reliably.
- Client logging (`src/lib/logging.ts`) just `console.info`s when `NEXT_PUBLIC_UX_DIAGNOSTICS` is truthy; there is no ingestion to OpenTelemetry or Cerebros telemetry backend, so analyzing UX regressions requires browser DevTools.

### 2.5 Tests & drift
- `src/tests/api/backend.test.ts` still mocks the legacy `/api/activity` shape. There are no regression tests for Doc Issues, graph metrics, or ingest fallbacks, so wiring mistakes slip through (e.g., missing headers, changed JSON shape).

## 3. Recommended Stabilization Work
1. **Config stratification**
   - Allow `OQOQO_MODE=synthetic` to bypass `GIT_*`/`SLACK_*` requirements and emit a single structured warning rather than spamming every request.
   - Introduce `LIVE_SOURCES=git,slack,docissues` toggles so partial live ingest is possible.
2. **Fetch wrappers with timeouts & errors**
   - Wrap `fetch` calls with `AbortController` timeouts (e.g., 3 s for Cerebros, 5 s for Git/Slack) and convert failures into structured JSON (`{ error: "upstream_timeout", upstream: "cerebros" }`).
   - Bubble the `mode` plus `liveStatus` flags back to the UI so components can surface “Live data degraded” banners.
3. **Synthetic transparency**
   - When fallback occurs, set `mode:"synthetic", fallbackReason:"cerebros_unreachable"` in the API response. Clients can then render a watermark.
4. **Ingest resilience**
   - Add minimal retry/backoff and per-source metrics (count, oldest timestamp) so the UI can indicate “Slack data stale (3h)”.
   - Sanitize logs (no raw Slack text) and centralize logging through a server-side telemetry hook.
5. **Testing & monitoring**
   - Update `src/tests/api/backend.test.ts` to cover the new JSON envelopes, synthetic fallback flags, and error codes.
   - Add edge tests for missing env vars, rate-limit responses, and Slack workspace misconfigurations.

These findings feed into `docs/stability_audit.md` and the stabilization backlog.

