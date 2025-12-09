from __future__ import annotations

import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse, urlunparse


_OWNER_ENV_KEYS = (
    "SLASH_GIT_REPO_OWNER",
    "GITHUB_REPO_OWNER",
    "GIT_ORG",
    "LIVE_GIT_ORG",
)


def determine_repo_owner_override(config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Resolve the preferred GitHub repo owner based on config or environment.

    Order of precedence:
      1. config["slash_git"]["repo_owner_override"]
      2. SLASH_GIT_REPO_OWNER / GITHUB_REPO_OWNER / GIT_ORG / LIVE_GIT_ORG
    """

    if config:
        slash_git_cfg = (config.get("slash_git") or {}) if isinstance(config, dict) else {}
        override = (slash_git_cfg or {}).get("repo_owner_override")
        if isinstance(override, str) and override.strip():
            return override.strip()

    for key in _OWNER_ENV_KEYS:
        value = os.getenv(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def rewrite_repo_slug(
    slug: Optional[str],
    *,
    owner_override: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Rewrite a repo slug (e.g., acme/core-api) so the owner matches the override.
    """

    if not slug or not isinstance(slug, str):
        return slug

    owner = owner_override or determine_repo_owner_override(config)
    if not owner:
        return slug

    parts = slug.split("/")
    if not parts:
        return slug

    if parts[0] == owner:
        return slug

    parts[0] = owner
    return "/".join(part for part in parts if part)


def rewrite_github_url(
    url: Optional[str],
    *,
    owner_override: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Ensure any GitHub URL uses the configured repo owner.
    """

    if not url or not isinstance(url, str):
        return url

    owner = owner_override or determine_repo_owner_override(config)
    if not owner:
        return url

    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "github.com" not in host:
        return url

    path_segments = [segment for segment in parsed.path.split("/") if segment]
    if not path_segments:
        return url

    if path_segments[0] == owner:
        return url

    path_segments[0] = owner
    new_path = "/" + "/".join(path_segments)
    updated = parsed._replace(path=new_path)
    return urlunparse(updated)


__all__ = [
    "determine_repo_owner_override",
    "rewrite_repo_slug",
    "rewrite_github_url",
]

