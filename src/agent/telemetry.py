"""
Lightweight telemetry manager for agent workflow instrumentation.

Provides simple in-memory tracking so higher-level components can record
phase starts/ends and reasoning breadcrumbs without requiring an external
observability stack.
"""

from datetime import datetime
import logging
import uuid
from threading import Lock
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


class TelemetryManager:
    """In-memory telemetry collector for automation workflows."""

    def __init__(self):
        self._lock = Lock()
        self._requests: Dict[str, Dict[str, Any]] = {}
        self._max_requests = 500  # Prevent unbounded growth

    def start_request(self, user_request: str, session_id: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Begin tracking a new automation request and return its correlation ID."""
        correlation_id = f"req_{uuid.uuid4().hex}"
        with self._lock:
            self._requests[correlation_id] = {
                "user_request": user_request,
                "session_id": session_id,
                "context": context or {},
                "started_at": datetime.utcnow().isoformat(),
                "phases": {},
                "reasoning_steps": [],
            }
            self._trim_if_needed()
        logger.debug(f"[TELEMETRY] Started request {correlation_id} ({session_id})")
        return correlation_id

    def record_phase_start(self, correlation_id: str, phase: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record the beginning of a workflow phase."""
        with self._lock:
            request = self._requests.get(correlation_id)
            if not request:
                logger.debug(f"[TELEMETRY] Missing request for phase start: {correlation_id}")
                return
            phases = request["phases"]
            phases[phase] = {
                "started_at": datetime.utcnow().isoformat(),
                "metadata": metadata or {},
            }
        logger.debug(f"[TELEMETRY] Phase start {phase} ({correlation_id})")

    def record_phase_end(
        self,
        correlation_id: str,
        phase: str,
        *,
        success: bool,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record completion of a workflow phase."""
        with self._lock:
            request = self._requests.get(correlation_id)
            if not request:
                logger.debug(f"[TELEMETRY] Missing request for phase end: {correlation_id}")
                return
            phase_entry = request["phases"].setdefault(
                phase,
                {
                    "started_at": datetime.utcnow().isoformat(),
                    "metadata": {},
                },
            )
            phase_entry["ended_at"] = datetime.utcnow().isoformat()
            phase_entry["success"] = success
            if error_message:
                phase_entry["error_message"] = error_message
            if metadata:
                phase_entry.setdefault("metadata", {}).update(metadata)
        logger.debug(f"[TELEMETRY] Phase end {phase} ({correlation_id}) success={success}")

    def record_reasoning_step(
        self,
        correlation_id: str,
        step_name: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append a reasoning breadcrumb for the current request."""
        with self._lock:
            request = self._requests.get(correlation_id)
            if not request:
                logger.debug(f"[TELEMETRY] Missing request for reasoning step: {correlation_id}")
                return
            request["reasoning_steps"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "step": step_name,
                "message": message,
                "metadata": metadata or {},
            })

    def end_request(self, correlation_id: str, final_result: Optional[Dict[str, Any]] = None) -> None:
        """Mark a request as completed and store its final result."""
        with self._lock:
            request = self._requests.get(correlation_id)
            if not request:
                logger.debug(f"[TELEMETRY] Missing request for completion: {correlation_id}")
                return
            request["completed_at"] = datetime.utcnow().isoformat()
            if final_result is not None:
                request["final_result"] = final_result
        logger.debug(f"[TELEMETRY] Completed request {correlation_id}")

    def get_request_summary(self, correlation_id: str) -> Optional[Dict[str, Any]]:
        """Return stored telemetry summary for a specific request."""
        with self._lock:
            request = self._requests.get(correlation_id)
            if not request:
                return None
            return dict(request)

    def _trim_if_needed(self) -> None:
        """Trim oldest entries if telemetry store grows too large."""
        if len(self._requests) <= self._max_requests:
            return
        excess = len(self._requests) - self._max_requests
        for correlation_id in list(self._requests.keys())[:excess]:
            del self._requests[correlation_id]


_TELEMETRY_INSTANCE: Optional[TelemetryManager] = None
_TELEMETRY_LOCK = Lock()


def get_telemetry() -> TelemetryManager:
    """Get singleton telemetry manager instance."""
    global _TELEMETRY_INSTANCE
    if _TELEMETRY_INSTANCE is None:
        with _TELEMETRY_LOCK:
            if _TELEMETRY_INSTANCE is None:
                _TELEMETRY_INSTANCE = TelemetryManager()
                logger.info("[TELEMETRY] Initialized telemetry manager")
    return _TELEMETRY_INSTANCE
