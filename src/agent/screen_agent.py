"""
Screen Capture Agent - Universal screenshot capabilities
"""

import logging
from typing import Dict, Any, Optional
from langchain_core.tools import tool

from ..utils.screenshot import get_screenshot_dir


logger = logging.getLogger(__name__)


@tool
def capture_screenshot(
    app_name: Optional[str] = None,
    output_name: Optional[str] = None,
    mode: Optional[str] = None,
    window_title: Optional[str] = None,
    region: Optional[Dict[str, int]] = None
) -> Dict[str, Any]:
    """
    Capture a screenshot of the screen, window, or region.

    SCREEN AGENT - LEVEL 1: Universal Screen Capture
    Use this to capture ANY visible content on screen.

    DEFAULT BEHAVIOR:
    - By default, captures the currently focused/frontmost window (e.g., Cerebros OS, Safari, etc.)
    - Automatically detects which app is in focus - no app_name needed
    - Works for any macOS application including Cerebros OS, Safari, Stocks, Calculator, etc.

    Works for:
    - Currently focused window (default, auto-detects app) - e.g., Cerebros OS, Safari, etc.
    - Stock app (app_name="Stocks", mode="focused")
    - Safari or any browser (app_name="Safari", mode="focused")
    - Calculator (app_name="Calculator", mode="focused")
    - Any macOS application window
    - Specific screen regions (mode="region")
    - Entire desktop (mode="full")

    Args:
        app_name: Name of application to capture (e.g., "Stocks", "Safari", "Calculator", "Cerebros OS")
                 Used for focused window capture. If None and mode="focused", auto-detects frontmost app.
        output_name: Optional custom name for screenshot file
        mode: Capture mode - "focused" (app window, default), "full" (entire screen), "region" (specific coords)
        window_title: Optional window title filter (best-effort)
        region: For mode="region", dict with x, y, width, height keys

    Returns:
        Dictionary with screenshot_path, app_name, mode, and success status

    Examples:
        capture_screenshot()  # Capture currently focused window (auto-detects app like Cerebros OS)
        capture_screenshot(app_name="Stocks", mode="focused")  # Capture Stock app window only
        capture_screenshot(app_name="Safari", mode="focused")  # Capture browser window only
        capture_screenshot(mode="full")  # Capture entire desktop
        capture_screenshot(mode="region", region={"x": 100, "y": 100, "width": 800, "height": 600})  # Capture specific area

    IMPORTANT:
    - DEFAULT: Calling capture_screenshot() with no parameters captures the currently focused window
    - Auto-detection works for any app including Cerebros OS, Safari, Stocks, etc.
    - For specific apps: Use mode="focused" with app_name for precise window capture
    - For desktop capture: Explicitly set mode="full"
    - For regions: Use mode="region" with region parameter
    - The app must be visible/open on screen (tool activates it automatically if app_name provided)
    - Falls back gracefully if focused capture unavailable
    """
    logger.info(f"[SCREEN AGENT] Tool: capture_screenshot(mode='{mode}', app_name='{app_name}', window_title='{window_title}')")

    try:
        from ..automation.screen_capture import ScreenCapture
        from ..utils import load_config

        config = load_config()
        screen_capture = ScreenCapture(config)

        # Generate output path if custom name provided
        output_path = None
        if output_name:
            screenshot_dir = get_screenshot_dir(config)
            output_path = str(screenshot_dir / f"{output_name}.png")

        # Default to None to let capture_screen use its default ("focused")
        result = screen_capture.capture_screen(
            app_name=app_name,
            window_title=window_title,
            output_path=output_path,
            mode=mode,  # None will default to "focused" in capture_screen
            region=region
        )

        if result.get("error") or not result.get("success"):
            return result

        return {
            "screenshot_path": result["screenshot_path"],
            "app_name": app_name or "screen",
            "mode": mode,
            "message": f"Screenshot captured: {result['screenshot_path']}"
        }

    except Exception as e:
        logger.error(f"[SCREEN AGENT] Error in capture_screenshot: {e}")
        return {
            "error": True,
            "error_type": "ScreenshotError",
            "error_message": str(e),
            "retry_possible": False
        }


# Export tools
SCREEN_AGENT_TOOLS = [
    capture_screenshot,
]

# Tool hierarchy for planner
SCREEN_AGENT_HIERARCHY = {
    "LEVEL 1 - Primary": [
        "capture_screenshot",  # Universal screen capture
    ],
}
