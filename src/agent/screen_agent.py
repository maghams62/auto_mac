"""
Screen Capture Agent - Universal screenshot capabilities
"""

import logging
from typing import Dict, Any, Optional
from langchain_core.tools import tool


logger = logging.getLogger(__name__)


@tool
def capture_screenshot(
    app_name: Optional[str] = None,
    output_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Capture a screenshot of the screen or specific application.

    SCREEN AGENT - LEVEL 1: Universal Screen Capture
    Use this to capture ANY visible content on screen.

    Works for:
    - Stock app (app_name="Stocks")
    - Safari or any browser (app_name="Safari")
    - Calculator (app_name="Calculator")
    - Any macOS application
    - Entire screen (app_name=None)

    Args:
        app_name: Name of application to capture (e.g., "Stocks", "Safari", "Calculator")
                 If None, captures entire screen
        output_name: Optional custom name for screenshot file

    Returns:
        Dictionary with screenshot_path and success status

    Examples:
        capture_screenshot(app_name="Stocks")  # Capture Stock app showing Apple price
        capture_screenshot(app_name="Safari")  # Capture browser window
        capture_screenshot()  # Capture entire screen

    IMPORTANT:
    - For stock prices: Use app_name="Stocks" to capture the macOS Stocks app
    - For web pages: Use app_name="Safari" or "Google Chrome"
    - The app must be visible/open on screen
    - The tool activates the app automatically before capturing
    """
    logger.info(f"[SCREEN AGENT] Tool: capture_screenshot(app_name='{app_name}')")

    try:
        from ..automation.screen_capture import ScreenCapture
        from ..utils import load_config

        config = load_config()
        screen_capture = ScreenCapture(config)

        # Generate output path if custom name provided
        output_path = None
        if output_name:
            from pathlib import Path
            screenshot_dir = Path("data/screenshots")
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(screenshot_dir / f"{output_name}.png")

        result = screen_capture.capture_screen(
            app_name=app_name,
            output_path=output_path
        )

        if result.get("error"):
            return result

        return {
            "screenshot_path": result["screenshot_path"],
            "app_name": app_name or "screen",
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
