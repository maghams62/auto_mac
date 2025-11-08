"""
iMessage Agent - Handles sending messages via iMessage on macOS.

This agent is responsible for:
- Sending text messages via iMessage
- Using AppleScript to interact with Messages.app
- Supporting both phone numbers and email addresses

Acts as a mini-orchestrator for iMessage operations.
"""

from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
import logging
import subprocess

logger = logging.getLogger(__name__)


def _send_imessage_applescript(recipient: str, message: str) -> bool:
    """
    Send an iMessage using AppleScript.

    Args:
        recipient: Phone number (e.g., "+16618572957") or email
        message: Message text to send

    Returns:
        True if successful, False otherwise
    """
    # Escape message for AppleScript (handle quotes and newlines)
    message_escaped = message.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

    # Improved AppleScript - simpler approach using send text
    applescript = f'''
    tell application "Messages"
        set myMessage to "{message_escaped}"
        set myBuddy to "{recipient}"
        send myMessage to buddy myBuddy of service "E:icloud.com"
    end tell
    '''

    try:
        # Execute AppleScript
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            logger.info(f"Successfully sent iMessage to {recipient}")
            return True
        else:
            logger.error(f"Failed to send iMessage: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("iMessage send timeout")
        return False
    except Exception as e:
        logger.error(f"Error sending iMessage: {e}")
        return False


@tool
def send_imessage(
    message: str,
    recipient: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send a text message via iMessage on macOS.

    **PREFERRED METHOD for sending Maps URLs, trip details, and quick messages to user.**

    Use this tool when you need to:
    - Send Maps URLs to the user's phone (HIGHLY RECOMMENDED for trips)
    - Send trip details, route information, or travel plans
    - Share any information via text message
    - Send quick notifications or updates

    This is BETTER than email for:
    - Maps URLs (can be opened directly on iPhone)
    - Time-sensitive information
    - Quick updates and notifications

    Args:
        message: The message text to send (supports URLs, emojis, newlines)
        recipient: Phone number (e.g., "+16618572957") or email address.
                  If None, uses default from config (+16618572957).

    Returns:
        Dictionary with status and message details

    Example:
        send_imessage(
            message="Your trip from Phoenix to LA is planned! Maps URL: maps://...",
            recipient="+16618572957"
        )
    """
    logger.info(f"[IMESSAGE AGENT] Tool: send_imessage(recipient='{recipient}')")

    try:
        from ..utils import load_config

        # Get recipient from config if not provided
        if recipient is None:
            config = load_config()
            recipient = config.get("imessage", {}).get("default_phone_number")

            if not recipient:
                return {
                    "error": True,
                    "error_type": "NoRecipient",
                    "error_message": "No recipient specified and no default configured",
                    "retry_possible": True
                }

        # Validate message
        if not message or len(message.strip()) == 0:
            return {
                "error": True,
                "error_type": "EmptyMessage",
                "error_message": "Message cannot be empty",
                "retry_possible": True
            }

        # Send the message
        success = _send_imessage_applescript(recipient, message)

        if success:
            return {
                "status": "sent",
                "recipient": recipient,
                "message": message,
                "message_length": len(message),
                "delivery": "iMessage via Messages.app"
            }
        else:
            return {
                "error": True,
                "error_type": "SendFailed",
                "error_message": "Failed to send iMessage (check Messages.app permissions)",
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"[IMESSAGE AGENT] Error in send_imessage: {e}")
        return {
            "error": True,
            "error_type": "iMessageError",
            "error_message": str(e),
            "retry_possible": False
        }


# iMessage Agent Tool Registry
IMESSAGE_AGENT_TOOLS = [
    send_imessage,
]


# iMessage Agent Hierarchy
IMESSAGE_AGENT_HIERARCHY = """
iMessage Agent Hierarchy:
========================

LEVEL 1: Text Messaging (iMessage/SMS)
└─ send_imessage(message: str, recipient: Optional[str]) → Send text via iMessage

DIFFERENT FROM EMAIL AGENT:
- Email Agent: compose_email(subject, body, recipient, attachments, send)
  └─ For formal communication with subject lines and attachments

- iMessage Agent: send_imessage(message, recipient)
  └─ For quick messages, Maps URLs, instant notifications
  └─ PREFERRED for Maps URLs (opens directly on iPhone)

Input Parameters:
  • message (required): Text to send (supports URLs, emojis, newlines)
  • recipient (optional): Phone number "+16618572957" or email
                         If None, uses default: +16618572957

Typical Workflow:
1. send_imessage(
     message="Trip planned! Maps: https://maps.google.com/...",
     recipient="+16618572957"  # or None for default
   )
   → Sends text message via Messages.app

Use Cases:
✓ Send Maps URLs to user's phone (HIGHLY RECOMMENDED)
✓ Quick trip notifications
✓ Time-sensitive updates
✓ Any text message to phone

Features:
- Direct phone number messaging
- Uses macOS Messages.app (iMessage/SMS)
- Default recipient: +16618572957 (from config)
- Supports emojis, URLs, multiline messages
- AppleScript automation

Example 1 - With default recipient:
send_imessage(message="Your trip is ready! maps://...")

Example 2 - With specific recipient:
send_imessage(
    message="Meeting at 3pm",
    recipient="+11234567890"
)
"""


class iMessageAgent:
    """
    iMessage Agent - Mini-orchestrator for iMessage operations.

    Responsibilities:
    - Sending text messages via iMessage
    - Using Messages.app on macOS
    - Managing default recipients

    This agent acts as a sub-orchestrator that handles all iMessage tasks.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in IMESSAGE_AGENT_TOOLS}
        logger.info(f"[IMESSAGE AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        """Get all iMessage agent tools."""
        return IMESSAGE_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get iMessage agent hierarchy documentation."""
        return IMESSAGE_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an iMessage agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"iMessage agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[IMESSAGE AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[IMESSAGE AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }
