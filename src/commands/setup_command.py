from __future__ import annotations

import json
from dataclasses import asdict
from typing import Dict, Optional

from telemetry.config import log_structured

from ..search import SearchConfig, SearchRegistry


class SetupCommand:
    """
    Read-only configuration helper that surfaces modality status, config, and
    registry metadata for /setup.
    """

    def __init__(self, search_config: SearchConfig, registry: SearchRegistry):
        self.search_config = search_config
        self.registry = registry

    def run(self, task: Optional[str] = None) -> Dict[str, any]:
        task = (task or "").strip()
        if not self.search_config.enabled:
            return {
                "status": "error",
                "message": "Universal search is disabled in config.yaml under `search.enabled`.",
                "details": "Set search.enabled=true and rerun /setup.",
            }

        if not task:
            return self._status_payload()

        parts = task.split()
        verb = parts[0].lower()
        if verb in {"detail", "show"} and len(parts) >= 2:
            modality_id = parts[1]
            return self._detail_payload(modality_id)

        if verb == "config":
            return {
                "status": "success",
                "message": "Search config snapshot",
                "data": _serialize_config(self.search_config),
            }

        return {
            "status": "error",
            "message": f"Unknown /setup directive '{task}'.",
            "details": "Supported: `/setup`, `/setup detail <modality>`, `/setup config`.",
        }

    # ------------------------------------------------------------------ #
    def _status_payload(self) -> Dict[str, any]:
        rows = []
        reindex_needed = []
        for modality_id, modality_cfg in self.search_config.modalities.items():
            state = self.registry.get_state(modality_id)
            config_stale = bool(
                state.config_hash and state.config_hash != self.search_config.raw_hash
            )
            if config_stale:
                reindex_needed.append(modality_id)
            rows.append(
                {
                    "modality": modality_id,
                    "enabled": modality_cfg.enabled,
                    "can_ingest": modality_cfg.enabled,
                    "fallback_only": modality_cfg.fallback_only,
                    "last_indexed_at": state.last_indexed_at,
                    "last_error": state.last_error,
                    "config_hash": state.config_hash,
                    "needs_reindex": config_stale,
                    "warning": "Config changed; re-run /index" if config_stale else None,
                }
            )

        message = "Active modalities:\n" + "\n".join(
            [
                f"- {row['modality']}: enabled={row['enabled']} last_indexed={row['last_indexed_at'] or 'never'}"
                for row in rows
            ]
        )
        if reindex_needed:
            message += "\n⚠ Needs re-index: " + ", ".join(sorted(reindex_needed))

        log_structured(
            "info",
            "/setup status summary",
            reindex_needed=reindex_needed,
            total_modalities=len(rows),
            disabled=[row["modality"] for row in rows if not row["enabled"]],
        )

        return {
            "status": "success",
            "message": message,
            "data": {"modalities": rows},
        }

    def _detail_payload(self, modality_id: str) -> Dict[str, any]:
        modality_cfg = self.search_config.modalities.get(modality_id)
        if not modality_cfg:
            return {
                "status": "error",
                "message": f"Unknown modality '{modality_id}'.",
            }
        state = self.registry.get_state(modality_id)
        payload = {
            "config": {
                "enabled": modality_cfg.enabled,
                "weight": modality_cfg.weight,
                "timeout_ms": modality_cfg.timeout_ms,
                "max_results": modality_cfg.max_results,
                "scope": modality_cfg.scope,
                "fallback_only": modality_cfg.fallback_only,
            },
            "state": state.to_dict(),
        }
        return {
            "status": "success",
            "message": f"Details for modality '{modality_id}'.",
            "data": payload,
        }


def _serialize_config(config: SearchConfig) -> Dict[str, any]:
    return {
        "enabled": config.enabled,
        "workspace_id": config.workspace_id,
        "defaults": asdict(config.defaults),
        "modalities": {
            modality_id: {
                "enabled": modality.enabled,
                "weight": modality.weight,
                "timeout_ms": modality.timeout_ms,
                "max_results": modality.max_results,
                "fallback_only": modality.fallback_only,
                "scope": modality.scope,
            }
            for modality_id, modality in config.modalities.items()
        },
    }

