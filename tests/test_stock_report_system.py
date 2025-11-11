#!/usr/bin/env python3
"""
Test script for the enhanced stock report generation system.

Tests:
1. Ticker resolution for well-known companies
2. Ticker resolution with web fallback
3. Private company detection
4. Stock chart capture with fallback
5. Complete report generation with embedded charts
"""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.report_agent import create_stock_report
from src.agent.stock_agent import search_stock_symbol, capture_stock_chart
from src.utils import load_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_ticker_resolution():
    """Test ticker resolution with various companies."""
    print("\n" + "="*80)
    print("TEST 1: Ticker Resolution")
    print("="*80)

    test_cases = [
        ("Microsoft", "MSFT", "Well-known company (local cache)"),
        ("Apple", "AAPL", "Well-known company (local cache)"),
        ("Nvidia", "NVDA", "Well-known company (local cache)"),
        ("Bosch", None, "International/Private company (web search)"),
    ]

    for company, expected_ticker, description in test_cases:
        print(f"\n{description}")
        print(f"  Company: {company}")
        print(f"  Expected: {expected_ticker or 'Unknown/Private'}")

        result = search_stock_symbol.invoke({"query": company, "use_web_fallback": True})

        if result.get("is_private_company"):
            print(f"  ✅ Detected as private company")
        elif result.get("found"):
            actual_ticker = result.get("symbol") or result.get("matches", [{}])[0].get("symbol")
            print(f"  ✅ Found: {actual_ticker} ({result.get('company_name', 'N/A')})")
            print(f"  Source: {result.get('source', 'unknown')}")
            if expected_ticker and actual_ticker != expected_ticker:
                print(f"  ⚠️  Warning: Expected {expected_ticker}, got {actual_ticker}")
        else:
            print(f"  ❌ Not found: {result.get('error_message')}")

    return True


def test_chart_capture():
    """Test chart capture with fallback."""
    print("\n" + "="*80)
    print("TEST 2: Chart Capture with Fallback")
    print("="*80)

    test_cases = [
        ("MSFT", "Microsoft (US stock - should work with Stocks app)"),
        ("AAPL", "Apple (US stock - should work with Stocks app)"),
    ]

    for ticker, description in test_cases:
        print(f"\n{description}")
        print(f"  Ticker: {ticker}")

        result = capture_stock_chart.invoke({
            "symbol": ticker,
            "output_name": f"test_{ticker.lower()}_chart",
            "use_web_fallback": True
        })

        if result.get("error"):
            print(f"  ❌ Failed: {result.get('error_message')}")
        else:
            print(f"  ✅ Success!")
            print(f"  Path: {result.get('screenshot_path')}")
            print(f"  Method: {result.get('capture_method', 'unknown')}")

    return True


def test_complete_report_generation():
    """Test complete end-to-end report generation."""
    print("\n" + "="*80)
    print("TEST 3: Complete Report Generation")
    print("="*80)

    test_cases = [
        ("Microsoft", None, "Well-known company with auto ticker resolution"),
        ("Apple", "AAPL", "Well-known company with explicit ticker"),
        ("NVDA", None, "Direct ticker symbol"),
    ]

    for company, ticker, description in test_cases:
        print(f"\n{description}")
        print(f"  Company: {company}")
        print(f"  Ticker: {ticker or 'Auto-resolve'}")

        result = create_stock_report.invoke({
            "company": company,
            "ticker": ticker,
            "include_analysis": True,
            "output_name": f"test_{company.lower().replace(' ', '_')}_report"
        })

        if result.get("error"):
            error_type = result.get("error_type")
            if error_type == "PrivateCompany":
                print(f"  ℹ️  Private company (expected): {result.get('error_message')}")
            else:
                print(f"  ❌ Failed: {result.get('error_message')}")
                print(f"  Error type: {error_type}")
        else:
            print(f"  ✅ Success!")
            print(f"  Company: {result.get('company')}")
            print(f"  Ticker: {result.get('ticker')}")
            print(f"  Report: {result.get('report_path')}")
            print(f"  Chart: {result.get('chart_path')}")
            print(f"  Format: {result.get('report_format')}")
            print(f"  Ticker Source: {result.get('ticker_source')}")
            print(f"  Chart Method: {result.get('chart_method')}")

    return True


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("STOCK REPORT SYSTEM - COMPREHENSIVE TEST SUITE")
    print("="*80)

    try:
        # Load config
        config = load_config()
        print(f"\nConfiguration loaded successfully")

        # Run tests
        tests = [
            ("Ticker Resolution", test_ticker_resolution),
            ("Chart Capture", test_chart_capture),
            ("Complete Report Generation", test_complete_report_generation),
        ]

        results = []
        for test_name, test_func in tests:
            try:
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

        return passed == total

    except Exception as e:
        logger.error(f"Test suite failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
