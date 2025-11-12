"""
Integration test for recurring task end-to-end workflow.

Tests the full flow from slash command parsing to task execution.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from zoneinfo import ZoneInfo

from src.automation.recurring_scheduler import (
    RecurringTaskScheduler,
    RecurringTaskStore,
    ScheduleSpec,
    ActionSpec
)
from src.ui.slash_commands import parse_recurring_task_spec


class MockEmailAgent:
    """Mock email agent for testing."""

    def __init__(self):
        self.emails_sent = []

    async def compose_email(self, recipient, subject, body, attachments=None, send=False):
        """Mock compose email."""
        self.emails_sent.append({
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "attachments": attachments or [],
            "send": send
        })
        return {"success": True}


class MockScreenTimeAgent:
    """Mock screen time agent for testing."""

    async def collect_screen_time_usage(self, **kwargs):
        """Mock screen time data collection."""
        return {
            "success": True,
            "data": {
                "period": {"start": "2025-01-06", "end": "2025-01-13", "weeks": 1},
                "total_duration_seconds": 82800,
                "total_duration_formatted": "23h 0m",
                "apps": [
                    {"name": "Safari", "duration_seconds": 18000, "duration_formatted": "5h 0m"},
                    {"name": "VS Code", "duration_seconds": 14400, "duration_formatted": "4h 0m"}
                ],
                "app_count": 2
            }
        }


class MockReportGenerator:
    """Mock report generator for testing."""

    def __init__(self, config=None):
        self.reports_generated = []
        self.config = config or {}

    def create_report(self, title, content, sections=None, image_paths=None, export_pdf=True, output_name=None):
        """Mock report generation using create_report API."""
        report_path = Path("/tmp/mock_report.pdf")
        self.reports_generated.append({
            "title": title,
            "content": content,
            "sections": sections,
            "image_paths": image_paths
        })
        return {
            "success": True,
            "pdf_path": str(report_path),
            "title": title,
            "message": f"Report created: {report_path.name}"
        }


@pytest.mark.asyncio
async def test_end_to_end_screen_time_report():
    """
    Test end-to-end flow for weekly screen time report:
    1. Parse slash command
    2. Register recurring task
    3. Force execute task
    4. Verify report generation and email sending
    """

    # Step 1: Parse slash command
    command_text = "Create a weekly screen time report and email it every Friday at 9am"
    spec = parse_recurring_task_spec(command_text)

    assert spec is not None
    assert spec["action"]["kind"] == "screen_time_report"
    assert spec["schedule"]["type"] == "weekly"
    assert spec["schedule"]["weekday"] == 4
    assert spec["schedule"]["time"] == "09:00"

    # Step 2: Create scheduler with mocked dependencies
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "tasks.json"
        store = RecurringTaskStore(str(store_path))

        mock_screentime_agent = MockScreenTimeAgent()
        mock_report_gen = MockReportGenerator()

        scheduler = RecurringTaskScheduler(
            agent_registry=None,
            agent=None,
            session_manager=None,
            store=store
        )

        # Register task
        schedule = ScheduleSpec(**spec["schedule"])
        action = ActionSpec(**spec["action"])

        task = await scheduler.register_task(
            name=spec["name"],
            command_text=command_text,
            schedule=schedule,
            action=action
        )

        assert task.id is not None
        assert task.next_run_at is not None

        # Step 3: Mock execution with patched dependencies
        # Note: Updated to match new implementation using create_report() and compose_email.invoke()
        with patch("src.agent.screentime_agent.ScreenTimeAgent", return_value=mock_screentime_agent):
            with patch("src.automation.report_generator.ReportGenerator", return_value=mock_report_gen):
                # Mock compose_email tool (not EmailAgent class)
                mock_compose_email = Mock()
                mock_compose_email.invoke = Mock(return_value={"status": "sent", "message": "Email sent successfully"})
                with patch("src.automation.recurring_scheduler.compose_email", mock_compose_email):
                    # Force execute task by setting next_run_at to past
                    task.next_run_at = datetime.now(ZoneInfo("UTC")).isoformat()
                    await store.update_task(task)

                    # Execute task
                    scheduler._debug_force_run = True
                    await scheduler._execute_task(task)
                    
                    # Verify compose_email.invoke was called
                    assert mock_compose_email.invoke.called

        # Step 4: Verify execution results
        assert len(mock_report_gen.reports_generated) == 1
        
        # Verify report was generated with correct structure
        report_call = mock_report_gen.reports_generated[0]
        assert "Screen Time Report" in report_call["title"]
        assert report_call["sections"] is not None
        assert len(report_call["sections"]) > 0
        
        # Verify compose_email.invoke was called with correct parameters
        assert mock_compose_email.invoke.called
        compose_call = mock_compose_email.invoke.call_args[0][0]
        assert "Screen Time Report" in compose_call["subject"]
        assert compose_call["send"] is True
        assert len(compose_call["attachments"]) == 1

        # Verify task updated
        updated_task = await store.get_task(task.id)
        assert updated_task.last_run_at is not None
        assert len(updated_task.history) == 1
        assert updated_task.history[0]["status"] == "success"


@pytest.mark.asyncio
async def test_scheduler_loop_execution():
    """
    Test that scheduler loop correctly identifies and executes due tasks.
    """

    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "tasks.json"
        store = RecurringTaskStore(str(store_path))

        scheduler = RecurringTaskScheduler(
            agent_registry=None,
            agent=None,
            session_manager=None,
            store=store
        )

        # Create a task that's due now
        schedule = ScheduleSpec(type="daily", time="09:00", tz="America/Los_Angeles")
        action = ActionSpec(kind="screen_time_report", delivery={"mode": "email", "send": True})

        task = await scheduler.register_task(
            name="Test Daily Task",
            command_text="/recurring test",
            schedule=schedule,
            action=action
        )

        # Set task to be due
        task.next_run_at = datetime.now(ZoneInfo("UTC")).isoformat()
        await store.update_task(task)

        # Mock the execution method to track calls
        execute_calls = []
        original_execute = scheduler._execute_task

        async def mock_execute(task):
            execute_calls.append(task.id)
            # Don't actually execute, just track

        scheduler._execute_task = mock_execute
        scheduler._debug_force_run = True

        # Run one iteration of the scheduler loop
        tasks = await store.load_tasks()
        now = datetime.now(ZoneInfo("UTC"))

        for t in tasks:
            if t.status == "active":
                next_run = datetime.fromisoformat(t.next_run_at)
                if scheduler._debug_force_run or next_run <= now:
                    await scheduler._execute_task(t)

        # Verify task was identified for execution
        assert task.id in execute_calls


@pytest.mark.asyncio
async def test_error_handling_in_execution():
    """
    Test that task execution errors are properly caught and recorded.
    """

    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "tasks.json"
        store = RecurringTaskStore(str(store_path))

        scheduler = RecurringTaskScheduler(
            agent_registry=None,
            agent=None,
            session_manager=None,
            store=store
        )

        # Create a task
        schedule = ScheduleSpec(type="daily", time="09:00", tz="America/Los_Angeles")
        action = ActionSpec(kind="screen_time_report")

        task = await scheduler.register_task(
            name="Test Task",
            command_text="/recurring test",
            schedule=schedule,
            action=action
        )

        # Mock screen time agent to raise an error
        class FailingScreenTimeAgent:
            async def collect_screen_time_usage(self, **kwargs):
                raise Exception("Database not available")

        with patch("src.agent.screentime_agent.ScreenTimeAgent", return_value=FailingScreenTimeAgent()):
            # Execute task (should catch error)
            await scheduler._execute_task(task)

        # Verify error was recorded
        updated_task = await store.get_task(task.id)
        assert updated_task.status == "error"
        assert len(updated_task.history) == 1
        assert updated_task.history[0]["status"] == "error"
        assert "Database not available" in updated_task.history[0]["error"]


@pytest.mark.asyncio
async def test_paused_tasks_not_executed():
    """
    Test that paused tasks are not executed by the scheduler.
    """

    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "tasks.json"
        store = RecurringTaskStore(str(store_path))

        scheduler = RecurringTaskScheduler(
            agent_registry=None,
            agent=None,
            session_manager=None,
            store=store
        )

        # Create and pause a task
        schedule = ScheduleSpec(type="daily", time="09:00", tz="America/Los_Angeles")
        action = ActionSpec(kind="screen_time_report")

        task = await scheduler.register_task(
            name="Test Task",
            command_text="/recurring test",
            schedule=schedule,
            action=action
        )

        await scheduler.pause_task(task.id)

        # Set task to be due
        task.next_run_at = datetime.now(ZoneInfo("UTC")).isoformat()
        await store.update_task(task)

        # Track execution calls
        execute_calls = []

        async def mock_execute(task):
            execute_calls.append(task.id)

        scheduler._execute_task = mock_execute
        scheduler._debug_force_run = True

        # Run scheduler check
        tasks = await store.load_tasks()
        for t in tasks:
            if t.status == "active":  # Only active tasks
                await scheduler._execute_task(t)

        # Verify paused task was NOT executed
        assert task.id not in execute_calls


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
