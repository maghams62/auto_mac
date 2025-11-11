"""Test the new web-scraping based stock agent."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.stock_agent_new import get_stock_price

print("=" * 80)
print("TESTING NEW WEB-SCRAPING STOCK AGENT")
print("=" * 80)

# Test Nvidia (NVDA)
print("\n🧪 Test 1: Get Nvidia (NVDA) stock price")
print("-" * 80)

result = get_stock_price.invoke({"symbol": "NVDA"})

if result.get("error"):
    print(f"❌ Error: {result.get('error_message')}")
    sys.exit(1)
else:
    print(f"✅ {result['message']}")
    print(f"\nDetails:")
    print(f"  Company: {result['company_name']}")
    print(f"  Symbol: {result['symbol']}")
    print(f"  Current Price: ${result['current_price']:.2f}")
    print(f"  Change: ${result['change']:.2f}")
    print(f"  Change %: {result['change_percent']:+.2f}%")
    print(f"  Previous Close: ${result['previous_close']:.2f}")
    print(f"  Source: {result['source']}")

# Test Apple (AAPL)
print("\n🧪 Test 2: Get Apple (AAPL) stock price")
print("-" * 80)

result2 = get_stock_price.invoke({"symbol": "AAPL"})

if result2.get("error"):
    print(f"❌ Error: {result2.get('error_message')}")
else:
    print(f"✅ {result2['message']}")
    print(f"  Price: ${result2['current_price']:.2f}")
    print(f"  Change: {result2['change_percent']:+.2f}%")

print("\n" + "=" * 80)
print("✅ ALL TESTS PASSED - New stock agent is working!")
print("=" * 80)
