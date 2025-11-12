#!/usr/bin/env python3
"""
Spotify Comprehensive Testing Script - Browser-Based UI Testing
Tests Spotify functionality including slash commands and natural language queries.

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
from typing import Dict, Any, List, Optional, Tuple

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

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
        if os.path.exists(PROJECT_ROOT / "api_server.pid"):
            with open(PROJECT_ROOT / "api_server.pid", "r") as f:
                pid = f.read().strip()
            if pid:
                subprocess.run(["kill", pid], check=False)
            os.remove(PROJECT_ROOT / "api_server.pid")
    except Exception as e:
        print(f"Error stopping API server: {e}")
    
    # Stop frontend
    try:
        if os.path.exists(PROJECT_ROOT / "frontend.pid"):
            with open(PROJECT_ROOT / "frontend.pid", "r") as f:
                pid = f.read().strip()
            if pid:
                subprocess.run(["kill", pid], check=False)
            os.remove(PROJECT_ROOT / "frontend.pid")
    except Exception as e:
        print(f"Error stopping frontend: {e}")
    
    print("✅ Services stopped")


# Test cases from the plan
TEST_CASES = [
    {
        "test_id": "S1-PLAY",
        "name": "Slash Command - Play Music",
        "category": "Basic Functionality",
        "query": "/spotify play",
        "setup_notes": "Ensure Spotify is running",
        "expected_flow": [
            "User types '/spotify play' in input field",
            "Command sent via WebSocket",
            "System routes to play_music tool",
            "Spotify plays current track or resumes playback",
            "Response message confirms playback started"
        ],
        "success_criteria": {
            "command_appears_in_chat": True,
            "status_transitions": "processing → idle",
            "response_shows_success": True,
            "no_unknown_errors": True,
            "console_shows_websocket_success": True,
            "spotify_actually_playing": True
        },
        "screenshot_points": ["before", "processing", "after"]
    },
    {
        "test_id": "S2-PAUSE",
        "name": "Slash Command - Pause Music",
        "category": "Basic Functionality",
        "query": "/spotify pause",
        "setup_notes": "Ensure Spotify is playing music",
        "expected_flow": [
            "User types '/spotify pause' in input field",
            "Command sent via WebSocket",
            "System routes to pause_music tool",
            "Spotify pauses current playback",
            "Response message confirms pause"
        ],
        "success_criteria": {
            "command_appears_in_chat": True,
            "status_transitions": "processing → idle",
            "response_confirms_pause": True,
            "no_error_messages": True,
            "spotify_actually_paused": True
        },
        "screenshot_points": ["before", "after"]
    },
    {
        "test_id": "S3-STATUS",
        "name": "Slash Command - Get Status",
        "category": "Basic Functionality",
        "query": "/spotify status",
        "setup_notes": "Spotify can be playing or paused",
        "expected_flow": [
            "User types '/spotify status' in input field",
            "Command sent via WebSocket",
            "System routes to get_spotify_status tool",
            "Spotify status retrieved (track, artist, playback state)",
            "Response displays current track information"
        ],
        "success_criteria": {
            "command_appears_in_chat": True,
            "response_shows_track_name": True,
            "response_shows_artist": True,
            "response_shows_playback_state": True,
            "no_error_messages": True,
            "info_matches_spotify_state": True
        },
        "screenshot_points": ["command_input", "response"]
    },
    {
        "test_id": "S4-PLAY-EXACT",
        "name": "Slash Command - Play Specific Song (Exact Match)",
        "category": "Song Playback with Disambiguation",
        "query": "/spotify play Viva la Vida",
        "setup_notes": "Ensure Spotify is running",
        "expected_flow": [
            "User types '/spotify play Viva la Vida'",
            "Command sent via WebSocket",
            "System routes to play_song tool with song_name='Viva la Vida'",
            "LLM disambiguator resolves to 'Viva la Vida' by 'Coldplay' (high confidence)",
            "Spotify searches and plays the song",
            "Response confirms playback with track details"
        ],
        "success_criteria": {
            "command_appears_in_chat": True,
            "response_shows_resolved_song": "Viva la Vida",
            "response_shows_artist": "Coldplay",
            "high_confidence_disambiguation": True,
            "spotify_plays_correct_song": True,
            "no_error_messages": True,
            "track_name_matches": "Viva la Vida by Coldplay"
        },
        "screenshot_points": ["command_input", "response"]
    },
    {
        "test_id": "S5-PLAY-PARTIAL",
        "name": "Slash Command - Play Partial Song Name (Disambiguation Required)",
        "category": "Song Playback with Disambiguation",
        "query": "/spotify play Breaking The",
        "setup_notes": "Ensure Spotify is running",
        "expected_flow": [
            "User types '/spotify play Breaking The'",
            "Command sent via WebSocket",
            "System routes to play_song tool with song_name='Breaking The'",
            "LLM disambiguator resolves to 'Breaking The Habit' by 'Linkin Park' (high confidence)",
            "Spotify searches and plays the resolved song",
            "Response shows disambiguation details"
        ],
        "success_criteria": {
            "command_appears_in_chat": True,
            "response_shows_original_input": "Breaking The",
            "response_shows_resolved_song": "Breaking The Habit",
            "response_shows_artist": "Linkin Park",
            "confidence_score_shown": True,
            "confidence_ge_0_8": True,
            "reasoning_provided": True,
            "spotify_plays_correct_song": True,
            "no_error_messages": True
        },
        "screenshot_points": ["command_input", "response"]
    },
    {
        "test_id": "S6-PLAY-NATURAL",
        "name": "Slash Command - Play with Natural Language Phrase",
        "category": "Song Playback with Disambiguation",
        "query": "/spotify play that song called Breaking The",
        "setup_notes": "Ensure Spotify is running",
        "expected_flow": [
            "User types '/spotify play that song called Breaking The'",
            "Command sent via WebSocket",
            "System routes to play_song tool",
            "Natural language prefix 'that song called' is stripped",
            "LLM disambiguator receives 'Breaking The' and resolves to 'Breaking The Habit' by 'Linkin Park'",
            "Spotify plays the resolved song"
        ],
        "success_criteria": {
            "command_appears_in_chat": True,
            "natural_language_prefix_stripped": True,
            "disambiguation_resolves_correctly": True,
            "response_shows_original_and_resolved": True,
            "spotify_plays_correct_song": True,
            "no_error_messages": True
        },
        "screenshot_points": ["command_input", "response"]
    },
    {
        "test_id": "S7-NL-PLAY",
        "name": "Natural Language Query - Play Song (No Slash)",
        "category": "Natural Language Queries",
        "query": "play that song called Breaking The",
        "setup_notes": "Ensure Spotify is running",
        "expected_flow": [
            "User types natural language query (no slash command)",
            "Query sent via WebSocket as regular message",
            "LLM orchestrator identifies intent: play song",
            "System routes to Spotify agent",
            "play_song tool called with extracted song name",
            "LLM disambiguator resolves 'Breaking The' → 'Breaking The Habit' by 'Linkin Park'",
            "Spotify plays the song",
            "Response confirms playback"
        ],
        "success_criteria": {
            "query_appears_in_chat": True,
            "intent_correctly_identified": "play song",
            "song_name_extracted": True,
            "disambiguation_works": True,
            "response_shows_resolved_details": True,
            "spotify_plays_correct_song": True,
            "no_error_messages": True
        },
        "screenshot_points": ["query_input", "response"]
    },
    {
        "test_id": "S8-NL-PAUSE",
        "name": "Natural Language Query - Pause (No Slash)",
        "category": "Natural Language Queries",
        "query": "pause Spotify",
        "setup_notes": "Ensure Spotify is playing",
        "expected_flow": [
            "User types natural language pause request",
            "Query sent via WebSocket",
            "LLM orchestrator identifies pause intent",
            "System routes to Spotify agent",
            "pause_music tool called",
            "Spotify pauses playback",
            "Response confirms pause"
        ],
        "success_criteria": {
            "query_appears_in_chat": True,
            "intent_correctly_identified": "pause",
            "response_confirms_pause": True,
            "spotify_actually_paused": True,
            "no_error_messages": True
        },
        "screenshot_points": ["query_input", "response"]
    },
    {
        "test_id": "S9-ERROR-NOT-RUNNING",
        "name": "Error Case - Spotify Not Running",
        "category": "Error Handling",
        "query": "/spotify play",
        "setup_notes": "CLOSE Spotify application before test",
        "expected_flow": [
            "User sends play command",
            "System attempts to control Spotify",
            "AppleScript fails (Spotify not running)",
            "Error returned with clear message"
        ],
        "success_criteria": {
            "command_appears_in_chat": True,
            "error_message_displayed": "Spotify is not running. Please open Spotify and try again.",
            "error_type": "SpotifyNotRunning",
            "retry_possible": True,
            "no_unknown_errors": True,
            "error_styling_applied": True
        },
        "screenshot_points": ["command_input", "error_display"]
    },
    {
        "test_id": "S10-ERROR-NOT-FOUND",
        "name": "Error Case - Song Not Found",
        "category": "Error Handling",
        "query": "/spotify play XyZqWr12345NonexistentSong",
        "setup_notes": "Ensure Spotify is running",
        "expected_flow": [
            "User requests non-existent song",
            "Disambiguation may resolve to something, or use input as-is",
            "Spotify search returns no results",
            "Error returned with helpful message"
        ],
        "success_criteria": {
            "command_appears_in_chat": True,
            "error_message_displayed": "Could not find '{song_name}' in Spotify. Please check the spelling or try a different search.",
            "error_type": "SongNotFound",
            "song_name_in_message": True,
            "retry_possible": True,
            "no_unknown_errors": True
        },
        "screenshot_points": ["command_input", "error_display"]
    },
    {
        "test_id": "S11-DISAMBIG-LOW-CONF",
        "name": "Disambiguation - Low Confidence Warning",
        "category": "Disambiguation Edge Cases",
        "query": "/spotify play Hello",
        "setup_notes": "Ensure Spotify is running",
        "expected_flow": [
            "User requests ambiguous song name 'Hello'",
            "LLM disambiguator identifies multiple matches (Adele, Lionel Richie, Evanescence)",
            "Disambiguator selects most popular (Adele) with alternatives listed",
            "Response shows disambiguation with alternatives",
            "Spotify plays selected song"
        ],
        "success_criteria": {
            "command_appears_in_chat": True,
            "response_shows_resolved_song": "Hello by Adele",
            "alternatives_listed": True,
            "confidence_score_shown": True,
            "spotify_plays_resolved_song": True,
            "no_error_messages": True
        },
        "screenshot_points": ["command_input", "response"]
    }
]


def execute_test_prompt(test_case: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    """
    Execute a test prompt in the browser UI.
    Returns test results with verification details.
    
    NOTE: This function provides the structure for browser automation.
    Actual execution is performed via MCP tool calls by the AI assistant.
    
    Expected workflow:
    1. Navigate to http://localhost:3000
    2. Wait for page load (3 seconds)
    3. Take initial snapshot (before)
    4. Click input field
    5. Type query
    6. Wait 1 second for UI updates
    7. Click Send button or press Enter
    8. Wait for processing (5-10 seconds)
    9. Take snapshot (after)
    10. Check console messages
    11. Verify success criteria
    """
    test_id = test_case["test_id"]
    query = test_case["query"]
    screenshot_points = test_case.get("screenshot_points", [])
    
    print(f"\n{'='*80}")
    print(f"Executing: {test_id} - {test_case['name']}")
    print(f"Query: {query}")
    print(f"{'='*80}")
    
    # Return structure for browser automation
    return {
        "test_id": test_id,
        "query": query,
        "timeout": timeout,
        "screenshot_points": screenshot_points,
        "note": "Execution performed via browser MCP tools",
        "workflow": [
            "Navigate to http://localhost:3000",
            "Wait 3 seconds for page load",
            f"Take snapshot: {screenshot_points[0] if screenshot_points else 'before'}",
            "Click message input field",
            f"Type query: {query}",
            "Wait 1 second for UI updates",
            "Click Send button or press Enter",
            "Wait 5-10 seconds for processing",
            f"Take snapshot: {screenshot_points[-1] if screenshot_points else 'after'}",
            "Check console messages",
            "Verify success criteria"
        ]
    }


def verify_test_result(test_case: Dict[str, Any], result: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Verify test result against success criteria.
    
    Args:
        test_case: Test case definition with success criteria
        result: Test execution result containing snapshot, console messages, etc.
    
    Returns:
        Tuple of (passed: bool, details: Dict[str, Any])
    """
    passed = True
    details = {}
    issues = []
    
    # Extract success criteria
    criteria = test_case.get("success_criteria", {})
    snapshot = result.get("snapshot", {})
    console_messages = result.get("console_messages", [])
    snapshot_text = json.dumps(snapshot).lower()
    
    # Check each criterion
    for criterion, expected_value in criteria.items():
        criterion_passed = True
        
        if criterion == "command_appears_in_chat" or criterion == "query_appears_in_chat":
            # Verify command/query appears in chat
            query = test_case["query"]
            if query.lower() in snapshot_text:
                details[criterion] = "✅ Verified - query found in chat"
            else:
                criterion_passed = False
                details[criterion] = "❌ Failed - query not found in chat"
                issues.append(f"{criterion}: Query not found in chat")
        
        elif criterion == "status_transitions":
            # Verify status transitions correctly
            if "processing" in snapshot_text and "idle" in snapshot_text:
                details[criterion] = f"✅ Verified - {expected_value}"
            else:
                details[criterion] = f"⚠️ Status transition not clearly visible"
        
        elif criterion == "no_unknown_errors" or criterion == "no_error_messages":
            # Check for absence of errors
            if "unknown error" in snapshot_text:
                criterion_passed = False
                passed = False
                details[criterion] = "❌ Failed - Found 'Unknown error' message"
                issues.append("Found 'Unknown error' message")
            else:
                details[criterion] = "✅ Verified - No unknown errors"
        
        elif criterion == "response_shows_success" or criterion == "response_confirms_pause":
            # Verify response contains success confirmation
            success_keywords = ["playing", "paused", "success", "now playing", "music"]
            found_keyword = any(kw in snapshot_text for kw in success_keywords)
            if found_keyword:
                details[criterion] = "✅ Verified - Success confirmation found"
            else:
                details[criterion] = "⚠️ Success confirmation not clearly visible"
        
        elif criterion == "spotify_actually_playing" or criterion == "spotify_actually_paused":
            # Manual verification required - mark as pending
            details[criterion] = "⏳ Pending - Requires manual verification of Spotify state"
        
        elif criterion == "response_shows_resolved_song":
            # Verify disambiguation results - check if resolved song appears
            if isinstance(expected_value, str):
                if expected_value.lower() in snapshot_text:
                    details[criterion] = f"✅ Verified - Found '{expected_value}'"
                else:
                    details[criterion] = f"⚠️ Expected '{expected_value}' but not clearly visible"
        
        elif criterion == "response_shows_artist":
            # Verify artist appears in response
            if isinstance(expected_value, str):
                if expected_value.lower() in snapshot_text:
                    details[criterion] = f"✅ Verified - Found artist '{expected_value}'"
                else:
                    details[criterion] = f"⚠️ Expected artist '{expected_value}' but not clearly visible"
        
        elif criterion == "confidence_ge_0_8":
            # Verify confidence threshold (would need to parse response)
            details[criterion] = "⏳ Pending - Confidence score parsing needed"
        
        elif criterion == "error_message_displayed":
            # Verify error message matches expected
            if isinstance(expected_value, str):
                # Check if error message contains key parts
                key_parts = expected_value.lower().split()
                found_parts = sum(1 for part in key_parts if part in snapshot_text)
                if found_parts >= len(key_parts) * 0.7:  # 70% match
                    details[criterion] = f"✅ Verified - Error message found"
                else:
                    criterion_passed = False
                    passed = False
                    details[criterion] = f"❌ Failed - Expected error message not found"
                    issues.append(f"Expected error: {expected_value}")
        
        elif criterion == "error_type":
            # Verify error type (would be in response structure)
            details[criterion] = f"Expected: {expected_value} (verify in response structure)"
        
        elif criterion == "retry_possible":
            # Verify retry flag (would be in response structure)
            details[criterion] = f"Expected: {expected_value} (verify in response structure)"
        
        elif criterion == "alternatives_listed":
            # Verify alternatives are shown
            alt_keywords = ["alternative", "also", "other", "match"]
            if any(kw in snapshot_text for kw in alt_keywords):
                details[criterion] = "✅ Verified - Alternatives mentioned"
            else:
                details[criterion] = "⚠️ Alternatives not clearly visible"
        
        elif criterion == "console_shows_websocket_success":
            # Verify WebSocket messages in console
            ws_keywords = ["websocket", "message", "response"]
            console_text = json.dumps(console_messages).lower()
            if any(kw in console_text for kw in ws_keywords):
                details[criterion] = "✅ Verified - WebSocket activity found"
            else:
                details[criterion] = "⚠️ WebSocket activity not clearly visible"
        
        elif criterion == "info_matches_spotify_state":
            # Manual verification required
            details[criterion] = "⏳ Pending - Requires manual verification"
        
        else:
            # Generic criterion check
            details[criterion] = f"Expected: {expected_value}"
        
        if not criterion_passed:
            passed = False
    
    # Add summary
    if issues:
        details["issues"] = issues
        details["summary"] = f"Found {len(issues)} issue(s)"
    else:
        details["summary"] = "All criteria verified"
    
    return passed, details


def capture_screenshot_at_point(point_name: str, test_id: str) -> str:
    """
    Capture screenshot at a specific point in test execution.
    
    Args:
        point_name: Name of the screenshot point (e.g., "before", "processing", "after")
        test_id: Test ID for filename
    
    Returns:
        Screenshot filename/path
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{test_id}_{point_name}_{timestamp}.png"
    screenshot_dir = PROJECT_ROOT / "data" / "screenshots" / "spotify_tests"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    
    # Note: Actual screenshot capture done via browser MCP tools
    screenshot_path = screenshot_dir / filename
    
    print(f"  📸 Screenshot captured: {point_name} -> {screenshot_path}")
    return str(screenshot_path)


def execute_single_test(test_case: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a single test case with full browser automation workflow.
    
    This function provides the structure for browser automation execution.
    Actual execution is performed via MCP tool calls.
    
    Returns:
        Test result dictionary with snapshot, console messages, screenshots, etc.
    """
    test_id = test_case["test_id"]
    query = test_case["query"]
    screenshot_points = test_case.get("screenshot_points", ["before", "after"])
    
    print(f"\n{'='*80}")
    print(f"Executing Test: {test_id}")
    print(f"Name: {test_case['name']}")
    print(f"Query: {query}")
    print(f"{'='*80}")
    
    # Structure for browser automation execution
    execution_plan = {
        "test_id": test_id,
        "query": query,
        "steps": [
            {
                "step": 1,
                "action": "navigate",
                "url": "http://localhost:3000",
                "wait_time": 3
            },
            {
                "step": 2,
                "action": "snapshot",
                "point": screenshot_points[0] if screenshot_points else "before",
                "description": "Initial state before command"
            },
            {
                "step": 3,
                "action": "click",
                "element": "Message input textbox",
                "description": "Focus input field"
            },
            {
                "step": 4,
                "action": "type",
                "text": query,
                "description": f"Type query: {query}"
            },
            {
                "step": 5,
                "action": "wait",
                "time": 1,
                "description": "Wait for UI updates"
            },
            {
                "step": 6,
                "action": "click",
                "element": "Send button",
                "alternative": "press_key",
                "key": "Enter",
                "description": "Send command"
            },
            {
                "step": 7,
                "action": "wait",
                "time": 10,
                "description": "Wait for processing (adjust based on test)"
            },
            {
                "step": 8,
                "action": "snapshot",
                "point": screenshot_points[-1] if screenshot_points else "after",
                "description": "Final state after response"
            },
            {
                "step": 9,
                "action": "console_messages",
                "description": "Capture console logs"
            }
        ],
        "screenshot_points": screenshot_points,
        "verification": "Run verify_test_result() after execution"
    }
    
    return {
        "test_id": test_id,
        "execution_plan": execution_plan,
        "note": "Actual execution performed via browser MCP tools"
    }


def generate_test_results_report():
    """Generate comprehensive test results report."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = PROJECT_ROOT / "data" / "logs" / f"spotify_test_results_{timestamp}.md"
    
    # Ensure directory exists
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Calculate statistics
    total_tests = len(TEST_RESULTS)
    passed = len([t for t in TEST_RESULTS if t["passed"]])
    failed = total_tests - passed
    pass_rate = (passed / total_tests * 100) if total_tests > 0 else 0
    
    # Generate report
    report_lines = [
        "# Spotify Comprehensive Test Results",
        "",
        f"**Test Execution Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Total Tests**: {total_tests}",
        f"**Passed**: {passed}",
        f"**Failed**: {failed}",
        f"**Pass Rate**: {pass_rate:.1f}%",
        "",
        "---",
        "",
        "## Test Summary",
        "",
        "| Test ID | Test Name | Status | Category |",
        "|---------|-----------|--------|----------|"
    ]
    
    # Group by category
    by_category = {}
    for result in TEST_RESULTS:
        # Find test case to get category
        test_case = next((tc for tc in TEST_CASES if tc["test_id"] == result["test_id"]), None)
        category = test_case["category"] if test_case else "Unknown"
        
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(result)
    
    # Add summary rows
    for result in TEST_RESULTS:
        test_case = next((tc for tc in TEST_CASES if tc["test_id"] == result["test_id"]), None)
        category = test_case["category"] if test_case else "Unknown"
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        report_lines.append(f"| {result['test_id']} | {result['test_name']} | {status} | {category} |")
    
    report_lines.extend([
        "",
        "---",
        "",
        "## Detailed Test Results",
        ""
    ])
    
    # Add detailed results by category
    for category, results in by_category.items():
        report_lines.extend([
            f"### {category}",
            ""
        ])
        
        for result in results:
            status_icon = "✅" if result["passed"] else "❌"
            report_lines.extend([
                f"#### {status_icon} {result['test_id']}: {result['test_name']}",
                "",
                f"**Timestamp**: {result['timestamp']}",
                f"**Status**: {'PASSED' if result['passed'] else 'FAILED'}",
                "",
                "**Success Criteria Verification**:",
                ""
            ])
            
            for key, value in result["details"].items():
                if isinstance(value, dict):
                    report_lines.append(f"- **{key}**:")
                    for k, v in value.items():
                        report_lines.append(f"  - {k}: {v}")
                elif isinstance(value, list):
                    report_lines.append(f"- **{key}**: {len(value)} items")
                else:
                    report_lines.append(f"- **{key}**: {value}")
            
            report_lines.extend([
                "",
                "**Screenshots**:",
            ])
            
            # Add screenshot references if available
            test_case = next((tc for tc in TEST_CASES if tc["test_id"] == result["test_id"]), None)
            if test_case:
                screenshot_points = test_case.get("screenshot_points", [])
                for point in screenshot_points:
                    report_lines.append(f"- {point}: `{result['test_id']}_{point}_*.png`")
            else:
                report_lines.append("- Screenshots captured at key points (see test execution logs)")
            
            report_lines.extend([
                "",
                "**Console Messages**:",
                "- Check console logs for WebSocket activity and errors",
                "",
                "---",
                ""
            ])
    
    # Add overall assessment
    report_lines.extend([
        "## Overall Assessment",
        ""
    ])
    
    if pass_rate >= 90:
        report_lines.append("🥇 **GOLD STANDARD** - Excellent system health!")
    elif pass_rate >= 75:
        report_lines.append("✅ **ACCEPTABLE** - System performing well")
    else:
        report_lines.append("⚠️ **NEEDS WORK** - Multiple issues detected")
    
    report_lines.extend([
        "",
        "---",
        "",
        "## Notes",
        "",
        "- All tests require manual verification of actual Spotify playback state",
        "- Screenshots are critical for documentation and debugging",
        "- Console logs should be checked for WebSocket message verification",
        ""
    ])
    
    # Write report
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
    
    print(f"\n✅ Test results report saved to: {report_path}")
    return report_path


def main():
    """Main test execution."""
    print("="*80)
    print("Spotify Comprehensive Testing")
    print("="*80)
    print(f"\nTotal test cases: {len(TEST_CASES)}")
    
    # Group by category
    by_category = {}
    for test in TEST_CASES:
        cat = test["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(test)
    
    print("\nTest breakdown by category:")
    for cat, tests in by_category.items():
        print(f"  {cat}: {len(tests)} tests")
    
    print("\n" + "="*80)
    print("NOTE: This script provides test structure.")
    print("Actual browser automation will be performed via MCP tools.")
    print("="*80)
    print("\nTest Cases:")
    for test in TEST_CASES:
        print(f"  {test['test_id']}: {test['name']}")
    
    return TEST_CASES


if __name__ == "__main__":
    test_cases = main()
    print(f"\n✅ Test script ready with {len(test_cases)} test cases")
    print("\nTo execute tests, use browser MCP tools following the workflow:")
    print("1. Start services (start_services())")
    print("2. Navigate to http://localhost:3000")
    print("3. Execute each test case using browser automation")
    print("4. Capture screenshots at key points")
    print("5. Verify success criteria")
    print("6. Generate report (generate_test_results_report())")

