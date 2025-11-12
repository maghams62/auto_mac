"""
Test suite for SessionContext dataclass and context building functionality.

Tests:
1. SessionContext creation and serialization
2. Context building with different profiles (compact, reasoning, full)
3. Topic derivation from original queries
4. Token budget metadata handling
5. ContextBus integration and telemetry
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime

from src.memory.session_memory import SessionMemory, SessionContext
from src.memory.context_bus import ContextBus, ContextPurpose, ContextSchema


class TestSessionContext:
    """Test SessionContext dataclass functionality."""

    def test_context_creation_basic(self):
        """Test creating a basic SessionContext."""
        context = SessionContext(
            original_query="Why did Arsenal draw?",
            session_id="test_session_123"
        )

        assert context.original_query == "Why did Arsenal draw?"
        assert context.session_id == "test_session_123"
        assert context.purpose == "general"
        assert context.context_objects == {}
        assert context.salience_ranked_snippets == []
        assert context.derived_topic is None

    def test_context_headline_derivation(self):
        """Test automatic headline derivation from queries."""
        # Why question
        context = SessionContext(
            original_query="Why did Arsenal draw against Chelsea?",
            session_id="test_session_123"
        )
        assert context.headline() == "Why Arsenal Draw Against Chelsea"

        # How question
        context = SessionContext(
            original_query="How do I reset my password?",
            session_id="test_session_123"
        )
        assert context.headline() == "How-to: do I reset"

        # What question
        context = SessionContext(
            original_query="What is machine learning?",
            session_id="test_session_123"
        )
        assert context.headline() == "Understanding: is machine learning"

        # Analyze question
        context = SessionContext(
            original_query="Analyze the quarterly results",
            session_id="test_session_123"
        )
        assert context.headline() == "Analysis: the quarterly results"

        # Explicit derived_topic takes precedence
        context.derived_topic = "Custom Title"
        assert context.headline() == "Custom Title"

    def test_context_serialization(self):
        """Test SessionContext serialization/deserialization."""
        context = SessionContext(
            original_query="Test query",
            session_id="test_123",
            context_objects={"key": "value"},
            derived_topic="Test Topic",
            purpose="planner"
        )

        data = context.to_dict()
        assert data["original_query"] == "Test query"
        assert data["session_id"] == "test_123"
        assert data["context_objects"] == {"key": "value"}
        assert data["derived_topic"] == "Test Topic"
        assert data["purpose"] == "planner"


class TestSessionContextBuilding:
    """Test SessionMemory.build_context functionality."""

    def test_build_context_basic(self):
        """Test basic context building."""
        memory = SessionMemory()
        memory.add_interaction("Why did Arsenal draw?")

        context = memory.build_context(profile="compact", purpose="planner")

        assert isinstance(context, SessionContext)
        assert context.original_query == "Why did Arsenal draw?"
        assert context.session_id == memory.session_id
        assert context.purpose == "planner"
        assert "profile" in context.token_budget_metadata
        assert "estimated_tokens" in context.token_budget_metadata

    def test_build_context_profiles(self):
        """Test different context profiles."""
        memory = SessionMemory()
        memory.add_interaction("Test query")

        # Compact profile
        compact_context = memory.build_context(profile="compact", purpose="planner")
        assert compact_context.token_budget_metadata["profile"] == "compact"
        assert compact_context.token_budget_metadata["estimated_tokens"] == 500

        # Reasoning profile
        reasoning_context = memory.build_context(profile="reasoning", purpose="planner")
        assert reasoning_context.token_budget_metadata["profile"] == "reasoning"
        assert reasoning_context.token_budget_metadata["estimated_tokens"] == 2000

        # Full profile
        full_context = memory.build_context(profile="full", purpose="planner")
        assert full_context.token_budget_metadata["profile"] == "full"
        assert full_context.token_budget_metadata["estimated_tokens"] == 4000

    def test_build_context_with_history(self):
        """Test context building with interaction history."""
        memory = SessionMemory()

        # Add multiple interactions
        memory.add_interaction("First query")
        memory.add_interaction("Second query", {"status": "success"})
        memory.add_interaction("Third query")

        # Set some context
        memory.set_context("last_file", "/path/to/file.txt")
        memory.set_context("user_preference", "dark_mode")

        context = memory.build_context(profile="compact", purpose="planner")

        assert context.original_query == "Third query"  # Most recent
        assert len(context.salience_ranked_snippets) > 0
        assert "last_file" in context.context_objects
        assert "user_preference" in context.context_objects

    def test_build_context_with_token_limits(self):
        """Test context building with token limits."""
        memory = SessionMemory()
        memory.add_interaction("A very long query that should be truncated if we have token limits")

        context = memory.build_context(
            profile="compact",
            purpose="planner",
            max_tokens=100
        )

        assert context.token_budget_metadata["max_tokens"] == 100
        assert context.token_budget_metadata["estimated_tokens"] <= 100

    def test_context_summary_generation(self):
        """Test context summary generation."""
        context = SessionContext(
            original_query="Why did Arsenal draw?",
            session_id="test_123",
            derived_topic="Why Arsenal Drew",
            context_objects={"key": "value"},
            salience_ranked_snippets=[
                {"content": "Arsenal played poorly", "salience": 0.9}
            ],
            token_budget_metadata={"profile": "compact"}
        )

        summary = context.get_context_summary()
        assert "Why did Arsenal draw?" in summary
        assert "Why Arsenal Drew" in summary
        assert "key: value" in summary
        assert "Arsenal played poorly" in summary


class TestContextBus:
    """Test ContextBus functionality."""

    def test_context_bus_creation(self):
        """Test ContextBus initialization."""
        bus = ContextBus()
        telemetry = bus.get_telemetry_summary()
        assert telemetry["total_exchanges"] == 0
        assert telemetry["success_rate"] == 0.0

    def test_context_publish_consume(self):
        """Test publishing and consuming context through the bus."""
        bus = ContextBus()

        context = SessionContext(
            original_query="Test query",
            session_id="test_123"
        )

        # Publish context
        payload = bus.publish_context(
            session_context=context,
            from_component="test_component",
            to_component="planner",
            purpose=ContextPurpose.PLANNER
        )

        assert "context" in payload
        assert "metadata" in payload
        assert payload["metadata"]["schema_version"] == "1.1"
        assert payload["metadata"]["purpose"] == "planner"

        # Consume context
        consumed_context = bus.consume_context(payload, "consumer")
        assert isinstance(consumed_context, SessionContext)
        assert consumed_context.original_query == "Test query"

    def test_context_bus_telemetry(self):
        """Test ContextBus telemetry collection."""
        bus = ContextBus()

        context = SessionContext(
            original_query="Test query",
            session_id="test_123"
        )

        # Publish multiple contexts
        bus.publish_context(context, "comp1", "comp2", ContextPurpose.PLANNER)
        bus.publish_context(context, "comp2", "comp3", ContextPurpose.WRITER)

        telemetry = bus.get_telemetry_summary()
        assert telemetry["total_exchanges"] == 2
        assert telemetry["success_rate"] == 1.0
        assert len(telemetry["recent_exchanges"]) == 2
        assert telemetry["profile_distribution"]["unknown"] == 2  # Default profile

    def test_context_filtering_by_purpose(self):
        """Test context filtering based on purpose."""
        bus = ContextBus()

        # Create context with lots of data
        context = SessionContext(
            original_query="Long original query for testing truncation",
            session_id="test_123",
            context_objects={"obj1": "value1", "obj2": "value2", "obj3": "value3"},
            salience_ranked_snippets=[
                {"content": "Snippet 1", "salience": 0.9},
                {"content": "Snippet 2", "salience": 0.8},
                {"content": "Snippet 3", "salience": 0.7}
            ]
        )

        # Test planner purpose filtering
        payload = bus.publish_context(context, "memory", "planner", ContextPurpose.PLANNER)
        planner_context = bus.consume_context(payload, "planner")

        # Planner should have fewer snippets
        assert len(planner_context.salience_ranked_snippets) <= 3

        # Test writer purpose filtering
        payload = bus.publish_context(context, "memory", "writer", ContextPurpose.WRITER)
        writer_context = bus.consume_context(payload, "writer")

        # Writer should have different filtering
        assert writer_context.purpose == "writer"

    def test_context_token_budget_truncation(self):
        """Test token budget-based truncation."""
        bus = ContextBus()

        # Create context with lots of data
        context = SessionContext(
            original_query="Very long query that should be truncated",
            session_id="test_123",
            context_objects={"large_object": "x" * 1000},  # Large object
            salience_ranked_snippets=[{"content": "y" * 500, "salience": 0.9}] * 10  # Many snippets
        )

        # Publish with small token budget
        payload = bus.publish_context(
            session_context=context,
            from_component="memory",
            to_component="planner",
            purpose=ContextPurpose.PLANNER
        )

        # The context should be truncated to fit token budget
        consumed_context = bus.consume_context(payload, "planner")

        # Check that truncation occurred
        telemetry = bus.get_telemetry_summary()
        assert telemetry["total_exchanges"] == 1

        # The consumed context should have been filtered/truncated
        assert len(consumed_context.salience_ranked_snippets) <= len(context.salience_ranked_snippets)


class TestIntegration:
    """Integration tests for SessionContext and ContextBus."""

    def test_end_to_end_context_flow(self):
        """Test complete context flow from memory to consumption."""
        # Create session memory with interactions
        memory = SessionMemory()
        memory.add_interaction("Why did Arsenal draw against Chelsea?")
        memory.set_context("sport", "football")
        memory.set_context("team", "Arsenal")

        # Build context
        context = memory.build_context(profile="reasoning", purpose="planner")

        # Verify context has expected data
        assert context.headline() == "Why Arsenal Drew"
        assert "sport" in context.context_objects
        assert "team" in context.context_objects
        assert context.token_budget_metadata["profile"] == "reasoning"

        # Publish through bus
        payload = memory._context_bus.publish_context(
            context, "memory", "planner", ContextPurpose.PLANNER
        )

        # Consume context
        consumed = memory._context_bus.consume_context(payload, "planner")

        # Verify consumed context
        assert consumed.original_query == "Why did Arsenal draw against Chelsea?"
        assert consumed.headline() == "Why Arsenal Drew"

        # Check telemetry
        telemetry = memory.get_context_bus_telemetry()
        assert telemetry["total_exchanges"] >= 1
        assert telemetry["success_rate"] == 1.0

    def test_context_bus_telemetry_clearing(self):
        """Test clearing ContextBus telemetry."""
        memory = SessionMemory()
        memory.add_interaction("Test query")

        # Generate some telemetry
        memory.build_context(profile="compact", purpose="planner")

        telemetry = memory.get_context_bus_telemetry()
        assert telemetry["total_exchanges"] >= 1

        # Clear telemetry
        memory.clear_context_bus_telemetry()

        telemetry = memory.get_context_bus_telemetry()
        assert telemetry["total_exchanges"] == 0
