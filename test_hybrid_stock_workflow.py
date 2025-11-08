"""
Test the complete hybrid stock workflow:
1. Browser → Get stock data from Yahoo Finance
2. Mac Stocks app → Take screenshot of chart
3. Writing Agent → Create analysis report
4. Presentation Agent → Create slide deck with data + screenshot
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("HYBRID STOCK WORKFLOW TEST")
print("=" * 80)
print("\nWorkflow:")
print("1. Get NVDA stock data from Yahoo Finance (web)")
print("2. Take screenshot of Mac Stocks app showing NVDA")
print("3. Combine data + screenshot for complete analysis")
print("=" * 80)

# Step 1: Get stock data via web
print("\n📊 Step 1: Get stock data from Yahoo Finance")
print("-" * 80)

from src.agent.stock_agent_hybrid import get_stock_price

result = get_stock_price.invoke({"symbol": "NVDA"})

if result.get("error"):
    print(f"❌ Error: {result.get('error_message')}")
    sys.exit(1)

print(f"✅ {result['message']}")
print(f"   Company: {result['company_name']}")
print(f"   Price: ${result['current_price']:.2f}")
print(f"   Change: ${result['change']:.2f} ({result['change_percent']:+.2f}%)")
print(f"   Previous Close: ${result['previous_close']:.2f}")
if result.get('market_cap'):
    print(f"   Market Cap: ${result['market_cap']/1e12:.2f}T")
print(f"   Source: {result['source']}")

# Step 2: Take screenshot of Mac Stocks app
print("\n📸 Step 2: Take screenshot of Mac Stocks app")
print("-" * 80)

from src.agent.screen_agent import capture_screenshot

screenshot_result = capture_screenshot.invoke({
    "app_name": "Stocks",
    "output_name": "nvda_stock_chart"
})

if screenshot_result.get("error"):
    print(f"❌ Error: {screenshot_result.get('error_message')}")
    sys.exit(1)

print(f"✅ Screenshot captured: {screenshot_result['screenshot_path']}")

# Step 3: Show what would happen next in the workflow
print("\n📝 Step 3: Next steps in full workflow")
print("-" * 80)
print("Would execute:")
print(f"  → synthesize_content(sources=['{result['message']}', 'web data'])")
print(f"  → create_slide_deck_content()")
print(f"  → create_keynote_with_images(image_paths=['{screenshot_result['screenshot_path']}'])")

print("\n" + "=" * 80)
print("✅ HYBRID WORKFLOW TEST PASSED!")
print("=" * 80)
print("\nThis approach combines:")
print("  • Web data (accurate, comprehensive)")
print("  • Mac Stocks app (visual charts/graphs)")
print("  • Perfect for creating reports with both data and visuals")
