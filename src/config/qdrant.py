"""Central helpers for Qdrant configuration defaults."""

from __future__ import annotations

import os
from typing import Optional

DEFAULT_COLLECTION = "oqoqo_context"


def get_qdrant_collection_name(preferred: Optional[str] = None) -> str:
    """
    Resolve the Qdrant collection name with sane fallbacks.

    Order of precedence:
    1. Explicit value (unless it looks like an unresolved ${VAR:-default} template)
    2. QDRANT_COLLECTION env var
    3. VECTORDB_COLLECTION env var (legacy)
    4. Built-in default (`oqoqo_context`)
    """

    def _clean(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        trimmed = value.strip()
        return trimmed or None

    candidate = _clean(preferred)
    if candidate and not candidate.startswith("${"):
        return candidate

    env_value = _clean(os.getenv("QDRANT_COLLECTION"))
    if env_value:
        return env_value

    legacy_value = _clean(os.getenv("VECTORDB_COLLECTION"))
    if legacy_value:
        return legacy_value

    return DEFAULT_COLLECTION


__all__ = ["get_qdrant_collection_name", "DEFAULT_COLLECTION"]

