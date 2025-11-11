"""
Micro Actions Agent - Lightweight everyday utilities.

This agent provides simple, fast micro-actions for daily productivity:
- Launch applications
- Copy text snippets to clipboard
- Set timers/reminders

Built on top of simple AppleScript/open calls without heavy infrastructure.
"""

from typing import Dict, Any, Optional
from langchain_core.tools import tool
import logging
import subprocess

logger = logging.getLogger(__name__)


@tool
def launch_app(app_name: str) -> Dict[str, Any]:
    """
    Launch a macOS application by name.

    Use this tool when you need to:
    - Open an application quickly
    - Start a specific app (e.g., "Safari", "Notes", "Calculator")
    - Launch apps without navigating through Finder

    This is useful for:
    - Quick app access ("launch Safari")
    - Workflow automation ("open Notes before writing")
    - App switching ("launch Calculator")

    Args:
        app_name: Name of the application to launch (e.g., "Safari", "Notes", "Calculator", "Mail")
                  Can be the app name without .app extension

    Returns:
        Dictionary with launch status and app details

    Examples:
        # Launch Safari
        launch_app(app_name="Safari")

        # Launch Notes
        launch_app(app_name="Notes")

        # Launch Calculator
        launch_app(app_name="Calculator")
    """
    logger.info(f"[MICRO ACTIONS] Tool: launch_app(app_name='{app_name}')")

    try:
        # Validate input
        if not app_name or not isinstance(app_name, str) or len(app_name.strip()) == 0:
            return {
                "error": True,
                "error_type": "InvalidInput",
                "error_message": "App name must be a non-empty string",
                "retry_possible": True,
                "suggestion": "Provide a valid app name like 'Safari', 'Notes', or 'Calculator'"
            }

        app_name = app_name.strip()
        
        # Sanitize app name - remove .app extension if present (open -a handles it)
        if app_name.endswith('.app'):
            app_name = app_name[:-4]

        # Use 'open -a' command (simpler and more reliable than AppleScript for app launching)
        # This handles app name variations automatically (e.g., "Safari" or "Safari.app")
        result = subprocess.run(
            ["open", "-a", app_name],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            logger.info(f"Successfully launched app: {app_name}")
            return {
                "success": True,
                "app_name": app_name,
                "status": "launched",
                "message": f"Launched {app_name}"
            }
        else:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Failed to launch application"
            logger.warning(f"Failed to launch {app_name}: {error_msg}")
            
            # Provide helpful error messages based on common issues
            suggestion = "Make sure the app name is correct and the app is installed"
            if "Unable to find application" in error_msg or "No such file" in error_msg:
                suggestion = f"App '{app_name}' not found. Check spelling or install the app. Common apps: Safari, Notes, Mail, Calendar, Calculator"
            elif "permission" in error_msg.lower() or "denied" in error_msg.lower():
                suggestion = "Permission denied. Check System Preferences > Security & Privacy > Accessibility"
            
            return {
                "error": True,
                "error_type": "LaunchFailed",
                "error_message": f"Could not launch '{app_name}': {error_msg}",
                "app_name": app_name,
                "retry_possible": True,
                "suggestion": suggestion
            }

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout launching app: {app_name}")
        return {
            "error": True,
            "error_type": "Timeout",
            "error_message": f"Timeout launching {app_name}",
            "retry_possible": True
        }
    except Exception as e:
        logger.error(f"[MICRO ACTIONS] Error in launch_app: {e}")
        return {
            "error": True,
            "error_type": "LaunchError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def copy_snippet(text: str) -> Dict[str, Any]:
    """
    Copy text to the macOS clipboard.

    Use this tool when you need to:
    - Copy text snippets for pasting elsewhere
    - Store text temporarily in clipboard
    - Prepare content for pasting into other apps

    This is useful for:
    - Quick text copying ("copy this text")
    - Workflow automation (copy result, then paste in another app)
    - Content sharing ("copy the link to clipboard")

    Args:
        text: Text content to copy to clipboard (required)

    Returns:
        Dictionary with copy status and text details

    Examples:
        # Copy a simple text
        copy_snippet(text="Hello, world!")

        # Copy a URL
        copy_snippet(text="https://example.com")

        # Copy formatted text
        copy_snippet(text="Meeting Notes\n- Item 1\n- Item 2")
    """
    logger.info(f"[MICRO ACTIONS] Tool: copy_snippet(text_length={len(text) if text else 0})")

    try:
        # Validate input
        if text is None:
            return {
                "error": True,
                "error_type": "InvalidInput",
                "error_message": "Text cannot be None",
                "retry_possible": True,
                "suggestion": "Provide text content to copy to clipboard"
            }

        # Convert to string if needed
        text_str = str(text)
        
        # Set reasonable max length to prevent issues (1MB)
        MAX_CLIPBOARD_SIZE = 1024 * 1024
        if len(text_str.encode('utf-8')) > MAX_CLIPBOARD_SIZE:
            return {
                "error": True,
                "error_type": "InvalidInput",
                "error_message": f"Text too large (max {MAX_CLIPBOARD_SIZE // 1024}KB). Current size: {len(text_str.encode('utf-8')) // 1024}KB",
                "retry_possible": True,
                "max_size_bytes": MAX_CLIPBOARD_SIZE
            }

        # Use pbcopy command (standard macOS clipboard utility)
        result = subprocess.run(
            ["pbcopy"],
            input=text_str,
            text=True,
            capture_output=True,
            timeout=2
        )

        if result.returncode == 0:
            logger.info(f"Successfully copied {len(text_str)} characters to clipboard")
            return {
                "success": True,
                "status": "copied",
                "text_length": len(text_str),
                "text_preview": text_str[:100] + "..." if len(text_str) > 100 else text_str,
                "message": f"Copied {len(text_str)} characters to clipboard"
            }
        else:
            error_msg = result.stderr.strip() or "Failed to copy to clipboard"
            logger.error(f"Failed to copy to clipboard: {error_msg}")
            return {
                "error": True,
                "error_type": "CopyFailed",
                "error_message": f"Could not copy to clipboard: {error_msg}",
                "retry_possible": True
            }

    except subprocess.TimeoutExpired:
        logger.error("Timeout copying to clipboard")
        return {
            "error": True,
            "error_type": "Timeout",
            "error_message": "Timeout copying to clipboard",
            "retry_possible": True
        }
    except Exception as e:
        logger.error(f"[MICRO ACTIONS] Error in copy_snippet: {e}")
        return {
            "error": True,
            "error_type": "CopyError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def set_timer(duration_minutes: float, message: Optional[str] = None) -> Dict[str, Any]:
    """
    Set a timer that will notify you when it expires.

    Use this tool when you need to:
    - Set a reminder after a specific duration
    - Get notified when time is up
    - Create time-based alerts

    This is useful for:
    - Pomodoro timers ("set a 25 minute timer")
    - Reminders ("remind me in 10 minutes")
    - Time tracking ("set a 30 minute timer for this task")

    Args:
        duration_minutes: Duration in minutes (can be decimal, e.g., 0.5 for 30 seconds)
        message: Optional message to display when timer expires (default: "Timer expired")

    Returns:
        Dictionary with timer status and details

    Examples:
        # Simple 5 minute timer
        set_timer(duration_minutes=5.0)

        # 25 minute Pomodoro timer with message
        set_timer(duration_minutes=25.0, message="Pomodoro session complete!")

        # 30 second quick timer
        set_timer(duration_minutes=0.5, message="Quick reminder")
    """
    logger.info(f"[MICRO ACTIONS] Tool: set_timer(duration_minutes={duration_minutes}, message='{message}')")

    try:
        # Validate input
        if duration_minutes is None or duration_minutes <= 0:
            return {
                "error": True,
                "error_type": "InvalidInput",
                "error_message": "Duration must be greater than 0",
                "retry_possible": True
            }

        # Set reasonable max duration (24 hours) to prevent abuse
        MAX_DURATION_MINUTES = 24 * 60
        if duration_minutes > MAX_DURATION_MINUTES:
            return {
                "error": True,
                "error_type": "InvalidInput",
                "error_message": f"Duration exceeds maximum of {MAX_DURATION_MINUTES} minutes (24 hours)",
                "retry_possible": True,
                "max_duration_minutes": MAX_DURATION_MINUTES
            }

        # Convert minutes to seconds for the delay
        duration_seconds = int(duration_minutes * 60)

        # Default message
        timer_message = message or "Timer expired"

        # Escape message for AppleScript
        message_escaped = _escape_applescript(timer_message)

        # Build AppleScript to display notification after delay
        # Use double quotes for the AppleScript string to avoid shell escaping issues
        notification_script = f'display notification "{message_escaped}" with title "Timer" sound name "Glass"'
        
        # Create a shell command that sleeps then runs the notification
        # Use double quotes for osascript -e to properly escape the AppleScript
        # Detach process properly to prevent zombie processes
        shell_cmd = f'sleep {duration_seconds} && osascript -e "{notification_script}"'
        
        # Execute in background using subprocess.Popen with proper process detachment
        # Use start_new_session=True to detach from parent process group
        # This prevents zombie processes and ensures cleanup
        process = subprocess.Popen(
            shell_cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True  # Detach from parent process group
        )
        
        # Don't wait for process - it will complete in the background
        # Process will be cleaned up automatically by the OS when it completes

        logger.info(f"Timer set for {duration_minutes} minutes ({duration_seconds} seconds)")
        return {
            "success": True,
            "status": "set",
            "duration_minutes": duration_minutes,
            "duration_seconds": duration_seconds,
            "message": timer_message,
            "expires_at_approx": f"In {duration_minutes} minutes",
            "notification_message": timer_message
        }

    except Exception as e:
        logger.error(f"[MICRO ACTIONS] Error in set_timer: {e}")
        return {
            "error": True,
            "error_type": "TimerError",
            "error_message": str(e),
            "retry_possible": False
        }


def _escape_applescript(text: str) -> str:
    """
    Escape text for AppleScript.

    Args:
        text: Text to escape

    Returns:
        Escaped text safe for AppleScript
    """
    if not text:
        return ""

    # Escape backslashes first (must be first!)
    text = text.replace('\\', '\\\\')
    # Escape quotes
    text = text.replace('"', '\\"')
    # Handle newlines
    text = text.replace('\n', '\\n')
    # Handle carriage returns
    text = text.replace('\r', '\\r')
    # Handle tabs
    text = text.replace('\t', '\\t')

    return text


# Micro Actions Agent Tool Registry
MICRO_ACTIONS_AGENT_TOOLS = [
    launch_app,
    copy_snippet,
    set_timer,
]


# Micro Actions Agent Hierarchy
MICRO_ACTIONS_AGENT_HIERARCHY = """
Micro Actions Agent Hierarchy:
==============================

LEVEL 1: Quick Utilities
├─ launch_app(app_name: str)
│  → Launch a macOS application by name
│  → Uses 'open -a' command for fast app launching
│  → Handles app name variations automatically
│
├─ copy_snippet(text: str)
│  → Copy text to macOS clipboard
│  → Uses pbcopy command (standard macOS utility)
│  → Fast and reliable clipboard operations
│
└─ set_timer(duration_minutes: float, message: Optional[str])
   → Set a timer with notification when it expires
   → Uses AppleScript with background process
   → Displays notification when timer completes

Input Parameters:
  • launch_app:
    - app_name (required): Application name (e.g., "Safari", "Notes", "Calculator")
  
  • copy_snippet:
    - text (required): Text content to copy to clipboard
  
  • set_timer:
    - duration_minutes (required): Duration in minutes (can be decimal, e.g., 0.5 for 30 seconds)
    - message (optional): Message to display when timer expires (default: "Timer expired")

Typical Workflows:
1. launch_app(app_name="Safari")
   → Opens Safari browser

2. copy_snippet(text="https://example.com")
   → Copies URL to clipboard for pasting

3. set_timer(duration_minutes=25.0, message="Pomodoro complete!")
   → Sets 25-minute timer, notifies when done

Use Cases:
✓ Quick app launching ("launch Notes")
✓ Clipboard operations ("copy this text")
✓ Time management ("set a 10 minute timer")
✓ Workflow automation (launch app → copy snippet → set reminder)
✓ Pomodoro timers and productivity tracking

Features:
- Lightweight: Uses simple system commands (open, pbcopy, osascript)
- Fast: No heavy infrastructure, direct system calls
- Reliable: Built on macOS native utilities
- Non-blocking: Timer runs in background
- Simple: Easy to use for everyday tasks

Example 1 - Launch app:
launch_app(app_name="Safari")
→ Opens Safari browser

Example 2 - Copy text:
copy_snippet(text="Meeting at 3pm")
→ Copies text to clipboard

Example 3 - Set timer:
set_timer(duration_minutes=5.0, message="Coffee break!")
→ Sets 5-minute timer, notifies when done

Example 4 - Quick timer (30 seconds):
set_timer(duration_minutes=0.5, message="Quick reminder")
→ Sets 30-second timer

Example 5 - Pomodoro timer:
set_timer(duration_minutes=25.0, message="Pomodoro session complete! Take a 5-minute break.")
→ Sets 25-minute Pomodoro timer
"""


class MicroActionsAgent:
    """
    Micro Actions Agent - Mini-orchestrator for everyday utilities.

    Responsibilities:
    - Launching applications quickly
    - Clipboard operations
    - Timer/reminder management

    This agent provides lightweight, fast micro-actions for daily productivity
    without requiring heavy infrastructure. Built on simple AppleScript/open calls.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in MICRO_ACTIONS_AGENT_TOOLS}
        logger.info(f"[MICRO ACTIONS AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> list:
        """Get all micro actions agent tools."""
        return MICRO_ACTIONS_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get micro actions agent hierarchy documentation."""
        return MICRO_ACTIONS_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a micro actions agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Micro actions agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[MICRO ACTIONS AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[MICRO ACTIONS AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }

