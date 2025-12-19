"""
Shortcuts Agent - Handles running macOS Shortcuts.

This agent is responsible for:
- Running named shortcuts with optional input
- Listing available shortcuts
- Using AppleScript to interact with Shortcuts Events

Acts as a mini-orchestrator for macOS Shortcuts operations.
"""

from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
import logging

from src.automation.shortcuts_automation import ShortcutsAutomation

logger = logging.getLogger(__name__)

# Singleton automation instance
_shortcuts_automation: Optional[ShortcutsAutomation] = None


def _get_shortcuts_automation(config: Optional[Dict[str, Any]] = None) -> ShortcutsAutomation:
    """Get or create the shortcuts automation instance."""
    global _shortcuts_automation
    if _shortcuts_automation is None:
        _shortcuts_automation = ShortcutsAutomation(config)
    return _shortcuts_automation


@tool
def run_shortcut(
    name: str,
    input_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run a macOS Shortcut by name.

    Use this tool when you need to:
    - Execute a user-defined automation workflow
    - Run a shortcut with optional text input
    - Trigger complex automations the user has created

    Args:
        name: The exact name of the shortcut to run (case-sensitive)
        input_text: Optional text input to pass to the shortcut

    Returns:
        Dictionary with:
        - success: True if shortcut ran successfully
        - shortcut_name: Name of the shortcut
        - output: Any output from the shortcut

    Example:
        run_shortcut(name="Resize Images", input_text="800x600")
        run_shortcut(name="Daily Backup")
    """
    logger.info(f"[SHORTCUTS AGENT] Tool: run_shortcut(name='{name}')")

    try:
        automation = _get_shortcuts_automation()
        result = automation.run_shortcut(name, input_text)
        return result

    except Exception as e:
        logger.error(f"[SHORTCUTS AGENT] Error in run_shortcut: {e}")
        return {
            "error": True,
            "error_type": "ShortcutExecutionError",
            "error_message": str(e),
            "shortcut_name": name,
            "retry_possible": False
        }


@tool
def list_shortcuts() -> Dict[str, Any]:
    """
    List all available macOS Shortcuts.

    Use this tool when you need to:
    - See what shortcuts are available on the system
    - Help user find the exact name of a shortcut
    - Verify a shortcut exists before running it

    Returns:
        Dictionary with:
        - success: True if list was retrieved
        - shortcuts: List of shortcut objects with name and folder
        - count: Number of shortcuts found

    Example:
        list_shortcuts()
        # Returns: {"success": True, "shortcuts": [{"name": "Daily Backup", "folder": ""}, ...], "count": 15}
    """
    logger.info("[SHORTCUTS AGENT] Tool: list_shortcuts()")

    try:
        automation = _get_shortcuts_automation()
        result = automation.list_shortcuts()
        return result

    except Exception as e:
        logger.error(f"[SHORTCUTS AGENT] Error in list_shortcuts: {e}")
        return {
            "error": True,
            "error_type": "ShortcutListError",
            "error_message": str(e),
            "retry_possible": False
        }


# Shortcuts Agent Tool Registry
SHORTCUTS_AGENT_TOOLS = [
    run_shortcut,
    list_shortcuts,
]


# Shortcuts Agent Hierarchy
SHORTCUTS_AGENT_HIERARCHY = """
Shortcuts Agent Hierarchy:
=========================

LEVEL 1: Shortcut Execution
├─ run_shortcut(name: str, input_text: Optional[str]) → Execute a shortcut
└─ list_shortcuts() → List all available shortcuts

Input Parameters:
  • run_shortcut:
    - name (required): Exact name of the shortcut (case-sensitive)
    - input_text (optional): Text input to pass to the shortcut
  • list_shortcuts:
    - No parameters

Output Format:
  • run_shortcut success:
    {"success": True, "shortcut_name": "...", "output": "..."}
  • list_shortcuts success:
    {"success": True, "shortcuts": [{"name": "...", "folder": ""}], "count": N}

Typical Workflow:
1. list_shortcuts() → See available shortcuts
2. run_shortcut(name="Daily Backup") → Run a specific shortcut

Use Cases:
✓ Execute user-defined automation workflows
✓ Run complex multi-step automations
✓ Trigger shortcuts with custom input
✓ Discover available shortcuts on the system

Features:
- Uses macOS Shortcuts Events for automation
- Supports passing text input to shortcuts
- Returns shortcut output when available
- Proper error handling with retry hints

Example 1 - List shortcuts:
list_shortcuts()
→ {"success": True, "shortcuts": [{"name": "Morning Routine"}, {"name": "Resize Images"}], "count": 2}

Example 2 - Run shortcut without input:
run_shortcut(name="Daily Backup")
→ {"success": True, "shortcut_name": "Daily Backup", "output": "Backup completed"}

Example 3 - Run shortcut with input:
run_shortcut(name="Resize Images", input_text="1920x1080")
→ {"success": True, "shortcut_name": "Resize Images", "output": "5 images resized"}
"""


class ShortcutsAgent:
    """
    Shortcuts Agent - Mini-orchestrator for macOS Shortcuts operations.

    Responsibilities:
    - Running named shortcuts
    - Listing available shortcuts
    - Managing shortcut execution with input

    This agent acts as a sub-orchestrator that handles all Shortcuts tasks.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in SHORTCUTS_AGENT_TOOLS}
        # Initialize the automation with config
        global _shortcuts_automation
        _shortcuts_automation = ShortcutsAutomation(config)
        logger.info(f"[SHORTCUTS AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        """Get all Shortcuts agent tools."""
        return SHORTCUTS_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get Shortcuts agent hierarchy documentation."""
        return SHORTCUTS_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Shortcuts agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Shortcuts agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[SHORTCUTS AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[SHORTCUTS AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }
