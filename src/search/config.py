"""
search.config
==============

LLM-facing helpers for loading the universal search configuration.

The goal is to provide deterministic, declarative control over which
modalities participate in /setup, /index, and /cerebros.  The config is
defined under `config.yaml -> search` and can be extended with more
modalities over time without rewriting the command logic.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return default


@dataclass(frozen=True)
class SearchDefaults:
    """Global defaults applied to every modality unless overridden."""

    max_results_per_modality: int = 5
    timeout_ms_per_modality: int = 2000
    web_fallback_weight: float = 0.6


@dataclass(frozen=True)
class PlannerRule:
    """Simple keyword→modality mapping used by the heuristic planner."""

    name: str
    include: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)

    def matches(self, question: str) -> bool:
        normalized = (question or "").lower()
        for keyword in self.keywords:
            token = (keyword or "").strip().lower()
            if not token:
                continue
            if token in normalized:
                return True
        return False


@dataclass(frozen=True)
class PlannerConfig:
    enabled: bool = True
    rules: List[PlannerRule] = field(default_factory=list)


@dataclass
class ModalityConfig:
    """
    Declarative configuration for a single modality (slack/git/files/...).

    The registry relies on this structure to determine whether a modality
    should ingest/query, how long it may run, and how heavily to weight the
    resulting matches when ranking universal search results.
    """

    modality_id: str
    enabled: bool
    scope: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    timeout_ms: int = 2000
    max_results: int = 5
    fallback_only: bool = False

    def is_queryable(self) -> bool:
        """
        True if the modality is enabled and not marked fallback-only.
        Fallback-only modalities (e.g., web search) are invoked only after
        internal sources fail.
        """

        return self.enabled and not self.fallback_only


@dataclass
class SearchConfig:
    """Root configuration object consumed by /setup, /index, /cerebros."""

    enabled: bool
    workspace_id: str
    defaults: SearchDefaults
    modalities: Dict[str, ModalityConfig]
    raw_hash: str
    planner: PlannerConfig

    def enabled_modalities(self, *, include_fallback: bool = True) -> Dict[str, ModalityConfig]:
        """
        Return the subset of modalities that are enabled, optionally excluding
        fallback-only modalities (web search).
        """

        result = {}
        for modality_id, modality in self.modalities.items():
            if not modality.enabled:
                continue
            if not include_fallback and modality.fallback_only:
                continue
            result[modality_id] = modality
        return result

    def get(self, modality_id: str) -> Optional[ModalityConfig]:
        return self.modalities.get(modality_id)

    def iter(self) -> Iterable[ModalityConfig]:
        return self.modalities.values()


def load_search_config(app_config: Dict[str, Any]) -> SearchConfig:
    """
    Load the search config from the global config snapshot.

    Args:
        app_config: Result of config_manager.get_config()
    """

    search_cfg = (app_config or {}).get("search") or {}
    enabled = _coerce_bool(search_cfg.get("enabled"), default=False)
    workspace_id = search_cfg.get("workspace_id") or "default_workspace"

    defaults_cfg = search_cfg.get("defaults") or {}
    defaults = SearchDefaults(
        max_results_per_modality=int(defaults_cfg.get("max_results_per_modality", 5)),
        timeout_ms_per_modality=int(defaults_cfg.get("timeout_ms_per_modality", 2000)),
        web_fallback_weight=float(defaults_cfg.get("web_fallback_weight", 0.6)),
    )

    modalities_cfg = search_cfg.get("modalities") or {}
    modalities: Dict[str, ModalityConfig] = {}
    for modality_id, cfg in modalities_cfg.items():
        cfg = cfg or {}
        modality = ModalityConfig(
            modality_id=modality_id,
            enabled=_coerce_bool(cfg.get("enabled"), default=False),
            scope=_extract_scope(cfg),
            weight=float(cfg.get("weight", 1.0)),
            timeout_ms=int(cfg.get("timeout_ms", defaults.timeout_ms_per_modality)),
            max_results=int(cfg.get("max_results", defaults.max_results_per_modality)),
            fallback_only=_coerce_bool(cfg.get("fallback_only"), default=False),
        )
        modalities[modality_id] = modality

    planner = _load_planner_config(search_cfg, modalities)
    raw_hash = _hash_config(search_cfg)
    return SearchConfig(
        enabled=enabled,
        workspace_id=workspace_id,
        defaults=defaults,
        modalities=modalities,
        raw_hash=raw_hash,
        planner=planner,
    )


def _extract_scope(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize modality-specific scope keys into a dict.

    The registry deliberately keeps this opaque so modality handlers can
    interpret the keys they care about (channels, repos, roots, etc.).
    """

    scope_keys = ("channels", "repos", "roots", "videos", "video_ids", "filters")
    scope: Dict[str, Any] = {}
    for key in scope_keys:
        if key in cfg:
            scope[key] = cfg[key]
    # Include any nested scope block verbatim
    if isinstance(cfg.get("scope"), dict):
        scope.update(cfg["scope"])
    return scope


def _load_planner_config(search_cfg: Dict[str, Any], modalities: Dict[str, ModalityConfig]) -> PlannerConfig:
    planner_cfg = search_cfg.get("planner") or {}
    enabled = _coerce_bool(planner_cfg.get("enabled"), default=True)
    rules_cfg = planner_cfg.get("rules") or []
    rules: List[PlannerRule] = []
    if rules_cfg:
        for index, rule_cfg in enumerate(rules_cfg):
            rule_name = rule_cfg.get("name") or f"rule_{index}"
            include = [mid for mid in rule_cfg.get("include", []) if mid in modalities]
            keywords = [kw for kw in rule_cfg.get("keywords", []) if kw]
            if include and keywords:
                rules.append(PlannerRule(name=rule_name, include=include, keywords=keywords))
    if not rules:
        rules = _default_planner_rules(modalities)
    return PlannerConfig(enabled=enabled, rules=rules)


def _default_planner_rules(modalities: Dict[str, ModalityConfig]) -> List[PlannerRule]:
    defaults = [
        ("code", ["git", "files"], ["stack trace", ".py", "exception", "error code", "traceback"]),
        ("chat", ["slack"], ["slack", "dm", "channel", "thread", "conversation"]),
        ("video", ["youtube"], ["video", "youtube", "talk", "lecture", "watch"]),
    ]
    rules: List[PlannerRule] = []
    for name, include, keywords in defaults:
        filtered_include = [mid for mid in include if mid in modalities]
        if not filtered_include:
            continue
        rules.append(PlannerRule(name=name, include=filtered_include, keywords=keywords))
    return rules


def _hash_config(search_cfg: Dict[str, Any]) -> str:
    """
    Produce a deterministic hash for the search config.
    Stored alongside cached ingestion metadata so we can detect when a
    modality needs to be re-indexed due to config changes.
    """

    serialized = repr(_stable_sort(search_cfg)).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _stable_sort(value: Any) -> Any:
    """
    Recursively sort lists/dicts to ensure consistent hashing.
    """

    if isinstance(value, dict):
        return {k: _stable_sort(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_stable_sort(item) for item in value]
    return value

