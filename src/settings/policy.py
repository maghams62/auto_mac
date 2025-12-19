"""Helpers for resolving source-of-truth policies."""
from __future__ import annotations

from typing import List, Optional

from .manager import get_global_settings_manager
from .schema import DomainPolicy

_DEFAULT_PRIORITY = ["code", "api_spec", "docs"]


def get_domain_policy(domain: str, *, settings_manager=None) -> DomainPolicy:
    """Return the configured policy for a domain (or defaults)."""
    manager = settings_manager or get_global_settings_manager()
    settings = manager.get_effective_settings()
    domains = (settings.get("sourceOfTruth") or {}).get("domains", {})
    payload = domains.get(domain)
    if not payload:
        return DomainPolicy(priority=list(_DEFAULT_PRIORITY), hints=[])
    return DomainPolicy(**payload)


def get_priority_list(domain: str, *, settings_manager=None) -> List[str]:
    """Convenience helper that only returns the priority ordering."""
    policy = get_domain_policy(domain, settings_manager=settings_manager)
    return policy.priority or list(_DEFAULT_PRIORITY)


def get_hint_sources(domain: str, *, settings_manager=None) -> List[str]:
    policy = get_domain_policy(domain, settings_manager=settings_manager)
    return policy.hints or []

