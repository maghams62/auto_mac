"""
macOS System Control automation using AppleScript.

This module provides automation for system-level controls like volume,
dark mode, and Do Not Disturb.
"""

import logging
import os
import json
from typing import Dict, Any, Optional

from ..utils.applescript_utils import run_applescript, format_applescript_error, escape_applescript_string

logger = logging.getLogger(__name__)


class SystemControlAutomation:
    """
    Automates macOS system controls using AppleScript.

    Provides methods to:
    - Set system volume
    - Toggle dark mode
    - Set Do Not Disturb (optional)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize System Control automation.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.fake_data_path = os.getenv("SYSTEM_CONTROL_FAKE_DATA_PATH")

    def set_volume(self, level: int) -> Dict[str, Any]:
        """
        Set the system output volume.

        Args:
            level: Volume level from 0 to 100

        Returns:
            Dictionary with success status and current volume
        """
        # Clamp volume to valid range
        level = max(0, min(100, level))
        logger.info(f"[SYSTEM CONTROL] Setting volume to {level}")

        # Check for fake data path for testing
        if self.fake_data_path and os.path.exists(self.fake_data_path):
            logger.info(f"Using fake system control data from: {self.fake_data_path}")
            return {
                "success": True,
                "volume_level": level,
                "muted": level == 0
            }

        try:
            script = self._build_set_volume_applescript(level)
            result, user_error = run_applescript(script, timeout=10)

            if result.returncode == 0:
                output = result.stdout.strip()

                # Check for error in output
                if output.startswith("Error:"):
                    error_msg = output[6:].strip()
                    logger.error(f"[SYSTEM CONTROL] Volume error: {error_msg}")
                    return {
                        "success": False,
                        "error": True,
                        "error_type": "SystemControlError",
                        "error_message": error_msg,
                        "retry_possible": True
                    }

                logger.info(f"[SYSTEM CONTROL] Successfully set volume to {level}")
                return {
                    "success": True,
                    "volume_level": level,
                    "muted": level == 0
                }
            else:
                logger.error(f"[SYSTEM CONTROL] Failed to set volume: {result.stderr}")
                error_info = format_applescript_error(
                    result,
                    f"set volume to {level}",
                    "System",
                    user_error
                )
                return {
                    "success": False,
                    "error": True,
                    "error_type": error_info.get("error_type", "SystemControlError"),
                    "error_message": error_info.get("error_message", "Unknown error"),
                    "retry_possible": error_info.get("retry_possible", True)
                }

        except Exception as e:
            logger.error(f"[SYSTEM CONTROL] Error setting volume: {e}")
            return {
                "success": False,
                "error": True,
                "error_type": "SystemControlError",
                "error_message": str(e),
                "retry_possible": False
            }

    def get_volume(self) -> Dict[str, Any]:
        """
        Get the current system output volume.

        Returns:
            Dictionary with current volume level
        """
        logger.info("[SYSTEM CONTROL] Getting current volume")

        try:
            script = '''
try
    set currentVolume to output volume of (get volume settings)
    return currentVolume as text
on error errMsg
    return "Error: " & errMsg
end try
'''
            result, user_error = run_applescript(script, timeout=10)

            if result.returncode == 0:
                output = result.stdout.strip()

                if output.startswith("Error:"):
                    return {
                        "success": False,
                        "error": True,
                        "error_type": "SystemControlError",
                        "error_message": output[6:].strip(),
                        "retry_possible": True
                    }

                try:
                    volume = int(output)
                    return {
                        "success": True,
                        "volume_level": volume,
                        "muted": volume == 0
                    }
                except ValueError:
                    return {
                        "success": False,
                        "error": True,
                        "error_type": "ParseError",
                        "error_message": f"Could not parse volume: {output}",
                        "retry_possible": True
                    }
            else:
                error_info = format_applescript_error(
                    result,
                    "get volume",
                    "System",
                    user_error
                )
                return {
                    "success": False,
                    "error": True,
                    "error_type": error_info.get("error_type", "SystemControlError"),
                    "error_message": error_info.get("error_message", "Unknown error"),
                    "retry_possible": error_info.get("retry_possible", True)
                }

        except Exception as e:
            logger.error(f"[SYSTEM CONTROL] Error getting volume: {e}")
            return {
                "success": False,
                "error": True,
                "error_type": "SystemControlError",
                "error_message": str(e),
                "retry_possible": False
            }

    def toggle_dark_mode(self) -> Dict[str, Any]:
        """
        Toggle system dark mode on/off.

        Returns:
            Dictionary with success status and new dark mode state
        """
        logger.info("[SYSTEM CONTROL] Toggling dark mode")

        # Check for fake data path for testing
        if self.fake_data_path and os.path.exists(self.fake_data_path):
            logger.info(f"Using fake system control data from: {self.fake_data_path}")
            return {
                "success": True,
                "dark_mode": True,
                "message": "Dark mode toggled"
            }

        try:
            script = self._build_toggle_dark_mode_applescript()
            result, user_error = run_applescript(script, timeout=10)

            if result.returncode == 0:
                output = result.stdout.strip()

                if output.startswith("Error:"):
                    error_msg = output[6:].strip()
                    logger.error(f"[SYSTEM CONTROL] Dark mode error: {error_msg}")
                    return {
                        "success": False,
                        "error": True,
                        "error_type": "SystemControlError",
                        "error_message": error_msg,
                        "retry_possible": True
                    }

                # Parse the result to determine new state
                is_dark = output.lower() == "true"
                logger.info(f"[SYSTEM CONTROL] Dark mode is now: {'on' if is_dark else 'off'}")
                return {
                    "success": True,
                    "dark_mode": is_dark,
                    "message": f"Dark mode is now {'on' if is_dark else 'off'}"
                }
            else:
                logger.error(f"[SYSTEM CONTROL] Failed to toggle dark mode: {result.stderr}")
                error_info = format_applescript_error(
                    result,
                    "toggle dark mode",
                    "System Preferences",
                    user_error
                )
                return {
                    "success": False,
                    "error": True,
                    "error_type": error_info.get("error_type", "SystemControlError"),
                    "error_message": error_info.get("error_message", "Unknown error"),
                    "retry_possible": error_info.get("retry_possible", True)
                }

        except Exception as e:
            logger.error(f"[SYSTEM CONTROL] Error toggling dark mode: {e}")
            return {
                "success": False,
                "error": True,
                "error_type": "SystemControlError",
                "error_message": str(e),
                "retry_possible": False
            }

    def set_do_not_disturb(self, enabled: bool) -> Dict[str, Any]:
        """
        Set Do Not Disturb mode.

        Note: Direct DND control is limited in macOS. This method returns a
        "not implemented" error recommending the use of a Shortcut instead.

        Args:
            enabled: True to enable DND, False to disable

        Returns:
            Dictionary with error status explaining limitation
        """
        logger.info(f"[SYSTEM CONTROL] Setting Do Not Disturb to {'on' if enabled else 'off'}")

        # Check for fake data path for testing
        if self.fake_data_path and os.path.exists(self.fake_data_path):
            logger.info(f"Using fake system control data from: {self.fake_data_path}")
            return {
                "success": True,
                "do_not_disturb": enabled,
                "message": f"Do Not Disturb is now {'on' if enabled else 'off'}"
            }

        # Direct DND control is not reliably available via AppleScript on modern macOS
        # Return an explicit "not implemented" error with guidance
        logger.warning("[SYSTEM CONTROL] Do Not Disturb control is not implemented via AppleScript")
        return {
            "success": False,
            "error": True,
            "error_type": "NotImplemented",
            "error_message": (
                "Do Not Disturb cannot be controlled directly via AppleScript on modern macOS. "
                "To toggle DND, create a macOS Shortcut that controls Focus modes, then use "
                "/shortcut run 'Your DND Shortcut Name' to execute it."
            ),
            "retry_possible": False,
            "workaround": "Create a Shortcut to toggle Focus/DND and run it via the Shortcuts agent"
        }

    def _build_set_volume_applescript(self, level: int) -> str:
        """Build AppleScript to set system volume."""
        script = f'''
try
    set volume output volume {level}
    return "Success"
on error errMsg
    return "Error: " & errMsg
end try
'''
        return script

    def _build_toggle_dark_mode_applescript(self) -> str:
        """Build AppleScript to toggle dark mode."""
        script = '''
try
    tell application "System Events"
        tell appearance preferences
            set dark mode to not dark mode
            return dark mode as text
        end tell
    end tell
on error errMsg
    return "Error: " & errMsg
end try
'''
        return script

    def _build_set_dnd_applescript(self, enabled: bool) -> str:
        """Build AppleScript to set Do Not Disturb."""
        # Note: This uses a workaround since direct DND control is limited
        # On newer macOS, Focus modes would need to be controlled via shortcuts
        action = "true" if enabled else "false"
        script = f'''
try
    -- Note: Direct DND control is limited in macOS
    -- This is a placeholder that returns success
    -- For full DND control, consider using a Shortcut
    return "Success"
on error errMsg
    return "Error: " & errMsg
end try
'''
        return script

    def test_system_control_integration(self) -> bool:
        """
        Test if system controls are accessible.

        Returns:
            True if system controls are accessible, False otherwise
        """
        try:
            script = '''
            set vol to output volume of (get volume settings)
            return vol as text
            '''
            result, _ = run_applescript(script, timeout=5)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"System control integration test failed: {e}")
            return False
