"""
Unit tests for ReasoningTrace functionality.

Tests the hybrid reasoning trace system that tracks decisions,
evidence, and commitments across agent executions.

Success Criteria:
1. ReasoningTrace works independently (no dependencies on agents)
2. SessionMemory integration is backward compatible
3. Feature flag correctly enables/disables functionality
4. Trace collection has minimal performance impact
5. All methods gracefully handle disabled state
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.memory.reasoning_trace import (
    ReasoningEntry,
    ReasoningTrace,
    ReasoningStage,
    OutcomeStatus,
    extract_attachments_from_step_result,
    detect_commitments_from_user_request
)
from src.memory.session_memory import SessionMemory, REASONING_TRACE_AVAILABLE


class TestReasoningEntry:
    """Test ReasoningEntry dataclass."""

    def test_entry_creation(self):
        """Test creating a reasoning entry."""
        entry = ReasoningEntry(
            entry_id="test_1",
            interaction_id="int_1",
            timestamp="2025-01-01T00:00:00",
            stage=ReasoningStage.PLANNING.value,
            thought="Planning to search documents",
            action="search_documents",
            parameters={"query": "Tesla"},
            evidence=["Found 3 PDFs"],
            outcome=OutcomeStatus.SUCCESS.value
        )

        assert entry.entry_id == "test_1"
        assert entry.thought == "Planning to search documents"
        assert entry.is_complete()
        assert not entry.has_pending_commitments()

    def test_entry_with_commitments(self):
        """Test entry with pending commitments."""
        entry = ReasoningEntry(
            entry_id="test_2",
            interaction_id="int_1",
            timestamp="2025-01-01T00:00:00",
            stage=ReasoningStage.EXECUTION.value,
            thought="Need to send email",
            commitments=["send_email", "attach_document"],
            outcome=OutcomeStatus.PENDING.value
        )

        assert entry.has_pending_commitments()
        assert "send_email" in entry.commitments

    def test_entry_serialization(self):
        """Test entry to_dict and from_dict."""
        original = ReasoningEntry(
            entry_id="test_3",
            interaction_id="int_1",
            timestamp="2025-01-01T00:00:00",
            stage=ReasoningStage.VERIFICATION.value,
            thought="Verifying output",
            outcome=OutcomeStatus.SUCCESS.value
        )

        # Serialize and deserialize
        data = original.to_dict()
        restored = ReasoningEntry.from_dict(data)

        assert restored.entry_id == original.entry_id
        assert restored.thought == original.thought
        assert restored.stage == original.stage


class TestReasoningTrace:
    """Test ReasoningTrace functionality."""

    def test_trace_creation(self):
        """Test creating a reasoning trace."""
        trace = ReasoningTrace(interaction_id="int_1")
        assert trace.interaction_id == "int_1"
        assert len(trace.entries) == 0

    def test_add_entry(self):
        """Test adding entries to trace."""
        trace = ReasoningTrace(interaction_id="int_1")

        entry_id = trace.add_entry(
            stage=ReasoningStage.PLANNING,
            thought="Planning workflow",
            evidence=["User requested email"],
            outcome=OutcomeStatus.SUCCESS
        )

        assert entry_id is not None
        assert len(trace.entries) == 1
        assert trace.entries[0].thought == "Planning workflow"

    def test_update_entry(self):
        """Test updating an existing entry."""
        trace = ReasoningTrace(interaction_id="int_1")

        entry_id = trace.add_entry(
            stage=ReasoningStage.EXECUTION,
            thought="Executing search",
            outcome=OutcomeStatus.PENDING
        )

        # Update with results
        success = trace.update_entry(
            entry_id,
            outcome=OutcomeStatus.SUCCESS,
            evidence=["Found 5 documents"],
            attachments=[{"type": "file", "path": "/test.pdf"}]
        )

        assert success
        entry = trace._entry_index[entry_id]
        assert entry.outcome == OutcomeStatus.SUCCESS.value
        assert "Found 5 documents" in entry.evidence
        assert len(entry.attachments) == 1

    def test_get_summary(self):
        """Test generating trace summary."""
        trace = ReasoningTrace(interaction_id="int_1")

        trace.add_entry(
            stage=ReasoningStage.PLANNING,
            thought="Plan to search and email",
            commitments=["send_email"],
            outcome=OutcomeStatus.SUCCESS
        )

        trace.add_entry(
            stage=ReasoningStage.EXECUTION,
            thought="Searching documents",
            action="search_documents",
            parameters={"query": "Tesla"},
            evidence=["Found 3 PDFs"],
            attachments=[{"type": "file", "path": "/tesla.pdf"}],
            outcome=OutcomeStatus.SUCCESS
        )

        summary = trace.get_summary()
        assert "PLANNING" in summary
        assert "Plan to search and email" in summary
        assert "EXECUTION" in summary
        assert "Searching documents" in summary
        assert "tesla.pdf" in summary

    def test_get_pending_commitments(self):
        """Test retrieving pending commitments."""
        trace = ReasoningTrace(interaction_id="int_1")

        trace.add_entry(
            stage=ReasoningStage.PLANNING,
            thought="Need to send email",
            commitments=["send_email", "attach_document"],
            outcome=OutcomeStatus.PENDING
        )

        pending = trace.get_pending_commitments()
        assert "send_email" in pending
        assert "attach_document" in pending

    def test_get_attachments(self):
        """Test retrieving all attachments."""
        trace = ReasoningTrace(interaction_id="int_1")

        trace.add_entry(
            stage=ReasoningStage.EXECUTION,
            thought="Search step",
            attachments=[
                {"type": "file", "path": "/doc1.pdf"},
                {"type": "file", "path": "/doc2.pdf"}
            ],
            outcome=OutcomeStatus.SUCCESS
        )

        attachments = trace.get_attachments()
        assert len(attachments) == 2
        assert attachments[0]["path"] == "/doc1.pdf"

    def test_get_corrections(self):
        """Test retrieving corrective guidance."""
        trace = ReasoningTrace(interaction_id="int_1")

        trace.add_entry(
            stage=ReasoningStage.CORRECTION,
            thought="Analysis of failure",
            corrections=[
                "Retry with broader query",
                "Check file permissions"
            ],
            outcome=OutcomeStatus.SUCCESS
        )

        corrections = trace.get_corrections()
        assert len(corrections) == 2
        assert "Retry with broader query" in corrections

    def test_trace_serialization(self):
        """Test trace serialization."""
        trace = ReasoningTrace(interaction_id="int_1")

        trace.add_entry(
            stage=ReasoningStage.PLANNING,
            thought="Test entry",
            outcome=OutcomeStatus.SUCCESS
        )

        # Serialize and deserialize
        data = trace.to_dict()
        restored = ReasoningTrace.from_dict(data)

        assert restored.interaction_id == trace.interaction_id
        assert len(restored.entries) == len(trace.entries)
        assert restored.entries[0].thought == "Test entry"


class TestSessionMemoryIntegration:
    """Test SessionMemory integration with ReasoningTrace."""

    def test_session_without_trace(self):
        """Test session memory without reasoning trace (default behavior)."""
        memory = SessionMemory()

        # Should work normally without trace
        assert not memory.is_reasoning_trace_enabled()
        assert memory.get_reasoning_summary() == ""
        assert memory.get_pending_commitments() == []

        # Adding entries should be no-op but safe
        entry_id = memory.add_reasoning_entry(
            stage="planning",
            thought="Test"
        )
        assert entry_id is None

    @pytest.mark.skipif(not REASONING_TRACE_AVAILABLE, reason="ReasoningTrace not available")
    def test_session_with_trace_enabled(self):
        """Test session memory with reasoning trace enabled."""
        memory = SessionMemory(enable_reasoning_trace=True)

        assert memory.is_reasoning_trace_enabled()

        # Start trace for interaction
        interaction_id = memory.add_interaction(
            user_request="Test request"
        )
        memory.start_reasoning_trace(interaction_id)

        # Add reasoning entry
        entry_id = memory.add_reasoning_entry(
            stage="planning",
            thought="Planning test workflow",
            evidence=["User input received"],
            outcome="success"
        )

        assert entry_id is not None

        # Get summary
        summary = memory.get_reasoning_summary()
        assert "Planning test workflow" in summary

    @pytest.mark.skipif(not REASONING_TRACE_AVAILABLE, reason="ReasoningTrace not available")
    def test_session_update_entry(self):
        """Test updating reasoning entry through session memory."""
        memory = SessionMemory(enable_reasoning_trace=True)

        interaction_id = memory.add_interaction(user_request="Test")
        memory.start_reasoning_trace(interaction_id)

        entry_id = memory.add_reasoning_entry(
            stage="execution",
            thought="Running tool",
            outcome="pending"
        )

        # Update entry
        updated = memory.update_reasoning_entry(
            entry_id,
            outcome="success",
            evidence=["Tool completed successfully"]
        )

        assert updated

    @pytest.mark.skipif(not REASONING_TRACE_AVAILABLE, reason="ReasoningTrace not available")
    def test_backward_compatibility(self):
        """Test that existing SessionMemory code works unchanged."""
        # Old code (without trace)
        memory_old = SessionMemory()
        memory_old.add_interaction(user_request="Old request")
        memory_old.set_context("test_key", "test_value")

        # Should work exactly as before
        assert memory_old.get_context("test_key") == "test_value"
        assert len(memory_old.interactions) == 1

        # New code (with trace)
        memory_new = SessionMemory(enable_reasoning_trace=True)
        memory_new.add_interaction(user_request="New request")
        memory_new.set_context("test_key", "test_value")

        # Should still work for existing functionality
        assert memory_new.get_context("test_key") == "test_value"
        assert len(memory_new.interactions) == 1


class TestUtilityFunctions:
    """Test utility functions."""

    def test_extract_attachments_from_files_list(self):
        """Test extracting attachments from files list."""
        result = {
            "files": ["/path/doc1.pdf", "/path/doc2.pdf"]
        }

        attachments = extract_attachments_from_step_result(result)
        assert len(attachments) == 2
        assert attachments[0]["type"] == "file"
        assert attachments[0]["path"] == "/path/doc1.pdf"

    def test_extract_attachments_from_documents(self):
        """Test extracting attachments from documents list."""
        result = {
            "documents": [
                {"file_path": "/doc1.pdf", "name": "Document 1"},
                {"file_path": "/doc2.pdf", "name": "Document 2"}
            ]
        }

        attachments = extract_attachments_from_step_result(result)
        assert len(attachments) == 2
        assert attachments[0]["type"] == "document"
        assert attachments[0]["name"] == "Document 1"

    def test_extract_attachments_from_output_path(self):
        """Test extracting single output path."""
        result = {
            "output_path": "/generated/report.pdf"
        }

        attachments = extract_attachments_from_step_result(result)
        assert len(attachments) == 1
        assert attachments[0]["status"] == "created"

    def test_detect_commitments_from_request(self):
        """Test detecting commitments from user request."""
        config = {
            "delivery": {
                "intent_verbs": ["email", "send", "mail", "attach"]
            }
        }

        # Email with attachment
        request1 = "Search for Tesla docs and email them to me"
        commitments1 = detect_commitments_from_user_request(request1, config)
        assert "send_email" in commitments1
        assert "attach_documents" in commitments1

        # Just email
        request2 = "Send me a summary by email"
        commitments2 = detect_commitments_from_user_request(request2, config)
        assert "send_email" in commitments2

        # No delivery intent
        request3 = "What's the weather today?"
        commitments3 = detect_commitments_from_user_request(request3, config)
        assert len(commitments3) == 0


class TestPerformance:
    """Test performance characteristics."""

    @pytest.mark.skipif(not REASONING_TRACE_AVAILABLE, reason="ReasoningTrace not available")
    def test_trace_overhead_acceptable(self):
        """Test that trace collection has minimal overhead."""
        import time

        # Without trace
        memory_no_trace = SessionMemory(enable_reasoning_trace=False)
        interaction_id = memory_no_trace.add_interaction(user_request="Test")

        start = time.time()
        for i in range(100):
            memory_no_trace.add_reasoning_entry(
                stage="execution",
                thought=f"Step {i}"
            )
        time_no_trace = time.time() - start

        # With trace
        memory_with_trace = SessionMemory(enable_reasoning_trace=True)
        interaction_id = memory_with_trace.add_interaction(user_request="Test")
        memory_with_trace.start_reasoning_trace(interaction_id)

        start = time.time()
        for i in range(100):
            memory_with_trace.add_reasoning_entry(
                stage="execution",
                thought=f"Step {i}"
            )
        time_with_trace = time.time() - start

        # Overhead should be < 50ms for 100 operations
        overhead = time_with_trace - time_no_trace
        assert overhead < 0.05, f"Trace overhead too high: {overhead*1000:.2f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
