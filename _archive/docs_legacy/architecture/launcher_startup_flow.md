# Cerebros Launcher Startup Flow

This note captures how the three major pieces of the system come online in development:

```
┌────────┐     spawn      ┌──────────┐     HTTP      ┌─────────────┐
│Electron├───────────────▶│Python API├──────────────▶│Next.js UI   │
│desktop/│  (main.ts)     │api_server│  (port 8000)  │frontend/    │
└────────┘                └──────────┘               └─────────────┘
         ╲______________________________________________╱
                          IPC + HTTP
```

## Components

- **Python backend** (`api_server.py`): FastAPI/Uvicorn application that wires `AutomationAgent`, session managers, telemetry, Mongo/Neo4j integrations, etc. Exposes `/health` plus REST/WebSocket endpoints on port `8000`. Runs inside the project `venv` in development or a self-managed venv under `~/Library/Application Support/cerebros-launcher/` in production.
- **Next.js UI** (`frontend/`): Serves the launcher (`/launcher`) and desktop (`/desktop`) routes on port `3000` when `npm run dev` is active. Production builds are statically exported into `frontend/out`.
- **Electron shell** (`desktop/src/main.ts`): Orchestrates backend/frontend lifetime, manages the Raycast-style window, registers the global hotkey, and proxies IPC to the renderer.

## Startup Paths

### 1. Shell Script (`start_ui.sh`)

For manual debugging outside Electron:

1. Kills stray `api_server.py`, Next.js, and port `3000/8000` listeners.
2. Clears caches (`__pycache__`, `.pyc`, `frontend/.next`).
3. Ensures `venv` and `frontend/node_modules` exist.
4. Optionally runs import verification.
5. Starts `python api_server.py` (logs in `api_server.log`) and `npm run dev` (logs in `frontend.log`).
6. Provides tail commands to follow the services.

### 2. Electron Dev (`desktop/npm run dev`)

Inside `desktop/src/main.ts`:

1. Determine `rootDir` (repo root) and whether we're in dev (`!app.isPackaged`).
2. Initialize `Logger`, record environment, hide the dock, and honor the "start at login" preference.
3. **Backend detection**: probe `http://127.0.0.1:8000/health` and port `8000`. If idle, spawn `${rootDir}/venv/bin/python api_server.py` with `cwd = rootDir`. Pipe stdout/stderr into `logs/electron/…` (buffering last 100 lines for diagnostics).
4. **Frontend detection** (dev only): probe `http://localhost:3000` and port `3000`. If idle, spawn `npm run dev` inside `frontend/`.
5. Poll both services (`waitForServer`) until healthy, logging latency and the backend process state. On success, continue to UI initialization; otherwise pop the diagnostics window with buffered output.
6. Create the frameless launcher window that loads `http://localhost:3000/launcher`, set up tray + hotkey, and wire IPC channels (lock/unlock, expanded window, settings, diagnostics).

### 3. Electron Production

Packaged apps skip `frontend/npm run dev` because the static build lives under `process.resourcesPath/app/frontend/out`. During first run Electron:

1. Creates a private Python venv inside `userData/python-venv`.
2. Installs `requirements.txt`, then spawns `python api_server.py` from `process.resourcesPath`.
3. Serves launcher UI from the exported HTML files rather than hitting `localhost:3000`.

## Window Lifecycle Hooks

- Renderer uses `window.electronAPI` (preload bridge) to react to `window-shown`/`window-hidden`, enforce the visibility lock during queries, and drive preferences.
- Main process enforces the state machine documented in `docs/WINDOW_VISIBILITY_STATE_MACHINE.md`: `toggleWindow()` locks visibility, centers on the primary display, and only unlocks after a 250 ms grace period. Blur events defer to lock/grace flags before hiding.

## Telemetry & Logs

- **Electron logs**: `logs/electron/*.log` (one per run, includes backend stdout/stderr excerpts).
- **Backend logs**: `api_server.log` (when using `start_ui.sh`) or whatever Uvicorn prints into Electron's capture buffer when spawned.
- **Frontend logs**: `frontend.log` (when started via script) plus browser console output.

Understanding where each subsystem is supposed to emit logs makes it easier to triage whether failures originate in process orchestration, backend imports, or Next.js compilation.

