"""
Test Result Storage Utilities

Provides test result storage and retrieval for agents and test infrastructure.
Follows the agent_coordination.py pattern for consistency.

Usage:
    from src.utils.test_results import save_test_result, get_test_status
    
    # Save test result
    save_test_result("email_attachments", {
        "status": "passed",
        "pass_count": 5,
        "fail_count": 0,
        "details": {...}
    })
    
    # Get test status
    status = get_test_status("email_attachments")
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
TEST_RESULTS_DIR = BASE_DIR / "data" / "test_results"
RESULTS_DIR = TEST_RESULTS_DIR / "results"
STATUS_BOARD_PATH = TEST_RESULTS_DIR / "status_board.json"
TEST_LOCKS_DIR = BASE_DIR / "data" / ".agent_locks" / "test_infrastructure"

# Ensure directories exist
TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
TEST_LOCKS_DIR.mkdir(parents=True, exist_ok=True)


def _get_agent_id() -> str:
    """Get current agent ID from environment or generate one."""
    agent_id = os.environ.get("AGENT_ID", "unknown_agent")
    return agent_id


def _load_status_board() -> Dict[str, Any]:
    """Load the status board from disk."""
    if not STATUS_BOARD_PATH.exists():
        return {
            "version": "1.0",
            "last_updated": None,
            "tests": {},
            "locks": {},
            "messages": []
        }
    
    try:
        with open(STATUS_BOARD_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading test status board: {e}")
        return {
            "version": "1.0",
            "last_updated": None,
            "tests": {},
            "locks": {},
            "messages": []
        }


def _save_status_board(board: Dict[str, Any]) -> None:
    """Save the status board to disk."""
    try:
        board["last_updated"] = datetime.now().isoformat()
        with open(STATUS_BOARD_PATH, 'w') as f:
            json.dump(board, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving test status board: {e}")


def save_test_result(test_name: str, result_data: Dict[str, Any]) -> str:
    """
    Save a test result to disk.
    
    Args:
        test_name: Name of the test (e.g., "email_attachments")
        result_data: Dictionary containing test result data:
            - status: "passed" | "failed" | "error"
            - pass_count: int
            - fail_count: int
            - details: dict with test-specific details
            - timestamp: ISO format timestamp (optional, auto-generated)
            - execution_time: float seconds (optional)
            - error_message: str (optional, for failures)
    
    Returns:
        Path to saved result file
    """
    timestamp = datetime.now()
    timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
    
    # Ensure result_data has required fields
    if "timestamp" not in result_data:
        result_data["timestamp"] = timestamp.isoformat()
    if "test_name" not in result_data:
        result_data["test_name"] = test_name
    
    # Create result filename
    result_filename = f"{test_name}_{timestamp_str}.json"
    result_path = RESULTS_DIR / result_filename
    
    # Save result file
    try:
        with open(result_path, 'w') as f:
            json.dump(result_data, f, indent=2)
        logger.info(f"[TEST RESULTS] Saved test result: {result_path}")
    except Exception as e:
        logger.error(f"[TEST RESULTS] Error saving result file: {e}")
        raise
    
    # Update status board
    board = _load_status_board()
    if "tests" not in board:
        board["tests"] = {}
    
    board["tests"][test_name] = {
        "last_run": result_data["timestamp"],
        "status": result_data.get("status", "unknown"),
        "pass_count": result_data.get("pass_count", 0),
        "fail_count": result_data.get("fail_count", 0),
        "result_file": result_filename,
        "execution_time": result_data.get("execution_time"),
        "error_message": result_data.get("error_message")
    }
    
    _save_status_board(board)
    
    return str(result_path)


def get_test_status(test_name: str) -> Optional[Dict[str, Any]]:
    """
    Get the latest status for a test.
    
    Args:
        test_name: Name of the test
    
    Returns:
        Dictionary with test status or None if test not found
    """
    board = _load_status_board()
    return board.get("tests", {}).get(test_name)


def get_all_test_statuses() -> Dict[str, Dict[str, Any]]:
    """
    Get status board with all test statuses.
    
    Returns:
        Dictionary mapping test names to their status
    """
    board = _load_status_board()
    return board.get("tests", {})


def get_test_result(test_name: str, timestamp: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get full test result data.
    
    Args:
        test_name: Name of the test
        timestamp: Optional ISO timestamp to get specific result (default: latest)
    
    Returns:
        Full test result dictionary or None if not found
    """
    board = _load_status_board()
    test_info = board.get("tests", {}).get(test_name)
    
    if not test_info:
        return None
    
    # If timestamp specified, find that specific result
    if timestamp:
        # Find result file matching timestamp
        for result_file in RESULTS_DIR.glob(f"{test_name}_*.json"):
            try:
                with open(result_file, 'r') as f:
                    result = json.load(f)
                    if result.get("timestamp") == timestamp:
                        return result
            except Exception as e:
                logger.warning(f"[TEST RESULTS] Error reading result file {result_file}: {e}")
        return None
    
    # Otherwise return latest result
    result_filename = test_info.get("result_file")
    if result_filename:
        result_path = RESULTS_DIR / result_filename
        if result_path.exists():
            try:
                with open(result_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"[TEST RESULTS] Error reading result file: {e}")
    
    return None


def list_available_tests() -> List[str]:
    """
    List all tests that have results.
    
    Returns:
        List of test names
    """
    board = _load_status_board()
    return list(board.get("tests", {}).keys())


def read_test_status_for_agent(test_name: str) -> Dict[str, Any]:
    """
    Get test status in agent-friendly format.
    
    Args:
        test_name: Name of the test
    
    Returns:
        Dictionary with agent-friendly status information
    """
    status = get_test_status(test_name)
    if not status:
        return {
            "test_name": test_name,
            "status": "not_found",
            "message": f"Test '{test_name}' has no recorded results"
        }
    
    return {
        "test_name": test_name,
        "status": status.get("status", "unknown"),
        "last_run": status.get("last_run"),
        "pass_count": status.get("pass_count", 0),
        "fail_count": status.get("fail_count", 0),
        "execution_time": status.get("execution_time"),
        "error_message": status.get("error_message"),
        "message": f"Test '{test_name}' last ran {status.get('last_run')} with status: {status.get('status')}"
    }


def check_if_test_needs_rerun(test_name: str, max_age_hours: int = 24) -> bool:
    """
    Check if a test needs to be rerun based on age.
    
    Args:
        test_name: Name of the test
        max_age_hours: Maximum age in hours before rerun needed
    
    Returns:
        True if test needs rerun, False otherwise
    """
    status = get_test_status(test_name)
    if not status:
        return True  # No results, needs to run
    
    last_run_str = status.get("last_run")
    if not last_run_str:
        return True
    
    try:
        last_run = datetime.fromisoformat(last_run_str.replace('Z', '+00:00'))
        age_hours = (datetime.now(last_run.tzinfo) - last_run).total_seconds() / 3600
        return age_hours > max_age_hours
    except Exception as e:
        logger.warning(f"[TEST RESULTS] Error parsing timestamp: {e}")
        return True  # On error, suggest rerun


# Test execution locks (using agent_coordination pattern)
def acquire_test_lock(test_name: str, agent_id: Optional[str] = None, timeout: int = 3600) -> bool:
    """
    Acquire a lock for test execution to prevent concurrent runs.
    
    Args:
        test_name: Name of the test
        agent_id: Agent identifier (default: from environment)
        timeout: Lock timeout in seconds (default: 1 hour)
    
    Returns:
        True if lock acquired, False otherwise
    """
    if agent_id is None:
        agent_id = _get_agent_id()
    
    lock_file = TEST_LOCKS_DIR / f"{test_name}.lock"
    lock_data = {
        "test_name": test_name,
        "agent_id": agent_id,
        "timestamp": datetime.now().isoformat(),
        "timeout": timeout
    }
    
    # Check if lock exists and is valid
    if lock_file.exists():
        try:
            with open(lock_file, 'r') as f:
                existing_lock = json.load(f)
            
            existing_time = datetime.fromisoformat(existing_lock["timestamp"])
            age_seconds = (datetime.now() - existing_time).total_seconds()
            
            if age_seconds < timeout:
                if existing_lock["agent_id"] != agent_id:
                    logger.warning(f"[TEST RESULTS] Test '{test_name}' is locked by {existing_lock['agent_id']}")
                    return False
                else:
                    # Same agent, refresh lock
                    logger.info(f"[TEST RESULTS] Refreshing lock for test '{test_name}'")
        except Exception as e:
            logger.warning(f"[TEST RESULTS] Error reading lock file: {e}")
    
    # Acquire/refresh lock
    try:
        with open(lock_file, 'w') as f:
            json.dump(lock_data, f, indent=2)
        logger.info(f"[TEST RESULTS] Acquired lock for test '{test_name}' (agent: {agent_id})")
        return True
    except Exception as e:
        logger.error(f"[TEST RESULTS] Error acquiring lock: {e}")
        return False


def release_test_lock(test_name: str, agent_id: Optional[str] = None) -> bool:
    """
    Release a test execution lock.
    
    Args:
        test_name: Name of the test
        agent_id: Agent identifier (default: from environment)
    
    Returns:
        True if lock released, False otherwise
    """
    if agent_id is None:
        agent_id = _get_agent_id()
    
    lock_file = TEST_LOCKS_DIR / f"{test_name}.lock"
    
    if not lock_file.exists():
        logger.warning(f"[TEST RESULTS] No lock file found for test '{test_name}'")
        return False
    
    try:
        with open(lock_file, 'r') as f:
            lock_data = json.load(f)
        
        if lock_data.get("agent_id") != agent_id:
            logger.warning(f"[TEST RESULTS] Lock held by different agent: {lock_data.get('agent_id')}")
            return False
        
        lock_file.unlink()
        logger.info(f"[TEST RESULTS] Released lock for test '{test_name}'")
        return True
    except Exception as e:
        logger.error(f"[TEST RESULTS] Error releasing lock: {e}")
        return False


def check_test_conflicts(test_name: str, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Check if a test is currently locked by another agent.
    
    Args:
        test_name: Name of the test
        agent_id: Agent identifier (default: from environment)
    
    Returns:
        List of conflict information (empty if no conflicts)
    """
    if agent_id is None:
        agent_id = _get_agent_id()
    
    lock_file = TEST_LOCKS_DIR / f"{test_name}.lock"
    conflicts = []
    
    if lock_file.exists():
        try:
            with open(lock_file, 'r') as f:
                lock_data = json.load(f)
            
            if lock_data.get("agent_id") != agent_id:
                conflicts.append({
                    "test_name": test_name,
                    "locked_by": lock_data.get("agent_id"),
                    "timestamp": lock_data.get("timestamp"),
                    "message": f"Test '{test_name}' is currently locked by {lock_data.get('agent_id')}"
                })
        except Exception as e:
            logger.warning(f"[TEST RESULTS] Error reading lock file: {e}")
    
    return conflicts

