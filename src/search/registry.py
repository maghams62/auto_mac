"""
Registry for universal search modality handlers.

The registry glues together:
    - Declarative config (`SearchConfig`)
    - Runtime handler instances (Slack/Git/Files/etc.)
    - Persistent state (last indexed timestamps, config hash, errors)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from telemetry.config import log_structured

from .config import ModalityConfig, SearchConfig
from .modalities import BaseModalityHandler


@dataclass
class ModalityState:
    """Persisted metadata about a modality's ingestion status."""

    modality_id: str
    last_indexed_at: Optional[str] = None
    last_error: Optional[str] = None
    config_hash: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modality_id": self.modality_id,
            "last_indexed_at": self.last_indexed_at,
            "last_error": self.last_error,
            "config_hash": self.config_hash,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModalityState":
        return cls(
            modality_id=data.get("modality_id") or "unknown",
            last_indexed_at=data.get("last_indexed_at"),
            last_error=data.get("last_error"),
            config_hash=data.get("config_hash"),
            extra=data.get("extra") or {},
        )


class SearchRegistry:
    """
    Central registry for modality handlers + state.

    Usage:
        registry = SearchRegistry(load_search_config(app_config))
        registry.register_handler(SlackHandler(...))
        for handler, config, state in registry.iter_ingestion_handlers():
            handler.ingest(...)
            registry.update_state(handler.modality_id, last_indexed_at=now_iso)
    """

    def __init__(
        self,
        config: SearchConfig,
        state_path: Path | str = "data/state/search_registry.json",
    ):
        self.config = config
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._handlers: Dict[str, BaseModalityHandler] = {}
        self._state: Dict[str, ModalityState] = self._load_state()

    # ------------------------------------------------------------------
    # Handler registration / lookup
    # ------------------------------------------------------------------
    def register_handler(self, handler: BaseModalityHandler) -> None:
        self._handlers[handler.modality_id] = handler

    def get_handler(self, modality_id: str) -> Optional[BaseModalityHandler]:
        return self._handlers.get(modality_id)

    def iter_ingestion_handlers(self) -> Iterable[Tuple[BaseModalityHandler, ModalityConfig, ModalityState]]:
        for modality_id, handler in self._handlers.items():
            config = self.config.get(modality_id)
            if not self._should_run_handler(config):
                continue
            if not handler.can_ingest():
                continue
            yield handler, config, self.get_state(modality_id)

    def iter_query_handlers(
        self,
        *,
        include_fallback: bool = False,
        modalities: Optional[Iterable[str]] = None,
    ) -> Iterable[Tuple[BaseModalityHandler, ModalityConfig, ModalityState]]:
        modality_filter = set(modalities) if modalities is not None else None
        for modality_id, handler in self._handlers.items():
            if modality_filter is not None and modality_id not in modality_filter:
                continue
            config = self.config.get(modality_id)
            if not self._should_run_handler(config, include_fallback=include_fallback):
                continue
            if not handler.can_query():
                continue
            yield handler, config, self.get_state(modality_id)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def get_state(self, modality_id: str) -> ModalityState:
        if modality_id not in self._state:
            self._state[modality_id] = ModalityState(modality_id=modality_id)
        return self._state[modality_id]

    def update_state(
        self,
        modality_id: str,
        *,
        last_error: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        touched_at: Optional[datetime] = None,
    ) -> ModalityState:
        state = self.get_state(modality_id)
        state.last_indexed_at = _to_iso(touched_at or datetime.now(timezone.utc))
        state.last_error = last_error
        state.config_hash = self.config.raw_hash
        if extra:
            state.extra.update(extra)
        self._state[modality_id] = state
        self._persist_state()
        log_structured(
            "info",
            "search_registry_state_updated",
            modality_id=modality_id,
            last_indexed_at=state.last_indexed_at,
            last_error=state.last_error,
            extra=extra or {},
        )
        return state

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _should_run_handler(
        self,
        config: Optional[ModalityConfig],
        *,
        include_fallback: bool = False,
    ) -> bool:
        if not config or not config.enabled:
            return False
        if config.fallback_only and not include_fallback:
            return False
        return True

    def _load_state(self) -> Dict[str, ModalityState]:
        if not self.state_path.exists():
            return {}
        try:
            data = json.loads(self.state_path.read_text())
        except Exception:
            return {}
        snapshot = data.get("modalities") if isinstance(data, dict) else None
        if not snapshot:
            return {}
        return {
            modality_id: ModalityState.from_dict(value)
            for modality_id, value in snapshot.items()
        }

    def _persist_state(self) -> None:
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "modalities": {mid: state.to_dict() for mid, state in self._state.items()},
        }
        self.state_path.write_text(json.dumps(payload, indent=2))


def _to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()

