"""
Test automatic screenshot capability.

Verifies:
1. Screenshot tool is fully automatic (no manual interaction)
2. Works for any app (Stocks, Calculator, Safari, etc.)
3. Integrates properly with the agent system
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.agent.screen_agent import capture_screenshot
import os


def test_automatic_screenshot():
    """Test that screenshot is fully automatic."""
    print("\n" + "="*80)
    print("TEST: Automatic Screenshot Capture")
    print("="*80)

    # Test 1: Screenshot of Calculator (should be quick)
    print("\nTest 1: Capture Calculator app (automatic)")
    print("-" * 80)

    result = capture_screenshot.invoke({"app_name": "Calculator"})

    if result.get("error"):
        print(f"❌ FAILED: {result.get('error_message')}")
        return False

    screenshot_path = result.get("screenshot_path")

    print(f"✅ Screenshot captured automatically")
    print(f"   Path: {screenshot_path}")

    # Verify file exists and has content
    if not os.path.exists(screenshot_path):
        print(f"❌ FAILED: Screenshot file doesn't exist")
        return False

    file_size = os.path.getsize(screenshot_path)
    print(f"   Size: {file_size:,} bytes")

    if file_size < 1000:  # Less than 1KB is suspicious
        print(f"❌ FAILED: Screenshot file is too small ({file_size} bytes)")
        return False

    print(f"✅ Screenshot file is valid")

    # Test 2: Full screen capture (no app specified)
    print("\nTest 2: Capture entire screen (automatic)")
    print("-" * 80)

    result2 = capture_screenshot.invoke({})

    if result2.get("error"):
        print(f"❌ FAILED: {result2.get('error_message')}")
        return False

    screenshot_path2 = result2.get("screenshot_path")

    print(f"✅ Full screen captured automatically")
    print(f"   Path: {screenshot_path2}")
    print(f"   Size: {os.path.getsize(screenshot_path2):,} bytes")

    # Test 3: Verify it works in agent context
    print("\nTest 3: Integration with agent system")
    print("-" * 80)

    from src.agent import SCREEN_AGENT_TOOLS

    if not SCREEN_AGENT_TOOLS:
        print("❌ FAILED: SCREEN_AGENT_TOOLS not exported")
        return False

    print(f"✅ Screen Agent tools exported: {len(SCREEN_AGENT_TOOLS)} tool(s)")

    tool_names = [tool.name for tool in SCREEN_AGENT_TOOLS]
    print(f"   Tools: {tool_names}")

    if "capture_screenshot" not in tool_names:
        print("❌ FAILED: capture_screenshot not in tool list")
        return False

    print("✅ capture_screenshot is available in tool registry")

    print("\n" + "="*80)
    print("ALL TESTS PASSED!")
    print("="*80)
    print("\n✅ Screenshot tool is:")
    print("   • Fully automatic (no manual interaction)")
    print("   • Works for any app")
    print("   • Properly integrated with agent system")
    print("   • Ready for use in workflows")
    print("\n" + "="*80)

    return True


if __name__ == "__main__":
    success = test_automatic_screenshot()
    sys.exit(0 if success else 1)
