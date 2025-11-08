"""
Email Agent - Handles all email operations.

This agent is responsible for:
- Composing emails
- Sending emails
- Managing attachments

Acts as a mini-orchestrator for email-related operations.
"""

from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)


@tool
def compose_email(
    subject: str,
    body: str,
    recipient: Optional[str] = None,
    attachments: Optional[List[str]] = None,
    send: bool = False
) -> Dict[str, Any]:
    """
    Create and optionally send an email via Mail.app.

    EMAIL AGENT - LEVEL 1: Email Composition
    Use this to create and send emails.

    Args:
        subject: Email subject
        body: Email body (supports markdown)
        recipient: Email address (None = draft only)
        attachments: List of file paths to attach
        send: If True, send immediately; if False, open draft

    Returns:
        Dictionary with status ('sent' or 'draft')
    """
    logger.info(f"[EMAIL AGENT] Tool: compose_email(subject='{subject}', recipient='{recipient}', send={send})")

    try:
        from automation import MailComposer
        from utils import load_config

        config = load_config()
        mail_composer = MailComposer(config)

        success = mail_composer.compose_email(
            subject=subject,
            body=body,
            recipient=recipient,
            attachment_paths=attachments,
            send_immediately=send
        )

        if success:
            return {
                "status": "sent" if send else "draft",
                "message": f"Email {'sent' if send else 'drafted'} successfully"
            }
        else:
            return {
                "error": True,
                "error_type": "MailError",
                "error_message": "Failed to compose email",
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"[EMAIL AGENT] Error in compose_email: {e}")
        return {
            "error": True,
            "error_type": "MailError",
            "error_message": str(e),
            "retry_possible": False
        }


# Email Agent Tool Registry
EMAIL_AGENT_TOOLS = [
    compose_email,
]


# Email Agent Hierarchy
EMAIL_AGENT_HIERARCHY = """
Email Agent Hierarchy:
=====================

LEVEL 1: Email Composition
└─ compose_email → Create and send emails via Mail.app

Typical Workflow:
1. compose_email(subject, body, recipient, attachments, send=True)

Note: This is a simple agent with a single primary tool.
Future enhancements could include:
- Reading emails
- Searching mailbox
- Managing folders
- Filtering and rules
"""


class EmailAgent:
    """
    Email Agent - Mini-orchestrator for email operations.

    Responsibilities:
    - Composing emails
    - Sending emails
    - Managing attachments

    This agent acts as a sub-orchestrator that handles all email-related tasks.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in EMAIL_AGENT_TOOLS}
        logger.info(f"[EMAIL AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        """Get all email agent tools."""
        return EMAIL_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get email agent hierarchy documentation."""
        return EMAIL_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an email agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Email agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[EMAIL AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[EMAIL AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }
