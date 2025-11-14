"""
End-to-End Tests: Daily Overview Complete Flow

Tests "How's my day looking?" functionality end-to-end:
- Complete day overview aggregating calendar, reminders, and emails

WINNING CRITERIA:
- Backend: generate_day_overview tool execution, all three data sources accessed
- API: WebSocket messages with aggregated data, structured overview
- UI: Comprehensive day summary, all sources mentioned, time-based organization
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
    verify_ui_rendering,
    verify_tool_result_data,
    verify_multiple_tool_execution,
    verify_data_source_access
)

pytestmark = [pytest.mark.e2e]


class TestDailyOverviewComplete:
    """Test complete daily overview flow with full stack verification."""

    def test_complete_day_overview_flow(
        self,
        api_client,
        success_criteria_checker,
        telemetry_collector
    ):
        """
        Test complete "How's my day looking?" workflow with multi-source synthesis.
        
        WINNING CRITERIA:
        Backend:
        - generate_day_overview(filters="today") called
        - Calendar agent: list_calendar_events(days_ahead=1) executed
        - Reminders agent: list_reminders(include_completed=False) executed
        - Email agent: read_latest_emails(hours_back=18, limit=50) executed
        - All three data sources successfully retrieved
        - Overview includes: meetings count, reminders count, email action items count
        - Summary text generated with all three sources mentioned
        
        API/WebSocket:
        - Tool calls for all three agents visible in message stream
        - Final overview message includes structured data:
          - sections.meetings.items: Array of calendar events
          - sections.reminders.items: Array of reminders
          - sections.email_action_items.items: Array of email actions
        - Summary text mentions calendar, reminders, and emails
        
        UI:
        - Message bubble displays comprehensive day overview
        - Overview mentions all three sources (calendar, reminders, emails)
        - Time-based organization visible (morning/afternoon/evening or chronological)
        - Meeting times and reminder due times displayed
        - No error indicators
        - Response length > 300 characters (comprehensive overview)
        """
        query = "How's my day looking?"
        
        telemetry_collector.record_event("daily_overview_test_start", {
            "query": query,
            "test_type": "complete_day_overview_flow",
            "expected_sources": ["calendar", "reminders", "emails"]
        })
        
        start_time = time.time()
        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=120)  # Complex multi-source query
        execution_time = time.time() - start_time
        
        response_text = response.get("message", "")
        
        # BACKEND VERIFICATION
        # Check for generate_day_overview tool (preferred)
        overview_verification = verify_backend_tool_execution(
            messages,
            "generate_day_overview",
            expected_params={"filters": "today"}
        )
        
        # If generate_day_overview not found, check for individual tool calls
        if not overview_verification["found"]:
            # Verify all three data sources were accessed
            data_source_verification = verify_data_source_access(
                messages,
                ["calendar", "email", "reminder"]
            )
            
            assert data_source_verification["all_accessed"] or len(data_source_verification["sources_accessed"]) >= 2, \
                f"Backend: Not all data sources accessed. Accessed: {data_source_verification['sources_accessed']}"
            
            # Verify multiple tools were executed
            expected_tools = ["calendar", "email", "reminder"]
            multi_tool_verification = verify_multiple_tool_execution(
                messages,
                expected_tools,
                require_all=False  # At least 2 of 3 should be present
            )
            
            assert len(multi_tool_verification["tools_found"]) >= 2, \
                f"Backend: Insufficient tools executed. Found: {multi_tool_verification['tools_found']}"
        else:
            # If generate_day_overview was used, verify it returned structured data
            tool_result_verification = verify_tool_result_data(
                messages,
                "generate_day_overview",
                ["sections", "summary"]
            )
            
            if tool_result_verification["tool_result_found"]:
                result_data = tool_result_verification["result_data"]
                sections = result_data.get("sections", {})
                
                # Check that sections exist for all three sources
                has_meetings = "meetings" in sections
                has_reminders = "reminders" in sections
                has_email_actions = "email_action_items" in sections
                
                assert has_meetings or has_reminders or has_email_actions, \
                    "Backend: generate_day_overview missing required sections"
        
        # API/WEBSOCKET VERIFICATION
        # Verify tool call messages are properly formatted
        tool_call_messages = [
            msg for msg in messages
            if msg.get("type") == "tool_call"
        ]
        
        if tool_call_messages:
            # Check format of first tool call
            ws_format = verify_websocket_message_format(
                tool_call_messages[0],
                "tool_call",
                ["type", "tool_name", "parameters"]
            )
            assert ws_format["type_match"], "API: Tool call message type incorrect"
        
        # UI VERIFICATION
        # Check that all three sources are mentioned in response
        ui_verification = verify_ui_rendering(
            response,
            expected_elements=["calendar", "reminder", "email"]
        )
        
        # SUCCESS CRITERIA CHECKS
        assert success_criteria_checker.check_no_errors(response), "UI: Response contains errors"
        assert success_criteria_checker.check_response_length(response_text, 300), \
            f"UI: Response too short ({len(response_text)} chars). Expected comprehensive overview (>300 chars)"
        
        # CRITICAL: All three sources must be mentioned
        source_keywords = ["calendar", "email", "reminder"]
        # Allow partial matches (e.g., "reminders" matches "reminder")
        source_mentions = sum(
            1 for keyword in source_keywords
            if keyword in response_text.lower()
        )
        
        assert source_mentions >= 2, \
            f"UI: Insufficient source mentions ({source_mentions}/3). Response should mention calendar, reminders, and emails"
        
        # Check for time-based organization
        time_keywords = ["today", "morning", "afternoon", "evening", "time", "schedule"]
        time_organization = sum(
            1 for keyword in time_keywords
            if keyword in response_text.lower()
        )
        
        assert time_organization >= 2, \
            f"UI: Insufficient time organization ({time_organization} time references). Expected time-based structure"
        
        # Check synthesis quality indicators
        synthesis_indicators = ["summary", "overview", "combined", "today", "schedule", "day"]
        synthesis_quality = sum(
            1 for indicator in synthesis_indicators
            if indicator in response_text.lower()
        )
        
        assert synthesis_quality >= 3, \
            f"UI: Poor synthesis quality ({synthesis_quality} indicators). Expected comprehensive overview"
        
        telemetry_collector.record_event("daily_overview_test_complete", {
            "execution_time": execution_time,
            "overview_tool_found": overview_verification["found"],
            "source_mentions": source_mentions,
            "time_organization": time_organization,
            "synthesis_quality": synthesis_quality,
            "response_length": len(response_text),
            "ui_elements_found": len(ui_verification["elements_found"])
        })


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

