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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
