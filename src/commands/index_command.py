from __future__ import annotations

import concurrent.futures
import logging
from typing import Dict, List, Optional, Tuple

from telemetry.config import log_structured, set_span_error

from ..search import SearchRegistry

logger = logging.getLogger(__name__)


class IndexCommand:
    """
    Coordinate ingestion across modality handlers based on /index requests.
    """

    def __init__(self, registry: SearchRegistry):
        self.registry = registry

    def run(self, task: Optional[str] = None) -> Dict[str, any]:
        if not self.registry.config.enabled:
            return {
                "status": "error",
                "message": "Universal search is disabled. Enable `search.enabled` in config.yaml.",
            }

        requested_modalities = self._parse_targets(task)
        if not requested_modalities:
            return {
                "status": "error",
                "message": "No modalities matched the request.",
            }

        target_modalities = [entry[0] for entry in requested_modalities]
        log_structured(
            "info",
            "/index starting",
            requested_modalities=target_modalities,
            task=task or "",
        )

        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(requested_modalities)) as executor:
            future_map: Dict[concurrent.futures.Future, Tuple[str, int]] = {}
            for modality_id, handler, config in requested_modalities:
                timeout_sec = max(1.0, config.timeout_ms / 1000.0)
                future = executor.submit(self._ingest_single, modality_id, handler, config)
                future_map[future] = (modality_id, timeout_sec)

            for future, (modality_id, timeout_sec) in future_map.items():
                try:
                    result_payload = future.result(timeout=timeout_sec)
                    results[modality_id] = {"status": "success", "result": result_payload}
                    log_structured(
                        "info",
                        "/index modality success",
                        modality_id=modality_id,
                        result=result_payload,
                    )
                except concurrent.futures.TimeoutError:
                    logger.warning("[SEARCH][INDEX] %s timed out after %ss", modality_id, timeout_sec)
                    results[modality_id] = {"status": "timeout", "error": f"Timed out after {timeout_sec}s"}
                    self.registry.update_state(modality_id, last_error="timeout")
                    log_structured(
                        "warning",
                        "/index modality timeout",
                        modality_id=modality_id,
                        timeout_seconds=timeout_sec,
                    )
                except Exception as exc:
                    logger.exception("[SEARCH][INDEX] %s failed", modality_id)
                    results[modality_id] = {"status": "error", "error": str(exc)}
                    self.registry.update_state(modality_id, last_error=str(exc))
                    set_span_error(None, exc, {"modality_id": modality_id})
                    log_structured(
                        "error",
                        "/index modality error",
                        modality_id=modality_id,
                        error=str(exc),
                    )

        success_modalities = [mid for mid, payload in results.items() if payload["status"] == "success"]
        message = (
            "Indexed: " + ", ".join(success_modalities)
            if success_modalities
            else "Index attempt finished with warnings."
        )

        log_structured(
            "info",
            "/index completed",
            succeeded=success_modalities,
            failed=[mid for mid, payload in results.items() if payload["status"] != "success"],
        )

        return {
            "status": "success",
            "message": message,
            "data": results,
        }

    # ------------------------------------------------------------------ #
    def _parse_targets(
        self,
        task: Optional[str],
    ) -> List[Tuple[str, any, any]]:
        task = (task or "").strip()
        available_handlers = list(self.registry.iter_ingestion_handlers())
        if not task:
            return [
                (config.modality_id, handler, config)
                for handler, config, _state in available_handlers
            ]

        tokens = [token.lower() for token in task.split()]
        requested = []
        for modality_id in tokens:
            handler = self.registry.get_handler(modality_id)
            config = self.registry.config.get(modality_id)
            if not handler or not config:
                logger.info("[SEARCH][INDEX] Unknown modality requested via /index: %s", modality_id)
                continue
            requested.append((modality_id, handler, config))
        return requested

    def _ingest_single(self, modality_id: str, handler, config) -> Dict[str, any]:
        logger.info("[SEARCH][INDEX] Running ingestion for %s", modality_id)
        result = handler.ingest()
        self.registry.update_state(modality_id, last_error=None, extra={"last_result": result})
        return result

