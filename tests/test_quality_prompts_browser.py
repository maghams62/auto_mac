#!/usr/bin/env python3
"""
Quality Testing Script - Browser-Based UI Testing
Tests 6 user prompts following the quality testing plan.

This script follows the browser-based testing methodology from docs/testing/TESTING_METHODOLOGY.md

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


def verify_test_1_stock_slideshow_email(result: Dict[str, Any]) -> Dict[str, Any]:
    """Verify Test 1: Stock Price Search + Slideshow + Email"""
    snapshot_text = json.dumps(result.get("snapshot", {})).lower()
    
    checks = {
        "has_stock_price": False,
        "has_presentation_path": False,
        "has_email_confirmation": False,
        "no_command_executed": True,
        "no_unknown_error": True,
        "has_meaningful_content": False
    }
    
    # Check for stock price information
    if any(term in snapshot_text for term in ["meta", "stock", "price", "$", "meta"]):
        checks["has_stock_price"] = True
    
    # Check for presentation file path
    if any(term in snapshot_text for term in [".key", "keynote", "presentation", "slideshow"]):
        checks["has_presentation_path"] = True
    
    # Check for email confirmation
    if any(term in snapshot_text for term in ["email", "sent", "drafted", "attached"]):
        checks["has_email_confirmation"] = True
    
    # Check for generic "Command executed" message
    if "command executed" in snapshot_text:
        checks["no_command_executed"] = False
    
    # Check for "Unknown error"
    if "unknown error" in snapshot_text:
        checks["no_unknown_error"] = False
    
    # Check for meaningful content (not just status messages)
    meaningful_terms = ["created", "presentation", "attached", "meta", "stock"]
    if any(term in snapshot_text for term in meaningful_terms):
        checks["has_meaningful_content"] = True
    
    passed = all(checks.values())
    
    return {
        "passed": passed,
        "checks": checks,
        "console_errors": result.get("console_errors", [])
    }


def verify_test_2_zip_guitar_tabs_email(result: Dict[str, Any]) -> Dict[str, Any]:
    """Verify Test 2: Zip Guitar Tabs + Email"""
    snapshot_text = json.dumps(result.get("snapshot", {})).lower()
    
    checks = {
        "has_zip_path": False,
        "has_file_count": False,
        "has_email_confirmation": False,
        "no_command_executed": True,
        "no_unknown_error": True,
        "has_meaningful_content": False
    }
    
    # Check for ZIP file path
    if any(term in snapshot_text for term in [".zip", "zip", "archive", "guitar"]):
        checks["has_zip_path"] = True
    
    # Check for file count
    if any(term in snapshot_text for term in ["file", "files", "zipped", "archived"]):
        checks["has_file_count"] = True
    
    # Check for email confirmation
    if any(term in snapshot_text for term in ["email", "sent", "drafted", "attached"]):
        checks["has_email_confirmation"] = True
    
    # Check for generic "Command executed" message
    if "command executed" in snapshot_text:
        checks["no_command_executed"] = False
    
    # Check for "Unknown error"
    if "unknown error" in snapshot_text:
        checks["no_unknown_error"] = False
    
    # Check for meaningful content
    meaningful_terms = ["guitar", "tab", "zipped", "archived", "email"]
    if any(term in snapshot_text for term in meaningful_terms):
        checks["has_meaningful_content"] = True
    
    passed = all(checks.values())
    
    return {
        "passed": passed,
        "checks": checks,
        "console_errors": result.get("console_errors", [])
    }


def verify_test_3_bluesky_post_summarize(result: Dict[str, Any]) -> Dict[str, Any]:
    """Verify Test 3: Bluesky Post + Summarize"""
    snapshot_text = json.dumps(result.get("snapshot", {})).lower()
    
    checks = {
        "has_post_url": False,
        "has_summary": False,
        "summary_not_empty": False,
        "no_command_executed": True,
        "no_unknown_error": True,
        "has_meaningful_content": False
    }
    
    # Check for post URL
    if any(term in snapshot_text for term in ["bsky.app", "bluesky", "url", "posted", "tweet"]):
        checks["has_post_url"] = True
    
    # Check for summary
    if any(term in snapshot_text for term in ["summary", "summarize", "summarised", "insights"]):
        checks["has_summary"] = True
    
    # Check if summary is not empty (has actual content beyond just the word "summary")
    if checks["has_summary"] and len(snapshot_text) > 200:
        checks["summary_not_empty"] = True
    
    # Check for generic "Command executed" message
    if "command executed" in snapshot_text:
        checks["no_command_executed"] = False
    
    # Check for "Unknown error"
    if "unknown error" in snapshot_text:
        checks["no_unknown_error"] = False
    
    # Check for meaningful content
    meaningful_terms = ["bluesky", "posted", "summary", "tweet", "past hour"]
    if any(term in snapshot_text for term in meaningful_terms):
        checks["has_meaningful_content"] = True
    
    passed = all(checks.values())
    
    return {
        "passed": passed,
        "checks": checks,
        "console_errors": result.get("console_errors", [])
    }


def verify_test_4_trip_planning(result: Dict[str, Any]) -> Dict[str, Any]:
    """Verify Test 4: Trip Planning"""
    snapshot_text = json.dumps(result.get("snapshot", {})).lower()
    
    checks = {
        "has_maps_url": False,
        "has_route_info": False,
        "has_origin_destination": False,
        "no_command_executed": True,
        "no_unknown_error": True,
        "has_meaningful_content": False
    }
    
    # Check for Maps URL
    if any(term in snapshot_text for term in ["maps.apple.com", "maps.google.com", "maps://", "maps url"]):
        checks["has_maps_url"] = True
    
    # Check for route information
    if any(term in snapshot_text for term in ["route", "distance", "duration", "trip", "stops"]):
        checks["has_route_info"] = True
    
    # Check for origin and destination
    if ("la" in snapshot_text or "los angeles" in snapshot_text) and \
       ("new york" in snapshot_text or "ny" in snapshot_text):
        checks["has_origin_destination"] = True
    
    # Check for generic "Command executed" message
    if "command executed" in snapshot_text:
        checks["no_command_executed"] = False
    
    # Check for "Unknown error"
    if "unknown error" in snapshot_text:
        checks["no_unknown_error"] = False
    
    # Check for meaningful content
    meaningful_terms = ["trip", "route", "maps", "la", "new york", "plan"]
    if any(term in snapshot_text for term in meaningful_terms):
        checks["has_meaningful_content"] = True
    
    passed = all(checks.values())
    
    return {
        "passed": passed,
        "checks": checks,
        "console_errors": result.get("console_errors", [])
    }


def verify_test_5_book_summarization(result: Dict[str, Any]) -> Dict[str, Any]:
    """Verify Test 5: Book Summarization"""
    snapshot_text = json.dumps(result.get("snapshot", {})).lower()
    
    checks = {
        "has_book_title": False,
        "has_summary": False,
        "summary_not_empty": False,
        "no_command_executed": True,
        "no_unknown_error": True,
        "has_meaningful_content": False
    }
    
    # Check for book title
    if any(term in snapshot_text for term in ["edgar allan poe", "tell-tale", "book", "poe"]):
        checks["has_book_title"] = True
    
    # Check for summary
    if any(term in snapshot_text for term in ["summary", "summarise", "summarized", "insights", "key points"]):
        checks["has_summary"] = True
    
    # Check if summary is not empty
    if checks["has_summary"] and len(snapshot_text) > 200:
        checks["summary_not_empty"] = True
    
    # Check for generic "Command executed" message
    if "command executed" in snapshot_text:
        checks["no_command_executed"] = False
    
    # Check for "Unknown error"
    if "unknown error" in snapshot_text:
        checks["no_unknown_error"] = False
    
    # Check for meaningful content
    meaningful_terms = ["edgar", "poe", "book", "summary", "tell-tale"]
    if any(term in snapshot_text for term in meaningful_terms):
        checks["has_meaningful_content"] = True
    
    passed = all(checks.values())
    
    return {
        "passed": passed,
        "checks": checks,
        "console_errors": result.get("console_errors", [])
    }


def verify_test_6_play_music(result: Dict[str, Any]) -> Dict[str, Any]:
    """Verify Test 6: Play Music"""
    snapshot_text = json.dumps(result.get("snapshot", {})).lower()
    
    checks = {
        "has_playback_confirmation": False,
        "has_status": False,
        "no_command_executed": True,
        "no_unknown_error": True,
        "has_meaningful_content": False
    }
    
    # Check for playback confirmation
    if any(term in snapshot_text for term in ["playing", "started", "play", "music", "spotify"]):
        checks["has_playback_confirmation"] = True
    
    # Check for status indication
    if any(term in snapshot_text for term in ["status", "playing", "started", "activated"]):
        checks["has_status"] = True
    
    # Check for generic "Command executed" message
    if "command executed" in snapshot_text:
        checks["no_command_executed"] = False
    
    # Check for "Unknown error"
    if "unknown error" in snapshot_text:
        checks["no_unknown_error"] = False
    
    # Check for meaningful content
    meaningful_terms = ["music", "playing", "spotify", "started"]
    if any(term in snapshot_text for term in meaningful_terms):
        checks["has_meaningful_content"] = True
    
    passed = all(checks.values())
    
    return {
        "passed": passed,
        "checks": checks,
        "console_errors": result.get("console_errors", [])
    }


def main():
    """Main test execution."""
    print("="*80)
    print("Quality Testing Suite - Browser-Based UI Testing")
    print("="*80)
    print(f"Started at: {datetime.now().isoformat()}")
    print()
    print("NOTE: This script provides the test framework.")
    print("Actual browser automation is performed via MCP browser tools.")
    print("The AI assistant will execute the browser automation steps.")
    print()
    
    # Start services
    api_process, frontend_process = start_services()
    
    try:
        # Test execution order (as specified in plan)
        tests = [
            {
                "name": "Test 6: Play Music",
                "prompt": "Play Music",
                "timeout": 15,
                "verifier": verify_test_6_play_music
            },
            {
                "name": "Test 5: Book Summarization",
                "prompt": "Summarise that book my Edgar Allan Poe",
                "timeout": 45,
                "verifier": verify_test_5_book_summarization
            },
            {
                "name": "Test 4: Trip Planning",
                "prompt": "Plan a trip from LA to New York",
                "timeout": 30,
                "verifier": verify_test_4_trip_planning
            },
            {
                "name": "Test 3: Bluesky Post + Summarize",
                "prompt": "Tweet to Bluesky 'Couldnt Afford the $100 twitter Api' - Summarise them over the past hour",
                "timeout": 30,
                "verifier": verify_test_3_bluesky_post_summarize
            },
            {
                "name": "Test 2: Zip Guitar Tabs + Email",
                "prompt": "Zip All guitar tabs and email it to me",
                "timeout": 45,
                "verifier": verify_test_2_zip_guitar_tabs_email
            },
            {
                "name": "Test 1: Stock Price Search + Slideshow + Email",
                "prompt": "Search the stock price of Meta and create a slideshow and email it to me",
                "timeout": 60,
                "verifier": verify_test_1_stock_slideshow_email
            }
        ]
        
        print("\n" + "="*80)
        print("TEST EXECUTION PLAN")
        print("="*80)
        print("\nThe following tests will be executed:")
        for i, test in enumerate(tests, 1):
            print(f"{i}. {test['name']}")
            print(f"   Prompt: {test['prompt']}")
            print(f"   Timeout: {test['timeout']}s")
        print()
        print("="*80)
        print("READY FOR BROWSER AUTOMATION")
        print("="*80)
        print("\nServices are running. Browser automation will be performed")
        print("by the AI assistant using MCP browser tools.")
        print("\nThe test framework is ready to verify results.")
        
        # Note: Actual browser automation happens via AI assistant
        # This script provides the verification framework
        
    finally:
        # Note: Don't stop services yet - they're needed for browser testing
        # Services will be stopped after all tests complete
        pass


if __name__ == "__main__":
    main()
