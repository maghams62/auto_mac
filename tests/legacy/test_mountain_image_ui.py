#!/usr/bin/env python3
"""
Browser-based UI test for mountain image search.

Tests the complete UI flow:
1. Image appears in FileList component
2. Image thumbnail is visible and clickable
3. Preview modal opens and displays image
4. Modal can be closed

NOTE: This script provides the structure for browser automation.
Actual execution is performed via MCP browser tools by the AI assistant.
"""

import time
import subprocess
import sys
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent

# Test configuration
TEST_QUERY = "pull up the picture of a mountain"
UI_URL = "http://localhost:3000"
API_URL = "http://localhost:8000"
TIMEOUT = 90  # seconds

# Test results storage
TEST_RESULTS: List[Dict[str, Any]] = []


def log_test_result(test_id: str, test_name: str, passed: bool, details: Dict[str, Any]):
    """Log test result with details."""
    result = {
        "test_id": test_id,
        "test_name": test_name,
        "timestamp": datetime.now().isoformat(),
        "passed": passed,
        "details": details
    }
    TEST_RESULTS.append(result)
    
    status = "✅ PASSED" if passed else "❌ FAILED"
    print(f"\n{'='*80}")
    print(f"{status}: {test_id} - {test_name}")
    print(f"{'='*80}")
    for key, value in details.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        elif isinstance(value, list):
            print(f"  {key}: {len(value)} items")
        else:
            print(f"  {key}: {value}")
    print()


def start_services():
    """Start API server and frontend."""
    print("="*80)
    print("Starting services for browser testing...")
    print("="*80)
    
    # Check if services are already running
    import requests
    try:
        requests.get(f"{API_URL}/health", timeout=2)
        print("✅ API server already running")
    except:
        # Start API server
        api_server_path = PROJECT_ROOT / "api_server.py"
        if api_server_path.exists():
            subprocess.Popen(
                ["python3", str(api_server_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(PROJECT_ROOT)
            )
            print("✅ API server started")
            time.sleep(3)
        else:
            print("⚠️  API server file not found")
    
    try:
        requests.get(UI_URL, timeout=2)
        print("✅ Frontend already running")
    except:
        # Start frontend
        frontend_path = PROJECT_ROOT / "frontend"
        if frontend_path.exists():
            subprocess.Popen(
                ["npm", "run", "dev"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(frontend_path)
            )
            print("✅ Frontend started")
            time.sleep(3)
        else:
            print("⚠️  Frontend directory not found")
    
    # Wait for services to be ready
    print("Waiting 6 seconds for services to initialize...")
    time.sleep(6)
    print("✅ Services ready")


def stop_services():
    """Stop API server and frontend."""
    print("\n" + "="*80)
    print("Stopping services...")
    print("="*80)
    
    # Stop API server
    api_pid_file = PROJECT_ROOT / "api_server.pid"
    if api_pid_file.exists():
        with open(api_pid_file) as f:
            pid = f.read().strip()
        try:
            subprocess.run(["kill", pid], check=False)
            api_pid_file.unlink()
            print("✅ API server stopped")
        except Exception as e:
            print(f"⚠️  Error stopping API server: {e}")
    
    # Stop frontend
    frontend_pid_file = PROJECT_ROOT / "frontend.pid"
    if frontend_pid_file.exists():
        with open(frontend_pid_file) as f:
            pid = f.read().strip()
        try:
            subprocess.run(["kill", pid], check=False)
            frontend_pid_file.unlink()
            print("✅ Frontend stopped")
        except Exception as e:
            print(f"⚠️  Error stopping frontend: {e}")
    
    print("✅ Services stopped")


# Test case definition
TEST_CASE = {
    "test_id": "MOUNTAIN-IMAGE-UI",
    "name": "Mountain Image UI Rendering Test",
    "category": "UI Rendering",
    "query": TEST_QUERY,
    "expected_flow": [
        "Navigate to UI",
        "Wait for WebSocket connection",
        "Type query in input field",
        "Query sent via WebSocket",
        "Response received with image results",
        "Image thumbnail appears in FileList",
        "Thumbnail is clickable",
        "Click opens preview modal",
        "Full-size image displays in modal",
        "Modal can be closed"
    ],
    "success_criteria": {
        "page_loads": True,
        "websocket_connected": True,
        "query_sent": True,
        "response_received": True,
        "image_thumbnail_visible": True,
        "thumbnail_size_correct": "60x60px",
        "thumbnail_clickable": True,
        "modal_opens": True,
        "image_displays_in_modal": True,
        "modal_closable": True,
        "no_console_errors": True,
        "no_network_errors": True,
        "thumbnail_url_works": True,
        "preview_url_works": True,
        "preview_head_request_200": True,  # HEAD request to /api/files/preview returns 200
        "preview_get_request_200": True,  # GET request to /api/files/preview returns 200 with image
        "preview_image_loads": True  # Image actually loads in preview modal
    }
}


def print_test_instructions():
    """Print instructions for manual browser testing."""
    print("\n" + "="*80)
    print("MOUNTAIN IMAGE UI TEST - BROWSER AUTOMATION INSTRUCTIONS")
    print("="*80)
    print(f"\nTest Query: '{TEST_QUERY}'")
    print(f"UI URL: {UI_URL}")
    print(f"API URL: {API_URL}")
    print("\nThis test will be executed using browser automation tools.")
    print("The AI assistant will:")
    print("1. Navigate to the UI")
    print("2. Wait for page to load")
    print("3. Type the query")
    print("4. Wait for response")
    print("5. Verify image appears")
    print("6. Click on image")
    print("7. Verify modal opens")
    print("8. Verify HEAD request to /api/files/preview returns 200")
    print("9. Verify GET request to /api/files/preview returns 200 with image")
    print("10. Verify image displays in modal")
    print("11. Test modal close")
    print("12. Check browser console for [PreviewModal] logs")
    print("13. Check backend logs for [FILE PREVIEW] entries")
    print("\nSuccess Criteria:")
    for criterion, expected in TEST_CASE["success_criteria"].items():
        print(f"  ✅ {criterion}: {expected}")
    print("="*80)


def generate_test_report():
    """Generate test report."""
    print("\n" + "="*80)
    print("TEST REPORT")
    print("="*80)
    
    total_tests = len(TEST_RESULTS)
    passed_tests = sum(1 for r in TEST_RESULTS if r["passed"])
    failed_tests = total_tests - passed_tests
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    
    if failed_tests > 0:
        print("\nFailed Tests:")
        for result in TEST_RESULTS:
            if not result["passed"]:
                print(f"  ❌ {result['test_id']}: {result['test_name']}")
                for key, value in result["details"].items():
                    if isinstance(value, dict) and "error" in str(value).lower():
                        print(f"    Error: {value}")
    
    # Save report to file
    report_path = PROJECT_ROOT / f"mountain_image_ui_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w') as f:
        json.dump({
            "test_case": TEST_CASE,
            "results": TEST_RESULTS,
            "summary": {
                "total": total_tests,
                "passed": passed_tests,
                "failed": failed_tests
            }
        }, f, indent=2)
    
    print(f"\nReport saved to: {report_path}")
    print("="*80)
    
    return failed_tests == 0


if __name__ == "__main__":
    print("="*80)
    print("MOUNTAIN IMAGE UI RENDERING TEST")
    print("="*80)
    print("\nThis test validates:")
    print("1. Image appears in UI with thumbnail")
    print("2. Image is clickable")
    print("3. Preview modal opens")
    print("4. Image displays in modal")
    print("5. Modal can be closed")
    print("\nNOTE: This script provides test structure.")
    print("Actual browser automation will be performed by AI assistant.")
    print("="*80)
    
    # Start services
    try:
        start_services()
        
        # Print test instructions
        print_test_instructions()
        
        # Note: Actual browser automation will be performed by AI assistant
        # using MCP browser tools (browser_navigate, browser_click, etc.)
        print("\n" + "="*80)
        print("READY FOR BROWSER AUTOMATION")
        print("="*80)
        print("\nThe AI assistant will now execute the browser test.")
        print("Please wait for test results...")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Don't stop services automatically - let user decide
        # stop_services()
        pass

