#!/usr/bin/env python3
"""
Test Google Finance Agent - Extract data from Google Finance pages.

Tests the complete workflow:
1. Search for company on Google Finance
2. Extract price and AI research
3. Capture chart screenshot
4. Create report or presentation
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from agent.google_finance_agent import (
    search_google_finance_stock,
    extract_google_finance_data,
    capture_google_finance_chart,
    create_stock_report_from_google_finance
)
from utils import load_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_search():
    """Test searching for stocks on Google Finance."""
    print("\n" + "="*80)
    print("TEST 1: Search Google Finance (with anti-CAPTCHA strategies)")
    print("="*80)

    test_companies = [
        ("PLTR", "Ticker - Direct URL (fastest, no CAPTCHA risk)"),
        ("MSFT", "Ticker - Direct URL"),
        ("NVDA", "Ticker - Direct URL"),
        # ("Palantir", "Company name - May trigger search"),  # Commented to avoid CAPTCHA
    ]

    for company, description in test_companies:
        print(f"\n🔍 Testing: {company}")
        print(f"   Strategy: {description}")
        result = search_google_finance_stock.invoke({"company": company})

        if result.get("error"):
            error_type = result.get("error_type")
            if error_type == "CAPTCHADetected":
                print(f"  ⚠️  CAPTCHA: {result['error_message']}")
                print(f"  💡 Suggestion: {result.get('suggestion')}")
            else:
                print(f"  ❌ Error: {result['error_message']}")
        else:
            print(f"  ✅ Found via {result.get('method', 'unknown')}!")
            print(f"     Company: {result.get('company_name')}")
            print(f"     Ticker: {result.get('ticker')}")
            print(f"     Exchange: {result.get('exchange')}")
            print(f"     URL: {result.get('url')}")

        # Add delay between requests to avoid rate limiting
        print("   ⏸️  Waiting 3 seconds...")
        import time
        time.sleep(3)

    return True


def test_extract_data():
    """Test extracting data from Google Finance pages."""
    print("\n" + "="*80)
    print("TEST 2: Extract Google Finance Data")
    print("="*80)

    # Test with Palantir (the URL you provided)
    test_url = "https://www.google.com/finance/quote/PLTR:NASDAQ"

    print(f"\n📊 Extracting data from: {test_url}")
    result = extract_google_finance_data.invoke({"url": test_url})

    if result.get("error"):
        print(f"  ❌ Error: {result['error_message']}")
        return False
    else:
        print(f"  ✅ Data extracted!")

        if result.get("price_data"):
            print(f"\n  💰 Price Data:")
            for key, value in result["price_data"].items():
                print(f"     {key}: {value}")

        if result.get("research"):
            print(f"\n  🔬 AI Research:")
            research = result["research"]
            print(f"     {research[:200]}..." if len(research) > 200 else f"     {research}")

        if result.get("statistics"):
            print(f"\n  📈 Statistics:")
            for key, value in list(result["statistics"].items())[:5]:
                print(f"     {key}: {value}")

        if result.get("about"):
            print(f"\n  ℹ️  About:")
            about = result["about"]
            print(f"     {about[:150]}..." if len(about) > 150 else f"     {about}")

    return True


def test_capture_chart():
    """Test capturing chart screenshots."""
    print("\n" + "="*80)
    print("TEST 3: Capture Google Finance Chart")
    print("="*80)

    test_url = "https://www.google.com/finance/quote/PLTR:NASDAQ"

    print(f"\n📸 Capturing chart from: {test_url}")
    result = capture_google_finance_chart.invoke({
        "url": test_url,
        "output_name": "test_palantir"
    })

    if result.get("error"):
        print(f"  ❌ Error: {result['error_message']}")
        return False
    else:
        print(f"  ✅ Chart captured!")
        print(f"     Path: {result.get('screenshot_path')}")

    return True


def test_complete_report():
    """Test complete report generation from Google Finance."""
    print("\n" + "="*80)
    print("TEST 4: Complete Report Generation")
    print("="*80)

    test_cases = [
        ("Palantir", "pdf"),
        ("MSFT", "pdf"),
        # ("NVDA", "presentation"),  # Uncomment to test presentations
    ]

    for company, output_format in test_cases:
        print(f"\n📝 Creating {output_format} for: {company}")
        result = create_stock_report_from_google_finance.invoke({
            "company": company,
            "output_format": output_format
        })

        if result.get("error"):
            print(f"  ❌ Error: {result['error_message']}")
        else:
            print(f"  ✅ {output_format.upper()} created!")
            print(f"     Company: {result.get('company')}")
            print(f"     Ticker: {result.get('ticker')}")

            if output_format == "pdf":
                print(f"     Report: {result.get('report_path')}")
            else:
                print(f"     Presentation: {result.get('presentation_path')}")

            print(f"     Chart: {result.get('chart_path')}")
            print(f"     Google Finance: {result.get('google_finance_url')}")

            # Show extracted data summary
            data = result.get("data_extracted", {})
            if data.get("research"):
                print(f"\n     📊 Research extracted: {len(data['research'])} characters")
            if data.get("price_data"):
                print(f"     💰 Price data: {data['price_data']}")

    return True


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("GOOGLE FINANCE AGENT - TEST SUITE")
    print("="*80)
    print("\nThis will open browser windows to interact with Google Finance.")
    print("Please ensure you have internet connection.\n")

    try:
        # Load config
        config = load_config()
        print("✅ Configuration loaded")

        # Run tests
        tests = [
            ("Search Google Finance", test_search),
            ("Extract Data", test_extract_data),
            ("Capture Chart", test_capture_chart),
            ("Complete Report", test_complete_report),
        ]

        results = []
        for test_name, test_func in tests:
            try:
                print(f"\n{'='*80}")
                print(f"Running: {test_name}")
                print(f"{'='*80}")
                success = test_func()
                results.append((test_name, success))
            except Exception as e:
                logger.error(f"Test '{test_name}' failed with exception: {e}", exc_info=True)
                results.append((test_name, False))

        # Print summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)

        for test_name, success in results:
            status = "✅ PASSED" if success else "❌ FAILED"
            print(f"{test_name}: {status}")

        passed = sum(1 for _, success in results if success)
        total = len(results)
        print(f"\nTotal: {passed}/{total} tests passed")

        print("\n" + "="*80)
        print("OUTPUT LOCATIONS")
        print("="*80)
        print("Reports: data/reports/")
        print("Charts: data/screenshots/")

        return passed == total

    except Exception as e:
        logger.error(f"Test suite failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
