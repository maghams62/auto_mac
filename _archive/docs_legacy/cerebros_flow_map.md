# Cerebros Runtime Flow Map

## 1. Launcher Boot & Visibility State
- `[frontend/app/launcher/page.tsx](/Users/siddharthsuresh/Downloads/auto_mac/frontend/app/launcher/page.tsx)` owns the Spotlight-style surface. It:
  - Mounts `CommandPalette` in `"launcher"` mode and keeps it open by default.
  - Subscribes to Electron window signals via `onWindowShown/onWindowHidden` to reset input, unlock the window, and focus the text field.
  - Delegates actual window locking/unlocking to Electron helpers (`unlockWindow`, `hideWindow`) defined in `desktop/src/main.ts`.
- `[desktop/src/main.ts](/Users/siddharthsuresh/Downloads/auto_mac/desktop/src/main.ts)` enforces the `lockWindowVisibility()/unlockWindowVisibility()` contract referenced throughout `CommandPalette.tsx`. Any query submission must lock before an async call and unlock in all exit paths to avoid the “stuck hidden” bug captured in `docs/WINDOW_VISIBILITY_STATE_MACHINE.md`.

```
[Global hotkey] → Electron main lockWindowVisibility()
   ↓
[frontend/app/launcher/page.tsx] renders CommandPalette + history pane
   ↓
Window blur/hide events routed back through `unlockWindow` + state reset
```

## 2. Spotlight Query Lifecycle
1. **Input + Local Routing**
   - `CommandPalette` tracks the text field, selection state, and preview panels (~2.6k lines).
   - `handleSubmitQuery` (`frontend/components/CommandPalette.tsx` L741-L845) builds a `CommandRouterContext` and calls `routeCommand` from `[frontend/lib/useCommandRouter.ts](/Users/siddharthsuresh/Downloads/auto_mac/frontend/lib/useCommandRouter.ts)`.
   - Deterministic patterns cover Spotify controls, `/help`, `/clear`, `/stop`, and Electron-specific commands. Successful local routes emit to the telemetry bus and skip the LLM.
2. **WebSocket Submission**
   - If the router does not handle the query, `CommandPalette` uses `useWebSocket`’s `wsSendMessage` to push the query and sets `submittedQuery`/`isProcessing`.
   - When `wsConnected` is false, submissions are queued (`pendingSubmissionRef`) until the socket reconnects, but the UI still unlocks the window—causing the “phantom lock” bug when reconnection takes too long.
3. **History/Preview Surfaces**
   - `LauncherHistoryPanel` renders the last N user/assistant turns plus plan chips, but it depends entirely on `useWebSocket`’s `messages` array; no session storage or `/api/conversation/history` hydration currently works because the API route is missing.

## 3. WebSocket + Task Lifecycle
- **Endpoint**: `/ws/chat` in `[api_server.py](/Users/siddharthsuresh/Downloads/auto_mac/api_server.py)` (≈L4414) assigns or generates a `session_id`, connects `WebSocketManager`, and loads `SessionMemory`. Because neither `CommandPalette` nor `ChatInterface` passes a `session_id`, every attachment creates a random UUID and the UI believes there is a single implicit session.
- **Message Loop**:
  - Normal chat: `record_chat_event` + `agent.handle_message`.
  - Slash utilities: `/help`, `/index`, `/clear`, `/stop` handled inline before invoking LangGraph.
  - `/index` creates an `asyncio.Event` cancel hook, offloads to `get_orchestrator().reindex_documents`, and streams status updates back to the launcher.
- **Plan Events**: LangGraph responses propagate via `manager.send_plan_message`, `send_plan_update`, `send_plan_finalize`.
  - `[frontend/lib/useWebSocket.ts](/Users/siddharthsuresh/Downloads/auto_mac/frontend/lib/useWebSocket.ts)` listens for `type === "plan"` to initialize a `PlanState`, `plan_update` to mutate steps, and `plan_finalize` to mark completion/cancellation. A bug around lines 463-507 returns early on `plan_finalize`, so the later `setMessages` block never runs and the UI stays “processing”.

```
CommandPalette/ChatInterface
   │ wsSendMessage/wsSendCommand
   ▼
/ws/chat (session_id?, session memory)
   │
LangGraph workflow (`src/workflow.py`, `src/agent/agent.py`)
   │
plan → plan_update → plan_finalize events
   ▼
useWebSocket hook → planState + messages → LauncherHistoryPanel & Desktop Chat UI
```

## 4. Expanded View (Desktop)
- `DesktopExpandAnimation` overlays `CommandPalette` during the transition while the Electron desktop bundle hydrates. It reads status steps from `spotlightUi.motion`.
- When a user clicks “Expand” in `LauncherHistoryPanel`, `openExpandedWindow()` signals Electron to show the desktop window, which hosts `[frontend/components/ChatInterface.tsx](/Users/siddharthsuresh/Downloads/auto_mac/frontend/components/ChatInterface.tsx)`.
- `ChatInterface` spins up its own WebSocket connection (`getWebSocketUrl("/ws/chat")`), manages audio transcription, plan telemetry (`usePlanTelemetry`), and feedback capture. Because spotlight and desktop each own separate sockets and message stores, stopping a task in one surface does not guarantee the other surface reflects the change—especially without shared `session_id`.

## 5. Known Fragility Hotspots
- **Session Identifiers**: UI never supplies `session_id`, so `/ws/chat` generates UUIDs per connection and history hydration via `/api/conversation/history/${sessionId}` (called in `CommandPalette`) 404s.
- **Plan Finalization**: Early return in `useWebSocket` prevents messages/status chips from updating when backend sends `plan_finalize`.
- **Window Locks**: `CommandPalette` locks visibility on submit, but error/timeout/bounce paths (e.g., queued submissions) unlock immediately, allowing blur to hide the palette mid-processing, violating `WINDOW_VISIBILITY_STATE_MACHINE`.
- **History Panel**: Only consumes live `messages`; small UI edits to `Message` shape or plan payload break `LauncherHistoryPanel`, `DesktopExpandAnimation`, and telemetry because all derive from the same massively shared state blob.

These notes feed into `docs/stability_audit.md` and the stabilization backlog.

## 6. `/youtube` Flow
- Slash command routing now instantiates `SlashYouTubeAssistant`, which:
  - Parses `/youtube <url|@alias> [question]` and maintains session-scoped `VideoContext` objects inside `SessionMemory.shared_context`.
  - Fetches metadata via the YouTube Data API (or oEmbed fallback), persists MRU entries to `data/state/youtube_history.json`, and now exposes fuzzy title recall via `GET /api/youtube/history/search` (used by `/youtube` autosuggest) alongside the existing clipboard-aware `/api/youtube/suggestions`.
  - Streams transcripts via `YouTubeTranscriptService` (or hydrates from the on-disk transcript cache), pushes chunk payloads into the same universal Qdrant collection used by Slack/Git, and mirrors `Video`/`Channel`/`TranscriptChunk` nodes into Neo4j via `YouTubeGraphWriter`.
  - Answers timestamp-aware vs. semantic questions by building a `YouTubeQueryPlan` (intent classification, constraints, required outputs), retrieving the relevant chunks, and prompting `synthesize_content` to return hierarchical JSON (gist + sections + key concepts + channel notes) that the assistant renders in markdown with timestamped source cards.
- REST coverage:
  - `GET /api/youtube/videos/{session_id}` → serialized contexts + active video ID.
  - `GET /api/youtube/history/search?query=` → MRU YouTube metadata filtered by title/channel for autosuggest + clipboard/title recall.
  - `POST /api/youtube/videos/{video_id}/refresh?session_id=...` → forces transcript re-ingestion and re-indexing when captions change.
- Clipboard awareness is controlled via `youtube.clipboard.enabled` in `config.yaml`; clipboard reads never leave the local machine and only surface sanitized URLs/titles in the suggestions payload.
- `/index youtube` reads `search.modalities.youtube.video_ids` (IDs or URLs) and re-chunks those transcripts into the universal vector collection. When the list is empty, `/setup` and `/index` both report that YouTube ingestion remains manual via `/youtube`.

## 7. `/setup`, `/index`, `/cerebros`
- `config.yaml` now contains a `search` block describing each modality (enablement, scopes, weights, timeouts). `build_search_system()` in `src/search/bootstrap.py` loads that snapshot, instantiates modality handlers, and persists registry state to `data/state/search_registry.json`.
- `/setup` calls `SetupCommand` to render modality status (last indexed timestamp, config hash, errors) plus a JSON snapshot of the current configuration. Advanced flows use ` /setup detail <modality>` to inspect scopes or MRU state.
- `/index` invokes `IndexCommand`, which walks the modality registry, fans out ingestion jobs via thread pool, enforces per-modality timeouts, and updates registry state once each handler finishes (Slack/Git reuse the existing ingestors, files/youtube/web share the universal embedding schema).
- `/cerebros` routes through `CerebrosCommand`. It classifies the query, executes semantic searches per modality (Slack/Git/Files/YouTube) with their configured limits, normalizes scores, and falls back to `google_search` only when internal sources return no confident matches. Responses include a textual summary plus raw result metadata so the UI can render source cards.
- `/api/graph/query` now produces a `cerebros_answer` object that frontends can consume directly. The payload includes:
  - `answer` – the synthesized summary.
  - `option` – `"activity_graph"` (Option 1), `"cross_system_context"` (Option 2), or `"generic"`.
  - `components` – resolved/impacted component IDs.
  - `sources[]` – normalized Slack/Git/Doc/Issue chips with deep links.
  - `doc_priorities[]` (Option 1 only) – ranked documentation fixes computed with config-driven weights.
- **Option 1 narrative template**: when `option === "activity_graph"` the backend now emits a deterministic, LLM-free narrative with four blocks:
  1. **Summary** – “`<component>` docs are drifting in `<N>` areas…” with downstream impact callouts.
  2. **What’s drifting** – numbered list per doc issue showing explicit “Docs say … / Reality …” contrasts plus severity & impact, each tagged with evidence footnotes.
  3. **What to change now** – actionable doc edits derived from the drift items, again footnoted.
  4. **Evidence** – numbered Slack/Git/Doc/Impact references (the same entries exposed through `sources[]`).
  Evidence footnotes only include modalities enabled in `search.modalities` so `/cerebros` continues to respect config gating even when historical Slack chatter was attached to an issue.
- `activity_signals.weights` in `config.yaml` declares the prioritization hierarchy (git vs. issues vs. support vs. slack vs. docs). Changing the weights changes both `/cerebros` answers and dashboard prioritization without touching code.
- Slash `/cerebros` now calls the same graph reasoner when `graph.enabled` and `activity_graph` are on. When the graph stack is disabled, it falls back to the legacy semantic search implementation automatically.
- Each command now emits structured telemetry (`telemetry.config.log_structured`) describing planner decisions, ingestion successes/timeouts, and `/setup` re-index warnings. These logs land in OTLP/Grafana and in `api_server.log`, giving the graph agent and QA runs a deterministic trail for auditing.
- Phase 1 Brain Views: `/api/brain/universe` + `/brain/universe` expose chunk/source nodes in a 3D graph with modality/time filters, while `/api/brain/trace/{query_id}` + `/brain/trace/[queryId]` hydrate per-query traces (modalities, retrieved chunks, BELONGS_TO edges). `/cerebros` payloads now carry `brain_trace_url` + `brain_universe_url`, and DocIssues surface a “View reasoning path” link when that metadata is present.

