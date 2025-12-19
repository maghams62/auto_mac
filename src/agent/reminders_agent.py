"""
Reminders Agent - Handles Apple Reminders creation and management.

This agent is responsible for:
- Creating time-based reminders
- Setting due dates and times
- Organizing reminders into lists
- Managing task completion

INTEGRATION PATTERN:
- Reminders are used for time-sensitive actions
- Due times can be inferred by LLM from context
- Conditional reminder creation based on external data (weather, etc.)
- LLM decides WHEN to remind based on natural language reasoning

Acts as a time-based action trigger layer.
"""

from typing import Dict, Any, Optional, List
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)


@tool
def create_reminder(
    title: str,
    due_time: Optional[str] = None,
    list_name: str = "Reminders",
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new reminder in Apple Reminders with optional due date/time.

    REMINDERS AGENT - LEVEL 1: Reminder Creation
    Use this to create time-based action triggers for the user.

    Args:
        title: Reminder title/description (what to remind about)
        due_time: Due date/time in natural language or ISO format
            Examples:
            - "tomorrow at 9am" → Tomorrow at 9:00 AM
            - "today at 5pm" → Today at 5:00 PM
            - "in 2 hours" → 2 hours from now
            - "2024-12-25 10:00" → Specific datetime
            - None → No due date (just a task)
        list_name: Target list name (default: "Reminders")
                  Auto-creates list if doesn't exist
        notes: Optional additional details/notes for reminder

    Returns:
        Dictionary with creation status:
        {
            "success": True,
            "reminder_title": str,
            "reminder_id": str,
            "list_name": str,
            "due_date": str,  # ISO format
            "created_at": str,
            "message": str
        }

    Example Workflow (Weather-Conditional Reminder):
        Step 0: get_weather_forecast(location="NYC", timeframe="today")
        Step 1: synthesize_content(
            source_contents=["$step0.precipitation_chance", "$step0.precipitation_type"],
            topic="Should user carry umbrella today?",
            synthesis_style="brief"
        )
        Step 2: IF $step1 says "yes" -> create_reminder(
            title="Bring umbrella",
            due_time="today at 7am",
            notes="Rain expected today ($step0.precipitation_chance% chance)"
        )

    CRITICAL: LLM decides WHEN to remind
    - Use Writing Agent to infer optimal reminder time from context
    - Example: "before commute" → LLM decides "7am"
    - Example: "before meeting" → LLM infers from user's schedule context

    Example (LLM-Inferred Timing):
        User: "Remind me to charge laptop before tomorrow's presentation"
        Step 0: synthesize_content(
            source_contents=["tomorrow's presentation"],
            topic="When should user be reminded to charge laptop?",
            synthesis_style="brief"
        )
        → LLM output: "Evening before, around 8pm"
        Step 1: create_reminder(
            title="Charge laptop for presentation",
            due_time="today at 8pm"
        )
    """
    logger.info(f"[REMINDERS AGENT] create_reminder(title={title}, due_time={due_time}, list={list_name})")

    try:
        from ..automation.reminders_automation import RemindersAutomation
        from ..utils import load_config

        config = load_config()

        # Initialize reminders automation
        reminders_automation = RemindersAutomation(config)

        # Create reminder
        result = reminders_automation.create_reminder(title, due_time, list_name, notes)

        if result.get("success"):
            due_info = f" due {result.get('due_date')}" if result.get('due_date') else " (no due date)"
            logger.info(f"[REMINDERS AGENT] ✅ Created reminder: {title}{due_info}")
            
            # Format success message for UI using reply_to_user pattern
            message = result.get("message", f"Created reminder '{title}' in list '{list_name}'")
            details = ""
            if due_date := result.get('due_date'):
                from datetime import datetime
                try:
                    dt = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                    details = f"Due: {dt.strftime('%Y-%m-%d %H:%M')}"
                except:
                    details = f"Due: {due_date}"
            
            # Return formatted result that UI can display nicely
            return {
                **result,
                "type": "reply",
                "status": "success",
                "completion_event": {
                    "action_type": "reminder_created",
                    "summary": message,
                    "status": "success",
                    "artifact_metadata": {
                        "reminder_id": result.get("reminder_id"),
                        "list_name": list_name,
                        "due_date": result.get("due_date")
                    }
                }
            }
        else:
            logger.error(f"[REMINDERS AGENT] ❌ Failed to create reminder: {result.get('error_message')}")
            # Format error message for UI
            error_msg = result.get("user_friendly_message") or result.get("error_message", "Failed to create reminder")
            return {
                **result,
                "type": "reply",
                "status": "error",
                "message": f"❌ Failed to create reminder: {error_msg}"
            }

        return result

    except Exception as e:
        logger.error(f"[REMINDERS AGENT] Error in create_reminder: {e}")
        return {
            "success": False,
            "error": True,
            "error_type": "ReminderCreationError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def list_reminders(
    list_name: Optional[str] = None,
    include_completed: bool = False
) -> Dict[str, Any]:
    """
    List reminders from macOS Reminders.app.

    REMINDERS AGENT - LEVEL 1: Reminder Reading
    Use this to retrieve reminders and todos.

    Args:
        list_name: Optional list name to filter by (None = all lists)
        include_completed: Whether to include completed reminders (default: False)

    Returns:
        Dictionary with:
        - reminders: List of reminder dictionaries (title, due_date, notes, list_name, completed)
        - count: Number of reminders found
        - list_name: Optional list name that was queried

    Example Workflow:
        Step 0: list_reminders(include_completed=False)
        → Returns: {reminders: [...], count: 5}
        Step 1: synthesize_content(
            source_contents=["$step0.reminders"],
            topic="Summary of upcoming reminders",
            synthesis_style="concise"
        )
        Step 2: reply_to_user(message="$step1.synthesized_content")
    """
    logger.info(f"[REMINDERS AGENT] list_reminders(list_name={list_name}, include_completed={include_completed})")

    try:
        from ..automation.reminders_automation import RemindersAutomation
        from ..utils import load_config

        config = load_config()

        # Initialize reminders automation
        reminders_automation = RemindersAutomation(config)

        # List reminders
        result = reminders_automation.list_reminders(list_name, include_completed)

        if result.get("error"):
            logger.error(f"[REMINDERS AGENT] ❌ Failed to list reminders: {result.get('error_message')}")
        else:
            logger.info(f"[REMINDERS AGENT] ✅ Retrieved {result.get('count', 0)} reminders")

        return result

    except Exception as e:
        logger.error(f"[REMINDERS AGENT] Error in list_reminders: {e}")
        return {
            "reminders": [],
            "count": 0,
            "list_name": list_name,
            "error": True,
            "error_type": "ReminderListError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def complete_reminder(
    reminder_title: str,
    list_name: str = "Reminders"
) -> Dict[str, Any]:
    """
    Mark a reminder as complete.

    REMINDERS AGENT - LEVEL 1: Reminder Completion
    Use this to mark tasks as done.

    Args:
        reminder_title: Title of reminder to complete
        list_name: List containing the reminder (default: "Reminders")

    Returns:
        Dictionary with completion status:
        {
            "success": True,
            "reminder_title": str,
            "list_name": str,
            "message": str
        }

    Example Workflow:
        Step 0: complete_reminder(
            reminder_title="Bring umbrella",
            list_name="Reminders"
        )
        Step 1: reply_to_user(message="Marked 'Bring umbrella' as complete")
    """
    logger.info(f"[REMINDERS AGENT] complete_reminder(title={reminder_title}, list={list_name})")

    try:
        from ..automation.reminders_automation import RemindersAutomation
        from ..utils import load_config

        config = load_config()

        # Initialize reminders automation
        reminders_automation = RemindersAutomation(config)

        # Complete reminder
        result = reminders_automation.complete_reminder(reminder_title, list_name)

        if result.get("success"):
            logger.info(f"[REMINDERS AGENT] ✅ Completed reminder: {reminder_title}")
        else:
            logger.error(f"[REMINDERS AGENT] ❌ Failed to complete reminder: {result.get('error_message')}")

        return result

    except Exception as e:
        logger.error(f"[REMINDERS AGENT] Error in complete_reminder: {e}")
        return {
            "success": False,
            "error": True,
            "error_type": "ReminderCompletionError",
            "error_message": str(e),
            "retry_possible": False
        }


# Reminders Agent Tool Registry
REMINDERS_AGENT_TOOLS = [
    list_reminders,
    create_reminder,
    complete_reminder,
]


# Tool hierarchy documentation
REMINDERS_AGENT_HIERARCHY = """
REMINDERS AGENT TOOL HIERARCHY
==============================

LEVEL 1: Reminder Management
├─ list_reminders → List reminders from Apple Reminders
│  ├─ Can filter by list name (optional)
│  ├─ Can include/exclude completed reminders
│  └─ Returns list of reminders with details (title, due_date, notes, list_name, completed)
│
├─ create_reminder → Create time-based reminder with optional due date
│  ├─ Natural language due time parsing ("tomorrow at 9am", "in 2 hours")
│  ├─ Organizes into lists (auto-creates if needed)
│  ├─ Optional notes field for additional context
│  └─ Returns reminder_id and due_date
│
└─ complete_reminder → Mark reminder as complete
   ├─ Finds reminder by title in specified list
   └─ Marks as done in Apple Reminders

INTEGRATION PATTERNS:

Pattern 1: Weather-Conditional Reminder
───────────────────────────────────────
User: "If it's going to rain today, remind me to carry umbrella"

Step 0: get_weather_forecast(location="NYC", timeframe="today")
→ Returns: {precipitation_chance: 75%, precipitation_type: "rain"}

Step 1: synthesize_content(
    source_contents=["$step0.precipitation_chance", "$step0.precipitation_type"],
    topic="Will it rain heavily enough to need umbrella?",
    synthesis_style="brief"
)
→ LLM returns: "Yes, 75% chance of rain. User should bring umbrella."

Step 2: create_reminder(
    title="Bring umbrella",
    due_time="today at 7am",
    notes="Rain expected: 75% chance"
)

Step 3: reply_to_user(
    message="It's going to rain today (75% chance). I've set a reminder for 7am to bring your umbrella."
)

Pattern 2: Sunny Weather Note (Alternative Action)
──────────────────────────────────────────────────
User: "If it's sunny tomorrow, remind me to bring sunglasses"

Step 0: get_weather_forecast(location="LA", timeframe="tomorrow")
→ Returns: {current_conditions: "Sunny", precipitation_chance: 5%}

Step 1: synthesize_content(
    source_contents=["$step0.current_conditions"],
    topic="Is it sunny?",
    synthesis_style="brief"
)
→ LLM returns: "Yes, conditions are sunny."

Step 2: create_reminder(
    title="Bring sunglasses",
    due_time="tomorrow at 8am",
    notes="Sunny weather expected"
)

Step 3: reply_to_user(
    message="Tomorrow will be sunny! I've set a reminder for 8am to bring sunglasses."
)

Pattern 3: LLM-Inferred Timing
──────────────────────────────
User: "Remind me to charge my laptop before tomorrow's presentation"

Step 0: synthesize_content(
    source_contents=["tomorrow's presentation context"],
    topic="When should user be reminded to charge laptop before presentation?",
    synthesis_style="brief"
)
→ LLM returns: "Remind user evening before, around 8pm, so laptop can charge overnight."

Step 1: create_reminder(
    title="Charge laptop for presentation",
    due_time="today at 8pm",
    notes="For tomorrow's presentation"
)

Pattern 4: Multi-Step Conditional Logic
───────────────────────────────────────
User: "Check weather. If rain > 60%, remind me to bring umbrella. Otherwise, note to bring sunglasses."

Step 0: get_weather_forecast(location="SF", timeframe="today")

Step 1: synthesize_content(
    source_contents=["$step0.precipitation_chance"],
    topic="Is rain probability above 60%?",
    synthesis_style="brief"
)

Step 2A (IF rain > 60%):
create_reminder(title="Bring umbrella", due_time="today at 7am")

Step 2B (ELSE):
create_note(title="Weather note", body="Sunny today - bring sunglasses", folder="Personal")

Step 3: reply_to_user(message="Decision result...")

CRITICAL PRINCIPLES:
- LLM interprets weather data and decides actions
- NO hardcoded thresholds (60%, 50%, etc.) - LLM reasons about probabilities
- Timing inferred by LLM from natural language context
- Conditional branching lives in LLM reasoning, not hardcoded Python logic
- Always finish workflow with reply_to_user
"""


def execute_reminders_agent_tools(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a reminders agent tool by name.

    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments as dictionary

    Returns:
        Tool execution result
    """
    logger.info(f"[REMINDERS AGENT] Executing tool: {tool_name}")

    tool_map = {
        "list_reminders": list_reminders,
        "create_reminder": create_reminder,
        "complete_reminder": complete_reminder,
    }

    if tool_name not in tool_map:
        return {
            "error": True,
            "error_type": "UnknownTool",
            "error_message": f"Unknown reminders agent tool: {tool_name}",
            "retry_possible": False
        }


class RemindersAgent:
    """
    Wrapper class exposing reminder tools through an execute() API.

    Some higher-level agents (daily overview, slash command router, etc.)
    expect a CalendarAgent-style interface with `get_tools()` and
    `execute()`. The class reference existed but the implementation was
    missing, which caused imports to fail and downstream workflows (like
    "How's my deal looking?") to hang before a reply was produced.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in REMINDERS_AGENT_TOOLS}
        logger.info(f"[REMINDERS AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        return REMINDERS_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        return REMINDERS_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Reminders agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys()),
            }

        params = inputs or {}
        tool = self.tools[tool_name]
        logger.info(f"[REMINDERS AGENT] Executing: {tool_name}")

        try:
            return tool.invoke(params)
        except Exception as exc:
            logger.error(f"[REMINDERS AGENT] Execution error: {exc}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(exc),
                "retry_possible": False,
            }
