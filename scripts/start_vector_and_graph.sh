#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILES="${ENV_FILES:-$ROOT_DIR/.env}"

load_env_file() {
  local file_path="$1"
  [ -f "$file_path" ] || return
  echo "[datastores] Loading environment from $file_path"

  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%%$'\r'}"
    case "$line" in
      ''|\#*) continue ;;
    esac
    if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
      local key="${line%%=*}"
      local value="${line#*=}"
    if [[ "$value" =~ ^\".*\"$ || "$value" =~ ^\'.*\'$ ]]; then
      if [ "${#value}" -ge 2 ]; then
        value="${value:1:${#value}-2}"
      else
        value=""
      fi
      fi
      export "$key=$value"
    fi
  done < "$file_path"
}

for env_file in $ENV_FILES; do
  load_env_file "$env_file"
done

if ! command -v docker >/dev/null 2>&1; then
  echo "[datastores] docker CLI not found in PATH" >&2
  exit 1
fi

QDRANT_CONTAINER_NAME="${QDRANT_CONTAINER_NAME:-oqoqo-qdrant}"
QDRANT_IMAGE="${QDRANT_IMAGE:-qdrant/qdrant:v1.7.3}"
QDRANT_PORT="${QDRANT_PORT:-6333}"
QDRANT_STORAGE_DIR="${QDRANT_STORAGE_DIR:-$ROOT_DIR/qdrant_storage}"

NEO4J_CONTAINER_NAME="${NEO4J_CONTAINER_NAME:-oqoqo-neo4j}"
NEO4J_IMAGE="${NEO4J_IMAGE:-neo4j:5.22}"
NEO4J_HTTP_PORT="${NEO4J_HTTP_PORT:-7474}"
NEO4J_BOLT_PORT="${NEO4J_BOLT_PORT:-7687}"
NEO4J_DATA_ROOT="${NEO4J_DATA_ROOT:-$ROOT_DIR/data/neo4j}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-strongpassword}"

mkdir -p "$QDRANT_STORAGE_DIR"
mkdir -p "$NEO4J_DATA_ROOT"/{data,logs,plugins}

start_qdrant() {
  if docker ps --format '{{.Names}}' | grep -q "^${QDRANT_CONTAINER_NAME}$"; then
    echo "[qdrant] Container '${QDRANT_CONTAINER_NAME}' already running."
    return
  fi

  if docker ps -a --format '{{.Names}}' | grep -q "^${QDRANT_CONTAINER_NAME}$"; then
    echo "[qdrant] Starting existing container '${QDRANT_CONTAINER_NAME}'..."
    docker start "$QDRANT_CONTAINER_NAME" >/dev/null
    return
  fi

  echo "[qdrant] Creating container '${QDRANT_CONTAINER_NAME}'..."
  docker run -d \
    --name "$QDRANT_CONTAINER_NAME" \
    -p "${QDRANT_PORT}:6333" \
    -v "${QDRANT_STORAGE_DIR}:/qdrant/storage" \
    "$QDRANT_IMAGE" >/dev/null
  echo "[qdrant] Listening on http://localhost:${QDRANT_PORT}"
}

start_neo4j() {
  if docker ps --format '{{.Names}}' | grep -q "^${NEO4J_CONTAINER_NAME}$"; then
    echo "[neo4j] Container '${NEO4J_CONTAINER_NAME}' already running."
    return
  fi

  if docker ps -a --format '{{.Names}}' | grep -q "^${NEO4J_CONTAINER_NAME}$"; then
    echo "[neo4j] Starting existing container '${NEO4J_CONTAINER_NAME}'..."
    docker start "$NEO4J_CONTAINER_NAME" >/dev/null
    return
  fi

  echo "[neo4j] Creating container '${NEO4J_CONTAINER_NAME}'..."
  docker run -d \
    --name "$NEO4J_CONTAINER_NAME" \
    -p "${NEO4J_HTTP_PORT}:7474" \
    -p "${NEO4J_BOLT_PORT}:7687" \
    -e "NEO4J_AUTH=${NEO4J_USER}/${NEO4J_PASSWORD}" \
    -e "NEO4JLABS_PLUGINS=[\"apoc\"]" \
    -v "${NEO4J_DATA_ROOT}/data:/data" \
    -v "${NEO4J_DATA_ROOT}/logs:/logs" \
    -v "${NEO4J_DATA_ROOT}/plugins:/plugins" \
    "$NEO4J_IMAGE" >/dev/null
  echo "[neo4j] Bolt: bolt://localhost:${NEO4J_BOLT_PORT} (user: ${NEO4J_USER})"
  echo "[neo4j] Browser: http://localhost:${NEO4J_HTTP_PORT}"
}

start_qdrant
start_neo4j

echo "[datastores] Both services ensured running."

