"""Runtime settings manager layered on top of config.yaml."""
from __future__ import annotations

import json
import logging
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

from .schema import (
    AutomationSettings,
    DomainAutomationSettings,
    DomainPolicy,
    GitMonitorSettings,
    SettingsEffective,
    SettingsOverrides,
    SourceOfTruthSettings,
)

logger = logging.getLogger(__name__)

_DEFAULT_DOMAIN_POLICIES: Dict[str, DomainPolicy] = {
    "api_params": DomainPolicy(
        priority=["code", "api_spec", "docs"],
        hints=["slack", "tickets"],
    ),
    "feature_flags": DomainPolicy(
        priority=["config", "code", "docs"],
        hints=["slack"],
    ),
}


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


class SettingsManager:
    """Loads defaults from config + JSON overrides and produces effective settings."""

    def __init__(
        self,
        config_manager,
        settings_path: str = "data/settings.json",
    ) -> None:
        from src.config_manager import ConfigManager  # local import to avoid cycles

        if not isinstance(config_manager, ConfigManager):
            raise TypeError("SettingsManager expects a ConfigManager instance")
        self._config_manager = config_manager
        self._settings_path = Path(settings_path)
        self._lock = threading.RLock()
        self._overrides: Dict[str, Any] = {}
        self._defaults: Dict[str, Any] = {}
        self._effective: Dict[str, Any] = {}
        self.reload()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def reload(self) -> None:
        """Reload settings overrides and recompute effective payload."""
        with self._lock:
            self._overrides = self._load_overrides()
            self._defaults = self._build_defaults()
            merged = self._merge_settings(self._defaults, self._overrides)
            self._effective = SettingsEffective(**merged).model_dump(by_alias=True)
            logger.info("[SETTINGS] Reloaded settings (overrides=%s)", bool(self._overrides))

    def get_effective_settings(self) -> Dict[str, Any]:
        with self._lock:
            return deepcopy(self._effective)

    def get_defaults(self) -> Dict[str, Any]:
        with self._lock:
            return deepcopy(self._defaults)

    def get_overrides(self) -> Dict[str, Any]:
        with self._lock:
            return deepcopy(self._overrides)

    def update_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Persist override updates and return the new effective payload."""
        with self._lock:
            validated = SettingsOverrides(**updates)
            update_blob = validated.model_dump(exclude_none=True, by_alias=True)
            if not update_blob:
                return deepcopy(self._effective)
            next_overrides = self._merge_settings(self._overrides, update_blob)
            self._write_overrides(next_overrides)
            self._overrides = next_overrides
            merged = self._merge_settings(self._defaults, self._overrides)
            self._effective = SettingsEffective(**merged).model_dump(by_alias=True)
            logger.info("[SETTINGS] Updated settings override")
            return deepcopy(self._effective)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_overrides(self) -> Dict[str, Any]:
        if not self._settings_path.exists():
            return {}
        try:
            data = json.loads(self._settings_path.read_text())
            model = SettingsOverrides(**data)
            return model.model_dump(exclude_none=True, by_alias=True)
        except Exception as exc:  # pragma: no cover - corrupted files rare
            logger.warning("[SETTINGS] Failed to load settings.json: %s", exc)
            return {}

    def _write_overrides(self, payload: Dict[str, Any]) -> None:
        _ensure_parent_dir(self._settings_path)
        serialized = json.dumps(payload, indent=2, sort_keys=True)
        self._settings_path.write_text(serialized)

    def _build_defaults(self) -> Dict[str, Any]:
        config = self._config_manager.get_config()
        defaults = {
            "version": 1,
            "sourceOfTruth": self._build_source_of_truth_defaults(config),
            "gitMonitor": self._build_git_monitor_defaults(config),
            "automation": self._build_automation_defaults(config),
        }
        return SettingsEffective(**defaults).model_dump(by_alias=True)

    @staticmethod
    def _merge_settings(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        if not overrides:
            return deepcopy(base)
        result = deepcopy(base)

        def _merge(target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
            for key, value in source.items():
                if (
                    key in target
                    and isinstance(target[key], dict)
                    and isinstance(value, dict)
                ):
                    target[key] = _merge(target[key], value)
                else:
                    target[key] = deepcopy(value)
            return target

        return _merge(result, overrides)

    def _build_source_of_truth_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        defaults = {}
        for domain, policy in _DEFAULT_DOMAIN_POLICIES.items():
            defaults[domain] = policy.model_dump(by_alias=True)
        # Hook for future config-derived defaults if needed.
        return SourceOfTruthSettings(domains=defaults).model_dump(by_alias=True)

    def _build_git_monitor_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        activity_cfg = (config.get("activity_ingest") or {}).get("git") or {}
        github_cfg = config.get("github") or {}
        default_branch = (
            activity_cfg.get("default_branch")
            or github_cfg.get("base_branch")
            or "main"
        )
        projects: Dict[str, list] = {}
        for repo_cfg in activity_cfg.get("repos", []):
            owner = repo_cfg.get("owner") or repo_cfg.get("repo_owner")
            name = repo_cfg.get("name") or repo_cfg.get("repo_name")
            repo_id = repo_cfg.get("repo_id")
            if not repo_id and owner and name:
                repo_id = f"{owner}/{name}"
            elif not repo_id and name:
                repo_id = name
            if not repo_id:
                continue
            branch = repo_cfg.get("branch") or default_branch
            project_id = repo_cfg.get("project_id") or repo_cfg.get("project") or "default"
            projects.setdefault(project_id, []).append({
                "repoId": repo_id,
                "branch": branch,
            })
        payload = {
            "defaultBranch": default_branch,
            "projects": projects,
        }
        return GitMonitorSettings(**payload).model_dump(by_alias=True)

    def _build_automation_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        impact_cfg = config.get("impact") or {}
        auto_from_slash = bool(impact_cfg.get("auto_from_slash"))
        default_mode = "suggest_only" if auto_from_slash else "off"
        doc_updates = {
            "api_params": DomainAutomationSettings(mode=default_mode).model_dump(by_alias=True)
        }
        payload = {"docUpdates": doc_updates}
        return AutomationSettings(**payload).model_dump(by_alias=True)


_global_settings_manager: Optional[SettingsManager] = None


def get_global_settings_manager(
    config_manager=None,
    settings_path: str = "data/settings.json",
) -> SettingsManager:
    """Return singleton SettingsManager, creating it if needed."""
    global _global_settings_manager
    if _global_settings_manager is None:
        if config_manager is None:
            from src.config_manager import get_global_config_manager

            config_manager = get_global_config_manager()
        _global_settings_manager = SettingsManager(
            config_manager=config_manager,
            settings_path=settings_path,
        )
    return _global_settings_manager


def set_global_settings_manager(manager: Optional[SettingsManager]) -> None:
    global _global_settings_manager
    _global_settings_manager = manager

