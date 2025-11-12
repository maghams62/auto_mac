# Recurring Tasks Feature

## Overview

The Recurring Tasks feature allows users to schedule automated workflows that run on a regular basis (daily, weekly, or monthly). Tasks are persisted locally and survive server restarts.

## Quick Start

### Creating a Recurring Task

Use the `/recurring` slash command to schedule a task:

```
/recurring Create a weekly screen time report and email it every Friday at 9am
```

Other examples:
```
/recurring Generate a daily summary every day at 2pm
/schedule Send me a weekly report every Monday
```

### Managing Tasks

#### List All Tasks
```bash
curl http://localhost:8000/api/recurring/tasks
```

#### Pause a Task
```bash
curl -X POST http://localhost:8000/api/recurring/tasks/{task_id}/pause
```

#### Resume a Task
```bash
curl -X POST http://localhost:8000/api/recurring/tasks/{task_id}/resume
```

#### Delete a Task
```bash
curl -X DELETE http://localhost:8000/api/recurring/tasks/{task_id}
```

## Architecture

### Components

1. **RecurringTaskScheduler** ([src/automation/recurring_scheduler.py](../../src/automation/recurring_scheduler.py))
   - Main scheduler that runs as a background task
   - Checks every 60 seconds for due tasks
   - Executes tasks with concurrency limits (max 3 concurrent)

2. **RecurringTaskStore** ([src/automation/recurring_scheduler.py](../../src/automation/recurring_scheduler.py))
   - JSON-backed persistent storage
   - Stores tasks in `data/recurring_tasks.json`
   - Atomic writes with temp files to prevent corruption

3. **ScreenTimeCollector** ([src/automation/screen_time_usage.py](../../src/automation/screen_time_usage.py))
   - Collects screen time data from macOS Knowledge database
   - Provides weekly, daily, and category breakdowns
   - Falls back to mock data if database is unavailable

4. **Slash Command Parser** ([src/ui/slash_commands.py](../../src/ui/slash_commands.py))
   - Parses natural language recurring task specifications
   - Extracts schedule type, timing, and delivery options
   - Function: `parse_recurring_task_spec()`

### Data Model

#### RecurringTask

```python
{
    "id": "uuid",
    "name": "Weekly Screen Time Report",
    "command_text": "/recurring ...",
    "schedule": {
        "type": "weekly",        # "daily", "weekly", or "monthly"
        "weekday": 4,            # 0=Monday, 6=Sunday (for weekly)
        "day": None,             # Day of month (for monthly)
        "time": "09:00",         # Time in HH:MM format
        "tz": "America/Los_Angeles"
    },
    "action": {
        "kind": "screen_time_report",  # Action type
        "delivery": {
            "mode": "email",
            "send": true,
            "recipient": "default"
        },
        "params": {}
    },
    "next_run_at": "2025-01-17T09:00:00-08:00",
    "last_run_at": "2025-01-10T09:00:00-08:00",
    "status": "active",  # "active", "paused", or "error"
    "history": [
        {
            "timestamp": "2025-01-10T09:00:00Z",
            "status": "success",
            "duration_ms": 1234
        }
    ],
    "created_at": "2025-01-03T10:00:00Z"
}
```

### Execution Pipeline

For `screen_time_report` action kind:

1. **Collect Data**: Call `ScreenTimeAgent.collect_screen_time_usage()`
2. **Generate Report**: Use `ReportGenerator.generate_screen_time_report()` to create PDF
3. **Deliver**: Send via `EmailAgent.compose_email()` with attachment

## Supported Actions

### Current

- **screen_time_report**: Weekly screen time usage report with PDF attachment

### Planned

- **file_summary_report**: Summary of recently modified files
- **general_report**: Custom reports based on local data
- **daily_summary**: Daily activity summary

## Natural Language Parsing

The parser extracts:

### Schedule Type
- **Weekly**: "weekly", "every week", day names ("Monday", "Friday", etc.)
- **Daily**: "daily", "every day"

### Timing
- **Time patterns**:
  - "at 9am", "at 2:30pm"
  - "9am", "14:30"
  - Defaults to 9:00am if not specified

### Day of Week (for weekly)
- Monday (0), Tuesday (1), ..., Sunday (6)
- Defaults to Friday if weekly but no day specified

### Delivery
- "email", "send" → Sets delivery mode to email with send=true

## Configuration

### Timezone

Default timezone is `America/Los_Angeles`. To customize:

```python
# In parse_recurring_task_spec() or when creating ScheduleSpec
schedule = ScheduleSpec(
    type="weekly",
    weekday=4,
    time="09:00",
    tz="America/New_York"  # Custom timezone
)
```

### Concurrency

Maximum concurrent task executions is controlled by:

```python
self._execution_lock = asyncio.Semaphore(3)  # Max 3 concurrent
```

Modify in `RecurringTaskScheduler.__init__()` to change limit.

### Check Interval

Scheduler checks for due tasks every 60 seconds:

```python
await asyncio.sleep(60)  # In _scheduler_loop()
```

## Testing

### Unit Tests

Run unit tests for individual components:

```bash
pytest tests/test_recurring_scheduler.py -v
```

Tests cover:
- Schedule calculation (weekly, daily, monthly)
- Task persistence (save, load, update, delete)
- Slash command parsing
- Error handling

### Integration Tests

Run end-to-end integration tests:

```bash
pytest tests/test_recurring_integration.py -v
```

Tests cover:
- Full flow from slash command to execution
- Email sending with attachments
- Error handling and recording
- Paused task exclusion

### Manual Testing

1. **Start the server**:
   ```bash
   python api_server.py
   ```

2. **Register a task via WebSocket**:
   ```
   /recurring Create a weekly screen time report and email it every Friday
   ```

3. **Check data file**:
   ```bash
   cat data/recurring_tasks.json
   ```

4. **Force execution** (for testing):
   - Set `_debug_force_run = True` in scheduler
   - Or manually set `next_run_at` to a past time

5. **Verify logs**:
   ```bash
   tail -f data/logs/api_server.log | grep recurring
   ```

## API Endpoints

### GET /api/recurring/tasks

Get all recurring tasks.

**Response**:
```json
{
    "success": true,
    "tasks": [...]
}
```

### POST /api/recurring/tasks

Create a new recurring task.

**Request Body**:
```json
{
    "name": "Weekly Screen Time Report",
    "command_text": "/recurring ...",
    "schedule": {
        "type": "weekly",
        "weekday": 4,
        "time": "09:00",
        "tz": "America/Los_Angeles"
    },
    "action": {
        "kind": "screen_time_report",
        "delivery": {"mode": "email", "send": true, "recipient": "default"},
        "params": {}
    }
}
```

**Response**:
```json
{
    "success": true,
    "task": {...},
    "message": "Recurring task 'Weekly Screen Time Report' created successfully. Next run: 2025-01-17T09:00:00-08:00"
}
```

### DELETE /api/recurring/tasks/{task_id}

Delete a recurring task.

### POST /api/recurring/tasks/{task_id}/pause

Pause a recurring task.

### POST /api/recurring/tasks/{task_id}/resume

Resume a paused recurring task.

## Troubleshooting

### Task Not Executing

1. **Check task status**:
   ```bash
   curl http://localhost:8000/api/recurring/tasks | jq '.tasks[] | {id, name, status, next_run_at}'
   ```

2. **Check scheduler is running**:
   ```bash
   curl http://localhost:8000/health  # Look for scheduler status
   ```

3. **Check logs**:
   ```bash
   grep "Executing recurring task" data/logs/api_server.log
   ```

### Screen Time Data Not Available

The ScreenTimeCollector falls back to mock data if the macOS Knowledge database is unavailable. To enable real data:

1. Ensure Screen Time is enabled in System Preferences
2. Grant appropriate permissions to the application
3. Check database path: `~/Library/Application Support/Knowledge/knowledgeC.db`

### Email Not Sending

1. **Verify email configuration** in `config.yaml`:
   ```yaml
   email:
     default_account: "your-email@example.com"
   ```

2. **Check EmailAgent logs** for errors

3. **Test email sending manually**:
   ```
   /email Send a test email to me
   ```

## Future Enhancements

1. **UI Management**:
   - Dashboard for viewing/managing recurring tasks
   - Task execution history visualization
   - Edit task schedules from UI

2. **Additional Actions**:
   - Custom report templates
   - Webhook notifications
   - Slack/Discord integrations
   - Database backups

3. **Advanced Scheduling**:
   - Cron-style expressions
   - Multiple execution times per day
   - Holiday awareness

4. **Error Recovery**:
   - Retry failed tasks with exponential backoff
   - Alert on repeated failures
   - Dead letter queue for failed tasks

## Related Documentation

- [Slash Commands](../architecture/guides/SLASH_COMMANDS.md)
- [Email Agent](../features/EMAIL_FEATURE_SUMMARY.md)
- [Report Generator](../features/REPORT_GENERATOR.md)
