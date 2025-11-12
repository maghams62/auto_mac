#!/usr/bin/env python3
"""
Test enriched NVIDIA stock presentation using DuckDuckGo search.
"""
from src.agent.enriched_stock_agent import create_stock_report_and_email
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("=== Testing Enriched NVIDIA Stock Report ===\n")

    # Run the complete workflow
    result = create_stock_report_and_email.invoke({
        "company": "NVIDIA",
        "recipient": "me"
    })

    logger.info("\n=== RESULT ===")
    print(json.dumps(result, indent=2, default=str))

    if result.get("success"):
        logger.info("\n✅ SUCCESS!")
        logger.info(f"Presentation: {result.get('presentation_path')}")
        logger.info(f"Email Status: {result.get('email_status')}")
        logger.info(f"Searches Performed: {result.get('searches_performed')}")
    else:
        logger.error("\n❌ FAILED!")
        logger.error(f"Error: {result.get('error_message')}")

if __name__ == "__main__":
    main()
