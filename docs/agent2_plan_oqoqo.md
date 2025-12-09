# Agent 2 Plan – Oqoqo Dashboard & Infrastructure

## Scope
- **External dependency hardening** – Cerebros, GitHub, Slack, Neo4j, Qdrant client wrappers plus ingest helpers (`oqoqo-dashboard/src/lib/ingest/*`, `src/lib/config.ts`).
- **Next.js API stability** – `/api/activity`, `/api/doc-issues`, `/api/impact/*`, graph snapshot + alert feeds (`oqoqo-dashboard/src/app/api/**`).
- **Graceful UI degradation** – Dashboard tiles, charts, and detail views that consume the APIs (`oqoqo-dashboard/src/components/**`, `src/lib/ui/**`).
- **Error/result contracts** – Shared envelopes + mode/fallback semantics aligned with Agent 1’s Cerebros runtime.
- **Logging + telemetry** – Minimal structured logs and counters for failure diagnostics (`src/lib/logging.ts`, server utilities).

## Work Areas

| Area | Problem | Proposed Fix | Effort | Priority |
| --- | --- | --- | --- | --- |
| External dependency hardening | Upstream calls (Cerebros/GitHub/Slack/Qdrant/Neo4j) lack timeouts, retries, or structured envelopes, so failures bubble up as unhandled errors. | Introduce resilient client wrappers with AbortController timeouts, bounded retries, and `{ status, data, error, meta }` return objects that never throw. | M | Tier 0 |
| Next.js API stability | API routes proxy upstream responses directly and may emit HTML/stack traces, causing UI crashes and inconsistent schemas. | Refactor `/api/activity`, `/api/doc-issues`, `/api/impact/*`, and graph snapshot routes to normalize outputs, always send JSON, and plumb fallback metadata from the hardened clients. | M | Tier 0 |
| Graceful UI degradation | React components assume `status==="OK"` and crash/render empty charts when data is missing or stale. | Update hooks/components to branch on `status`, render Unavailable/Not Found states, label synthetic fallbacks, and guard visualizations against empty datasets. | S | Tier 0 |
| Error/result consistency | No agreed contract between Agent 1 Cerebros responses and dashboard expectations, so mode/fallback meanings drift. | Adopt shared status schema across clients + APIs, embed `mode`, `liveStatus`, `fallbackReason`, and ensure dashboards interpret them uniformly. | S | Tier 0 |
| Logging + telemetry | Failures only appear in console logs; no provider/endpoint context or counts for degraded states. | Add structured logging helper capturing `provider`, `endpoint`, `status`, `errorType`, `project/component` plus lightweight metrics for retries/fallbacks. | S | Tier 0 |
| Testing & verification | Existing tests cover legacy stubs only and miss degraded scenarios. | Expand API + UI test suites to simulate upstream outages/timeouts/rate limits and verify JSON envelopes + degraded rendering. | M | Tier 0 |

## Shared Contracts with Agent 1

| Condition | Expected Shape | Meaning |
| --- | --- | --- |
| Service Offline | `{ status: "UNAVAILABLE", error, data: null }` | Upstream unreachable or timed out; UI must degrade gracefully without breaking. |
| 404 | `{ status: "NOT_FOUND" }` | Missing repo/project/component; show “Not Found” state. |
| OK | `{ status: "OK", data: … }` | Normal flow; downstream consumers may render charts/tables. |

## Deliverables
1. Updated `docs/agent2_plan_oqoqo.md` with scope definition, work areas, and shared contracts.
2. Implementation tickets covering external clients, hardened API routes, graceful UI handling, and logging/telemetry hooks.
3. Regression tests for the stabilized flows (API + UI) plus smoke checks ensuring `/api/activity?mode=atlas` returns valid JSON even under dependency failures.

