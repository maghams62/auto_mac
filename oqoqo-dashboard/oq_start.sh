#!/usr/bin/env bash

if [ -n "${ZSH_VERSION:-}" ] && [ -z "${__OQ_START_REEXEC:-}" ]; then
  export __OQ_START_REEXEC=1
  exec bash "$0" "$@"
fi

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# --------------------------------------------------------------------------------------
# PORT CONTRACT FOR OQOQO DASHBOARD (READ BEFORE EDITING)
# --------------------------------------------------------------------------------------
# This script intentionally keeps the following split:
#   - FastAPI backend (Cerebros API):  http://127.0.0.1:8000
#   - Cerebros UI / Graph Explorer:   http://localhost:3300  (master_start.sh)
#   - Oqoqo dashboard (this app):     http://localhost:3100
#
# Coding LLMs:
#   - Do NOT change DEFAULT_PORT away from 3100 just to “fix” a port conflict.
#     If 3100 is busy, use `PORT=<free-port> ./oq_start.sh` instead.
#   - Do NOT point CEREBROS_API_BASE or NEXT_PUBLIC_CEREBROS_API_BASE at 3300.
#     3300 serves a *browser UI*, not the FastAPI JSON API. All backend calls
#     in this app must continue to hit 8000; see DEFAULT_BASE in
#     `src/lib/clients/cerebros.ts`.
#   - If you ever move the Cerebros UI off 3300, you *must* update:
#       * The redirect in `src/app/brain/universe/page.tsx`
#       * Any NEXT_PUBLIC_BRAIN_* env hints in docs and .env.local
#       * The comments in master_start.sh about port layout
#
# Human operators:
#   - For a clean local stack, the expected sequence is:
#       MASTER_PORT=3300 bash master_start.sh      # backend 8000 + Cerebros 3300
#       ./oq_start.sh                              # dashboard on 3100
# --------------------------------------------------------------------------------------
cd "$SCRIPT_DIR"

if [ -z "${CEREBROS_API_BASE:-}" ]; then
  export CEREBROS_API_BASE="http://127.0.0.1:8000"
fi

if [ -z "${NEXT_PUBLIC_CEREBROS_API_BASE:-}" ]; then
  export NEXT_PUBLIC_CEREBROS_API_BASE="$CEREBROS_API_BASE"
fi

DEFAULT_PORT=3100
REQUESTED_PORT="${PORT:-$DEFAULT_PORT}"
if lsof -ti tcp:"$REQUESTED_PORT" >/dev/null 2>&1; then
  echo "[oq_start] Port $REQUESTED_PORT is already in use. Set PORT=<free-port> ./oq_start.sh to override."
  exit 1
fi
PORT="$REQUESTED_PORT"

echo "Starting Oqoqo dashboard on http://localhost:${PORT} ..."
echo "  Available routes: /projects, /incidents, /brain/universe (redirects to http://localhost:3300/brain/neo4j/)."
echo "  Tip: Cerebros chat via master_start now runs on port 3300, so the dashboard keeps 3100 by default. Override with PORT=<free-port> ./oq_start.sh as needed."
PORT="$PORT" npm run dev -- --port "${PORT}"

