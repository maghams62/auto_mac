"""
Test All Agent Tools
====================
Quick tests for all 17 tools across 5 agents
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils import load_config, setup_logging
from src.agent.agent import AutomationAgent

logger = logging.getLogger(__name__)


def run_test(name, goal, expected_success=True):
    """Run a single test."""
    print(f"\n{'='*80}")
    print(f"TEST: {name}")
    print(f"{'='*80}")
    print(f"Goal: {goal}")
    print(f"{'='*80}\n")

    try:
        config = load_config()
        agent = AutomationAgent(config)

        result = agent.run(goal)

        success = result.get("success") or result.get("status") == "success"

        if success:
            print(f"\n✅ {name} - PASSED")
            if result.get('steps_executed'):
                print(f"   Steps executed: {result['steps_executed']}")
            return True
        else:
            print(f"\n❌ {name} - FAILED")
            print(f"   Error: {result.get('message', 'Unknown error')}")
            return False

    except Exception as e:
        print(f"\n❌ {name} - EXCEPTION: {e}")
        logger.error(f"Test {name} failed with exception", exc_info=True)
        return False


def main():
    """Run all tool tests."""

    config = load_config()
    setup_logging(config)

    print("\n" + "="*80)
    print("COMPREHENSIVE TOOL TESTING")
    print("Testing all 17 tools across 5 agents")
    print("="*80)

    tests = [
        # FILE AGENT TESTS (4 tools)
        ("File Agent - Search Documents",
         "Find the document about fingerstyle guitar"),

        ("File Agent - Extract Section",
         "Find the perfect guitar tab and extract page 3"),

        ("File Agent - Take Screenshot (PDF)",
         "Find a guitar tab and capture page 2 as an image"),

        ("File Agent - Organize Files",
         "Move all non-PDF files from test_data to a folder called test_organization"),

        # BROWSER AGENT TESTS (5 tools)
        ("Browser Agent - Google Search",
         "Search Google for 'Python documentation'"),

        ("Browser Agent - Navigate to URL",
         "Navigate to https://www.python.org"),

        ("Browser Agent - Extract Page Content",
         "Go to https://news.ycombinator.com and extract the top article titles"),

        ("Browser Agent - Take Web Screenshot",
         "Take a screenshot of the Python.org homepage"),

        ("Browser Agent - Close Browser",
         "Search Google for AI news then close the browser"),

        # PRESENTATION AGENT TESTS (3 tools)
        ("Presentation Agent - Create Keynote (Text)",
         "Create a Keynote presentation about Python programming"),

        ("Presentation Agent - Create Keynote (Images)",
         "Take a screenshot of Python.org and create a presentation with it"),

        ("Presentation Agent - Create Pages Doc",
         "Create a Pages document about machine learning"),

        # EMAIL AGENT TESTS (1 tool)
        ("Email Agent - Compose Email",
         "Draft an email with subject 'Test' and body 'Testing the system'"),

        # MULTI-TOOL TESTS
        ("Multi-Tool - File to Email",
         "Find a guitar tab document and email it to test@example.com"),

        ("Multi-Tool - Web to Presentation",
         "Search for Python tutorials, take a screenshot, and create a presentation"),

        ("Multi-Tool - ORIGINAL FAILING CASE",
         "Take a screenshot of Google News, add to presentation, email to spamstuff062@gmail.com"),
    ]

    results = []

    for i, (name, goal) in enumerate(tests, 1):
        print(f"\n[Test {i}/{len(tests)}]")

        passed = run_test(name, goal)
        results.append((name, passed))

        # Ask to continue
        if i < len(tests):
            try:
                response = input("\nPress Enter for next test (or 'q' to quit, 's' to skip remaining): ")
                if response.lower() == 'q':
                    print("\nQuitting...")
                    break
                elif response.lower() == 's':
                    print(f"\nSkipping remaining {len(tests) - i} tests...")
                    break
            except (EOFError, KeyboardInterrupt):
                print("\nInterrupted, showing results so far...")
                break

    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed_count = sum(1 for _, p in results if p)
    total = len(results)

    # Group by agent
    file_tests = [r for r in results if "File Agent" in r[0]]
    browser_tests = [r for r in results if "Browser Agent" in r[0]]
    presentation_tests = [r for r in results if "Presentation Agent" in r[0]]
    email_tests = [r for r in results if "Email Agent" in r[0]]
    multi_tests = [r for r in results if "Multi-Tool" in r[0]]

    def print_category(name, tests):
        if tests:
            passed = sum(1 for _, p in tests if p)
            print(f"\n{name}: {passed}/{len(tests)} passed")
            for test_name, passed_test in tests:
                symbol = "✅" if passed_test else "❌"
                print(f"  {symbol} {test_name}")

    print_category("FILE AGENT", file_tests)
    print_category("BROWSER AGENT", browser_tests)
    print_category("PRESENTATION AGENT", presentation_tests)
    print_category("EMAIL AGENT", email_tests)
    print_category("MULTI-TOOL WORKFLOWS", multi_tests)

    print(f"\n{'='*80}")
    print(f"OVERALL: {passed_count}/{total} tests passed ({passed_count/max(total,1)*100:.1f}%)")
    print(f"{'='*80}")

    # Tool coverage
    print(f"\n📊 Tool Coverage:")
    print(f"  FILE AGENT: {len(file_tests)}/4 tools tested")
    print(f"  BROWSER AGENT: {len(browser_tests)}/5 tools tested")
    print(f"  PRESENTATION AGENT: {len(presentation_tests)}/3 tools tested")
    print(f"  EMAIL AGENT: {len(email_tests)}/1 tool tested")
    print(f"  MULTI-TOOL: {len(multi_tests)} workflow tests")

    total_tools_tested = len(file_tests) + len(browser_tests) + len(presentation_tests) + len(email_tests)
    print(f"\n  TOTAL: {total_tools_tested}/13 core tools tested")


if __name__ == "__main__":
    main()
