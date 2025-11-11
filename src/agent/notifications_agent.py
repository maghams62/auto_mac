"""
Notifications Agent - Handles system notifications on macOS.

This agent is responsible for:
- Sending system notifications via Notification Center
- Using AppleScript to interact with macOS notification system
- Supporting titles, messages, sounds, and optional actions

Based on AppleScript MCP best practices with improved error handling.
"""

from typing import Dict, Any, Optional, List
from langchain_core.tools import tool
import logging
import subprocess

logger = logging.getLogger(__name__)


@tool
def send_notification(
    title: str,
    message: str,
    sound: Optional[str] = None,
    subtitle: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send a system notification via macOS Notification Center.

    Use this tool when you need to:
    - Alert the user of task completion
    - Notify about important events or errors
    - Send time-sensitive updates
    - Display status messages

    This is useful for:
    - Background task completion (e.g., "Report generated successfully")
    - Error notifications (e.g., "Failed to send email")
    - Progress updates (e.g., "File processing complete")
    - Reminders and alerts

    Args:
        title: Notification title (required, shown in bold)
        message: Notification body text (required, main content)
        sound: Optional sound name (e.g., "default", "Glass", "Hero", "Submarine")
               Use None for silent notification
        subtitle: Optional subtitle (shown between title and message)

    Returns:
        Dictionary with status and notification details

    Examples:
        # Simple notification
        send_notification(
            title="Task Complete",
            message="Your stock report has been generated"
        )

        # With sound
        send_notification(
            title="Email Sent",
            message="Message delivered to recipient",
            sound="Glass"
        )

        # With subtitle
        send_notification(
            title="Automation Update",
            subtitle="Trip Planning",
            message="Your LA to Phoenix route is ready",
            sound="default"
        )

    Available sounds: default, Basso, Blow, Bottle, Frog, Funk, Glass, Hero,
                     Morse, Ping, Pop, Purr, Sosumi, Submarine, Tink
    """
    logger.info(f"[NOTIFICATIONS AGENT] Tool: send_notification(title='{title}')")

    try:
        # Validate inputs
        if not title or len(title.strip()) == 0:
            return {
                "error": True,
                "error_type": "InvalidInput",
                "error_message": "Notification title cannot be empty",
                "retry_possible": True
            }

        if not message or len(message.strip()) == 0:
            return {
                "error": True,
                "error_type": "InvalidInput",
                "error_message": "Notification message cannot be empty",
                "retry_possible": True
            }

        # Send the notification
        result = _send_notification_applescript(
            title=title,
            message=message,
            sound=sound,
            subtitle=subtitle
        )

        if result.get("success"):
            return {
                "status": "sent",
                "title": title,
                "message": message,
                "subtitle": subtitle,
                "sound": sound or "silent",
                "delivery": "macOS Notification Center",
                "message_length": len(message)
            }
        else:
            return {
                "error": True,
                "error_type": "NotificationFailed",
                "error_message": result.get("error_message", "Failed to send notification"),
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"[NOTIFICATIONS AGENT] Error in send_notification: {e}")
        return {
            "error": True,
            "error_type": "NotificationError",
            "error_message": str(e),
            "retry_possible": False
        }


def _send_notification_applescript(
    title: str,
    message: str,
    sound: Optional[str] = None,
    subtitle: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send notification using AppleScript.

    Args:
        title: Notification title
        message: Notification message
        sound: Optional sound name
        subtitle: Optional subtitle

    Returns:
        Dictionary with success status
    """
    # Escape strings for AppleScript
    title_escaped = _escape_applescript(title)
    message_escaped = _escape_applescript(message)
    subtitle_escaped = _escape_applescript(subtitle) if subtitle else None

    # Build AppleScript with try-catch for better error handling
    # Use osascript -e "display notification" which is the modern approach
    applescript_parts = []

    applescript_parts.append('try')

    # Build notification command
    notification_cmd = f'display notification "{message_escaped}" with title "{title_escaped}"'

    if subtitle_escaped:
        notification_cmd += f' subtitle "{subtitle_escaped}"'

    if sound:
        # Validate sound name (basic validation)
        valid_sounds = [
            "default", "Basso", "Blow", "Bottle", "Frog", "Funk", "Glass",
            "Hero", "Morse", "Ping", "Pop", "Purr", "Sosumi", "Submarine", "Tink"
        ]
        if sound in valid_sounds:
            notification_cmd += f' sound name "{sound}"'
        else:
            logger.warning(f"Invalid sound name: {sound}, using default")
            notification_cmd += ' sound name "default"'

    applescript_parts.append(f'    {notification_cmd}')
    applescript_parts.append('    return "Success"')
    applescript_parts.append('on error errMsg')
    applescript_parts.append('    return "Error: " & errMsg')
    applescript_parts.append('end try')

    applescript = '\n'.join(applescript_parts)

    try:
        # Execute AppleScript
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            output = result.stdout.strip()
            if "Error:" in output:
                logger.error(f"Notification AppleScript error: {output}")
                return {
                    "success": False,
                    "error_message": output
                }

            logger.info(f"Successfully sent notification: {title}")
            return {"success": True}
        else:
            logger.error(f"Failed to send notification: {result.stderr}")
            return {
                "success": False,
                "error_message": result.stderr
            }

    except subprocess.TimeoutExpired:
        logger.error("Notification send timeout")
        return {
            "success": False,
            "error_message": "Notification timeout"
        }
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return {
            "success": False,
            "error_message": str(e)
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

    # Escape backslashes first
    text = text.replace('\\', '\\\\')
    # Escape quotes
    text = text.replace('"', '\\"')
    # Handle newlines
    text = text.replace('\n', '\\n')

    return text


# Notifications Agent Tool Registry
NOTIFICATIONS_AGENT_TOOLS = [
    send_notification,
]


# Notifications Agent Hierarchy
NOTIFICATIONS_AGENT_HIERARCHY = """
Notifications Agent Hierarchy:
==============================

LEVEL 1: System Notifications
└─ send_notification(title: str, message: str, sound: Optional[str], subtitle: Optional[str])
   → Send system notification via Notification Center

Input Parameters:
  • title (required): Notification title (shown in bold)
  • message (required): Notification body text
  • sound (optional): Sound name ("default", "Glass", "Hero", "Submarine", etc.)
                      Omit for silent notification
  • subtitle (optional): Subtitle between title and message

Typical Workflow:
1. send_notification(
     title="Task Complete",
     message="Your report is ready",
     sound="Glass"
   )
   → Displays notification with sound

Use Cases:
✓ Background task completion alerts
✓ Error and warning notifications
✓ Progress updates and status messages
✓ Time-sensitive alerts
✓ Workflow completion confirmations

Features:
- macOS Notification Center integration
- Custom sounds (15 built-in options)
- Optional subtitles
- Silent mode (no sound parameter)
- Non-blocking (doesn't interrupt user)
- Visible in Notification Center history

Available Sounds:
  • default - Standard notification sound
  • Basso, Blow, Bottle - Low frequency sounds
  • Frog, Funk - Playful sounds
  • Glass, Hero - Alert sounds
  • Morse, Ping, Pop - Short beeps
  • Purr, Sosumi, Submarine, Tink - Distinctive sounds

Example 1 - Simple notification:
send_notification(
    title="Stock Report Ready",
    message="AAPL report generated successfully"
)

Example 2 - With sound:
send_notification(
    title="Email Sent",
    message="Message delivered to recipient",
    sound="Glass"
)

Example 3 - With subtitle:
send_notification(
    title="Automation Update",
    subtitle="Trip Planning",
    message="Your route from LA to Phoenix is ready",
    sound="Hero"
)

Example 4 - Silent notification:
send_notification(
    title="Background Task",
    message="File processing complete",
    sound=None
)
"""


class NotificationsAgent:
    """
    Notifications Agent - Mini-orchestrator for system notifications.

    Responsibilities:
    - Sending system notifications via Notification Center
    - Managing notification sounds and formatting
    - Providing non-blocking user alerts

    This agent acts as a sub-orchestrator that handles all notification tasks.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in NOTIFICATIONS_AGENT_TOOLS}
        logger.info(f"[NOTIFICATIONS AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        """Get all notifications agent tools."""
        return NOTIFICATIONS_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get notifications agent hierarchy documentation."""
        return NOTIFICATIONS_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a notifications agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Notifications agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[NOTIFICATIONS AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[NOTIFICATIONS AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }
