"""Runtime mode helper layered on top of config + env.

This provides a single high-level switch (CEREBROS_MODE / config.runtime.mode)
that controls whether we default to live integrations vs fast/synthetic dev flows.

Design goals:
- Do NOT hardcode workspace-specific values (repos, channels, etc.)
- Only derive boolean feature flags and env overrides from a small set of modes.
- Never override an explicit env var the user has already set.
"""

from __future__ import annotations

import enum
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


class RuntimeMode(str, enum.Enum):
    DEV = "dev"
    DEMO = "demo"
    LIVE = "live"

    @classmethod
    def from_str(cls, value: Optional[str]) -> "RuntimeMode":
        """Parse a runtime mode string with sane fallbacks."""
        if not value:
            return cls.DEV

        normalized = value.strip().lower()

        # Common aliases
        if normalized in {"prod", "production"}:
            return cls.LIVE
        if normalized in {"stage", "staging"}:
            # Treat staging as live from a feature-flag perspective
            return cls.LIVE

        for m in cls:
            if normalized == m.value:
                return m

        logger.warning("[RUNTIME_MODE] Unknown mode %r, defaulting to dev", value)
        return cls.DEV


@dataclass(frozen=True)
class RuntimeFlags:
    """Derived feature flags for the current runtime mode.

    These are intentionally generic booleans; individual subsystems decide
    how to interpret them (e.g., whether "live git" means enabling PR service
    or just allowing read‑only metadata calls).
    """

    mode: RuntimeMode

    # High-level toggles
    enable_live_git: bool
    enable_live_slack: bool
    enable_live_graph: bool

    # Whether to prefer synthetic fixtures / test endpoints
    enable_fixtures: bool

    # Whether to run heavier background workers (ingest, warmers, schedulers)
    enable_heavy_workers: bool


def detect_runtime_mode(config: Dict[str, Any]) -> RuntimeMode:
    """Detect current runtime mode from env and config.

    Priority:
    1. CEREBROS_MODE env var
    2. config["runtime"]["mode"]
    3. default "dev"
    """
    env_mode = os.getenv("CEREBROS_MODE")
    if env_mode:
        mode = RuntimeMode.from_str(env_mode)
        logger.info("[RUNTIME_MODE] CEREBROS_MODE=%s -> %s", env_mode, mode.value)
        return mode

    runtime_cfg = (config.get("runtime") or {}) if isinstance(config, dict) else {}
    cfg_mode = runtime_cfg.get("mode")
    if cfg_mode:
        mode = RuntimeMode.from_str(str(cfg_mode))
        logger.info("[RUNTIME_MODE] config.runtime.mode=%s -> %s", cfg_mode, mode.value)
        return mode

    logger.info("[RUNTIME_MODE] No mode configured; defaulting to dev")
    return RuntimeMode.DEV


def build_runtime_flags(config: Dict[str, Any]) -> RuntimeFlags:
    """Build derived feature flags for the current mode.

    We keep this mapping intentionally small and generic so it is easy to
    reason about and easy to override with explicit env vars if needed.
    """
    mode = detect_runtime_mode(config)

    if mode is RuntimeMode.LIVE:
        return RuntimeFlags(
            mode=mode,
            enable_live_git=True,
            enable_live_slack=True,
            enable_live_graph=True,
            enable_fixtures=False,
            enable_heavy_workers=True,
        )

    # DEV / DEMO: default to fast, fixture‑friendly behavior.
    # Demo is currently identical to dev from a backend perspective; the UI
    # can still distinguish them via NEXT_PUBLIC_MODE if desired.
    return RuntimeFlags(
        mode=mode,
        enable_live_git=False,
        enable_live_slack=False,
        enable_live_graph=False,
        enable_fixtures=True,
        enable_heavy_workers=False,
    )


def apply_runtime_env_overrides(flags: RuntimeFlags) -> None:
    """Best‑effort env defaults driven by runtime flags.

    IMPORTANT:
    - We NEVER overwrite an env var that is already set.
    - We only touch env toggles that are already documented elsewhere
      (e.g., in docs/live_mode_audit.md and quickstart docs).
    - This function is idempotent and cheap; safe to call at startup.
    """

    # Helper so we never clobber explicit user settings.
    def _set_default_env(key: str, value: str) -> None:
        if key in os.environ:
            return
        os.environ[key] = value
        logger.info("[RUNTIME_MODE] Defaulted %s=%s", key, value)

    # Neo4j / graph backend
    if flags.enable_live_graph:
        _set_default_env("NEO4J_ENABLED", "true")
    else:
        _set_default_env("NEO4J_ENABLED", "false")

    # Slash Git live vs synthetic dataset
    if flags.enable_live_git:
        _set_default_env("SLASH_GIT_USE_LIVE_DATA", "true")
        # Let SLASH_GIT_DATA_MODE default from config.yaml unless overridden
    else:
        _set_default_env("SLASH_GIT_USE_LIVE_DATA", "false")
        # Bias toward graph‑only / synthetic unless caller explicitly opts into live
        _set_default_env("SLASH_GIT_DATA_MODE", "graph")

    # Impact pipeline data mode (doc issues, synthetic vs live)
    # We keep LIVE as default even in dev/demo so that most flows still
    # exercise the real pipeline once data is ingested, but honor an
    # explicit IMPACT_DATA_MODE if the user sets one.
    if flags.mode is RuntimeMode.LIVE:
        _set_default_env("IMPACT_DATA_MODE", "live")
    else:
        # For dev/demo, prefer fast synthetic fixtures if available.
        _set_default_env("IMPACT_DATA_MODE", "synthetic")

    # Test fixture endpoints (Brain Universe, synthetic graph endpoints, etc.)
    if flags.enable_fixtures:
        _set_default_env("ENABLE_TEST_FIXTURE_ENDPOINTS", "1")
    else:
        _set_default_env("ENABLE_TEST_FIXTURE_ENDPOINTS", "0")

    # Slack/Git ingest and heavy workers can later hook into these:
    _set_default_env("CEREBROS_ENABLE_HEAVY_WORKERS", "1" if flags.enable_heavy_workers else "0")



