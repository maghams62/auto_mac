"""
Feasibility checker for deciding when to route UI automations through the
vision-assisted fallback path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import logging


logger = logging.getLogger(__name__)


@dataclass
class FeasibilityDecision:
    use_vision: bool
    confidence: float
    reason: str


class FeasibilityChecker:
    """
    Lightweight heuristic framework that decides whether to escalate a UI
    automation step to the vision-assisted pipeline.
    """

    def __init__(self, vision_config):
        # Handle both dict and VisionSettings dataclass
        if hasattr(vision_config, 'enabled'):
            # It's a VisionSettings dataclass
            self.enabled: bool = vision_config.enabled
            self.min_confidence: float = float(vision_config.min_confidence)
            self.max_calls_per_session: int = int(vision_config.max_calls_per_session)
            self.max_calls_per_task: int = int(vision_config.max_calls_per_task)
            self.retry_threshold: int = int(vision_config.retry_threshold)
            self.eligible_tools = set(vision_config.eligible_tools)
        else:
            # It's a dict (backward compatibility)
            self.enabled: bool = vision_config.get("enabled", False)
            self.min_confidence: float = float(vision_config.get("min_confidence", 0.6))
            self.max_calls_per_session: int = int(vision_config.get("max_calls_per_session", 5))
            self.max_calls_per_task: int = int(vision_config.get("max_calls_per_task", 2))
            self.retry_threshold: int = int(vision_config.get("retry_threshold", 2))
            self.eligible_tools = set(vision_config.get("eligible_tools", []))

    def is_tool_eligible(self, tool_name: str) -> bool:
        if not self.enabled:
            return False
        if not self.eligible_tools:
            return True
        return tool_name in self.eligible_tools

    def should_use_vision(
        self,
        tool_name: str,
        attempt_count: int,
        recent_errors: Optional[List[str]],
        vision_usage: Dict[str, Any]
    ) -> FeasibilityDecision:
        """
        Decide whether to route the current tool execution through the vision path.

        Args:
            tool_name: Name of the tool about to run.
            attempt_count: Number of times this tool has already been attempted.
            recent_errors: Recent error messages from this tool (if any).
            vision_usage: Vision usage metadata stored on the agent state.
        """
        if not self.is_tool_eligible(tool_name):
            return FeasibilityDecision(False, 0.0, "Tool not eligible")

        vision_usage.setdefault("count", 0)
        vision_usage.setdefault("session_count", 0)

        total_calls = vision_usage.get("count", 0)
        if total_calls >= self.max_calls_per_task:
            return FeasibilityDecision(False, 0.0, "Vision usage capped for this task")

        session_total = vision_usage.get("session_count", 0)
        if session_total >= self.max_calls_per_session:
            return FeasibilityDecision(False, 0.0, "Vision usage capped for session")

        # Base confidence derived from number of attempts.
        base_confidence = min(1.0, 0.25 * max(0, attempt_count - 1))

        # Additional confidence for repeated errors or specific patterns.
        error_list = recent_errors or []
        error_bonus = 0.0
        if error_list:
            unique_errors = {msg.strip().lower() for msg in error_list if msg}
            error_bonus = min(0.4, 0.1 * len(unique_errors))

        confidence = min(1.0, base_confidence + error_bonus)

        reason_parts = []
        if attempt_count > 1:
            reason_parts.append(f"{attempt_count} attempts")
        if error_list:
            reason_parts.append(f"{len(error_list)} recent error(s)")
        if not reason_parts:
            reason_parts.append("heuristic escalation")

        reason = ", ".join(reason_parts)

        if attempt_count < self.retry_threshold:
            return FeasibilityDecision(False, confidence, "Below retry threshold")

        if confidence < self.min_confidence:
            return FeasibilityDecision(False, confidence, "Confidence below threshold")

        logger.info(
            "[FEASIBILITY] Escalating %s to vision path (confidence=%.2f, reason=%s)",
            tool_name,
            confidence,
            reason,
        )
        return FeasibilityDecision(True, confidence, reason)
