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
from typing import Dict, Any, Optional, Union
from datetime import datetime

from ..utils.screenshot import get_screenshot_dir

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
        self.screenshot_dir = get_screenshot_dir(config)

    def capture_screen(
        self,
        app_name: Optional[str] = None,
        window_title: Optional[str] = None,
        output_path: Optional[str] = None,
        mode: str = "full",
        region: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Capture a screenshot of the screen, window, or region.

        Args:
            app_name: Name of application to capture (e.g., "Stocks", "Safari", "Notes")
                     Used for focused window capture
            window_title: Optional specific window title to capture (best-effort filter)
            output_path: Custom output path (if None, auto-generates)
            mode: Capture mode - "full" (entire screen), "focused" (app window), "region" (specific coords)
            region: For mode="region", dict with x, y, width, height keys

        Returns:
            Dictionary with screenshot_path, success status

        Examples:
            # Capture entire screen
            capture_screen()

            # Capture focused Stock app window
            capture_screen(app_name="Stocks", mode="focused")

            # Capture Safari window
            capture_screen(app_name="Safari", mode="focused")

            # Capture specific region
            capture_screen(mode="region", region={"x": 100, "y": 100, "width": 800, "height": 600})
        """
        logger.info(f"[SCREEN CAPTURE] Capturing: mode={mode}, app={app_name}, window={window_title}, region={region}")

        try:
            # Generate output path if not provided
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if mode == "focused" and app_name:
                    filename = f"{app_name}_{timestamp}.png"
                elif mode == "region":
                    filename = f"region_{timestamp}.png"
                else:
                    filename = f"screen_{timestamp}.png"
                output_path = str(self.screenshot_dir / filename)

            # Route to appropriate capture method based on mode
            if mode == "focused":
                if not app_name and not window_title:
                    return {
                        "success": False,
                        "error": True,
                        "error_message": "focused mode requires app_name or window_title parameter",
                        "retry_possible": False
                    }
                result = self._capture_focused_window(app_name, window_title, output_path)
            elif mode == "region":
                if region is None:
                    return {
                        "success": False,
                        "error": True,
                        "error_message": "region parameter required for mode='region'",
                        "retry_possible": False
                    }
                result = self.capture_region(
                    region["x"], region["y"], region["width"], region["height"], output_path
                )
            elif mode == "full":
                result = self._capture_full_screen(output_path)
            else:
                return {
                    "success": False,
                    "error": True,
                    "error_message": f"Invalid mode: {mode}. Must be 'full', 'focused', or 'region'",
                    "retry_possible": False
                }

            # Legacy support: if mode is "full" but app_name/window_title provided, use focused
            if mode == "full" and (app_name or window_title):
                logger.warning("Legacy usage: app_name/window_title provided with mode='full'. Using mode='focused' instead.")
                result = self._capture_focused_window(app_name, window_title, output_path)

            if result["success"]:
                logger.info(f"[SCREEN CAPTURE] Screenshot saved: {output_path}")
                return {
                    "screenshot_path": output_path,
                    "success": True,
                    "app_name": app_name,
                    "mode": mode,
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

    def _capture_focused_window(
        self,
        app_name: Optional[str],
        window_title: Optional[str],
        output_path: str
    ) -> Dict[str, Any]:
        """
        Capture a focused application window using multiple fallback strategies.

        Strategy 1: Quartz CGWindowID (preferred - captures exact window)
        Strategy 2: AppleScript bounds (fallback - captures window region)
        Strategy 3: Full screen with app activated (last resort)

        Args:
            app_name: Application name to capture
            window_title: Window title filter (best-effort)
            output_path: Where to save screenshot

        Returns:
            Result dictionary
        """
        try:
            # Strategy 1: Use Quartz to find and capture specific window by CGWindowID
            try:
                import Quartz

                # Get list of all windows
                window_list = Quartz.CGWindowListCopyWindowInfo(
                    Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
                    Quartz.kCGNullWindowID
                )

                # Find the target window
                target_window_id = None
                for window in window_list:
                    owner = window.get('kCGWindowOwnerName', '')
                    if app_name and owner == app_name:
                        window_layer = window.get('kCGWindowLayer', -1)
                        # Get the frontmost window (layer 0)
                        if window_layer == 0:
                            target_window_id = window.get('kCGWindowNumber')
                            logger.info(f"Found {app_name} window with CGWindowID: {target_window_id}")
                            break
                    elif window_title:
                        window_name = window.get('kCGWindowName', '')
                        if window_title.lower() in window_name.lower():
                            target_window_id = window.get('kCGWindowNumber')
                            logger.info(f"Found window '{window_name}' with CGWindowID: {target_window_id}")
                            break

                if target_window_id:
                    # Capture the specific window using CGWindowID
                    logger.info(f"Capturing window (CGWindowID: {target_window_id})")

                    # Use -o flag to remove shadow from window capture
                    capture_cmd = [
                        "screencapture",
                        "-l", str(target_window_id),  # Capture specific window by CGWindowID
                        "-x",  # No sound
                        "-o",  # No shadow
                        "-t", "png",
                        output_path
                    ]

                    result = subprocess.run(capture_cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        logger.info(f"Focused window screenshot saved: {output_path}")
                        return {
                            "success": True,
                            "screenshot_path": output_path
                        }
                    else:
                        logger.warning(f"CGWindowID capture failed: {result.stderr}")

            except ImportError:
                logger.warning("Quartz/PyObjC not available, skipping CGWindowID method")
            except Exception as e:
                logger.warning(f"CGWindow method failed: {e}, trying AppleScript bounds")

            # Strategy 2: Use AppleScript to get window bounds and capture region
            try:
                if app_name:
                    # Activate app first
                    activate_script = f'''
                    tell application "{app_name}"
                        activate
                        delay 0.5
                    end tell
                    '''
                    subprocess.run(
                        ["osascript", "-e", activate_script],
                        capture_output=True,
                        text=True
                    )

                    # Get window bounds
                    bounds_script = f'''
                    tell application "System Events"
                        tell process "{app_name}"
                            set frontWindow to window 1
                            get bounds of frontWindow
                        end tell
                    end tell
                    '''

                    result = subprocess.run(
                        ["osascript", "-e", bounds_script],
                        capture_output=True,
                        text=True
                    )

                    if result.returncode == 0 and result.stdout.strip():
                        # Parse bounds: {x, y, width, height} -> x,y,width,height
                        bounds_str = result.stdout.strip()
                        # Remove curly braces and split by comma
                        coords = bounds_str.strip('{}').split(',')
                        if len(coords) == 4:
                            x, y, w, h = [int(c.strip()) for c in coords]
                            logger.info(f"Window bounds: x={x}, y={y}, w={w}, h={h}")

                            # Capture the region
                            capture_cmd = [
                                "screencapture",
                                "-x",  # No sound
                                "-R", f"{x},{y},{w},{h}",  # Capture specific region
                                "-t", "png",
                                output_path
                            ]

                            result = subprocess.run(capture_cmd, capture_output=True, text=True)
                            if result.returncode == 0:
                                logger.info(f"Window region screenshot saved: {output_path}")
                                return {
                                    "success": True,
                                    "screenshot_path": output_path
                                }
                            else:
                                logger.warning(f"Region capture failed: {result.stderr}")

            except Exception as e:
                logger.warning(f"AppleScript bounds method failed: {e}, using full-screen fallback")

            # Strategy 3: Full screen fallback with app activated
            logger.info("Using full-screen fallback with app activated")

            if app_name:
                # Ensure app is activated
                subprocess.run(
                    ["osascript", "-e", f'tell application "{app_name}" to activate'],
                    capture_output=True
                )
                import time
                time.sleep(0.8)

            # Capture full screen with cursor (since app is now frontmost)
            capture_cmd = ["screencapture", "-x", "-C", "-t", "png", output_path]

            result = subprocess.run(capture_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"Full-screen fallback screenshot saved: {output_path}")
                return {
                    "success": True,
                    "screenshot_path": output_path
                }
            else:
                logger.error(f"All capture strategies failed: {result.stderr}")
                return {
                    "success": False,
                    "error": f"All capture strategies failed: {result.stderr}"
                }

        except Exception as e:
            logger.error(f"Focused window capture failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

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
