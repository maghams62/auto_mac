"""
Integration test for ReasoningTrace with existing agent workflow.

This test demonstrates the hybrid approach: existing code works unchanged,
and new code can optionally use reasoning trace for enhanced context.

Success Criteria:
1. Existing workflow runs without modifications
2. Trace-enabled workflow collects reasoning data
3. Trace summary provides useful context for LLM prompts
4. Commitment tracking helps with delivery validation
5. Performance impact is negligible
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.memory.session_memory import SessionMemory, REASONING_TRACE_AVAILABLE
from src.memory.reasoning_trace import (
    extract_attachments_from_step_result,
    detect_commitments_from_user_request
)
from src.memory.session_manager import SessionManager


class TestWorkflowIntegration:
    """Test full workflow integration."""

    def test_existing_workflow_without_trace(self):
        """
        Test that existing workflow continues to work unchanged.

        This simulates the current system behavior where SessionMemory
        is used without reasoning trace.
        """
        # Create session (trace disabled by default)
        memory = SessionMemory()

        # Simulate user request
        user_request = "Search for Tesla documents and email them"
        interaction_id = memory.add_interaction(user_request=user_request)

        # Store some context (existing pattern)
        memory.set_context("last_search_query", "Tesla")
        memory.set_context("last_search_results", ["/doc1.pdf", "/doc2.pdf"])

        # Finalize interaction
        memory.update_interaction(
            interaction_id,
            agent_response={"status": "success", "message": "Email sent"}
        )

        # Verify existing functionality works
        assert memory.get_context("last_search_query") == "Tesla"
        assert len(memory.get_context("last_search_results")) == 2
        assert len(memory.interactions) == 1

        # Trace methods return empty/safe defaults
        assert memory.get_reasoning_summary() == ""
        assert memory.get_pending_commitments() == []

    @pytest.mark.skipif(not REASONING_TRACE_AVAILABLE, reason="ReasoningTrace not available")
    def test_enhanced_workflow_with_trace(self):
        """
        Test enhanced workflow with reasoning trace enabled.

        This demonstrates how new code can use trace for richer context
        without breaking existing patterns.
        """
        # Create session with trace enabled
        memory = SessionMemory(enable_reasoning_trace=True)
        config = {
            "delivery": {
                "intent_verbs": ["email", "send", "mail", "attach"]
            }
        }

        # Simulate user request
        user_request = "Search for Tesla documents and email them"
        interaction_id = memory.add_interaction(user_request=user_request)

        # Start reasoning trace
        memory.start_reasoning_trace(interaction_id)

        # 1. PLANNING PHASE
        # Detect commitments from user request
        commitments = detect_commitments_from_user_request(user_request, config)

        planning_entry = memory.add_reasoning_entry(
            stage="planning",
            thought="User wants to search documents and email them",
            evidence=[
                f"User request: {user_request}",
                f"Detected intents: {commitments}"
            ],
            commitments=commitments,
            outcome="success"
        )

        # 2. EXECUTION PHASE - Search
        search_entry = memory.add_reasoning_entry(
            stage="execution",
            thought="Executing document search",
            action="search_documents",
            parameters={"query": "Tesla"},
            outcome="pending"
        )

        # Simulate search results
        search_result = {
            "files": ["/docs/tesla_report.pdf", "/docs/tesla_analysis.pdf"],
            "count": 2
        }
        attachments = extract_attachments_from_step_result(search_result)

        # Update search entry with results
        memory.update_reasoning_entry(
            search_entry,
            outcome="success",
            evidence=[f"Found {len(attachments)} documents"],
            attachments=attachments
        )

        # Store in shared context (existing pattern still works)
        memory.set_context("last_search_results", search_result["files"])

        # 3. EXECUTION PHASE - Email
        email_entry = memory.add_reasoning_entry(
            stage="execution",
            thought="Composing email with attachments",
            action="compose_email",
            parameters={
                "recipient": "user@example.com",
                "subject": "Tesla Documents",
                "attachments": [a["path"] for a in attachments]
            },
            outcome="pending"
        )

        # Simulate email success
        memory.update_reasoning_entry(
            email_entry,
            outcome="success",
            evidence=["Email sent successfully with 2 attachments"]
        )

        # 4. VERIFICATION PHASE
        # Check if commitments were fulfilled
        pending = memory.get_pending_commitments()
        trace_attachments = memory.get_trace_attachments()

        # All commitments should be fulfilled (no pending)
        # Note: In real workflow, finalization logic would check this
        assert len(trace_attachments) == 2

        # 5. GET REASONING SUMMARY FOR LLM CONTEXT
        # This is what would be injected into planner prompts
        summary = memory.get_reasoning_summary()

        # Verify summary contains key information
        assert "PLANNING" in summary
        assert "EXECUTION" in summary
        assert "search_documents" in summary
        assert "compose_email" in summary
        assert "tesla_report.pdf" in summary
        assert "Found 2 documents" in summary

        # Existing functionality still works
        assert memory.get_context("last_search_results") == search_result["files"]
        assert len(memory.interactions) == 1

    @pytest.mark.skipif(not REASONING_TRACE_AVAILABLE, reason="ReasoningTrace not available")
    def test_critic_feedback_integration(self):
        """
        Test Critic agent feedback integration with trace.

        Demonstrates how corrective guidance flows through the trace.
        """
        memory = SessionMemory(enable_reasoning_trace=True)
        interaction_id = memory.add_interaction(user_request="Test request")
        memory.start_reasoning_trace(interaction_id)

        # Step 1: Attempt fails
        search_entry = memory.add_reasoning_entry(
            stage="execution",
            thought="Searching with narrow query",
            action="search_documents",
            parameters={"query": "very_specific_term"},
            outcome="pending"
        )

        # Simulate failure
        memory.update_reasoning_entry(
            search_entry,
            outcome="failed",
            error="No documents found",
            evidence=["Query returned 0 results"]
        )

        # Step 2: Critic analyzes failure
        critic_entry = memory.add_reasoning_entry(
            stage="correction",
            thought="Analyzing search failure",
            evidence=["Query too specific", "No results returned"],
            corrections=[
                "Retry with broader query terms",
                "Consider using stemming or fuzzy matching"
            ],
            outcome="success"
        )

        # Step 3: Retry with correction applied
        retry_entry = memory.add_reasoning_entry(
            stage="execution",
            thought="Retrying search with broader query",
            action="search_documents",
            parameters={"query": "specific"},
            outcome="success",
            evidence=["Found 5 documents with broader query"]
        )

        # Get corrections for future planning
        corrections = memory.get_trace_corrections()
        assert len(corrections) == 2
        assert "broader query" in corrections[0].lower()

        # Summary includes correction guidance
        summary = memory.get_reasoning_summary()
        assert "CORRECTION" in summary
        assert "Analyzing search failure" in summary

    @pytest.mark.skipif(not REASONING_TRACE_AVAILABLE, reason="ReasoningTrace not available")
    def test_attachment_validation_workflow(self):
        """
        Test attachment tracking for delivery validation.

        This solves the problem: "Did we actually attach the files we
        promised to attach?"
        """
        memory = SessionMemory(enable_reasoning_trace=True)
        config = {"delivery": {"intent_verbs": ["email", "send"]}}

        user_request = "Find quarterly reports and email them to finance team"
        interaction_id = memory.add_interaction(user_request=user_request)
        memory.start_reasoning_trace(interaction_id)

        # Planning: Detect delivery commitment
        commitments = detect_commitments_from_user_request(user_request, config)

        memory.add_reasoning_entry(
            stage="planning",
            thought="Need to search and email with attachments",
            commitments=commitments,
            outcome="success"
        )

        # Execution: Search finds documents
        search_entry = memory.add_reasoning_entry(
            stage="execution",
            thought="Searching for quarterly reports",
            action="search_documents",
            outcome="pending"
        )

        search_result = {
            "documents": [
                {"file_path": "/reports/Q1_2024.pdf", "name": "Q1 Report"},
                {"file_path": "/reports/Q2_2024.pdf", "name": "Q2 Report"}
            ]
        }
        attachments = extract_attachments_from_step_result(search_result)

        memory.update_reasoning_entry(
            search_entry,
            outcome="success",
            attachments=attachments,
            evidence=[f"Found {len(attachments)} reports"]
        )

        # Execution: Email is sent
        email_entry = memory.add_reasoning_entry(
            stage="execution",
            thought="Sending email to finance team",
            action="compose_email",
            parameters={
                "recipient": "finance@company.com",
                "attachments": [a["path"] for a in attachments]
            },
            outcome="success",
            evidence=["Email sent with 2 attachments"]
        )

        # Finalization: Validate attachments were included
        trace_attachments = memory.get_trace_attachments()

        assert len(trace_attachments) == 2
        assert any("Q1_2024.pdf" in a["path"] for a in trace_attachments)
        assert any("Q2_2024.pdf" in a["path"] for a in trace_attachments)

        # In real finalization logic, this would prevent:
        # "Email sent" response when no attachments were actually included

    def test_performance_with_large_trace(self):
        """
        Test performance with many reasoning entries.

        Ensures trace doesn't slow down long-running workflows.
        """
        import time

        memory = SessionMemory(enable_reasoning_trace=True)
        interaction_id = memory.add_interaction(user_request="Complex task")
        memory.start_reasoning_trace(interaction_id)

        # Simulate 50 steps (typical complex workflow)
        start = time.time()
        for i in range(50):
            entry_id = memory.add_reasoning_entry(
                stage="execution",
                thought=f"Executing step {i}",
                action=f"tool_{i}",
                outcome="success",
                evidence=[f"Result {i}"]
            )
        elapsed = time.time() - start

        # Should complete in < 100ms
        assert elapsed < 0.1, f"Trace collection too slow: {elapsed*1000:.2f}ms"

        # Summary generation should also be fast
        start = time.time()
        summary = memory.get_reasoning_summary(max_entries=10)
        summary_time = time.time() - start

        assert summary_time < 0.01, f"Summary generation too slow: {summary_time*1000:.2f}ms"
        assert "Executing step 49" in summary  # Should include recent entries


class TestHybridPromptPattern:
    """Test hybrid prompt pattern: existing + trace context."""

    @pytest.mark.skipif(not REASONING_TRACE_AVAILABLE, reason="ReasoningTrace not available")
    def test_prompt_augmentation_pattern(self):
        """
        Demonstrate how trace augments (not replaces) existing prompts.

        Pattern:
        1. Use existing prompt examples for cold-start
        2. If trace available, inject real execution history
        3. LLM gets both: general examples + actual context
        """
        memory = SessionMemory(enable_reasoning_trace=True)
        interaction_id = memory.add_interaction(user_request="Test task")
        memory.start_reasoning_trace(interaction_id)

        # Add some reasoning
        memory.add_reasoning_entry(
            stage="planning",
            thought="Previous attempt used tool X",
            evidence=["Tool X succeeded", "Output was Y"],
            outcome="success"
        )

        # Simulate prompt construction (pseudo-code)
        existing_prompt_examples = """
        Example 1: User asks for email, agent uses compose_email
        Example 2: User asks for search, agent uses search_documents
        """

        # Get trace context (returns empty string if disabled)
        trace_context = memory.get_reasoning_summary()

        # Hybrid prompt combines both
        if trace_context:
            full_prompt = f"{existing_prompt_examples}\n\n{trace_context}\n\n[Current task...]"
        else:
            full_prompt = f"{existing_prompt_examples}\n\n[Current task...]"

        # Verify trace is included when available
        assert "Previous attempt used tool X" in full_prompt
        assert "Example 1:" in full_prompt  # Existing examples still there

        # This is the key insight: trace doesn't replace prompts,
        # it provides additional real-world context


    @pytest.mark.skipif(not REASONING_TRACE_AVAILABLE, reason="ReasoningTrace not available")
    def test_trace_enabled_end_to_end(self):
        """
        End-to-end test: verify trace enabled, entries exist, /clear removes them.

        This test exercises the full flow:
        1. Config flag flows through SessionManager → SessionMemory
        2. Trace entries are created during planning/execution
        3. /clear purges all traces
        """
        # Create config with reasoning_trace.enabled: true
        config = {
            "reasoning_trace": {
                "enabled": True
            },
            "delivery": {
                "intent_verbs": ["email", "send", "mail", "attach"]
            }
        }

        # Initialize SessionManager with config
        session_manager = SessionManager(storage_dir="data/test_sessions", config=config)

        # Create session and verify trace is enabled
        memory = session_manager.get_or_create_session("test_trace_session")
        assert memory.is_reasoning_trace_enabled(), "Trace should be enabled"

        # Simulate one request: add interaction, start trace, add planning/execution entries
        user_request = "Search for Tesla documents and email them"
        interaction_id = memory.add_interaction(user_request=user_request)
        memory.start_reasoning_trace(interaction_id)

        # Add planning entry
        from src.memory.reasoning_trace import detect_commitments_from_user_request
        commitments = detect_commitments_from_user_request(user_request, config)
        planning_entry_id = memory.add_reasoning_entry(
            stage="planning",
            thought="Created plan: Search and email documents",
            evidence=["Steps: 2"],
            commitments=commitments,
            outcome="success"
        )
        assert planning_entry_id is not None

        # Add execution entry
        execution_entry_id = memory.add_reasoning_entry(
            stage="execution",
            thought="Executing search_documents",
            action="search_documents",
            parameters={"query": "Tesla"},
            outcome="pending"
        )
        assert execution_entry_id is not None

        # Update execution entry with results
        memory.update_reasoning_entry(
            execution_entry_id,
            outcome="success",
            evidence=["Found 2 documents"],
            attachments=[{"type": "file", "path": "/test/tesla.pdf"}]
        )

        # Verify entries exist via get_reasoning_summary()
        summary = memory.get_reasoning_summary()
        assert "PLANNING" in summary
        assert "EXECUTION" in summary
        assert "search_documents" in summary
        assert "Created plan" in summary

        # Call memory.clear() (simulating /clear)
        memory.clear()

        # Verify _reasoning_traces is empty and get_reasoning_summary() returns empty string
        assert len(memory._reasoning_traces) == 0, "Traces should be cleared"
        assert memory._current_interaction_id is None, "Current interaction ID should be reset"
        assert memory.get_reasoning_summary() == "", "Summary should be empty after clear"

    @pytest.mark.skipif(not REASONING_TRACE_AVAILABLE, reason="ReasoningTrace not available")
    def test_serialization_round_trip(self):
        """
        Test serialization round-trip: traces persist across save/load.
        """
        config = {
            "reasoning_trace": {
                "enabled": True
            }
        }

        session_manager = SessionManager(storage_dir="data/test_sessions", config=config)

        # Create session with trace enabled, add entries
        memory = session_manager.get_or_create_session("test_serialization")
        assert memory.is_reasoning_trace_enabled()

        interaction_id = memory.add_interaction(user_request="Test request")
        memory.start_reasoning_trace(interaction_id)

        memory.add_reasoning_entry(
            stage="planning",
            thought="Test planning entry",
            evidence=["Test evidence"],
            outcome="success"
        )

        memory.add_reasoning_entry(
            stage="execution",
            thought="Test execution entry",
            action="test_tool",
            outcome="success"
        )

        # Get original summary
        original_summary = memory.get_reasoning_summary()
        assert "Test planning entry" in original_summary
        assert "Test execution entry" in original_summary

        # Serialize via to_dict()
        data = memory.to_dict()
        assert "reasoning_traces" in data
        assert "reasoning_trace_enabled" in data
        assert data["reasoning_trace_enabled"] is True

        # Create new session via from_dict()
        restored_memory = SessionMemory.from_dict(data)

        # Verify traces are restored
        assert restored_memory.is_reasoning_trace_enabled()
        assert len(restored_memory._reasoning_traces) > 0

        # Set current interaction ID to match restored trace
        restored_memory._current_interaction_id = interaction_id

        # Verify get_reasoning_summary() returns same content
        restored_summary = restored_memory.get_reasoning_summary()
        assert "Test planning entry" in restored_summary
        assert "Test execution entry" in restored_summary

    def test_reasoning_context_assembly_fix(self):
        """
        Regression test: ensure reasoning context assembly uses correct SessionMemory methods.

        This tests the fix for the issue where memory.get_reasoning_summary().get("commitments", [])
        was called on a string return value, and memory.get_interaction_count() was undefined.
        """
        # Create memory with reasoning trace enabled
        memory = SessionMemory(enable_reasoning_trace=True)

        # Add some interactions to build context
        interaction_id = memory.add_interaction(user_request="play some music")
        memory.start_reasoning_trace(interaction_id)
        memory.add_reasoning_entry(
            stage="planning",
            thought="User wants to play music",
            commitments=["play requested song"],
            outcome="success"
        )
        memory.add_reasoning_entry("execution", "Calling play_song tool")

        # Test the fixed reasoning context assembly logic
        # This simulates the code in agent.py execute_step method
        try:
            reasoning_context = {
                "trace_enabled": True,
                "commitments": memory.get_pending_commitments(),
                "past_attempts": len(memory.interactions),
                "interaction_id": getattr(memory, '_current_interaction_id', None)
            }
        except Exception as e:
            pytest.fail(f"Reasoning context assembly failed: {e}")

        # Verify the context was built correctly
        assert reasoning_context["trace_enabled"] is True
        assert isinstance(reasoning_context["commitments"], list)  # Should be list from get_pending_commitments()
        assert isinstance(reasoning_context["past_attempts"], int)  # Should be int from len(interactions)
        assert reasoning_context["interaction_id"] == interaction_id

        # Verify the old broken approach would have failed
        with pytest.raises(AttributeError):
            # This is what the old code tried to do - call .get() on a string
            broken_commitments = memory.get_reasoning_summary().get("commitments", [])

        # Verify get_interaction_count doesn't exist (would raise AttributeError)
        with pytest.raises(AttributeError):
            broken_attempts = memory.get_interaction_count()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
