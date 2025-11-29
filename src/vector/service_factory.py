"""
Factory helpers for vector search services with strict configuration validation.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from .vector_search_service import QdrantVectorSearchService, VectorSearchService

logger = logging.getLogger(__name__)

LOCAL_URL_PREFIXES = (
    "http://localhost",
    "http://127.0.0.1",
    "https://localhost",
    "https://127.0.0.1",
)


class VectorServiceConfigError(ValueError):
    """Raised when the vectordb section is misconfigured."""


def _resolve_setting(
    config_value: Optional[str],
    primary_env: str,
    legacy_env: Optional[str],
    default: Optional[str] = None,
) -> Optional[str]:
    """
    Prefer explicit config, then modern env var, then legacy env var, then default.
    """
    if isinstance(config_value, str):
        stripped = config_value.strip()
        if stripped:
            return stripped

    env_value = os.getenv(primary_env)
    if env_value:
        return env_value.strip()

    if legacy_env:
        legacy_value = os.getenv(legacy_env)
        if legacy_value:
            logger.info(
                "[VECTOR CONFIG] Falling back to legacy env var '%s' for '%s'",
                legacy_env,
                primary_env,
            )
            return legacy_value.strip()

    return default


def _validate_dimension(value: Any) -> int:
    try:
        dimension = int(value)
    except (TypeError, ValueError):
        raise VectorServiceConfigError("vectordb.dimension must be an integer")
    if dimension <= 0:
        raise VectorServiceConfigError("vectordb.dimension must be greater than zero")
    return dimension


def validate_vectordb_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize the vectordb config block.
    """
    vectordb_config = dict(config.get("vectordb") or {})
    enabled = vectordb_config.get("enabled", True)
    if not enabled:
        raise VectorServiceConfigError("Vector search is disabled via config.")

    provider = (vectordb_config.get("provider") or "qdrant").strip().lower()
    if provider != "qdrant":
        raise VectorServiceConfigError(
            f"Unsupported vectordb provider '{provider}'. Only 'qdrant' is currently supported."
        )

    url = _resolve_setting(
        vectordb_config.get("url"),
        primary_env="QDRANT_URL",
        legacy_env="VECTORDB_URL",
        default="http://localhost:6333",
    )
    if not url:
        raise VectorServiceConfigError(
            "vectordb.url is not configured. Set QDRANT_URL (or legacy VECTORDB_URL)."
        )

    api_key = _resolve_setting(
        vectordb_config.get("api_key"),
        primary_env="QDRANT_API_KEY",
        legacy_env="VECTORDB_API_KEY",
        default=None,
    )
    is_local = url.startswith(LOCAL_URL_PREFIXES)
    if not api_key and not is_local:
        raise VectorServiceConfigError(
            "Qdrant API key missing for non-local deployment. Set QDRANT_API_KEY."
        )

    collection = _resolve_setting(
        vectordb_config.get("collection"),
        primary_env="QDRANT_COLLECTION",
        legacy_env="VECTORDB_COLLECTION",
        default="oqoqo_context",
    )
    if not collection:
        raise VectorServiceConfigError("vectordb.collection must be provided.")

    timeout = vectordb_config.get("timeout_seconds", 6.0)
    try:
        timeout = float(timeout)
    except (TypeError, ValueError):
        raise VectorServiceConfigError("vectordb.timeout_seconds must be numeric")
    if timeout <= 0:
        raise VectorServiceConfigError("vectordb.timeout_seconds must be greater than zero")

    default_top_k = vectordb_config.get("default_top_k", 12)
    try:
        default_top_k = int(default_top_k)
    except (TypeError, ValueError):
        raise VectorServiceConfigError("vectordb.default_top_k must be an integer")

    min_score = vectordb_config.get("min_score", 0.35)
    try:
        min_score = float(min_score)
    except (TypeError, ValueError):
        raise VectorServiceConfigError("vectordb.min_score must be numeric")

    dimension = _validate_dimension(vectordb_config.get("dimension", 1536))

    return {
        **vectordb_config,
        "enabled": True,
        "provider": provider,
        "url": url,
        "api_key": api_key,
        "collection": collection,
        "timeout_seconds": timeout,
        "default_top_k": default_top_k,
        "min_score": min_score,
        "dimension": dimension,
    }


def get_vector_search_service(config: Dict[str, Any]) -> Optional[VectorSearchService]:
    """
    Return a configured vector search service or None if configuration is invalid.
    """
    try:
        validated_vectordb = validate_vectordb_config(config)
    except VectorServiceConfigError as exc:
        logger.warning("[VECTOR CONFIG] %s", exc)
        return None

    provider = validated_vectordb["provider"]
    merged_config = dict(config)
    merged_config["vectordb"] = {
        **config.get("vectordb", {}),
        **validated_vectordb,
    }

    if provider == "qdrant":
        service = QdrantVectorSearchService(merged_config)
        if service.is_configured():
            return service
        logger.warning("[VECTOR CONFIG] Qdrant service failed internal readiness checks.")
        return None

    logger.warning("[VECTOR CONFIG] Provider '%s' is not supported.", provider)
    return None

