"""
End-to-End Tests: Explain Command Functionality

Tests the explain command for:
- Code file explanations
- Functionality explanations
- Complex system understanding
- Error handling for missing files
- UI display of explanations

WINNING CRITERIA:
- Files properly located and read
- Explanations structured and informative
- Key functions/components identified
- UI renders formatted explanations
"""

import pytest
import time
from pathlib import Path
from typing import Dict, Any, List

pytestmark = [pytest.mark.e2e]


class TestExplainCommands:
    """Test comprehensive explain command functionality."""

    def test_explain_code_file(
        self,
        api_client,
        success_criteria_checker,
        telemetry_collector
    ):
        """
        Test explaining a code file with proper structure.

        WINNING CRITERIA:
        - File located successfully
        - Structured explanation provided
        - Key functions identified
        - Code sections explained
        - UI displays formatted explanation
        """
        # Use a known file from the codebase
        target_file = "src/agent/agent.py"

        query = f"Explain {target_file}"

        telemetry_collector.record_event("explain_test_start", {
            "type": "code_file",
            "file": target_file
        })

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=90)  # Longer timeout for analysis

        response_text = response.get("message", "")

        # Check success criteria
        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 300)  # Substantial explanation

        # Check explanation quality keywords
        explanation_keywords = ["function", "class", "purpose", "component"]
        assert success_criteria_checker.check_keywords_present(response_text, explanation_keywords)

        # Verify file was accessed
        file_accessed = any(
            target_file in str(msg.get("parameters", {}))
            for msg in messages
            if msg.get("type") == "tool_call" and "read" in msg.get("tool_name", "")
        )
        assert file_accessed, f"File {target_file} was not accessed for explanation"

        telemetry_collector.record_event("explain_test_complete", {
            "file_explained": target_file,
            "explanation_length": len(response_text)
        })

    def test_explain_functionality(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test explaining system functionality.

        WINNING CRITERIA:
        - Functionality understood
        - Process explained clearly
        - Components identified
        - Examples provided where relevant
        """
        query = "Explain how the reminders system works"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=90)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 200)

        # Check for functionality explanation keywords
        functionality_keywords = ["reminder", "schedule", "automation", "storage"]
        assert success_criteria_checker.check_keywords_present(response_text, functionality_keywords)

        # Should explain the process/steps
        process_keywords = ["create", "store", "trigger", "notification"]
        assert success_criteria_checker.check_keywords_present(response_text, process_keywords)

    def test_explain_complex_workflow(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test explaining complex multi-component workflows.

        WINNING CRITERIA:
        - Multiple components explained
        - Integration points identified
        - Data flow described
        - Dependencies clarified
        """
        query = "Explain how email reading and summarization works"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=90)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 250)

        # Check for workflow explanation
        workflow_keywords = ["email", "read", "summarize", "process", "integration"]
        assert success_criteria_checker.check_keywords_present(response_text, workflow_keywords)

        # Should mention key components
        component_keywords = ["gmail", "parsing", "analysis", "storage"]
        found_components = sum(1 for keyword in component_keywords if keyword in response_text.lower())
        assert found_components >= 2, f"Only {found_components} components mentioned, need at least 2"

    def test_explain_ui_display(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test that explanations display properly in UI.

        WINNING CRITERIA:
        - Formatted display
        - Code sections highlighted
        - Navigation aids present
        - Structured layout
        """
        query = "Explain the main orchestrator component"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=90)

        # Check for UI formatting messages
        ui_messages = [msg for msg in messages if msg.get("type") in ["formatted_explanation", "code_display", "structured_content"]]

        # Should have some UI formatting
        assert len(ui_messages) > 0, "No UI formatting for explanation"

        response_text = response.get("message", "")
        assert success_criteria_checker.check_response_length(response_text, 150)

    def test_explain_missing_file_handling(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        NEGATIVE TEST: Handle missing files gracefully.

        WINNING CRITERIA:
        - Missing file detected
        - Helpful error message
        - Suggestions provided
        - No crash or confusion
        """
        query = "Explain non_existent_file.py"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        # Should handle missing file gracefully
        missing_file_handled = (
            "not found" in response_text.lower() or
            "doesn't exist" in response_text.lower() or
            "cannot find" in response_text.lower() or
            "error" in response_text.lower()
        )

        assert missing_file_handled, "Missing file not handled gracefully"

        # Should provide helpful guidance
        has_guidance = (
            "check" in response_text.lower() or
            "verify" in response_text.lower() or
            "path" in response_text.lower() or
            "try" in response_text.lower()
        )

        assert has_guidance, "No helpful guidance provided for missing file"

    def test_explain_large_file_chunking(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test explanation of large files with proper chunking.

        WINNING CRITERIA:
        - Large file handled
        - Content chunked appropriately
        - Key sections identified
        - Summary provided
        - Navigation between sections
        """
        # Use a known large file
        large_file = "src/agent/agent.py"  # This is typically large

        query = f"Explain the {large_file} file in detail"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=120)  # Extra time for large file

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 500)  # Detailed explanation

        # Should show chunking/structure handling
        structure_keywords = ["section", "part", "component", "module"]
        assert success_criteria_checker.check_keywords_present(response_text, structure_keywords)

    def test_explain_with_cross_references(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test explanations that include cross-references to other components.

        WINNING CRITERIA:
        - Related components mentioned
        - Dependencies explained
        - Integration points identified
        - Reference links provided
        """
        query = "Explain the agent registry and how it relates to other components"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=90)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 300)

        # Should mention relationships and cross-references
        reference_keywords = ["integrates", "connects", "uses", "depends", "related"]
        assert success_criteria_checker.check_keywords_present(response_text, reference_keywords)

        # Should mention multiple components
        components = ["agent", "orchestrator", "registry", "memory", "tool"]
        mentioned_components = sum(1 for comp in components if comp in response_text.lower())
        assert mentioned_components >= 3, f"Only {mentioned_components} components mentioned, need at least 3"

    def test_explain_error_recovery(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test explanation error recovery and fallback behavior.

        WINNING CRITERIA:
        - Errors handled gracefully
        - Fallback explanations provided
        - User not left confused
        - Partial information given when possible
        """
        # Test with a problematic query
        query = "Explain the quantum physics implementation"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        # Should handle unknown topics gracefully
        graceful_handling = (
            "not found" in response_text.lower() or
            "available" in response_text.lower() or
            "clarify" in response_text.lower() or
            "help" in response_text.lower() or
            success_criteria_checker.check_no_errors(response)
        )

        assert graceful_handling, "Unknown topic not handled gracefully"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
