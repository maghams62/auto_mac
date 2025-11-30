#!/usr/bin/env python3
"""
Lightweight health checks for Qdrant (vector DB) and Neo4j (graph DB).

This script assumes the developer's .env is already configured. It loads the
same config stack as Cerebros, pings the configured backends, and exits with a
non-zero status if any enabled backend is unreachable.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config_manager import ConfigManager
from src.graph.service import GraphService
from src.vector.vector_store_factory import create_vector_store


def _resolve_vectordb_backend(config: Dict[str, Dict]) -> str:
    vectordb_cfg = config.get("vectordb") or {}
    backend = os.getenv("VECTOR_BACKEND") or vectordb_cfg.get("backend") or "local"
    return backend.strip().lower()


def _resolve_vectordb_url(config: Dict[str, Dict]) -> Optional[str]:
    vectordb_cfg = config.get("vectordb") or {}
    return vectordb_cfg.get("url") or os.getenv("QDRANT_URL")


def _resolve_vectordb_api_key(config: Dict[str, Dict]) -> Optional[str]:
    vectordb_cfg = config.get("vectordb") or {}
    return vectordb_cfg.get("api_key") or os.getenv("QDRANT_API_KEY")


def check_qdrant(config: Dict[str, Dict]) -> bool:
    backend = _resolve_vectordb_backend(config)
    if backend != "qdrant":
        print("Qdrant: skipped (VECTOR_BACKEND!=qdrant)")
        return True

    start = time.perf_counter()
    try:
        store = create_vector_store(
            "slack",
            local_path=Path("data/vector_index/slack_index.json"),
            config=config,
        )
    except Exception as exc:  # pragma: no cover - network failure
        print(f"Qdrant: ERROR (failed to initialize vector store: {exc})")
        return False
    finally:
        # LocalVectorStore has no close(), guard access.
        close_fn = getattr(locals().get("store", None), "close", None)
        if callable(close_fn):
            try:
                close_fn()
            except Exception:
                pass

    base_url = _resolve_vectordb_url(config)
    api_key = _resolve_vectordb_api_key(config)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key

    try:
        with httpx.Client(base_url=base_url, headers=headers, timeout=10.0) as client:
            response = client.get("/collections")
            response.raise_for_status()
            collections = [
                entry.get("name") for entry in response.json().get("result", {}).get("collections", [])
            ]
    except Exception as exc:  # pragma: no cover - network failure
        print(f"Qdrant: ERROR (failed to list collections: {exc})")
        return False

    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    print(f"Qdrant: OK (collections={len(collections)} latency_ms={latency_ms})")
    return True


def check_neo4j(config: Dict[str, Dict]) -> bool:
    graph_cfg = config.get("graph") or {}
    env_enabled = os.getenv("NEO4J_ENABLED")
    enabled = graph_cfg.get("enabled", False)
    if env_enabled is not None:
        enabled = env_enabled.lower() == "true"

    if not enabled:
        print("Neo4j: skipped (graph.enabled=false)")
        return True

    graph_service = GraphService(config)
    if not graph_service.is_available():
        print("Neo4j: ERROR (graph configured but unavailable)")
        return False

    start = time.perf_counter()
    try:
        records = graph_service.run_query("MATCH (n) RETURN count(n) AS total LIMIT 1")
        total = records[0].get("total", 0) if records else 0
    except Exception as exc:  # pragma: no cover - query failure
        graph_service.close()
        print(f"Neo4j: ERROR (query failed: {exc})")
        return False

    graph_service.close()
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    print(f"Neo4j: OK (node_count={total} latency_ms={latency_ms})")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify vector + graph backends are reachable.")
    parser.add_argument("--skip-vector", action="store_true", help="Skip the Qdrant health check.")
    parser.add_argument("--skip-graph", action="store_true", help="Skip the Neo4j health check.")
    args = parser.parse_args()

    config = ConfigManager().get_config()
    vector_ok = True
    graph_ok = True

    if not args.skip_vector:
        vector_ok = check_qdrant(config)
    else:
        print("Qdrant: skipped via --skip-vector")

    if not args.skip_graph:
        graph_ok = check_neo4j(config)
    else:
        print("Neo4j: skipped via --skip-graph")

    return 0 if vector_ok and graph_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

