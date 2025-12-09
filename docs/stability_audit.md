# Cerebros & Oqoqo Stability Audit

## Executive Summary
- Launcher and desktop surfaces share no `session_id`; `CommandPalette` and `ChatInterface` each open a `/ws/chat` connection, so task status chips desync and `/stop` requests only cancel one client (`frontend/components/CommandPalette.tsx`, `frontend/components/ChatInterface.tsx`, `frontend/lib/useWebSocket.ts`).
- `frontend/lib/useWebSocket.ts` returns early on `plan_finalize`, so the “processing” indicator never clears and history panels never get the terminal assistant message (`docs/cerebros_flow_map.md` details the lifecycle).
- `/api/universal-search` queries the entire FAISS index without folder scoping or ingest metadata, while `/slash file` just forwards `/files …` text to the same endpoint. Users cannot constrain search to configured folders nor diagnose stale embeddings (`api_server.py`, `src/documents/indexer.py`, `frontend/components/CommandPalette.tsx`).
- Prompt stack still advertises 60+ AppleScript agents (Maps, WhatsApp, Keynote) and enforces `compose_email` delivery workflows, even though the live product routes everything through slash automations. LangGraph wastes tokens planning artifacts it cannot execute (`prompts/system.md`, `prompts/tool_definitions.md`, `prompts/task_decomposition.md`).
- Oqoqo API routes fall back to synthetic data whenever Cerebros, Slack, or Git fetches fail, but the JSON payload never flags the degradation. Operators have no way to tell whether the dashboard is live or fixture mode (`oqoqo-dashboard/src/app/api/activity/route.ts`, `src/lib/mode.ts`).
- Oqoqo ingest helpers fetch GitHub/Slack data without timeouts, retries, or logging sinks. Rate limits or workspace issues quietly drop entire signal groups, leading to empty cards with no banner (`oqoqo-dashboard/src/lib/ingest/git.ts`, `src/lib/ingest/slack.ts`).
- Quick wins for Day 1: wire `session_id` through launcher/desktop, fix `plan_finalize` handling, scope `/api/universal-search` by configured folders with basic telemetry, add explicit synthetic-mode banners in Oqoqo, and add fetch timeouts + structured errors to the Next.js API routes.

## Cerebros – Findings

### Architecture Overview
- Spotlight launcher (`frontend/app/launcher/page.tsx`) instantiates `CommandPalette` and coordinates Electron window locks via `desktop/src/main.ts`. Expanded mode hosts `ChatInterface` with its own WebSocket.
- `CommandPalette` multiplexes deterministic commands (`frontend/lib/useCommandRouter.ts`), slash file search, and WebSocket chat in a ~2.6 k line component; no shared store exists for plan state or task queueing.
- Backend WebSocket handler (`api_server.py` @ `/ws/chat`) spins up sessions via `SessionManager` and streams plan events from LangGraph (`src/workflow.py`, `src/agent/agent.py`), but it generates a random `session_id` unless the client supplies one.

### Bug-Prone Flows
- **Launcher ⇄ Expanded View** – Because each surface opens a fresh WebSocket and never shares `session_id`, `/stop` or `/clear` issued in one window does not affect the other. History panels show stale turns until both tabs reconnect (`docs/cerebros_flow_map.md`).
- **Plan finalize** – `frontend/lib/useWebSocket.ts` short-circuits on `plan_finalize`, so the `PlanState` never transitions to `completed|failed`. `LauncherHistoryPanel` (`frontend/components/LauncherHistoryPanel.tsx`) keeps showing the running plan halo indefinitely.
- **Queued submissions** – When the socket is down, `CommandPalette` locks the Electron window, enqueues the submission, then immediately unlocks. If the backend reconnects slowly, the UI hides while the task still enqueues, violating the documented state machine (`docs/WINDOW_VISIBILITY_STATE_MACHINE.md`).

### Prompt System & Tool Descriptions
- `prompts/system.md` and `prompts/tool_definitions.md` assume a macOS automation stack (Mail, Maps, WhatsApp, Keynote) and force `compose_email` in any plan containing “send/email”. The live runtime no longer exposes most of these AppleScript agents, so LangGraph produces plans that call nonexistent tools and stall.
- Doc Insights, Slash Slack, `/api/universal-search`, and activity graph providers are absent from the prompt catalog. The planner therefore tries to route Slack recaps through generic `synthesize_content` steps instead of the dedicated slash orchestrator (`src/orchestrator/slash_slack/orchestrator.py`).
- `prompts/task_decomposition.md` requires multi-step JSON for all tasks, expanding even simple `/slack summarize #incidents` requests into six-step workflows (search → report → Keynote → compose_email), inflating latency and hallucinations (`docs/prompt_inventory.md`).

### RAG / Slash Indexing
- Document ingestion (`src/documents/indexer.py`) only respects the folders hardcoded in `config.yaml`; `/slash index` ignores user-provided paths because `/ws/chat` treats anything other than `/index` as a normal chat message. Users think they scoped indexing, but the backend silently reuses the default fixture path.
- FAISS metadata stores `file_mtime`, but `/api/universal-search` never returns ingest timestamps or folder identifiers. The UI cannot warn when results come from stale embeddings or unexpected directories.
- There is no telemetry linking `/slash file` queries to underlying FAISS hits—`telemetry/config.py` sets up OpenTelemetry exporters, yet `frontend/lib/logger.ts` posts to `/api/logs`, which is unimplemented, so structured console logs never leave the browser.

### State Management & UI Coupling
- `CommandPalette` owns nearly all spotlight UI state, including slash list, history pane, preview panel, and plan chips. Minor JSX tweaks often break voice recording, slash detection, or plan telemetry because everything shares the same React component.
- `LauncherHistoryPanel` slices `messages` per render and assumes `planState` updates. When `plan_finalize` fails to fire, the panel spams Electron `openExpandedWindow()` prompts even though no plan is running.
- Desktop expand animation (`frontend/components/DesktopExpandAnimation.tsx`) shows status steps from a local array; it never consumes real plan progress or ingest status, so users see canned messaging even when the desktop bundle is still connecting.

### Error Handling, Logging, Telemetry
- Frontend logger batches to `/api/logs`, but no such FastAPI route exists, so telemetry is effectively console-only. Server-side, `telemetry/config.py` initializes OpenTelemetry, yet `/api/universal-search` is the only handler that emits spans.
- WebSocket errors (`manager.connect`) log to the backend but do not propagate to the client; `CommandPalette` simply retries silently, resulting in “stuck processing” indicators without actionable errors.
- `desktop/src/main.ts` enforces window lock contracts, but nothing on the frontend enforces `lockWindowVisibility()`/`unlockWindowVisibility()` pairings. Missing `finally` blocks leave the launcher invisible until the process is restarted.

## Oqoqo Dashboard – Findings

### Architecture Overview
- Next.js API routes under `oqoqo-dashboard/src/app/api` hydrate dashboard tiles by calling Cerebros (`/activity/snapshot`, `/api/graph/snapshot`), live ingest helpers (`src/lib/ingest/*`), Doc Issues providers, and Neo4j metrics.
- `src/lib/config.ts` validates `.env` and builds the ingest configuration; `src/lib/mode.ts` toggles between synthetic, atlas, or hybrid runtime modes.
- Client components consume these API responses but have no explicit telemetry or banners to indicate data quality.

### Live Data & API Fragility
- `src/app/api/activity/route.ts` fetches live snapshots, but on any error it either drops into `fetchLiveActivity` (Git/Slack ingest) or synthetic fixtures without flagging the downgrade. The `mode` field changes to `"synthetic"`, yet the UI never surfaces this difference.
- No fetch timeouts or retries exist for Cerebros/Neo4j calls. A hung upstream request ties up the Next.js worker, and the frontend simply displays an empty state.
- `getIngestionConfig()` requires Git and Slack tokens even for synthetic-only demos, making `npm run dev` brittle.

### Ingest & Data Quality
- Git ingest hits GitHub REST endpoints sequentially per repo with no rate-limit handling; once `fetchJson` returns `null`, the dashboard quietly omits commits/PRs for that repo.
- Slack ingest only calls `conversations.history` once per channel, uses naive keyword matching to map messages to components, and never marks stale data when `slackFetch` fails. Negative sentiment detection is trivial string matching (“error/fail/broken”), yielding noisy signals.
- Graph snapshot hydration replays `mockProjects` for live mode but does not verify component mappings; a stale or partial snapshot results in missing doc issues without any alerts.

### Mode Handling & UX Signaling
- `allowSyntheticFallback()` defaults to whatever `NEXT_PUBLIC_ALLOW_SYNTHETIC_FALLBACK` is, but API responses never explain *why* a fallback occurred. Operators can’t distinguish between “synthetic by request” and “synthetic because Cerebros timed out.”
- Client logging writes to `console.info` when `__OQOQO_UX_DIAGNOSTICS__` is set, yet there is no centralized sink or correlation ID sent to Cerebros, so debugging production issues requires grabbing screenshots.

### Testing & Observability
- The only integration test (`src/tests/api/backend.test.ts`) exercises a legacy backend stub; there are no tests for the new API routes, ingest fallbacks, or graph merging logic.
- Neither server nor client metrics exist for ingest freshness (last Slack timestamp, last Git commit). Dashboard cards can therefore show empty states indefinitely without warning.

## Quick Wins (48 h Feasible)
1. **Session plumbing + plan finalize fix** – Thread a deterministic `session_id` from launcher to desktop, patch `useWebSocket` to process `plan_finalize`, and expose `session_id` in `/ws/chat` welcome messages so history hydration can work.
2. **Scoped search + telemetry** – Update `/api/universal-search` to honor `documents.folders`, include ingest metadata in responses, and log queries + folder scope via OpenTelemetry. Teach `/files` slash handler to pass explicit scope parameters.
3. **Prompt trimming** – Introduce a “launcher” prompt profile that advertises Doc Insights + slash toolsets, hides dormant AppleScript agents, and removes `compose_email` enforcement unless `mac_automation` is enabled.
4. **Oqoqo API hardening** – Wrap Cerebros/Slack/Git fetches with `AbortController` timeouts, return structured `{ error, fallbackMode }` payloads, and display a banner when synthetic mode is active.
5. **Ingest resilience** – Add per-source freshness metrics and warnings (e.g., “Slack data stale (3h)”), plus minimal retries/backoff for Slack and Git requests so transient failures don’t silently zero out signals.

These items seed the two-day stabilization plan and Tier 1 fixes backlog.

