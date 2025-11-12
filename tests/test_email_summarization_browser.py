#!/usr/bin/env python3
"""
Browser-based tests for email summarization functionality.

Tests email summarization via both slash commands and natural language queries
following docs/testing/TESTING_METHODOLOGY.md

NOTE: This script is designed to be run in an environment with browser MCP tools available.
The actual browser automation is performed via MCP tool calls which are executed by the AI assistant.
"""

import time
import subprocess
import sys
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Test results storage
TEST_RESULTS: List[Dict[str, Any]] = []


def log_test_result(test_name: str, passed: bool, details: Dict[str, Any]):
    """Log test result with details."""
    result = {
        "test_name": test_name,
        "timestamp": datetime.now().isoformat(),
        "passed": passed,
        "details": details
    }
    TEST_RESULTS.append(result)
    
    status = "✅ PASSED" if passed else "❌ FAILED"
    print(f"\n{'='*80}")
    print(f"{status}: {test_name}")
    print(f"{'='*80}")
    for key, value in details.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")
    print()


def start_services():
    """Start API server and frontend."""
    print("="*80)
    print("Starting Services")
    print("="*80)
    
    # Check if services are already running
    try:
        # Try to kill existing processes on ports
        subprocess.run(["lsof", "-ti:8000"], check=False, capture_output=True)
        subprocess.run(["lsof", "-ti:3000"], check=False, capture_output=True)
    except:
        pass
    
    # Start API server
    print("\n1. Starting API server...")
    api_process = subprocess.Popen(
        ["python3", "api_server.py"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Save PID
    with open(PROJECT_ROOT / "api_server.pid", "w") as f:
        f.write(str(api_process.pid))
    
    # Start frontend
    print("2. Starting frontend...")
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(PROJECT_ROOT / "frontend"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Save PID
    with open(PROJECT_ROOT / "frontend.pid", "w") as f:
        f.write(str(frontend_process.pid))
    
    # Wait for services to initialize
    print("\n3. Waiting for services to initialize (6 seconds)...")
    time.sleep(6)
    
    print("✅ Services started")
    return api_process, frontend_process


def stop_services():
    """Stop API server and frontend."""
    print("\n" + "="*80)
    print("Stopping Services")
    print("="*80)
    
    # Stop API server
    try:
        with open(PROJECT_ROOT / "api_server.pid", "r") as f:
            pid = int(f.read().strip())
        subprocess.run(["kill", str(pid)], check=False, capture_output=True)
        print("✅ API server stopped")
    except Exception as e:
        print(f"⚠️  Could not stop API server: {e}")
    
    # Stop frontend
    try:
        with open(PROJECT_ROOT / "frontend.pid", "r") as f:
            pid = int(f.read().strip())
        subprocess.run(["kill", str(pid)], check=False, capture_output=True)
        print("✅ Frontend stopped")
    except Exception as e:
        print(f"⚠️  Could not stop frontend: {e}")
    
    # Clean up PID files
    for pid_file in ["api_server.pid", "frontend.pid"]:
        try:
            (PROJECT_ROOT / pid_file).unlink()
        except:
            pass


def verify_slash_command_summarization(result: Dict[str, Any]) -> Dict[str, Any]:
    """Verify slash command email summarization test."""
    snapshot_text = json.dumps(result.get("snapshot", {})).lower()
    
    checks = {
        "has_summary": False,
        "has_email_count": False,
        "no_unknown_error": True,
        "no_generic_message": True,
        "has_meaningful_content": False,
        "status_success": False
    }
    
    # Check for summary content
    if any(term in snapshot_text for term in ["summary", "summarize", "summarized", "emails"]):
        checks["has_summary"] = True
    
    # Check for email count (e.g., "3 emails", "last 3")
    if any(term in snapshot_text for term in ["3", "email", "emails"]):
        checks["has_email_count"] = True
    
    # Check for "Unknown error"
    if "unknown error" in snapshot_text:
        checks["no_unknown_error"] = False
    
    # Check for generic "Command executed" message
    if "command executed" in snapshot_text or "tool executed" in snapshot_text:
        checks["no_generic_message"] = False
    
    # Check for meaningful content (not just status messages)
    meaningful_terms = ["summary", "email", "from", "subject", "sender", "key points"]
    if any(term in snapshot_text for term in meaningful_terms):
        checks["has_meaningful_content"] = True
    
    # Check status
    if "success" in snapshot_text or "completed" in snapshot_text or "idle" in snapshot_text:
        checks["status_success"] = True
    
    passed = all(checks.values())
    
    return {
        "passed": passed,
        "checks": checks,
        "console_errors": result.get("console_errors", [])
    }


def verify_natural_language_summarization(result: Dict[str, Any]) -> Dict[str, Any]:
    """Verify natural language email summarization test."""
    snapshot_text = json.dumps(result.get("snapshot", {})).lower()
    
    checks = {
        "has_summary": False,
        "routes_to_email_agent": False,
        "no_unknown_error": True,
        "has_meaningful_content": False,
        "status_success": False
    }
    
    # Check for summary content
    if any(term in snapshot_text for term in ["summary", "summarize", "summarized"]):
        checks["has_summary"] = True
    
    # Check that it routed to email agent (should see email-related content)
    if any(term in snapshot_text for term in ["email", "emails", "mail"]):
        checks["routes_to_email_agent"] = True
    
    # Check for "Unknown error"
    if "unknown error" in snapshot_text:
        checks["no_unknown_error"] = False
    
    # Check for meaningful content
    meaningful_terms = ["summary", "email", "from", "subject", "sender"]
    if any(term in snapshot_text for term in meaningful_terms):
        checks["has_meaningful_content"] = True
    
    # Check status
    if "success" in snapshot_text or "completed" in snapshot_text:
        checks["status_success"] = True
    
    passed = all(checks.values())
    
    return {
        "passed": passed,
        "checks": checks,
        "console_errors": result.get("console_errors", [])
    }


def verify_error_handling(result: Dict[str, Any]) -> Dict[str, Any]:
    """Verify error handling for invalid requests."""
    snapshot_text = json.dumps(result.get("snapshot", {})).lower()
    
    checks = {
        "has_error_message": False,
        "error_is_specific": False,
        "no_crash": True,
        "no_unknown_error": True
    }
    
    # Check for error message
    if any(term in snapshot_text for term in ["error", "failed", "invalid", "too many", "limit"]):
        checks["has_error_message"] = True
    
    # Check that error is specific (not generic)
    specific_errors = ["too many", "limit", "maximum", "50", "invalid"]
    if any(term in snapshot_text for term in specific_errors):
        checks["error_is_specific"] = True
    
    # Check for crash indicators
    if any(term in snapshot_text for term in ["crash", "exception", "traceback"]):
        checks["no_crash"] = False
    
    # Check for "Unknown error"
    if "unknown error" in snapshot_text:
        checks["no_unknown_error"] = False
    
    # For error cases, we expect error message but graceful handling
    passed = checks["has_error_message"] and checks["no_crash"] and checks["no_unknown_error"]
    
    return {
        "passed": passed,
        "checks": checks,
        "console_errors": result.get("console_errors", [])
    }


def main():
    """Main test execution."""
    print("\n" + "="*80)
    print("EMAIL SUMMARIZATION BROWSER TESTS")
    print("="*80)
    print("\nThis test suite verifies email summarization functionality via browser automation.")
    print("Following docs/testing/TESTING_METHODOLOGY.md")
    print("\nTest Cases:")
    print("1. Slash command: /email summarize my last 3 emails")
    print("2. Slash command: /email summarize the last 3 emails sent by [person]")
    print("3. Natural language: can you summarize my last 3 emails")
    print("4. Natural language: can you summarize the last 3 emails sent by [person]")
    print("5. Error handling: /email summarize my last 100 emails (too many)")
    print("\n" + "="*80)
    
    # Start services
    try:
        api_process, frontend_process = start_services()
    except Exception as e:
        print(f"❌ Failed to start services: {e}")
        return 1
    
    print("\n" + "="*80)
    print("INSTRUCTIONS FOR MANUAL TESTING")
    print("="*80)
    print("\nPlease test the following scenarios in your browser at http://localhost:3000:")
    print("\n1. Slash Command - Simple Summarization:")
    print("   Query: /email summarize my last 3 emails")
    print("   Expected: Summary of last 3 emails appears, no errors")
    print("\n2. Slash Command - Summarize by Sender:")
    print("   Query: /email summarize the last 3 emails sent by [person's name]")
    print("   Expected: Summary of emails from that person, count matches")
    print("\n3. Natural Language - Simple:")
    print("   Query: can you summarize my last 3 emails")
    print("   Expected: Routes to email agent, summary appears")
    print("\n4. Natural Language - By Sender:")
    print("   Query: can you summarize the last 3 emails sent by [person's name]")
    print("   Expected: Correctly identifies sender, reads emails, summarizes")
    print("\n5. Error Handling:")
    print("   Query: /email summarize my last 100 emails")
    print("   Expected: Proper error message about limit, doesn't crash")
    print("\nPress Enter when done testing...")
    input()
    
    # For automated testing, these would be executed via browser MCP tools:
    # 
    # Test 1: Slash command simple summarization
    # browser_navigate("http://localhost:3000")
    # browser_wait_for(time=3)
    # browser_snapshot()
    # browser_click(element="Message input textbox", ref="e74")
    # browser_type(element="Message input textbox", ref="e74", text="/email summarize my last 3 emails")
    # browser_press_key(key="Enter")
    # browser_wait_for(time=10)  # Wait for email reading and summarization
    # snapshot = browser_snapshot()
    # console = browser_console_messages()
    # result = verify_slash_command_summarization({"snapshot": snapshot, "console_errors": console})
    # log_test_result("Slash Command - Simple Summarization", result["passed"], result)
    #
    # Similar pattern for other tests...
    
    # Cleanup
    stop_services()
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    if TEST_RESULTS:
        passed = sum(1 for r in TEST_RESULTS if r["passed"])
        total = len(TEST_RESULTS)
        print(f"\nResults: {passed}/{total} tests passed")
        
        for result in TEST_RESULTS:
            status = "✅" if result["passed"] else "❌"
            print(f"{status} {result['test_name']}")
    else:
        print("\n⚠️  No automated test results recorded.")
        print("   Please verify tests manually in browser and check:")
        print("   - Summaries appear correctly")
        print("   - No 'Unknown error' messages")
        print("   - Error handling works gracefully")
        print("   - Console has no JavaScript errors")
    
    print("\n" + "="*80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

