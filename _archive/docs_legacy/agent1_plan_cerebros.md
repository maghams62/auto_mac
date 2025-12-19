# Agent 1 Plan – Cerebros Runtime & AI Stack

## Scope
- Launcher + desktop UX parity: `frontend/app/launcher/page.tsx`, `frontend/components/CommandPalette.tsx`, `frontend/components/ChatInterface.tsx`, `desktop/src/main.ts`.
- WebSocket orchestration + LangGraph plan lifecycle: `frontend/lib/useWebSocket.ts`, `/ws/chat` handler in `api_server.py`, `src/workflow.py`.
- Slash / RAG services: `/api/universal-search`, `src/documents/indexer.py`, `src/documents/search.py`, `frontend/lib/slashCommands.ts`.
- Prompt/tool catalog alignment: `prompts/system.md`, `prompts/tool_definitions.md`, `prompts/task_decomposition.md`, `src/agent/agent_registry.py`.

## Problem Statements & Proposed Fixes

| Area | Issue | Fix | Effort | Priority |
| --- | --- | --- | --- | --- |
| Session Lifecycle | Launcher and desktop each open independent `/ws/chat` sessions, so `/stop` and plan chips desync. | Generate a deterministic `session_id` when launcher mounts, store in shared context/localStorage, and append `?session_id=` to both WebSocket URLs. Echo the ID in backend welcome payload + telemetry. | M | Tier 1 |
| Plan Finalization | `useWebSocket` returns before `setMessages` when `plan_finalize` arrives, leaving UI stuck in “processing”. | Refactor handler to update `planState`, append final assistant/status message, and bubble final telemetry. Add Jest tests for the reducer. | S | Tier 1 |
| CommandPalette Submission | Queued submissions unlock the window immediately, violating the state machine; `/api/conversation/history` call 404s. | Ensure `lockWindow()`/`unlockWindow()` pairs wrap queued flush, add diagnostics logs, and either implement the history endpoint in FastAPI or remove the request + UI expectation. | M | Tier 1 |
| Slash Search Scope | `/api/universal-search` ignores `config.documents.folders`; `/files` doesn’t pass scope, and results lack ingest metadata. | Add optional `scope` params + folder filtering in FastAPI, return `folder`, `indexed_at`, `ingest_source`. Update CommandPalette slash handlers to pass scope + render metadata. | M | Tier 1 |
| `/slash index` Feedback | `/index` command ignores folder args and provides no progress telemetry. | Accept optional folder tokens in frontend, log the configured folder list in backend status updates, and emit plan/telemetry events for start/progress/completion. | M | Tier 2 |
| Prompt Drift | System/task prompts list stale AppleScript agents and force `compose_email`, causing plans to include nonexistent tools. | Create a “Launcher” prompt profile that enumerates Doc Insights, Slash Slack, universal search, etc., demote dormant AppleScript agents, and update tool definitions accordingly. | M | Tier 1 |
| Telemetry/Logging | Frontend logs try to POST to `/api/logs`, which doesn’t exist. Slash/WebSocket events lack spans/correlation IDs. | Implement `/api/logs` on FastAPI, wire `frontend/lib/logger.ts` to it, and emit OpenTelemetry spans for plan lifecycle + slash searches (session_id, plan_id). | M | Tier 2 |

## Dependencies & Coordination
- Requires backend support for `/api/logs`, slash telemetry metadata, and optional `scope` params in `/api/universal-search`.
- Agent 2 (Oqoqo) consumes the new search metadata and telemetry; coordinate on JSON schemas and fallback reasons.
- Prompt changes must align with whatever tool surface Agent 2 advertises for shared Doc Insights / activity graph APIs.

## Testing Strategy
- WebSocket: Jest tests simulating plan events (`plan`, `plan_update`, `plan_finalize`), verifying `planState` and messages update correctly.
- Universal search: pytest covering folder filtering, metadata fields, and backward compatibility.
- Slash flows: React Testing Library tests for `/files` path to ensure metadata renders and scope passes through.
- Prompt snapshots: commit updated prompt files + unit tests (if any) ensuring loader returns expected tool subset.

## Test Plan for Tier 1 Cerebros Fixes
| Area | What to Test | How to Test |
| --- | --- | --- |
| Session + WebSocket behavior | A single `session_id` is reused by launcher (`CommandPalette`) and desktop (`ChatInterface`), backend `/ws/chat`, and `/api/conversation/history/{session_id}`. History endpoints return valid empty payloads for new sessions and actual transcripts once messages have been sent. | Unit/Integration: Jest tests to ensure hooks pick up the shared session ID and append it to WS URLs; backend pytest using FastAPI `TestClient` to create a session, push events, and fetch `/api/conversation/history/{session_id}` with/without history. |
| Plan lifecycle + “stuck processing” | `plan` → `plan_update` → `plan_finalize` events advance `planState` and clear “processing”, and messages capture the final status. | Jest/Vitest tests targeting `useWebSocket` that simulate message events and assert final state/messages; backend smoke (pytest) verifying plan finalization payload structure if needed. |
| `/api/universal-search` scope & metadata | `scope`/`folders` filters actually constrain results, `folder_label`/`indexed_at` fields populate, and optional params don’t 500. | Pytest suite invoking the FastAPI route with different query strings (no filters, scope only, folders only, both) against fixture data; assert HTTP 200 and filtered payload shape. |
| Conversation history API | `/api/conversation/history/{session_id}` returns a consistent envelope for empty + populated sessions and handles bogus IDs gracefully. | Pytest coverage calling the route before/after injecting interactions, plus malformed IDs, asserting status 200 and empty arrays instead of 500. |

## Acceptance Criteria
- **Session IDs**: shared between launcher and expanded view, echoed by `/ws/chat`, and `/api/conversation/history/{session_id}` returns prior turns (or empty arrays) per session without errors.
- **Plan lifecycle**: no “stuck processing” once `plan_finalize` arrives; messages include the final plan result/status.
- **Universal search**: `scope`/`folders` filters work as intended, metadata fields are present when expected, and the endpoint tolerates missing/extra optional params without 500s.
- **Conversation history**: new sessions return empty-but-valid responses; sessions with history return stored interactions; invalid IDs don’t crash the API.

