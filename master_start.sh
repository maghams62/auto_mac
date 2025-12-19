#!/usr/bin/env bash

if [ -n "${ZSH_VERSION:-}" ] && [ -z "${__MASTER_START_REEXEC:-}" ]; then
  export __MASTER_START_REEXEC=1
  exec bash "$0" "$@"
fi

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
# --------------------------------------------------------------------------------------
# PORT CONTRACT (PLEASE READ BEFORE CHANGING ANYTHING HERE)
# --------------------------------------------------------------------------------------
# This script is the *only* place that should decide where the Cerebros UI runs.
# The agreed, stable defaults are:
#   - FastAPI backend (API):     http://127.0.0.1:8000
#   - Cerebros chat/graph UI:    http://localhost:3300
#   - Oqoqo dashboard (Drift):   http://localhost:3100  (see oqoqo-dashboard/oq_start.sh)
#
# Coding LLMs and humans alike:
#   - DO NOT move Cerebros off 3300 without ALSO updating:
#       * oqoqo-dashboard/oq_start.sh (brain redirect comment)
#       * oqoqo-dashboard/.env.local (NEXT_PUBLIC_BRAIN_* URLs)
#       * docs/neo4j_universe_parity.md and docs/runtime_modes_and_ingest.md
#   - DO NOT point the dashboard at 3300 for API calls; all backend calls
#     must continue to target the FastAPI origin on 8000 (see DEFAULT_BASE
#     in oqoqo-dashboard/src/lib/clients/cerebros.ts).
#   - If a port collision appears, change *PORT/MASTER_PORT/FRONTEND_PORT*
#     values via environment variables when launching, rather than hard-coding.
#
# The invariant to preserve is:
#   "8000 = API, 3300 = Cerebros UI, 3100 = dashboard"
# If any future change breaks that invariant, you *must* update all of the
# places mentioned above and re-run the documented curl/health checks.
# --------------------------------------------------------------------------------------
FRONTEND_DIR="$ROOT_DIR/frontend"
DESKTOP_DIR="$ROOT_DIR/desktop"
LOG_DIR="$ROOT_DIR/logs/master-start"
ENABLE_ELECTRON="${ENABLE_ELECTRON:-0}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
# MASTER_PORT controls the Cerebros Next.js dev server. 3300 is the canonical
# default; do not change this lightly (see port contract above).
MASTER_PORT="${MASTER_PORT:-3300}"
FRONTEND_PORT="${FRONTEND_PORT:-$MASTER_PORT}"
MASTER_PORT="$FRONTEND_PORT"
ENABLE_TEST_FIXTURE_ENDPOINTS="${ENABLE_TEST_FIXTURE_ENDPOINTS:-1}"
BRAIN_GRAPH_FIXTURE="${BRAIN_GRAPH_FIXTURE:-live}"
NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://${BACKEND_HOST}:${BACKEND_PORT}}"
NEXT_PUBLIC_GRAPH_TEST_HOOKS="${NEXT_PUBLIC_GRAPH_TEST_HOOKS:-0}"
PORT="${PORT:-$FRONTEND_PORT}"

mkdir -p "$LOG_DIR"

echo "[master-start] Stopping existing servers…"
pkill -f '/desktop/node_modules/electron/dist/Electron.app' 2>/dev/null || true
pkill -f 'frontend/node_modules/.bin/next dev' 2>/dev/null || true
pkill -f 'api_server.py' 2>/dev/null || true

ensure_node_modules() {
  local dir="$1"
  if [ ! -d "$dir/node_modules" ]; then
    echo "[master-start] Installing dependencies in $dir…"
    (cd "$dir" && npm install) >/dev/null 2>&1
  fi
}

wait_for_http() {
  local url="$1"
  local retries="${2:-40}"
  local delay="${3:-1}"
  for ((i=1; i<=retries; i++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

echo "[master-start] Freeing ports ${FRONTEND_PORT}/${BACKEND_PORT}…"
for PORT_CANDIDATE in "$FRONTEND_PORT" "$BACKEND_PORT"; do
  if PIDS=$(lsof -nP -iTCP:$PORT_CANDIDATE -sTCP:LISTEN -t 2>/dev/null); then
    echo "  - Killing processes on port $PORT_CANDIDATE: $PIDS"
    echo "$PIDS" | xargs -r kill -9
  fi
done

echo "[master-start] Starting backend (FastAPI)…"
cd "$ROOT_DIR"
ENABLE_TEST_FIXTURE_ENDPOINTS="$ENABLE_TEST_FIXTURE_ENDPOINTS" \
BRAIN_GRAPH_FIXTURE="$BRAIN_GRAPH_FIXTURE" \
uvicorn api_server:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" >"$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
if ! wait_for_http "http://${BACKEND_HOST}:${BACKEND_PORT}/health" 40 1; then
  echo "Backend failed to become healthy; see $LOG_DIR/backend.log"
  kill "$BACKEND_PID" 2>/dev/null || true
  exit 1
fi

echo "[master-start] Starting frontend (Next.js dev)…"
ensure_node_modules "$FRONTEND_DIR"
cd "$FRONTEND_DIR"
PORT="$FRONTEND_PORT" \
NEXT_PUBLIC_API_URL="$NEXT_PUBLIC_API_URL" \
NEXT_PUBLIC_GRAPH_TEST_HOOKS="$NEXT_PUBLIC_GRAPH_TEST_HOOKS" \
npm run dev >"$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
if ! wait_for_http "http://127.0.0.1:${FRONTEND_PORT}/brain/neo4j/" 60 1; then
  echo "Frontend failed; see $LOG_DIR/frontend.log"
  kill "$FRONTEND_PID" "$BACKEND_PID" 2>/dev/null || true
  exit 1
fi

ELECTRON_PID=""
if [ "$ENABLE_ELECTRON" = "1" ]; then
  echo "[master-start] Starting Electron launcher…"
  ensure_node_modules "$DESKTOP_DIR"
  cd "$DESKTOP_DIR"
  npm run dev >"$LOG_DIR/electron.log" 2>&1 &
  ELECTRON_PID=$!
else
  echo "[master-start] Skipping Electron launcher (set ENABLE_ELECTRON=1 to enable)"
fi

shutdown() {
  echo "[master-start] Shutting down"
  if [ -n "$ELECTRON_PID" ]; then
    kill "$ELECTRON_PID" 2>/dev/null || true
  fi
  kill "$FRONTEND_PID" "$BACKEND_PID" 2>/dev/null || true
}

trap shutdown INT TERM

echo
echo "All services running:"
echo "  Backend PID:   $BACKEND_PID  (logs: $LOG_DIR/backend.log)"
echo "  Frontend PID:  $FRONTEND_PID (logs: $LOG_DIR/frontend.log)"
if [ -n "$ELECTRON_PID" ]; then
  echo "  Electron PID:  $ELECTRON_PID (logs: $LOG_DIR/electron.log)"
else
  echo "  Electron:     skipped (ENABLE_ELECTRON=1 to enable)"
fi
echo
echo "Graph Explorer ready at: http://localhost:${FRONTEND_PORT}/brain/neo4j/"
echo "  - Universe slice: http://localhost:${FRONTEND_PORT}/brain/universe/"
echo "  - Trace viewer:   http://localhost:${FRONTEND_PORT}/brain/trace/<queryId>"
echo "Need the Oqoqo dashboard instead? Run: cd oqoqo-dashboard && ./oq_start.sh"
echo
if [ -n "$ELECTRON_PID" ]; then
  wait "$BACKEND_PID" "$FRONTEND_PID" "$ELECTRON_PID"
else
  wait "$BACKEND_PID" "$FRONTEND_PID"
fi

