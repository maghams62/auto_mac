"""Automation-related helpers derived from settings."""
from __future__ import annotations

from typing import Literal

from .manager import get_global_settings_manager

AutomationMode = Literal["off", "suggest_only", "pr_only", "pr_and_auto_merge"]


def get_doc_update_mode(
    domain: str,
    *,
    default: AutomationMode = "off",
    settings_manager=None,
) -> AutomationMode:
    manager = settings_manager or get_global_settings_manager()
    settings = manager.get_effective_settings()
    doc_updates = (settings.get("automation") or {}).get("docUpdates") or {}
    entry = doc_updates.get(domain)
    if not entry:
        return default
    return entry.get("mode", default)


def allows_auto_merge(domain: str, *, settings_manager=None) -> bool:
    return get_doc_update_mode(domain, settings_manager=settings_manager) == "pr_and_auto_merge"


def allows_pr_creation(domain: str, *, settings_manager=None) -> bool:
    mode = get_doc_update_mode(domain, settings_manager=settings_manager)
    return mode in {"pr_only", "pr_and_auto_merge"}


def allows_auto_suggestions(domain: str, *, settings_manager=None) -> bool:
    mode = get_doc_update_mode(domain, settings_manager=settings_manager)
    return mode in {"suggest_only", "pr_only", "pr_and_auto_merge"}

