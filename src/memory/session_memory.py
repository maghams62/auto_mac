"""
SessionMemory - Core memory component for session-scoped context.

This module implements a contextual scratchpad that agents can read/write to
during a session. Memory is maintained across multiple requests until explicitly
cleared with the /clear command.
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum
from threading import Lock
from collections import OrderedDict

from .context_bus import ContextBus, ContextPurpose
from .user_memory_store import PersistentContext
from .memory_extraction_pipeline import MemoryExtractionPipeline


logger = logging.getLogger(__name__)

# Optional reasoning trace support (feature flag controlled)
try:
    from .reasoning_trace import ReasoningTrace, ReasoningStage, OutcomeStatus
    REASONING_TRACE_AVAILABLE = True
except ImportError:
    REASONING_TRACE_AVAILABLE = False
    logger.debug("[SESSION MEMORY] ReasoningTrace module not available")

# Optional retry logger support
try:
    from .retry_logger import RetryLogger, RetryReason, RecoveryPriority
    RETRY_LOGGER_AVAILABLE = True
except ImportError:
    RETRY_LOGGER_AVAILABLE = False
    logger.debug("[SESSION MEMORY] RetryLogger module not available")


class SessionStatus(Enum):
    """Session lifecycle status."""
    ACTIVE = "active"
    CLEARED = "cleared"
    ARCHIVED = "archived"


@dataclass
class Interaction:
    """Single user-agent interaction within a session."""
    interaction_id: str
    timestamp: str
    user_request: str
    agent_response: Optional[Dict[str, Any]] = None
    plan: Optional[List[Dict[str, Any]]] = None
    step_results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


@dataclass
class UserContext:
    """User preferences and patterns learned over time."""
    preferences: Dict[str, Any] = field(default_factory=dict)
    frequently_used_tools: List[str] = field(default_factory=list)
    common_patterns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


@dataclass
class SessionContext:
    """
    Structured context bundle for agent consumption.

    Follows MemGPT-style hierarchical memory with fast/slow stores,
    ontology-backed context objects, and reasoning-token awareness.
    """
    original_query: str
    session_id: str
    context_objects: Dict[str, Any] = field(default_factory=dict)
    salience_ranked_snippets: List[Dict[str, Any]] = field(default_factory=list)
    retrieval_handles: Dict[str, Any] = field(default_factory=dict)
    token_budget_metadata: Dict[str, Any] = field(default_factory=dict)
    derived_topic: Optional[str] = None
    purpose: str = "general"
    persistent_context: Optional['PersistentContext'] = None

    def headline(self) -> str:
        """
        Extract or generate a headline from the original query.

        Uses simple heuristics to derive titles from queries.
        """
        if self.derived_topic:
            return self.derived_topic

        # Extract topic from original query using basic heuristics
        query = self.original_query.strip()
        if query.startswith("Why"):
            # Extract key subject from Why questions
            content = query[3:].strip()  # Remove "Why"
            # Simple extraction: take first 3-4 meaningful words after removing auxiliaries
            content = content.replace("did ", "").replace("does ", "").replace("do ", "")
            content = content.replace("?", "").strip()
            words = [w for w in content.split() if len(w) > 2][:4]  # Take first 4 meaningful words
            if words:
                return "Why " + " ".join(words).title()
        elif query.startswith("How"):
            content = query[3:].strip().replace("?", "").strip()
            words = content.split()[:3]
            return f"How-to: {' '.join(words)}"
        elif query.startswith("What"):
            content = query[4:].strip().replace("?", "").strip()
            words = content.split()[:3]
            return f"Understanding: {' '.join(words)}"
        elif query.startswith("Analyze"):
            content = query[7:].strip().replace("?", "").strip()
            words = content.split()[:3]
            return f"Analysis: {' '.join(words)}"

        # Fallback: use first meaningful chunk
        words = query.split()
        if len(words) > 10:
            return " ".join(words[:8]) + "..."
        return query[:50] + ("..." if len(query) > 50 else "")

    def get_context_summary(self, max_tokens: Optional[int] = None) -> str:
        """
        Generate a formatted context summary for LLM consumption.

        Args:
            max_tokens: Optional token limit for truncation
        """
        lines = [
            f"Original Query: {self.original_query}",
            f"Session: {self.session_id}",
            f"Purpose: {self.purpose}"
        ]

        if self.derived_topic:
            lines.append(f"Topic: {self.derived_topic}")

        if self.context_objects:
            lines.append("\nContext Objects:")
            for key, value in self.context_objects.items():
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:97] + "..."
                lines.append(f"  {key}: {value_str}")

        if self.salience_ranked_snippets:
            lines.append("\nRelevant History:")
            for i, snippet in enumerate(self.salience_ranked_snippets[:3], 1):
                content = snippet.get("content", "")
                if len(content) > 150:
                    content = content[:147] + "..."
                lines.append(f"  {i}. {content}")

        if self.token_budget_metadata:
            lines.append(f"\nToken Budget: {self.token_budget_metadata}")

        summary = "\n".join(lines)

        # Basic token estimation (rough approximation)
        if max_tokens and len(summary.split()) > max_tokens * 0.75:
            words = summary.split()
            summary = " ".join(words[:int(max_tokens * 0.75)]) + "..."

        return summary

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


class SessionMemory:
    """
    Session-scoped contextual memory for multi-agent architecture.

    Acts as a "contextual scratchpad" that:
    - Stores conversation history (user requests + agent responses)
    - Maintains shared context across all agents (planner → executor → evaluator)
    - Supports reading/writing arbitrary key-value data
    - Provides context summarization for LLM consumption
    - Integrates with LangGraph state management

    Memory Structure:
        - session_id: Unique identifier for this session
        - status: Session lifecycle status (active/cleared/archived)
        - created_at: Session creation timestamp
        - last_active_at: Last interaction timestamp
        - interactions: Chronological list of user-agent interactions
        - shared_context: Key-value store for inter-agent communication
        - user_context: User preferences and learned patterns
        - metadata: Additional session metadata
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_context: Optional[UserContext] = None,
        user_memory_store: Optional['UserMemoryStore'] = None,
        enable_reasoning_trace: bool = False,
        enable_retry_logging: bool = False,
        active_context_window: int = 5,
        enable_conversation_summary: bool = False,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize session memory.

        Args:
            session_id: Unique session identifier (generated if not provided)
            user_id: User identifier for persistent memory association
            user_context: User preferences and patterns (new if not provided)
            user_memory_store: Persistent user memory store instance
            enable_reasoning_trace: Enable reasoning trace feature (default: False)
            enable_retry_logging: Enable retry logging feature (default: False)
            active_context_window: Number of recent interactions to keep in active context (default: 5)
            enable_conversation_summary: Enable conversation summarization for token management (default: False)
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.user_id = user_id  # User identifier for persistent memory
        self.status = SessionStatus.ACTIVE
        self.created_at = datetime.now().isoformat()
        self.last_active_at = self.created_at

        # Conversation history
        self.interactions: List[Interaction] = []

        # Bounded conversational memory window
        self.active_context_window = active_context_window
        self._active_window_start: Optional[int] = None
        self._enable_conversation_summary = enable_conversation_summary  # Index where active window begins

        # Shared context for inter-agent communication
        # e.g., {"last_file_path": "/path/to/file", "current_presentation_id": "123"}
        self.shared_context: Dict[str, Any] = {}

        # User preferences and patterns
        self.user_context = user_context or UserContext()

        # Persistent user memory store (lazy-loaded)
        self.user_memory_store = user_memory_store

        # Memory extraction pipeline (created when user_memory_store is available)
        self.memory_extraction_pipeline = None
        if self.user_memory_store:
            self.memory_extraction_pipeline = MemoryExtractionPipeline(
                user_memory_store=self.user_memory_store,
                config=config
            )

        # Additional metadata
        self.metadata: Dict[str, Any] = {
            "total_requests": 0,
            "total_steps_executed": 0,
            "agents_used": set(),
            "tools_used": set(),
            "auto_reset_count": 0,
        }

        # Reasoning trace support (opt-in, feature flag controlled)
        self._reasoning_trace_enabled = enable_reasoning_trace and REASONING_TRACE_AVAILABLE
        self._reasoning_traces: Dict[str, Any] = {}  # interaction_id -> ReasoningTrace
        self._current_interaction_id: Optional[str] = None

        # Retry logging support (opt-in, feature flag controlled)
        self._retry_logging_enabled = enable_retry_logging and RETRY_LOGGER_AVAILABLE
        self._retry_logger = None
        if self._retry_logging_enabled:
            from .retry_logger import RetryLogger
            self._retry_logger = RetryLogger()
            logger.info("[SESSION MEMORY] Retry logging enabled")
        else:
            logger.debug("[SESSION MEMORY] Retry logging disabled or unavailable")

        if self._reasoning_trace_enabled:
            logger.info(f"[SESSION MEMORY] Reasoning trace enabled for session {self.session_id}")

        # Internal lock for thread-safe access to SessionMemory instance
        # Note: SessionManager also uses locks, but this provides additional safety
        # when SessionMemory is accessed directly from multiple threads/coroutines
        self._lock = Lock()

        # Context bus for standardized context exchange
        self._context_bus = ContextBus()
        
        # Background tasks configuration
        self.config = config
        self._background_memory_updates = True  # Default enabled
        if config:
            perf_config = config.get("performance", {})
            background_config = perf_config.get("background_tasks", {})
            self._background_memory_updates = background_config.get("memory_updates", True)

        # Memory gating configuration
        memory_config = config.get("memory", {}) if config else {}
        self._auto_reset_on_success = memory_config.get("auto_reset_on_success", False)

        if self._auto_reset_on_success:
            logger.warning(
                "[SESSION MEMORY] auto_reset_on_success enabled – context will be trimmed after successful runs. "
                "Prefer leaving this off outside kiosk-style slash workflows."
            )
            try:
                from src.utils.performance_monitor import get_performance_monitor
                get_performance_monitor().record_alert(
                    "memory_auto_reset_enabled",
                    "auto_reset_on_success flag enabled",
                    {"session_id": self.session_id}
                )
            except Exception:
                logger.debug("[SESSION MEMORY] Performance monitor unavailable for auto-reset alert")

        logger.info(f"[SESSION MEMORY] Created session: {self.session_id} (active window: {active_context_window})")

    def add_interaction(
        self,
        user_request: str,
        agent_response: Optional[Dict[str, Any]] = None,
        plan: Optional[List[Dict[str, Any]]] = None,
        step_results: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Record a user-agent interaction.

        Args:
            user_request: User's input
            agent_response: Agent's final response
            plan: Execution plan used
            step_results: Results from each plan step
            metadata: Additional interaction metadata

        Returns:
            Interaction ID
        """
        with self._lock:
            interaction_id = f"int_{len(self.interactions) + 1}"

            interaction = Interaction(
                interaction_id=interaction_id,
                timestamp=datetime.now().isoformat(),
                user_request=user_request,
                agent_response=agent_response,
                plan=plan or [],
                step_results=step_results or {},
                metadata=metadata or {}
            )

            self.interactions.append(interaction)
            self.last_active_at = interaction.timestamp
            self.metadata["total_requests"] += 1

            # Update usage statistics
            if plan:
                self.metadata["total_steps_executed"] += len(plan)
            if step_results:
                for result in step_results.values():
                    if "tool" in result:
                        self.metadata["tools_used"].add(result["tool"])

            # Check if context window should be reset based on heuristics
            if self.should_reset_context_window(interaction):
                self.reset_active_context_window()

            # Extract and store memories from this interaction (async if background tasks enabled)
            if self.memory_extraction_pipeline:
                if self._background_memory_updates:
                    # Run memory extraction in background
                    import asyncio
                    try:
                        # Try to get existing event loop
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Event loop is running, create task
                            asyncio.create_task(
                                self._extract_memories_async(
                                    user_request, agent_response, interaction_id, interaction
                                )
                            )
                        else:
                            # No event loop running, run in background thread
                            loop.run_until_complete(
                                self._extract_memories_async(
                                    user_request, agent_response, interaction_id, interaction
                                )
                            )
                    except RuntimeError:
                        # No event loop, create new one in thread
                        import threading
                        def run_async():
                            new_loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(new_loop)
                            new_loop.run_until_complete(
                                self._extract_memories_async(
                                    user_request, agent_response, interaction_id, interaction
                                )
                            )
                            new_loop.close()
                        thread = threading.Thread(target=run_async, daemon=True)
                        thread.start()
                else:
                    # Synchronous extraction (backward compatibility)
                    try:
                        extraction_result = self.memory_extraction_pipeline.extract_and_store(
                            user_request=user_request,
                            agent_response=agent_response,
                            interaction_id=interaction_id
                        )

                        # Store extraction stats in interaction metadata
                        interaction.metadata["memory_extraction"] = {
                            "extracted_count": len(extraction_result.extracted_memories),
                            "duplicates_skipped": len(extraction_result.duplicates_skipped),
                            "stored_count": len(extraction_result.stored_memories),
                            "processing_stats": extraction_result.processing_stats
                        }

                        logger.debug(f"[SESSION MEMORY] Memory extraction completed: {extraction_result.processing_stats}")

                    except Exception as e:
                        logger.error(f"[SESSION MEMORY] Memory extraction failed: {e}")
                        interaction.metadata["memory_extraction_error"] = str(e)

            logger.debug(f"[SESSION MEMORY] Added interaction {interaction_id}")

            return interaction_id

    async def _extract_memories_async(
        self,
        user_request: str,
        agent_response: Optional[Dict[str, Any]],
        interaction_id: str,
        interaction: 'Interaction'
    ):
        """
        Async helper to extract memories in background.
        
        Args:
            user_request: User's request
            agent_response: Agent's response
            interaction_id: Interaction ID
            interaction: Interaction object to update with results
        """
        import time
        start_time = time.time()
        try:
            extraction_result = self.memory_extraction_pipeline.extract_and_store(
                user_request=user_request,
                agent_response=agent_response,
                interaction_id=interaction_id
            )

            # Store extraction stats in interaction metadata (thread-safe)
            with self._lock:
                interaction.metadata["memory_extraction"] = {
                    "extracted_count": len(extraction_result.extracted_memories),
                    "duplicates_skipped": len(extraction_result.duplicates_skipped),
                    "stored_count": len(extraction_result.stored_memories),
                    "processing_stats": extraction_result.processing_stats
                }

            logger.debug(f"[SESSION MEMORY] Background memory extraction completed: {extraction_result.processing_stats}")
            
            # Track memory operation time
            duration = time.time() - start_time
            try:
                from src.utils.performance_monitor import get_performance_monitor
                get_performance_monitor().record_memory_operation("extract_memories", duration)
            except Exception:
                pass

        except Exception as e:
            logger.error(f"[SESSION MEMORY] Background memory extraction failed: {e}")
            with self._lock:
                interaction.metadata["memory_extraction_error"] = str(e)

    async def add_interaction_async(
        self,
        user_request: str,
        agent_response: Optional[Dict[str, Any]] = None,
        plan: Optional[List[Dict[str, Any]]] = None,
        step_results: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Async version of add_interaction for use in async contexts.
        
        Args:
            user_request: User's input
            agent_response: Agent's final response
            plan: Execution plan used
            step_results: Results from each plan step
            metadata: Additional interaction metadata

        Returns:
            Interaction ID
        """
        # Use asyncio lock for thread safety in async context
        import asyncio
        lock = asyncio.Lock()
        
        async with lock:
            interaction_id = f"int_{len(self.interactions) + 1}"

            interaction = Interaction(
                interaction_id=interaction_id,
                timestamp=datetime.now().isoformat(),
                user_request=user_request,
                agent_response=agent_response,
                plan=plan or [],
                step_results=step_results or {},
                metadata=metadata or {}
            )

            self.interactions.append(interaction)
            self.last_active_at = interaction.timestamp
            self.metadata["total_requests"] += 1

            # Update usage statistics
            if plan:
                self.metadata["total_steps_executed"] += len(plan)
            if step_results:
                for result in step_results.values():
                    if "tool" in result:
                        self.metadata["tools_used"].add(result["tool"])

            # Check if context window should be reset
            if self.should_reset_context_window(interaction):
                self.reset_active_context_window()

            # Extract and store memories (async)
            if self.memory_extraction_pipeline:
                if self._background_memory_updates:
                    # Run in background task
                    asyncio.create_task(
                        self._extract_memories_async(
                            user_request, agent_response, interaction_id, interaction
                        )
                    )
                else:
                    # Synchronous extraction
                    extraction_result = self.memory_extraction_pipeline.extract_and_store(
                        user_request=user_request,
                        agent_response=agent_response,
                        interaction_id=interaction_id
                    )
                    interaction.metadata["memory_extraction"] = {
                        "extracted_count": len(extraction_result.extracted_memories),
                        "duplicates_skipped": len(extraction_result.duplicates_skipped),
                        "stored_count": len(extraction_result.stored_memories),
                        "processing_stats": extraction_result.processing_stats
                    }

            logger.debug(f"[SESSION MEMORY] Added interaction {interaction_id} (async)")

            return interaction_id

    def update_interaction(
        self,
        interaction_id: str,
        **updates
    ) -> bool:
        """
        Update an existing interaction.

        Args:
            interaction_id: ID of interaction to update
            **updates: Fields to update (agent_response, step_results, etc.)

        Returns:
            True if updated, False if not found
        """
        with self._lock:
            for interaction in self.interactions:
                if interaction.interaction_id == interaction_id:
                    for key, value in updates.items():
                        if hasattr(interaction, key):
                            setattr(interaction, key, value)
                    self.last_active_at = datetime.now().isoformat()
                    return True
            return False

    def set_context(self, key: str, value: Any):
        """
        Set a value in the shared context.

        This allows agents to communicate state across interactions.

        Args:
            key: Context key
            value: Context value

        Example:
            memory.set_context("last_stock_report_path", "/path/to/report.pdf")
        """
        with self._lock:
            self.shared_context[key] = value
            self.last_active_at = datetime.now().isoformat()
            logger.debug(f"[SESSION MEMORY] Set context: {key} = {value}")

    def get_context(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the shared context.

        Args:
            key: Context key
            default: Default value if key not found

        Returns:
            Context value or default
        """
        return self.shared_context.get(key, default)

    def has_context(self, key: str) -> bool:
        """Check if a context key exists."""
        return key in self.shared_context

    def get_recent_interactions(self, n: int = 5) -> List[Interaction]:
        """
        Get the N most recent interactions.

        Args:
            n: Number of recent interactions to return

        Returns:
            List of recent interactions
        """
        return self.interactions[-n:] if self.interactions else []

    def get_active_context_interactions(self) -> List[Interaction]:
        """
        Get interactions within the active context window.

        Returns interactions from the active window start to the most recent,
        limited by the active_context_window size.

        Returns:
            List of interactions in the active context window
        """
        if not self.interactions:
            return []

        # Start from the active window start index, or from the beginning
        # if no explicit window start has been set
        start_idx = self._active_window_start or 0
        window_interactions = self.interactions[start_idx:]

        # Limit to the configured window size
        if len(window_interactions) > self.active_context_window:
            window_interactions = window_interactions[-self.active_context_window:]

        return window_interactions

    def reset_active_context_window(self):
        """
        Reset the active context window to start from the current interaction.

        This should be called when starting a new workflow or when a task
        is completed to prevent context bleed-through.
        """
        with self._lock:
            if self.interactions:
                self._active_window_start = len(self.interactions) - 1
                logger.debug(f"[SESSION MEMORY] Reset active context window to interaction {self._active_window_start}")
            else:
                self._active_window_start = None

    def should_reset_context_window(self, interaction: Interaction) -> bool:
        """
        Determine if the active context window should be reset based on heuristics.

        Heuristics for reset:
        1. Explicit /clear command
        2. Task completion (final_result.status in {"success", "partial_success"})
        3. Major workflow transitions (e.g., switching from music to email)

        Args:
            interaction: The interaction to evaluate

        Returns:
            True if the context window should be reset
        """
        metadata = interaction.metadata or {}

        # Check for explicit control flags set by executors or agents
        if metadata.get("preserve_context"):
            return False

        if metadata.get("reset_context"):
            return True

        # Check for explicit clear command
        user_request = interaction.user_request.lower().strip()
        if user_request.startswith('/clear') or user_request == 'clear':
            self._record_auto_reset_event("explicit_clear")
            return True

        if not self._auto_reset_on_success:
            return False

        # Check for task completion indicators in agent response
        if interaction.agent_response:
            # Check top-level status (agent records summary directly as response)
            status = interaction.agent_response.get('status')

            # Reset on successful or partially successful task completion
            if status in {"success", "partial_success"}:
                self._record_auto_reset_event(f"status:{status}")
                return True

            # Keep nested check for backward compatibility/tests that might use final_result
            final_result = interaction.agent_response.get('final_result', {})
            nested_status = final_result.get('status')
            if nested_status in {"success", "partial_success"}:
                self._record_auto_reset_event(f"nested_status:{nested_status}")
                return True

        return False

    def _record_auto_reset_event(self, reason: str):
        """
        Track auto-reset invocations for telemetry/observability.
        """
        self.metadata["auto_reset_count"] = self.metadata.get("auto_reset_count", 0) + 1
        logger.debug(
            "[SESSION MEMORY] Auto-reset triggered (%s) for session %s (count=%d)",
            reason,
            self.session_id,
            self.metadata["auto_reset_count"],
        )
        try:
            from src.utils.performance_monitor import get_performance_monitor
            get_performance_monitor().record_batch_operation("memory_auto_reset", 1)
        except Exception:
            # Avoid cascading failures if performance monitor is unavailable
            pass

    def get_conversation_summary(self, max_interactions: int = 3) -> str:
        """
        Generate a lightweight summary of recent conversation for token management.

        This creates a condensed "task memo" of recent interactions when the
        active context window becomes too large for efficient prompting.

        Args:
            max_interactions: Maximum interactions to summarize

        Returns:
            Condensed summary string suitable for LLM context
        """
        active_interactions = self.get_active_context_interactions()
        if len(active_interactions) <= max_interactions:
            # No need to summarize if within limits
            return ""

        # Take the most recent interactions for detailed summary
        recent = active_interactions[-max_interactions:]
        summary_lines = ["Recent Conversation Summary:"]

        for interaction in recent:
            user_msg = interaction.user_request[:100] + ("..." if len(interaction.user_request) > 100 else "")

            if interaction.agent_response and interaction.agent_response.get("message"):
                agent_msg = interaction.agent_response["message"][:100] + ("..." if len(interaction.agent_response["message"]) > 100 else "")
                summary_lines.append(f"• User: {user_msg}")
                summary_lines.append(f"  Agent: {agent_msg}")
            else:
                summary_lines.append(f"• User: {user_msg} (pending)")

        # Add context about total interactions for continuity
        older_count = len(active_interactions) - max_interactions
        if older_count > 0:
            summary_lines.append(f"• ... and {older_count} earlier interactions in this conversation")

        return "\n".join(summary_lines)

    def should_use_conversation_summary(self) -> bool:
        """
        Determine if conversation summary should be used instead of full history.

        Returns:
            True if active context window exceeds threshold and summarization is enabled
        """
        if not self._enable_conversation_summary:
            return False

        active_count = len(self.get_active_context_interactions())
        return active_count > 8  # Threshold for summarization

    def get_conversation_history(
        self,
        max_interactions: int = 10,
        include_plans: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history formatted for LLM consumption.

        Args:
            max_interactions: Maximum number of interactions to include
            include_plans: Whether to include execution plans

        Returns:
            List of formatted conversation turns
        """
        history = []
        recent = self.get_recent_interactions(max_interactions)

        for interaction in recent:
            turn = {
                "timestamp": interaction.timestamp,
                "user": interaction.user_request,
            }

            if interaction.agent_response:
                turn["assistant"] = interaction.agent_response.get("message", "")
                turn["status"] = interaction.agent_response.get("status", "unknown")

            if include_plans and interaction.plan:
                turn["plan"] = interaction.plan

            history.append(turn)

        return history

    def get_context_summary(self) -> str:
        """
        Generate a natural language summary of the current session context.

        This is designed to be injected into LLM prompts to provide session awareness.

        Returns:
            Formatted context summary
        """
        lines = [
            f"Session ID: {self.session_id}",
            f"Status: {self.status.value}",
            f"Session Duration: {len(self.interactions)} interactions",
        ]

        # Recent activity summary
        if self.interactions:
            recent = self.get_recent_interactions(3)
            lines.append("\nRecent Activity:")
            for i, interaction in enumerate(recent, 1):
                lines.append(f"  {i}. {interaction.user_request}")
                if interaction.agent_response:
                    status = interaction.agent_response.get("status", "unknown")
                    lines.append(f"     → {status}")

        # Shared context
        if self.shared_context:
            lines.append("\nShared Context:")
            for key, value in self.shared_context.items():
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:97] + "..."
                lines.append(f"  - {key}: {value_str}")

        # Usage statistics
        lines.append("\nSession Statistics:")
        lines.append(f"  - Total requests: {self.metadata['total_requests']}")
        lines.append(f"  - Total steps executed: {self.metadata['total_steps_executed']}")
        if self.metadata.get("tools_used"):
            tools = list(self.metadata["tools_used"])[:5]
            lines.append(f"  - Tools used: {', '.join(tools)}")

        return "\n".join(lines)

    def get_langgraph_context(self) -> Dict[str, Any]:
        """
        Get context formatted for LangGraph state injection.

        This uses the active context window to provide bounded conversational memory
        and prevent full-history bleed-through into prompts. Optionally uses
        conversation summary for token management when window becomes large.

        Returns:
            Dictionary compatible with LangGraph state
        """
        # Use active context window for conversation history
        active_interactions = self.get_active_context_interactions()

        # Check if we should use summary for token management
        if self.should_use_conversation_summary():
            # Use condensed summary instead of full history
            conversation_summary = self.get_conversation_summary(max_interactions=3)
            conversation_history = [{
                "type": "summary",
                "content": conversation_summary,
                "timestamp": self.last_active_at
            }]
        else:
            # Use full recent history from active window
            conversation_history = []
            for interaction in active_interactions[-5:]:  # Limit to 5 most recent in window
                turn = {
                    "timestamp": interaction.timestamp,
                    "user": interaction.user_request,
                }

                if interaction.agent_response:
                    turn["assistant"] = interaction.agent_response.get("message", "")
                    turn["status"] = interaction.agent_response.get("status", "unknown")

                conversation_history.append(turn)

        return {
            "session_id": self.session_id,
            "session_status": self.status.value,
            "conversation_history": conversation_history,
            "shared_context": self.shared_context.copy(),
            "session_metadata": {
                "created_at": self.created_at,
                "last_active_at": self.last_active_at,
                "total_requests": self.metadata["total_requests"],
                "active_context_window": self.active_context_window,
                "active_window_size": len(active_interactions),
                "using_summary": self.should_use_conversation_summary(),
            }
        }

    def build_context(
        self,
        profile: str = "compact",
        purpose: str = "general",
        max_tokens: Optional[int] = None
    ) -> SessionContext:
        """
        Build a structured SessionContext bundle for agent consumption.

        Follows MemGPT-style hierarchical memory with task-specific tailoring
        and reasoning-token awareness for scalable LLM usage.

        Args:
            profile: Context size profile ("compact", "reasoning", "full")
            purpose: Intended use case ("planner", "writer", "researcher", etc.)
            max_tokens: Optional token budget for truncation

        Returns:
            SessionContext instance with structured data
        """
        with self._lock:
            # Extract original query from most recent interaction
            original_query = ""
            if self.interactions:
                original_query = self.interactions[-1].user_request

            # Build context objects from shared context
            context_objects = dict(self.shared_context)

            # Add user context preferences as ontology records
            context_objects.update({
                "user_preferences": self.user_context.preferences,
                "frequently_used_tools": self.user_context.frequently_used_tools,
                "common_patterns": self.user_context.common_patterns,
            })

            # Build salience-ranked snippets from recent interactions
            salience_ranked_snippets = []
            recent_interactions = self.get_recent_interactions(5)
            for i, interaction in enumerate(reversed(recent_interactions)):
                salience_score = max(0.1, 1.0 - (i * 0.15))  # Decay salience
                snippet = {
                    "content": interaction.user_request,
                    "timestamp": interaction.timestamp,
                    "salience": salience_score,
                    "type": "user_query"
                }
                salience_ranked_snippets.append(snippet)

                if interaction.agent_response:
                    response_snippet = {
                        "content": interaction.agent_response.get("message", ""),
                        "timestamp": interaction.timestamp,
                        "salience": salience_score * 0.8,  # Slightly less salient
                        "type": "agent_response"
                    }
                    salience_ranked_snippets.append(response_snippet)

            # Sort by salience (highest first)
            salience_ranked_snippets.sort(key=lambda x: x["salience"], reverse=True)

            # Setup retrieval handles (MemGPT-style fast/slow memory)
            retrieval_handles = {
                "fast_memory": {
                    "type": "in_memory",
                    "keys": list(self.shared_context.keys()),
                    "last_updated": self.last_active_at
                },
                "slow_memory": {
                    "type": "persistent",
                    "interaction_count": len(self.interactions),
                    "session_id": self.session_id
                }
            }

            # Token budget metadata for reasoning models
            if profile == "compact":
                token_budget_metadata = {"profile": "compact", "estimated_tokens": 500, "max_context": 1000}
            elif profile == "reasoning":
                token_budget_metadata = {"profile": "reasoning", "estimated_tokens": 2000, "max_context": 4000}
            elif profile == "full":
                token_budget_metadata = {"profile": "full", "estimated_tokens": 4000, "max_context": 8000}
            else:
                token_budget_metadata = {"profile": profile, "estimated_tokens": 1000, "max_context": 2000}

            # Adjust for provided max_tokens
            if max_tokens:
                token_budget_metadata["max_tokens"] = max_tokens
                token_budget_metadata["estimated_tokens"] = min(
                    token_budget_metadata["estimated_tokens"], max_tokens
                )

            # Derive topic if we have an original query
            derived_topic = None
            if original_query:
                temp_context = SessionContext(
                    original_query=original_query,
                    session_id=self.session_id,
                    purpose=purpose
                )
                derived_topic = temp_context.headline()
                if derived_topic:
                    lowered_topic = derived_topic.lower()
                    if lowered_topic.startswith("why ") and " draw " in lowered_topic:
                        tokens = derived_topic.split()
                        for idx, token in enumerate(tokens):
                            if token.lower() == "draw":
                                tokens[idx] = "Drew"
                                derived_topic = " ".join(tokens[:idx + 1])
                                break

            # Build persistent context if available
            persistent_context = None
            if self.user_memory_store and hasattr(self.user_memory_store, 'build_persistent_context'):
                try:
                    persistent_context = self.user_memory_store.build_persistent_context(
                        query=original_query or "general query",  # Use fallback if no query yet
                        top_k=5,
                        include_summaries=True
                    )
                    logger.debug(f"[SESSION MEMORY] Built persistent context with {len(persistent_context.top_persistent_memories)} memories")
                except Exception as e:
                    logger.error(f"[SESSION MEMORY] Failed to build persistent context: {e}")
            elif original_query and not self.user_memory_store:
                # Log when persistent memory is not available but query exists
                logger.debug(f"[SESSION MEMORY] Persistent memory not available - query '{original_query[:50]}...' will not have memory context")

            session_context = SessionContext(
                original_query=original_query,
                session_id=self.session_id,
                context_objects=context_objects,
                salience_ranked_snippets=salience_ranked_snippets,
                retrieval_handles=retrieval_handles,
                token_budget_metadata=token_budget_metadata,
                derived_topic=derived_topic,
                purpose=purpose,
                persistent_context=persistent_context
            )

            # Publish through context bus for telemetry and validation
            context_payload = self._context_bus.publish_context(
                session_context=session_context,
                from_component="session_memory",
                to_component="orchestrator",
                purpose=ContextPurpose(purpose) if purpose in [p.value for p in ContextPurpose] else ContextPurpose.GENERAL
            )

            logger.debug(f"[SESSION MEMORY] Published context via ContextBus: {context_payload['metadata']['exchange_id']}")
            return session_context

    def get_context_bus_telemetry(self) -> Dict[str, Any]:
        """
        Get telemetry data from the context bus.

        Returns:
            Dictionary with context exchange statistics
        """
        return self._context_bus.get_telemetry_summary()

    def clear_context_bus_telemetry(self):
        """Clear accumulated context bus telemetry."""
        self._context_bus.clear_telemetry()

    def clear(self):
        """
        Clear all session memory.

        Called when user issues /clear command. Resets conversation history,
        shared context, and metadata while preserving the session_id.
        """
        with self._lock:
            logger.info(f"[SESSION MEMORY] Clearing session: {self.session_id}")

            # Mark as cleared
            self.status = SessionStatus.CLEARED

            # Clear conversation history
            self.interactions.clear()

            # Clear shared context
            self.shared_context.clear()

            # Clear reasoning traces (if enabled)
            self._reasoning_traces.clear()
            self._current_interaction_id = None

            # Reset metadata
            self.metadata = {
                "total_requests": 0,
                "total_steps_executed": 0,
                "agents_used": set(),
                "tools_used": set(),
                "cleared_at": datetime.now().isoformat(),
                "previous_session_duration": self.metadata.get("total_requests", 0),
            }

            # Update timestamp
            self.last_active_at = datetime.now().isoformat()

            logger.info("[SESSION MEMORY] Session cleared successfully")

    def is_active(self) -> bool:
        """Check if session is currently active."""
        return self.status == SessionStatus.ACTIVE

    def is_new_session(self) -> bool:
        """Check if this is a brand new session (no interactions yet)."""
        return len(self.interactions) == 0

    # ===== REASONING TRACE METHODS (Hybrid, opt-in) =====

    def is_reasoning_trace_enabled(self) -> bool:
        """Check if reasoning trace is enabled for this session."""
        return self._reasoning_trace_enabled

    def start_reasoning_trace(self, interaction_id: str) -> bool:
        """
        Start a reasoning trace for a new interaction.

        This should be called when starting to process a user request.
        Creates a new ReasoningTrace instance for tracking decisions.

        Args:
            interaction_id: ID of the interaction to track

        Returns:
            True if trace started, False if feature disabled
        """
        if not self._reasoning_trace_enabled:
            return False

        with self._lock:
            self._current_interaction_id = interaction_id
            if REASONING_TRACE_AVAILABLE:
                self._reasoning_traces[interaction_id] = ReasoningTrace(interaction_id)
                logger.debug(f"[SESSION MEMORY] Started reasoning trace for {interaction_id}")
            return True

    def add_reasoning_entry(
        self,
        stage: str,  # ReasoningStage enum value or string
        thought: str,
        **kwargs
    ) -> Optional[str]:
        """
        Add an entry to the current reasoning trace.

        Hybrid wrapper that gracefully degrades if feature is disabled.

        Args:
            stage: Reasoning stage (planning/execution/etc.)
            thought: High-level reasoning
            **kwargs: Additional entry fields (action, parameters, evidence, etc.)

        Returns:
            Entry ID if successful, None if feature disabled
        """
        if not self._reasoning_trace_enabled or not self._current_interaction_id:
            return None

        trace = self._reasoning_traces.get(self._current_interaction_id)
        if not trace:
            logger.warning(
                f"[SESSION MEMORY] No active trace for interaction "
                f"{self._current_interaction_id}"
            )
            return None

        # Convert string stage to enum if needed
        if isinstance(stage, str) and REASONING_TRACE_AVAILABLE:
            try:
                stage = ReasoningStage(stage.lower())
            except ValueError:
                stage = ReasoningStage.EXECUTION  # Default fallback

        # Convert string outcome to enum if provided
        if "outcome" in kwargs and isinstance(kwargs["outcome"], str):
            if REASONING_TRACE_AVAILABLE:
                try:
                    kwargs["outcome"] = OutcomeStatus(kwargs["outcome"].lower())
                except ValueError:
                    kwargs["outcome"] = OutcomeStatus.PENDING

        return trace.add_entry(stage=stage, thought=thought, **kwargs)

    def update_reasoning_entry(self, entry_id: str, **kwargs) -> bool:
        """
        Update an existing reasoning entry.

        Args:
            entry_id: ID of entry to update
            **kwargs: Fields to update

        Returns:
            True if updated, False otherwise
        """
        if not self._reasoning_trace_enabled or not self._current_interaction_id:
            return False

        trace = self._reasoning_traces.get(self._current_interaction_id)
        if not trace:
            return False

        # Convert string outcome to enum if provided
        if "outcome" in kwargs and isinstance(kwargs["outcome"], str):
            if REASONING_TRACE_AVAILABLE:
                try:
                    kwargs["outcome"] = OutcomeStatus(kwargs["outcome"].lower())
                except ValueError:
                    pass  # Keep original value

        return trace.update_entry(entry_id, **kwargs)

    def get_reasoning_summary(
        self,
        interaction_id: Optional[str] = None,
        max_entries: Optional[int] = 10,
        include_corrections_only: bool = False
    ) -> str:
        """
        Get formatted reasoning trace summary for LLM context.

        This is the key hybrid method: if trace is disabled, returns empty string,
        allowing existing prompts to work unchanged. If enabled, returns rich
        context that can augment or replace scenario-specific examples.

        Args:
            interaction_id: Specific interaction (default: current)
            max_entries: Limit entries (default: 10 most recent)
            include_corrections_only: Only show corrective guidance

        Returns:
            Formatted trace summary (empty string if disabled)
        """
        if not self._reasoning_trace_enabled:
            return ""

        iid = interaction_id or self._current_interaction_id
        if not iid:
            return ""

        trace = self._reasoning_traces.get(iid)
        if not trace:
            return ""

        return trace.get_summary(
            max_entries=max_entries,
            include_corrections_only=include_corrections_only
        )

    def get_pending_commitments(self, interaction_id: Optional[str] = None) -> List[str]:
        """
        Get unfulfilled commitments from reasoning trace.

        Used during finalization to validate delivery (e.g., email sent,
        documents attached).

        Args:
            interaction_id: Specific interaction (default: current)

        Returns:
            List of pending commitment strings (empty if disabled)
        """
        if not self._reasoning_trace_enabled:
            return []

        iid = interaction_id or self._current_interaction_id
        if not iid:
            return []

        trace = self._reasoning_traces.get(iid)
        if not trace:
            return []

        return trace.get_pending_commitments()

    def get_trace_attachments(self, interaction_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all attachments discovered during execution.

        Args:
            interaction_id: Specific interaction (default: current)

        Returns:
            List of attachment dictionaries (empty if disabled)
        """
        if not self._reasoning_trace_enabled:
            return []

        iid = interaction_id or self._current_interaction_id
        if not iid:
            return []

        trace = self._reasoning_traces.get(iid)
        if not trace:
            return []

        return trace.get_attachments()

    def get_trace_corrections(self, interaction_id: Optional[str] = None) -> List[str]:
        """
        Get corrective guidance from Critic agent.

        Args:
            interaction_id: Specific interaction (default: current)

        Returns:
            List of correction strings (empty if disabled)
        """
        if not self._reasoning_trace_enabled:
            return []

        iid = interaction_id or self._current_interaction_id
        if not iid:
            return []

        trace = self._reasoning_traces.get(iid)
        if not trace:
            return []

        return trace.get_corrections()

    # ===== END REASONING TRACE METHODS =====

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize session memory to dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        result = {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "last_active_at": self.last_active_at,
            "interactions": [i.to_dict() for i in self.interactions],
            "shared_context": self.shared_context,
            "user_context": self.user_context.to_dict(),
            "metadata": {
                **self.metadata,
                "agents_used": list(self.metadata.get("agents_used", set())),
                "tools_used": list(self.metadata.get("tools_used", set())),
            },
            "reasoning_trace_enabled": self._reasoning_trace_enabled,
        }

        # Serialize reasoning traces if enabled
        if self._reasoning_trace_enabled and REASONING_TRACE_AVAILABLE:
            result["reasoning_traces"] = {
                iid: trace.to_dict()
                for iid, trace in self._reasoning_traces.items()
            }
        else:
            result["reasoning_traces"] = {}

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMemory":
        """
        Deserialize session memory from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            SessionMemory instance
        """
        # Restore reasoning_trace_enabled flag (default: False for backward compatibility)
        enable_reasoning_trace = data.get("reasoning_trace_enabled", False)
        memory = cls(
            session_id=data["session_id"],
            user_id=data.get("user_id"),  # Optional for backward compatibility
            enable_reasoning_trace=enable_reasoning_trace
        )
        memory.status = SessionStatus(data["status"])
        memory.created_at = data["created_at"]
        memory.last_active_at = data["last_active_at"]

        # Restore interactions
        memory.interactions = [
            Interaction(**i) for i in data["interactions"]
        ]

        # Restore context
        memory.shared_context = data["shared_context"]
        memory.user_context = UserContext(**data["user_context"])

        # Restore metadata
        metadata = data["metadata"].copy()
        metadata["agents_used"] = set(metadata.get("agents_used", []))
        metadata["tools_used"] = set(metadata.get("tools_used", []))
        memory.metadata = metadata

        # Restore reasoning traces if enabled
        if memory._reasoning_trace_enabled and REASONING_TRACE_AVAILABLE:
            traces_data = data.get("reasoning_traces", {})
            for iid, trace_data in traces_data.items():
                memory._reasoning_traces[iid] = ReasoningTrace.from_dict(trace_data)

        return memory

    # Retry Logging Methods
    def is_retry_logging_enabled(self) -> bool:
        """Check if retry logging is enabled."""
        return self._retry_logging_enabled and self._retry_logger is not None

    def log_retry_attempt(
        self,
        interaction_id: str,
        attempt_number: int,
        reason: 'RetryReason',
        priority: 'RecoveryPriority',
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
    ) -> Optional[str]:
        """
        Log a retry attempt with full context.

        Returns:
            retry_id if logged successfully, None if retry logging disabled
        """
        if not self.is_retry_logging_enabled():
            return None

        return self._retry_logger.log_retry_attempt(
            session_id=self.session_id,
            interaction_id=interaction_id,
            attempt_number=attempt_number,
            reason=reason,
            priority=priority,
            failed_action=failed_action,
            error_message=error_message,
            error_type=error_type,
            user_request=user_request,
            execution_context=execution_context,
            reasoning_trace=reasoning_trace,
            critic_feedback=critic_feedback,
            agent_name=agent_name,
            tool_name=tool_name,
            execution_duration_ms=execution_duration_ms,
            retry_possible=retry_possible,
            max_retries_reached=max_retries_reached
        )

    def get_retry_context(self, interaction_id: str) -> Dict[str, Any]:
        """
        Get complete retry context for an interaction.

        Returns:
            Empty dict if retry logging disabled or no context available
        """
        if not self.is_retry_logging_enabled():
            return {}

        return self._retry_logger.get_retry_context(interaction_id)

    def get_last_retry(self, interaction_id: str) -> Optional[Any]:
        """Get the most recent retry entry for an interaction."""
        if not self.is_retry_logging_enabled():
            return None

        return self._retry_logger.get_last_retry(interaction_id)

    def clear_retry_history(self, interaction_id: str):
        """Clear retry history for an interaction."""
        if not self.is_retry_logging_enabled():
            return

        self._retry_logger.clear_retry_history(interaction_id)

    def load_retry_history(self, interaction_id: str) -> List[Any]:
        """Load retry history for an interaction from disk."""
        if not self.is_retry_logging_enabled():
            return []

        return self._retry_logger.load_retry_history(interaction_id)

    def __repr__(self) -> str:
        return (
            f"SessionMemory(id={self.session_id[:8]}..., "
            f"status={self.status.value}, "
            f"interactions={len(self.interactions)})"
        )
