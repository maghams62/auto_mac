"""
Test Runner Utilities

Provides programmatic test execution using pytest.
Integrates with test_results.py for result storage.

Usage:
    from src.utils.test_runner import TestRunner
    
    runner = TestRunner()
    result = runner.run_test("email_attachments", "tests/test_email_attachments.py")
"""

import subprocess
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import time

from .test_results import (
    save_test_result,
    acquire_test_lock,
    release_test_lock,
    check_test_conflicts
)

logger = logging.getLogger(__name__)

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
TESTS_DIR = BASE_DIR / "tests"


class TestRunner:
    """Test execution runner using pytest."""
    
    def __init__(self):
        self.tests_dir = TESTS_DIR
    
    def _find_test_file(self, test_name: str) -> Optional[Path]:
        """
        Find test file by name.
        
        Args:
            test_name: Name of test (e.g., "email_attachments")
        
        Returns:
            Path to test file or None if not found
        """
        # Try common patterns
        patterns = [
            f"test_{test_name}.py",
            f"test_{test_name}_*.py",
            f"{test_name}.py"
        ]
        
        for pattern in patterns:
            matches = list(self.tests_dir.glob(pattern))
            if matches:
                return matches[0]
        
        # Try exact match
        test_file = self.tests_dir / f"test_{test_name}.py"
        if test_file.exists():
            return test_file
        
        return None
    
    def run_test(
        self,
        test_name: str,
        test_file_path: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run a single test file.
        
        Args:
            test_name: Name of the test
            test_file_path: Optional path to test file (auto-detected if not provided)
            agent_id: Optional agent ID for locking
        
        Returns:
            Dictionary with test execution results
        """
        start_time = time.time()
        
        # Acquire lock
        if not acquire_test_lock(test_name, agent_id):
            conflicts = check_test_conflicts(test_name, agent_id)
            return {
                "test_name": test_name,
                "status": "locked",
                "error": True,
                "error_message": f"Test '{test_name}' is currently locked by another agent",
                "conflicts": conflicts,
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            # Find test file if not provided
            if test_file_path:
                test_path = Path(test_file_path)
            else:
                test_path = self._find_test_file(test_name)
            
            if not test_path or not test_path.exists():
                return {
                    "test_name": test_name,
                    "status": "error",
                    "error": True,
                    "error_message": f"Test file not found for '{test_name}'",
                    "timestamp": datetime.now().isoformat()
                }
            
            logger.info(f"[TEST RUNNER] Running test: {test_name} ({test_path})")
            
            # Run pytest
            result = self._run_pytest(str(test_path), test_name)
            
            execution_time = time.time() - start_time
            
            # Prepare result data
            result_data = {
                "test_name": test_name,
                "test_file": str(test_path),
                "status": result.get("status", "unknown"),
                "pass_count": result.get("passed", 0),
                "fail_count": result.get("failed", 0),
                "error_count": result.get("errors", 0),
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat(),
                "details": result
            }
            
            if result.get("error_message"):
                result_data["error_message"] = result["error_message"]
            
            # Save result
            save_test_result(test_name, result_data)
            
            logger.info(f"[TEST RUNNER] Test '{test_name}' completed: {result_data['status']}")
            
            return result_data
            
        except Exception as e:
            logger.error(f"[TEST RUNNER] Error running test '{test_name}': {e}", exc_info=True)
            execution_time = time.time() - start_time
            
            result_data = {
                "test_name": test_name,
                "status": "error",
                "error": True,
                "error_message": str(e),
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat()
            }
            
            save_test_result(test_name, result_data)
            return result_data
            
        finally:
            # Release lock
            release_test_lock(test_name, agent_id)
    
    def _run_pytest(self, test_file: str, test_name: str) -> Dict[str, Any]:
        """
        Run pytest on a test file and capture results.
        
        Args:
            test_file: Path to test file
            test_name: Name of test
        
        Returns:
            Dictionary with pytest results
        """
        try:
            # Run pytest with JSON output
            cmd = [
                sys.executable,
                "-m", "pytest",
                test_file,
                "-v",
                "--tb=short",
                "--no-header",
                "-q"  # Quiet mode for cleaner output
            ]
            
            logger.info(f"[TEST RUNNER] Executing: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=str(BASE_DIR)
            )
            
            # Parse output
            output = result.stdout + result.stderr
            
            # Count test results from output
            passed = output.count("PASSED")
            failed = output.count("FAILED")
            errors = output.count("ERROR")
            
            # Determine overall status
            if result.returncode == 0:
                status = "passed"
            elif failed > 0:
                status = "failed"
            elif errors > 0:
                status = "error"
            else:
                status = "unknown"
            
            return {
                "status": status,
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "output": output
            }
            
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "error_message": f"Test '{test_name}' timed out after 5 minutes",
                "passed": 0,
                "failed": 0,
                "errors": 1
            }
        except Exception as e:
            logger.error(f"[TEST RUNNER] Error executing pytest: {e}")
            return {
                "status": "error",
                "error_message": str(e),
                "passed": 0,
                "failed": 0,
                "errors": 1
            }
    
    def run_test_suite(self, suite_name: str, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Run a group of related tests.
        
        Args:
            suite_name: Name of test suite (e.g., "email", "bluesky")
            agent_id: Optional agent ID
        
        Returns:
            Dictionary with suite results
        """
        # Find all tests matching suite
        test_files = list(self.tests_dir.glob(f"test_*{suite_name}*.py"))
        
        if not test_files:
            return {
                "suite_name": suite_name,
                "status": "error",
                "error": True,
                "error_message": f"No tests found for suite '{suite_name}'",
                "timestamp": datetime.now().isoformat()
            }
        
        results = []
        for test_file in test_files:
            # Extract test name from filename
            test_name = test_file.stem.replace("test_", "")
            result = self.run_test(test_name, str(test_file), agent_id)
            results.append(result)
        
        # Aggregate results
        total_passed = sum(r.get("pass_count", 0) for r in results)
        total_failed = sum(r.get("fail_count", 0) for r in results)
        total_errors = sum(1 for r in results if r.get("status") == "error")
        
        overall_status = "passed" if total_failed == 0 and total_errors == 0 else "failed"
        
        return {
            "suite_name": suite_name,
            "status": overall_status,
            "test_count": len(results),
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_errors": total_errors,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
    
    def run_all_tests(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Run all tests in the tests directory.
        
        Args:
            agent_id: Optional agent ID
        
        Returns:
            Dictionary with all test results
        """
        test_files = list(self.tests_dir.glob("test_*.py"))
        
        if not test_files:
            return {
                "status": "error",
                "error": True,
                "error_message": "No test files found",
                "timestamp": datetime.now().isoformat()
            }
        
        results = []
        for test_file in test_files:
            test_name = test_file.stem.replace("test_", "")
            result = self.run_test(test_name, str(test_file), agent_id)
            results.append(result)
        
        # Aggregate results
        total_passed = sum(r.get("pass_count", 0) for r in results)
        total_failed = sum(r.get("fail_count", 0) for r in results)
        total_errors = sum(1 for r in results if r.get("status") == "error")
        
        overall_status = "passed" if total_failed == 0 and total_errors == 0 else "failed"
        
        return {
            "status": overall_status,
            "test_count": len(results),
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_errors": total_errors,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }

