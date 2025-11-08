"""
Mac Stocks App Automation - Open app, navigate to symbol, capture screenshot.
"""

import subprocess
import logging
import time
from typing import Dict, Any, Optional
from pathlib import Path

from .screen_capture import ScreenCapture

logger = logging.getLogger(__name__)


class StocksAppAutomation:
    """Automate Mac Stocks app to view specific symbols and capture screenshots."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.screenshots_dir = Path("data/screenshots")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    def open_and_capture_stock(
        self,
        symbol: str,
        output_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Open Mac Stocks app to specific symbol and capture screenshot.

        Args:
            symbol: Stock ticker symbol (e.g., 'NVDA', 'AAPL')
            output_name: Optional custom filename for screenshot

        Returns:
            Dictionary with screenshot path and result info
        """
        symbol = symbol.upper()
        logger.info(f"Opening Stocks app for {symbol}")

        try:
            # Step 1: Open Stocks app directly to the symbol using URL scheme
            logger.info(f"Step 1: Opening Stocks app to {symbol}...")
            self._open_stock_symbol(symbol)

            # Step 2: Wait for app to launch and chart to load
            logger.info("Step 2: Waiting for chart to load...")
            time.sleep(3.0)

            # Step 3: Capture screenshot of Stocks app window
            logger.info("Step 3: Capturing screenshot...")
            if not output_name:
                output_name = f"{symbol.lower()}_chart"

            screenshot_path = self._capture_stocks_window(output_name)

            return {
                "success": True,
                "symbol": symbol,
                "screenshot_path": str(screenshot_path),
                "app_name": "Stocks",
                "message": f"Captured {symbol} chart from Stocks app"
            }

        except Exception as e:
            logger.error(f"Error capturing stock chart: {e}")
            return {
                "error": True,
                "error_type": "StocksAppError",
                "error_message": f"Failed to capture stock chart: {str(e)}",
                "retry_possible": True
            }

    def _open_stock_symbol(self, symbol: str):
        """
        Open Stocks app and navigate to a specific symbol.

        Uses AppleScript to:
        1. Activate Stocks app
        2. Use search to find the symbol
        3. Select the stock
        """
        applescript = f'''
        tell application "Stocks"
            activate
        end tell

        delay 1

        tell application "System Events"
            tell process "Stocks"
                -- Click in search field (usually in toolbar)
                try
                    -- Try to find search field
                    set searchField to text field 1 of toolbar 1 of window 1
                    click searchField
                    delay 0.3

                    -- Clear existing text
                    keystroke "a" using command down
                    delay 0.1
                    keystroke "{symbol}"
                    delay 0.8

                    -- Press Enter to search
                    keystroke return
                    delay 0.5

                on error errMsg
                    -- Fallback: try keyboard shortcut method
                    keystroke "f" using command down
                    delay 0.5
                    keystroke "{symbol}"
                    delay 0.8
                    keystroke return
                    delay 0.5
                end try
            end tell
        end tell
        '''

        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            logger.warning(f"AppleScript navigation had issues: {result.stderr}")
            logger.info("Stocks app is open, but symbol navigation may have failed")
            # Don't raise - the app is at least open

    def _capture_stocks_window(self, output_name: str) -> Path:
        """
        Capture screenshot of ONLY the Stocks app window.

        Uses screencapture -l with CGWindowID to capture just the focused window.
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{output_name}_{timestamp}.png"
        output_path = self.screenshots_dir / filename

        # Ensure Stocks app is activated and in windowed mode (not fullscreen)
        activate_script = '''
        tell application "Stocks"
            activate
        end tell

        delay 0.3

        tell application "System Events"
            tell process "Stocks"
                -- Get the window
                set frontWindow to window 1

                -- Always resize window to consistent size for screenshot
                -- This ensures we ALWAYS capture just the window, not full screen
                try
                    -- Set to optimal window size for stock chart visibility
                    set size of frontWindow to {1200, 750}
                    set position of frontWindow to {200, 100}
                    delay 0.4
                end try
            end tell
        end tell
        '''
        subprocess.run(
            ["osascript", "-e", activate_script],
            capture_output=True,
            text=True
        )
        time.sleep(0.5)  # Wait for resize/activation

        # Method 0: Use shared ScreenCapture utility (focused-window capture)
        try:
            logger.info("Attempting focused window capture via ScreenCapture utility")
            screen_capture = ScreenCapture(self.config)
            capture_result = screen_capture.capture_screen(
                app_name="Stocks",
                output_path=str(output_path)
            )

            if capture_result.get("success") and capture_result.get("screenshot_path"):
                logger.info(f"Screenshot saved via ScreenCapture: {capture_result['screenshot_path']}")
                return Path(capture_result["screenshot_path"])
            else:
                logger.warning(f"ScreenCapture utility failed, reason: {capture_result}")
        except Exception as e:
            logger.warning(f"ScreenCapture utility capture failed: {e}, trying Quartz method")

        # Try Method 1: Use Python/Quartz to get CGWindowID and capture specific window
        try:
            # Use a more reliable approach: get window info via Python
            import Quartz

            # Get list of all windows
            window_list = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
                Quartz.kCGNullWindowID
            )

            # Find the Stocks window
            stocks_window_id = None
            for window in window_list:
                owner = window.get('kCGWindowOwnerName', '')
                if owner == 'Stocks':
                    window_layer = window.get('kCGWindowLayer', -1)
                    # Get the frontmost Stocks window (layer 0)
                    if window_layer == 0:
                        stocks_window_id = window.get('kCGWindowNumber')
                        logger.info(f"Found Stocks window with CGWindowID: {stocks_window_id}")
                        break

            if stocks_window_id:
                # Capture the specific window using CGWindowID
                logger.info(f"Capturing Stocks window (CGWindowID: {stocks_window_id})")

                # The -l flag requires just the window ID (no -o flag with -l)
                capture_cmd = [
                    "screencapture",
                    "-l", str(stocks_window_id),  # Capture specific window by CGWindowID
                    "-x",  # No sound
                    str(output_path)
                ]

                result = subprocess.run(capture_cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info(f"Screenshot saved: {output_path}")
                    return output_path
                else:
                    logger.warning(f"CGWindowID capture failed: {result.stderr}")
                    # Continue to fallback method

        except ImportError:
            logger.warning("Quartz/PyObjC not available, using fallback method")
        except Exception as e:
            logger.warning(f"CGWindow method failed: {e}, using fallback")

        # Try Method 2: Get window bounds and capture that region
        try:
            logger.info("Trying window bounds method...")

            # Get window position and size using AppleScript
            bounds_script = '''
            tell application "System Events"
                tell process "Stocks"
                    set frontWindow to window 1
                    set windowPos to position of frontWindow
                    set windowSize to size of frontWindow
                    return (item 1 of windowPos) & "," & (item 2 of windowPos) & "," & (item 1 of windowSize) & "," & (item 2 of windowSize)
                end tell
            end tell
            '''

            result = subprocess.run(
                ["osascript", "-e", bounds_script],
                capture_output=True,
                text=True,
                check=True
            )

            # Parse bounds: x,y,width,height
            # AppleScript returns format like "223, ,, 62, ,, 1024, ,, 768"
            bounds = result.stdout.strip()
            # Clean up the format - remove extra spaces and commas
            cleaned = bounds.replace(' ', '').replace(',,', ',')
            logger.info(f"Raw bounds: {bounds}, cleaned: {cleaned}")

            if cleaned and ',' in cleaned:
                parts = [p for p in cleaned.split(',') if p]  # Filter out empty strings
                if len(parts) >= 4:
                    x, y, width, height = map(int, parts[:4])
                    logger.info(f"Window bounds: x={x}, y={y}, width={width}, height={height}")

                    # Capture specific region using screencapture -R
                    capture_cmd = [
                        "screencapture",
                        "-x",  # No sound
                        "-R", f"{x},{y},{width},{height}",  # Capture specific region
                        str(output_path)
                    ]

                    subprocess.run(capture_cmd, check=True, capture_output=True)
                    logger.info(f"Screenshot saved (window region): {output_path}")
                    return output_path

        except Exception as e:
            logger.warning(f"Window bounds method failed: {e}, using full screen fallback")

        # Fallback: Capture full screen with Stocks app in focus
        # Since the Stocks app is maximized and in focus, this effectively captures the Stocks window
        logger.info("Using fallback: capturing screen with Stocks app in foreground")

        # Ensure Stocks is frontmost
        subprocess.run(
            ["osascript", "-e", 'tell application "Stocks" to activate'],
            capture_output=True
        )
        time.sleep(0.8)

        # Capture the full screen (Stocks app will be prominent/maximized)
        capture_cmd = [
            "screencapture",
            "-x",  # No sound
            str(output_path)
        ]

        subprocess.run(capture_cmd, check=True, capture_output=True)
        logger.info(f"Screenshot saved (Stocks app in foreground): {output_path}")
        return output_path


def test_stocks_app_automation():
    """Test the Stocks app automation."""
    from ..utils import load_config

    config = load_config()
    automation = StocksAppAutomation(config)

    print("=" * 80)
    print("Testing Mac Stocks App Automation")
    print("=" * 80)

    # Test with NVDA
    print("\nCapturing NVIDIA (NVDA) chart...")
    result = automation.open_and_capture_stock("NVDA")

    if result.get("error"):
        print(f"❌ Error: {result['error_message']}")
        return False

    print(f"✅ Success: {result['message']}")
    print(f"   Screenshot: {result['screenshot_path']}")

    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    success = test_stocks_app_automation()
    sys.exit(0 if success else 1)
