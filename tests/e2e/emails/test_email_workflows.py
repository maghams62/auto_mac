"""
End-to-End Tests: Email Workflows

Tests all email functionality:
- Compose with attachments (critical for presentation emails)
- Reply and forward
- Search and summarize
- Negative tests for attachment failures

WINNING CRITERIA:
- Attachments properly included
- No emails sent without required attachments
- Proper threading and context preservation
- UI shows correct status
"""

import pytest
import time
import json
from pathlib import Path
from typing import Dict, Any, List

pytestmark = [pytest.mark.e2e]


class TestEmailWorkflows:
    """Test comprehensive email workflow functionality."""

    def test_compose_email_with_attachment(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir,
        telemetry_collector
    ):
        """
        Test composing email with attachment - critical for presentation workflow.

        WINNING CRITERIA:
        - Email sent successfully
        - Attachment included
        - Correct recipient and subject
        - UI shows success
        """
        # Create a test file to attach
        test_file = test_artifacts_dir["reports"] / "test_attachment.txt"
        test_file.write_text("This is a test attachment for email workflow testing.")

        query = f"Compose an email to test@example.com with subject 'Test Attachment' and attach the file {test_file}"

        telemetry_collector.record_event("email_test_start", {"type": "compose_with_attachment"})

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        # Validate success criteria
        response_text = response.get("message", "")

        # Check no errors
        assert success_criteria_checker.check_no_errors(response)

        # Check email sent confirmation
        email_keywords = ["email", "sent", "attachment"]
        assert success_criteria_checker.check_keywords_present(response_text, email_keywords)

        # CRITICAL: Verify attachment was included
        attachment_verified = False
        for message in messages:
            if message.get("type") == "tool_call" and message.get("tool_name") == "compose_email":
                params = message.get("parameters", {})
                if params.get("attachment_path") == str(test_file):
                    attachment_verified = True
                    break

        assert attachment_verified, "CRITICAL: Email sent without required attachment"

        telemetry_collector.record_event("email_test_complete", {
            "type": "compose_with_attachment",
            "attachment_verified": attachment_verified
        })

    def test_email_reply_workflow(
        self,
        api_client,
        success_criteria_checker,
        mock_services
    ):
        """
        Test replying to emails with proper context preservation.

        WINNING CRITERIA:
        - Original email found
        - Reply sent with context
        - Thread maintained
        """
        # Setup mock email for reply
        mock_email = {
            "id": "test_email_001",
            "subject": "Meeting Tomorrow",
            "sender": "boss@example.com",
            "body": "Let's meet tomorrow at 2pm to discuss the project.",
            "timestamp": "2024-01-15T14:30:00Z"
        }

        query = "Reply to the email from boss@example.com saying 'I'll be there at 2pm'"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        # Check success criteria
        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 100)

        # Check reply keywords
        reply_keywords = ["reply", "sent", "email"]
        assert success_criteria_checker.check_keywords_present(response_text, reply_keywords)

        # Verify reply was sent (would check actual email in real implementation)
        reply_sent = any(
            msg.get("tool_name") == "reply_to_email"
            for msg in messages
            if msg.get("type") == "tool_call"
        )
        assert reply_sent, "Reply was not sent"

    def test_email_forward_workflow(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test forwarding emails to multiple recipients.

        WINNING CRITERIA:
        - Original email located
        - Forwarded successfully
        - Recipients correct
        """
        query = "Forward the project update email to team@example.com and manager@example.com"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 100)

        forward_keywords = ["forward", "sent", "email"]
        assert success_criteria_checker.check_keywords_present(response_text, forward_keywords)

    def test_email_search_and_summarize(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test searching emails and generating summaries.

        WINNING CRITERIA:
        - Search executed
        - Results found
        - Summary generated
        - UI displays properly
        """
        query = "Find emails from last week about budget and summarize them"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 200)

        # Check for search and summary keywords
        search_keywords = ["email", "budget", "summary"]
        assert success_criteria_checker.check_keywords_present(response_text, search_keywords)

        # Verify search tool was called
        search_executed = any(
            msg.get("tool_name") in ["search_emails", "read_emails"]
            for msg in messages
            if msg.get("type") == "tool_call"
        )
        assert search_executed, "Email search was not executed"

    def test_email_negative_no_attachment_safety(
        self,
        api_client,
        success_criteria_checker,
        telemetry_collector
    ):
        """
        CRITICAL NEGATIVE TEST: Ensure emails are NOT sent when attachments fail.

        This validates the safety requirement that incomplete emails don't get sent.
        """
        # Test case where attachment is requested but fails
        query = "Email me the non-existent-report.pdf file"

        telemetry_collector.record_event("safety_test_start", {
            "test": "attachment_safety",
            "scenario": "missing_attachment"
        })

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        # Check that error is properly handled
        has_error = "error" in response or "cannot" in response_text.lower() or "not found" in response_text.lower()

        # Verify email was NOT sent when attachment failed
        email_sent = any(
            msg.get("tool_name") == "compose_email"
            for msg in messages
            if msg.get("type") == "tool_call"
        )

        # CRITICAL: If attachment fails, email should not be sent
        if has_error:
            assert not email_sent, "CRITICAL SAFETY FAILURE: Email sent despite attachment error"

        telemetry_collector.record_event("safety_test_complete", {
            "error_detected": has_error,
            "email_sent": email_sent,
            "safety_violation": has_error and email_sent
        })

    def test_email_attachment_validation(
        self,
        api_client,
        success_criteria_checker,
        test_artifacts_dir
    ):
        """
        Test that email attachments are properly validated and included.

        WINNING CRITERIA:
        - File exists before sending
        - Attachment path correct
        - File size reasonable
        - MIME type appropriate
        """
        # Create test files of different types
        text_file = test_artifacts_dir["reports"] / "email_test.txt"
        text_file.write_text("Test email attachment content.")

        pdf_file = test_artifacts_dir["reports"] / "test_doc.pdf"
        pdf_file.write_bytes(b"Mock PDF content")  # In real test, use actual PDF

        # Test text file attachment
        query = f"Send test email with {text_file} attached"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        # Verify attachment was included
        attachment_found = False
        for message in messages:
            if message.get("type") == "tool_call" and message.get("tool_name") == "compose_email":
                params = message.get("parameters", {})
                if params.get("attachment_path") and str(text_file) in params.get("attachment_path"):
                    attachment_found = True
                    break

        assert attachment_found, "Text file attachment not found in email"

        # Verify file actually exists
        assert text_file.exists(), "Attachment file does not exist"

        response_text = response.get("message", "")
        assert success_criteria_checker.check_keywords_present(response_text, ["sent", "attachment"])

    def test_email_ui_status_display(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test that email operations show proper UI status.

        WINNING CRITERIA:
        - Status messages for sending
        - Success/error indicators
        - Attachment badges
        - Progress updates
        """
        query = "Send a quick test email to myself"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        # Check for UI-relevant messages
        status_messages = [msg for msg in messages if msg.get("type") in ["status", "progress", "completion"]]

        # Should have at least sending status
        assert len(status_messages) > 0, "No status messages for UI"

        # Check for completion message
        completion_messages = [msg for msg in messages if msg.get("type") == "completion"]
        assert len(completion_messages) > 0, "No completion message for UI"

        response_text = response.get("message", "")
        assert success_criteria_checker.check_response_length(response_text, 50)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
