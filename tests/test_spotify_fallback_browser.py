#!/usr/bin/env python3
"""
Browser-based test for Spotify song query fallback scenario.

Tests that when the LLM cannot identify a song from the query, it uses
google_search (DuckDuckGo) as a fallback to find the song name, then
plays it using play_song.

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


# Test case for fallback scenario
TEST_CASE = {
    "test_id": "FALLBACK-SEARCH",
    "name": "Obscure Song Query - DuckDuckGo Fallback",
    "category": "Fallback Song Query",
    "query": "play that song from the new Taylor Swift album",
    "setup_notes": "Ensure Spotify is running",
    "expected_plan_steps": [
        {
            "action": "google_search",
            "parameters": {
                "query": "new Taylor Swift album songs 2024"
            }
        },
        {
            "action": "play_song",
            "parameters": {
                "song_name": "$step1.summary"
            },
            "dependencies": [1]
        },
        {
            "action": "reply_to_user",
            "dependencies": [2]
        }
    ],
    "required_actions": ["google_search", "play_song"],
    "expected_flow": [
        "User types query in input field",
        "Query sent via WebSocket",
        "System creates plan with google_search FIRST (fallback scenario)",
        "google_search finds song information",
        "play_song uses search results to identify and play song",
        "Response confirms successful playback"
    ],
    "success_criteria": {
        "command_appears_in_chat": True,
        "plan_contains_google_search": True,
        "plan_contains_play_song": True,
        "google_search_before_play_song": True,
        "response_shows_song_playing": True,
        "no_error_messages": True,
        "spotify_actually_playing": True,
        "status_transitions": "processing → idle"
    },
    "screenshot_points": ["before", "plan", "after"]
}


def execute_test_prompt(test_case: Dict[str, Any], timeout: int = 90) -> Dict[str, Any]:
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
    9. Take snapshot (plan) - verify plan structure (MUST have google_search)
    10. Wait for google_search to complete (5-10 seconds)
    11. Wait for play_song to complete (10-20 seconds)
    12. Take snapshot (after)
    13. Check console messages
    14. Verify success criteria
    15. Check Spotify status to verify song is playing
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
        "expected_plan_steps": test_case.get("expected_plan_steps", []),
        "required_actions": test_case.get("required_actions", []),
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
            "Verify plan contains google_search FIRST (fallback scenario)",
            "Verify plan contains play_song AFTER google_search",
            "Wait 5-10 seconds for google_search to complete",
            "Wait 10-20 seconds for play_song to complete",
            f"Take snapshot: {screenshot_points[-1] if screenshot_points else 'after'}",
            "Check console messages for errors",
            "Verify response shows song is playing",
            "Check Spotify status to verify song is playing",
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
    required_actions = test_case.get("required_actions", [])
    
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
        
        # Check plan structure - should contain google_search and play_song
        plan_actions = [step.get("action", "") for step in plan_steps if isinstance(step, dict)]
        
        # Verify required actions are in plan
        for action in required_actions:
            has_action = action in plan_actions
            verification[f"plan_contains_{action}"] = has_action
            if not has_action:
                passed = False
        
        # Verify google_search comes BEFORE play_song
        if "google_search" in plan_actions and "play_song" in plan_actions:
            google_search_idx = plan_actions.index("google_search")
            play_song_idx = plan_actions.index("play_song")
            search_before_play = google_search_idx < play_song_idx
            verification["google_search_before_play_song"] = search_before_play
            if not search_before_play:
                passed = False
        else:
            verification["google_search_before_play_song"] = False
            passed = False
        
        # Verify plan has dependencies (play_song depends on google_search)
        if len(plan_steps) > 1:
            play_song_step = next((s for s in plan_steps if s.get("action") == "play_song"), None)
            if play_song_step:
                dependencies = play_song_step.get("dependencies", [])
                has_dependency = len(dependencies) > 0
                verification["play_song_has_dependencies"] = has_dependency
                if not has_dependency:
                    passed = False
    
    # Check if response was received
    if not result.get("response_received"):
        verification["response_received"] = False
        passed = False
    else:
        verification["response_received"] = True
        response_text = result.get("response_text", "").lower()
        
        # Check if song is mentioned (should be playing)
        song_playing_indicators = ["playing", "now playing", "playing:", "song"]
        has_playing_indicator = any(indicator in response_text for indicator in song_playing_indicators)
        verification["response_shows_song_playing"] = has_playing_indicator
        if not has_playing_indicator:
            passed = False
        
        # Check for errors
        console_errors = result.get("console_errors", [])
        verification["no_console_errors"] = len(console_errors) == 0
        if console_errors:
            passed = False
        
        # Check Spotify status
        spotify_status = result.get("spotify_status", {})
        if spotify_status:
            is_playing = spotify_status.get("is_playing", False)
            verification["spotify_actually_playing"] = is_playing
            if not is_playing:
                passed = False
    
    details["verification"] = verification
    
    return passed, details


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("SPOTIFY FALLBACK QUERY BROWSER TEST")
    print("=" * 80)
    
    print("\nNOTE: This test suite requires browser automation via MCP tools.")
    print("The AI assistant will execute this test using browser automation.")
    print("\nTest case:")
    print(f"  - {TEST_CASE['test_id']}: {TEST_CASE['name']}")
    print(f"    Query: {TEST_CASE['query']}")
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
5. Type the query: "play that song from the new Taylor Swift album"
6. Wait 1 second
7. Click Send or press Enter
8. Wait 5-10 seconds for plan to appear
9. Take snapshot (plan) - CRITICAL: Verify plan structure
10. Verify plan contains google_search FIRST (fallback scenario)
11. Verify plan contains play_song AFTER google_search
12. Wait 5-10 seconds for google_search to complete
13. Wait 10-20 seconds for play_song to complete
14. Take snapshot (after)
15. Check console messages
16. Verify response shows song is playing
17. Check Spotify status to verify song is playing
18. Verify all success criteria

CRITICAL VERIFICATION:
- ✅ Plan must contain google_search FIRST (fallback scenario)
- ✅ Plan must contain play_song AFTER google_search
- ✅ play_song must depend on google_search (dependencies: [1])
- ✅ Response must show song is playing
- ✅ Spotify must be playing a song
- ✅ No error messages
- ✅ Status transitions: processing → idle
    """)
    
    print("\nTest structure ready for browser automation execution.")

