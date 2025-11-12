#!/usr/bin/env python3
"""
Browser-based comprehensive tests for summarize command features.

Tests all summarize scenarios via browser UI following TESTING_METHODOLOGY.md:
- Email summarization
- Bluesky/tweets summarization  
- Reminders summarization
- Calendar summarization
- News summarization

Uses browser automation tools and API endpoints.
"""

import sys
import os
import json
import time
import requests
from typing import Dict, Any, List, Tuple
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Test configuration
API_BASE_URL = "http://localhost:8000"
TEST_SESSION_ID = f"test-summarize-{int(time.time())}"

# Test results
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


def send_chat_message(message: str, session_id: str = None) -> Dict[str, Any]:
    """Send a chat message via API."""
    url = f"{API_BASE_URL}/api/chat"
    payload = {
        "message": message,
        "session_id": session_id or TEST_SESSION_ID
    }
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e), "response": None}


def verify_summary_quality(response: Dict[str, Any], expected_keywords: List[str] = None) -> Tuple[bool, Dict[str, Any]]:
    """Verify summary quality from response."""
    details = {}
    
    if "error" in response:
        return False, {"error": response["error"]}
    
    response_text = response.get("response", "")
    if not response_text:
        return False, {"error": "No response text"}
    
    # Check for summary indicators
    has_summary = any(keyword in response_text.lower() for keyword in ["summary", "summarize", "summarized"])
    details["has_summary_keyword"] = has_summary
    
    # Check for expected keywords
    if expected_keywords:
        found_keywords = [kw for kw in expected_keywords if kw.lower() in response_text.lower()]
        details["found_keywords"] = found_keywords
        details["keyword_coverage"] = len(found_keywords) / len(expected_keywords) if expected_keywords else 0
    
    # Check for error messages (but not false positives from response structure)
    # Look for actual error patterns, not just the word "error" in JSON structure
    error_patterns = [
        "unknown error",
        "error occurred",
        "failed to",
        "unable to",
        "exception",
        '"error": true',
        '"error": True',
        "status.*error"
    ]
    has_error = any(pattern in response_text.lower() for pattern in error_patterns)
    # Also check if response is a retry_with_orchestrator (which means it didn't complete)
    has_retry = "retry_with_orchestrator" in response_text.lower()
    details["has_error"] = has_error or has_retry
    details["has_retry"] = has_retry
    
    # Check response length (should be substantial for a summary)
    details["response_length"] = len(response_text)
    has_substance = len(response_text) > 100
    details["has_substance"] = has_substance
    
    # Overall quality check
    # A valid summary doesn't need to contain the word "summary" - it just needs:
    # 1. No errors or retries (means it completed)
    # 2. Substantial content (actual summary data)
    # 3. For some cases, expected keywords (if provided)
    # The "has_summary" keyword check is informational, not required for passing
    passed = has_substance and not has_error and not has_retry
    # If expected keywords provided, require at least 50% coverage
    if expected_keywords and len(expected_keywords) > 0:
        passed = passed and (details.get("keyword_coverage", 0) >= 0.5)
    
    return passed, details


def test_email_summarize_last_n():
    """TEST E1: Summarize last N emails"""
    test_id = "E1"
    test_name = "Summarize Last N Emails"
    
    print(f"\n{'='*80}")
    print(f"Testing: {test_name}")
    print(f"{'='*80}")
    
    queries = [
        "/email summarize my last 3 emails",
        "/email summarize the last 5 emails"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        response = send_chat_message(query)
        
        passed, details = verify_summary_quality(response, ["email", "summary"])
        details["query"] = query
        details["response_preview"] = response.get("response", "")[:200] if response.get("response") else None
        
        log_test_result(f"{test_id}-{queries.index(query)+1}", f"{test_name} - {query}", passed, details)


def test_email_summarize_by_time():
    """TEST E2: Summarize emails by time window"""
    test_id = "E2"
    test_name = "Summarize Emails by Time Window"
    
    print(f"\n{'='*80}")
    print(f"Testing: {test_name}")
    print(f"{'='*80}")
    
    queries = [
        "/email summarize emails from the past 2 hours",
        "/email summarize emails from the last hour"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        response = send_chat_message(query)
        
        passed, details = verify_summary_quality(response, ["email", "hour"])
        details["query"] = query
        details["response_preview"] = response.get("response", "")[:200] if response.get("response") else None
        
        log_test_result(f"{test_id}-{queries.index(query)+1}", f"{test_name} - {query}", passed, details)


def test_bluesky_summarize():
    """TEST B1: Summarize Bluesky posts"""
    test_id = "B1"
    test_name = "Summarize Bluesky Posts"
    
    print(f"\n{'='*80}")
    print(f"Testing: {test_name}")
    print(f"{'='*80}")
    
    queries = [
        "/bluesky summarize \"AI agents\" 12h",
        "/bluesky summarize what happened in the past hour"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        response = send_chat_message(query)
        
        passed, details = verify_summary_quality(response, ["bluesky", "summary"])
        details["query"] = query
        details["response_preview"] = response.get("response", "")[:200] if response.get("response") else None
        
        log_test_result(f"{test_id}-{queries.index(query)+1}", f"{test_name} - {query}", passed, details)


def test_reminders_summarize():
    """TEST R1: Summarize reminders"""
    test_id = "R1"
    test_name = "Summarize Reminders"
    
    print(f"\n{'='*80}")
    print(f"Testing: {test_name}")
    print(f"{'='*80}")
    
    queries = [
        "summarize my reminders",
        "summarize my todos"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        response = send_chat_message(query)
        
        passed, details = verify_summary_quality(response, ["reminder", "todo"])
        details["query"] = query
        details["response_preview"] = response.get("response", "")[:200] if response.get("response") else None
        
        log_test_result(f"{test_id}-{queries.index(query)+1}", f"{test_name} - {query}", passed, details)


def test_calendar_summarize():
    """TEST C1: Summarize calendar events with mock data"""
    test_id = "C1"
    test_name = "Summarize Calendar Events"
    
    print(f"\n{'='*80}")
    print(f"Testing: {test_name}")
    print(f"{'='*80}")
    
    # Setup mock calendar data
    import os
    from fixtures.calendar_fixtures import get_mock_calendar_fixture_path
    mock_data_path = get_mock_calendar_fixture_path()
    os.environ['CALENDAR_FAKE_DATA_PATH'] = mock_data_path
    print(f"Using mock calendar data from: {mock_data_path}")
    
    queries = [
        "summarize my calendar for the next week",
        "summarize my calendar events"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        response = send_chat_message(query)
        
        # Verify summary includes actual event content from mock data
        response_text = response.get("response", "")
        
        # Check for mock event titles in response
        from fixtures.calendar_fixtures import get_mock_calendar_events
        mock_events = get_mock_calendar_events()
        event_titles = [e.get('title', '').lower() for e in mock_events[:5]]
        response_lower = response_text.lower()
        mentioned_titles = [title for title in event_titles if title and title in response_lower]
        
        passed, details = verify_summary_quality(response, ["calendar", "event"])
        
        # Additional checks for calendar summaries
        details["query"] = query
        details["response_preview"] = response_text[:200] if response_text else None
        details["has_mock_event_titles"] = len(mentioned_titles) > 0
        details["mock_title_coverage"] = len(mentioned_titles) / len([t for t in event_titles if t]) if event_titles else 0.0
        
        # Require substantial content and event details
        if details.get("has_substance") and details.get("has_mock_event_titles"):
            passed = True
        elif not details.get("has_substance"):
            passed = False
        
        log_test_result(f"{test_id}-{queries.index(query)+1}", f"{test_name} - {query}", passed, details)


def test_news_summarize():
    """TEST N1: Summarize news"""
    test_id = "N1"
    test_name = "Summarize News"
    
    print(f"\n{'='*80}")
    print(f"Testing: {test_name}")
    print(f"{'='*80}")
    
    queries = [
        "summarize news about AI",
        "summarize recent tech news"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        response = send_chat_message(query)
        
        passed, details = verify_summary_quality(response, ["news", "summary"])
        details["query"] = query
        details["response_preview"] = response.get("response", "")[:200] if response.get("response") else None
        
        log_test_result(f"{test_id}-{queries.index(query)+1}", f"{test_name} - {query}", passed, details)


def main():
    """Run all summarize tests."""
    print("="*80)
    print("COMPREHENSIVE SUMMARIZE COMMAND TESTING")
    print("="*80)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Test Session ID: {TEST_SESSION_ID}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*80)
    
    # Check API connectivity
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        print(f"✅ API server is reachable")
    except Exception as e:
        print(f"❌ API server is not reachable: {e}")
        print("Please ensure API server is running on port 8000")
        return
    
    # Run all tests
    test_email_summarize_last_n()
    test_email_summarize_by_time()
    test_bluesky_summarize()
    test_reminders_summarize()
    test_calendar_summarize()
    test_news_summarize()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total_tests = len(TEST_RESULTS)
    passed_tests = sum(1 for r in TEST_RESULTS if r["passed"])
    failed_tests = total_tests - passed_tests
    
    print(f"Total Tests: {total_tests}")
    print(f"✅ Passed: {passed_tests}")
    print(f"❌ Failed: {failed_tests}")
    print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
    
    # Save results
    results_file = f"tests/summarize_test_results_{int(time.time())}.json"
    with open(results_file, "w") as f:
        json.dump(TEST_RESULTS, f, indent=2)
    print(f"\nResults saved to: {results_file}")
    
    # Print failed tests
    if failed_tests > 0:
        print("\n" + "="*80)
        print("FAILED TESTS:")
        print("="*80)
        for result in TEST_RESULTS:
            if not result["passed"]:
                print(f"❌ {result['test_id']}: {result['test_name']}")
                if "error" in result["details"]:
                    print(f"   Error: {result['details']['error']}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()

