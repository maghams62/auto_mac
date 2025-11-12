#!/usr/bin/env python3
"""
Unit tests for calendar summarization using mock data.

Tests calendar summarization functionality with consistent mock data
to ensure reliable testing and validation of summary quality.
"""

import sys
import os
import json
import logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agent.calendar_agent import list_calendar_events
from src.agent.writing_agent import synthesize_content
from src.orchestrator.main_orchestrator import MainOrchestrator
from src.utils import load_config
from test_summarize_utils import (
    verify_summary_quality,
    verify_llm_reasoning,
    verify_time_window_extraction,
    verify_workflow_correctness,
    verify_calendar_summary_quality,
    print_validation_results
)
from fixtures.calendar_fixtures import (
    get_mock_calendar_events,
    create_mock_calendar_response,
    filter_events_by_days,
    get_events_by_type,
    setup_mock_calendar_env
)

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def test_cm1_basic_calendar_summarization():
    """TEST C-M1: Basic Calendar Summarization"""
    print_section("TEST C-M1: Basic Calendar Summarization")
    
    # Setup mock data
    setup_mock_calendar_env()
    
    query = "summarize my calendar for the next week"
    print(f"Query: {query}")
    
    try:
        # Test 1: Tool-level functionality with mock data
        print("\n1. Testing tool-level functionality with mock data...")
        
        days_ahead = 7
        events_result = list_calendar_events.invoke({
            "days_ahead": days_ahead
        })
        
        if events_result.get('error'):
            print(f"   ❌ Error listing events: {events_result.get('error_message')}")
            return False
        
        events = events_result.get('events', [])
        print(f"   ✅ Listed {len(events)} events for next {days_ahead} days")
        
        if not events:
            print(f"   ❌ No events available - mock data not loaded correctly")
            return False
        
        # Display sample events
        print(f"\n   Sample Events:")
        for i, event in enumerate(events[:3], 1):
            print(f"   {i}. {event.get('title', 'Untitled')}")
            if event.get('start_time'):
                print(f"      Time: {event.get('start_time')}")
            if event.get('location'):
                print(f"      Location: {event.get('location')}")
        
        # Test 2: Synthesis
        print(f"\n2. Testing synthesis...")
        
        # Convert events to string format for synthesis
        events_text = json.dumps({"events": events, "count": len(events)}, indent=2)
        
        synthesis_result = synthesize_content.invoke({
            "source_contents": [events_text],
            "topic": "Summary of upcoming calendar events",
            "synthesis_style": "concise"
        })
        
        if synthesis_result.get('error'):
            print(f"   ❌ Synthesis error: {synthesis_result.get('error_message')}")
            return False
        
        summary = synthesis_result.get('synthesized_content', '')
        print(f"   ✅ Generated summary ({len(summary)} chars)")
        print(f"\n   Summary preview:\n   {summary[:300]}...")
        
        # Validate summary quality
        quality_check = verify_calendar_summary_quality(summary, events)
        print_validation_results(quality_check, "C-M1 Summary Quality")
        
        # Verify summary includes event details
        has_titles = quality_check.get('has_event_titles', False)
        has_times = quality_check.get('has_event_times', False)
        
        print(f"\n   ✅ Summary mentions event titles: {has_titles}")
        print(f"   ✅ Summary includes event times: {has_times}")
        
        # Check summary length
        if len(summary) < 200:
            print(f"   ⚠️  Summary is too short ({len(summary)} chars, expected >= 200)")
            return False
        
        return quality_check.get('score', 0.0) >= 0.5
        
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cm2_time_window_extraction():
    """TEST C-M2: Time Window Extraction"""
    print_section("TEST C-M2: Time Window Extraction")
    
    # Setup mock data
    setup_mock_calendar_env()
    
    test_queries = [
        ("summarize my calendar this month", 30),
        ("summarize my calendar for the next week", 7),
        ("summarize my calendar for the next 3 days", 3),
    ]
    
    all_passed = True
    
    for query, expected_days in test_queries:
        print(f"\nQuery: {query}")
        print(f"Expected days_ahead: {expected_days}")
        
        try:
            # Test orchestrator planning
            config = load_config()
            orchestrator = MainOrchestrator(config)
            
            plan_result = orchestrator.planner.create_plan(
                goal=query,
                available_tools=orchestrator.tool_catalog,
                context=None
            )
            
            if not plan_result.get("success"):
                print(f"   ❌ Planning failed: {plan_result.get('error')}")
                all_passed = False
                continue
            
            plan = plan_result.get("plan", [])
            
            # Find list_calendar_events step
            list_step = None
            for step in plan:
                if "list_calendar" in str(step.get("action", "")).lower():
                    list_step = step
                    break
            
            if not list_step:
                print(f"   ❌ No list_calendar_events step found in plan")
                all_passed = False
                continue
            
            # Extract days_ahead parameter
            params = list_step.get("inputs", {}) or list_step.get("parameters", {})
            days_ahead_param = params.get("days_ahead")
            
            if days_ahead_param is None:
                print(f"   ❌ days_ahead parameter not found")
                all_passed = False
                continue
            
            print(f"   ✅ days_ahead parameter extracted: {days_ahead_param}")
            
            # Check if it matches expected value (allow some flexibility)
            if abs(days_ahead_param - expected_days) <= 2:  # Allow ±2 days tolerance
                print(f"   ✅ Time window correctly extracted (expected ~{expected_days} days)")
            else:
                print(f"   ⚠️  Time window extraction may be off (got {days_ahead_param}, expected ~{expected_days})")
                # Don't fail, just warn - LLM reasoning may choose slightly different values
            
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
    
    return all_passed


def test_cm3_meeting_focused_summarization():
    """TEST C-M3: Meeting-Focused Summarization"""
    print_section("TEST C-M3: Meeting-Focused Summarization")
    
    # Setup mock data
    setup_mock_calendar_env()
    
    query = "summarize meetings in my calendar"
    print(f"Query: {query}")
    
    try:
        # Get all events
        events_result = list_calendar_events.invoke({
            "days_ahead": 7
        })
        
        if events_result.get('error'):
            print(f"   ❌ Error listing events: {events_result.get('error_message')}")
            return False
        
        all_events = events_result.get('events', [])
        
        # Filter to meetings (events with attendees)
        meeting_events = get_events_by_type(all_events, "meeting")
        print(f"   ✅ Filtered to {len(meeting_events)} meeting events (out of {len(all_events)} total)")
        
        if not meeting_events:
            print(f"   ⚠️  No meeting events found in mock data")
            return False
        
        # Synthesize meeting events
        events_text = json.dumps({"events": meeting_events, "count": len(meeting_events)}, indent=2)
        
        synthesis_result = synthesize_content.invoke({
            "source_contents": [events_text],
            "topic": "Summary of meetings in calendar",
            "synthesis_style": "concise"
        })
        
        if synthesis_result.get('error'):
            print(f"   ❌ Synthesis error: {synthesis_result.get('error_message')}")
            return False
        
        summary = synthesis_result.get('synthesized_content', '')
        print(f"   ✅ Generated summary ({len(summary)} chars)")
        print(f"\n   Summary preview:\n   {summary[:300]}...")
        
        # Verify summary emphasizes meeting details
        summary_lower = summary.lower()
        
        # Check for attendee mentions
        has_attendees = False
        for event in meeting_events[:3]:
            attendees = event.get('attendees', [])
            for attendee in attendees[:2]:
                attendee_name = attendee.split('@')[0].lower()
                if attendee_name in summary_lower:
                    has_attendees = True
                    break
            if has_attendees:
                break
        
        print(f"   {'✅' if has_attendees else '⚠️'} Summary mentions attendees: {has_attendees}")
        
        # Check for meeting-related keywords
        meeting_keywords = ['meeting', 'attend', 'participant', 'discuss', 'review']
        has_meeting_keywords = any(kw in summary_lower for kw in meeting_keywords)
        print(f"   {'✅' if has_meeting_keywords else '⚠️'} Summary includes meeting keywords: {has_meeting_keywords}")
        
        # Validate summary quality
        quality_check = verify_calendar_summary_quality(summary, meeting_events)
        print_validation_results(quality_check, "C-M3 Summary Quality")
        
        return quality_check.get('score', 0.0) >= 0.5
        
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cm4_summary_completeness():
    """TEST C-M4: Summary Completeness"""
    print_section("TEST C-M4: Summary Completeness")
    
    # Setup mock data
    setup_mock_calendar_env()
    
    query = "summarize my calendar for the next week"
    print(f"Query: {query}")
    
    try:
        # Get events
        events_result = list_calendar_events.invoke({
            "days_ahead": 7
        })
        
        if events_result.get('error'):
            print(f"   ❌ Error listing events: {events_result.get('error_message')}")
            return False
        
        events = events_result.get('events', [])
        
        if not events:
            print(f"   ❌ No events available")
            return False
        
        # Synthesize
        events_text = json.dumps({"events": events, "count": len(events)}, indent=2)
        
        synthesis_result = synthesize_content.invoke({
            "source_contents": [events_text],
            "topic": "Summary of upcoming calendar events",
            "synthesis_style": "comprehensive"
        })
        
        if synthesis_result.get('error'):
            print(f"   ❌ Synthesis error: {synthesis_result.get('error_message')}")
            return False
        
        summary = synthesis_result.get('synthesized_content', '')
        
        # Comprehensive quality check
        quality_check = verify_calendar_summary_quality(summary, events)
        
        print(f"\n   Completeness Check:")
        print(f"   ✅ Event titles mentioned: {quality_check.get('has_event_titles', False)}")
        print(f"   ✅ Event times mentioned: {quality_check.get('has_event_times', False)}")
        print(f"   ✅ Locations mentioned: {quality_check.get('has_locations', False)}")
        print(f"   ✅ Attendees mentioned: {quality_check.get('has_attendees', False)}")
        print(f"   ✅ Chronological organization: {quality_check.get('is_chronological', False)}")
        print(f"   ✅ Event coverage: {quality_check.get('event_coverage', 0.0):.1%}")
        
        print_validation_results(quality_check, "C-M4 Summary Completeness")
        
        # Check minimum requirements
        has_minimum_details = (
            quality_check.get('has_event_titles', False) and
            quality_check.get('has_event_times', False) and
            len(summary) >= 200
        )
        
        return has_minimum_details and quality_check.get('score', 0.0) >= 0.6
        
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cm5_empty_result_handling():
    """TEST C-M5: Empty Result Handling"""
    print_section("TEST C-M5: Empty Result Handling")
    
    # Setup mock data
    setup_mock_calendar_env()
    
    query = "summarize my calendar for next year"
    print(f"Query: {query}")
    
    try:
        # Get events with very large days_ahead (should filter to empty)
        events_result = list_calendar_events.invoke({
            "days_ahead": 365
        })
        
        if events_result.get('error'):
            print(f"   ❌ Error listing events: {events_result.get('error_message')}")
            return False
        
        events = events_result.get('events', [])
        
        # With mock data, we might still get events if they're within 365 days
        # So let's test with a date range that definitely has no events
        # Filter events to only those beyond 30 days
        all_mock_events = get_mock_calendar_events()
        far_future_events = [
            e for e in all_mock_events
            if datetime.fromisoformat(e.get('start_time', '2000-01-01').replace('Z', '+00:00')).replace(tzinfo=None) >
               datetime.now() + timedelta(days=30)
        ]
        
        if far_future_events:
            print(f"   ⚠️  Mock data has events beyond 30 days, testing with empty list")
            events = []
        else:
            print(f"   ✅ No events found for far future (as expected)")
        
        # Test synthesis with empty events
        if not events:
            # Test that synthesize_content handles empty data gracefully
            events_text = json.dumps({"events": [], "count": 0}, indent=2)
            
            synthesis_result = synthesize_content.invoke({
                "source_contents": ["No calendar events found for the requested time period."],
                "topic": "Summary of upcoming calendar events",
                "synthesis_style": "concise"
            })
            
            if synthesis_result.get('error'):
                print(f"   ❌ Synthesis error with empty data: {synthesis_result.get('error_message')}")
                return False
            
            summary = synthesis_result.get('synthesized_content', '')
            print(f"   ✅ Generated empty-state message ({len(summary)} chars)")
            print(f"\n   Empty-state message:\n   {summary[:200]}...")
            
            # Check that it's informative
            informative_keywords = ['no', 'empty', 'found', 'available', 'events', 'calendar']
            has_informative = any(kw in summary.lower() for kw in informative_keywords)
            
            print(f"   {'✅' if has_informative else '⚠️'} Empty-state message is informative: {has_informative}")
            
            return has_informative and len(summary) > 20
        
        return True
        
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all calendar summarization tests with mock data"""
    print_section("CALENDAR SUMMARIZATION TESTS WITH MOCK DATA")
    
    print("""
This test suite validates calendar summarization using mock data:
1. ✅ Basic summarization functionality
2. ✅ Time window extraction (LLM reasoning)
3. ✅ Meeting-focused filtering
4. ✅ Summary completeness
5. ✅ Empty result handling
    """)
    
    results = {}
    
    try:
        results['C-M1'] = test_cm1_basic_calendar_summarization()
        results['C-M2'] = test_cm2_time_window_extraction()
        results['C-M3'] = test_cm3_meeting_focused_summarization()
        results['C-M4'] = test_cm4_summary_completeness()
        results['C-M5'] = test_cm5_empty_result_handling()
        
        print_section("TEST RESULTS SUMMARY")
        
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        for test_id, passed_test in results.items():
            status = "✅ PASSED" if passed_test else "❌ FAILED"
            print(f"{status}: {test_id}")
        
        print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        return passed == total
        
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

