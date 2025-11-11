#!/usr/bin/env python3
"""
Quick test script for google_search to diagnose issues.
"""

import sys
import logging
from src.agent.google_agent import google_search

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_google_search():
    """Test google_search with a simple query."""
    logger.info("=" * 80)
    logger.info("TESTING: google_search()")
    logger.info("=" * 80)

    query = "Python programming language"
    num_results = 5

    logger.info(f"Query: {query}")
    logger.info(f"Num results: {num_results}")
    logger.info("-" * 80)

    try:
        result = google_search.invoke({
            "query": query,
            "num_results": num_results,
            "search_type": "web"
        })

        logger.info("=" * 80)
        logger.info("RESULT:")
        logger.info("=" * 80)

        if result.get("error"):
            logger.error(f"ERROR: {result.get('error_type')}")
            logger.error(f"Message: {result.get('error_message')}")
            logger.error(f"Retry possible: {result.get('retry_possible')}")
            return False

        logger.info(f"Query: {result.get('query')}")
        logger.info(f"Total results: {result.get('total_results')}")
        logger.info(f"Source: {result.get('source')}")
        logger.info(f"Summary: {result.get('summary', 'N/A')}")
        logger.info("-" * 80)

        results = result.get("results", [])
        logger.info(f"Retrieved {len(results)} results:")
        logger.info("-" * 80)

        for idx, item in enumerate(results, 1):
            logger.info(f"{idx}. {item.get('title', 'N/A')}")
            logger.info(f"   URL: {item.get('link', 'N/A')}")
            logger.info(f"   Snippet: {item.get('snippet', 'N/A')[:100]}...")
            logger.info(f"   Display link: {item.get('display_link', 'N/A')}")
            logger.info("")

        logger.info("=" * 80)
        logger.info("✅ TEST PASSED")
        logger.info("=" * 80)
        return True

    except Exception as e:
        logger.error(f"EXCEPTION: {e}", exc_info=True)
        logger.info("=" * 80)
        logger.info("❌ TEST FAILED")
        logger.info("=" * 80)
        return False

if __name__ == "__main__":
    success = test_google_search()
    sys.exit(0 if success else 1)
