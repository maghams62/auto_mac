"""
Slack-specific utility helpers shared across integrations and services.
"""

from __future__ import annotations

import re
from typing import Optional


_CHANNEL_CLEANER = re.compile(r"[\s/]+")
_CHANNEL_ALLOWED = re.compile(r"[^a-z0-9._-]")
_DASH_COMPRESSION = re.compile(r"-{2,}")


def normalize_channel_name(name: Optional[str]) -> Optional[str]:
    """
    Normalize a Slack channel token into a canonical comparison key.

    Args:
        name: Raw channel name or label (may include #, spaces, etc.)

    Returns:
        Lowercase normalized identifier suitable for fuzzy comparisons.
    """
    if not name:
        return None
    normalized = name.strip().lstrip("#").lower()
    normalized = _CHANNEL_CLEANER.sub("-", normalized)
    normalized = _CHANNEL_ALLOWED.sub("", normalized)
    normalized = _DASH_COMPRESSION.sub("-", normalized).strip("-._")
    return normalized or None


