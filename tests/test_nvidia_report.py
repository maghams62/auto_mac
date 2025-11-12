#!/usr/bin/env python3
"""
Test NVIDIA stock report generation.
"""
from src.agent.enriched_stock_agent import create_enriched_stock_report
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("=== Testing NVIDIA Stock Report ===\n")

    # Test report generation (HTML is more reliable than PDF on macOS)
    result = create_enriched_stock_report.invoke({
        "company": "NVIDIA",
        "output_format": "html"
    })

    logger.info("\n=== RESULT ===")
    print(json.dumps(result, indent=2, default=str))

    if result.get("success"):
        logger.info("\n✅ SUCCESS!")
        logger.info(f"Report: {result.get('report_path')}")
        logger.info(f"Format: {result.get('output_format')}")
        logger.info(f"Company: {result.get('company')}")
        logger.info(f"Price: {result.get('current_price')}")
        logger.info(f"Data Date: {result.get('data_date')}")
    else:
        logger.error("\n❌ FAILED!")
        logger.error(f"Error: {result.get('error_message')}")

if __name__ == "__main__":
    main()
