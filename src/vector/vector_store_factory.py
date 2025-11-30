from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .local_vector_store import LocalVectorStore
from .qdrant_vector_store import QdrantVectorStore


def _vector_backend() -> str:
    return os.getenv("VECTOR_BACKEND", "local").strip().lower()


def create_vector_store(
    domain: str,
    *,
    local_path: Optional[Path],
    config: Optional[dict] = None,
):
    """
    Create a vector store for the requested domain.

    Args:
        domain: Logical data source (e.g., "slack", "git").
        local_path: JSON path used when VECTOR_BACKEND=local.
        config: Optional config dict for pulling vectordb defaults.
    """
    backend = _vector_backend()
    if backend == "qdrant":
        cfg = (config or {}).get("vectordb", {})
        base_url = cfg.get("url") or os.getenv("QDRANT_URL")
        api_key = cfg.get("api_key") or os.getenv("QDRANT_API_KEY")
        collection = cfg.get("collection") or os.getenv("QDRANT_COLLECTION") or "oqoqo_context"
        dimension = cfg.get("dimension", 1536)

        collection_name = f"{collection}_{domain}"

        if not base_url:
            raise ValueError(
                "Qdrant backend requested but QDRANT_URL (or vectordb.url) is missing."
            )

        return QdrantVectorStore(
            base_url=base_url,
            api_key=api_key,
            collection=collection_name,
            dimension=dimension,
        )

    # Default to local JSON-backed store
    if not local_path:
        raise ValueError("Local vector store requires a path to persist embeddings.")
    return LocalVectorStore(local_path)

