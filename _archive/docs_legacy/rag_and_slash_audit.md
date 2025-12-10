# RAG + Slash Subsystem Audit

## 1. Document Indexing & Search (FAISS path)
- **Indexer contract** – `[src/documents/indexer.py](/Users/siddharthsuresh/Downloads/auto_mac/src/documents/indexer.py)` always expands `documents.folders` from `config.yaml` unless an explicit folder list is provided by an internal agent. The `/slash index` handler in `/ws/chat` never parses arguments, so user-provided paths are silently ignored and only the baked-in folders (currently `tests/data/test_docs`) are ever re-embedded.
- **Change detection** – Indexed files are tracked via `metadata.pkl`, but the `file_mtime` tolerance is ±1 second (L253-L268). Editing a document inside a synced drive can result in mtimes that differ by <1 second, so stale embeddings stay in FAISS until a manual `data/embeddings` wipe.
- **Storage gap** – The FAISS index + metadata live under `data/embeddings/`, yet there is no health or capacity check tied to `/api/universal-search`. If FAISS fails to load (corrupt file, permission issue), `DocumentIndexer._initialize_index` logs and creates an empty IndexFlatIP but `/api/universal-search` still returns 200 with zero results.
- **Telemetry** – `/api/universal-search` wraps spans via `telemetry/config.py`, but the front-end never sends a correlation ID. There’s no log linking a user query back to the folder set, ingest timestamp, or DocIndexer stats, so debugging “missing file” reports requires tailing FAISS logs manually.

## 2. Spotlight `/files` + `/folder` experience
- `CommandPalette.performSearch` (`frontend/components/CommandPalette.tsx` L1010-L1079) always calls `${baseUrl}/api/universal-search?q=…&limit=10` without passing the slash prefix, folder hints, or `types=document`. The backend therefore searches documents *and* images even when the user specifically chooses `/folder`, and it cannot narrow results to a workspace/project scope.
- `config.yaml` contains `universal_search.security.allowed_paths_only=true`, but the handler never enforces it—`_generate_breadcrumb` merely truncates paths. Any file indexed under `documents.folders` is exposed regardless of the caller’s workspace.
- The search response lacks ingest metadata (`file_mtime`, embedding age, folder name). `LauncherHistoryPanel` cannot show “Indexed 3 days ago” badges, which contributes to user distrust when `/slash file` surfaces stale snippets.

## 3. `/slash index` lifecycle
- `/ws/chat` (≈L4510) only checks whether the incoming message *equals* `/index` (case-insensitive). Any arguments (e.g., `/index ~/Projects/docs`) remain in `stripped_message` but `get_orchestrator().reindex_documents` is invoked without them, so users think they targeted a folder even though the system ignored it.
- Indexing runs inside `asyncio.to_thread` with a single cancellation event, but no heartbeat/telemetry is propagated back to the UI. The launcher only sees a “processing…” `status` message and then silence until success/failure, contradicting `docs/spotlight_ux_findings.md` which calls for multi-step progress.
- When reindexing finishes, the backend sends a generic status update yet the frontend doesn’t invalidate cached `/api/universal-search` results. Users still see the old FAISS hits until they close/reopen the launcher.

## 4. Slash Slack orchestration risks
- `SlashSlackParser` accepts free-form commands but `_resolve_channel_id` (`src/orchestrator/slash_slack/orchestrator.py` L271-L290) silently falls back to `default_channel_id` from config when resolution fails. The user is never told that their requested `#incident-xyz` wasn’t found—`SlashSlackToolingAdapter` logs a warning, yet the LangGraph state continues with the wrong channel.
- Slack API failures (rate limits, 5xx) are caught inside the adapter and re-raised, but there is no retry/backoff policy per executor. A transient `httpx.TimeoutException` cancels the entire slash task and leaves the launcher in a “failed” status without guidance.
- Telemetry is limited to logger statements; no OpenTelemetry spans or metrics exist for `fetch_channel_messages`, `fetch_thread`, or `search_messages`. As a result, `/slash slack` latency spikes can’t be correlated with Slack rate limits or analyzer bottlenecks.
- The orchestrator writes synthesized sections/graphs, but the payloads exceed the `CommandPalette` display budget. When the backend returns >12 preview messages, `LauncherHistoryPanel` truncates them without warning, so users cannot inspect the evidence backing the summary.

## 5. Slash file/folder semantics
- `/files` and `/folder` are modeled as “special UI” commands in `[frontend/lib/slashCommands.ts](/Users/siddharthsuresh/Downloads/auto_mac/frontend/lib/slashCommands.ts)` but the backend has no dedicated handler. Everything funnels through the universal search REST call. Consequently:
  - `/folder` should list directories or allow navigation, yet the UI simply runs semantic search over documents.
  - `/files` is expected to scope to the active project (per `docs/spotlight_ux_findings.md`), but without session context or config scoping, results mix personal fixture files with work repos.
- No analytics event differentiates organic search vs `/files`, so we cannot measure fail rates or empty-result frequency.

### Immediate Stabilization Targets
1. Add folder + ingest metadata to FAISS entries and include them in `/api/universal-search` responses; switch frontend to pass an explicit `scope` parameter derived from `/files ……`.
2. Emit structured progress updates during `/slash index` (queueing, parsing, embedding, completion) and cache-bust the FAISS client in the frontend once indexing succeeds.
3. Introduce channel resolution warnings + retries in `SlashSlackParser/BaseSlackExecutor` and wire spans around Slack API calls for observability.
4. Gate `/files` results by `documents.security.allowed_paths` and expose a configuration mismatch warning when the launcher runs outside those roots.

Findings flow into `docs/stability_audit.md` and the two-day plan.

