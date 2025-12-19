"""
Recurring task scheduler for automated workflows.

Handles registration, persistence, and execution of scheduled tasks like
weekly screen time reports, daily summaries, etc.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Literal
from zoneinfo import ZoneInfo
import uuid
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


@dataclass
class ScheduleSpec:
    """Schedule specification for recurring tasks."""
    type: Literal["weekly", "daily", "monthly"]  # Schedule type
    weekday: Optional[int] = None  # 0=Monday, 6=Sunday (for weekly)
    day: Optional[int] = None  # Day of month (for monthly)
    time: str = "09:00"  # Time in HH:MM format
    tz: str = "America/Los_Angeles"  # Timezone


@dataclass
class ActionSpec:
    """Action specification for what to execute."""
    kind: str  # e.g., "screen_time_report"
    delivery: Dict[str, Any] = field(default_factory=dict)  # Delivery options
    params: Dict[str, Any] = field(default_factory=dict)  # Additional parameters


@dataclass
class RecurringTask:
    """A scheduled recurring task."""
    id: str
    name: str
    command_text: str  # Original command for reference
    schedule: ScheduleSpec
    action: ActionSpec
    next_run_at: Optional[str] = None  # ISO format
    last_run_at: Optional[str] = None  # ISO format
    status: Literal["active", "paused", "error"] = "active"
    history: List[Dict[str, Any]] = field(default_factory=list)  # Recent runs
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "command_text": self.command_text,
            "schedule": asdict(self.schedule),
            "action": asdict(self.action),
            "next_run_at": self.next_run_at,
            "last_run_at": self.last_run_at,
            "status": self.status,
            "history": self.history[-10:],  # Keep last 10 runs
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecurringTask":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            command_text=data["command_text"],
            schedule=ScheduleSpec(**data["schedule"]),
            action=ActionSpec(**data["action"]),
            next_run_at=data.get("next_run_at"),
            last_run_at=data.get("last_run_at"),
            status=data.get("status", "active"),
            history=data.get("history", []),
            created_at=data.get("created_at")
        )


class RecurringTaskStore:
    """JSON-backed persistent store for recurring tasks."""

    def __init__(self, file_path: str = "data/recurring_tasks.json"):
        self.file_path = Path(file_path)
        self._lock = asyncio.Lock()
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Bootstrap the file if it doesn't exist."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._write_sync({"version": 1, "tasks": []})

    def _write_sync(self, data: Dict[str, Any]):
        """Synchronous write with atomic temp file."""
        temp_path = self.file_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)
            temp_path.replace(self.file_path)
        except Exception as e:
            logger.error(f"Failed to write recurring tasks: {e}")
            if temp_path.exists():
                temp_path.unlink()
            raise

    async def load_tasks(self) -> List[RecurringTask]:
        """Load all tasks from storage."""
        async with self._lock:
            try:
                with open(self.file_path, 'r') as f:
                    data = json.load(f)

                # Handle schema upgrades here if needed
                if data.get("version") != 1:
                    logger.warning(f"Unknown schema version: {data.get('version')}")

                return [RecurringTask.from_dict(t) for t in data.get("tasks", [])]
            except FileNotFoundError:
                return []
            except Exception as e:
                logger.error(f"Failed to load recurring tasks: {e}")
                return []

    async def save_tasks(self, tasks: List[RecurringTask]):
        """Save all tasks to storage."""
        async with self._lock:
            data = {
                "version": 1,
                "tasks": [t.to_dict() for t in tasks]
            }
            await asyncio.to_thread(self._write_sync, data)

    async def add_task(self, task: RecurringTask):
        """Add a new task."""
        tasks = await self.load_tasks()
        tasks.append(task)
        await self.save_tasks(tasks)

    async def update_task(self, task: RecurringTask):
        """Update an existing task."""
        tasks = await self.load_tasks()
        for i, t in enumerate(tasks):
            if t.id == task.id:
                tasks[i] = task
                break
        await self.save_tasks(tasks)

    async def remove_task(self, task_id: str):
        """Remove a task by ID."""
        tasks = await self.load_tasks()
        tasks = [t for t in tasks if t.id != task_id]
        await self.save_tasks(tasks)

    async def get_task(self, task_id: str) -> Optional[RecurringTask]:
        """Get a task by ID."""
        tasks = await self.load_tasks()
        for task in tasks:
            if task.id == task_id:
                return task
        return None


class RecurringTaskScheduler:
    """
    Scheduler that runs recurring tasks at specified intervals.

    Runs an async loop that checks for due tasks every 60 seconds and
    executes them via the agent system.
    """

    def __init__(self, agent_registry, agent, session_manager, store: RecurringTaskStore = None):
        """
        Initialize scheduler.

        Args:
            agent_registry: Registry of available agents
            agent: Main orchestrator agent
            session_manager: Session manager for tracking executions
            store: Task store (creates default if None)
        """
        self.agent_registry = agent_registry
        self.agent = agent
        self.session_manager = session_manager
        self.store = store or RecurringTaskStore()
        # Get config from agent or global config manager
        if hasattr(agent, 'config'):
            self.config = agent.config
        else:
            from src.config_manager import get_global_config_manager
            self.config = get_global_config_manager().get_config()
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._execution_lock = asyncio.Semaphore(3)  # Max 3 concurrent executions
        self._debug_force_run = False  # For testing

    def _calculate_next_run(self, schedule: ScheduleSpec, from_time: datetime = None) -> datetime:
        """
        Calculate the next run time based on schedule spec.

        Args:
            schedule: Schedule specification
            from_time: Calculate from this time (defaults to now)

        Returns:
            Next run datetime in the schedule's timezone
        """
        if from_time is None:
            from_time = datetime.now(ZoneInfo(schedule.tz))

        # Parse target time
        hour, minute = map(int, schedule.time.split(':'))

        if schedule.type == "daily":
            # Next occurrence at target time
            next_run = from_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= from_time:
                next_run += timedelta(days=1)

        elif schedule.type == "weekly":
            # Next occurrence on target weekday at target time
            target_weekday = schedule.weekday or 0
            days_ahead = target_weekday - from_time.weekday()
            if days_ahead < 0:  # Target day already happened this week
                days_ahead += 7

            next_run = from_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            next_run += timedelta(days=days_ahead)

            # If same day but time passed, move to next week
            if days_ahead == 0 and next_run <= from_time:
                next_run += timedelta(days=7)

        elif schedule.type == "monthly":
            # Next occurrence on target day of month
            target_day = schedule.day or 1
            next_run = from_time.replace(day=target_day, hour=hour, minute=minute, second=0, microsecond=0)

            if next_run <= from_time:
                # Move to next month
                if from_time.month == 12:
                    next_run = next_run.replace(year=from_time.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=from_time.month + 1)

        else:
            raise ValueError(f"Unknown schedule type: {schedule.type}")

        return next_run

    async def _execute_task(self, task: RecurringTask):
        """
        Execute a single task.

        Args:
            task: Task to execute
        """
        async with self._execution_lock:
            logger.info(f"Executing recurring task: {task.name} (ID: {task.id})")
            start_time = datetime.now(ZoneInfo("UTC"))

            try:
                # Execute based on action kind
                if task.action.kind == "screen_time_report":
                    await self._execute_screen_time_report(task)
                else:
                    logger.warning(f"Unknown action kind: {task.action.kind}")
                    raise ValueError(f"Unknown action kind: {task.action.kind}")

                # Record success
                task.last_run_at = start_time.isoformat()
                task.next_run_at = self._calculate_next_run(task.schedule, start_time).isoformat()
                task.status = "active"

                task.history.append({
                    "timestamp": start_time.isoformat(),
                    "status": "success",
                    "duration_ms": int((datetime.now(ZoneInfo("UTC")) - start_time).total_seconds() * 1000)
                })

                logger.info(f"Task {task.name} completed successfully")

            except Exception as e:
                logger.error(f"Task {task.name} failed: {e}", exc_info=True)

                task.last_run_at = start_time.isoformat()
                task.status = "error"

                task.history.append({
                    "timestamp": start_time.isoformat(),
                    "status": "error",
                    "error": str(e),
                    "duration_ms": int((datetime.now(ZoneInfo("UTC")) - start_time).total_seconds() * 1000)
                })

            finally:
                # Save updated task state
                await self.store.update_task(task)

    async def _execute_screen_time_report(self, task: RecurringTask):
        """
        Execute a screen time report task.

        Args:
            task: Task to execute
        """
        # Import here to avoid circular dependencies
        from src.agent.screentime_agent import ScreenTimeAgent
        from src.automation.report_generator import ReportGenerator
        from src.agent.email_agent import compose_email

        # Collect screen time data
        screentime_agent = ScreenTimeAgent()
        usage_data = await screentime_agent.collect_screen_time_usage()

        # Check if data collection was successful
        if not usage_data.get("success"):
            error_msg = usage_data.get("error", "Unknown error")
            logger.error(f"Failed to collect screen time data: {error_msg}")
            raise ValueError(f"Screen time data collection failed: {error_msg}")

        # Format screen time data into report sections
        data = usage_data.get("data", {})
        sections = []
        
        # Summary section
        total_duration = data.get("total_duration_formatted", "N/A")
        period_info = data.get("period", {})
        period_str = f"{period_info.get('start', '')} to {period_info.get('end', '')}"
        
        sections.append({
            "heading": "Summary",
            "content": f"Total screen time: {total_duration}\nPeriod: {period_str}"
        })
        
        # Apps section
        apps = data.get("apps", [])
        if apps:
            apps_content = "Top applications:\n"
            for app in apps[:10]:  # Top 10 apps
                app_name = app.get("name", "Unknown")
                app_duration = app.get("duration_formatted", "N/A")
                apps_content += f"• {app_name}: {app_duration}\n"
            sections.append({
                "heading": "Application Usage",
                "content": apps_content
            })

        # Generate report using create_report
        report_gen = ReportGenerator(self.config)
        report_result = report_gen.create_report(
            title=f"Screen Time Report - {datetime.now().strftime('%Y-%m-%d')}",
            content="",
            sections=sections,
            export_pdf=True,
            output_name=f"screen_time_report_{datetime.now().strftime('%Y%m%d')}"
        )

        # Check if report generation was successful
        if report_result.get("error"):
            error_msg = report_result.get("error_message", "Unknown error")
            logger.error(f"Failed to generate report: {error_msg}")
            raise ValueError(f"Report generation failed: {error_msg}")

        # Get report path (prefer PDF, fallback to RTF/HTML)
        report_path = report_result.get("pdf_path") or report_result.get("rtf_path") or report_result.get("html_path")
        if not report_path:
            raise ValueError("Report generated but no file path returned")

        # Deliver via email if requested
        delivery = task.action.delivery
        if delivery.get("mode") == "email":
            recipient = delivery.get("recipient", "default")

            subject = f"Weekly Screen Time Report - {datetime.now().strftime('%Y-%m-%d')}"
            body = "Please find your weekly screen time report attached."

            # Use compose_email.invoke() instead of await (it's a synchronous LangChain tool)
            email_result = compose_email.invoke({
                "subject": subject,
                "body": body,
                "recipient": recipient,
                "attachments": [report_path],
                "send": delivery.get("send", True)
            })

            if email_result.get("error"):
                error_msg = email_result.get("error_message", "Unknown error")
                logger.error(f"Failed to send email: {error_msg}")
                raise ValueError(f"Email delivery failed: {error_msg}")

            logger.info(f"Screen time report sent to {recipient}")

    async def _scheduler_loop(self):
        """Main scheduler loop that checks for due tasks."""
        logger.info("Recurring task scheduler started")

        while self._running:
            try:
                tasks = await self.store.load_tasks()
                now = datetime.now(ZoneInfo("UTC"))

                for task in tasks:
                    # Skip inactive tasks
                    if task.status != "active":
                        continue

                    # Initialize next_run_at if not set
                    if task.next_run_at is None:
                        task.next_run_at = self._calculate_next_run(task.schedule).isoformat()
                        await self.store.update_task(task)
                        continue

                    # Check if due
                    next_run = datetime.fromisoformat(task.next_run_at)
                    if self._debug_force_run or next_run <= now:
                        # Execute in background
                        asyncio.create_task(self._execute_task(task))

            except Exception as e:
                logger.error(f"Scheduler loop error: {e}", exc_info=True)

            # Wait 60 seconds before next check
            await asyncio.sleep(60)

        logger.info("Recurring task scheduler stopped")

    async def start(self):
        """Start the scheduler background task."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Recurring task scheduler initialized")

    async def stop(self):
        """Stop the scheduler background task."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Recurring task scheduler shutdown complete")

    async def register_task(
        self,
        name: str,
        command_text: str,
        schedule: ScheduleSpec,
        action: ActionSpec
    ) -> RecurringTask:
        """
        Register a new recurring task.

        Args:
            name: Friendly name for the task
            command_text: Original command text
            schedule: Schedule specification
            action: Action specification

        Returns:
            Created RecurringTask
        """
        task = RecurringTask(
            id=str(uuid.uuid4()),
            name=name,
            command_text=command_text,
            schedule=schedule,
            action=action,
            created_at=datetime.now(ZoneInfo("UTC")).isoformat()
        )

        # Calculate initial next_run_at
        task.next_run_at = self._calculate_next_run(schedule).isoformat()

        await self.store.add_task(task)
        logger.info(f"Registered recurring task: {name} (ID: {task.id})")

        return task

    async def get_tasks(self) -> List[RecurringTask]:
        """Get all registered tasks."""
        return await self.store.load_tasks()

    async def pause_task(self, task_id: str):
        """Pause a task."""
        task = await self.store.get_task(task_id)
        if task:
            task.status = "paused"
            await self.store.update_task(task)

    async def resume_task(self, task_id: str):
        """Resume a paused task."""
        task = await self.store.get_task(task_id)
        if task:
            task.status = "active"
            await self.store.update_task(task)

    async def delete_task(self, task_id: str):
        """Delete a task."""
        await self.store.remove_task(task_id)
