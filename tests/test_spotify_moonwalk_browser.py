#!/usr/bin/env python3
"""
Browser-based test for Michael Jackson moonwalk song query.

Tests that the query "play that Michael Jackson song where he does the moonwalk"
creates a plan with ONLY play_song (no google_search) and correctly plays
"Smooth Criminal" in Spotify.

Following TESTING_METHODOLOGY.md for browser automation testing.
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


# Test case for moonwalk query
TEST_CASE = {
    "test_id": "MOONWALK-DIRECT",
    "name": "Michael Jackson Moonwalk - Direct play_song",
    "category": "Descriptive Song Query",
    "query": "play that Michael Jackson song where he does the moonwalk",
    "setup_notes": "Ensure Spotify is running",
    "expected_song": "Smooth Criminal",
    "expected_artist": "Michael Jackson",
    "expected_plan_steps": [
        {
            "action": "play_song",
            "parameters": {
                "song_name": "that Michael Jackson song where he does the moonwalk"
            }
        },
        {
            "action": "reply_to_user"
        }
    ],
    "forbidden_actions": ["google_search", "extract_page_content", "navigate_to_url"],
    "expected_flow": [
        "User types query in input field",
        "Query sent via WebSocket",
        "System creates plan with ONLY play_song (no google_search)",
        "play_song tool identifies 'Smooth Criminal' by Michael Jackson",
        "Spotify searches and plays the song",
        "Response confirms correct song identification"
    ],
    "success_criteria": {
        "command_appears_in_chat": True,
        "plan_contains_only_play_song": True,
        "plan_does_not_contain_google_search": True,
        "response_shows_correct_song": True,
        "response_shows_correct_artist": True,
        "no_error_messages": True,
        "spotify_actually_playing": True,
        "spotify_plays_correct_song": True,
        "status_transitions": "processing → idle"
    },
    "screenshot_points": ["before", "plan", "after"]
}


def execute_test_prompt(test_case: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    """
    Execute a test prompt in the browser UI.
    Returns test results with verification details.
    
    NOTE: This function provides the structure for browser automation.
    Actual execution is performed via MCP browser tools by the AI assistant.
    
    Expected workflow:
    1. Navigate to http://localhost:3000
    2. Wait for page load (3 seconds)
    3. Take initial snapshot (before)
    4. Click input field
    5. Type query
    6. Wait 1 second for UI updates
    7. Click Send button or press Enter
    8. Wait for plan to appear (5-10 seconds)
    9. Take snapshot (plan) - verify plan structure
    10. Wait for processing to complete (10-20 seconds for LLM disambiguation + Spotify playback)
    11. Take snapshot (after)
    12. Check console messages
    13. Verify success criteria
    14. Check Spotify status to verify correct song is playing
    """
    test_id = test_case["test_id"]
    query = test_case["query"]
    screenshot_points = test_case.get("screenshot_points", [])
    
    print(f"\n{'='*80}")
    print(f"Executing: {test_id} - {test_case['name']}")
    print(f"Query: {query}")
    print(f"Expected: {test_case.get('expected_song')} by {test_case.get('expected_artist')}")
    print(f"{'='*80}")
    
    # Return structure for browser automation
    return {
        "test_id": test_id,
        "query": query,
        "timeout": timeout,
        "screenshot_points": screenshot_points,
        "expected_song": test_case.get("expected_song"),
        "expected_artist": test_case.get("expected_artist"),
        "expected_plan_steps": test_case.get("expected_plan_steps", []),
        "forbidden_actions": test_case.get("forbidden_actions", []),
        "note": "Execution performed via browser MCP tools",
        "workflow": [
            "Navigate to http://localhost:3000",
            "Wait 3 seconds for page load",
            f"Take snapshot: {screenshot_points[0] if screenshot_points else 'before'}",
            "Click message input field",
            f"Type query: {query}",
            "Wait 1 second for UI updates",
            "Click Send button or press Enter",
            "Wait 5-10 seconds for plan to appear",
            f"Take snapshot: {screenshot_points[1] if len(screenshot_points) > 1 else 'plan'} - VERIFY PLAN STRUCTURE",
            "Verify plan contains ONLY play_song (no google_search)",
            "Wait 10-20 seconds for processing (LLM disambiguation + Spotify playback)",
            f"Take snapshot: {screenshot_points[-1] if screenshot_points else 'after'}",
            "Check console messages for errors",
            "Verify response shows correct song and artist",
            "Check Spotify status to verify correct song is playing",
            "Verify all success criteria"
        ]
    }


def verify_test_result(test_case: Dict[str, Any], result: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Verify test results against success criteria.
    
    Args:
        test_case: Original test case definition
        result: Test execution result from browser
        
    Returns:
        Tuple of (passed: bool, details: dict)
    """
    success_criteria = test_case.get("success_criteria", {})
    expected_song = test_case.get("expected_song", "").lower()
    expected_artist = test_case.get("expected_artist", "").lower()
    forbidden_actions = test_case.get("forbidden_actions", [])
    
    details = {
        "response_received": result.get("response_received", False),
        "plan_received": result.get("plan_received", False),
        "plan_steps": result.get("plan_steps", []),
        "response_text": result.get("response_text", ""),
        "console_errors": result.get("console_errors", []),
        "spotify_status": result.get("spotify_status", {}),
        "verification": {}
    }
    
    passed = True
    verification = {}
    
    # Check if plan was received
    if not result.get("plan_received"):
        verification["plan_received"] = False
        passed = False
    else:
        verification["plan_received"] = True
        plan_steps = result.get("plan_steps", [])
        
        # Check plan structure - should only contain play_song
        plan_actions = [step.get("action", "") for step in plan_steps if isinstance(step, dict)]
        
        # Verify play_song is in plan
        has_play_song = "play_song" in plan_actions
        verification["plan_contains_play_song"] = has_play_song
        if not has_play_song:
            passed = False
        
        # Verify forbidden actions are NOT in plan
        has_forbidden = any(action in plan_actions for action in forbidden_actions)
        verification["plan_does_not_contain_forbidden"] = not has_forbidden
        if has_forbidden:
            verification["forbidden_actions_found"] = [a for a in plan_actions if a in forbidden_actions]
            passed = False
        
        # Verify plan is simple (only play_song + reply_to_user)
        if len(plan_actions) > 2:
            verification["plan_too_complex"] = True
            verification["plan_action_count"] = len(plan_actions)
            passed = False
    
    # Check if response was received
    if not result.get("response_received"):
        verification["response_received"] = False
        passed = False
    else:
        verification["response_received"] = True
        response_text = result.get("response_text", "").lower()
        
        # Check if correct song is mentioned
        if expected_song:
            song_found = expected_song in response_text
            verification["correct_song_mentioned"] = song_found
            if not song_found:
                passed = False
        
        # Check if correct artist is mentioned
        if expected_artist:
            artist_found = expected_artist in response_text
            verification["correct_artist_mentioned"] = artist_found
            if not artist_found:
                passed = False
        
        # Check for errors
        console_errors = result.get("console_errors", [])
        verification["no_console_errors"] = len(console_errors) == 0
        if console_errors:
            passed = False
        
        # Check Spotify status
        spotify_status = result.get("spotify_status", {})
        if spotify_status:
            current_track = spotify_status.get("track", "").lower()
            current_artist = spotify_status.get("artist", "").lower()
            
            if expected_song and current_track:
                track_match = expected_song in current_track or current_track in expected_song
                verification["spotify_track_matches"] = track_match
                if not track_match:
                    passed = False
            
            if expected_artist and current_artist:
                artist_match = expected_artist in current_artist or current_artist in expected_artist
                verification["spotify_artist_matches"] = artist_match
                if not artist_match:
                    passed = False
    
    details["verification"] = verification
    
    return passed, details


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("SPOTIFY MOONWALK QUERY BROWSER TEST")
    print("=" * 80)
    
    print("\nNOTE: This test suite requires browser automation via MCP tools.")
    print("The AI assistant will execute this test using browser automation.")
    print("\nTest case:")
    print(f"  - {TEST_CASE['test_id']}: {TEST_CASE['name']}")
    print(f"    Query: {TEST_CASE['query']}")
    print(f"    Expected: {TEST_CASE.get('expected_song')} by {TEST_CASE.get('expected_artist')}")
    print(f"\nSuccess Criteria:")
    for criterion, value in TEST_CASE.get("success_criteria", {}).items():
        print(f"  - {criterion}: {value}")
    
    print("\n" + "=" * 80)
    print("BROWSER AUTOMATION WORKFLOW")
    print("=" * 80)
    print("""
For this test case, follow this workflow:

1. Navigate to http://localhost:3000
2. Wait 3 seconds for page load
3. Take snapshot (before)
4. Click message input field
5. Type the query: "play that Michael Jackson song where he does the moonwalk"
6. Wait 1 second
7. Click Send or press Enter
8. Wait 5-10 seconds for plan to appear
9. Take snapshot (plan) - CRITICAL: Verify plan structure
10. Verify plan contains ONLY play_song (no google_search, no extract_page_content)
11. Wait 10-20 seconds for processing
12. Take snapshot (after)
13. Check console messages
14. Verify response shows "Smooth Criminal" by "Michael Jackson"
15. Check Spotify status to verify song is playing
16. Verify all success criteria

CRITICAL VERIFICATION:
- ✅ Plan must contain ONLY play_song (no google_search)
- ✅ Response must show "Smooth Criminal" by "Michael Jackson"
- ✅ Spotify must be playing the correct song
- ✅ No error messages
- ✅ Status transitions: processing → idle
    """)
    
    print("\nTest structure ready for browser automation execution.")

