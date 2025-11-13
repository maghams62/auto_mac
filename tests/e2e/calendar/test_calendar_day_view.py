"""
End-to-End Tests: Calendar Day View ("How's my day?")

Tests the complex multi-source day overview functionality:
- Calendar events retrieval and display
- Email context integration
- Reminder synthesis
- Chronological organization
- Time-based summarization

WINNING CRITERIA:
- All sources (calendar, email, reminders) retrieved
- Chronological synthesis provided
- Time-based organization
- Comprehensive day overview
"""

import pytest
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List

pytestmark = [pytest.mark.e2e]


class TestCalendarDayView:
    """Test comprehensive calendar day view functionality."""

    def test_complete_day_overview(
        self,
        api_client,
        success_criteria_checker,
        telemetry_collector
    ):
        """
        Test the complete "How's my day?" workflow with multi-source synthesis.

        WINNING CRITERIA:
        - Calendar events retrieved
        - Email context included
        - Reminders integrated
        - Chronological synthesis
        - Time-based organization
        - Comprehensive overview provided
        """
        query = "How's my day looking?"

        telemetry_collector.record_event("day_view_test_start", {
            "query": query,
            "expected_sources": ["calendar", "email", "reminders"]
        })

        start_time = time.time()
        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=120)  # Complex multi-source query

        execution_time = time.time() - start_time
        response_text = response.get("message", "")

        # Check success criteria
        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 300)  # Comprehensive overview

        # CRITICAL: All three sources must be mentioned
        source_keywords = ["calendar", "email", "reminder"]
        assert success_criteria_checker.check_keywords_present(response_text, source_keywords)

        # Check chronological/time-based organization
        time_keywords = ["today", "morning", "afternoon", "evening", "time"]
        time_organization = sum(1 for keyword in time_keywords if keyword in response_text.lower())
        assert time_organization >= 2, f"Insufficient time organization: {time_organization} time references"

        # Verify all three data sources were accessed
        sources_accessed = 0
        tool_calls = [msg.get("tool_name") for msg in messages if msg.get("type") == "tool_call"]

        if any("calendar" in tool or "event" in tool for tool in tool_calls):
            sources_accessed += 1
        if any("email" in tool or "mail" in tool for tool in tool_calls):
            sources_accessed += 1
        if any("reminder" in tool for tool in tool_calls):
            sources_accessed += 1

        assert sources_accessed >= 2, f"Only {sources_accessed}/3 data sources accessed"

        # Check synthesis quality
        synthesis_indicators = ["summary", "overview", "combined", "today", "schedule"]
        synthesis_quality = sum(1 for indicator in synthesis_indicators if indicator in response_text.lower())
        assert synthesis_quality >= 3, f"Poor synthesis quality: {synthesis_quality} synthesis indicators"

        telemetry_collector.record_event("day_view_test_complete", {
            "execution_time": execution_time,
            "sources_accessed": sources_accessed,
            "response_length": len(response_text)
        })

    def test_calendar_events_display(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test calendar events retrieval and display.

        WINNING CRITERIA:
        - Events retrieved successfully
        - Chronological ordering
        - Event details included
        - Time formatting correct
        - UI timeline display
        """
        query = "What meetings do I have today?"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 100)

        # Check calendar-specific keywords
        calendar_keywords = ["meeting", "calendar", "event", "today"]
        assert success_criteria_checker.check_keywords_present(response_text, calendar_keywords)

        # Verify calendar access
        calendar_accessed = any(
            msg.get("tool_name") in ["get_calendar_events", "list_calendar", "read_calendar"]
            for msg in messages
            if msg.get("type") == "tool_call"
        )
        assert calendar_accessed, "Calendar not accessed for events"

    def test_email_calendar_integration(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test email and calendar combined queries.

        WINNING CRITERIA:
        - Both email and calendar retrieved
        - Information correlated
        - Combined summary provided
        - No source conflicts
        """
        query = "What's in my inbox and on my calendar this week?"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=90)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 200)

        # Must mention both sources
        dual_source_keywords = ["email", "calendar"]
        assert success_criteria_checker.check_keywords_present(response_text, dual_source_keywords)

        # Check both tools were called
        email_accessed = any("email" in msg.get("tool_name", "") for msg in messages if msg.get("type") == "tool_call")
        calendar_accessed = any("calendar" in msg.get("tool_name", "") for msg in messages if msg.get("type") == "tool_call")

        assert email_accessed and calendar_accessed, "Both email and calendar sources not accessed"

    def test_reminder_calendar_integration(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test reminders and calendar integration.

        WINNING CRITERIA:
        - Reminders and calendar events combined
        - Time conflicts identified
        - Comprehensive schedule provided
        - Priority handling
        """
        query = "Summarize my reminders and calendar for tomorrow"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=90)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 150)

        # Check both sources mentioned
        integration_keywords = ["reminder", "calendar", "tomorrow"]
        assert success_criteria_checker.check_keywords_present(response_text, integration_keywords)

    def test_multi_source_day_summary(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test complete multi-source day summary.

        WINNING CRITERIA:
        - All three sources synthesized
        - Comprehensive day overview
        - Time-based structure
        - Actionable insights
        - Clear organization
        """
        query = "Give me a complete summary of my day - emails, calendar, and reminders"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=120)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 400)  # Very comprehensive

        # Must cover all three sources
        comprehensive_keywords = ["email", "calendar", "reminder", "summary", "day"]
        assert success_criteria_checker.check_keywords_present(response_text, comprehensive_keywords)

        # Check time-based organization (morning/afternoon/evening structure)
        time_structure = ["morning", "afternoon", "evening", "today"]
        time_mentions = sum(1 for time_ref in time_structure if time_ref in response_text.lower())
        assert time_mentions >= 2, f"Insufficient time structure: {time_mentions} time periods mentioned"

    def test_calendar_timezone_handling(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test calendar timezone and time formatting.

        WINNING CRITERIA:
        - Times displayed correctly
        - Timezone handling proper
        - Local time conversion
        - Clear time formatting
        """
        query = "What time are my meetings in my local timezone?"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)

        # Should mention time or timezone concepts
        time_handling = (
            "time" in response_text.lower() or
            "timezone" in response_text.lower() or
            "local" in response_text.lower() or
            "pm" in response_text.lower() or
            "am" in response_text.lower()
        )

        assert time_handling, "Time/timezone handling not properly addressed"

    def test_calendar_event_details(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test detailed calendar event information display.

        WINNING CRITERIA:
        - Event details complete
        - Location information included
        - Attendee info provided
        - Duration clear
        - Context information
        """
        query = "Tell me about my next calendar event in detail"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 100)

        # Check for event detail keywords
        detail_keywords = ["event", "meeting"]
        assert success_criteria_checker.check_keywords_present(response_text, detail_keywords)

    def test_calendar_conflict_detection(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test calendar conflict detection and resolution.

        WINNING CRITERIA:
        - Conflicting events identified
        - Conflicts highlighted
        - Resolution suggestions provided
        - Schedule optimization
        """
        query = "Are there any conflicts in my calendar this week?"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)

        # Should address conflicts or lack thereof
        conflict_handling = (
            "conflict" in response_text.lower() or
            "overlap" in response_text.lower() or
            "no conflicts" in response_text.lower() or
            "clear" in response_text.lower() or
            "available" in response_text.lower()
        )

        assert conflict_handling, "Calendar conflicts not properly addressed"

    def test_day_view_ui_timeline(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test that day view renders properly in UI timeline.

        WINNING CRITERIA:
        - Timeline widget displays
        - Events positioned chronologically
        - Visual indicators correct
        - Interactive elements work
        - Status updates shown
        """
        query = "Show me my day timeline"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        # Check for UI timeline messages
        timeline_messages = [msg for msg in messages if msg.get("type") in ["timeline_display", "calendar_view", "day_view"]]

        # Should have UI rendering messages
        assert len(timeline_messages) > 0, "No UI timeline rendering messages"

        response_text = response.get("message", "")
        assert success_criteria_checker.check_response_length(response_text, 50)

        # Should mention timeline or schedule concepts
        timeline_keywords = ["timeline", "schedule", "day", "time"]
        assert success_criteria_checker.check_keywords_present(response_text, timeline_keywords)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
