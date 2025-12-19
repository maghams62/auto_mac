"""
Retry Context Manager for Cerebro OS

This module provides a context manager that handles retry logic, logging, and recovery
for agent executions. It integrates with the retry logger to capture full context
and provides smart recovery mechanisms.
"""

import time
import logging
from contextlib import contextmanager
from typing import Dict, Any, List, Optional, Callable, Generator
from dataclasses import dataclass

from .retry_logger import RetryReason, RecoveryPriority


logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    backoff_multiplier: float = 2.0
    enable_logging: bool = True
    enable_context_preservation: bool = True


@dataclass
class ExecutionContext:
    """Context for a single execution attempt."""
    interaction_id: str
    user_request: str
    current_plan: Optional[Dict[str, Any]] = None
    execution_state: Dict[str, Any] = None
    tool_parameters: Dict[str, Any] = None
    agent_name: str = ""
    tool_name: str = ""

    def __post_init__(self):
        if self.execution_state is None:
            self.execution_state = {}
        if self.tool_parameters is None:
            self.tool_parameters = {}


class RetryContextManager:
    """
    Context manager for handling retries with comprehensive logging and recovery.

    This manager:
    1. Tracks execution attempts and failures
    2. Logs detailed context for each retry
    3. Provides recovery suggestions based on failure patterns
    4. Manages exponential backoff and retry limits
    """

    def __init__(
        self,
        session_memory: Any,  # SessionMemory instance
        config: RetryConfig = None
    ):
        """
        Initialize retry context manager.

        Args:
            session_memory: SessionMemory instance for logging
            config: Retry configuration
        """
        self.session_memory = session_memory
        self.config = config or RetryConfig()
        self._current_attempt = 0
        self._execution_context: Optional[ExecutionContext] = None
        self._reasoning_trace: List[Dict[str, Any]] = []
        self._critic_feedback: List[Dict[str, Any]] = []

    def set_execution_context(
        self,
        interaction_id: str,
        user_request: str,
        current_plan: Optional[Dict[str, Any]] = None,
        execution_state: Optional[Dict[str, Any]] = None,
        tool_parameters: Optional[Dict[str, Any]] = None,
        agent_name: str = "",
        tool_name: str = ""
    ):
        """Set the execution context for retry attempts."""
        self._execution_context = ExecutionContext(
            interaction_id=interaction_id,
            user_request=user_request,
            current_plan=current_plan,
            execution_state=execution_state or {},
            tool_parameters=tool_parameters or {},
            agent_name=agent_name,
            tool_name=tool_name
        )

    def add_reasoning_trace(self, trace_entry: Dict[str, Any]):
        """Add a reasoning trace entry."""
        self._reasoning_trace.append(trace_entry)

    def add_critic_feedback(self, feedback: Dict[str, Any]):
        """Add critic feedback."""
        self._critic_feedback.append(feedback)

    def get_retry_context_for_llm(self) -> Dict[str, Any]:
        """Get retry context formatted for LLM consumption."""
        if not self._execution_context:
            return {}

        return self.session_memory.get_retry_context(self._execution_context.interaction_id)

    def should_retry(
        self,
        error_message: str,
        error_type: str,
        failed_action: str
    ) -> bool:
        """
        Determine if a retry should be attempted based on error analysis.

        Args:
            error_message: The error that occurred
            error_type: Type of error
            failed_action: What action failed

        Returns:
            True if retry should be attempted
        """
        # Check attempt limits
        if self._current_attempt >= self.config.max_attempts:
            return False

        # Analyze error for retry feasibility
        non_retryable_errors = [
            "permission denied",
            "authentication failed",
            "invalid credentials",
            "resource not found",
            "configuration error"
        ]

        error_lower = error_message.lower()
        for non_retryable in non_retryable_errors:
            if non_retryable in error_lower:
                logger.info(f"[RETRY MGR] Non-retryable error detected: {non_retryable}")
                return False

        # Check if this is a timeout or transient error
        transient_indicators = [
            "timeout",
            "connection refused",
            "service unavailable",
            "temporary failure",
            "rate limit"
        ]

        for indicator in transient_indicators:
            if indicator in error_lower:
                logger.info(f"[RETRY MGR] Transient error detected, will retry: {indicator}")
                return True

        # Default to retry for most errors
        return True

    def calculate_backoff_delay(self) -> float:
        """Calculate delay before next retry attempt using exponential backoff."""
        if self._current_attempt <= 1:
            return 0.0

        # Exponential backoff: base_delay * (backoff_multiplier ^ (attempt - 1))
        delay = self.config.base_delay_seconds * (
            self.config.backoff_multiplier ** (self._current_attempt - 1)
        )

        # Cap at maximum delay
        delay = min(delay, self.config.max_delay_seconds)

        return delay

    @contextmanager
    def retry_context(
        self,
        reason: RetryReason = RetryReason.EXECUTION_ERROR,
        priority: RecoveryPriority = RecoveryPriority.HIGH
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Context manager for retry execution.

        Usage:
            with retry_manager.retry_context() as context:
                try:
                    result = some_operation()
                    context['result'] = result
                except Exception as e:
                    context['error'] = str(e)
                    context['error_type'] = type(e).__name__
                    raise
        """
        self._current_attempt += 1
        start_time = time.time()

        # Prepare context for the execution
        execution_context = {
            'attempt_number': self._current_attempt,
            'start_time': start_time,
            'reason': reason,
            'priority': priority,
            'result': None,
            'error': None,
            'error_type': None,
            'execution_duration_ms': 0
        }

        try:
            # Execute the code block
            yield execution_context

            # Success - no retry needed
            execution_context['execution_duration_ms'] = int((time.time() - start_time) * 1000)
            logger.info(f"[RETRY MGR] Attempt {self._current_attempt} succeeded")

        except Exception as e:
            # Failure - log and determine if retry is needed
            execution_context['error'] = str(e)
            execution_context['error_type'] = type(e).__name__
            execution_context['execution_duration_ms'] = int((time.time() - start_time) * 1000)

            if self._execution_context and self.config.enable_logging:
                self._log_retry_attempt(
                    reason=reason,
                    priority=priority,
                    failed_action=self._execution_context.tool_name or "unknown_action",
                    error_message=str(e),
                    error_type=type(e).__name__,
                    execution_context=execution_context
                )

            # Determine if we should retry
            should_retry_attempt = self.should_retry(
                str(e), type(e).__name__,
                self._execution_context.tool_name if self._execution_context else "unknown"
            )

            if should_retry_attempt and self._current_attempt < self.config.max_attempts:
                delay = self.calculate_backoff_delay()
                if delay > 0:
                    logger.info(f"[RETRY MGR] Waiting {delay:.1f}s before retry {self._current_attempt + 1}")
                    time.sleep(delay)

            raise  # Re-raise the original exception

    def _log_retry_attempt(
        self,
        reason: RetryReason,
        priority: RecoveryPriority,
        failed_action: str,
        error_message: str,
        error_type: str,
        execution_context: Dict[str, Any]
    ):
        """Log a retry attempt with full context."""
        if not self._execution_context:
            logger.warning("[RETRY MGR] No execution context set for retry logging")
            return

        retry_id = self.session_memory.log_retry_attempt(
            interaction_id=self._execution_context.interaction_id,
            attempt_number=self._current_attempt,
            reason=reason,
            priority=priority,
            failed_action=failed_action,
            error_message=error_message,
            error_type=error_type,
            user_request=self._execution_context.user_request,
            execution_context={
                'current_plan': self._execution_context.current_plan,
                'execution_state': self._execution_context.execution_state,
                'tool_parameters': self._execution_context.tool_parameters,
                'attempt_context': execution_context
            },
            reasoning_trace=self._reasoning_trace.copy(),
            critic_feedback=self._critic_feedback.copy(),
            agent_name=self._execution_context.agent_name,
            tool_name=self._execution_context.tool_name,
            execution_duration_ms=execution_context.get('execution_duration_ms', 0),
            retry_possible=self._current_attempt < self.config.max_attempts,
            max_retries_reached=self._current_attempt >= self.config.max_attempts
        )

        if retry_id:
            logger.info(f"[RETRY MGR] Logged retry attempt {self._current_attempt}, ID: {retry_id[:8]}...")
        else:
            logger.debug("[RETRY MGR] Retry logging disabled or unavailable")

    def reset(self):
        """Reset the retry manager for a new execution sequence."""
        self._current_attempt = 0
        self._execution_context = None
        self._reasoning_trace.clear()
        self._critic_feedback.clear()

    def get_attempt_count(self) -> int:
        """Get the current attempt count."""
        return self._current_attempt

    def is_max_attempts_reached(self) -> bool:
        """Check if maximum retry attempts have been reached."""
        return self._current_attempt >= self.config.max_attempts


class SmartRetryManager:
    """
    Higher-level retry manager that provides intelligent retry strategies
    based on failure analysis and recovery patterns.
    """

    def __init__(self, session_memory: Any, config: RetryConfig = None):
        self.session_memory = session_memory
        self.config = config or RetryConfig()
        self.retry_manager = RetryContextManager(session_memory, config)

    def execute_with_smart_retry(
        self,
        func: Callable,
        execution_context: ExecutionContext,
        reason: RetryReason = RetryReason.EXECUTION_ERROR,
        priority: RecoveryPriority = RecoveryPriority.HIGH,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a function with smart retry logic.

        Args:
            func: Function to execute
            execution_context: Execution context
            reason: Reason for potential retries
            priority: Recovery priority
            *args, **kwargs: Arguments for the function

        Returns:
            Function result if successful

        Raises:
            Exception: Last exception if all retries failed
        """
        self.retry_manager.set_execution_context(
            interaction_id=execution_context.interaction_id,
            user_request=execution_context.user_request,
            current_plan=execution_context.current_plan,
            execution_state=execution_context.execution_state,
            tool_parameters=execution_context.tool_parameters,
            agent_name=execution_context.agent_name,
            tool_name=execution_context.tool_name
        )

        last_exception = None

        while not self.retry_manager.is_max_attempts_reached():
            try:
                with self.retry_manager.retry_context(reason=reason, priority=priority) as context:
                    result = func(*args, **kwargs)
                    context['result'] = result
                    return result

            except Exception as e:
                last_exception = e
                logger.warning(f"[SMART RETRY] Attempt {self.retry_manager.get_attempt_count()} failed: {e}")

                # If we've reached max attempts, don't continue
                if self.retry_manager.is_max_attempts_reached():
                    break

        # All retries exhausted
        logger.error(f"[SMART RETRY] All {self.config.max_attempts} attempts failed")
        raise last_exception

    def get_recovery_instructions(self, interaction_id: str) -> str:
        """Get recovery instructions for a failed interaction."""
        context = self.retry_manager.get_retry_context_for_llm()
        return context.get('recovery_instructions', 'No recovery instructions available')

    def get_fresh_llm_context(self, interaction_id: str) -> str:
        """Get context formatted for a fresh LLM."""
        context = self.retry_manager.get_retry_context_for_llm()
        return context.get('context_for_fresh_llm', 'No context available for fresh LLM')
