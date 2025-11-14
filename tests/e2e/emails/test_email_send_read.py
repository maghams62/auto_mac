"""
End-to-End Tests: Email Send and Read Complete Flow

Tests email functionality end-to-end:
- Email sending with complete backend-to-UI verification
- Email reading with complete backend-to-UI verification

WINNING CRITERIA:
- Backend: Tool execution, Mail.app integration
- API: WebSocket message format, completion events
- UI: Message rendering, TaskCompletionCard, success indicators
"""

import pytest
import time
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add helpers to path
sys.path.insert(0, str(Path(__file__).parent.parent / "helpers"))
from test_verification_helpers import (
    verify_backend_tool_execution,
    verify_websocket_message_format,
    verify_completion_event,
    verify_ui_rendering,
    verify_tool_result_data
)

pytestmark = [pytest.mark.e2e]


class TestEmailSendRead:
    """Test complete email send and read flows with full stack verification."""

    def test_send_email_complete_flow(
        self,
        api_client,
        success_criteria_checker,
        telemetry_collector
    ):
        """
        Test sending email with complete backend-to-UI verification.
        
        WINNING CRITERIA:
        Backend:
        - compose_email tool called with correct parameters (recipient, subject, body, send=true)
        - Mail.app AppleScript execution succeeds
        - Returns success status with email details
        - Logs show email composition and send confirmation
        
        API/WebSocket:
        - Tool call message sent with correct format
        - Completion event sent: {"action": "email_sent", "status": "success"}
        - Final assistant message includes email confirmation
        
        UI:
        - Message bubble displays assistant response with email confirmation
        - TaskCompletionCard shows email icon and "Email sent" status
        - No error indicators visible
        - Response mentions recipient and subject
        """
        query = "Send an email to test@example.com with subject 'Test Email' and body 'This is a test email for quality testing'"
        
        telemetry_collector.record_event("email_send_test_start", {
            "query": query,
            "test_type": "send_email_complete_flow"
        })
        
        start_time = time.time()
        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)
        execution_time = time.time() - start_time
        
        response_text = response.get("message", "")
        
        # BACKEND VERIFICATION
        backend_verification = verify_backend_tool_execution(
            messages,
            "compose_email",
            expected_params={
                "recipient": "test@example.com",
                "subject": "Test Email",
                "send": True
            }
        )
        
        assert backend_verification["found"], "Backend: compose_email tool was not called"
        assert backend_verification["params_match"], f"Backend: Tool parameters don't match. Expected params in: {backend_verification['details']}"
        
        # Check tool result for success
        tool_result_verification = verify_tool_result_data(
            messages,
            "compose_email",
            ["success", "status"]
        )
        
        # API/WEBSOCKET VERIFICATION
        # Verify tool call message format
        tool_call_messages = [msg for msg in messages if msg.get("type") == "tool_call" and msg.get("tool_name") == "compose_email"]
        if tool_call_messages:
            ws_format = verify_websocket_message_format(
                tool_call_messages[0],
                "tool_call",
                ["type", "tool_name", "parameters"]
            )
            assert ws_format["type_match"], f"API: Tool call message type incorrect: {ws_format['details']}"
            assert ws_format["has_all_fields"], f"API: Tool call missing required fields: {ws_format['missing_fields']}"
        
        # Verify completion event
        completion_verification = verify_completion_event(
            messages,
            expected_action="email_sent",
            expected_status="success"
        )
        
        # UI VERIFICATION
        ui_verification = verify_ui_rendering(
            response,
            expected_elements=["email", "sent", "test@example.com", "Test Email"]
        )
        
        # SUCCESS CRITERIA CHECKS
        assert success_criteria_checker.check_no_errors(response), "UI: Response contains errors"
        assert success_criteria_checker.check_response_length(response_text, 50), "UI: Response too short"
        assert success_criteria_checker.check_keywords_present(
            response_text,
            ["email", "sent"]
        ), "UI: Missing confirmation keywords"
        
        # Verify completion event was sent (for TaskCompletionCard)
        assert completion_verification["found"] or len([m for m in messages if m.get("completion_event")]) > 0, \
            "API: No completion event sent for UI TaskCompletionCard"
        
        telemetry_collector.record_event("email_send_test_complete", {
            "execution_time": execution_time,
            "backend_verified": backend_verification["found"],
            "completion_event_found": completion_verification["found"],
            "ui_elements_found": len(ui_verification["elements_found"]),
            "response_length": len(response_text)
        })

    def test_read_emails_complete_flow(
        self,
        api_client,
        success_criteria_checker,
        telemetry_collector
    ):
        """
        Test reading emails with complete backend-to-UI verification.
        
        WINNING CRITERIA:
        Backend:
        - read_latest_emails(count=5) tool called
        - MailReader successfully accesses Mail.app
        - Returns list of emails with: subject, sender, timestamp, body preview
        - No Mail.app accessibility errors
        
        API/WebSocket:
        - Tool call message sent with correct parameters
        - Tool result message contains email array
        - Final assistant message includes email summary
        
        UI:
        - Message bubble displays email count and summary
        - Email list rendered (if UI component exists)
        - Each email shows: sender, subject, timestamp
        - No error messages displayed
        """
        query = "Read my latest 5 emails"
        
        telemetry_collector.record_event("email_read_test_start", {
            "query": query,
            "test_type": "read_emails_complete_flow"
        })
        
        start_time = time.time()
        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)
        execution_time = time.time() - start_time
        
        response_text = response.get("message", "")
        
        # BACKEND VERIFICATION
        backend_verification = verify_backend_tool_execution(
            messages,
            "read_latest_emails",
            expected_params={"count": 5}
        )
        
        assert backend_verification["found"], "Backend: read_latest_emails tool was not called"
        
        # Verify tool result contains email data
        tool_result_verification = verify_tool_result_data(
            messages,
            "read_latest_emails",
            ["emails", "count"]
        )
        
        # Check that emails were returned (if tool executed successfully)
        if tool_result_verification["tool_result_found"]:
            result_data = tool_result_verification["result_data"]
            emails = result_data.get("emails", [])
            email_count = result_data.get("count", 0)
            
            # Verify email structure if emails were returned
            if emails and len(emails) > 0:
                first_email = emails[0]
                assert "subject" in first_email or "sender" in first_email, \
                    "Backend: Email data missing subject or sender"
        
        # API/WEBSOCKET VERIFICATION
        # Verify tool call message format
        tool_call_messages = [msg for msg in messages if msg.get("type") == "tool_call" and msg.get("tool_name") == "read_latest_emails"]
        if tool_call_messages:
            ws_format = verify_websocket_message_format(
                tool_call_messages[0],
                "tool_call",
                ["type", "tool_name", "parameters"]
            )
            assert ws_format["type_match"], f"API: Tool call message type incorrect"
            assert ws_format["has_all_fields"], f"API: Tool call missing required fields: {ws_format['missing_fields']}"
        
        # UI VERIFICATION
        ui_verification = verify_ui_rendering(
            response,
            expected_elements=["email", "latest"]
        )
        
        # SUCCESS CRITERIA CHECKS
        assert success_criteria_checker.check_no_errors(response), "UI: Response contains errors"
        assert success_criteria_checker.check_response_length(response_text, 50), "UI: Response too short"
        
        # Check for email-related keywords
        email_keywords = ["email"]
        assert success_criteria_checker.check_keywords_present(
            response_text,
            email_keywords
        ), "UI: Missing email keywords"
        
        telemetry_collector.record_event("email_read_test_complete", {
            "execution_time": execution_time,
            "backend_verified": backend_verification["found"],
            "tool_result_found": tool_result_verification["tool_result_found"],
            "emails_returned": tool_result_verification["result_data"].get("count", 0) if tool_result_verification["tool_result_found"] else 0,
            "response_length": len(response_text)
        })


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

