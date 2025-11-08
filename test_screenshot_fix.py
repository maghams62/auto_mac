#!/usr/bin/env python3
"""
Test the fixed screenshot functionality for Stock app.
Verifies that only the Stock app window is captured, not the entire desktop.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.automation.stocks_app_automation import StocksAppAutomation
from src.utils import load_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_stock_screenshot():
    """Test capturing screenshot of Stock app window only."""
    print("=" * 80)
    print("Testing Fixed Screenshot Functionality")
    print("=" * 80)

    config = load_config()
    automation = StocksAppAutomation(config)

    # Test with Microsoft stock
    print("\n📊 Opening Stocks app for MSFT (Microsoft)...")
    print("⏳ The app will open and the screenshot will capture ONLY the Stocks window")
    print("   (not the entire desktop)")

    result = automation.open_and_capture_stock("MSFT", "microsoft_stock_test")

    if result.get("error"):
        print(f"\n❌ Error: {result['error_message']}")
        return False

    print(f"\n✅ Success!")
    print(f"   Screenshot path: {result['screenshot_path']}")
    print(f"   App captured: {result.get('app_name', 'Unknown')}")
    print(f"   Symbol: {result.get('symbol', 'Unknown')}")

    # Verify file exists and has reasonable size
    screenshot_path = Path(result['screenshot_path'])
    if screenshot_path.exists():
        file_size = screenshot_path.stat().st_size / 1024  # KB
        print(f"   File size: {file_size:.1f} KB")

        if file_size < 50:
            print("\n⚠️  Warning: Screenshot file is very small, may not have captured correctly")
            return False
        else:
            print("\n✨ Screenshot looks good! The image should show ONLY the Stocks app window.")
            print(f"   Open the file to verify: {screenshot_path}")
            return True
    else:
        print("\n❌ Screenshot file not found!")
        return False


if __name__ == "__main__":
    success = test_stock_screenshot()
    sys.exit(0 if success else 1)
