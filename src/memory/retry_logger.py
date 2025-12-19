"""
Retry Logging System for Cerebro OS

This module provides comprehensive logging for failed attempts and reasoning chains,
enabling smarter retries and recovery. It captures:
- Full reasoning traces for failed executions
- Codebase context and configuration
- Recovery instructions for fresh LLMs
- Retry patterns and corrective actions
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

from .reasoning_trace import ReasoningStage, OutcomeStatus
from ..utils.trajectory_logger import get_trajectory_logger


logger = logging.getLogger(__name__)


class RetryReason(Enum):
    """Reasons for retry attempts."""
    TOOL_FAILURE = "tool_failure"
    VERIFICATION_FAILED = "verification_failed"
    PLANNING_ERROR = "planning_error"
    EXECUTION_ERROR = "execution_error"
    CRITIC_RECOMMENDED = "critic_recommended"
    USER_REQUESTED = "user_requested"
    TIMEOUT = "timeout"
    RESOURCE_UNAVAILABLE = "resource_unavailable"


class RecoveryPriority(Enum):
    """Priority levels for recovery attempts."""
    CRITICAL = "critical"  # Must succeed for workflow completion
    HIGH = "high"         # Important but workflow can continue
    MEDIUM = "medium"     # Nice to have, can be skipped
    LOW = "low"          # Optional, can be deferred


@dataclass
class CodebaseContext:
    """Context about the codebase for LLM understanding."""
    project_name: str = "Cerebro OS"
    version: str = "2.0"
    architecture: str = "LangGraph multi-agent system"
    key_components: List[str] = field(default_factory=lambda: [
        "LangGraph automation agent", "Agent registry", "Specialist agents",
        "Session memory", "Reasoning trace system", "Critic agent"
    ])
    config_requirements: Dict[str, Any] = field(default_factory=dict)
    environment_variables: List[str] = field(default_factory=lambda: [
        "OPENAI_API_KEY", "DISCORD_EMAIL", "DISCORD_PASSWORD", "GOOGLE_MAPS_API_KEY"
    ])
    important_paths: Dict[str, str] = field(default_factory=lambda: {
        "config": "config.yaml",
        "logs": "data/app.log",
        "sessions": "data/sessions/",
        "documents": "tests/data/test_docs/"
    })

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


@dataclass
class RetryEntry:
    """Complete retry context for a failed attempt."""
    retry_id: str
    session_id: str
    interaction_id: str
    attempt_number: int
    timestamp: str

    # Failure details
    reason: RetryReason
    priority: RecoveryPriority
    failed_action: str
    error_message: str
    error_type: str

    # Execution context
    user_request: str
    current_plan: Optional[Dict[str, Any]] = None
    execution_state: Dict[str, Any] = field(default_factory=dict)
    tool_parameters: Dict[str, Any] = field(default_factory=dict)

    # Reasoning chain (from reasoning trace)
    reasoning_trace: List[Dict[str, Any]] = field(default_factory=list)
    critic_feedback: List[Dict[str, Any]] = field(default_factory=list)

    # Recovery context
    suggested_fixes: List[str] = field(default_factory=list)
    alternative_approaches: List[str] = field(default_factory=list)
    required_changes: Dict[str, Any] = field(default_factory=dict)

    # Codebase context for LLM
    codebase_context: CodebaseContext = field(default_factory=CodebaseContext)

    # Metadata
    agent_name: str = ""
    tool_name: str = ""
    execution_duration_ms: int = 0
    retry_possible: bool = True
    max_retries_reached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Convert enums to strings
        data['reason'] = self.reason.value
        data['priority'] = self.priority.value
        data['codebase_context'] = self.codebase_context.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RetryEntry':
        """Create from dictionary."""
        # Convert strings back to enums
        data['reason'] = RetryReason(data['reason'])
        data['priority'] = RecoveryPriority(data['priority'])
        data['codebase_context'] = CodebaseContext(**data['codebase_context'])
        return cls(**data)


@dataclass
class RetrySummary:
    """Summary of all retry attempts for a session/interaction."""
    session_id: str
    interaction_id: str
    total_attempts: int
    successful_attempts: int
    failed_attempts: int
    last_failure_reason: Optional[RetryReason] = None
    recovery_suggestions: List[str] = field(default_factory=list)
    patterns_identified: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        if self.last_failure_reason:
            data['last_failure_reason'] = self.last_failure_reason.value
        return data


class RetryLogger:
    """
    Comprehensive retry logging system that captures full context for failed attempts.

    This enables:
    1. Complete reasoning chain preservation across retries
    2. Smart recovery suggestions for fresh LLMs
    3. Pattern analysis for systemic issues
    4. Codebase context for better understanding
    """

    def __init__(self, log_dir: str = "data/retry_logs", config: Optional[Dict[str, Any]] = None):
        """
        Initialize retry logger.

        Args:
            log_dir: Directory to store retry logs
            config: Optional configuration dict
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._current_retries: Dict[str, List[RetryEntry]] = {}
        self.config = config or {}
        self.trajectory_logger = get_trajectory_logger(config)

    def log_retry_attempt(
        self,
        session_id: str,
        interaction_id: str,
        attempt_number: int,
        reason: RetryReason,
        priority: RecoveryPriority,
        failed_action: str,
        error_message: str,
        error_type: str,
        user_request: str,
        execution_context: Dict[str, Any],
        reasoning_trace: Optional[List[Dict[str, Any]]] = None,
        critic_feedback: Optional[List[Dict[str, Any]]] = None,
        agent_name: str = "",
        tool_name: str = "",
        execution_duration_ms: int = 0,
        retry_possible: bool = True,
        max_retries_reached: bool = False
    ) -> str:
        """
        Log a retry attempt with full context.

        Args:
            session_id: Session identifier
            interaction_id: Interaction identifier
            attempt_number: Which attempt this is (1, 2, 3...)
            reason: Why this retry is happening
            priority: How critical this recovery is
            failed_action: What action/step failed
            error_message: The error that occurred
            error_type: Type/classification of error
            user_request: Original user request
            execution_context: Current execution state
            reasoning_trace: Full reasoning chain from reasoning trace system
            critic_feedback: Critic analysis and suggestions
            agent_name: Which agent was executing
            tool_name: Which tool failed
            execution_duration_ms: How long the attempt took
            retry_possible: Whether another retry is feasible
            max_retries_reached: Whether we've hit retry limits

        Returns:
            retry_id: Unique identifier for this retry entry
        """
        retry_id = str(uuid.uuid4())

        # Extract additional context
        current_plan = execution_context.get('current_plan')
        execution_state = execution_context.get('execution_state', {})
        tool_parameters = execution_context.get('tool_parameters', {})

        # Generate recovery suggestions based on error patterns
        suggested_fixes, alternative_approaches, required_changes = self._analyze_failure(
            error_message, error_type, failed_action, reasoning_trace or []
        )

        # Create codebase context
        codebase_context = self._generate_codebase_context()

        # Create retry entry
        entry = RetryEntry(
            retry_id=retry_id,
            session_id=session_id,
            interaction_id=interaction_id,
            attempt_number=attempt_number,
            timestamp=datetime.utcnow().isoformat() + "Z",
            reason=reason,
            priority=priority,
            failed_action=failed_action,
            error_message=error_message,
            error_type=error_type,
            user_request=user_request,
            current_plan=current_plan,
            execution_state=execution_state,
            tool_parameters=tool_parameters,
            reasoning_trace=reasoning_trace or [],
            critic_feedback=critic_feedback or [],
            suggested_fixes=suggested_fixes,
            alternative_approaches=alternative_approaches,
            required_changes=required_changes,
            codebase_context=codebase_context,
            agent_name=agent_name,
            tool_name=tool_name,
            execution_duration_ms=execution_duration_ms,
            retry_possible=retry_possible,
            max_retries_reached=max_retries_reached
        )

        # Store in memory
        if interaction_id not in self._current_retries:
            self._current_retries[interaction_id] = []
        self._current_retries[interaction_id].append(entry)

        # Persist to disk
        self._save_retry_entry(entry)

        logger.info(f"[RETRY LOGGER] Logged retry attempt {attempt_number} for {failed_action}: {error_message}")
        return retry_id

    def get_retry_context(self, interaction_id: str) -> Dict[str, Any]:
        """
        Get complete retry context for an interaction, formatted for LLM consumption.

        Args:
            interaction_id: Interaction to get context for

        Returns:
            Dictionary with retry history, patterns, and recovery instructions
        """
        retries = self._current_retries.get(interaction_id, [])
        if not retries:
            return {}

        # Create summary
        summary = RetrySummary(
            session_id=retries[0].session_id,
            interaction_id=interaction_id,
            total_attempts=len(retries) + 1,  # +1 for current attempt
            successful_attempts=0,  # TODO: track successes
            failed_attempts=len(retries),
            last_failure_reason=retries[-1].reason if retries else None,
            recovery_suggestions=self._aggregate_recovery_suggestions(retries),
            patterns_identified=self._identify_patterns(retries),
            recommended_actions=self._generate_recommended_actions(retries)
        )

        return {
            "summary": summary.to_dict(),
            "retry_history": [entry.to_dict() for entry in retries],
            "codebase_context": retries[0].codebase_context.to_dict() if retries else {},
            "recovery_instructions": self._generate_recovery_instructions(retries, summary),
            "context_for_fresh_llm": self._generate_fresh_llm_context(retries, summary)
        }

    def get_last_retry(self, interaction_id: str) -> Optional[RetryEntry]:
        """Get the most recent retry entry for an interaction."""
        retries = self._current_retries.get(interaction_id, [])
        return retries[-1] if retries else None

    def clear_retry_history(self, interaction_id: str):
        """Clear retry history for an interaction."""
        if interaction_id in self._current_retries:
            del self._current_retries[interaction_id]

    def _analyze_failure(
        self,
        error_message: str,
        error_type: str,
        failed_action: str,
        reasoning_trace: List[Dict[str, Any]]
    ) -> Tuple[List[str], List[str], Dict[str, Any]]:
        """Analyze failure and generate recovery suggestions."""
        suggested_fixes = []
        alternative_approaches = []
        required_changes = {}

        # Pattern-based analysis
        if "timeout" in error_message.lower():
            suggested_fixes.extend([
                "Increase timeout values in config.yaml",
                "Break down complex operations into smaller steps",
                "Add retry logic with exponential backoff"
            ])
            alternative_approaches.append("Use asynchronous execution for long-running tasks")

        elif "permission" in error_message.lower() or "access" in error_message.lower():
            suggested_fixes.extend([
                "Check file permissions and sandbox restrictions",
                "Verify API credentials in environment variables",
                "Ensure required applications are installed and accessible"
            ])
            required_changes["permissions"] = "Check and fix access permissions"

        elif "not found" in error_message.lower():
            suggested_fixes.extend([
                "Verify file paths exist and are correct",
                "Check if required tools/services are available",
                "Validate input parameters and data formats"
            ])
            alternative_approaches.append("Use search functionality to locate missing resources")

        elif "api" in error_message.lower():
            suggested_fixes.extend([
                "Check API credentials and rate limits",
                "Verify network connectivity",
                "Implement proper error handling for API failures"
            ])
            required_changes["api_config"] = "Review and update API configuration"

        # Reasoning trace analysis
        if reasoning_trace:
            last_reasoning = reasoning_trace[-1] if reasoning_trace else {}
            if last_reasoning.get("stage") == "correction":
                corrections = last_reasoning.get("corrections", [])
                suggested_fixes.extend(corrections)

        return suggested_fixes, alternative_approaches, required_changes

    def _aggregate_recovery_suggestions(self, retries: List[RetryEntry]) -> List[str]:
        """Aggregate recovery suggestions from all retries."""
        all_suggestions = []
        for retry in retries:
            all_suggestions.extend(retry.suggested_fixes)
            all_suggestions.extend(retry.alternative_approaches)

        # Remove duplicates while preserving order
        seen = set()
        unique_suggestions = []
        for suggestion in all_suggestions:
            if suggestion not in seen:
                seen.add(suggestion)
                unique_suggestions.append(suggestion)

        return unique_suggestions

    def _identify_patterns(self, retries: List[RetryEntry]) -> List[str]:
        """Identify patterns in retry attempts."""
        patterns = []

        if len(retries) >= 3:
            patterns.append("Multiple consecutive failures - consider fundamental approach change")

        error_types = [r.error_type for r in retries]
        if len(set(error_types)) == 1 and len(retries) >= 2:
            patterns.append(f"Consistent {error_types[0]} errors - systematic issue detected")

        # Check for timeout patterns
        timeout_count = sum(1 for r in retries if "timeout" in r.error_message.lower())
        if timeout_count >= 2:
            patterns.append("Recurring timeout issues - review performance bottlenecks")

        return patterns

    def _generate_recommended_actions(self, retries: List[RetryEntry]) -> List[str]:
        """Generate recommended actions based on retry history."""
        actions = []

        if not retries:
            return actions

        last_retry = retries[-1]

        if last_retry.max_retries_reached:
            actions.append("Maximum retries reached - escalate to human operator")
            actions.append("Review system configuration and resource constraints")

        if last_retry.priority == RecoveryPriority.CRITICAL:
            actions.append("Critical failure - immediate human intervention required")
            actions.append("Preserve all logs and context for debugging")

        # Pattern-based recommendations
        patterns = self._identify_patterns(retries)
        if "systematic issue" in " ".join(patterns).lower():
            actions.append("Address root cause before attempting further retries")
            actions.append("Consider updating system architecture or dependencies")

        return actions

    def _generate_codebase_context(self) -> CodebaseContext:
        """Generate current codebase context."""
        context = CodebaseContext()

        # Load config to get current settings
        try:
            from ..utils import load_config
            config = load_config()
            context.config_requirements = {
                "openai_model": config.get("openai", {}).get("model", "gpt-4o"),
                "reasoning_trace_enabled": config.get("reasoning_trace", {}).get("enabled", False),
                "vision_enabled": config.get("vision", {}).get("enabled", False)
            }
        except Exception:
            logger.debug("[RETRY LOGGER] Could not load config for context")

        return context

    def _generate_recovery_instructions(
        self,
        retries: List[RetryEntry],
        summary: RetrySummary
    ) -> str:
        """Generate detailed recovery instructions for LLMs."""
        instructions = []

        instructions.append("# RECOVERY INSTRUCTIONS FOR CEREBRO OS")
        instructions.append("")
        instructions.append("## FAILURE ANALYSIS")
        instructions.append(f"- Total failed attempts: {summary.failed_attempts}")
        instructions.append(f"- Last failure reason: {summary.last_failure_reason.value if summary.last_failure_reason else 'Unknown'}")
        instructions.append("")

        if summary.patterns_identified:
            instructions.append("## IDENTIFIED PATTERNS")
            for pattern in summary.patterns_identified:
                instructions.append(f"- {pattern}")
            instructions.append("")

        instructions.append("## SUGGESTED FIXES")
        for suggestion in summary.recovery_suggestions[:5]:  # Limit to top 5
            instructions.append(f"- {suggestion}")
        instructions.append("")

        if summary.recommended_actions:
            instructions.append("## RECOMMENDED ACTIONS")
            for action in summary.recommended_actions:
                instructions.append(f"- {action}")
            instructions.append("")

        instructions.append("## LAST ATTEMPT DETAILS")
        if retries:
            last = retries[-1]
            instructions.append(f"- Failed action: {last.failed_action}")
            instructions.append(f"- Error: {last.error_message}")
            instructions.append(f"- Agent: {last.agent_name}")
            instructions.append(f"- Tool: {last.tool_name}")
        instructions.append("")

        return "\n".join(instructions)

    def _generate_fresh_llm_context(
        self,
        retries: List[RetryEntry],
        summary: RetrySummary
    ) -> str:
        """Generate context for a fresh LLM to understand the situation."""
        context = []

        context.append("# CEREBRO OS - FRESH LLM RECOVERY CONTEXT")
        context.append("")
        context.append("## SYSTEM OVERVIEW")
        context.append("You are taking over execution in Cerebro OS, an AI-powered macOS automation system.")
        context.append("The previous execution failed, and you need to understand what happened and how to fix it.")
        context.append("")

        # Add codebase context
        if retries:
            cb_ctx = retries[0].codebase_context
            context.append("## CODEBASE CONTEXT")
            context.append(f"- Project: {cb_ctx.project_name} v{cb_ctx.version}")
            context.append(f"- Architecture: {cb_ctx.architecture}")
            context.append(f"- Key Components: {', '.join(cb_ctx.key_components)}")
            context.append("")

            if cb_ctx.environment_variables:
                context.append("## REQUIRED ENVIRONMENT VARIABLES")
                for var in cb_ctx.environment_variables:
                    context.append(f"- {var}")
                context.append("")

            if cb_ctx.important_paths:
                context.append("## IMPORTANT PATHS")
                for name, path in cb_ctx.important_paths.items():
                    context.append(f"- {name}: {path}")
                context.append("")

        # Add failure context
        context.append("## FAILURE SITUATION")
        context.append(f"- User request: {retries[0].user_request if retries else 'Unknown'}")
        context.append(f"- Failed attempts: {summary.failed_attempts}")
        context.append("- You have access to the complete reasoning trace and execution history")
        context.append("")

        context.append("## YOUR MISSION")
        context.append("1. Analyze the failure patterns and reasoning traces")
        context.append("2. Understand why previous attempts failed")
        context.append("3. Apply the suggested fixes and alternative approaches")
        context.append("4. Execute with the accumulated knowledge to succeed")
        context.append("5. If you succeed, document what made the difference")
        context.append("")

        context.append("## AVAILABLE RESOURCES")
        context.append("- Complete reasoning trace from previous attempts")
        context.append("- Critic feedback and correction suggestions")
        context.append("- Execution history and state")
        context.append("- System configuration and capabilities")
        context.append("- All previous tool calls and their results")
        context.append("")

        return "\n".join(context)

    def _save_retry_entry(self, entry: RetryEntry):
        """Save retry entry to disk."""
        try:
            filename = f"retry_{entry.interaction_id}_{entry.attempt_number}_{entry.retry_id[:8]}.json"
            filepath = self.log_dir / filename

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(entry.to_dict(), f, indent=2, ensure_ascii=False)

            logger.debug(f"[RETRY LOGGER] Saved retry entry to {filepath}")
        except Exception as e:
            logger.error(f"[RETRY LOGGER] Failed to save retry entry: {e}")

    def load_retry_history(self, interaction_id: str) -> List[RetryEntry]:
        """Load retry history for an interaction from disk."""
        retries = []
        try:
            pattern = f"retry_{interaction_id}_*.json"
            for filepath in self.log_dir.glob(pattern):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    retries.append(RetryEntry.from_dict(data))

            # Sort by attempt number
            retries.sort(key=lambda x: x.attempt_number)
            return retries
        except Exception as e:
            logger.error(f"[RETRY LOGGER] Failed to load retry history: {e}")
            return []
