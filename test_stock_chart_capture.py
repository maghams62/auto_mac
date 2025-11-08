"""Test the new capture_stock_chart tool that opens Stocks app and captures chart."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("TEST: Stock Chart Capture from Mac Stocks App")
print("=" * 80)
print("\nThis will:")
print("1. Open Mac Stocks app")
print("2. Search for NVDA")
print("3. Wait for chart to load")
print("4. Capture ONLY the Stocks app window")
print("=" * 80)

from src.agent.stock_agent import capture_stock_chart

# Test capturing NVDA chart
print("\n📸 Capturing NVIDIA chart...")
result = capture_stock_chart.invoke({"symbol": "NVDA"})

if result.get("error"):
    print(f"❌ Error: {result['error_message']}")
    sys.exit(1)

print(f"✅ {result['message']}")
print(f"   Screenshot: {result['screenshot_path']}")
print(f"   Symbol: {result['symbol']}")

print("\n" + "=" * 80)
print("✅ TEST PASSED - Chart captured from Stocks app!")
print("=" * 80)
print("\nThe screenshot should show:")
print("  • NVDA chart with price graph")
print("  • Current price visible")
print("  • ONLY the Stocks app (not desktop)")
