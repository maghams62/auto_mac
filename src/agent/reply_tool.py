"""
Reply agent and tool for crafting user-facing messages.
"""

from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)


@tool
def reply_to_user(
    message: str,
    details: str = "",
    artifacts: Optional[List[str]] = None,
    status: str = "success"
) -> Dict[str, Any]:
    """
    Compose the final UI-facing reply message.

    Use this as the last step after completing all required actions so the
    interface can present a concise, human-friendly summary instead of
    raw JSON results.

    Args:
        message: Main message to surface to the user.
        details: Optional secondary context (bullet list, next steps).
        artifacts: Optional list of paths or URLs to highlight.
        status: Overall outcome indicator (success|partial_success|info|error).

    Returns:
        Structured payload recorded in step_results so the UI can render it.
    """
    artifacts = artifacts or []

    payload: Dict[str, Any] = {
        "type": "reply",
        "message": message,
        "details": details,
        "artifacts": artifacts,
        "status": status,
        "error": False,
    }

    logger.info("[REPLY TOOL] Prepared reply payload: %s", payload)
    return payload


REPLY_AGENT_TOOLS = [reply_to_user]


REPLY_AGENT_HIERARCHY = """
Reply Agent Hierarchy:
=====================

LEVEL 1: Reply Composition
└─ reply_to_user → Create the final user-facing message with optional details and artifacts.

Typical Workflow:
1. Complete all action-oriented steps (search, extract, compose, etc.)
2. Call reply_to_user with the high-level message, supporting details, and outputs to highlight
3. UI consumes this payload instead of raw JSON tool outputs

Use this tool to guarantee consistent, human-friendly responses.
"""


class ReplyAgent:
    """
    Reply agent that exposes the reply_to_user tool.

    Keeps a consistent surface for generating UI-facing responses across workflows.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in REPLY_AGENT_TOOLS}
        logger.info("[REPLY AGENT] Initialized")

    def get_tools(self) -> List:
        """Return registered reply tools."""
        return REPLY_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Return hierarchy documentation."""
        return REPLY_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a reply tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Reply agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        try:
            return tool.invoke(inputs)
        except Exception as exc:  # Defensive: propagate structured failure
            logger.error("[REPLY AGENT] Execution error: %s", exc)
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(exc),
                "retry_possible": False
            }
