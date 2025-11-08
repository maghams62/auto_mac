#!/usr/bin/env python3
"""
Example: Create a stock report for any company

This example demonstrates the new unified stock report generation system that:
- Automatically resolves stock tickers
- Detects private companies
- Captures charts from multiple sources
- Generates PDF reports with embedded visualizations

Usage:
    python examples/stock_report_example.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent.report_agent import create_stock_report
from utils import load_config
import logging

logging.basicConfig(level=logging.INFO)


def main():
    """Demonstrate stock report generation for various companies."""

    print("="*80)
    print("Stock Report Generation Examples")
    print("="*80)

    # Load configuration
    config = load_config()

    # Example 1: Well-known company (auto ticker resolution)
    print("\n" + "="*80)
    print("Example 1: Microsoft Stock Report (Auto-resolve ticker)")
    print("="*80)

    result = create_stock_report.invoke({
        "company": "Microsoft",
        "include_analysis": True
    })

    if result.get("error"):
        print(f"❌ Error: {result.get('error_message')}")
    else:
        print(f"✅ Report created successfully!")
        print(f"   Company: {result['company']} ({result['ticker']})")
        print(f"   Report: {result['report_path']}")
        print(f"   Chart: {result['chart_path']}")
        print(f"   {result['message']}")

    # Example 2: Direct ticker symbol
    print("\n" + "="*80)
    print("Example 2: NVIDIA Stock Report (Direct ticker)")
    print("="*80)

    result = create_stock_report.invoke({
        "company": "NVIDIA",
        "ticker": "NVDA",
        "include_analysis": True,
        "output_name": "nvidia_stock_analysis"
    })

    if result.get("error"):
        print(f"❌ Error: {result.get('error_message')}")
    else:
        print(f"✅ Report created successfully!")
        print(f"   Company: {result['company']} ({result['ticker']})")
        print(f"   Report: {result['report_path']}")
        print(f"   Chart: {result['chart_path']}")
        print(f"   Format: {result['report_format']}")

    # Example 3: Test private company detection
    print("\n" + "="*80)
    print("Example 3: Bosch (Private Company Detection)")
    print("="*80)

    result = create_stock_report.invoke({
        "company": "Bosch",
        "include_analysis": True
    })

    if result.get("error"):
        if result.get("error_type") == "PrivateCompany":
            print(f"ℹ️  {result.get('error_message')}")
            print("   (This is expected behavior - Bosch is primarily private)")
        else:
            print(f"❌ Error: {result.get('error_message')}")
    else:
        print(f"✅ Report created successfully!")
        print(f"   Company: {result['company']} ({result['ticker']})")
        print(f"   Report: {result['report_path']}")

    print("\n" + "="*80)
    print("Examples completed!")
    print("="*80)
    print("\nGenerated reports can be found in: data/reports/")
    print("Generated charts can be found in: data/screenshots/")


if __name__ == "__main__":
    main()
