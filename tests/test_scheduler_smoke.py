"""
Smoke test for _execute_screen_time_report to verify fixes work.

This test verifies that the fixed implementation:
1. Passes config to ReportGenerator
2. Uses create_report() instead of generate_screen_time_report()
3. Uses compose_email.invoke() instead of await EmailAgent.compose_email()
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from zoneinfo import ZoneInfo

from src.automation.recurring_scheduler import (
    RecurringTaskScheduler,
    RecurringTaskStore,
    ScheduleSpec,
    ActionSpec,
    RecurringTask
)


@pytest.mark.asyncio
async def test_execute_screen_time_report_smoke():
    """
    Smoke test for _execute_screen_time_report with fixed implementation.
    
    Verifies:
    - Config is passed to ReportGenerator
    - create_report() is called (not generate_screen_time_report)
    - compose_email.invoke() is used (not await EmailAgent.compose_email)
    """
    # Create test config
    test_config = {
        "openai": {"api_key": "test-key"},
        "email": {"default_recipient": "test@example.com"}
    }
    
    # Create mock agent with config
    mock_agent = Mock()
    mock_agent.config = test_config
    
    # Create scheduler
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "tasks.json"
        store = RecurringTaskStore(str(store_path))
        
        scheduler = RecurringTaskScheduler(
            agent_registry=None,
            agent=mock_agent,
            session_manager=None,
            store=store
        )
        
        # Verify config was stored
        assert scheduler.config == test_config
        
        # Create a test task
        task = RecurringTask(
            id="test-task-1",
            name="Test Screen Time Report",
            command_text="test command",
            schedule=ScheduleSpec(type="weekly", weekday=4, time="09:00"),
            action=ActionSpec(
                kind="screen_time_report",
                delivery={"mode": "email", "recipient": "test@example.com", "send": True}
            )
        )
        
        # Mock screen time data
        mock_usage_data = {
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
        
        # Mock report result
        mock_report_result = {
            "success": True,
            "pdf_path": "/tmp/test_report.pdf",
            "title": "Screen Time Report - 2025-01-13",
            "message": "Report created: test_report.pdf"
        }
        
        # Mock email result
        mock_email_result = {
            "status": "sent",
            "message": "Email sent successfully"
        }
        
        # Mock all dependencies
        mock_screentime_agent = Mock()
        mock_screentime_agent.collect_screen_time_usage = AsyncMock(return_value=mock_usage_data)
        
        mock_report_gen = Mock()
        mock_report_gen.create_report = Mock(return_value=mock_report_result)
        
        mock_compose_email = Mock()
        mock_compose_email.invoke = Mock(return_value=mock_email_result)
        
        # Patch dependencies
        with patch("src.automation.recurring_scheduler.ScreenTimeAgent", return_value=mock_screentime_agent):
            with patch("src.automation.recurring_scheduler.ReportGenerator", return_value=mock_report_gen):
                with patch("src.automation.recurring_scheduler.compose_email", mock_compose_email):
                    # Execute the screen time report
                    await scheduler._execute_screen_time_report(task)
        
        # Verify ReportGenerator was initialized with config
        assert mock_report_gen.create_report.called
        call_args = mock_report_gen.create_report.call_args
        assert call_args is not None
        
        # Verify create_report() was called (not generate_screen_time_report)
        assert "title" in call_args.kwargs
        assert "sections" in call_args.kwargs
        assert "Screen Time Report" in call_args.kwargs["title"]
        
        # Verify compose_email.invoke() was called (not await EmailAgent.compose_email)
        assert mock_compose_email.invoke.called
        email_call = mock_compose_email.invoke.call_args[0][0]
        assert "subject" in email_call
        assert "body" in email_call
        assert "attachments" in email_call
        assert "send" in email_call
        assert email_call["send"] is True
        assert len(email_call["attachments"]) == 1
        assert email_call["attachments"][0] == "/tmp/test_report.pdf"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

