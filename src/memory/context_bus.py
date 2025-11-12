"""
ContextBus - Standardized context exchange and telemetry.

Implements MCP-style (Model Context Protocol) schemas for context sharing,
validation, versioning, and observability across memory, planner, and tools.
"""

import json
import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock

# Lazy import to avoid circular dependency


logger = logging.getLogger(__name__)


class ContextSchema(Enum):
    """Supported context schema versions for validation."""
    V1_0 = "1.0"
    V1_1 = "1.1"  # Adds reasoning budget hints


class ContextPurpose(Enum):
    """Standardized context purposes for telemetry."""
    PLANNER = "planner"
    WRITER = "writer"
    RESEARCHER = "researcher"
    GENERAL = "general"


@dataclass
class ContextExchange:
    """
    Metadata for context exchanges between components.

    Tracks telemetry for observability and optimization.
    """
    exchange_id: str
    timestamp: str
    from_component: str
    to_component: str
    purpose: ContextPurpose
    schema_version: ContextSchema
    context_size_bytes: int
    token_estimate: int
    profile: str
    latency_ms: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    truncation_events: List[Dict[str, Any]] = field(default_factory=list)
    budget_escalations: List[Dict[str, Any]] = field(default_factory=list)


class ContextBus:
    """
    Centralized bus for context exchange with validation and telemetry.

    Implements MCP-style protocols for:
    - Schema validation and versioning
    - Serialization/deserialization
    - Telemetry collection
    - Context size management
    - Truncation and escalation tracking
    """

    def __init__(self):
        self._lock = Lock()
        self._exchanges: List[ContextExchange] = []
        self._telemetry_enabled = True
        logger.info("[CONTEXT BUS] Initialized")

    def publish_context(
        self,
        session_context: "SessionContext",
        from_component: str,
        to_component: str,
        purpose: ContextPurpose = ContextPurpose.GENERAL
    ) -> Dict[str, Any]:
        """
        Publish context to a target component with validation and telemetry.

        Args:
            session_context: The context to publish
            from_component: Source component name
            to_component: Target component name
            purpose: Purpose of the context exchange

        Returns:
            Dictionary with serialized context and metadata
        """
        start_time = datetime.now()

        with self._lock:
            try:
                # Validate and serialize context
                serialized = self._serialize_context(session_context, purpose)
                context_size = len(json.dumps(serialized).encode('utf-8'))

                # Create exchange record
                exchange = ContextExchange(
                    exchange_id=f"ctx_{len(self._exchanges) + 1}",
                    timestamp=start_time.isoformat(),
                    from_component=from_component,
                    to_component=to_component,
                    purpose=purpose,
                    schema_version=ContextSchema.V1_1,  # Current version
                    context_size_bytes=context_size,
                    token_estimate=session_context.token_budget_metadata.get("estimated_tokens", 1000),
                    profile=session_context.token_budget_metadata.get("profile", "unknown")
                )

                # Record latency
                end_time = datetime.now()
                exchange.latency_ms = int((end_time - start_time).total_seconds() * 1000)

                self._exchanges.append(exchange)

                logger.debug(f"[CONTEXT BUS] Published context {exchange.exchange_id}: {from_component} → {to_component} ({context_size} bytes)")

                return {
                    "context": serialized,
                    "metadata": {
                        "exchange_id": exchange.exchange_id,
                        "schema_version": exchange.schema_version.value,
                        "purpose": exchange.purpose.value,
                        "token_budget": session_context.token_budget_metadata
                    }
                }

            except Exception as e:
                logger.error(f"[CONTEXT BUS] Error publishing context: {e}")
                # Record failed exchange
                exchange = ContextExchange(
                    exchange_id=f"ctx_{len(self._exchanges) + 1}",
                    timestamp=start_time.isoformat(),
                    from_component=from_component,
                    to_component=to_component,
                    purpose=purpose,
                    schema_version=ContextSchema.V1_1,
                    context_size_bytes=0,
                    token_estimate=0,
                    profile="error",
                    success=False,
                    error_message=str(e)
                )
                self._exchanges.append(exchange)
                raise

    def consume_context(
        self,
        context_payload: Dict[str, Any],
        consumer_component: str
    ) -> "SessionContext":
        """
        Consume and validate context from the bus.

        Args:
            context_payload: Context payload from publish_context
            consumer_component: Component consuming the context

        Returns:
            Deserialized SessionContext
        """
        with self._lock:
            try:
                metadata = context_payload.get("metadata", {})
                serialized_context = context_payload.get("context", {})

                # Validate schema version
                schema_version = metadata.get("schema_version", "1.0")
                if schema_version not in [s.value for s in ContextSchema]:
                    raise ValueError(f"Unsupported schema version: {schema_version}")

                # Deserialize context
                session_context = self._deserialize_context(serialized_context)

                # Update exchange record with consumption
                exchange_id = metadata.get("exchange_id")
                if exchange_id and self._telemetry_enabled:
                    for exchange in self._exchanges:
                        if exchange.exchange_id == exchange_id:
                            # Could add consumption telemetry here
                            break

                logger.debug(f"[CONTEXT BUS] Consumed context {exchange_id} by {consumer_component}")
                return session_context

            except Exception as e:
                logger.error(f"[CONTEXT BUS] Error consuming context: {e}")
                raise

    def _serialize_context(
        self,
        session_context: "SessionContext",
        purpose: ContextPurpose
    ) -> Dict[str, Any]:
        """
        Serialize SessionContext with purpose-specific optimizations.

        Applies adaptive context distillation based on purpose and profile.
        """
        base_data = session_context.to_dict()

        # Apply purpose-specific filtering
        if purpose == ContextPurpose.PLANNER:
            # For planners, prioritize original query and derived topic
            filtered = {
                "original_query": base_data["original_query"],
                "session_id": base_data["session_id"],
                "derived_topic": base_data.get("derived_topic"),
                "context_objects": base_data["context_objects"],
                "salience_ranked_snippets": base_data["salience_ranked_snippets"][:5],  # Top 5 snippets
                "token_budget_metadata": base_data["token_budget_metadata"],
                "purpose": base_data["purpose"]
            }
        elif purpose == ContextPurpose.WRITER:
            # For writers, include more context objects but fewer snippets
            filtered = {
                "original_query": base_data["original_query"],
                "session_id": base_data["session_id"],
                "derived_topic": base_data.get("derived_topic"),
                "context_objects": base_data["context_objects"],
                "salience_ranked_snippets": base_data["salience_ranked_snippets"][:3],  # Top 3 snippets
                "token_budget_metadata": base_data["token_budget_metadata"],
                "purpose": base_data["purpose"]
            }
        else:
            # General purpose - include all data
            filtered = base_data

        # Apply token budget constraints
        profile = session_context.token_budget_metadata.get("profile", "compact")
        max_tokens = session_context.token_budget_metadata.get("max_tokens")

        if max_tokens:
            filtered = self._apply_token_budget(filtered, max_tokens, profile)

        return filtered

    def _deserialize_context(self, serialized_data: Dict[str, Any]) -> "SessionContext":
        """
        Deserialize context data back to SessionContext.

        Validates required fields and reconstructs the object.
        """
        # Ensure required fields exist
        required_fields = ["original_query", "session_id"]
        for field in required_fields:
            if field not in serialized_data:
                raise ValueError(f"Missing required field in context: {field}")

        # Lazy import to avoid circular dependency
        from .session_memory import SessionContext

        # Reconstruct SessionContext
        # Note: We need to handle the case where some optional fields might be missing
        # due to filtering during serialization
        return SessionContext(
            original_query=serialized_data["original_query"],
            session_id=serialized_data["session_id"],
            context_objects=serialized_data.get("context_objects", {}),
            salience_ranked_snippets=serialized_data.get("salience_ranked_snippets", []),
            retrieval_handles=serialized_data.get("retrieval_handles", {}),
            token_budget_metadata=serialized_data.get("token_budget_metadata", {}),
            derived_topic=serialized_data.get("derived_topic"),
            purpose=serialized_data.get("purpose", "general")
        )

    def _apply_token_budget(
        self,
        context_data: Dict[str, Any],
        max_tokens: int,
        profile: str
    ) -> Dict[str, Any]:
        """
        Apply adaptive context distillation based on token budget.

        Uses techniques from Wang et al. (2024) for preserving salient facts.
        """
        # Rough token estimation (words * 1.3 for subword tokens)
        current_tokens = self._estimate_tokens(context_data)

        if current_tokens <= max_tokens:
            return context_data

        # Apply distillation strategies based on profile
        if profile == "compact":
            # Aggressive truncation for compact profiles
            context_data["salience_ranked_snippets"] = context_data["salience_ranked_snippets"][:1]  # Keep only top snippet
            context_data["context_objects"] = self._truncate_context_objects(context_data["context_objects"], 0.5)
        elif profile == "reasoning":
            # Moderate truncation for reasoning profiles
            context_data["salience_ranked_snippets"] = context_data["salience_ranked_snippets"][:3]
            context_data["context_objects"] = self._truncate_context_objects(context_data["context_objects"], 0.7)
        else:
            # Conservative truncation for full profiles
            context_data["salience_ranked_snippets"] = context_data["salience_ranked_snippets"][:5]
            context_data["context_objects"] = self._truncate_context_objects(context_data["context_objects"], 0.9)

        # Final check and truncation if still over budget
        final_tokens = self._estimate_tokens(context_data)
        if final_tokens > max_tokens:
            context_data = self._truncate_to_budget(context_data, max_tokens)

        return context_data

    def _estimate_tokens(self, data: Dict[str, Any]) -> int:
        """Rough token estimation for context data."""
        json_str = json.dumps(data)
        word_count = len(json_str.split())
        return int(word_count * 1.3)  # Rough approximation

    def _truncate_context_objects(self, context_objects: Dict[str, Any], keep_ratio: float) -> Dict[str, Any]:
        """Truncate context objects while preserving most important ones."""
        if not context_objects:
            return {}

        # Prioritize user preferences and frequently used tools
        priority_keys = ["user_preferences", "frequently_used_tools", "common_patterns"]
        result = {}

        # Keep priority items
        for key in priority_keys:
            if key in context_objects:
                result[key] = context_objects[key]

        # Keep a portion of remaining items
        remaining_keys = [k for k in context_objects.keys() if k not in priority_keys]
        keep_count = max(1, int(len(remaining_keys) * keep_ratio))

        for key in remaining_keys[:keep_count]:
            result[key] = context_objects[key]

        return result

    def _truncate_to_budget(self, context_data: Dict[str, Any], max_tokens: int) -> Dict[str, Any]:
        """Final truncation to ensure token budget compliance."""
        # Remove snippets first
        context_data["salience_ranked_snippets"] = []

        # Then truncate context objects
        context_data["context_objects"] = self._truncate_context_objects(context_data["context_objects"], 0.3)

        # If still over budget, truncate the original query
        if self._estimate_tokens(context_data) > max_tokens:
            original_query = context_data["original_query"]
            max_query_length = min(len(original_query), max_tokens // 2)
            context_data["original_query"] = original_query[:max_query_length] + "..."

        return context_data

    def get_telemetry_summary(self) -> Dict[str, Any]:
        """
        Get telemetry summary for observability.

        Returns:
            Dictionary with exchange statistics and performance metrics
        """
        with self._lock:
            if not self._exchanges:
                return {"total_exchanges": 0, "success_rate": 0.0}

            total_exchanges = len(self._exchanges)
            successful_exchanges = sum(1 for e in self._exchanges if e.success)
            avg_latency = sum(e.latency_ms for e in self._exchanges if e.latency_ms) / total_exchanges
            total_bytes = sum(e.context_size_bytes for e in self._exchanges)
            total_tokens = sum(e.token_estimate for e in self._exchanges)

            # Profile distribution
            profile_counts = {}
            for exchange in self._exchanges:
                profile_counts[exchange.profile] = profile_counts.get(exchange.profile, 0) + 1

            return {
                "total_exchanges": total_exchanges,
                "success_rate": successful_exchanges / total_exchanges,
                "average_latency_ms": avg_latency,
                "total_context_bytes": total_bytes,
                "total_estimated_tokens": total_tokens,
                "profile_distribution": profile_counts,
                "recent_exchanges": [
                    {
                        "id": e.exchange_id,
                        "from": e.from_component,
                        "to": e.to_component,
                        "purpose": e.purpose.value,
                        "success": e.success,
                        "latency_ms": e.latency_ms,
                        "tokens": e.token_estimate
                    }
                    for e in self._exchanges[-10:]  # Last 10 exchanges
                ]
            }

    def clear_telemetry(self):
        """Clear accumulated telemetry data."""
        with self._lock:
            self._exchanges.clear()
            logger.info("[CONTEXT BUS] Telemetry cleared")
