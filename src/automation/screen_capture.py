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

    def _get_frontmost_application(self) -> Optional[str]:
        """
        Get the name of the currently frontmost/active application.

        Returns:
            Application name (e.g., "Safari", "Cerebros OS", "Stocks") or None if detection fails
        """
        try:
            applescript = '''
            tell application "System Events"
                set frontApp to name of first application process whose frontmost is true
                return frontApp
            end tell
            '''
            
            result = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                app_name = result.stdout.strip()
                logger.info(f"[SCREEN CAPTURE] Detected frontmost application: {app_name}")
                return app_name
            else:
                logger.warning(f"Failed to detect frontmost app: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.warning("Timeout while detecting frontmost application")
            return None
        except Exception as e:
            logger.warning(f"Error detecting frontmost application: {e}")
            return None

    def _validate_screenshot(self, output_path: str, expected_app: Optional[str] = None) -> bool:
        """
        Validate that a screenshot file was created successfully and is not empty.
        
        Args:
            output_path: Path to screenshot file
            expected_app: Optional app name for logging
            
        Returns:
            True if screenshot is valid, False otherwise
        """
        try:
            output_file = Path(output_path)
            if not output_file.exists():
                logger.warning(f"Screenshot validation failed: File does not exist: {output_path}")
                return False
            
            file_size = output_file.stat().st_size
            if file_size == 0:
                logger.warning(f"Screenshot validation failed: File is empty: {output_path}")
                return False
            
            # Basic validation: file should be at least a few KB for a valid screenshot
            if file_size < 1024:  # Less than 1KB is suspicious
                logger.warning(f"Screenshot validation failed: File too small ({file_size} bytes): {output_path}")
                return False
            
            logger.info(f"Screenshot validation passed: {output_path} ({file_size} bytes)")
            return True
            
        except Exception as e:
            logger.warning(f"Screenshot validation error: {e}")
            return False

    def _get_frontmost_window_id(self) -> Optional[int]:
        """
        Get the CGWindowID of the frontmost window using Quartz.

        Returns:
            CGWindowID as integer, or None if detection fails
        """
        try:
            import Quartz
            
            # Get list of all windows
            window_list = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
                Quartz.kCGNullWindowID
            )
            
            # Find the frontmost window (layer 0)
            for window in window_list:
                window_layer = window.get('kCGWindowLayer', -1)
                if window_layer == 0:
                    window_id = window.get('kCGWindowNumber')
                    owner = window.get('kCGWindowOwnerName', '')
                    logger.info(f"[SCREEN CAPTURE] Found frontmost window: CGWindowID={window_id}, owner={owner}")
                    return window_id
            
            logger.warning("No frontmost window found (layer 0)")
            return None
            
        except ImportError:
            logger.warning("Quartz/PyObjC not available for window ID detection")
            return None
        except Exception as e:
            logger.warning(f"Error getting frontmost window ID: {e}")
            return None

    def capture_screen(
        self,
        app_name: Optional[str] = None,
        window_title: Optional[str] = None,
        output_path: Optional[str] = None,
        mode: Optional[str] = None,
        region: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Capture a screenshot of the screen, window, or region.

        Args:
            app_name: Name of application to capture (e.g., "Stocks", "Safari", "Notes", "Cerebros OS")
                     Used for focused window capture. If None and mode="focused", auto-detects frontmost app.
            window_title: Optional specific window title to capture (best-effort filter)
            output_path: Custom output path (if None, auto-generates)
            mode: Capture mode - "focused" (app window, default), "full" (entire screen), "region" (specific coords)
            region: For mode="region", dict with x, y, width, height keys

        Returns:
            Dictionary with screenshot_path, success status

        Examples:
            # Capture focused window (auto-detects frontmost app like Cerebros OS)
            capture_screen()

            # Capture focused Stock app window
            capture_screen(app_name="Stocks", mode="focused")

            # Capture Safari window
            capture_screen(app_name="Safari", mode="focused")

            # Capture entire desktop
            capture_screen(mode="full")

            # Capture specific region
            capture_screen(mode="region", region={"x": 100, "y": 100, "width": 800, "height": 600})
        """
        # Default to "focused" mode if not specified
        if mode is None:
            mode = "focused"
        elif isinstance(mode, str):
            # Normalize common aliases (LLM may suggest "full_screen")
            normalized = mode.strip().lower()
            if normalized in {"full_screen", "fullscreen"}:
                logger.info("[SCREEN CAPTURE] Normalized mode 'full_screen' → 'full'")
                mode = "full"
            else:
                mode = normalized
        
        logger.info(f"[SCREEN CAPTURE] Capturing: mode={mode}, app={app_name}, window={window_title}, region={region}")

        try:
            # Auto-detect frontmost app if mode="focused" and no app_name provided
            detected_app_name = app_name
            if mode == "focused" and not app_name and not window_title:
                detected_app_name = self._get_frontmost_application()
                if detected_app_name:
                    logger.info(f"[SCREEN CAPTURE] Auto-detected frontmost app: {detected_app_name}")
                else:
                    logger.warning("[SCREEN CAPTURE] Could not detect frontmost app, falling back to full screen")
                    mode = "full"

            # Generate output path if not provided
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if mode == "focused" and detected_app_name:
                    filename = f"{detected_app_name}_{timestamp}.png"
                elif mode == "region":
                    filename = f"region_{timestamp}.png"
                else:
                    filename = f"screen_{timestamp}.png"
                output_path = str(self.screenshot_dir / filename)

            # Route to appropriate capture method based on mode
            fallback_context: Dict[str, Any] = {}

            if mode == "focused":
                result = self._capture_focused_window(detected_app_name, window_title, output_path)
                if not result.get("success"):
                    logger.warning(
                        "[SCREEN CAPTURE] Focused capture failed, attempting automatic full-screen fallback"
                    )
                    fallback_result = self._capture_full_screen(output_path)
                    if fallback_result.get("success"):
                        fallback_context = {
                            "fallback_used": "full_screen",
                            "fallback_reason": result.get("error") or result.get("error_message"),
                            "detected_app": detected_app_name or app_name,
                        }
                        result = fallback_result
                        mode = "full"
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
            if mode == "full" and (app_name or window_title) and not fallback_context:
                logger.warning("Legacy usage: app_name/window_title provided with mode='full'. Using mode='focused' instead.")
                result = self._capture_focused_window(app_name, window_title, output_path)

            if result.get("success"):
                logger.info(f"[SCREEN CAPTURE] Screenshot saved: {output_path}")
                response: Dict[str, Any] = {
                    "screenshot_path": output_path,
                    "success": True,
                    "app_name": detected_app_name or app_name,
                    "mode": mode,
                    "message": f"Screenshot captured: {Path(output_path).name}"
                }
                if fallback_context:
                    response.update(fallback_context)
                    response["message"] = (
                        f"Screenshot captured with fallback: {Path(output_path).name}"
                    )
                return response
            else:
                if fallback_context:
                    result.update(fallback_context)
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
            app_name: Application name to capture (can be None for auto-detection)
            window_title: Window title filter (best-effort)
            output_path: Where to save screenshot

        Returns:
            Result dictionary
        """
        try:
            # Strategy 1: Use Quartz to find and capture specific window by CGWindowID
            try:
                import Quartz

                target_window_id = None
                
                # First, try to get frontmost window ID directly (works even without app_name)
                if not app_name and not window_title:
                    target_window_id = self._get_frontmost_window_id()
                    if target_window_id:
                        logger.info(f"Using frontmost window CGWindowID: {target_window_id}")
                else:
                    # Get list of all windows
                    window_list = Quartz.CGWindowListCopyWindowInfo(
                        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
                        Quartz.kCGNullWindowID
                    )

                    # Find the target window
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
                    logger.info(f"[STRATEGY 1] Capturing window (CGWindowID: {target_window_id})")

                    # Use -o flag to remove shadow from window capture
                    capture_cmd = [
                        "screencapture",
                        "-l", str(target_window_id),  # Capture specific window by CGWindowID
                        "-x",  # No sound
                        "-o",  # No shadow
                        "-t", "png",
                        output_path
                    ]

                    result = subprocess.run(capture_cmd, capture_output=True, text=True, timeout=10)
                    
                    # Verify the command succeeded AND the file was created with content
                    if result.returncode == 0:
                        # Validate screenshot file
                        if self._validate_screenshot(output_path, app_name):
                            logger.info(f"[STRATEGY 1] SUCCESS: Focused window screenshot saved: {output_path}")
                            return {
                                "success": True,
                                "screenshot_path": output_path
                            }
                        else:
                            logger.warning(f"[STRATEGY 1] FAILED: Screenshot validation failed: {output_path}")
                    else:
                        error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                        logger.warning(f"[STRATEGY 1] FAILED: CGWindowID capture failed (returncode={result.returncode}): {error_msg}")
                else:
                    logger.warning("[STRATEGY 1] FAILED: No target window ID found")

            except ImportError:
                logger.warning("Quartz/PyObjC not available, skipping CGWindowID method")
            except Exception as e:
                logger.warning(f"CGWindow method failed: {e}, trying AppleScript bounds")

            # Strategy 2: Use AppleScript to get window bounds and capture region
            try:
                logger.info("[STRATEGY 2] Attempting AppleScript bounds method")
                # Use detected app_name or try to get frontmost app
                target_app = app_name
                if not target_app:
                    target_app = self._get_frontmost_application()
                
                if not target_app:
                    logger.warning("[STRATEGY 2] FAILED: Could not determine target app")
                    raise Exception("No target app available")
                
                logger.info(f"[STRATEGY 2] Target app: {target_app}")
                
                # Activate app first and verify it's running
                activate_script = f'''
                tell application "System Events"
                    if not (exists process "{target_app}") then
                        return "APP_NOT_RUNNING"
                    end if
                    tell process "{target_app}"
                        set frontmost to true
                    end tell
                end tell
                tell application "{target_app}"
                    activate
                    delay 0.5
                end tell
                '''
                
                activate_result = subprocess.run(
                    ["osascript", "-e", activate_script],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if activate_result.returncode != 0:
                    error_msg = activate_result.stderr.strip() if activate_result.stderr else "Unknown error"
                    logger.warning(f"[STRATEGY 2] FAILED: App activation failed: {error_msg}")
                    raise Exception(f"App activation failed: {error_msg}")
                
                if "APP_NOT_RUNNING" in activate_result.stdout:
                    logger.warning(f"[STRATEGY 2] FAILED: App {target_app} is not running")
                    raise Exception(f"App {target_app} is not running")
                
                # Wait a bit for app to fully activate
                import time
                time.sleep(0.3)

                # Get window bounds - verify window exists first
                bounds_script = f'''
                tell application "System Events"
                    tell process "{target_app}"
                        if not (exists window 1) then
                            return "NO_WINDOW"
                        end if
                        set frontWindow to window 1
                        get bounds of frontWindow
                    end tell
                end tell
                '''

                result = subprocess.run(
                    ["osascript", "-e", bounds_script],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode != 0:
                    error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                    logger.warning(f"[STRATEGY 2] FAILED: Could not get window bounds: {error_msg}")
                    raise Exception(f"Could not get window bounds: {error_msg}")
                
                if not result.stdout.strip():
                    logger.warning("[STRATEGY 2] FAILED: Empty bounds output")
                    raise Exception("Empty bounds output")
                
                bounds_str = result.stdout.strip()
                
                if "NO_WINDOW" in bounds_str:
                    logger.warning(f"[STRATEGY 2] FAILED: App {target_app} has no visible window")
                    raise Exception(f"App {target_app} has no visible window")
                
                # Parse bounds: {x, y, width, height} -> x,y,width,height
                # Remove curly braces and split by comma
                coords = bounds_str.strip('{}').split(',')
                if len(coords) != 4:
                    logger.warning(f"[STRATEGY 2] FAILED: Invalid bounds format: {bounds_str}")
                    raise Exception(f"Invalid bounds format: {bounds_str}")
                
                try:
                    x, y, w, h = [int(c.strip()) for c in coords]
                    logger.info(f"[STRATEGY 2] Window bounds: x={x}, y={y}, w={w}, h={h}")
                    
                    # Validate bounds are reasonable (not zero or negative)
                    if w <= 0 or h <= 0:
                        logger.warning(f"[STRATEGY 2] FAILED: Invalid window dimensions: {w}x{h}")
                        raise Exception(f"Invalid window dimensions: {w}x{h}")
                    
                except ValueError as e:
                    logger.warning(f"[STRATEGY 2] FAILED: Could not parse bounds: {e}")
                    raise Exception(f"Could not parse bounds: {e}")

                # Capture the region
                capture_cmd = [
                    "screencapture",
                    "-x",  # No sound
                    "-R", f"{x},{y},{w},{h}",  # Capture specific region
                    "-t", "png",
                    output_path
                ]

                result = subprocess.run(capture_cmd, capture_output=True, text=True, timeout=10)
                
                # Verify the capture succeeded and file was created
                if result.returncode == 0:
                    # Validate screenshot file
                    if self._validate_screenshot(output_path, target_app):
                        logger.info(f"[STRATEGY 2] SUCCESS: Window region screenshot saved: {output_path}")
                        return {
                            "success": True,
                            "screenshot_path": output_path
                        }
                    else:
                        logger.warning(f"[STRATEGY 2] FAILED: Screenshot validation failed: {output_path}")
                else:
                    error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                    logger.warning(f"[STRATEGY 2] FAILED: Region capture failed (returncode={result.returncode}): {error_msg}")

            except subprocess.TimeoutExpired:
                logger.warning("[STRATEGY 2] FAILED: Timeout while getting window bounds")
            except Exception as e:
                logger.warning(f"[STRATEGY 2] FAILED: AppleScript bounds method failed: {e}")

            # Strategy 3: Try one more time with Quartz frontmost window, then attempt region capture
            logger.info("[STRATEGY 3] Attempting final focused window capture")
            
            # Use detected app_name or try to get frontmost app
            target_app = app_name
            if not target_app:
                target_app = self._get_frontmost_application()
            
            if not target_app:
                logger.error("[STRATEGY 3] FAILED: Could not determine target app for focused capture")
                return {
                    "success": False,
                    "error": "Could not detect frontmost application. Please ensure an application window is visible and focused.",
                    "error_type": "FocusedWindowCaptureError"
                }
            
            logger.info(f"[STRATEGY 3] Target app: {target_app}")
            
            # Try one more time to get frontmost window ID using Quartz
            try:
                import Quartz
                frontmost_window_id = self._get_frontmost_window_id()
                if frontmost_window_id:
                    logger.info(f"[STRATEGY 3] Found frontmost window ID: {frontmost_window_id}, attempting capture")
                    capture_cmd = [
                        "screencapture",
                        "-l", str(frontmost_window_id),
                        "-x",  # No sound
                        "-o",  # No shadow
                        "-t", "png",
                        output_path
                    ]
                    result = subprocess.run(capture_cmd, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        # Validate screenshot file
                        if self._validate_screenshot(output_path, target_app):
                            logger.info(f"[STRATEGY 3] SUCCESS: Focused window captured via frontmost window ID")
                            return {
                                "success": True,
                                "screenshot_path": output_path
                            }
            except Exception as e:
                logger.warning(f"[STRATEGY 3] Quartz retry failed: {e}")
            
            # Final attempt: Activate app and try to capture its window using bounds
            try:
                # Activate the app
                activate_script = f'''
                tell application "{target_app}"
                    activate
                end tell
                delay 0.5
                '''
                subprocess.run(
                    ["osascript", "-e", activate_script],
                    capture_output=True,
                    timeout=10
                )
                import time
                time.sleep(0.5)
                
                # Try to get window bounds one more time
                bounds_script = f'''
                tell application "System Events"
                    tell process "{target_app}"
                        if exists window 1 then
                            get bounds of window 1
                        else
                            return "NO_WINDOW"
                        end if
                    end tell
                end tell
                '''
                
                result = subprocess.run(
                    ["osascript", "-e", bounds_script],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and result.stdout.strip() and "NO_WINDOW" not in result.stdout:
                    bounds_str = result.stdout.strip().strip('{}')
                    coords = bounds_str.split(',')
                    if len(coords) == 4:
                        try:
                            x, y, w, h = [int(c.strip()) for c in coords]
                            if w > 0 and h > 0:
                                capture_cmd = [
                                    "screencapture",
                                    "-x",
                                    "-R", f"{x},{y},{w},{h}",
                                    "-t", "png",
                                    output_path
                                ]
                                result = subprocess.run(capture_cmd, capture_output=True, text=True, timeout=10)
                                if result.returncode == 0:
                                    # Validate screenshot file
                                    if self._validate_screenshot(output_path, target_app):
                                        logger.info(f"[STRATEGY 3] SUCCESS: Window captured via bounds after activation")
                                        return {
                                            "success": True,
                                            "screenshot_path": output_path
                                        }
                        except (ValueError, IndexError):
                            pass
            except Exception as e:
                logger.warning(f"[STRATEGY 3] Final bounds attempt failed: {e}")
            
            # All strategies failed - return error instead of capturing full screen
            logger.error("[STRATEGY 3] FAILED: All focused window capture strategies failed")
            return {
                "success": False,
                "error": f"Failed to capture focused window of {target_app}. All capture strategies failed. The app may not have a visible window, or there may be permission issues.",
                "error_type": "FocusedWindowCaptureError",
                "detected_app": target_app
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
