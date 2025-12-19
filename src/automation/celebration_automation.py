"""
Celebration Automation - Trigger celebratory confetti effects on macOS using AppleScript.
"""

import subprocess
import logging
from typing import Dict, Any
from ..utils.message_personality import get_confetti_message

logger = logging.getLogger(__name__)


class CelebrationAutomation:
    """Automate celebratory effects on macOS for confetti celebrations."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def trigger_confetti(self) -> Dict[str, Any]:
        """
        Trigger confetti celebration effects using emoji notification spam.

        Returns:
            Dictionary with success status and message
        """
        logger.info("[CELEBRATION AUTOMATION] Triggering confetti effects")

        try:
            # Main confetti effect: emoji notification spam for 2-3 seconds
            applescript = '''
            set endTime to (current date) + 2.5
            repeat while (current date) < endTime
                display notification "🎉🎊🥳✨" with title "Celebrate"
                delay 0.1
            end repeat
            
            -- Optional voice announcement (try with default voice, ignore errors)
            try
                say "Celebration time!"
            on error
                -- Voice announcement failed, that's okay
            end try
            '''

            result = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "action": "confetti",
                    "message": get_confetti_message(),
                    "status": "celebrated"
                }
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                logger.error(f"[CELEBRATION AUTOMATION] Confetti failed: {error_msg}")
                return {
                    "success": False,
                    "error": True,
                    "error_type": "CelebrationError",
                    "error_message": f"Failed to trigger confetti: {error_msg}",
                    "retry_possible": True
                }

        except subprocess.TimeoutExpired:
            logger.error("[CELEBRATION AUTOMATION] Confetti command timed out")
            return {
                "success": False,
                "error": True,
                "error_type": "TimeoutError",
                "error_message": "Confetti command timed out",
                "retry_possible": True
            }
        except Exception as e:
            logger.error(f"[CELEBRATION AUTOMATION] Error triggering confetti: {e}")
            return {
                "success": False,
                "error": True,
                "error_type": "CelebrationError",
                "error_message": f"Error triggering confetti: {str(e)}",
                "retry_possible": True
            }

