"""
macOS Shortcuts.app integration using AppleScript.

This module provides automation for running and listing macOS Shortcuts,
allowing programmatic execution of user-defined workflows.
"""

import logging
import os
import json
from typing import Dict, Any, Optional, List

from ..utils.applescript_utils import run_applescript, format_applescript_error, escape_applescript_string

logger = logging.getLogger(__name__)


class ShortcutsAutomation:
    """
    Automates macOS Shortcuts app using AppleScript.

    Provides methods to:
    - Run named shortcuts with optional input
    - List available shortcuts
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Shortcuts automation.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.fake_data_path = os.getenv("SHORTCUTS_FAKE_DATA_PATH")

    def run_shortcut(
        self,
        name: str,
        input_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run a named shortcut.

        Args:
            name: Name of the shortcut to run
            input_text: Optional input text to pass to the shortcut

        Returns:
            Dictionary with success status and output
        """
        logger.info(f"[SHORTCUTS AUTOMATION] Running shortcut: {name}")

        # Check for fake data path for testing
        if self.fake_data_path and os.path.exists(self.fake_data_path):
            logger.info(f"Using fake shortcuts data from: {self.fake_data_path}")
            return self._load_fake_run_result(name)

        try:
            script = self._build_run_shortcut_applescript(name, input_text)
            result, user_error = run_applescript(script, timeout=60)

            if result.returncode == 0:
                output = result.stdout.strip()

                # Check for error in output (from try/on error block)
                if output.startswith("Error:"):
                    error_msg = output[6:].strip()
                    logger.error(f"[SHORTCUTS AUTOMATION] Shortcut error: {error_msg}")
                    return {
                        "success": False,
                        "error": True,
                        "error_type": "ShortcutExecutionError",
                        "error_message": error_msg,
                        "shortcut_name": name,
                        "retry_possible": True
                    }

                logger.info(f"[SHORTCUTS AUTOMATION] Successfully ran shortcut: {name}")
                return {
                    "success": True,
                    "shortcut_name": name,
                    "output": output if output else "Shortcut completed successfully"
                }
            else:
                logger.error(f"[SHORTCUTS AUTOMATION] Failed to run shortcut: {result.stderr}")
                error_info = format_applescript_error(
                    result,
                    f"run shortcut '{name}'",
                    "Shortcuts.app",
                    user_error
                )
                return {
                    "success": False,
                    "error": True,
                    "error_type": error_info.get("error_type", "ShortcutExecutionError"),
                    "error_message": error_info.get("error_message", "Unknown error"),
                    "shortcut_name": name,
                    "retry_possible": error_info.get("retry_possible", True)
                }

        except Exception as e:
            logger.error(f"[SHORTCUTS AUTOMATION] Error running shortcut: {e}")
            return {
                "success": False,
                "error": True,
                "error_type": "ShortcutExecutionError",
                "error_message": str(e),
                "shortcut_name": name,
                "retry_possible": False
            }

    def list_shortcuts(self) -> Dict[str, Any]:
        """
        List all available shortcuts.

        Returns:
            Dictionary with success status and list of shortcuts
        """
        logger.info("[SHORTCUTS AUTOMATION] Listing available shortcuts")

        # Check for fake data path for testing
        if self.fake_data_path and os.path.exists(self.fake_data_path):
            logger.info(f"Using fake shortcuts data from: {self.fake_data_path}")
            return self._load_fake_list_result()

        try:
            script = self._build_list_shortcuts_applescript()
            result, user_error = run_applescript(script, timeout=30)

            if result.returncode == 0:
                output = result.stdout.strip()

                # Check for error in output
                if output.startswith("Error:"):
                    error_msg = output[6:].strip()
                    logger.error(f"[SHORTCUTS AUTOMATION] List error: {error_msg}")
                    return {
                        "success": False,
                        "error": True,
                        "error_type": "ShortcutListError",
                        "error_message": error_msg,
                        "retry_possible": True
                    }

                shortcuts = self._parse_shortcuts_list(output)
                logger.info(f"[SHORTCUTS AUTOMATION] Found {len(shortcuts)} shortcuts")
                return {
                    "success": True,
                    "shortcuts": shortcuts,
                    "count": len(shortcuts)
                }
            else:
                logger.error(f"[SHORTCUTS AUTOMATION] Failed to list shortcuts: {result.stderr}")
                error_info = format_applescript_error(
                    result,
                    "list shortcuts",
                    "Shortcuts.app",
                    user_error
                )
                return {
                    "success": False,
                    "error": True,
                    "error_type": error_info.get("error_type", "ShortcutListError"),
                    "error_message": error_info.get("error_message", "Unknown error"),
                    "retry_possible": error_info.get("retry_possible", True)
                }

        except Exception as e:
            logger.error(f"[SHORTCUTS AUTOMATION] Error listing shortcuts: {e}")
            return {
                "success": False,
                "error": True,
                "error_type": "ShortcutListError",
                "error_message": str(e),
                "retry_possible": False
            }

    def _build_run_shortcut_applescript(
        self,
        name: str,
        input_text: Optional[str] = None
    ) -> str:
        """Build AppleScript to run a shortcut."""
        name_escaped = escape_applescript_string(name)

        if input_text:
            input_escaped = escape_applescript_string(input_text)
            script = f'''
try
    tell application "Shortcuts Events"
        set shortcutResult to run shortcut "{name_escaped}" with input "{input_escaped}"
        return shortcutResult as text
    end tell
on error errMsg
    return "Error: " & errMsg
end try
'''
        else:
            script = f'''
try
    tell application "Shortcuts Events"
        set shortcutResult to run shortcut "{name_escaped}"
        return shortcutResult as text
    end tell
on error errMsg
    return "Error: " & errMsg
end try
'''

        return script

    def _build_list_shortcuts_applescript(self) -> str:
        """Build AppleScript to list all shortcuts."""
        script = '''
try
    tell application "Shortcuts Events"
        set shortcutNames to {}
        set allShortcuts to every shortcut
        repeat with s in allShortcuts
            set end of shortcutNames to name of s
        end repeat
        set AppleScript's text item delimiters to "|||"
        return shortcutNames as text
    end tell
on error errMsg
    return "Error: " & errMsg
end try
'''
        return script

    def _parse_shortcuts_list(self, output: str) -> List[Dict[str, str]]:
        """Parse AppleScript output into list of shortcut dictionaries."""
        if not output or not output.strip():
            return []

        names = output.split("|||")
        shortcuts = []

        for name in names:
            name = name.strip()
            if name:
                shortcuts.append({
                    "name": name,
                    "folder": ""  # Shortcuts app doesn't expose folder info via AppleScript
                })

        return shortcuts

    def _load_fake_run_result(self, name: str) -> Dict[str, Any]:
        """Load fake run result from JSON file for testing."""
        try:
            with open(self.fake_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "run_result" in data:
                    result = data["run_result"]
                    result["shortcut_name"] = name
                    return result
                return {
                    "success": True,
                    "shortcut_name": name,
                    "output": "Fake shortcut completed"
                }
        except Exception as e:
            logger.error(f"Error loading fake data: {e}")
            return {
                "success": True,
                "shortcut_name": name,
                "output": "Fake shortcut completed"
            }

    def _load_fake_list_result(self) -> Dict[str, Any]:
        """Load fake list result from JSON file for testing."""
        try:
            with open(self.fake_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "shortcuts" in data:
                    return {
                        "success": True,
                        "shortcuts": data["shortcuts"],
                        "count": len(data["shortcuts"])
                    }
                return {
                    "success": True,
                    "shortcuts": [],
                    "count": 0
                }
        except Exception as e:
            logger.error(f"Error loading fake data: {e}")
            return {
                "success": True,
                "shortcuts": [],
                "count": 0
            }

    def test_shortcuts_integration(self) -> bool:
        """
        Test if Shortcuts app is accessible.

        Returns:
            True if Shortcuts app is accessible, False otherwise
        """
        try:
            script = '''
            tell application "Shortcuts Events"
                return name
            end tell
            '''
            result, _ = run_applescript(script, timeout=5)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Shortcuts integration test failed: {e}")
            return False
