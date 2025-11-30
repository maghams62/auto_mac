# Cerebros Stable Codebase Guide

_Reference for coding LLMs and developers working on the current Raycast-style Cerebros build._

The legacy “Cerebros OS” footprint has been archived; this guide describes only the surfaces that still ship:

- Spotlight launcher (Raycast-style mini view) and the expanded desktop window (Electron + Next.js).
- Slack/Git slash command flows backed by the FastAPI server.
- Spotify playback controls embedded in the launcher and desktop footer.
- Synthetic Git/Slack fixtures plus the vector/graph helpers required by the slash flows.

Use this document with `docs/DOCUMENTATION_INDEX.md` to stay oriented.

---

## 1. Runtime Topology

| Layer | Purpose | Key Files |
|-------|---------|-----------|
| Electron shell | Hosts the launcher window, expanded desktop view, and bridges IPC to the backend. | `desktop/src/main.ts`, `desktop/src/preload.ts`, `desktop/package.json` |
| Frontend (Next.js) | Renders the launcher (`app/launcher/`), desktop (`app/desktop/`), Spotify mini player, settings modals, etc. | `frontend/app/`, `frontend/components/`, `frontend/lib/` |
| Backend (FastAPI) | Slash command orchestration, Slack/Git integrations, telemetry, caching. | `api_server.py`, `src/agent/`, `src/orchestrator/slash_slack/`, `src/services/` |
| Background data & fixtures | Synthetic Git/Slack corpora, vector store assets, cached trajectories/logs. | `data/synthetic_git/`, `data/synthetic_slack/`, `docs/development/*.md` |

Communication flow:
1. Electron launches the Next.js server (dev) or serves the static export (prod) and creates the Spotlight window.
2. Frontend uses IPC + REST/WebSocket endpoints from `api_server.py`.
3. Slash commands route through `src/orchestrator/slash_slack/orchestrator.py` and supporting agents in `src/agent/`.
4. Vector/Qdrant helpers (`src/vector/`, `docs/operations/vector.md`) power semantic search and Git storyline lookups.

---

## 2. Active Directory Map

| Directory | What’s inside |
|-----------|---------------|
| `desktop/` | Electron wrapper: window lifecycle (`src/main.ts`), preload bridge, packaging scripts, and platform docs (`desktop/README.md`, `desktop/BUILD_AND_DEPLOY.md`). |
| `frontend/` | Next.js app (App Router). `app/launcher/` renders the Spotlight UI, `app/desktop/` renders the expanded view. Shared UI lives in `components/`, telemetry hooks in `lib/`. |
| `src/agent/` | Python agents invoked by slash commands (Git, Slack, Spotify helper, etc.). `src/agent/agent.py` wires prompts + caches. |
| `src/orchestrator/slash_slack/` | Planner/execution graph that converts `/git` and Slack commands into agent calls. |
| `src/services/` | Long-running services: `github_pr_service.py`, `branch_watcher_service.py`, `chat_storage.py`, `context_resolution_service.py`. |
| `src/vector/` | Vector service factory plus Qdrant adapters. |
| `scripts/` | Operational CLIs (vector verification, ingestion, git-story generation, slash smoke tests). |
| `docs/` | Current documentation set (see Section 7). Removed docs live in `docs/ARCHIVE_SUMMARY.md`. |
| `tests/` | Focused suites that still matter: `tests/test_slash_git.py`, `tests/test_slash_slack_orchestrator.py`, `tests/test_graph_service.py`, `tests/test_swagger_drift.py`, etc. |

Retired directories (e.g., `docs/agents/`, `tests/e2e/`) exist only in git history and are intentionally absent.

---

## 3. Launcher & Desktop Workflows

### Spotlight (Raycast-style) Launcher
- Entry: `frontend/app/launcher/page.tsx` renders `<CommandPalette />`.
- Input handling lives in `frontend/components/CommandPalette.tsx`. Slash commands bypass file search unless `/files` is explicitly typed.
- Shared spotlight tokens (mini conversation depth, motion curves, hint pills) live in `frontend/config/ui.ts`—update this file instead of scattering magic numbers.
- Spotify mini player parity is provided by `frontend/components/SpotifyMiniPlayer.tsx` (`variant="launcher-mini"`).
- Visibility + blur handling is centralized in Electron (`desktop/src/main.ts`) and documented in `docs/WINDOW_VISIBILITY_STATE_MACHINE.md`.

### Expanded Desktop View
- Entry: `frontend/app/desktop/page.tsx` wraps the chat interface plus the desktop footer Spotify player.
- Expansion/collapse animation lives in `frontend/components/DesktopExpandAnimation.tsx`, called via IPC from Electron (`collapseToSpotlight()`).

### IPC + Backend Contracts
- Electron exposes `window.electronAPI` in the renderer via `desktop/src/preload.ts`.
- The frontend uses REST (`getApiBaseUrl()`) and WebSockets via `frontend/lib/useWebSocket.ts` to hit the FastAPI server at `api_server.py`.

---

## 4. Backend Highlights

| Area | Files | Notes |
|------|-------|-------|
| Slash Slack orchestration | `src/orchestrator/slash_slack/orchestrator.py` | Plans & dispatches slash commands. |
| Git storyteller | `src/agent/git_agent.py`, `scripts/generate_git_story_commit.py`, fixtures in `data/synthetic_git/`. |
| Slack datasets | `data/synthetic_slack/`, docs in `docs/development/synthetic_slack_dataset.md`. |
| Spotify service | `src/services/spotify_service.py` (implicit), frontend uses `/api/spotify/*` endpoints (see `api_server.py`). |
| Context caches | `src/cache/startup_cache.py`, `src/memory/local_chat_cache.py`. |
| Vector/Qdrant | `src/vector/service_factory.py`, docs in `docs/operations/vector.md`. |

All backend configuration is centralized in `config.yaml`. Use `.env.sample` to supply API keys (OpenAI, Slack, GitHub, Spotify).

---

## 5. Build & Run Checklist (Stable Flow)

1. **Backend / API server**
   ```bash
   cd /Users/siddharthsuresh/Downloads/auto_mac
   source venv/bin/activate
   python api_server.py
   ```
   Optional flags/config live in `config.yaml`.

2. **Frontend (Next.js)**
```bash
   cd frontend
   npm install        # once
   npm run dev        # serves http://localhost:3000
   ```

3. **Electron desktop**
   ```bash
   cd desktop
   npm install        # once
   npm run dev        # attaches to the running frontend/backend
   ```

4. **Static build for packaging**
```bash
   cd frontend
   npm run build      # writes static export to frontend/out
   ```
   Electron picks up `frontend/out/` in production via `desktop/src/main.ts`.

---

## 6. Testing & Smoke Checks

| Test | Command | Purpose |
|------|---------|---------|
| Slash Git | `pytest tests/test_slash_git.py -v` | Validates Git storyline generation + vector lookups. |
| Slack orchestrator | `pytest tests/test_slash_slack_orchestrator.py -v` | Ensures slash planner integrations stay green. |
| Graph service | `pytest tests/test_graph_service.py -v` | Confirms Neo4j-style analytics service contracts. |
| Swagger drift | `pytest tests/test_swagger_drift.py -v` + `scripts/detect_swagger_drift.py` | Keeps API docs + fixtures aligned. |
| Startup cache | `pytest tests/unit/test_startup_cache.py -v` | Ensures cached prompt bundles bootstrap correctly. |
| Runbook | `docs/testing/INSTANT_STARTUP.md`, `docs/testing/SLASH_COMMANDS.md` | Manual checklist for launcher/Spotify guarantee. |

Utility scripts:
- `scripts/run_checks.py` – bundles smoke tests.
- `scripts/run_slash_smoke_tests.py` – calls key slash commands end-to-end.

---

## 7. Documentation Map (Current Set)

| Topic | Docs |
|-------|------|
| Overall index | `docs/DOCUMENTATION_INDEX.md` |
| Current build status | `docs/IMPLEMENTATION_STATUS.md` |
| Electron UI details | `docs/development/ELECTRON_UI_GUIDE.md` |
| Launcher lifecycle | `docs/architecture/launcher_startup_flow.md` |
| Window lock logic | `docs/WINDOW_VISIBILITY_STATE_MACHINE.md` |
| Synthetic datasets | `docs/development/synthetic_git_dataset.md`, `docs/development/synthetic_slack_dataset.md` |
| Vector service | `docs/operations/vector.md` |
| Diagnostics | `docs/diagnostics/electron_launcher.md`, `docs/plan_ui_launch_debug.md` |
| Testing playbooks | `docs/testing/SLASH_COMMANDS.md`, `docs/testing/INSTANT_STARTUP.md` |

Anything not listed above has been archived—consult `docs/ARCHIVE_SUMMARY.md` and git history if you need the old Cerebros OS artifacts.

---

## 8. Observability & Logs

| Surface | Location |
|---------|----------|
| Electron logs | `logs/electron/*.log` (see `docs/diagnostics/electron_launcher.md`). |
| Backend/API logs | stdout from `python api_server.py`, plus optional `data/trajectories/*.jsonl` for replay. |
| Slash plans & telemetry | `data/trajectories/`, `logs/`, and `scripts/run_activity_ingestion.py`. |
| Vector health | `scripts/verify_vectordb.py` and `/api/vector/health`. |

Use `scripts/check_spotify_health.sh`, `scripts/test_spotlight_features.py`, etc., when debugging integrations.

---

## 9. Coding Conventions & Tips

1. Keep launcher UX changes in `frontend/components/` synced between Spotlight and expanded variants.
2. When touching slash flows, update both the Python orchestrator (`src/orchestrator/slash_slack/`) and the synthetic fixtures/docs.
3. All new docs should be added to `docs/DOCUMENTATION_INDEX.md`; keep them concise and cross-link existing guides.
4. Always finish a slash command plan with `reply_to_user` and log telemetry via the event bus.
5. Prefer the provided scripts (`scripts/run_checks.py`, `scripts/detect_swagger_drift.py`) over ad-hoc tooling—they are what the ops docs describe.

_Last updated: November 2025_

