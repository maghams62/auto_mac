"""
Direct Agent Testing - Test without orchestrator
Uses the agent directly to test functionality
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils import load_config, setup_logging
from src.documents import DocumentIndexer
from src.agent.agent import AutomationAgent

logger = logging.getLogger(__name__)


def test_original_failing_case():
    """Test the original failing case directly."""

    print("\n" + "="*80)
    print("TESTING ORIGINAL FAILING CASE")
    print("="*80)
    print("\nGoal: Take a screenshot of the Google News homepage,")
    print("      add it to a presentation slide, and email it")
    print("\n" + "="*80 + "\n")

    # Load configuration
    config = load_config()
    setup_logging(config)

    # Initialize agent
    logger.info("Initializing agent...")
    indexer = DocumentIndexer(config)
    agent = AutomationAgent(config)

    # Execute task
    goal = "take a screenshot of the google news home webpage add it to a presentation slide and email it to spamstuff062@gmail.com"

    logger.info(f"Executing: {goal}")
    result = agent.run(goal)

    print("\n" + "="*80)
    print("RESULT")
    print("="*80)

    if result.get("success") or result.get("status") == "success":
        print("✅ TEST PASSED!")
        print(f"\nSummary: {result.get('summary', result.get('message', 'Success'))}")

        if result.get("steps_executed"):
            print(f"\nSteps executed: {result['steps_executed']}")

        return True
    else:
        print("❌ TEST FAILED!")
        print(f"\nError: {result.get('error', result.get('message', 'Unknown error'))}")

        if result.get("steps_status"):
            print("\nSteps status:")
            for i, status in enumerate(result["steps_status"], 1):
                symbol = "✅" if status == "success" else "❌"
                print(f"  {symbol} Step {i}: {status}")

        return False


def test_simple_browser_screenshot():
    """Test simple browser screenshot."""

    print("\n" + "="*80)
    print("TESTING SIMPLE BROWSER SCREENSHOT")
    print("="*80)
    print("\nGoal: Take a screenshot of the Google News homepage")
    print("\n" + "="*80 + "\n")

    # Load configuration
    config = load_config()
    setup_logging(config)

    # Initialize agent
    logger.info("Initializing agent...")
    indexer = DocumentIndexer(config)
    agent = AutomationAgent(config)

    # Execute task
    goal = "Take a screenshot of the Google News homepage"

    logger.info(f"Executing: {goal}")
    result = agent.run(goal)

    print("\n" + "="*80)
    print("RESULT")
    print("="*80)

    if result.get("success") or result.get("status") == "success":
        print("✅ TEST PASSED!")
        print(f"\nSummary: {result.get('summary', result.get('message', 'Success'))}")
        return True
    else:
        print("❌ TEST FAILED!")
        print(f"\nError: {result.get('error', result.get('message', 'Unknown error'))}")
        return False


def main():
    """Run tests."""

    tests = [
        ("Simple Browser Screenshot", test_simple_browser_screenshot),
        ("Original Failing Case", test_original_failing_case),
    ]

    results = []

    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            logger.error(f"Test {name} raised exception: {e}", exc_info=True)
            results.append((name, False))

        # Ask to continue
        if name != tests[-1][0]:
            response = input("\nPress Enter to continue to next test (or 'q' to quit): ")
            if response.lower() == 'q':
                break

    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for _, p in results if p)
    total = len(results)

    for name, passed_test in results:
        symbol = "✅" if passed_test else "❌"
        print(f"{symbol} {name}")

    print(f"\nTotal: {passed}/{total} passed ({(passed/total*100):.1f}%)")
    print("="*80)


if __name__ == "__main__":
    main()
