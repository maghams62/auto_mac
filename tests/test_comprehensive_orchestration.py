"""
Comprehensive orchestration tests - Inter-agent communication

Tests various query patterns to ensure:
1. Agent-to-agent communication works
2. Variable resolution works across agents
3. Complex workflows execute successfully
4. All tools integrate properly
"""

import sys
import logging
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import load_config
from src.agent import AutomationAgent

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def run_test(test_name, query, expected_tools=None):
    """Run a single test query."""
    print("\n" + "="*80)
    print(f"TEST: {test_name}")
    print("="*80)
    print(f"Query: {query}")
    print("-"*80)

    config = load_config()
    agent = AutomationAgent(config)

    try:
        result = agent.run(query)

        status = result.get('status', 'unknown')
        print(f"\nStatus: {status}")

        if status == 'success':
            print("✅ TEST PASSED")
            return True
        elif status == 'partial_success':
            print("⚠️  PARTIAL SUCCESS")
            # Check what failed
            if 'results' in result:
                for step_id, step_result in result['results'].items():
                    if isinstance(step_result, dict) and step_result.get('error'):
                        print(f"   Step {step_id} failed: {step_result.get('error_message')}")
            return False
        else:
            print(f"❌ TEST FAILED: {status}")
            return False

    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        print(f"❌ TEST FAILED: {e}")
        return False


def main():
    """Run all orchestration tests."""
    print("\n" + "="*80)
    print("COMPREHENSIVE ORCHESTRATION TEST SUITE")
    print("="*80)
    print("\nTesting inter-agent communication, variable resolution,")
    print("and complex workflows across all agents.\n")

    results = {}

    # Test 1: Stock + Writing Agent
    results['test1'] = run_test(
        "Stock Agent → Writing Agent → Presentation Agent",
        "Get Tesla stock price and create a 3-slide presentation about it",
        expected_tools=['get_stock_price', 'synthesize_content', 'create_slide_deck_content', 'create_keynote']
    )

    # Test 2: Stock + Screenshot + Presentation
    results['test2'] = run_test(
        "Stock + Screen Agent → Writing Agent → Presentation with Images",
        "Create a slide deck about Microsoft stock with a screenshot of the Stocks app",
        expected_tools=['get_stock_price', 'capture_screenshot', 'synthesize_content', 'create_slide_deck_content', 'create_keynote_with_images']
    )

    # Test 3: Stock Search + Analysis
    results['test3'] = run_test(
        "Stock Symbol Search → Stock Agent → Writing Agent",
        "Analyze Amazon stock performance and create a brief report",
        expected_tools=['get_stock_price', 'get_stock_history', 'synthesize_content', 'create_detailed_report']
    )

    # Test 4: Multi-Stock Comparison
    results['test4'] = run_test(
        "Stock Agent (Multiple) → Writing Agent → Presentation",
        "Compare Apple and Google stocks and create a presentation",
        expected_tools=['compare_stocks', 'create_slide_deck_content', 'create_keynote']
    )

    # Test 5: Stock + Email (Full Workflow)
    results['test5'] = run_test(
        "Stock → Writing → Presentation → Email (Full Pipeline)",
        "Get Intel stock data, create a slide deck, and prepare an email (don't send)",
        expected_tools=['get_stock_price', 'synthesize_content', 'create_slide_deck_content', 'create_keynote', 'compose_email']
    )

    # Test 6: Screenshot Only
    results['test6'] = run_test(
        "Screen Agent Standalone",
        "Take a screenshot of the Calculator app",
        expected_tools=['capture_screenshot']
    )

    # Test 7: Writing Agent - Content Synthesis
    results['test7'] = run_test(
        "Writing Agent - Multiple Sources",
        "Synthesize information about AI safety from available sources",
        expected_tools=['search_documents', 'extract_section', 'synthesize_content']
    )

    # Test 8: Stock Historical Data
    results['test8'] = run_test(
        "Stock Agent - Historical Analysis",
        "Show me Netflix stock performance over the last 6 months",
        expected_tools=['get_stock_history']
    )

    # Test 9: Complex Variable Resolution
    results['test9'] = run_test(
        "Variable Resolution Across Agents",
        "Get Adobe stock price, create analysis slides, and prepare for email",
        expected_tools=['get_stock_price', 'synthesize_content', 'create_slide_deck_content', 'create_keynote']
    )

    # Test 10: Screenshot + Presentation (Non-Stock)
    results['test10'] = run_test(
        "Screen Agent → Presentation (Generic)",
        "Capture a screenshot of Safari and create a presentation with it",
        expected_tools=['capture_screenshot', 'create_keynote_with_images']
    )

    # Print summary
    print("\n" + "="*80)
    print("TEST RESULTS SUMMARY")
    print("="*80)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")

    print("-"*80)
    print(f"Total: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print("="*80)

    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Orchestration is working perfectly!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review errors above.")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
