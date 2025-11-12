#!/usr/bin/env python3
"""
Browser-based tests for complex song disambiguation scenarios.

Tests Spotify song disambiguation with browser automation following TESTING_METHODOLOGY.md.
Verifies that complex queries correctly identify and play songs in Spotify.

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
    print("Starting services for browser testing...")
    print("="*80)
    
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
    else:
        print("⚠️  API server file not found")
    
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


# Test cases for complex disambiguation
TEST_CASES = [
    {
        "test_id": "D1-FULL-NAME",
        "name": "Full Song Name - Breaking the Habit",
        "category": "Complex Disambiguation",
        "query": "Play a song called breaking the habit on Spotify",
        "setup_notes": "Ensure Spotify is running",
        "expected_song": "Breaking the Habit",
        "expected_artist": "Linkin Park",
        "expected_flow": [
            "User types query in input field",
            "Query sent via WebSocket",
            "System routes to play_song tool",
            "SongDisambiguator extracts 'Breaking the Habit' by Linkin Park",
            "Spotify searches and plays the song",
            "Response confirms correct song identification"
        ],
        "success_criteria": {
            "command_appears_in_chat": True,
            "status_transitions": "processing → idle",
            "response_shows_correct_song": True,
            "response_shows_correct_artist": True,
            "no_error_messages": True,
            "spotify_actually_playing": True,
            "spotify_plays_correct_song": True
        },
        "screenshot_points": ["before", "processing", "after"]
    },
    {
        "test_id": "D2-VAGUE",
        "name": "Vague Reference - The Space Song",
        "category": "Complex Disambiguation",
        "query": "Play the space song",
        "setup_notes": "Ensure Spotify is running",
        "expected_song": "Space Song",
        "expected_artist": "Beach House",
        "expected_flow": [
            "User types vague query 'the space song'",
            "SongDisambiguator identifies as 'Space Song' by Beach House",
            "Spotify plays the correct song",
            "Response shows correct identification"
        ],
        "success_criteria": {
            "command_appears_in_chat": True,
            "response_shows_correct_song": True,
            "response_shows_correct_artist": True,
            "spotify_plays_correct_song": True,
            "no_error_messages": True
        },
        "screenshot_points": ["before", "after"]
    },
    {
        "test_id": "D3-DESCRIPTIVE",
        "name": "Descriptive Query - Michael Jackson Moonwalk",
        "category": "Complex Disambiguation",
        "query": "Play that song by Michael Jackson where he move like he moonwalks",
        "setup_notes": "Ensure Spotify is running",
        "expected_song": "Smooth Criminal",
        "expected_artist": "Michael Jackson",
        "expected_flow": [
            "User provides descriptive query about moonwalking",
            "SongDisambiguator identifies as 'Smooth Criminal' by Michael Jackson",
            "Spotify plays the correct song",
            "Response shows correct identification with reasoning"
        ],
        "success_criteria": {
            "command_appears_in_chat": True,
            "response_shows_correct_song": True,
            "response_shows_correct_artist": True,
            "spotify_plays_correct_song": True,
            "reasoning_visible_in_response": True,
            "no_error_messages": True
        },
        "screenshot_points": ["before", "after"]
    },
    {
        "test_id": "D4-PARTIAL",
        "name": "Partial Description - Space by Eminem",
        "category": "Complex Disambiguation",
        "query": "Play that song that starts with space by Eminem",
        "setup_notes": "Ensure Spotify is running",
        "expected_song": "Space Bound",
        "expected_artist": "Eminem",
        "expected_flow": [
            "User provides partial description with artist hint",
            "SongDisambiguator identifies as 'Space Bound' by Eminem",
            "Spotify plays the correct song",
            "Response shows correct identification"
        ],
        "success_criteria": {
            "command_appears_in_chat": True,
            "response_shows_correct_song": True,
            "response_shows_correct_artist": True,
            "spotify_plays_correct_song": True,
            "no_error_messages": True
        },
        "screenshot_points": ["before", "after"]
    }
]


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
    8. Wait for processing (5-15 seconds for LLM disambiguation)
    9. Take snapshot (after)
    10. Check console messages
    11. Verify success criteria
    12. Check Spotify status to verify correct song is playing
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
        "note": "Execution performed via browser MCP tools",
        "workflow": [
            "Navigate to http://localhost:3000",
            "Wait 3 seconds for page load",
            f"Take snapshot: {screenshot_points[0] if screenshot_points else 'before'}",
            "Click message input field",
            f"Type query: {query}",
            "Wait 1 second for UI updates",
            "Click Send button or press Enter",
            "Wait 10-15 seconds for processing (LLM disambiguation may take time)",
            f"Take snapshot: {screenshot_points[-1] if screenshot_points else 'after'}",
            "Check console messages for errors",
            "Verify response shows correct song and artist",
            "Check Spotify status to verify correct song is playing",
            "Verify success criteria"
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
    
    details = {
        "response_received": result.get("response_received", False),
        "response_text": result.get("response_text", ""),
        "console_errors": result.get("console_errors", []),
        "spotify_status": result.get("spotify_status", {}),
        "verification": {}
    }
    
    passed = True
    verification = {}
    
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


def run_browser_test_suite():
    """Run all browser automation tests."""
    print("\n" + "=" * 80)
    print("SPOTIFY DISAMBIGUATION BROWSER TEST SUITE")
    print("=" * 80)
    
    print("\nNOTE: This test suite requires browser automation via MCP tools.")
    print("The AI assistant will execute these tests using browser automation.")
    print("\nTest cases:")
    for test_case in TEST_CASES:
        print(f"  - {test_case['test_id']}: {test_case['name']}")
        print(f"    Query: {test_case['query']}")
        print(f"    Expected: {test_case.get('expected_song')} by {test_case.get('expected_artist')}")
    
    print("\n" + "=" * 80)
    print("BROWSER AUTOMATION WORKFLOW")
    print("=" * 80)
    print("""
For each test case, follow this workflow:

1. Navigate to http://localhost:3000
2. Wait 3 seconds for page load
3. Take snapshot (before)
4. Click message input field
5. Type the query
6. Wait 1 second
7. Click Send or press Enter
8. Wait 10-15 seconds for processing
9. Take snapshot (after)
10. Check console messages
11. Verify response shows correct song/artist
12. Check Spotify status to verify song is playing
13. Verify all success criteria

Success Criteria for Each Test:
- ✅ Query appears in chat
- ✅ Response received
- ✅ Response shows correct song name
- ✅ Response shows correct artist
- ✅ No console errors
- ✅ Spotify is playing
- ✅ Spotify is playing the correct song
- ✅ Status transitions: processing → idle
    """)
    
    return TEST_CASES


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Browser tests for song disambiguation")
    parser.add_argument("--start-services", action="store_true", help="Start API server and frontend")
    parser.add_argument("--stop-services", action="store_true", help="Stop API server and frontend")
    parser.add_argument("--list-tests", action="store_true", help="List all test cases")
    
    args = parser.parse_args()
    
    if args.start_services:
        start_services()
    elif args.stop_services:
        stop_services()
    elif args.list_tests:
        run_browser_test_suite()
    else:
        print("Use --list-tests to see test cases")
        print("Use --start-services to start required services")
        print("Use --stop-services to stop services")
        print("\nActual test execution is performed via browser MCP tools by the AI assistant.")

