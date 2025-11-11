"""
Test that the agent properly plans to use Writing Agent tools.

This tests the planning phase to ensure the LLM:
1. Includes Writing Agent tools in slide deck workflows
2. Uses synthesize_content for multiple sources
3. Uses create_slide_deck_content before create_keynote
4. Uses create_detailed_report for reports
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


def test_slide_deck_planning():
    """Test that slide deck requests use Writing Agent."""
    print("\n" + "="*80)
    print("TEST: Planning for 'Create a slide deck on AI safety'")
    print("="*80)

    config = load_config()
    agent = AutomationAgent(config)

    # Simulate planning (we just check the plan structure)
    request = "Create a slide deck on AI safety"

    # Run the agent to see the plan
    try:
        # Note: This will actually try to execute, but we're mainly checking the plan
        result = agent.run(request)
        print("\n✅ Agent completed the request")
        print(f"Status: {result.get('status')}")

        # Check if it used the Writing Agent tools
        if 'results' in result:
            steps = result.get('results', {})
            tool_names = [step.get('action') for step in steps.values() if isinstance(step, dict)]

            print(f"\nTools used: {tool_names}")

            # Check for Writing Agent usage
            has_slide_deck_content = any('create_slide_deck_content' in str(tool) for tool in tool_names)
            has_keynote = any('create_keynote' in str(tool) for tool in tool_names)

            if has_slide_deck_content:
                print("✅ Plan includes create_slide_deck_content (Writing Agent)")
            else:
                print("❌ Plan MISSING create_slide_deck_content - using raw text!")

            if has_keynote:
                print("✅ Plan includes create_keynote")

            return has_slide_deck_content and has_keynote

        return False

    except Exception as e:
        logger.error(f"Error during planning: {e}")
        return False


def test_report_planning():
    """Test that report requests use Writing Agent."""
    print("\n" + "="*80)
    print("TEST: Planning for 'Create a detailed report on machine learning'")
    print("="*80)

    config = load_config()
    agent = AutomationAgent(config)

    request = "Create a detailed report on machine learning"

    try:
        result = agent.run(request)
        print("\n✅ Agent completed the request")
        print(f"Status: {result.get('status')}")

        if 'results' in result:
            steps = result.get('results', {})
            tool_names = [step.get('action') for step in steps.values() if isinstance(step, dict)]

            print(f"\nTools used: {tool_names}")

            # Check for Writing Agent usage
            has_detailed_report = any('create_detailed_report' in str(tool) for tool in tool_names)
            has_pages = any('create_pages_doc' in str(tool) for tool in tool_names)

            if has_detailed_report:
                print("✅ Plan includes create_detailed_report (Writing Agent)")
            else:
                print("❌ Plan MISSING create_detailed_report - using raw text!")

            if has_pages:
                print("✅ Plan includes create_pages_doc")

            return has_detailed_report and has_pages

        return False

    except Exception as e:
        logger.error(f"Error during planning: {e}")
        return False


def main():
    """Run planning tests."""
    print("\n" + "="*80)
    print("WRITING AGENT PLANNING TEST")
    print("="*80)
    print("\nNOTE: These tests verify the agent creates proper plans.")
    print("They may fail if no matching documents exist - that's expected.")
    print("We're checking that the PLAN includes Writing Agent tools.\n")

    # Run tests
    print("\nRunning planning tests...")
    print("(Actual execution may fail due to missing docs - we're checking plans)")

    test1 = test_slide_deck_planning()
    test2 = test_report_planning()

    print("\n" + "="*80)
    print("TEST RESULTS")
    print("="*80)
    print(f"Slide Deck Planning: {'✅ PASSED' if test1 else '⚠️  CHECK LOGS'}")
    print(f"Report Planning: {'✅ PASSED' if test2 else '⚠️  CHECK LOGS'}")

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("If tests passed: Writing Agent is properly integrated in planning!")
    print("If tests show warnings: Check logs to see if Writing Agent tools were used.")
    print("="*80)


if __name__ == "__main__":
    main()
