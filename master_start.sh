#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
DESKTOP_DIR="$ROOT_DIR/desktop"
LOG_DIR="$ROOT_DIR/logs/master-start"
mkdir -p "$LOG_DIR"

echo "[master-start] Stopping existing servers…"
pkill -f '/desktop/node_modules/electron/dist/Electron.app' 2>/dev/null || true
pkill -f 'frontend/node_modules/.bin/next dev' 2>/dev/null || true
pkill -f 'api_server.py' 2>/dev/null || true

echo "[master-start] Freeing ports 3000/3001/8000…"
for PORT in 3000 3001 8000; do
  lsof -nP -iTCP:$PORT -sTCP:LISTEN -t | xargs -r kill -9
done

echo "[master-start] Starting backend (FastAPI)…"
cd "$ROOT_DIR"
python api_server.py >"$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
sleep 2
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  echo "Backend failed; see $LOG_DIR/backend.log"
  exit 1
fi

echo "[master-start] Starting frontend (Next.js dev)…"
cd "$FRONTEND_DIR"
npm install >/dev/null 2>&1 || true
npm run dev >"$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
sleep 4
if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
  echo "Frontend failed; see $LOG_DIR/frontend.log"
  kill "$BACKEND_PID"
  exit 1
fi

echo "[master-start] Starting Electron launcher…"
cd "$DESKTOP_DIR"
npm install >/dev/null 2>&1 || true
npm run dev >"$LOG_DIR/electron.log" 2>&1 &
ELECTRON_PID=$!

trap 'echo "[master-start] Shutting down"; kill $ELECTRON_PID $FRONTEND_PID $BACKEND_PID 2>/dev/null || true' INT TERM

echo
echo "All services running:"
echo "  Backend PID:   $BACKEND_PID  (logs: $LOG_DIR/backend.log)"
echo "  Frontend PID:  $FRONTEND_PID (logs: $LOG_DIR/frontend.log)"
echo "  Electron PID:  $ELECTRON_PID (logs: $LOG_DIR/electron.log)"
echo
wait

