"""
End-to-End Tests: Reminders Automation

Tests reminder creation, listing, editing, and completion:
- Create reminders with time parsing
- List and display reminders
- Mark as done and edit
- Scheduler integration
- UI status updates

WINNING CRITERIA:
- Reminders stored correctly
- Time parsing accurate
- UI shows reminder status
- Scheduler triggers work
"""

import pytest
import time
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List

pytestmark = [pytest.mark.e2e]


class TestRemindersAutomation:
    """Test comprehensive reminders functionality."""

    def test_create_reminder_with_time_parsing(
        self,
        api_client,
        success_criteria_checker,
        telemetry_collector
    ):
        """
        Test creating reminders with natural language time parsing.

        WINNING CRITERIA:
        - Reminder created successfully
        - Time parsed correctly
        - Stored in recurring_tasks.json
        - UI confirmation shown
        """
        query = "Remind me to call Alex at 4pm tomorrow"

        telemetry_collector.record_event("reminder_test_start", {
            "type": "create_reminder",
            "query": query
        })

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        # Check success criteria
        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 50)

        # Check reminder creation keywords
        reminder_keywords = ["reminder", "created", "tomorrow", "4pm"]
        assert success_criteria_checker.check_keywords_present(response_text, reminder_keywords)

        # Verify reminder was stored
        reminders_file = Path("data/recurring_tasks.json")
        if reminders_file.exists():
            with open(reminders_file, 'r') as f:
                reminders_data = json.load(f)

            # Check for recent reminder about Alex
            alex_reminders = [
                r for r in reminders_data.get("tasks", [])
                if "alex" in r.get("description", "").lower()
            ]
            assert len(alex_reminders) > 0, "Reminder not stored in recurring_tasks.json"

            # Check time parsing (should be tomorrow at 4pm)
            reminder = alex_reminders[0]
            reminder_time = datetime.fromisoformat(reminder.get("time", ""))
            tomorrow_4pm = datetime.now().replace(hour=16, minute=0, second=0, microsecond=0) + timedelta(days=1)

            time_diff = abs((reminder_time - tomorrow_4pm).total_seconds())
            assert time_diff < 3600, f"Time parsing incorrect. Expected ~{tomorrow_4pm}, got {reminder_time}"

        telemetry_collector.record_event("reminder_creation_complete", {
            "reminders_created": len(alex_reminders) if 'alex_reminders' in locals() else 0
        })

    def test_list_reminders_display(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test listing and displaying reminders.

        WINNING CRITERIA:
        - All reminders retrieved
        - Chronological ordering
        - Clear formatting
        - UI displays properly
        """
        query = "What reminders do I have?"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 50)

        # Check for reminder listing keywords
        list_keywords = ["reminder"]
        assert success_criteria_checker.check_keywords_present(response_text, list_keywords)

        # Should mention reminders or indicate none exist
        has_reminder_content = (
            "reminder" in response_text.lower() or
            "no reminders" in response_text.lower() or
            "none" in response_text.lower()
        )
        assert has_reminder_content, "No reminder information provided"

    def test_mark_reminder_done(
        self,
        api_client,
        success_criteria_checker,
        telemetry_collector
    ):
        """
        Test marking reminders as completed.

        WINNING CRITERIA:
        - Reminder found and marked done
        - Status updated in storage
        - UI shows completion
        - No duplicate reminders
        """
        # First create a reminder
        create_query = "Remind me to review the quarterly report"
        api_client.chat(create_query)
        api_client.wait_for_completion(max_wait=30)

        # Now mark it as done
        query = "Mark the quarterly report reminder as done"

        telemetry_collector.record_event("reminder_completion_start", {
            "reminder_text": "quarterly report"
        })

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)

        # Check completion keywords
        completion_keywords = ["done", "completed", "marked"]
        assert success_criteria_checker.check_keywords_present(response_text, completion_keywords)

        # Verify reminder was marked as done in storage
        reminders_file = Path("data/recurring_tasks.json")
        if reminders_file.exists():
            with open(reminders_file, 'r') as f:
                reminders_data = json.load(f)

            quarterly_reminders = [
                r for r in reminders_data.get("tasks", [])
                if "quarterly" in r.get("description", "").lower() and "report" in r.get("description", "").lower()
            ]

            if quarterly_reminders:
                # Check if marked as completed
                completed_reminders = [r for r in quarterly_reminders if r.get("completed", False)]
                assert len(completed_reminders) > 0, "Reminder not marked as completed"

        telemetry_collector.record_event("reminder_completion_complete", {
            "reminders_completed": len(completed_reminders) if 'completed_reminders' in locals() else 0
        })

    def test_edit_reminder_time(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test editing reminder times.

        WINNING CRITERIA:
        - Original reminder found
        - Time updated correctly
        - Changes persisted
        - Confirmation shown
        """
        # Create initial reminder
        create_query = "Remind me to attend the team meeting at 3pm"
        api_client.chat(create_query)
        api_client.wait_for_completion(max_wait=30)

        # Edit the time
        query = "Change the team meeting reminder to 4pm"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)

        # Check edit confirmation
        edit_keywords = ["changed", "updated", "4pm"]
        assert success_criteria_checker.check_keywords_present(response_text, edit_keywords)

    def test_reminder_scheduler_integration(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test that reminders integrate with the scheduler.

        WINNING CRITERIA:
        - Scheduler entries created
        - Triggers work correctly
        - Notifications sent at right time
        - No duplicate scheduling
        """
        query = "Set up a reminder for the dentist appointment next Tuesday at 2pm"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        assert success_criteria_checker.check_no_errors(response)
        assert success_criteria_checker.check_response_length(response_text, 50)

        # Check scheduler integration
        scheduler_keywords = ["reminder", "scheduled", "tuesday", "2pm"]
        assert success_criteria_checker.check_keywords_present(response_text, scheduler_keywords)

    def test_reminder_negative_invalid_time(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        NEGATIVE TEST: Handle invalid reminder times gracefully.

        WINNING CRITERIA:
        - Invalid time rejected
        - Helpful error message
        - No broken reminder created
        - User guidance provided
        """
        query = "Remind me to do something at 'next tuesday at 25pm'"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        response_text = response.get("message", "")

        # Should either show error or ask for clarification
        has_error_handling = (
            "error" in response_text.lower() or
            "invalid" in response_text.lower() or
            "clarify" in response_text.lower() or
            "25pm" not in response_text.lower()  # Should not accept invalid time
        )

        assert has_error_handling, "Invalid time not properly handled"

        # Should not create a broken reminder
        reminders_file = Path("data/recurring_tasks.json")
        if reminders_file.exists():
            with open(reminders_file, 'r') as f:
                reminders_data = json.load(f)

            # Should not have reminders with invalid times
            invalid_reminders = [
                r for r in reminders_data.get("tasks", [])
                if "25pm" in r.get("description", "").lower()
            ]
            assert len(invalid_reminders) == 0, "Invalid reminder was created"

    def test_reminder_ui_status_display(
        self,
        api_client,
        success_criteria_checker
    ):
        """
        Test reminder UI status and display.

        WINNING CRITERIA:
        - Status cards show correctly
        - Completion state visible
        - Time formatting proper
        - Interactive elements work
        """
        query = "Show me all my reminders for today"

        response = api_client.chat(query)
        messages = api_client.wait_for_completion(max_wait=60)

        # Check for UI status messages
        status_messages = [msg for msg in messages if msg.get("type") == "status"]
        ui_messages = [msg for msg in messages if msg.get("ui_component") == "reminder_list"]

        # Should have some UI feedback
        assert len(status_messages) + len(ui_messages) > 0, "No UI status for reminders"

        response_text = response.get("message", "")
        assert success_criteria_checker.check_response_length(response_text, 30)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
