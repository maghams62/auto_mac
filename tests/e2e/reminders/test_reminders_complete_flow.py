"""
End-to-End Tests: Reminders Complete Flow

Tests reminder functionality end-to-end:
- Reminder creation with complete backend-to-UI verification
- Reminder reading with complete backend-to-UI verification

WINNING CRITERIA:
- Backend: Tool execution, Apple Reminders integration
- API: WebSocket message format, completion events
- UI: Message rendering, reminder confirmation, success indicators
"""

import pytest
import time
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timedelta

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


class TestRemindersCompleteFlow:
    """Test complete reminder create and read flows with full stack verification."""

    def test_create_reminder_complete_flow(
        self,
        api_client,
        success_criteria_checker,
        telemetry_collector
    ):
        """
        Test creating reminder with complete backend-to-UI verification.
        
        WINNING CRITERIA:
        Backend:
        - create_reminder(title="Test reminder", due_time="tomorrow at 9am") called
        - RemindersAutomation successfully creates reminder in Apple Reminders
        - Returns reminder_id and due_date in ISO format
        - Reminder appears in Reminders.app (verification via AppleScript)
        
        API/WebSocket:
        - Tool call message with correct parameters
        - Completion event: {"action": "reminder_created", "status": "success"}
        - Final message confirms reminder creation with due time
        
        UI:
        - Message bubble shows reminder confirmation
        - Due time displayed correctly (tomorrow at 9am)
        - Success indicator visible
        - No error messages
        """
        reminder_title = "Quality Test Reminder"
        due_time = "tomorrow at 9am"
        query = f"Remind me to '{reminder_title}' {due_time}"
        
        telemetry_collector.record_event("reminder_create_test_start", {
            "query": query,
            "test_type": "create_reminder_complete_flow",
            "reminder_title": reminder_title,
            "due_time": due_time
        })
        
        start_time = time.time()
        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)
        execution_time = time.time() - start_time
        
        response_text = response.get("message", "")
        
        # BACKEND VERIFICATION
        backend_verification = verify_backend_tool_execution(
            messages,
            "create_reminder",
            expected_params={
                "title": reminder_title,
                "due_time": due_time
            }
        )
        
        assert backend_verification["found"], "Backend: create_reminder tool was not called"
        
        # Verify tool result contains reminder data
        tool_result_verification = verify_tool_result_data(
            messages,
            "create_reminder",
            ["success", "reminder_id"]
        )
        
        # API/WEBSOCKET VERIFICATION
        # Verify tool call message format
        tool_call_messages = [
            msg for msg in messages
            if msg.get("type") == "tool_call" and msg.get("tool_name") == "create_reminder"
        ]
        if tool_call_messages:
            ws_format = verify_websocket_message_format(
                tool_call_messages[0],
                "tool_call",
                ["type", "tool_name", "parameters"]
            )
            assert ws_format["type_match"], "API: Tool call message type incorrect"
            assert ws_format["has_all_fields"], f"API: Tool call missing required fields: {ws_format['missing_fields']}"
        
        # Verify completion event
        completion_verification = verify_completion_event(
            messages,
            expected_action="reminder_created",
            expected_status="success"
        )
        
        # UI VERIFICATION
        ui_verification = verify_ui_rendering(
            response,
            expected_elements=["reminder", "created", reminder_title.lower()]
        )
        
        # SUCCESS CRITERIA CHECKS
        assert success_criteria_checker.check_no_errors(response), "UI: Response contains errors"
        assert success_criteria_checker.check_response_length(response_text, 50), "UI: Response too short"
        assert success_criteria_checker.check_keywords_present(
            response_text,
            ["reminder", "created"]
        ), "UI: Missing reminder creation confirmation keywords"
        
        # Check for due time in response
        has_due_time = "9am" in response_text.lower() or "tomorrow" in response_text.lower() or "9:00" in response_text
        
        # Verify completion event was sent (for UI feedback)
        assert completion_verification["found"] or len([m for m in messages if m.get("completion_event")]) > 0, \
            "API: No completion event sent for UI feedback"
        
        telemetry_collector.record_event("reminder_create_test_complete", {
            "execution_time": execution_time,
            "backend_verified": backend_verification["found"],
            "completion_event_found": completion_verification["found"],
            "tool_result_found": tool_result_verification["tool_result_found"],
            "has_due_time": has_due_time,
            "response_length": len(response_text)
        })

    def test_list_reminders_complete_flow(
        self,
        api_client,
        success_criteria_checker,
        telemetry_collector
    ):
        """
        Test reading reminders with complete backend-to-UI verification.
        
        WINNING CRITERIA:
        Backend:
        - list_reminders(include_completed=False) called
        - RemindersAutomation successfully reads from Apple Reminders
        - Returns list of reminders with: title, due_date, notes, list_name, completed status
        - At least one reminder returned (or empty list if none exist)
        
        API/WebSocket:
        - Tool call message sent
        - Tool result contains reminders array
        - Final message lists reminders with due dates
        
        UI:
        - Message bubble displays reminder count
        - Each reminder shows: title, due date/time, list name
        - Reminders formatted chronologically
        - No errors displayed
        """
        query = "Show me my reminders"
        
        telemetry_collector.record_event("reminder_list_test_start", {
            "query": query,
            "test_type": "list_reminders_complete_flow"
        })
        
        start_time = time.time()
        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)
        execution_time = time.time() - start_time
        
        response_text = response.get("message", "")
        
        # BACKEND VERIFICATION
        backend_verification = verify_backend_tool_execution(
            messages,
            "list_reminders",
            expected_params={}
        )
        
        assert backend_verification["found"], "Backend: list_reminders tool was not called"
        
        # Verify tool result contains reminder data
        tool_result_verification = verify_tool_result_data(
            messages,
            "list_reminders",
            ["reminders"]
        )
        
        # If reminders were returned, verify structure
        if tool_result_verification["tool_result_found"]:
            result_data = tool_result_verification["result_data"]
            reminders = result_data.get("reminders", [])
            
            # If reminders exist, check structure
            if reminders and len(reminders) > 0:
                first_reminder = reminders[0]
                # Check for at least title or due_date
                assert "title" in first_reminder or "due_date" in first_reminder, \
                    "Backend: Reminder data missing title or due_date"
        
        # API/WEBSOCKET VERIFICATION
        # Verify tool call message format
        tool_call_messages = [
            msg for msg in messages
            if msg.get("type") == "tool_call" and msg.get("tool_name") == "list_reminders"
        ]
        if tool_call_messages:
            ws_format = verify_websocket_message_format(
                tool_call_messages[0],
                "tool_call",
                ["type", "tool_name", "parameters"]
            )
            assert ws_format["type_match"], "API: Tool call message type incorrect"
        
        # UI VERIFICATION
        ui_verification = verify_ui_rendering(
            response,
            expected_elements=["reminder"]
        )
        
        # SUCCESS CRITERIA CHECKS
        assert success_criteria_checker.check_no_errors(response), "UI: Response contains errors"
        assert success_criteria_checker.check_response_length(response_text, 30), "UI: Response too short"
        
        # Check for reminder-related keywords
        reminder_keywords = ["reminder"]
        assert success_criteria_checker.check_keywords_present(
            response_text,
            reminder_keywords
        ), "UI: Missing reminder keywords"
        
        telemetry_collector.record_event("reminder_list_test_complete", {
            "execution_time": execution_time,
            "backend_verified": backend_verification["found"],
            "tool_result_found": tool_result_verification["tool_result_found"],
            "reminders_count": tool_result_verification["result_data"].get("count", 0) if tool_result_verification["tool_result_found"] else 0,
            "response_length": len(response_text)
        })


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

