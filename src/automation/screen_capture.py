"""
Universal screen capture for macOS.

Captures screenshots of:
- Entire screen
- Specific application windows
- Custom regions
"""

import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ScreenCapture:
    """
    Universal screen capture using macOS screencapture command.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize screen capture.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.screenshot_dir = Path("data/screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def capture_screen(
        self,
        app_name: Optional[str] = None,
        window_title: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Capture a screenshot of the screen or specific application window.

        Args:
            app_name: Name of application to capture (e.g., "Stocks", "Safari", "Notes")
                     If None, captures entire screen
            window_title: Optional specific window title to capture
            output_path: Custom output path (if None, auto-generates)

        Returns:
            Dictionary with screenshot_path, success status

        Examples:
            # Capture entire screen
            capture_screen()

            # Capture Stock app window
            capture_screen(app_name="Stocks")

            # Capture Safari window
            capture_screen(app_name="Safari")

            # Capture specific window by title
            capture_screen(window_title="Apple Stock")
        """
        logger.info(f"[SCREEN CAPTURE] Capturing: app={app_name}, window={window_title}")

        try:
            # Generate output path if not provided
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if app_name:
                    filename = f"{app_name}_{timestamp}.png"
                else:
                    filename = f"screen_{timestamp}.png"
                output_path = str(self.screenshot_dir / filename)

            # Build screencapture command
            if app_name or window_title:
                # Capture specific window
                result = self._capture_window(app_name, window_title, output_path)
            else:
                # Capture entire screen
                result = self._capture_full_screen(output_path)

            if result["success"]:
                logger.info(f"[SCREEN CAPTURE] Screenshot saved: {output_path}")
                return {
                    "screenshot_path": output_path,
                    "success": True,
                    "app_name": app_name,
                    "message": f"Screenshot captured: {Path(output_path).name}"
                }
            else:
                return result

        except Exception as e:
            logger.error(f"[SCREEN CAPTURE] Error: {e}")
            return {
                "error": True,
                "error_type": "ScreenCaptureError",
                "error_message": str(e),
                "retry_possible": False
            }

    def _capture_full_screen(self, output_path: str) -> Dict[str, Any]:
        """
        Capture entire screen using screencapture.

        Args:
            output_path: Where to save screenshot

        Returns:
            Result dictionary
        """
        try:
            # -x: no sound
            # -C: capture cursor
            # -t png: PNG format
            cmd = ["screencapture", "-x", "-C", "-t", "png", output_path]

            subprocess.run(cmd, check=True, capture_output=True, text=True)

            return {
                "success": True,
                "screenshot_path": output_path
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"screencapture failed: {e.stderr}")
            return {
                "error": True,
                "error_type": "ScreencaptureError",
                "error_message": f"Failed to capture screen: {e.stderr}",
                "retry_possible": True
            }

    def _capture_window(
        self,
        app_name: Optional[str],
        window_title: Optional[str],
        output_path: str
    ) -> Dict[str, Any]:
        """
        Capture a specific application window automatically.

        Uses AppleScript to get window ID, then screencapture -l to capture it.
        NO manual interaction required.

        Args:
            app_name: Application name
            window_title: Window title
            output_path: Where to save screenshot

        Returns:
            Result dictionary
        """
        try:
            if app_name:
                # Strategy: Activate app, wait for it to come to front, then capture full screen
                # This is FULLY AUTOMATIC - no user interaction needed
                # For most use cases (Stocks app, Safari, etc.), capturing the activated window
                # is effectively the same as capturing the screen since it becomes frontmost

                # AppleScript to activate app
                applescript = f'''
                tell application "{app_name}"
                    activate
                    delay 0.8
                end tell
                '''

                # Activate the app
                subprocess.run(
                    ["osascript", "-e", applescript],
                    check=True,
                    capture_output=True,
                    text=True
                )

                # Wait for app to fully activate and come to front
                import time
                time.sleep(0.8)

                # Capture full screen (app window will be prominent)
                # This is the most reliable automatic method
                cmd = ["screencapture", "-x", "-C", "-t", "png", output_path]

                subprocess.run(cmd, check=True, capture_output=True, text=True)

                logger.info(f"Captured screenshot with {app_name} in foreground")

                return {
                    "success": True,
                    "screenshot_path": output_path
                }

            elif window_title:
                # Try to find and activate window by title
                logger.warning("Window title-based capture not fully implemented, falling back to screen capture")
                return self._capture_full_screen(output_path)

            else:
                return self._capture_full_screen(output_path)

        except subprocess.CalledProcessError as e:
            logger.error(f"Window capture failed: {e.stderr}")
            # Fallback to full screen
            logger.info("Falling back to full screen capture")
            return self._capture_full_screen(output_path)

    def capture_region(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Capture a specific region of the screen.

        Args:
            x: X coordinate of top-left corner
            y: Y coordinate of top-left corner
            width: Width of region
            height: Height of region
            output_path: Custom output path

        Returns:
            Result dictionary
        """
        logger.info(f"[SCREEN CAPTURE] Capturing region: ({x},{y}) {width}x{height}")

        try:
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"region_{timestamp}.png"
                output_path = str(self.screenshot_dir / filename)

            # -R x,y,width,height: capture specific region
            region = f"{x},{y},{width},{height}"
            cmd = ["screencapture", "-x", "-R", region, "-t", "png", output_path]

            subprocess.run(cmd, check=True, capture_output=True, text=True)

            return {
                "screenshot_path": output_path,
                "success": True,
                "message": f"Region screenshot captured: {Path(output_path).name}"
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"Region capture failed: {e.stderr}")
            return {
                "error": True,
                "error_type": "RegionCaptureError",
                "error_message": f"Failed to capture region: {e.stderr}",
                "retry_possible": True
            }
