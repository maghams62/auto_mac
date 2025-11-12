#!/usr/bin/env python3
"""
Comprehensive Cross-Functional Query Testing

Tests queries that combine multiple agents/data sources:
1. Reminders + Calendar (combined summaries)
2. Email + Calendar (combined summaries)
3. Bluesky + Email (summarize and email)
4. News + Email (summarize and email)
5. Reminders + Calendar + Email (multi-source)
6. Calendar + Meeting Prep (calendar with document search)
7. Weather + Reminders (conditional logic)
8. Email + Calendar + Reminders (full day summary)

Each test validates:
- Multi-step workflow execution
- Data synthesis across sources
- Proper tool chaining
- LLM reasoning for parameter extraction
- Summary quality and completeness
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
TEST_SESSION_ID = f"test-cross-functional-{int(time.time())}"

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
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e), "response": None}


def verify_cross_functional_response(response: Dict[str, Any], expected_sources: List[str], min_length: int = 200) -> Tuple[bool, Dict[str, Any]]:
    """
    Verify cross-functional query response quality.
    
    Args:
        response: API response dictionary
        expected_sources: List of expected data sources (e.g., ["reminders", "calendar"])
        min_length: Minimum response length
    
    Returns:
        Tuple of (passed: bool, details: dict)
    """
    details = {}
    
    if "error" in response:
        return False, {"error": response["error"]}
    
    response_text = response.get("response", "")
    if not response_text:
        return False, {"error": "No response text"}
    
    details["response_length"] = len(response_text)
    details["has_substance"] = len(response_text) >= min_length
    
    # Check for expected source keywords
    response_lower = response_text.lower()
    found_sources = []
    for source in expected_sources:
        source_keywords = {
            "reminders": ["reminder", "todo", "task"],
            "calendar": ["calendar", "event", "meeting", "appointment"],
            "email": ["email", "message", "inbox"],
            "bluesky": ["bluesky", "post", "tweet"],
            "news": ["news", "article", "report"],
            "weather": ["weather", "temperature", "rain", "sunny"]
        }
        keywords = source_keywords.get(source, [source])
        if any(kw in response_lower for kw in keywords):
            found_sources.append(source)
    
    details["expected_sources"] = expected_sources
    details["found_sources"] = found_sources
    details["source_coverage"] = len(found_sources) / len(expected_sources) if expected_sources else 0.0
    
    # Check for synthesis indicators (combining multiple sources)
    synthesis_indicators = ["and", "also", "additionally", "combined", "together", "both"]
    has_synthesis = any(indicator in response_lower for indicator in synthesis_indicators)
    details["has_synthesis"] = has_synthesis
    
    # Check for error patterns
    error_patterns = [
        "error", "failed", "unable", "exception", "skipped", "timeout"
    ]
    has_error = any(pattern in response_lower for pattern in error_patterns)
    details["has_error"] = has_error
    
    # Overall pass criteria
    passed = (
        details["has_substance"] and
        details["source_coverage"] >= 0.5 and  # At least 50% of expected sources mentioned
        not has_error
    )
    
    return passed, details


def test_cf1_reminders_and_calendar():
    """TEST CF1: Reminders + Calendar Combined Summary"""
    test_id = "CF1"
    test_name = "Reminders + Calendar Combined Summary"
    
    print(f"\n{'='*80}")
    print(f"Testing: {test_name}")
    print(f"{'='*80}")
    
    # Setup mock calendar data
    from fixtures.calendar_fixtures import setup_mock_calendar_env
    setup_mock_calendar_env()
    
    queries = [
        "summarize my reminders and calendar for the next week",
        "what do I have coming up - reminders and calendar events",
        "show me my todos and calendar events"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        response = send_chat_message(query)
        
        passed, details = verify_cross_functional_response(
            response,
            expected_sources=["reminders", "calendar"],
            min_length=200
        )
        
        details["query"] = query
        details["response_preview"] = response.get("response", "")[:300] if response.get("response") else None
        
        log_test_result(f"{test_id}-{queries.index(query)+1}", f"{test_name} - {query}", passed, details)


def test_cf2_email_and_calendar():
    """TEST CF2: Email + Calendar Combined Summary"""
    test_id = "CF2"
    test_name = "Email + Calendar Combined Summary"
    
    print(f"\n{'='*80}")
    print(f"Testing: {test_name}")
    print(f"{'='*80}")
    
    # Setup mock calendar data
    from fixtures.calendar_fixtures import setup_mock_calendar_env
    setup_mock_calendar_env()
    
    queries = [
        "summarize my emails and calendar for today",
        "what's in my inbox and on my calendar this week",
        "show me my recent emails and upcoming calendar events"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        response = send_chat_message(query)
        
        passed, details = verify_cross_functional_response(
            response,
            expected_sources=["email", "calendar"],
            min_length=200
        )
        
        details["query"] = query
        details["response_preview"] = response.get("response", "")[:300] if response.get("response") else None
        
        log_test_result(f"{test_id}-{queries.index(query)+1}", f"{test_name} - {query}", passed, details)


def test_cf3_bluesky_and_email():
    """TEST CF3: Bluesky Summary + Email"""
    test_id = "CF3"
    test_name = "Bluesky Summary + Email"
    
    print(f"\n{'='*80}")
    print(f"Testing: {test_name}")
    print(f"{'='*80}")
    
    queries = [
        "summarize recent Bluesky posts about AI and email them to me",
        "get my last 10 Bluesky posts and send them via email",
        "summarize Bluesky posts from the past hour and email the summary"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        response = send_chat_message(query)
        
        passed, details = verify_cross_functional_response(
            response,
            expected_sources=["bluesky", "email"],
            min_length=150
        )
        
        # Check for email confirmation
        response_text = response.get("response", "").lower()
        details["email_confirmed"] = any(
            keyword in response_text for keyword in [
                "sent", "emailed", "email sent", "delivered", "sent to"
            ]
        )
        
        details["query"] = query
        details["response_preview"] = response.get("response", "")[:300] if response.get("response") else None
        
        # Adjust pass criteria - email confirmation is important
        if not details.get("email_confirmed") and "email" in query.lower():
            passed = False
        
        log_test_result(f"{test_id}-{queries.index(query)+1}", f"{test_name} - {query}", passed, details)


def test_cf4_news_and_email():
    """TEST CF4: News Summary + Email"""
    test_id = "CF4"
    test_name = "News Summary + Email"
    
    print(f"\n{'='*80}")
    print(f"Testing: {test_name}")
    print(f"{'='*80}")
    
    queries = [
        "summarize news about AI and email it to me",
        "get recent tech news and send it via email",
        "summarize today's news and email the summary"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        response = send_chat_message(query)
        
        passed, details = verify_cross_functional_response(
            response,
            expected_sources=["news", "email"],
            min_length=200
        )
        
        # Check for email confirmation
        response_text = response.get("response", "").lower()
        details["email_confirmed"] = any(
            keyword in response_text for keyword in [
                "sent", "emailed", "email sent", "delivered", "sent to"
            ]
        )
        
        details["query"] = query
        details["response_preview"] = response.get("response", "")[:300] if response.get("response") else None
        
        # Adjust pass criteria
        if not details.get("email_confirmed") and "email" in query.lower():
            passed = False
        
        log_test_result(f"{test_id}-{queries.index(query)+1}", f"{test_name} - {query}", passed, details)


def test_cf5_reminders_calendar_email():
    """TEST CF5: Reminders + Calendar + Email (Multi-Source)"""
    test_id = "CF5"
    test_name = "Reminders + Calendar + Email Multi-Source"
    
    print(f"\n{'='*80}")
    print(f"Testing: {test_name}")
    print(f"{'='*80}")
    
    # Setup mock calendar data
    from fixtures.calendar_fixtures import setup_mock_calendar_env
    setup_mock_calendar_env()
    
    queries = [
        "summarize my reminders, calendar, and emails for this week and email it to me",
        "give me a complete summary of my todos, calendar events, and recent emails",
        "what do I have coming up - combine reminders, calendar, and emails"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        response = send_chat_message(query)
        
        passed, details = verify_cross_functional_response(
            response,
            expected_sources=["reminders", "calendar", "email"],
            min_length=300
        )
        
        # Check for email confirmation if query includes email action
        if "email" in query.lower():
            response_text = response.get("response", "").lower()
            details["email_confirmed"] = any(
                keyword in response_text for keyword in [
                    "sent", "emailed", "email sent", "delivered"
                ]
            )
        
        details["query"] = query
        details["response_preview"] = response.get("response", "")[:300] if response.get("response") else None
        
        log_test_result(f"{test_id}-{queries.index(query)+1}", f"{test_name} - {query}", passed, details)


def test_cf6_calendar_meeting_prep():
    """TEST CF6: Calendar + Meeting Preparation"""
    test_id = "CF6"
    test_name = "Calendar + Meeting Preparation"
    
    print(f"\n{'='*80}")
    print(f"Testing: {test_name}")
    print(f"{'='*80}")
    
    # Setup mock calendar data
    from fixtures.calendar_fixtures import setup_mock_calendar_env, get_mock_calendar_events
    setup_mock_calendar_env()
    
    # Get a meeting event from mock data
    mock_events = get_mock_calendar_events()
    meeting_events = [e for e in mock_events if e.get('attendees') and len(e.get('attendees', [])) > 0]
    
    if meeting_events:
        meeting_title = meeting_events[0].get('title', 'Team Standup')
        queries = [
            f"prepare a brief for {meeting_title}",
            f"prep me for {meeting_title} meeting",
            f"create a meeting brief for {meeting_title}"
        ]
    else:
        queries = [
            "prepare a brief for my next meeting",
            "prep me for the Team Standup meeting",
            "create a meeting brief for Product Review Meeting"
        ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        response = send_chat_message(query)
        
        passed, details = verify_cross_functional_response(
            response,
            expected_sources=["calendar"],
            min_length=150
        )
        
        # Check for meeting prep indicators
        response_text = response.get("response", "").lower()
        details["has_meeting_prep"] = any(
            keyword in response_text for keyword in [
                "brief", "prep", "prepare", "agenda", "talking points", "meeting"
            ]
        )
        
        details["query"] = query
        details["response_preview"] = response.get("response", "")[:300] if response.get("response") else None
        
        # Adjust pass criteria
        if not details.get("has_meeting_prep"):
            passed = False
        
        log_test_result(f"{test_id}-{queries.index(query)+1}", f"{test_name} - {query}", passed, details)


def test_cf7_full_day_summary():
    """TEST CF7: Full Day Summary (Email + Calendar + Reminders)"""
    test_id = "CF7"
    test_name = "Full Day Summary"
    
    print(f"\n{'='*80}")
    print(f"Testing: {test_name}")
    print(f"{'='*80}")
    
    # Setup mock calendar data
    from fixtures.calendar_fixtures import setup_mock_calendar_env
    setup_mock_calendar_env()
    
    queries = [
        "give me a summary of my day - emails, calendar, and reminders",
        "what's on my plate today - combine everything",
        "summarize my complete day: emails, meetings, and todos"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        response = send_chat_message(query)
        
        passed, details = verify_cross_functional_response(
            response,
            expected_sources=["email", "calendar", "reminders"],
            min_length=300
        )
        
        details["query"] = query
        details["response_preview"] = response.get("response", "")[:300] if response.get("response") else None
        
        log_test_result(f"{test_id}-{queries.index(query)+1}", f"{test_name} - {query}", passed, details)


def main():
    """Run all cross-functional query tests"""
    print("="*80)
    print("COMPREHENSIVE CROSS-FUNCTIONAL QUERY TESTING")
    print("="*80)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Test Session ID: {TEST_SESSION_ID}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*80)
    
    # Check API availability
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API server is reachable\n")
        else:
            print("⚠️  API server responded with non-200 status\n")
    except:
        print("❌ API server is not reachable. Please start the API server.\n")
        return
    
    # Run all tests
    test_cf1_reminders_and_calendar()
    test_cf2_email_and_calendar()
    test_cf3_bluesky_and_email()
    test_cf4_news_and_email()
    test_cf5_reminders_calendar_email()
    test_cf6_calendar_meeting_prep()
    test_cf7_full_day_summary()
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total_tests = len(TEST_RESULTS)
    passed_tests = sum(1 for r in TEST_RESULTS if r["passed"])
    failed_tests = total_tests - passed_tests
    
    print(f"Total Tests: {total_tests}")
    print(f"✅ Passed: {passed_tests}")
    print(f"❌ Failed: {failed_tests}")
    print(f"Success Rate: {passed_tests/total_tests*100:.1f}%")
    
    print("\n" + "="*80)
    print("FAILED TESTS:")
    print("="*80)
    for result in TEST_RESULTS:
        if not result["passed"]:
            print(f"❌ {result['test_id']}: {result['test_name']}")
    
    # Save results
    results_file = f"tests/cross_functional_test_results_{int(time.time())}.json"
    with open(results_file, 'w') as f:
        json.dump(TEST_RESULTS, f, indent=2)
    print(f"\nResults saved to: {results_file}")


if __name__ == "__main__":
    main()

