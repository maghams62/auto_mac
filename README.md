# Cerebros (Raycast-style launcher + slash flows)

FastAPI + Next.js + Electron stack for the Cerebros launcher, desktop chat, and slash-command pipelines (Slack/Git). Synthetic Git/Slack fixtures and graph/vector helpers live in the repo for demos and testing.

## What’s in this repo (current surfaces)
- FastAPI backend (`api_server.py`) powering slash commands, Spotify controls, graph/vector APIs, and ingestion helpers.
- Next.js UI (`frontend/`) for the launcher/desktop experiences and the brain graph views.
- Electron shell (`desktop/`) that wraps the launcher + expanded desktop window and owns window visibility/opacity rules.
- Oqoqo dashboard (`oqoqo-dashboard/`) for drift/impact views (runs on port 3100 via `./oq_start.sh`).
- Synthetic data, seeds, and scripts under `data/` and `scripts/` for slash flows and demos.

## Documentation (start here)
- `docs/LLM_CODEBASE_GUIDE.md` – canonical overview of the active system.
- `docs/DOCUMENTATION_INDEX.md` – map of the small, still-supported doc set.
- `CRITICAL_BEHAVIOR.md` – non-negotiable window/launcher invariants.
- `_archive/docs_legacy/ARCHIVE_SUMMARY.md` – where the older Cerebros OS docs/tests were archived.
- `docs/quickstart/SETUP_SLACK_GITHUB.md` – tokens and scopes needed for live Slack/Git usage.

## Prerequisites
- macOS, Python 3.11+, Node.js 18+, npm.
- Copy `.env.sample` → `.env` in the repo root and fill required keys (OpenAI, Slack, GitHub, Spotify, Qdrant/VectorDB if used).
- Install Python deps: `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`.
- Install JS deps: `npm install` in `frontend/` and `desktop/`.

## Run locally
### One-command dev (recommended)
```bash
MASTER_PORT=3300 BACKEND_PORT=8000 ENABLE_ELECTRON=1 bash master_start.sh
```
- Port contract: backend `8000`, Cerebros UI `3300`, dashboard `3100` (see script header). Logs land in `logs/master-start/`.
- Set `ENABLE_ELECTRON=0` if you only need the web UI.
- Dashboard: `cd oqoqo-dashboard && ./oq_start.sh` (defaults to port `3100`).

### Manual bring-up
1) Backend (FastAPI):  
```bash
source venv/bin/activate
python api_server.py   # or: uvicorn api_server:app --host 127.0.0.1 --port 8000
```
2) Frontend (Next.js):  
```bash
cd frontend
PORT=3300 NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run dev
```
3) Electron launcher (optional):  
```bash
cd desktop
npm run dev   # expects backend 8000 + frontend 3300
```

## Tests and smoke checks
- `python scripts/run_checks.py` – bundled smoke.
- `pytest tests/test_slash_git.py -q`
- `pytest tests/test_slash_slack_orchestrator.py -q`
- `pytest tests/test_graph_service.py -q`
- `python scripts/run_slash_smoke_tests.py --base-url http://localhost:8000`

## Active directory map
- `desktop/` – Electron wrapper, window lifecycle, IPC bridge.
- `frontend/` – Next.js launcher + desktop surfaces and graph UI.
- `src/orchestrator/slash_slack/`, `src/slash_git/`, `src/services/`, `src/vector/` – slash planners, services, vector adapters.
- `data/` – synthetic Git/Slack fixtures, live caches, trajectories.
- `scripts/` – ops helpers, seeds, health checks.
- `_archive/` – legacy docs/tests; read `ARCHIVE_SUMMARY.md` before reviving anything.

## Notes and guardrails
- Window visibility/opacity rules are defined in `CRITICAL_BEHAVIOR.md`; follow them when editing `desktop/` or `frontend/app/launcher/`.
- Keep new docs short and add them to `docs/DOCUMENTATION_INDEX.md`.
- Honor the port contract from `master_start.sh` if you change defaults.
