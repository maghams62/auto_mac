"""
System Control Agent - Handles macOS system controls.

This agent is responsible for:
- Setting system volume
- Toggling dark mode
- Managing Do Not Disturb (optional)

Acts as a mini-orchestrator for system control operations.
"""

from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
import logging

from src.automation.system_control_automation import SystemControlAutomation

logger = logging.getLogger(__name__)

# Singleton automation instance
_system_control_automation: Optional[SystemControlAutomation] = None


def _get_system_control_automation(config: Optional[Dict[str, Any]] = None) -> SystemControlAutomation:
    """Get or create the system control automation instance."""
    global _system_control_automation
    if _system_control_automation is None:
        _system_control_automation = SystemControlAutomation(config)
    return _system_control_automation


@tool
def set_volume(level: int) -> Dict[str, Any]:
    """
    Set the system output volume.

    Use this tool when you need to:
    - Adjust system volume
    - Mute the system (set to 0)
    - Set volume to a specific level

    Args:
        level: Volume level from 0 to 100 (0 = muted, 100 = max)

    Returns:
        Dictionary with:
        - success: True if volume was set
        - volume_level: The new volume level
        - muted: True if volume is 0

    Example:
        set_volume(level=50)  # Set to 50%
        set_volume(level=0)   # Mute
        set_volume(level=100) # Maximum volume
    """
    logger.info(f"[SYSTEM CONTROL AGENT] Tool: set_volume(level={level})")

    try:
        automation = _get_system_control_automation()
        result = automation.set_volume(level)
        return result

    except Exception as e:
        logger.error(f"[SYSTEM CONTROL AGENT] Error in set_volume: {e}")
        return {
            "error": True,
            "error_type": "SystemControlError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def toggle_dark_mode() -> Dict[str, Any]:
    """
    Toggle system dark mode on or off.

    Use this tool when you need to:
    - Switch between light and dark mode
    - Toggle the system appearance

    Returns:
        Dictionary with:
        - success: True if dark mode was toggled
        - dark_mode: True if dark mode is now on, False if off
        - message: Human-readable status message

    Example:
        toggle_dark_mode()
        # Returns: {"success": True, "dark_mode": True, "message": "Dark mode is now on"}
    """
    logger.info("[SYSTEM CONTROL AGENT] Tool: toggle_dark_mode()")

    try:
        automation = _get_system_control_automation()
        result = automation.toggle_dark_mode()
        return result

    except Exception as e:
        logger.error(f"[SYSTEM CONTROL AGENT] Error in toggle_dark_mode: {e}")
        return {
            "error": True,
            "error_type": "SystemControlError",
            "error_message": str(e),
            "retry_possible": False
        }


# System Control Agent Tool Registry
SYSTEM_CONTROL_AGENT_TOOLS = [
    set_volume,
    toggle_dark_mode,
]


# System Control Agent Hierarchy
SYSTEM_CONTROL_AGENT_HIERARCHY = """
System Control Agent Hierarchy:
==============================

LEVEL 1: System Controls
├─ set_volume(level: int) → Set system volume (0-100)
└─ toggle_dark_mode() → Toggle dark/light mode

Input Parameters:
  • set_volume:
    - level (required): Volume level 0-100 (0 = muted, 100 = max)
  • toggle_dark_mode:
    - No parameters

Output Format:
  • set_volume success:
    {"success": True, "volume_level": 50, "muted": False}
  • toggle_dark_mode success:
    {"success": True, "dark_mode": True, "message": "Dark mode is now on"}

Typical Workflow:
1. set_volume(level=50) → Set volume to 50%
2. toggle_dark_mode() → Switch appearance mode

Use Cases:
✓ Adjust system volume for presentations
✓ Mute system quickly
✓ Switch to dark mode for evening work
✓ Switch to light mode for daytime

Features:
- Direct system volume control
- Dark mode toggle via System Events
- Volume clamping (0-100)
- Proper error handling

Example 1 - Set volume to 50%:
set_volume(level=50)
→ {"success": True, "volume_level": 50, "muted": False}

Example 2 - Mute system:
set_volume(level=0)
→ {"success": True, "volume_level": 0, "muted": True}

Example 3 - Toggle dark mode:
toggle_dark_mode()
→ {"success": True, "dark_mode": True, "message": "Dark mode is now on"}
"""


class SystemControlAgent:
    """
    System Control Agent - Mini-orchestrator for macOS system control operations.

    Responsibilities:
    - Setting system volume
    - Toggling dark mode
    - Managing system appearance

    This agent acts as a sub-orchestrator that handles all system control tasks.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in SYSTEM_CONTROL_AGENT_TOOLS}
        # Initialize the automation with config
        global _system_control_automation
        _system_control_automation = SystemControlAutomation(config)
        logger.info(f"[SYSTEM CONTROL AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        """Get all System Control agent tools."""
        return SYSTEM_CONTROL_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get System Control agent hierarchy documentation."""
        return SYSTEM_CONTROL_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a System Control agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"System Control agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[SYSTEM CONTROL AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[SYSTEM CONTROL AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }
