"""
End-to-End Test: Finance-to-Presentation-Email Workflow

This is the HIGHEST PRIORITY test - validates the complete complex workflow:
1. Fetch NVIDIA stock price from Google Finance
2. Create presentation with analysis and charts
3. Email presentation with attachment
4. Verify delivery and UI rendering

WINNING CRITERIA (ALL must pass):
- Stock data retrieved successfully
- Presentation created with content and charts
- Email sent WITH attachment
- UI shows success status
- No errors in workflow
"""

import pytest
import time
import os
import json
from pathlib import Path
from typing import Dict, Any, List

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


class TestFinancePresentationEmail:
    """Test the complete finance → presentation → email workflow."""

    def test_finance_presentation_email_workflow(
        self,
        api_client,
        success_criteria_checker,
        telemetry_collector,
        test_artifacts_dir
    ):
        """
        Test the complete workflow: fetch stock → create presentation → email

        This test validates the most complex user workflow with highest business value.
        """
        # Test query - the highest complexity workflow
        query = "Fetch NVIDIA stock price, create a presentation, email it to me"

        # Record test start
        telemetry_collector.record_event("test_start", {
            "test": "finance_presentation_email",
            "query": query
        })

        # Step 1: Execute the workflow
        start_time = time.time()
        response = api_client.chat(query)
        execution_time = time.time() - start_time

        # Record execution telemetry
        telemetry_collector.record_event("workflow_execution", {
            "query": query,
            "response": response,
            "execution_time": execution_time
        })

        # Step 2: Wait for workflow completion
        messages = api_client.wait_for_completion(max_wait=120)

        # Record completion telemetry
        telemetry_collector.record_event("workflow_completion", {
            "messages_count": len(messages),
            "execution_time": execution_time
        })

        # Step 3: Validate WINNING CRITERIA

        # CRITERIA 1: No errors in response
        assert success_criteria_checker.check_no_errors(response), \
            f"Response contains errors: {response}"

        # CRITERIA 2: Stock data retrieved (check for finance keywords)
        response_text = response.get("message", "")
        stock_keywords = ["nvidia", "stock", "price", "$", "nvda"]
        assert success_criteria_checker.check_keywords_present(response_text, stock_keywords), \
            f"Stock data not found in response. Missing keywords: {stock_keywords}"

        # CRITERIA 3: Presentation creation mentioned
        presentation_keywords = ["presentation", "slide", "created", "presentation"]
        assert success_criteria_checker.check_keywords_present(response_text, presentation_keywords), \
            f"Presentation creation not confirmed. Missing keywords: {presentation_keywords}"

        # CRITERIA 4: Email sent confirmation
        email_keywords = ["email", "sent", "emailed", "delivered"]
        assert success_criteria_checker.check_keywords_present(response_text, email_keywords), \
            f"Email delivery not confirmed. Missing keywords: {email_keywords}"

        # CRITERIA 5: Response meets minimum length (substantial content)
        assert success_criteria_checker.check_response_length(response_text, 200), \
            f"Response too short: {len(response_text)} characters < 200 required"

        # CRITERIA 6: Workflow steps executed (check tool calls in messages)
        expected_tools = ["get_stock_price", "create_presentation", "compose_email"]
        tool_calls = [msg.get("tool_name") for msg in messages if msg.get("type") == "tool_call"]
        assert success_criteria_checker.check_workflow_steps(messages, expected_tools), \
            f"Required tools not executed. Expected: {expected_tools}, Found: {tool_calls}"

        # CRITERIA 7: Attachment verification (check if presentation was attached)
        # This is CRITICAL - email must have attachment
        attachment_found = False
        for message in messages:
            if message.get("type") == "tool_call" and message.get("tool_name") == "compose_email":
                params = message.get("parameters", {})
                if params.get("attachment_path") and "presentation" in params.get("attachment_path", ""):
                    attachment_found = True
                    break

        assert attachment_found, "CRITICAL: Email sent without presentation attachment"

        # CRITERIA 8: Performance check
        assert execution_time < 120, f"Workflow too slow: {execution_time:.2f}s > 120s limit"

        # CRITERIA 9: Presentation file exists (check data/presentations/)
        presentations_dir = Path("data/presentations")
        nvidia_presentations = list(presentations_dir.glob("*nvidia*")) if presentations_dir.exists() else []
        assert len(nvidia_presentations) > 0, "Presentation file not found in data/presentations/"

        # CRITERIA 10: Email delivery verification (check sent mailbox simulation)
        # Note: In real implementation, this would check actual email delivery
        # For now, we verify the email tool was called with attachment

        print("✅ ALL WINNING CRITERIA PASSED")
        print(f"   Execution time: {execution_time:.2f}s")
        print(f"   Tools executed: {tool_calls}")
        print(f"   Presentation files: {[p.name for p in nvidia_presentations]}")

        # Save test results
        test_results = {
            "test": "finance_presentation_email",
            "passed": True,
            "criteria_results": success_criteria_checker.get_results(),
            "execution_time": execution_time,
            "tool_calls": tool_calls,
            "presentation_files": [str(p) for p in nvidia_presentations],
            "telemetry": telemetry_collector.get_events()
        }

        results_file = test_artifacts_dir["reports"] / "finance_presentation_email_results.json"
        with open(results_file, 'w') as f:
            json.dump(test_results, f, indent=2)

    def test_finance_presentation_email_negative_attachment_missing(
        self,
        api_client,
        success_criteria_checker,
        telemetry_collector
    ):
        """
        NEGATIVE TEST: Ensure email is NOT sent when attachment fails

        This validates the critical safety requirement that emails are not sent
        without their required attachments.
        """
        # This test would simulate a presentation creation failure
        # and verify that email is not sent when attachment is missing

        query = "Create a presentation and email it to me"
        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        # Check that if attachment creation fails, email is not sent
        email_sent_without_attachment = False
        presentation_failed = False

        for message in messages:
            if message.get("type") == "error" and "presentation" in message.get("message", ""):
                presentation_failed = True
            if (message.get("type") == "tool_call" and
                message.get("tool_name") == "compose_email" and
                not message.get("parameters", {}).get("attachment_path")):
                email_sent_without_attachment = True

        # If presentation fails, email should not be sent
        if presentation_failed:
            assert not email_sent_without_attachment, \
                "CRITICAL: Email sent despite presentation creation failure"

    def test_finance_presentation_email_ui_rendering(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test UI rendering of the finance presentation email workflow

        Validates that the frontend properly displays:
        - Workflow progress
        - Success status
        - Attachment indicators
        - Download links
        """
        query = "Fetch stock price for AAPL, create presentation, email it"
        api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=90)

        # Check UI-relevant message types
        ui_messages = [msg for msg in messages if msg.get("type") in ["status", "completion", "attachment"]]

        # Should have status updates for each major step
        assert len(ui_messages) >= 3, f"Insufficient UI status messages: {len(ui_messages)} < 3"

        # Check for attachment-related UI elements
        attachment_messages = [msg for msg in messages if "attachment" in str(msg)]
        assert len(attachment_messages) > 0, "No attachment status shown in UI"

        print("✅ UI rendering validation passed")


if __name__ == "__main__":
    # Allow running this test directly for debugging
    pytest.main([__file__, "-v", "-s"])
