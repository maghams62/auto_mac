#!/usr/bin/env python3
"""
CLI Test Runner

Provides command-line interface for running tests and viewing results.

Usage:
    python -m tests.run email_attachments          # Run specific test
    python -m tests.run all                         # Run all tests
    python -m tests.run status                      # Show test statuses
    python -m tests.run results email_attachments   # Show test results
    python -m tests.run list                       # List available tests
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.test_runner import TestRunner
from src.utils.test_results import (
    get_test_status,
    get_all_test_statuses,
    get_test_result,
    list_available_tests
)


def format_status(status: dict, verbose: bool = False) -> str:
    """Format test status for display."""
    lines = []
    lines.append(f"Test: {status.get('test_name', 'unknown')}")
    lines.append(f"Status: {status.get('status', 'unknown').upper()}")
    
    if status.get('last_run'):
        lines.append(f"Last Run: {status.get('last_run')}")
    
    if status.get('pass_count') is not None:
        lines.append(f"Passed: {status.get('pass_count')}")
    
    if status.get('fail_count') is not None:
        lines.append(f"Failed: {status.get('fail_count')}")
    
    if status.get('execution_time'):
        lines.append(f"Execution Time: {status.get('execution_time'):.2f}s")
    
    if status.get('error_message'):
        lines.append(f"Error: {status.get('error_message')}")
    
    if verbose and status.get('details'):
        lines.append("\nDetails:")
        lines.append(json.dumps(status.get('details'), indent=2))
    
    return "\n".join(lines)


def run_test_command(test_name: str, json_output: bool = False):
    """Run a specific test."""
    print(f"Running test: {test_name}")
    print("-" * 60)
    
    runner = TestRunner()
    result = runner.run_test(test_name)
    
    if json_output:
        print(json.dumps(result, indent=2))
    else:
        if result.get("error"):
            print(f"❌ Error: {result.get('error_message')}")
        else:
            status_icon = "✅" if result.get("status") == "passed" else "❌"
            print(f"{status_icon} Status: {result.get('status', 'unknown').upper()}")
            print(f"Passed: {result.get('pass_count', 0)}")
            print(f"Failed: {result.get('fail_count', 0)}")
            if result.get("execution_time"):
                print(f"Execution Time: {result.get('execution_time'):.2f}s")
            
            if result.get("details", {}).get("output"):
                print("\nTest Output:")
                print(result["details"]["output"])


def run_all_tests_command(json_output: bool = False):
    """Run all tests."""
    print("Running all tests...")
    print("-" * 60)
    
    runner = TestRunner()
    result = runner.run_all_tests()
    
    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Test Count: {result.get('test_count', 0)}")
        print(f"Total Passed: {result.get('total_passed', 0)}")
        print(f"Total Failed: {result.get('total_failed', 0)}")
        print(f"Total Errors: {result.get('total_errors', 0)}")
        print(f"\nOverall Status: {result.get('status', 'unknown').upper()}")


def status_command(test_name: Optional[str] = None, json_output: bool = False):
    """Show test status(es)."""
    if test_name:
        status = get_test_status(test_name)
        if not status:
            print(f"Test '{test_name}' not found")
            return
        
        if json_output:
            print(json.dumps(status, indent=2))
        else:
            status["test_name"] = test_name
            print(format_status(status))
    else:
        all_statuses = get_all_test_statuses()
        
        if json_output:
            print(json.dumps(all_statuses, indent=2))
        else:
            print("Test Statuses:")
            print("=" * 60)
            
            if not all_statuses:
                print("No test results found")
                return
            
            for name, status in all_statuses.items():
                status["test_name"] = name
                print(format_status(status))
                print()


def results_command(test_name: str, json_output: bool = False):
    """Show detailed test results."""
    result = get_test_result(test_name)
    
    if not result:
        print(f"No results found for test '{test_name}'")
        return
    
    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Test Results: {test_name}")
        print("=" * 60)
        print(json.dumps(result, indent=2))


def list_command(json_output: bool = False):
    """List all available tests."""
    tests = list_available_tests()
    
    if json_output:
        print(json.dumps({"tests": tests, "count": len(tests)}, indent=2))
    else:
        print(f"Available Tests ({len(tests)}):")
        print("=" * 60)
        for test in sorted(tests):
            print(f"  - {test}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Test runner CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tests.run email_attachments          # Run specific test
  python -m tests.run all                         # Run all tests
  python -m tests.run status                      # Show all test statuses
  python -m tests.run status email_attachments    # Show specific test status
  python -m tests.run results email_attachments  # Show detailed results
  python -m tests.run list                        # List available tests
        """
    )
    
    parser.add_argument(
        "command",
        choices=["run", "status", "results", "list", "all"],
        help="Command to execute"
    )
    
    parser.add_argument(
        "test_name",
        nargs="?",
        help="Test name (required for 'run', 'status', 'results')"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    
    args = parser.parse_args()
    
    # Handle commands
    if args.command == "run":
        if not args.test_name:
            print("Error: test_name required for 'run' command")
            sys.exit(1)
        run_test_command(args.test_name, args.json)
    
    elif args.command == "all":
        run_all_tests_command(args.json)
    
    elif args.command == "status":
        status_command(args.test_name, args.json)
    
    elif args.command == "results":
        if not args.test_name:
            print("Error: test_name required for 'results' command")
            sys.exit(1)
        results_command(args.test_name, args.json)
    
    elif args.command == "list":
        list_command(args.json)


if __name__ == "__main__":
    main()

