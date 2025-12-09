# Slash Command Flow & Test Notes

## Architecture overview

### UI entrypoints
- The chat surface (`frontend/components/ChatInterface.tsx`) calls `sendMessage` from `useWebSocket` whenever the user submits text (including `/slack …` or `/git …`), immediately clearing the local input and showing a “Processing…” status if the last message in flight is a status event (`ChatInterface.tsx` lines 240‑305 and 293‑300).
- `useWebSocket` maintains the `/ws/chat` connection, maps server events into `Message` objects (including `slash_slack_summary` payloads), and streams plan events (`plan`, `plan_update`, `plan_finalize`) so the plan rail can transition from pending → running → completed (`frontend/lib/useWebSocket.ts` lines 1‑400 and 330‑430).

### Backend entrypoint
- `/ws/chat` (`api_server.py` lines 4400‑4585) accepts each WebSocket JSON payload, records telemetry, and forwards the raw user text to `agent.run(...)`, passing callbacks (`send_plan_to_ui`, `send_step_*`) so downstream components can stream plan progress back to the UI.

### Slash command interception
- `agent.run` short-circuits messages that start with `/` by instantiating `SlashCommandHandler` (`src/agent/agent.py` lines 3177‑3305). It emits a synthetic plan (“interpret” → “execute”) via `SlashPlanProgressEmitter` so the UI always shows task disambiguation even before the slash assistant replies.
- `SlashCommandHandler` (`src/ui/slash_commands.py` lines 1000‑1190) parses the command, dispatches to the deterministic assistant, and returns a structured payload (`type: "result"` with `result` body or `type: "error"`). `/slack` routes to `SlashSlackOrchestrator.handle`, `/git` routes to `SlashGitAssistant.handle`.
- If a slash handler needs to fall back (e.g., to the general agent), it returns `{ "type": "retry_with_orchestrator" }`, which `agent.run` bubbles back to `api_server.py` so the backend can re-submit a natural-language prompt to the main orchestrator (see `api_server.py` lines 1641‑1667).

### `/slack` flow
- `SlashSlackOrchestrator` (`src/orchestrator/slash_slack/orchestrator.py`) parses the command into a `SlashSlackQuery`, chooses an executor (`ChannelRecapExecutor`, `ThreadRecapExecutor`, `DecisionExecutor`, etc.), and calls `SlashSlackToolingAdapter` to pull channel history, thread replies, or search results from Slack (live) or synthetic JSON fixtures.
- Each executor produces a summary + sections (topics, decisions, tasks, references) and metadata about the channel/time window. The orchestrator optionally calls `DocDriftReasoner` for documentation references and emits a payload shaped like `{ "type": "slash_slack_summary", "message": "...", "sections": {...}, "context": {...} }`.
- `SlashCommandHandler` wraps that payload in `{ "type": "result", "agent": "slack", "result": <payload> }`. `useWebSocket.mapServerPayloadToMessage` detects `result.type === "slash_slack_summary"` and renders the specialized Slack card (per `frontend/lib/useWebSocket.ts` lines 140‑189).

### `/git` flow
- `SlashGitAssistant` (`src/agent/slash_git_assistant.py` lines 24‑400) handles routing for repo summaries, commits, branch context, and doc-drift lookups. It can:
  - Invoke `DocDriftReasoner` when keywords like “drift/docs/vat” appear, formatting the reasoning output into a status + details block.
  - Call `SlashGitPipeline` (`src/slash_git/pipeline.py`) to pull graph-aware commit/PR data, then format it via `SlashGitLLMFormatter`.
  - Fall back to deterministic tool invocations (commit list, branch info, tag listing) through the `GitMetadataService`.
- The assistant returns `{"status": "...", "message": "...", "final_result": {...}}`, which `SlashCommandHandler` wraps for WebSocket delivery. The UI renders it like any assistant message while the plan rail shows each slash step (interpret → execute) transitioning to “completed”.

## Canonical slash test inputs

| Command | Purpose | Expected signals |
| --- | --- | --- |
| `/slack what's the latest in #incidents?` | Channel recap sanity check | Channel recap executor fetches `#incidents` messages, summary references actual message authors/topics, plan rail moves interpret→execute→done, summary + preview not empty. |
| `/slack summarize billing complaints in #support` | Targeted drift context | Search executor pulls billing/Atlas mentions, decision/task sections cite quota mismatch, metadata tags include channel + time window. |
| `/slack summarize the thread https://slack.com/archives/C123/p1234567890123456` | Thread recap permalink | Thread executor resolves channel + TS, summary mentions participants, context includes `thread_ts`, preview covers the thread. |
| `/slack list action items about atlas billing last 48h` | Decision/task extraction | Decision/task executor emits task bullets containing assignee or follow-up phrasing, sections.tasks populated, context time window spans 48h. |
| `/slack search incidents mentioning "quota drift" across channels` | Cross-channel search | Search executor returns matches from multiple configured channels, references show channel labels + permalinks, summary states match count. |
| `/git what changed recently in the billing-service repo?` | Commit/PR listing | Git pipeline snapshot includes latest commits/PRs, summary reports counts + branch, data.snapshot.commits non-empty. |
| `/git compare pr 42 against main for core-api` | PR/branch compare | Assistant routes to PR handler, details list head/base branches, summary references PR title/author, files_changed appears in payload. |
| `/git doc drift around Atlas billing docs?` | Doc drift reasoning | DocDriftReasoner response mentions `docs/pricing/free_tier.md` / `src/pages/Pricing.tsx`, `data.doc_drift` non-empty, metadata.slash_route = `slash_git_assistant`. |
| `/git show commits mentioning rate limit spikes last week` | Commit keyword search | Commit search tool filters by text/time, summary states number of matches, data.commits items cite message excerpts containing “rate limit”. |
| `/git what changed in core-api since release/2024.10` | Alternate repo summary | Snapshot references `core-api` component, includes authors/files touched, ensures multi-repo catalog entries resolve. |

Use these as regression queries in backend tests (FastAPI client) and UI/WebSocket tests (Playwright or RTL). A PASS requires: no infinite “Processing…” spinner, plan steps reach “completed”, payload references real data (channels, commits, doc issues), and no fallback to the generic agent unless explicitly logged as a retry. 

## Observability quick reference

- **Backend log location:** `logs/master-start/backend.log` (when running via `master_start.sh`) or `api_server.log` when launching `python api_server.py`. Tail this file to watch `[SLASH PLAN] …` entries that now emit every plan update, including `/youtube`’s `fetch_transcript` and `synthesize` steps.
- **Transcript ingestion telemetry:** Slash YouTube emits `[SLASH YOUTUBE] Fetching transcript…` and `…Transcript ready…` lines from `src/agent/slash_youtube_assistant.py` whenever it calls the transcript API. Pair these with the `[VECTOR SEARCH] Indexed …` lines from the vector service logger to confirm embeddings landed in Qdrant.
- **Plan/UI parity:** If the plan rail stalls, grep for the session ID in `backend.log`. You should see the `plan` + `plan_update` WebSocket logs (from `src/utils/api_logging.py`) and the mirrored `[SLASH PLAN]` lines. Missing `fetch_transcript` or `synthesize` entries now point directly to the offending phase.

