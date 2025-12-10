# Two-Day Stabilization Plan

## Objectives
1. Restore end-to-end task lifecycle visibility (session IDs, plan finalize events, launcher/desktop parity).
2. Scope slash search + RAG flows to explicit folders with telemetry so we can diagnose misses.
3. Make Oqoqo dashboards honest about data freshness by hardening API routes and surfacing synthetic fallbacks.
4. Trim the prompt/tool surface so LangGraph plans align with what the launcher can actually execute.

## Day 1 – Architecture & High-Severity Fixes

| Tier | Item | Owner | Notes / Files |
| --- | --- | --- | --- |
| T0 | ✅ Publish audit artifacts (`docs/stability_audit.md`, `docs/cerebros_flow_map.md`, `docs/rag_and_slash_audit.md`, `docs/oqoqo_dashboard_audit.md`, `docs/prompt_inventory.md`) | Codex | Already merged; baseline context for contributors |
| T1 | Thread deterministic `session_id` through launcher + desktop | FE | Generate UUID in `frontend/app/launcher/page.tsx`, pass via query/nav, reuse in `CommandPalette` + `ChatInterface`, append to `/ws/chat?session_id=` |
| T1 | Fix `plan_finalize` handling & stuck “processing” state | FE | Remove early return and ensure `setMessages` runs in `frontend/lib/useWebSocket.ts`; `LauncherHistoryPanel` should consume final status |
| T1 | Remove orphaned `/api/conversation/history/${sessionId}` call or implement matching FastAPI route | FE/BE | Either implement read API in `api_server.py` using `SessionManager`, or stop calling it from `CommandPalette` |
| T1 | Scope `/api/universal-search` to `config.documents.folders` + emit ingest metadata | BE | Add optional `scope` param, filter FAISS results by folder, include `indexed_at` + `folder` in JSON |
| T1 | Add OpenTelemetry span for each slash search (`CommandPalette.performSearch`) | FE/BE | Propagate correlation ID; log queries + folder scope |
| T1 | Harden Oqoqo API fetches with `AbortController` timeouts + structured errors | Dashboard | Wrap Cerebros/Slack/Git/graph fetches; return `{ error, upstream, fallbackMode }` |
| T1 | Surface synthetic-mode banners in Oqoqo UI | Dashboard | When `mode!=="atlas"` or `fallbackReason` present, show warning ribbon |
| T2 | Add unit tests for new session plumbing + universal search scoping | FE/BE | Jest for hooks, pytest for FastAPI route |

## Day 2 – Prompt Hygiene, Telemetry, and Stretch Fixes

| Tier | Item | Owner | Notes / Files |
| --- | --- | --- | --- |
| T1 | Create “Launcher” prompt profile that advertises Doc Insights + slash toolset only | AI | Trim `prompts/system.md` + `prompts/task_decomposition.md`; auto-generate tool list from `AgentRegistry` filtered by runtime |
| T1 | Update `prompts/tool_definitions.md` with Doc Insights, Slash Slack, `/api/universal-search`, remove dormant AppleScript agents | AI | Use `docs/prompt_inventory.md` as reference |
| T1 | Expose ingest freshness + telemetry | BE/Dashboard | Emit `ingest_metadata` (last Slack/Git timestamps) in Oqoqo APIs; show stale badges when data >1 h |
| T1 | Implement `/api/logs` in FastAPI to receive frontend batches | BE | Bind to existing OpenTelemetry exporter |
| T2 | Minimal retry/backoff for Slack/Git ingest | Dashboard | Wrap `fetchJson`/`slackFetch` with retry + exponential backoff |
| T2 | Synthetic fixtures provenance | Dashboard | Embed `fallbackReason` (`cerebros_timeout`, `slack_rate_limit`) in API responses + client UI |
| T2 | Launcher UX polish once status chips are fixed (window lock audit, history hydration) | FE | Leverage `docs/cerebros_flow_map.md` contracts |

## Dependencies & Notes
- 🔄 Session plumbing + plan finalize fix unblock Tier 1 telemetry tasks; tackle them before prompt trimming.
- 🧪 Regression tests: run `pnpm test` (frontend), `pytest` (backend), and `npm test` inside `oqoqo-dashboard`.
- 🚨 Communication: call out synthetic fallback visibility + session ID fixes in release notes so ops expect new banners/logs.
- 📊 Telemetry: once `/api/logs` exists, point `frontend/lib/logger.ts` to FastAPI base URL and ensure OTel exporter ships spans to the configured collector (`telemetry/config.py`).

## Success Criteria
- Launcher + desktop both show consistent plan completion statuses, `/stop` cancels reliably, and `/api/universal-search` results list folder + ingest metadata.
- Prompt stack no longer references unavailable AppleScript agents, and LangGraph plans rely on slash + Doc Insights instead of Keynote/email.
- Oqoqo dashboard calls out when data is synthetic or stale, with server logs showing structured reasons for fallbacks.

