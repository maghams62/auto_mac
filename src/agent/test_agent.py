"""
Test Agent - Provides tools for agents to check test status and results.

This agent allows other agents to:
- Check test status without re-running tests
- Get detailed test results
- List all available test statuses
- Trigger test execution (with proper locking)
"""

import logging
from typing import Dict, Any, Optional, List
from langchain_core.tools import tool

from ..utils.test_results import (
    get_test_status,
    get_all_test_statuses,
    get_test_result,
    list_available_tests,
    read_test_status_for_agent,
    check_if_test_needs_rerun
)
from ..utils.test_runner import TestRunner

logger = logging.getLogger(__name__)


@tool
def check_test_status(test_name: str) -> Dict[str, Any]:
    """
    Check the status of a test without re-running it.
    
    This tool reads the latest test result from storage, allowing agents
    to check if tests have passed without executing them again.
    
    Args:
        test_name: Name of the test (e.g., "email_attachments", "tweet_accuracy")
    
    Returns:
        Dictionary with test status information:
        - test_name: Name of the test
        - status: "passed" | "failed" | "error" | "not_found"
        - last_run: ISO timestamp of last run
        - pass_count: Number of passing tests
        - fail_count: Number of failing tests
        - execution_time: Time taken in seconds
        - error_message: Error message if failed
        - message: Human-readable status message
    
    Example:
        check_test_status("email_attachments")
    """
    logger.info(f"[TEST AGENT] Checking status for test: {test_name}")
    
    try:
        status = read_test_status_for_agent(test_name)
        return status
    except Exception as e:
        logger.error(f"[TEST AGENT] Error checking test status: {e}")
        return {
            "test_name": test_name,
            "status": "error",
            "error": True,
            "error_message": str(e),
            "message": f"Error checking status for test '{test_name}': {e}"
        }


@tool
def get_test_results(test_name: str, timestamp: Optional[str] = None) -> Dict[str, Any]:
    """
    Get full test results for a specific test.
    
    Returns detailed test execution results including stdout, stderr,
    and all test details. Useful for debugging or detailed analysis.
    
    Args:
        test_name: Name of the test
        timestamp: Optional ISO timestamp to get specific result (default: latest)
    
    Returns:
        Dictionary with full test result data:
        - test_name: Name of the test
        - status: Overall status
        - test_file: Path to test file
        - pass_count: Number of passing tests
        - fail_count: Number of failing tests
        - execution_time: Time taken
        - details: Full pytest output and details
        - timestamp: When test was run
    
    Example:
        get_test_results("email_attachments")
        get_test_results("email_attachments", timestamp="2025-01-15T14:30:22")
    """
    logger.info(f"[TEST AGENT] Getting results for test: {test_name}")
    
    try:
        result = get_test_result(test_name, timestamp)
        
        if not result:
            return {
                "test_name": test_name,
                "status": "not_found",
                "error": True,
                "error_message": f"No results found for test '{test_name}'",
                "message": f"Test '{test_name}' has no recorded results"
            }
        
        return {
            "test_name": test_name,
            "status": "success",
            "result": result,
            "message": f"Retrieved results for test '{test_name}'"
        }
    except Exception as e:
        logger.error(f"[TEST AGENT] Error getting test results: {e}")
        return {
            "test_name": test_name,
            "status": "error",
            "error": True,
            "error_message": str(e),
            "message": f"Error retrieving results for test '{test_name}': {e}"
        }


@tool
def list_test_statuses() -> Dict[str, Any]:
    """
    List status of all available tests.
    
    Returns a summary of all tests that have been run, showing their
    latest status, last run time, and pass/fail counts.
    
    Returns:
        Dictionary with:
        - test_count: Number of tests found
        - tests: Dictionary mapping test names to their status
        - summary: Overall summary statistics
    
    Example:
        list_test_statuses()
    """
    logger.info("[TEST AGENT] Listing all test statuses")
    
    try:
        all_statuses = get_all_test_statuses()
        test_names = list_available_tests()
        
        # Calculate summary
        total_passed = sum(1 for s in all_statuses.values() if s.get("status") == "passed")
        total_failed = sum(1 for s in all_statuses.values() if s.get("status") == "failed")
        total_errors = sum(1 for s in all_statuses.values() if s.get("status") == "error")
        
        return {
            "test_count": len(test_names),
            "tests": all_statuses,
            "summary": {
                "total": len(test_names),
                "passed": total_passed,
                "failed": total_failed,
                "errors": total_errors
            },
            "message": f"Found {len(test_names)} test(s) with recorded results"
        }
    except Exception as e:
        logger.error(f"[TEST AGENT] Error listing test statuses: {e}")
        return {
            "status": "error",
            "error": True,
            "error_message": str(e),
            "message": f"Error listing test statuses: {e}"
        }


@tool
def run_test(test_name: str) -> Dict[str, Any]:
    """
    Trigger test execution for a specific test.
    
    This tool runs the test and saves results. Uses locks to prevent
    concurrent execution by multiple agents.
    
    Args:
        test_name: Name of the test to run
    
    Returns:
        Dictionary with test execution results:
        - test_name: Name of the test
        - status: "passed" | "failed" | "error" | "locked"
        - pass_count: Number of passing tests
        - fail_count: Number of failing tests
        - execution_time: Time taken
        - details: Full execution details
        - message: Status message
    
    Example:
        run_test("email_attachments")
    """
    logger.info(f"[TEST AGENT] Running test: {test_name}")
    
    try:
        import os
        agent_id = os.environ.get("AGENT_ID", "test_agent")
        
        runner = TestRunner()
        result = runner.run_test(test_name, agent_id=agent_id)
        
        # Format response
        if result.get("error"):
            return {
                "test_name": test_name,
                "status": result.get("status", "error"),
                "error": True,
                "error_message": result.get("error_message"),
                "message": f"Test '{test_name}' execution failed: {result.get('error_message')}"
            }
        
        return {
            "test_name": test_name,
            "status": result.get("status", "unknown"),
            "pass_count": result.get("pass_count", 0),
            "fail_count": result.get("fail_count", 0),
            "execution_time": result.get("execution_time"),
            "details": result.get("details", {}),
            "message": f"Test '{test_name}' completed with status: {result.get('status')}"
        }
    except Exception as e:
        logger.error(f"[TEST AGENT] Error running test: {e}")
        return {
            "test_name": test_name,
            "status": "error",
            "error": True,
            "error_message": str(e),
            "message": f"Error running test '{test_name}': {e}"
        }


# Export tools
TEST_AGENT_TOOLS = [
    check_test_status,
    get_test_results,
    list_test_statuses,
    run_test,
]


class TestAgent:
    """
    Test Agent - Provides test status and execution tools for other agents.
    
    This agent allows other agents to:
    - Check test status without re-running
    - Get detailed test results
    - Trigger test execution
    - List all available tests
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in TEST_AGENT_TOOLS}
        logger.info(f"[TEST AGENT] Initialized with {len(self.tools)} tools")
    
    def get_tools(self):
        """Get all test agent tools."""
        return TEST_AGENT_TOOLS
    
    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a test agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Test agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }
        
        tool = self.tools[tool_name]
        logger.info(f"[TEST AGENT] Executing: {tool_name}")
        
        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[TEST AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }

