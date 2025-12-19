#!/usr/bin/env python3
"""
Connectivity/permission check for the configured Qdrant instance.
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config_manager import get_config  # noqa: E402
from src.vector.service_factory import (  # noqa: E402
    VectorServiceConfigError,
    validate_vectordb_config,
)


def _build_http_client(vectordb_config):
    headers = {"Content-Type": "application/json"}
    api_key = vectordb_config.get("api_key")
    if api_key:
        headers["api-key"] = api_key

    base_url = vectordb_config["url"].rstrip("/")
    timeout = vectordb_config.get("timeout_seconds", 6.0)
    return httpx.Client(base_url=base_url, headers=headers, timeout=timeout)


def verify_vectordb(skip_mutation: bool = False) -> int:
    """
    Executes the verification flow. Returns process exit code.
    """
    try:
        vectordb_config = validate_vectordb_config(get_config())
    except VectorServiceConfigError as exc:
        print(f"[ERROR] Invalid vectordb configuration: {exc}")
        return 2

    with _build_http_client(vectordb_config) as client:
        try:
            start = time.perf_counter()
            response = client.get("/collections")
            response.raise_for_status()
            latency_ms = (time.perf_counter() - start) * 1000
            collections = response.json().get("result", {}).get("collections", [])
            print(f"[OK] Connected to Qdrant at {client.base_url} ({latency_ms:.1f} ms).")
            print(f"     Collections visible: {len(collections)}")
        except Exception as exc:
            print(f"[ERROR] Failed to list collections: {exc}")
            return 3

        if skip_mutation:
            return 0

        temp_collection = f"{vectordb_config['collection']}_verify_{uuid.uuid4().hex[:8]}"
        create_payload = {
            "vectors": {"size": vectordb_config["dimension"], "distance": "Cosine"}
        }
        try:
            client.put(f"/collections/{temp_collection}", json=create_payload).raise_for_status()
            print(f"[OK] Created temporary collection '{temp_collection}'.")
        except Exception as exc:
            print(f"[ERROR] Failed to create temporary collection '{temp_collection}': {exc}")
            return 4
        finally:
            try:
                client.delete(f"/collections/{temp_collection}", params={"force": "true"}).raise_for_status()
                print(f"[OK] Deleted temporary collection '{temp_collection}'.")
            except Exception as exc:
                print(f"[WARN] Could not delete temporary collection '{temp_collection}': {exc}")
                return 5

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Qdrant connectivity and permissions.")
    parser.add_argument(
        "--skip-mutation",
        action="store_true",
        help="Skip create/delete step and only verify read access.",
    )
    args = parser.parse_args()
    return verify_vectordb(skip_mutation=args.skip_mutation)


if __name__ == "__main__":
    raise SystemExit(main())

