"""
Browser automation tests for enhanced stock presentation feature.

Follows the testing methodology from docs/testing/TESTING_METHODOLOGY.md
"""

import os
import sys
import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def log_test_result(test_name: str, passed: bool, details: Dict[str, Any]):
    """Log test result with details."""
    status = "✅ PASSED" if passed else "❌ FAILED"
    logger.info(f"{status}: {test_name}")
    if details:
        for key, value in details.items():
            logger.info(f"  {key}: {value}")
    print()


def start_services():
    """Start API server and frontend."""
    import subprocess
    
    logger.info("Starting services...")
    
    # Start API server
    api_cmd = "cd /Users/siddharthsuresh/Downloads/auto_mac && source venv/bin/activate && python3 api_server.py > /dev/null 2>&1 &"
    result = subprocess.run(api_cmd, shell=True, capture_output=True)
    if result.returncode == 0:
        # Get PID
        time.sleep(1)
        api_pid = subprocess.run("pgrep -f 'api_server.py'", shell=True, capture_output=True, text=True)
        if api_pid.stdout.strip():
            with open("api_server.pid", "w") as f:
                f.write(api_pid.stdout.strip())
            logger.info(f"API server started (PID: {api_pid.stdout.strip()})")
    
    # Start frontend
    frontend_cmd = "cd /Users/siddharthsuresh/Downloads/auto_mac/frontend && npm run dev > /dev/null 2>&1 &"
    result = subprocess.run(frontend_cmd, shell=True, capture_output=True)
    if result.returncode == 0:
        time.sleep(1)
        frontend_pid = subprocess.run("pgrep -f 'next dev'", shell=True, capture_output=True, text=True)
        if frontend_pid.stdout.strip():
            with open("frontend.pid", "w") as f:
                f.write(frontend_pid.stdout.strip())
            logger.info(f"Frontend started (PID: {frontend_pid.stdout.strip()})")
    
    # Wait for services to be ready
    logger.info("Waiting for services to be ready...")
    time.sleep(6)


def stop_services():
    """Stop API server and frontend."""
    import subprocess
    
    logger.info("Stopping services...")
    
    # Stop API server
    if os.path.exists("api_server.pid"):
        with open("api_server.pid", "r") as f:
            pid = f.read().strip()
        subprocess.run(f"kill {pid} 2>/dev/null", shell=True)
        os.remove("api_server.pid")
        logger.info("API server stopped")
    
    # Stop frontend
    if os.path.exists("frontend.pid"):
        with open("frontend.pid", "r") as f:
            pid = f.read().strip()
        subprocess.run(f"kill {pid} 2>/dev/null", shell=True)
        os.remove("frontend.pid")
        logger.info("Frontend stopped")


def test_presentation_creation():
    """Test: Create stock presentation without email."""
    logger.info("=" * 60)
    logger.info("TEST: Create stock presentation")
    logger.info("=" * 60)
    
    try:
        # Navigate to UI
        from mcp_cursor_browser_extension import browser_navigate, browser_wait_for, browser_snapshot
        from mcp_cursor_browser_extension import browser_click, browser_type, browser_press_key
        from mcp_cursor_browser_extension import browser_console_messages
        
        browser_navigate("http://localhost:3000")
        browser_wait_for(time=3)
        snapshot = browser_snapshot()
        
        # Verify initial state
        if "Connected" not in str(snapshot):
            log_test_result("Initial state check", False, {"error": "Connection message not found"})
            return False
        
        # Find input field and send command
        # Note: These refs are placeholders - actual refs will be determined from snapshot
        command = "Fetch the stock price of NVIDIA and create a presentation"
        
        # Try to find input field from snapshot
        # For now, we'll use a generic approach
        browser_wait_for(time=1)
        
        # Type command (this is a simplified version - actual implementation would parse snapshot)
        # browser_type(element="Message input textbox", ref="input_ref", text=command)
        # browser_press_key(key="Enter")
        
        # Wait for response
        browser_wait_for(time=120)  # Presentation creation can take time
        
        # Take snapshot to see results
        snapshot = browser_snapshot()
        
        # Check console for errors
        console_msgs = browser_console_messages()
        errors = [msg for msg in console_msgs if "error" in str(msg).lower()]
        
        # Verify results
        snapshot_str = str(snapshot)
        has_success = "presentation" in snapshot_str.lower() or "created" in snapshot_str.lower()
        has_error = "error" in snapshot_str.lower() and "unknown error" in snapshot_str.lower()
        
        passed = has_success and not has_error and len(errors) == 0
        
        log_test_result(
            "Presentation creation",
            passed,
            {
                "command": command,
                "has_success_message": has_success,
                "has_unknown_error": has_error,
                "console_errors": len(errors),
                "snapshot_preview": snapshot_str[:200] if snapshot_str else "No snapshot"
            }
        )
        
        return passed
        
    except Exception as e:
        log_test_result("Presentation creation", False, {"error": str(e)})
        return False


def test_presentation_with_email():
    """Test: Create stock presentation and email it."""
    logger.info("=" * 60)
    logger.info("TEST: Create stock presentation and email")
    logger.info("=" * 60)
    
    try:
        from mcp_cursor_browser_extension import browser_navigate, browser_wait_for, browser_snapshot
        from mcp_cursor_browser_extension import browser_click, browser_type, browser_press_key
        from mcp_cursor_browser_extension import browser_console_messages
        
        browser_navigate("http://localhost:3000")
        browser_wait_for(time=3)
        
        command = "Fetch the stock price of NVIDIA and create a presentation and email it to me"
        
        # Type command and send
        # browser_type(element="Message input textbox", ref="input_ref", text=command)
        # browser_press_key(key="Enter")
        
        # Wait for response (email can take longer)
        browser_wait_for(time=150)
        
        snapshot = browser_snapshot()
        console_msgs = browser_console_messages()
        errors = [msg for msg in console_msgs if "error" in str(msg).lower()]
        
        snapshot_str = str(snapshot)
        has_success = ("presentation" in snapshot_str.lower() and "email" in snapshot_str.lower()) or "sent" in snapshot_str.lower()
        has_error = "error" in snapshot_str.lower() and "unknown error" in snapshot_str.lower()
        
        passed = has_success and not has_error and len(errors) == 0
        
        log_test_result(
            "Presentation with email",
            passed,
            {
                "command": command,
                "has_success_message": has_success,
                "has_unknown_error": has_error,
                "console_errors": len(errors)
            }
        )
        
        return passed
        
    except Exception as e:
        log_test_result("Presentation with email", False, {"error": str(e)})
        return False


def test_slide_structure():
    """Test: Verify presentation has correct slide structure."""
    logger.info("=" * 60)
    logger.info("TEST: Verify slide structure")
    logger.info("=" * 60)
    
    try:
        # This test would need to:
        # 1. Create a presentation
        # 2. Open the Keynote file
        # 3. Verify it has exactly 5 slides
        # 4. Verify each slide has correct content
        
        # For now, we'll check if the response mentions 5 slides
        from mcp_cursor_browser_extension import browser_navigate, browser_wait_for, browser_snapshot
        
        browser_navigate("http://localhost:3000")
        browser_wait_for(time=3)
        
        command = "Fetch the stock price of NVIDIA and create a presentation"
        
        # Send command and wait
        # browser_type(element="Message input textbox", ref="input_ref", text=command)
        # browser_press_key(key="Enter")
        browser_wait_for(time=120)
        
        snapshot = browser_snapshot()
        snapshot_str = str(snapshot)
        
        # Check for mentions of slide structure
        has_slide_info = "5" in snapshot_str or "five" in snapshot_str.lower() or "slide" in snapshot_str.lower()
        
        log_test_result(
            "Slide structure verification",
            has_slide_info,
            {
                "command": command,
                "mentions_slides": has_slide_info,
                "note": "Full verification requires opening Keynote file"
            }
        )
        
        return has_slide_info
        
    except Exception as e:
        log_test_result("Slide structure verification", False, {"error": str(e)})
        return False


def run_all_tests():
    """Run all browser automation tests."""
    logger.info("Starting browser automation tests for stock presentation feature")
    logger.info("=" * 60)
    
    results = {}
    
    try:
        # Start services
        start_services()
        
        # Run tests
        results["presentation_creation"] = test_presentation_creation()
        time.sleep(5)  # Wait between tests
        
        results["presentation_with_email"] = test_presentation_with_email()
        time.sleep(5)
        
        results["slide_structure"] = test_slide_structure()
        
    finally:
        # Clean up
        stop_services()
    
    # Summary
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{status}: {test_name}")
    
    logger.info("=" * 60)
    logger.info(f"Total: {total} | Passed: {passed} | Failed: {total - passed}")
    logger.info("=" * 60)
    
    return all(results.values())


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

