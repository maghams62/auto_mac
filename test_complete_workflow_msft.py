#!/usr/bin/env python3
"""
Test complete workflow:
1. Get Microsoft stock price analysis
2. Capture screenshot of stock app showing Microsoft
3. Create Keynote presentation with the analysis
4. Email the presentation with the screenshot attached
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.agent.stock_agent import get_stock_price, capture_stock_chart
from src.agent.presentation_agent import create_keynote_with_images
from src.agent.email_agent import compose_email
from src.utils import load_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_complete_workflow():
    """Test the complete workflow for Microsoft stock."""
    print("=" * 80)
    print("Complete Workflow Test: Microsoft Stock Analysis")
    print("=" * 80)

    config = load_config()

    # Step 1: Get stock price data
    print("\n📊 Step 1: Fetching Microsoft stock data...")
    price_result = get_stock_price.invoke({"symbol": "MSFT"})

    if price_result.get("error"):
        print(f"❌ Error fetching stock data: {price_result['error_message']}")
        return False

    print(f"✅ Current price: ${price_result['current_price']}")
    print(f"   Change: {price_result['change']} ({price_result['change_percent']}%)")
    print(f"   Company: {price_result['company_name']}")

    # Step 2: Capture screenshot from Stock app
    print("\n📸 Step 2: Capturing screenshot of Microsoft stock from Stock app...")
    print("   (This will capture ONLY the Stock app window, not the entire desktop)")
    screenshot_result = capture_stock_chart.invoke({
        "symbol": "MSFT",
        "output_name": "microsoft_stock_today"
    })

    if screenshot_result.get("error"):
        print(f"❌ Error capturing screenshot: {screenshot_result['error_message']}")
        return False

    screenshot_path = screenshot_result['screenshot_path']
    print(f"✅ Screenshot captured: {screenshot_path}")

    # Step 3: Create Keynote presentation
    print("\n📄 Step 3: Creating Keynote presentation...")

    # Create analysis content
    analysis = f"""Microsoft Corporation (MSFT) Stock Analysis

Current Price: ${price_result['current_price']}
Change: {'+' if price_result['change'] >= 0 else ''}{price_result['change']} ({'+' if price_result['change_percent'] >= 0 else ''}{price_result['change_percent']}%)

Day's Range: ${price_result.get('day_low', 'N/A')} - ${price_result.get('day_high', 'N/A')}
52-Week Range: ${price_result.get('fifty_two_week_low', 'N/A')} - ${price_result.get('fifty_two_week_high', 'N/A')}

Market Cap: {price_result.get('market_cap', 'N/A'):,} {price_result.get('currency', 'USD')}
Volume: {price_result.get('volume', 'N/A'):,}

Analysis Date: Today
"""

    presentation_result = create_keynote_with_images.invoke({
        "title": f"Microsoft Stock Analysis - ${price_result['current_price']}",
        "image_paths": [screenshot_path],
        "output_path": None
    })

    if presentation_result.get("error"):
        print(f"❌ Error creating presentation: {presentation_result['error_message']}")
        return False

    presentation_path = presentation_result['keynote_path']
    print(f"✅ Presentation created: {presentation_path}")
    print(f"   Slides: {presentation_result.get('slide_count', 'Unknown')}")

    # Step 4: Email the presentation with screenshot
    print("\n📧 Step 4: Creating email with presentation and screenshot...")

    email_result = compose_email.invoke({
        "subject": f"Microsoft (MSFT) Stock Analysis - ${price_result['current_price']}",
        "body": f"""Hi,

Here's today's analysis for Microsoft Corporation (MSFT):

Current Price: ${price_result['current_price']} ({'+' if price_result['change_percent'] >= 0 else ''}{price_result['change_percent']}%)

Please find attached:
- Keynote presentation with stock chart
- Screenshot of the current stock price

Best regards,
Stock Analysis Bot
""",
        "attachments": [presentation_path, screenshot_path],
        "recipient": None,  # Will create draft
        "send": False
    })

    if email_result.get("error"):
        print(f"❌ Error creating email: {email_result['error_message']}")
        return False

    print(f"✅ Email draft created!")
    print(f"   Status: {email_result.get('status', 'Unknown')}")

    print("\n" + "=" * 80)
    print("✨ Complete Workflow Success!")
    print("=" * 80)
    print(f"📊 Stock data: {price_result['company_name']} @ ${price_result['current_price']}")
    print(f"📸 Screenshot: {screenshot_path}")
    print(f"📄 Presentation: {presentation_path}")
    print(f"📧 Email: Draft created in Mail.app")
    print("\nThe screenshot should show ONLY the Stock app window (not the full desktop)!")
    print("=" * 80)

    return True


if __name__ == "__main__":
    success = test_complete_workflow()
    sys.exit(0 if success else 1)
