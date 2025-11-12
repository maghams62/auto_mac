"""
Unit tests for recurring task scheduler.
"""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.automation.recurring_scheduler import (
    RecurringTask,
    RecurringTaskStore,
    RecurringTaskScheduler,
    ScheduleSpec,
    ActionSpec
)


class TestScheduleSpec:
    """Test ScheduleSpec data class."""

    def test_weekly_schedule(self):
        """Test weekly schedule specification."""
        schedule = ScheduleSpec(
            type="weekly",
            weekday=4,  # Friday
            time="09:00",
            tz="America/Los_Angeles"
        )
        assert schedule.type == "weekly"
        assert schedule.weekday == 4
        assert schedule.time == "09:00"

    def test_daily_schedule(self):
        """Test daily schedule specification."""
        schedule = ScheduleSpec(
            type="daily",
            time="14:30",
            tz="UTC"
        )
        assert schedule.type == "daily"
        assert schedule.weekday is None


class TestRecurringTask:
    """Test RecurringTask data class."""

    def test_to_dict(self):
        """Test serialization to dictionary."""
        schedule = ScheduleSpec(type="weekly", weekday=4, time="09:00")
        action = ActionSpec(kind="screen_time_report", delivery={"mode": "email"})

        task = RecurringTask(
            id="test-123",
            name="Test Task",
            command_text="/recurring test",
            schedule=schedule,
            action=action
        )

        data = task.to_dict()
        assert data["id"] == "test-123"
        assert data["name"] == "Test Task"
        assert data["schedule"]["type"] == "weekly"
        assert data["action"]["kind"] == "screen_time_report"

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "id": "test-123",
            "name": "Test Task",
            "command_text": "/recurring test",
            "schedule": {"type": "weekly", "weekday": 4, "time": "09:00", "tz": "America/Los_Angeles"},
            "action": {"kind": "screen_time_report", "delivery": {}, "params": {}},
            "status": "active"
        }

        task = RecurringTask.from_dict(data)
        assert task.id == "test-123"
        assert task.schedule.type == "weekly"
        assert task.action.kind == "screen_time_report"


class TestRecurringTaskStore:
    """Test RecurringTaskStore persistence."""

    @pytest.fixture
    def temp_store(self):
        """Create a temporary store for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "tasks.json"
            yield RecurringTaskStore(str(store_path))

    @pytest.mark.asyncio
    async def test_save_and_load_tasks(self, temp_store):
        """Test saving and loading tasks."""
        schedule = ScheduleSpec(type="weekly", weekday=4, time="09:00")
        action = ActionSpec(kind="screen_time_report")

        task = RecurringTask(
            id="test-123",
            name="Test Task",
            command_text="/recurring test",
            schedule=schedule,
            action=action
        )

        await temp_store.add_task(task)

        # Load tasks
        tasks = await temp_store.load_tasks()
        assert len(tasks) == 1
        assert tasks[0].id == "test-123"
        assert tasks[0].name == "Test Task"

    @pytest.mark.asyncio
    async def test_update_task(self, temp_store):
        """Test updating a task."""
        schedule = ScheduleSpec(type="weekly", weekday=4, time="09:00")
        action = ActionSpec(kind="screen_time_report")

        task = RecurringTask(
            id="test-123",
            name="Test Task",
            command_text="/recurring test",
            schedule=schedule,
            action=action,
            status="active"
        )

        await temp_store.add_task(task)

        # Update task
        task.status = "paused"
        await temp_store.update_task(task)

        # Verify update
        loaded_task = await temp_store.get_task("test-123")
        assert loaded_task.status == "paused"

    @pytest.mark.asyncio
    async def test_remove_task(self, temp_store):
        """Test removing a task."""
        schedule = ScheduleSpec(type="weekly", weekday=4, time="09:00")
        action = ActionSpec(kind="screen_time_report")

        task = RecurringTask(
            id="test-123",
            name="Test Task",
            command_text="/recurring test",
            schedule=schedule,
            action=action
        )

        await temp_store.add_task(task)
        assert len(await temp_store.load_tasks()) == 1

        await temp_store.remove_task("test-123")
        assert len(await temp_store.load_tasks()) == 0


class TestRecurringTaskScheduler:
    """Test RecurringTaskScheduler."""

    @pytest.fixture
    def mock_scheduler(self):
        """Create a mock scheduler for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "tasks.json"
            store = RecurringTaskStore(str(store_path))
            scheduler = RecurringTaskScheduler(
                agent_registry=None,  # Mock
                agent=None,  # Mock
                session_manager=None,  # Mock
                store=store
            )
            yield scheduler

    def test_calculate_next_run_weekly(self, mock_scheduler):
        """Test calculating next run time for weekly schedule."""
        schedule = ScheduleSpec(
            type="weekly",
            weekday=4,  # Friday
            time="09:00",
            tz="America/Los_Angeles"
        )

        # Test from a Monday
        from_time = datetime(2025, 1, 6, 10, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))  # Monday
        next_run = mock_scheduler._calculate_next_run(schedule, from_time)

        # Should be next Friday at 9am
        assert next_run.weekday() == 4  # Friday
        assert next_run.hour == 9
        assert next_run.minute == 0

    def test_calculate_next_run_daily(self, mock_scheduler):
        """Test calculating next run time for daily schedule."""
        schedule = ScheduleSpec(
            type="daily",
            time="14:30",
            tz="America/Los_Angeles"
        )

        from_time = datetime(2025, 1, 6, 10, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        next_run = mock_scheduler._calculate_next_run(schedule, from_time)

        # Should be today at 14:30
        assert next_run.date() == from_time.date()
        assert next_run.hour == 14
        assert next_run.minute == 30

    def test_calculate_next_run_daily_after_time(self, mock_scheduler):
        """Test calculating next run when current time is after target time."""
        schedule = ScheduleSpec(
            type="daily",
            time="09:00",
            tz="America/Los_Angeles"
        )

        # Current time is 10am (after 9am target)
        from_time = datetime(2025, 1, 6, 10, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        next_run = mock_scheduler._calculate_next_run(schedule, from_time)

        # Should be tomorrow at 9am
        assert next_run.date() == (from_time + timedelta(days=1)).date()
        assert next_run.hour == 9

    @pytest.mark.asyncio
    async def test_register_task(self, mock_scheduler):
        """Test registering a new task."""
        schedule = ScheduleSpec(type="weekly", weekday=4, time="09:00")
        action = ActionSpec(kind="screen_time_report")

        task = await mock_scheduler.register_task(
            name="Test Task",
            command_text="/recurring test",
            schedule=schedule,
            action=action
        )

        assert task.id is not None
        assert task.name == "Test Task"
        assert task.next_run_at is not None

    @pytest.mark.asyncio
    async def test_pause_and_resume_task(self, mock_scheduler):
        """Test pausing and resuming a task."""
        schedule = ScheduleSpec(type="weekly", weekday=4, time="09:00")
        action = ActionSpec(kind="screen_time_report")

        task = await mock_scheduler.register_task(
            name="Test Task",
            command_text="/recurring test",
            schedule=schedule,
            action=action
        )

        # Pause task
        await mock_scheduler.pause_task(task.id)
        loaded_task = await mock_scheduler.store.get_task(task.id)
        assert loaded_task.status == "paused"

        # Resume task
        await mock_scheduler.resume_task(task.id)
        loaded_task = await mock_scheduler.store.get_task(task.id)
        assert loaded_task.status == "active"


class TestSlashCommandParsing:
    """Test parsing recurring task specifications from slash commands."""

    def test_parse_weekly_screen_time(self):
        """Test parsing weekly screen time report command."""
        from src.ui.slash_commands import parse_recurring_task_spec

        spec = parse_recurring_task_spec(
            "Create a weekly screen time report and email it every Friday"
        )

        assert spec is not None
        assert spec["action"]["kind"] == "screen_time_report"
        assert spec["schedule"]["type"] == "weekly"
        assert spec["schedule"]["weekday"] == 4  # Friday
        assert spec["action"]["delivery"]["mode"] == "email"

    def test_parse_daily_summary(self):
        """Test parsing daily summary command."""
        from src.ui.slash_commands import parse_recurring_task_spec

        spec = parse_recurring_task_spec(
            "Generate a daily summary every day at 9am"
        )

        assert spec is not None
        assert spec["schedule"]["type"] == "daily"
        assert spec["schedule"]["time"] == "09:00"

    def test_parse_custom_time(self):
        """Test parsing command with custom time."""
        from src.ui.slash_commands import parse_recurring_task_spec

        spec = parse_recurring_task_spec(
            "Send me a weekly report every Monday at 2:30pm"
        )

        assert spec is not None
        assert spec["schedule"]["type"] == "weekly"
        assert spec["schedule"]["weekday"] == 0  # Monday
        assert spec["schedule"]["time"] == "14:30"

    def test_parse_invalid_command(self):
        """Test parsing invalid command returns None."""
        from src.ui.slash_commands import parse_recurring_task_spec

        spec = parse_recurring_task_spec("This is not a valid recurring command")
        assert spec is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
