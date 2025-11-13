"""
Daily Overview Agent - Generates comprehensive daily briefings.

This agent orchestrates calendar, reminders, and email data to provide
holistic daily overviews with meetings, todos, and action items.
"""

from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
import logging
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import re

from src.config import get_config_context

logger = logging.getLogger(__name__)


def _parse_time_filters(filters: str) -> Dict[str, Any]:
    """
    Parse natural language time filters into structured parameters.

    Examples:
    - "today" -> {"days_ahead": 1, "include_today": True}
    - "this afternoon" -> {"start_hour": 12, "end_hour": 18}
    - "tomorrow morning" -> {"days_ahead": 1, "start_hour": 6, "end_hour": 12}
    - "next 3 days" -> {"days_ahead": 3}

    Returns:
        Dictionary with filter parameters for downstream tools
    """
    filters_lower = filters.lower().strip()
    now = datetime.now()
    params = {}

    # Extract day references
    if "today" in filters_lower:
        params["include_today"] = True
        params["days_ahead"] = 1
    elif "tomorrow" in filters_lower:
        params["include_today"] = False
        params["days_ahead"] = 1
    elif "week" in filters_lower or "7 days" in filters_lower:
        params["days_ahead"] = 7
    elif "next 3 days" in filters_lower or "3 days" in filters_lower:
        params["days_ahead"] = 3
    elif "next week" in filters_lower:
        params["days_ahead"] = 7
    else:
        # Default to today
        params["include_today"] = True
        params["days_ahead"] = 1

    # Extract time of day
    if "morning" in filters_lower:
        params["start_hour"] = 6
        params["end_hour"] = 12
    elif "afternoon" in filters_lower:
        params["start_hour"] = 12
        params["end_hour"] = 18
    elif "evening" in filters_lower:
        params["start_hour"] = 18
        params["end_hour"] = 22
    elif "night" in filters_lower:
        params["start_hour"] = 22
        params["end_hour"] = 6

    # Extract specific hours if mentioned
    hour_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', filters_lower)
    if hour_match:
        hour = int(hour_match.group(1))
        if hour_match.group(3):  # AM/PM specified
            if hour_match.group(3).lower() == 'pm' and hour != 12:
                hour += 12
            elif hour_match.group(3).lower() == 'am' and hour == 12:
                hour = 0
        params["specific_hour"] = hour

    # Extract email window if mentioned
    email_window_match = re.search(r'(\d+)\s*hours?\s*emails?', filters_lower)
    if email_window_match:
        params["email_window_hours"] = int(email_window_match.group(1))

    # Default email window: 18 hours for today, 24 for longer periods
    if "email_window_hours" not in params:
        params["email_window_hours"] = 18 if params.get("days_ahead", 1) == 1 else 24

    # Include completed items? Default False for daily overview
    params["include_completed"] = "completed" in filters_lower or "done" in filters_lower

    return params


def _classify_email_action_items(emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Classify emails for action items and meeting references.

    Uses simple heuristics to identify:
    - Meeting requests/updates
    - Action-required emails
    - Time-sensitive items
    """
    action_items = []

    for email in emails:
        subject = email.get("subject", "").lower()
        body = email.get("body", "").lower()
        sender = email.get("sender", "").lower()

        # Skip newsletters, notifications, etc.
        skip_senders = ["newsletter", "notification", "alert", "update", "digest"]
        if any(skip in sender for skip in skip_senders):
            continue

        # Check for action verbs in subject/body
        action_verbs = ["please", "can you", "need you to", "action required", "urgent", "asap", "deadline"]
        has_action = any(verb in subject or verb in body for verb in action_verbs)

        # Check for meeting references
        meeting_keywords = ["meeting", "call", "zoom", "teams", "google meet", "schedule", "reschedule"]
        has_meeting = any(keyword in subject or keyword in body for keyword in meeting_keywords)

        # Check for time sensitivity
        time_keywords = ["today", "tomorrow", "this week", "deadline", "due", "by", "before"]
        time_sensitive = any(keyword in subject or keyword in body for keyword in time_keywords)

        if has_action or has_meeting or time_sensitive:
            action_items.append({
                "type": "meeting" if has_meeting else "action",
                "subject": email.get("subject", ""),
                "sender": email.get("sender", ""),
                "time_received": email.get("timestamp", ""),
                "urgency": "high" if time_sensitive else "medium",
                "reason": "meeting_reference" if has_meeting else "action_required"
            })

    return action_items


def _analyze_backfill_opportunities(
    meetings: List[Dict[str, Any]],
    todos: List[Dict[str, Any]],
    email_action_items: List[Dict[str, Any]],
    calendar_agent: 'CalendarAgent'
) -> List[Dict[str, Any]]:
    """
    Analyze commitments in emails/reminders that might not have calendar events.

    Uses heuristics to identify:
    - Meeting commitments in emails without calendar events
    - Time-sensitive todos that should be calendar events
    - Recurring commitments that need calendar slots
    """
    suggestions = []

    # Extract existing meeting titles for deduplication
    existing_titles = {meeting.get("title", "").lower() for meeting in meetings}

    # Check email action items for meeting commitments
    for item in email_action_items:
        if item.get("type") == "meeting":
            title = item.get("subject", "").lower().strip()
            if title and title not in existing_titles:
                # Try to extract time information from the email
                time_info = _extract_time_from_email(item)
                if time_info:
                    suggestions.append({
                        "type": "email_meeting_commitment",
                        "title": item.get("subject", ""),
                        "suggested_event": {
                            "title": item.get("subject", ""),
                            "start_time": time_info.get("start_time"),
                            "end_time": time_info.get("end_time"),
                            "notes": f"Auto-detected from email: {item.get('sender', '')}",
                            "confidence": time_info.get("confidence", "low")
                        },
                        "source": "email",
                        "reason": "Meeting commitment found in email but no calendar event exists"
                    })

    # Check todos for time-sensitive items that should be calendar events
    for todo in todos:
        title = todo.get("title", "").lower()
        notes = todo.get("notes", "").lower() if todo.get("notes") else ""

        # Look for time indicators in todos
        if any(keyword in title or keyword in notes for keyword in
               ["meeting", "call", "appointment", "schedule", "at ", "time:"]):
            time_info = _extract_time_from_todo(todo)
            if time_info and title not in existing_titles:
                suggestions.append({
                    "type": "timed_todo",
                    "title": todo.get("title", ""),
                    "suggested_event": {
                        "title": todo.get("title", ""),
                        "start_time": time_info.get("start_time"),
                        "end_time": time_info.get("end_time"),
                        "notes": f"Converted from reminder: {todo.get('notes', '')}",
                        "confidence": time_info.get("confidence", "medium")
                    },
                    "source": "reminder",
                    "reason": "Time-sensitive reminder appears to be a meeting/appointment"
                })

    return suggestions


def _extract_time_from_email(email_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract time information from email content using heuristics.
    Returns None if no clear time information found.
    """
    subject = email_item.get("subject", "").lower()
    sender = email_item.get("sender", "").lower()

    # Simple heuristics for time extraction (could be enhanced with LLM)
    time_patterns = [
        r'tomorrow\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?',
        r'today\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?',
        r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
        r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)'
    ]

    import re
    for pattern in time_patterns:
        match = re.search(pattern, subject)
        if match:
            # Basic time parsing (simplified)
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            am_pm = match.group(3).lower() if match.group(3) else None

            if am_pm == 'pm' and hour != 12:
                hour += 12
            elif am_pm == 'am' and hour == 12:
                hour = 0

            # Assume tomorrow for "tomorrow", today for others
            days_offset = 1 if "tomorrow" in subject else 0
            base_date = datetime.now() + timedelta(days=days_offset)
            start_time = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            end_time = start_time + timedelta(hours=1)  # Assume 1 hour duration

            return {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "confidence": "medium"
            }

    return None


def _extract_time_from_todo(todo: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract time information from todo/reminder content.
    """
    title = todo.get("title", "").lower()
    notes = todo.get("notes", "").lower() if todo.get("notes") else ""

    # Check for due dates in the todo structure
    if todo.get("due_date"):
        try:
            due_date = date_parser.parse(todo["due_date"])
            # Assume 1-hour meeting at the due time
            return {
                "start_time": due_date.isoformat(),
                "end_time": (due_date + timedelta(hours=1)).isoformat(),
                "confidence": "high"
            }
        except:
            pass

    # Fallback to text parsing similar to email
    return _extract_time_from_email({"subject": title + " " + notes})


def _load_overview_runtime():
    """
    Load required components for daily overview operations.

    Returns:
        Tuple of (config, calendar_agent, reminders_agent, email_agent)
    """
    context = get_config_context()
    config = context.data

    # Import agents (lazy loading to avoid circular imports)
    from .calendar_agent import CalendarAgent
    from .reminders_agent import RemindersAgent
    from .email_agent import EmailAgent

    calendar_agent = CalendarAgent(config)
    reminders_agent = RemindersAgent(config)
    email_agent = EmailAgent(config)

    return config, calendar_agent, reminders_agent, email_agent


@tool
def generate_day_overview(filters: str = "today") -> Dict[str, Any]:
    """
    Generate a comprehensive daily overview by aggregating calendar, reminders, and emails.

    DAILY OVERVIEW AGENT - LEVEL 1: Holistic Day Briefing
    Use this to get a complete picture of your day including meetings, todos, and email actions.

    Args:
        filters: Natural language time filters (e.g., "today", "tomorrow morning", "next 3 days")

    Returns:
        Structured overview with:
        - meetings: Calendar events
        - reminders: Upcoming todos and reminders
        - email_action_items: Time-sensitive emails requiring action
        - summary: Brief overview text
        - time_window: Applied time filters
    """
    logger.info(f"[DAILY OVERVIEW] Tool: generate_day_overview(filters='{filters}')")

    try:
        config, calendar_agent, reminders_agent, email_agent = _load_overview_runtime()

        # Parse natural language filters
        time_params = _parse_time_filters(filters)
        days_ahead = time_params.get("days_ahead", 1)
        email_window_hours = time_params.get("email_window_hours", 18)

        logger.debug(f"[DAILY OVERVIEW] Parsed filters: {time_params}")

        # 1. Get calendar events
        calendar_result = calendar_agent.execute("list_calendar_events", {"days_ahead": days_ahead})
        meetings = []
        if not calendar_result.get("error"):
            meetings = calendar_result.get("events", [])

        # 2. Get reminders/todos
        reminders_result = reminders_agent.execute("list_reminders", {
            "include_completed": time_params.get("include_completed", False)
        })
        todos = []
        if not reminders_result.get("error"):
            todos = reminders_result.get("reminders", [])

        # 3. Get recent emails for action items
        email_result = email_agent.execute("read_latest_emails", {
            "hours_back": email_window_hours,
            "limit": 50  # Get enough emails to find action items
        })
        email_action_items = []
        if not email_result.get("error"):
            emails = email_result.get("emails", [])
            email_action_items = _classify_email_action_items(emails)

        # 4. Check for calendar backfill opportunities
        backfill_suggestions = _analyze_backfill_opportunities(
            meetings, todos, email_action_items, calendar_agent
        )

        # 5. Apply time filtering if specific hours requested
        if "start_hour" in time_params and "end_hour" in time_params:
            start_hour = time_params["start_hour"]
            end_hour = time_params["end_hour"]

            # Filter meetings by time
            filtered_meetings = []
            for meeting in meetings:
                try:
                    meeting_time = date_parser.parse(meeting.get("start_time", ""))
                    if start_hour <= meeting_time.hour < end_hour:
                        filtered_meetings.append(meeting)
                except:
                    # If we can't parse time, include it
                    filtered_meetings.append(meeting)
            meetings = filtered_meetings

        # 5. Generate summary
        summary_parts = []
        if meetings:
            summary_parts.append(f"{len(meetings)} meeting{'s' if len(meetings) != 1 else ''}")
        if todos:
            summary_parts.append(f"{len(todos)} reminder{'s' if len(todos) != 1 else ''}")
        if email_action_items:
            summary_parts.append(f"{len(email_action_items)} email action{'s' if len(email_action_items) != 1 else ''}")

        summary = f"Your {filters} includes: {', '.join(summary_parts) if summary_parts else 'No scheduled items'}"

        # 6. Structure the response
        overview = {
            "summary": summary,
            "time_window": time_params,
            "filters_applied": filters,
            "sections": {
                "meetings": {
                    "count": len(meetings),
                    "items": meetings,
                    "description": f"Calendar events for {filters}"
                },
                "reminders": {
                    "count": len(todos),
                    "items": todos,
                    "description": f"Reminders and todos for {filters}"
                },
                "email_action_items": {
                    "count": len(email_action_items),
                    "items": email_action_items,
                    "description": f"Time-sensitive emails requiring action (last {email_window_hours} hours)"
                },
                "calendar_backfill_suggestions": {
                    "count": len(backfill_suggestions),
                    "items": backfill_suggestions,
                    "description": "Suggested calendar events to create from commitments found in emails/reminders"
                }
            },
            "generated_at": datetime.now().isoformat(),
            "data_sources": {
                "calendar_days_ahead": days_ahead,
                "email_window_hours": email_window_hours,
                "include_completed_reminders": time_params.get("include_completed", False)
            }
        }

        logger.info(f"[DAILY OVERVIEW] Generated overview: {len(meetings)} meetings, {len(todos)} reminders, {len(email_action_items)} email actions")
        return overview

    except Exception as e:
        logger.error(f"[DAILY OVERVIEW] Error in generate_day_overview: {e}")
        return {
            "error": True,
            "error_type": "DailyOverviewError",
            "error_message": str(e),
            "retry_possible": True,
            "filters_attempted": filters
        }


# Daily Overview Agent Tools
DAILY_OVERVIEW_AGENT_TOOLS = [
    generate_day_overview,
]

# Daily Overview Agent Hierarchy
DAILY_OVERVIEW_AGENT_HIERARCHY = """
Daily Overview Agent Hierarchy:
===============================

LEVEL 1: Holistic Day Briefing
- generate_day_overview: Aggregate calendar + reminders + email actions
  └─ Orchestrates: list_calendar_events, list_reminders, read_latest_emails

The agent acts as a mini-orchestrator, combining multiple data sources
to provide comprehensive daily briefings with natural language filtering.
"""


class DailyOverviewAgent:
    """
    Daily Overview Agent - Mini-orchestrator for daily briefings.

    Responsibilities:
    - Aggregating calendar events, reminders, and email actions
    - Natural language time filtering
    - Generating structured daily overviews
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in DAILY_OVERVIEW_AGENT_TOOLS}
        logger.info(f"[DAILY OVERVIEW AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        """Get all daily overview agent tools."""
        return DAILY_OVERVIEW_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get daily overview agent hierarchy documentation."""
        return DAILY_OVERVIEW_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a daily overview agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Tool '{tool_name}' not found in DailyOverviewAgent",
                "available_tools": list(self.tools.keys())
            }

        try:
            tool = self.tools[tool_name]
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[DAILY OVERVIEW AGENT] Error executing {tool_name}: {e}")
            return {
                "error": True,
                "error_type": "ToolExecutionError",
                "error_message": str(e),
                "tool_name": tool_name
            }
