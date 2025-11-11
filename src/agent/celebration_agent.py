"""
Celebration Agent - Triggers celebratory confetti effects on macOS.

This agent is responsible for:
- Triggering confetti celebration effects
- Using emoji notification spam for visual celebration
- Optional voice announcements

Uses AppleScript to trigger macOS celebration effects.
"""

from typing import Dict, Any
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)


@tool
def trigger_confetti() -> Dict[str, Any]:
    """
    Trigger celebratory confetti effects using emoji notification spam.

    Use this tool when you need to:
    - Celebrate a task completion
    - Trigger confetti effects
    - Show celebratory notifications
    - Create a fun celebration moment

    This is useful for:
    - Task completion celebrations ("confetti", "celebrate", "party")
    - Success celebrations ("we did it!", "success!")
    - Fun moments ("let's celebrate")

    Returns:
        Dictionary with success status and message

    Examples:
        # Trigger confetti
        trigger_confetti()

        # User says "/confetti" or "celebrate"
        → trigger_confetti()
    """
    logger.info("[CELEBRATION AGENT] Tool: trigger_confetti()")

    try:
        from ..automation import CelebrationAutomation
        from ..utils import load_config

        config = load_config()
        celebration = CelebrationAutomation(config)

        result = celebration.trigger_confetti()

        if result.get("success"):
            return {
                "success": True,
                "action": "confetti",
                "status": "celebrated",
                "message": result.get("message", "Confetti celebration triggered! 🎉")
            }
        else:
            return result

    except Exception as e:
        logger.error(f"[CELEBRATION AGENT] Error in trigger_confetti: {e}")
        return {
            "error": True,
            "error_type": "CelebrationError",
            "error_message": f"Failed to trigger confetti: {str(e)}",
            "retry_possible": True
        }


# Tool exports
CELEBRATION_AGENT_TOOLS = [trigger_confetti]

# Agent hierarchy documentation
CELEBRATION_AGENT_HIERARCHY = """
CELEBRATION AGENT (1 tool)
Domain: Celebratory effects and fun interactions
└─ Tools:
   └─ trigger_confetti - Trigger celebratory confetti effects with emoji notifications
"""


class CelebrationAgent:
    """
    Celebration Agent - Triggers celebratory effects.

    This agent handles fun celebratory effects through macOS automation.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = CELEBRATION_AGENT_TOOLS
        logger.info("[CELEBRATION AGENT] Initialized")

    def get_tools(self):
        """Get all Celebration agent tools."""
        return CELEBRATION_AGENT_TOOLS

    def execute(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a Celebration tool.

        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters

        Returns:
            Tool execution result
        """
        logger.info(f"[CELEBRATION AGENT] Executing tool: {tool_name}")

        tool_map = {
            "trigger_confetti": trigger_confetti,
        }

        tool = tool_map.get(tool_name)
        if not tool:
            return {
                "error": True,
                "error_type": "UnknownTool",
                "error_message": f"Unknown tool: {tool_name}",
                "available_tools": list(tool_map.keys())
            }

        try:
            result = tool.invoke(parameters)
            return result
        except Exception as e:
            logger.error(f"[CELEBRATION AGENT] Tool execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e)
            }

