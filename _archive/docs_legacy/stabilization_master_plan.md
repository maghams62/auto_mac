# Stabilization Master Plan

## Mission & Timeline
- **Duration:** 2 days (Day 1 = architecture + hotfixes, Day 2 = prompt hygiene, telemetry, resiliency polish).
- **Systems:** Cerebros launcher/desktop runtime, LangGraph/prompt stack, slash/RAG services, Oqoqo Next.js dashboard + ingest.
- **Success Criteria:** shared `session_id` across surfaces, reliable plan lifecycle UI, scoped `/api/universal-search` with ingest metadata, telemetry/logging wired end-to-end, Oqoqo transparently signaling live vs synthetic data, and trimmed prompts that reflect the actual tool surface.

## Shared Guardrails
- **API Contracts**
  - `/ws/chat`: accept optional `session_id` query param and echo it in welcome payload so both launcher and desktop reuse the same session memory.
  - `/api/universal-search`: accept `scope`/`folders` hints, return `folder`, `indexed_at`, and correlation IDs. Preserve backwards compatibility for the desktop UI.
  - Oqoqo API routes (`/api/activity`, `/api/doc-issues`, `/api/graph-metrics`): return `{ mode, fallbackReason?, error? }` so clients can surface banners.
- **Telemetry & Logging**
  - Adopt OpenTelemetry spans for plan lifecycle, slash search events, and Oqoqo ingest steps. Include `session_id`, `plan_id`, and `source_component`.
  - Implement `/api/logs` (FastAPI) and point `frontend/lib/logger.ts` batching there; dashboard client logs follow the same schema.
- **Testing Expectations**
  - WebSocket hooks: Jest unit tests covering plan finalize, session propagation, `/stop`.
  - FastAPI universal search + new scope: pytest coverage for folder filtering and metadata.
  - Oqoqo API routes: Next.js route tests that verify timeouts, synthetic fallback flags, and env validation.
  - Prompt snapshots: enforce golden files after trimming tool catalogs.
- **Release Hygiene**
  - Document state-machine and telemetry changes in `docs/cerebros_flow_map.md` after implementation.
  - Update `docs/two_day_stabilization.md` with actual completion notes at the end of Day 2.

## Work Streams

### Stream A – Cerebros Runtime (Agent 1)
1. **Session Synchronization & Plan Lifecycle**
   - Generate a GUID at launcher boot, persist via context/local storage, and supply to both `CommandPalette` and `ChatInterface`.
   - Fix `useWebSocket` so `plan_finalize` events update `planState` and append terminal assistant messages/status rows.
   - Propagate `/stop` across windows by broadcasting via shared session context.
2. **CommandPalette State & API Hygiene**
   - Audit queued submissions to ensure `lockWindowVisibility()`/`unlockWindowVisibility()` pairs and telemetry logs exist.
   - Remove the dead `/api/conversation/history/${sessionId}` call or add the backend route so history hydration works.
3. **Slash / RAG Improvements**
   - Honor `documents.folders` in FastAPI search, include ingest metadata, and expose correlation IDs.
   - Update `/files`, `/file`, `/folder` detection in `CommandPalette` to pass scope hints and render metadata.
   - Improve `/slash index` messaging + telemetry (progress + folder list).
4. **Prompt & Tool Alignment**
   - Produce trimmed “Launcher” profile highlighting Doc Insights + slash tools; demote dormant AppleScript agents.

### Stream B – Oqoqo Dashboard (Agent 2)
1. **API Hardening**
   - Wrap Cerebros/Slack/Git fetches with `AbortController` timeouts, structured errors, and fallback reasons.
   - Emit ingest freshness metadata (last Slack thread timestamp, last Git commit) in API responses.
2. **UI Transparency**
   - Surface banners when `mode !== "atlas"` or `fallbackReason` exists, and label stale data.
   - Centralize client logging using the shared JSON schema.
3. **Ingest Resilience**
   - Add minimal retry/backoff for Slack + Git fetch helpers and sanitize logs.
   - Gate `.env` validation by mode so synthetic demos don’t require real tokens.

### Stream C – Shared Deliverables
- `docs/agent1_plan_cerebros.md`, `docs/agent2_plan_oqoqo.md` for deep-dives and ownership.
- `/api/logs` endpoint + client integrations.
- Updated regression tests spanning WebSocket hooks, FastAPI routes, and Next.js APIs.

## Dependencies
- Session plumbing (Stream A) must land before we rely on telemetry correlation IDs in Stream B.
- Universal search metadata fields must be stable before Oqoqo consumes them.
- Prompt trimming should occur after the new tool/API surface is defined to avoid churn.

