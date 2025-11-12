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


logger = logging.getLogger(__name__)

# Optional reasoning trace support (feature flag controlled)
try:
    from .reasoning_trace import ReasoningTrace, ReasoningStage, OutcomeStatus
    REASONING_TRACE_AVAILABLE = True
except ImportError:
    REASONING_TRACE_AVAILABLE = False
    logger.debug("[SESSION MEMORY] ReasoningTrace module not available")


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
        user_context: Optional[UserContext] = None,
        enable_reasoning_trace: bool = False
    ):
        """
        Initialize session memory.

        Args:
            session_id: Unique session identifier (generated if not provided)
            user_context: User preferences and patterns (new if not provided)
            enable_reasoning_trace: Enable reasoning trace feature (default: False)
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.status = SessionStatus.ACTIVE
        self.created_at = datetime.now().isoformat()
        self.last_active_at = self.created_at

        # Conversation history
        self.interactions: List[Interaction] = []

        # Shared context for inter-agent communication
        # e.g., {"last_file_path": "/path/to/file", "current_presentation_id": "123"}
        self.shared_context: Dict[str, Any] = {}

        # User preferences and patterns
        self.user_context = user_context or UserContext()

        # Additional metadata
        self.metadata: Dict[str, Any] = {
            "total_requests": 0,
            "total_steps_executed": 0,
            "agents_used": set(),
            "tools_used": set(),
        }

        # Reasoning trace support (opt-in, feature flag controlled)
        self._reasoning_trace_enabled = enable_reasoning_trace and REASONING_TRACE_AVAILABLE
        self._reasoning_traces: Dict[str, Any] = {}  # interaction_id -> ReasoningTrace
        self._current_interaction_id: Optional[str] = None

        if self._reasoning_trace_enabled:
            logger.info(f"[SESSION MEMORY] Reasoning trace enabled for session {self.session_id}")

        # Internal lock for thread-safe access to SessionMemory instance
        # Note: SessionManager also uses locks, but this provides additional safety
        # when SessionMemory is accessed directly from multiple threads/coroutines
        self._lock = Lock()

        logger.info(f"[SESSION MEMORY] Created session: {self.session_id}")

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

            logger.debug(f"[SESSION MEMORY] Added interaction {interaction_id}")

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

        This can be merged into OrchestratorState or AgentState to provide
        session awareness to the LangGraph execution.

        Returns:
            Dictionary compatible with LangGraph state
        """
        return {
            "session_id": self.session_id,
            "session_status": self.status.value,
            "conversation_history": self.get_conversation_history(max_interactions=5),
            "shared_context": self.shared_context.copy(),
            "session_metadata": {
                "created_at": self.created_at,
                "last_active_at": self.last_active_at,
                "total_requests": self.metadata["total_requests"],
            }
        }

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
        return {
            "session_id": self.session_id,
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
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMemory":
        """
        Deserialize session memory from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            SessionMemory instance
        """
        memory = cls(session_id=data["session_id"])
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

        return memory

    def __repr__(self) -> str:
        return (
            f"SessionMemory(id={self.session_id[:8]}..., "
            f"status={self.status.value}, "
            f"interactions={len(self.interactions)})"
        )
