"""
Reply agent and tool for crafting user-facing messages.
"""

from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)


def _format_duplicate_details(duplicates: List[Dict[str, Any]]) -> str:
    """
    Format duplicate file details into human-readable text.

    Args:
        duplicates: List of duplicate groups from folder_find_duplicates

    Returns:
        Formatted string with group details and file names
    """
    if not duplicates:
        return "No duplicate groups found."

    lines = []
    for idx, group in enumerate(duplicates, 1):
        files = group.get("files", [])
        size = group.get("size", 0)
        count = group.get("count", len(files))

        # Format size
        if size >= 1024 * 1024:
            size_str = f"{size / (1024 * 1024):.2f} MB"
        elif size >= 1024:
            size_str = f"{size / 1024:.2f} KB"
        else:
            size_str = f"{size} bytes"

        lines.append(f"\nGroup {idx} ({count} copies, {size_str} each):")
        for file in files:
            file_name = file.get("name", "unknown")
            lines.append(f"  - {file_name}")

    return "\n".join(lines)


@tool
def reply_to_user(
    message: str,
    details: Optional[str] = None,
    artifacts: Optional[List[str]] = None,
    status: str = "success",
    action_type: Optional[str] = None,
    summary: Optional[str] = None,
    artifact_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Compose the final UI-facing reply message with rich completion event data.

    Use this as the last step after completing all required actions so the
    interface can present a concise, human-friendly summary instead of
    raw JSON results.

    Args:
        message: Main message to surface to the user.
        details: Optional secondary context (bullet list, next steps).
        artifacts: Optional list of paths or URLs to highlight.
        status: Overall outcome indicator (success|partial_success|info|error).
        action_type: Type of action completed (e.g., 'email_sent', 'report_created', 'presentation_created').
        summary: Brief summary of what was accomplished (for completion cards).
        artifact_metadata: Rich metadata about artifacts (e.g., {'recipients': [...], 'file_type': 'pdf', 'file_size': 12345}).

    Returns:
        Structured payload recorded in step_results so the UI can render it.
    """
    artifacts = artifacts or []
    details = details or ""
    artifact_metadata = artifact_metadata or {}

    # AUTO-FORMAT: If details is a list (structured data), format it nicely
    if isinstance(details, list):
        logger.info("[REPLY TOOL] Details is a list, checking if it needs formatting")

        # Check if this looks like duplicate file data
        if details and isinstance(details[0], dict) and "files" in details[0]:
            logger.info("[REPLY TOOL] Detected duplicate file data, formatting...")
            details = _format_duplicate_details(details)
        else:
            # Generic list formatting
            details = "\n".join(f"  - {item}" for item in details)

    payload: Dict[str, Any] = {
        "type": "reply",
        "message": message,
        "details": details,
        "artifacts": artifacts,
        "status": status,
        "error": False,
    }

    # Add completion event data if action_type is provided
    if action_type:
        payload["completion_event"] = {
            "action_type": action_type,
            "summary": summary or message,
            "status": status,
            "artifact_metadata": artifact_metadata,
            "artifacts": artifacts
        }
        logger.info("[REPLY TOOL] Added completion_event: %s", payload["completion_event"])

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
