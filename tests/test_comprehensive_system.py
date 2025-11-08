"""
Comprehensive System Test Suite
================================

Tests all agents and tools with various task combinations to ensure
the system never fails and can properly use all available tools.

Test Categories:
1. Single Agent Tests (each agent individually)
2. Multi-Agent Workflows (combinations of agents)
3. Error Recovery Tests (handling failures gracefully)
4. Edge Case Tests (unusual inputs, missing files, etc.)

Agents to Test:
- FILE AGENT: 4 tools (search_documents, extract_section, take_screenshot, organize_files)
- BROWSER AGENT: 5 tools (google_search, navigate_to_url, extract_page_content, take_web_screenshot, close_browser)
- PRESENTATION AGENT: 3 tools (create_keynote, create_keynote_with_images, create_pages_doc)
- EMAIL AGENT: 1 tool (compose_email)
- CRITIC AGENT: 4 tools (verify_output, reflect_on_failure, validate_plan, check_quality)
"""

import logging
import sys
from pathlib import Path
from typing import Dict, List, Any
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils import load_config, setup_logging
from src.documents import DocumentIndexer

logger = logging.getLogger(__name__)


class TestCase:
    """Represents a single test case."""

    def __init__(self, name: str, goal: str, category: str, expected_tools: List[str]):
        self.name = name
        self.goal = goal
        self.category = category
        self.expected_tools = expected_tools
        self.result = None
        self.passed = False


class ComprehensiveTestSuite:
    """Comprehensive test suite for the automation system."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.test_cases = []
        self._define_test_cases()

    def _define_test_cases(self):
        """Define all test cases."""

        # ============================================================
        # CATEGORY 1: SINGLE AGENT - FILE AGENT (4 tools)
        # ============================================================

        self.test_cases.append(TestCase(
            name="File Agent - Search Documents",
            goal="Find the document about fingerstyle guitar",
            category="single_agent_file",
            expected_tools=["search_documents"]
        ))

        self.test_cases.append(TestCase(
            name="File Agent - Extract Section",
            goal="Find the perfect guitar tab and extract page 3",
            category="single_agent_file",
            expected_tools=["search_documents", "extract_section"]
        ))

        self.test_cases.append(TestCase(
            name="File Agent - Take Screenshot",
            goal="Find the perfect guitar tab and capture page 2 as an image",
            category="single_agent_file",
            expected_tools=["search_documents", "take_screenshot"]
        ))

        self.test_cases.append(TestCase(
            name="File Agent - Organize Files",
            goal="Move all guitar PDF files to a folder called 'music_tabs'",
            category="single_agent_file",
            expected_tools=["organize_files"]
        ))

        self.test_cases.append(TestCase(
            name="File Agent - Complex Multi-Tool",
            goal="Find guitar tabs, extract the first 2 pages, take screenshots of them, and organize them in a music folder",
            category="single_agent_file",
            expected_tools=["search_documents", "extract_section", "take_screenshot", "organize_files"]
        ))

        # ============================================================
        # CATEGORY 2: SINGLE AGENT - BROWSER AGENT (5 tools)
        # ============================================================

        self.test_cases.append(TestCase(
            name="Browser Agent - Google Search",
            goal="Search Google for 'LangChain documentation'",
            category="single_agent_browser",
            expected_tools=["google_search"]
        ))

        self.test_cases.append(TestCase(
            name="Browser Agent - Navigate to URL",
            goal="Navigate to https://www.python.org and tell me the page title",
            category="single_agent_browser",
            expected_tools=["navigate_to_url"]
        ))

        self.test_cases.append(TestCase(
            name="Browser Agent - Extract Page Content",
            goal="Navigate to https://news.ycombinator.com and extract the main article titles",
            category="single_agent_browser",
            expected_tools=["navigate_to_url", "extract_page_content"]
        ))

        self.test_cases.append(TestCase(
            name="Browser Agent - Take Web Screenshot",
            goal="Take a screenshot of the Google News homepage",
            category="single_agent_browser",
            expected_tools=["navigate_to_url", "take_web_screenshot"]
        ))

        self.test_cases.append(TestCase(
            name="Browser Agent - Search and Screenshot",
            goal="Search Google for 'OpenAI GPT-4', visit the first result, and take a screenshot",
            category="single_agent_browser",
            expected_tools=["google_search", "navigate_to_url", "take_web_screenshot"]
        ))

        self.test_cases.append(TestCase(
            name="Browser Agent - Full Workflow with Cleanup",
            goal="Search for Python tutorials, visit the top result, extract content, take a screenshot, then close the browser",
            category="single_agent_browser",
            expected_tools=["google_search", "navigate_to_url", "extract_page_content", "take_web_screenshot", "close_browser"]
        ))

        # ============================================================
        # CATEGORY 3: SINGLE AGENT - PRESENTATION AGENT (3 tools)
        # ============================================================

        self.test_cases.append(TestCase(
            name="Presentation Agent - Create Keynote from Text",
            goal="Create a Keynote presentation titled 'AI Overview' with content about artificial intelligence",
            category="single_agent_presentation",
            expected_tools=["create_keynote"]
        ))

        self.test_cases.append(TestCase(
            name="Presentation Agent - Create Keynote with Images",
            goal="Create a Keynote presentation with screenshots from web pages",
            category="single_agent_presentation",
            expected_tools=["create_keynote_with_images"]
        ))

        self.test_cases.append(TestCase(
            name="Presentation Agent - Create Pages Document",
            goal="Create a Pages document with a summary of machine learning concepts",
            category="single_agent_presentation",
            expected_tools=["create_pages_doc"]
        ))

        # ============================================================
        # CATEGORY 4: SINGLE AGENT - EMAIL AGENT (1 tool)
        # ============================================================

        self.test_cases.append(TestCase(
            name="Email Agent - Draft Email",
            goal="Create a draft email with subject 'Test' and body 'Hello World'",
            category="single_agent_email",
            expected_tools=["compose_email"]
        ))

        self.test_cases.append(TestCase(
            name="Email Agent - Email with Attachment",
            goal="Draft an email to test@example.com with a document attached",
            category="single_agent_email",
            expected_tools=["compose_email"]
        ))

        # ============================================================
        # CATEGORY 5: MULTI-AGENT - FILE + PRESENTATION
        # ============================================================

        self.test_cases.append(TestCase(
            name="Multi-Agent - Document to Presentation",
            goal="Find a guitar tab document and create a Keynote presentation from it",
            category="multi_agent_file_presentation",
            expected_tools=["search_documents", "extract_section", "create_keynote"]
        ))

        self.test_cases.append(TestCase(
            name="Multi-Agent - Screenshots to Presentation",
            goal="Find the perfect guitar tab, capture pages 1-3 as screenshots, and create a Keynote with those images",
            category="multi_agent_file_presentation",
            expected_tools=["search_documents", "take_screenshot", "create_keynote_with_images"]
        ))

        # ============================================================
        # CATEGORY 6: MULTI-AGENT - FILE + EMAIL
        # ============================================================

        self.test_cases.append(TestCase(
            name="Multi-Agent - Document to Email",
            goal="Find the document about fingerstyle guitar and email it to test@example.com",
            category="multi_agent_file_email",
            expected_tools=["search_documents", "compose_email"]
        ))

        self.test_cases.append(TestCase(
            name="Multi-Agent - Screenshot to Email",
            goal="Find a guitar tab, capture page 3, and email the screenshot to test@example.com",
            category="multi_agent_file_email",
            expected_tools=["search_documents", "take_screenshot", "compose_email"]
        ))

        # ============================================================
        # CATEGORY 7: MULTI-AGENT - BROWSER + PRESENTATION
        # ============================================================

        self.test_cases.append(TestCase(
            name="Multi-Agent - Web Content to Presentation",
            goal="Search Google for Python tutorials, extract content from the first result, and create a Keynote presentation",
            category="multi_agent_browser_presentation",
            expected_tools=["google_search", "navigate_to_url", "extract_page_content", "create_keynote"]
        ))

        self.test_cases.append(TestCase(
            name="Multi-Agent - Web Screenshot to Presentation (ORIGINAL FAILING TEST)",
            goal="Take a screenshot of the Google News homepage, add it to a presentation slide, and save it",
            category="multi_agent_browser_presentation",
            expected_tools=["navigate_to_url", "take_web_screenshot", "create_keynote_with_images"]
        ))

        # ============================================================
        # CATEGORY 8: MULTI-AGENT - BROWSER + EMAIL
        # ============================================================

        self.test_cases.append(TestCase(
            name="Multi-Agent - Web Content to Email",
            goal="Search for LangChain docs, extract the content, and email it to test@example.com",
            category="multi_agent_browser_email",
            expected_tools=["google_search", "navigate_to_url", "extract_page_content", "compose_email"]
        ))

        self.test_cases.append(TestCase(
            name="Multi-Agent - Web Screenshot to Email",
            goal="Take a screenshot of Python.org and email it to test@example.com",
            category="multi_agent_browser_email",
            expected_tools=["navigate_to_url", "take_web_screenshot", "compose_email"]
        ))

        # ============================================================
        # CATEGORY 9: MULTI-AGENT - BROWSER + PRESENTATION + EMAIL (FULL WORKFLOW)
        # ============================================================

        self.test_cases.append(TestCase(
            name="Multi-Agent - Full Workflow (ORIGINAL TEST)",
            goal="Take a screenshot of the Google News homepage, add it to a presentation slide, and email it to spamstuff062@gmail.com",
            category="multi_agent_full",
            expected_tools=["navigate_to_url", "take_web_screenshot", "create_keynote_with_images", "compose_email"]
        ))

        self.test_cases.append(TestCase(
            name="Multi-Agent - Search, Extract, Present, Email",
            goal="Search Google for AI news, extract content, create a presentation, and email it to test@example.com",
            category="multi_agent_full",
            expected_tools=["google_search", "navigate_to_url", "extract_page_content", "create_keynote", "compose_email"]
        ))

        # ============================================================
        # CATEGORY 10: MULTI-AGENT - FILE + BROWSER + PRESENTATION
        # ============================================================

        self.test_cases.append(TestCase(
            name="Multi-Agent - Document + Web Research + Presentation",
            goal="Find a document about guitar, search Google for related tutorials, and create a combined presentation",
            category="multi_agent_complex",
            expected_tools=["search_documents", "google_search", "navigate_to_url", "extract_page_content", "create_keynote"]
        ))

        # ============================================================
        # CATEGORY 11: MULTI-AGENT - ALL AGENTS (ULTIMATE TEST)
        # ============================================================

        self.test_cases.append(TestCase(
            name="Multi-Agent - Ultimate Full Stack Test",
            goal="Find a guitar tab, organize it, search web for guitar tutorials, take screenshots, create presentation with both local and web screenshots, and email everything to test@example.com",
            category="multi_agent_ultimate",
            expected_tools=["search_documents", "organize_files", "google_search", "take_web_screenshot", "take_screenshot", "create_keynote_with_images", "compose_email"]
        ))

        # ============================================================
        # CATEGORY 12: EDGE CASES & ERROR RECOVERY
        # ============================================================

        self.test_cases.append(TestCase(
            name="Edge Case - Nonexistent Document",
            goal="Find a document about quantum physics in ancient Rome",
            category="edge_case",
            expected_tools=["search_documents"]  # Should fail gracefully
        ))

        self.test_cases.append(TestCase(
            name="Edge Case - Invalid URL",
            goal="Navigate to https://this-website-definitely-does-not-exist-12345.com",
            category="edge_case",
            expected_tools=["navigate_to_url"]  # Should handle error
        ))

        self.test_cases.append(TestCase(
            name="Edge Case - Empty Category File Organization",
            goal="Organize files matching 'xyz123abc' category",
            category="edge_case",
            expected_tools=["organize_files"]  # Should return no files
        ))

        logger.info(f"Defined {len(self.test_cases)} test cases across {len(set(tc.category for tc in self.test_cases))} categories")

    def run_all_tests(self, orchestrator, dry_run: bool = False):
        """
        Run all test cases.

        Args:
            orchestrator: The orchestrator instance to use
            dry_run: If True, only validate test definitions without running
        """
        logger.info("=" * 80)
        logger.info("COMPREHENSIVE SYSTEM TEST SUITE")
        logger.info("=" * 80)

        if dry_run:
            logger.info("DRY RUN MODE - Validating test definitions only")
            self._print_test_summary()
            return

        results = {
            "total": len(self.test_cases),
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "categories": {}
        }

        for i, test_case in enumerate(self.test_cases, 1):
            logger.info(f"\n{'=' * 80}")
            logger.info(f"TEST {i}/{len(self.test_cases)}: {test_case.name}")
            logger.info(f"Category: {test_case.category}")
            logger.info(f"Goal: {test_case.goal}")
            logger.info(f"Expected Tools: {', '.join(test_case.expected_tools)}")
            logger.info(f"{'=' * 80}\n")

            try:
                # Execute test
                from src.orchestrator.state import Budget

                result = orchestrator.execute(
                    goal=test_case.goal,
                    context={},
                    budget=Budget(tokens=50000, time_s=300, steps=20)
                )

                test_case.result = result

                # Evaluate result
                if result.get("success"):
                    test_case.passed = True
                    results["passed"] += 1
                    logger.info(f"✅ TEST PASSED: {test_case.name}")
                else:
                    test_case.passed = False
                    results["failed"] += 1
                    logger.error(f"❌ TEST FAILED: {test_case.name}")
                    logger.error(f"Reason: {result.get('summary', 'Unknown error')}")

                # Track by category
                if test_case.category not in results["categories"]:
                    results["categories"][test_case.category] = {"passed": 0, "failed": 0}

                if test_case.passed:
                    results["categories"][test_case.category]["passed"] += 1
                else:
                    results["categories"][test_case.category]["failed"] += 1

            except Exception as e:
                logger.error(f"❌ TEST EXCEPTION: {test_case.name}")
                logger.error(f"Exception: {e}", exc_info=True)
                test_case.passed = False
                results["failed"] += 1

            # Ask to continue after each test
            if i < len(self.test_cases):
                print("\n" + "=" * 80)
                response = input("Press Enter to continue to next test (or 'q' to quit, 's' to skip remaining): ")
                if response.lower() == 'q':
                    results["skipped"] = len(self.test_cases) - i
                    break
                elif response.lower() == 's':
                    results["skipped"] = len(self.test_cases) - i
                    break

        # Print final results
        self._print_final_results(results)

        # Save results to file
        self._save_results(results)

    def _print_test_summary(self):
        """Print summary of all test cases."""
        logger.info("\n" + "=" * 80)
        logger.info("TEST SUITE SUMMARY")
        logger.info("=" * 80)

        categories = {}
        for tc in self.test_cases:
            if tc.category not in categories:
                categories[tc.category] = []
            categories[tc.category].append(tc)

        for category, tests in sorted(categories.items()):
            logger.info(f"\n{category.upper().replace('_', ' ')} ({len(tests)} tests):")
            for tc in tests:
                logger.info(f"  • {tc.name}")
                logger.info(f"    Goal: {tc.goal}")
                logger.info(f"    Expected Tools: {', '.join(tc.expected_tools)}")

        logger.info(f"\n{'=' * 80}")
        logger.info(f"TOTAL TESTS: {len(self.test_cases)}")
        logger.info(f"CATEGORIES: {len(categories)}")
        logger.info(f"{'=' * 80}\n")

    def _print_final_results(self, results: Dict[str, Any]):
        """Print final test results."""
        logger.info("\n" + "=" * 80)
        logger.info("FINAL TEST RESULTS")
        logger.info("=" * 80)

        logger.info(f"\nOverall:")
        logger.info(f"  Total Tests: {results['total']}")
        logger.info(f"  ✅ Passed: {results['passed']}")
        logger.info(f"  ❌ Failed: {results['failed']}")
        logger.info(f"  ⊘ Skipped: {results['skipped']}")
        logger.info(f"  Success Rate: {(results['passed'] / max(results['total'] - results['skipped'], 1)) * 100:.1f}%")

        logger.info(f"\nBy Category:")
        for category, stats in sorted(results["categories"].items()):
            total = stats["passed"] + stats["failed"]
            success_rate = (stats["passed"] / max(total, 1)) * 100
            logger.info(f"  {category}: {stats['passed']}/{total} passed ({success_rate:.1f}%)")

        logger.info("\n" + "=" * 80)

    def _save_results(self, results: Dict[str, Any]):
        """Save results to JSON file."""
        output_file = Path(__file__).parent / "test_results.json"

        test_results = []
        for tc in self.test_cases:
            test_results.append({
                "name": tc.name,
                "category": tc.category,
                "goal": tc.goal,
                "expected_tools": tc.expected_tools,
                "passed": tc.passed,
                "result_summary": tc.result.get("summary") if tc.result else None
            })

        output_data = {
            "summary": results,
            "tests": test_results
        }

        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)

        logger.info(f"\nResults saved to: {output_file}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Comprehensive system test suite")
    parser.add_argument("--dry-run", action="store_true", help="Only show test definitions without running")
    parser.add_argument("--category", type=str, help="Run only tests from specific category")
    args = parser.parse_args()

    # Load configuration
    config = load_config()
    setup_logging(config)

    logger.info("Initializing test suite...")

    # Create test suite
    test_suite = ComprehensiveTestSuite(config)

    if args.dry_run:
        test_suite.run_all_tests(None, dry_run=True)
        return

    # Initialize orchestrator
    logger.info("Initializing orchestrator...")
    from src.orchestrator import LangGraphOrchestrator

    indexer = DocumentIndexer(config)
    orchestrator = LangGraphOrchestrator(config, indexer)

    # Filter by category if specified
    if args.category:
        logger.info(f"Filtering tests for category: {args.category}")
        test_suite.test_cases = [
            tc for tc in test_suite.test_cases
            if tc.category == args.category
        ]
        logger.info(f"Running {len(test_suite.test_cases)} tests")

    # Run tests
    test_suite.run_all_tests(orchestrator)

    logger.info("\nTest suite completed!")


if __name__ == "__main__":
    main()
