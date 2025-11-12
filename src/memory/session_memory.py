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
        user_context: Optional[UserContext] = None,
        enable_reasoning_trace: bool = False,
        enable_retry_logging: bool = False
    ):
        """
        Initialize session memory.

        Args:
            session_id: Unique session identifier (generated if not provided)
            user_context: User preferences and patterns (new if not provided)
            enable_reasoning_trace: Enable reasoning trace feature (default: False)
            enable_retry_logging: Enable retry logging feature (default: False)
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

            session_context = SessionContext(
                original_query=original_query,
                session_id=self.session_id,
                context_objects=context_objects,
                salience_ranked_snippets=salience_ranked_snippets,
                retrieval_handles=retrieval_handles,
                token_budget_metadata=token_budget_metadata,
                derived_topic=derived_topic,
                purpose=purpose
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
        memory = cls(session_id=data["session_id"], enable_reasoning_trace=enable_reasoning_trace)
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
