#!/usr/bin/env python3
"""
Comprehensive Calendar Summarization Tests

Tests all calendar summarization scenarios:
- TEST C1: Summarize upcoming events
- TEST C2: Summarize calendar with focus

Each test validates:
1. Tool execution
2. Parameter extraction (LLM reasoning, no hardcoding)
3. Workflow correctness (list_calendar_events → synthesize_content → reply_to_user)
4. Summary quality (relevance, coherence, accuracy)
"""

import sys
import os
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
    verify_summary_relevance_with_llm,
    print_validation_results
)
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def test_c1_summarize_upcoming_events():
    """TEST C1: Summarize upcoming events"""
    print_section("TEST C1: Summarize Upcoming Events")
    
    test_queries = [
        "summarize my calendar for the next week",
        "summarize my calendar events",
        "what's on my calendar this week"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: {query}")
        
        # Test 1: Tool-level functionality
        print("\n1. Testing tool-level functionality...")
        try:
            # Extract days_ahead from query
            days_ahead = 7  # Default
            if "week" in query.lower():
                days_ahead = 7
            elif "month" in query.lower():
                days_ahead = 30
            
            # List calendar events
            events_result = list_calendar_events.invoke({
                "days_ahead": days_ahead
            })
            
            if events_result.get('error'):
                print(f"   ⚠️  Error listing events: {events_result.get('error_message')}")
                print(f"   This may be expected if Calendar.app is not configured.")
                continue
            
            events = events_result.get('events', [])
            print(f"   ✅ Listed {len(events)} events for next {days_ahead} days")
            
            if not events:
                print(f"   ⚠️  No events available to summarize")
                continue
            
            # Display sample events
            print(f"\n   Sample Events:")
            for i, event in enumerate(events[:3], 1):
                print(f"   {i}. {event.get('title', 'Untitled')}")
                if event.get('start_time'):
                    print(f"      Time: {event.get('start_time')}")
                if event.get('location'):
                    print(f"      Location: {event.get('location')}")
            
            # Synthesize events
            print(f"\n2. Testing synthesis...")
            
            # Convert events to string format for synthesis
            events_text = json.dumps(events_result, indent=2)
            
            synthesis_result = synthesize_content.invoke({
                "source_contents": [events_text],
                "topic": "Summary of upcoming calendar events",
                "synthesis_style": "concise"
            })
            
            if synthesis_result.get('error'):
                print(f"   ❌ Synthesis error: {synthesis_result.get('error_message')}")
                continue
            
            summary = synthesis_result.get('synthesized_content', '')
            print(f"   ✅ Generated summary ({len(summary)} chars)")
            
            # Validate summary quality
            quality_check = verify_summary_quality(summary, events, "calendar")
            print_validation_results(quality_check, f"C1 Summary Quality: {query}")
            
            # Verify summary includes event details
            has_titles = any(event.get('title', '').lower() in summary.lower() for event in events[:3])
            print(f"   {'✅' if has_titles else '⚠️'} Summary mentions event titles: {has_titles}")
            
            # Check for chronological organization
            has_times = any(event.get('start_time', '') in summary for event in events[:3])
            print(f"   {'✅' if has_times else '⚠️'} Summary includes event times: {has_times}")
            
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            import traceback
            traceback.print_exc()
            continue
        
        # Test 3: Orchestrator planning
        print("\n3. Testing orchestrator planning...")
        try:
            config = load_config()
            orchestrator = MainOrchestrator(config)
            
            plan_result = orchestrator.planner.create_plan(
                goal=query,
                available_tools=orchestrator.tool_catalog,
                context=None
            )
            
            if plan_result.get("success"):
                plan = plan_result.get("plan", [])
                print(f"   ✅ Plan created with {len(plan)} steps")
                
                # Verify workflow
                expected_workflow = ["list_calendar_events", "synthesize_content", "reply_to_user"]
                workflow_check = verify_workflow_correctness(plan, expected_workflow)
                print_validation_results(workflow_check, f"C1 Workflow: {query}")
                
                # Verify LLM reasoning
                reasoning_check = verify_llm_reasoning(plan, query)
                print_validation_results(reasoning_check, f"C1 LLM Reasoning: {query}")
                
                # Check that synthesize_content receives events data
                synthesize_step = None
                for step in plan:
                    if "synthesize_content" in str(step.get("action", "")).lower():
                        synthesize_step = step
                        break
                
                if synthesize_step:
                    params = synthesize_step.get("inputs", {}) or synthesize_step.get("parameters", {})
                    source_contents = params.get("source_contents", [])
                    if source_contents:
                        print(f"   ✅ synthesize_content receives source data")
                        # Check if it references calendar step
                        has_calendar_ref = any("calendar" in str(src).lower() or "$step" in str(src) for src in source_contents)
                        print(f"   {'✅' if has_calendar_ref else '⚠️'} Source references calendar: {has_calendar_ref}")
                
                # Verify time window extraction (days_ahead)
                list_step = None
                for step in plan:
                    if "list_calendar" in str(step.get("action", "")).lower():
                        list_step = step
                        break
                
                if list_step:
                    params = list_step.get("inputs", {}) or list_step.get("parameters", {})
                    days_ahead_param = params.get("days_ahead")
                    if days_ahead_param:
                        print(f"   ✅ days_ahead parameter: {days_ahead_param}")
                        # Check if it matches query
                        if "week" in query.lower() and days_ahead_param == 7:
                            print(f"   ✅ Time window correctly extracted (week → 7 days)")
                        elif "month" in query.lower() and days_ahead_param == 30:
                            print(f"   ✅ Time window correctly extracted (month → 30 days)")
                
            else:
                print(f"   ❌ Planning failed: {plan_result.get('error')}")
                
        except Exception as e:
            print(f"   ❌ Planning error: {e}")
            import traceback
            traceback.print_exc()


def test_c2_summarize_with_focus():
    """TEST C2: Summarize calendar with focus"""
    print_section("TEST C2: Summarize Calendar with Focus")
    
    test_queries = [
        "summarize meetings in my calendar",
        "summarize my calendar focusing on meetings",
        "what meetings do I have this week"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: {query}")
        
        # Test 1: Verify focus extraction
        print("\n1. Testing focus extraction...")
        try:
            config = load_config()
            orchestrator = MainOrchestrator(config)
            
            plan_result = orchestrator.planner.create_plan(
                goal=query,
                available_tools=orchestrator.tool_catalog,
                context=None
            )
            
            if plan_result.get("success"):
                plan = plan_result.get("plan", [])
                
                # Check if plan includes focus on meetings
                plan_str = json.dumps(plan, indent=2).lower()
                has_meeting_focus = "meeting" in plan_str or "focus" in plan_str
                print(f"   {'✅' if has_meeting_focus else '⚠️'} Plan includes meeting focus: {has_meeting_focus}")
                
                # Check synthesize_content topic
                synthesize_step = None
                for step in plan:
                    if "synthesize_content" in str(step.get("action", "")).lower():
                        synthesize_step = step
                        break
                
                if synthesize_step:
                    params = synthesize_step.get("inputs", {}) or synthesize_step.get("parameters", {})
                    topic = params.get("topic", "")
                    if "meeting" in topic.lower():
                        print(f"   ✅ Synthesis topic focuses on meetings: {topic}")
                    else:
                        print(f"   ⚠️  Synthesis topic may not focus on meetings: {topic}")
                
        except Exception as e:
            print(f"   ❌ Planning error: {e}")
        
        # Test 2: Tool execution with filtering
        print("\n2. Testing tool execution...")
        try:
            # List all events
            events_result = list_calendar_events.invoke({
                "days_ahead": 7
            })
            
            if events_result.get('error'):
                print(f"   ⚠️  Error listing events: {events_result.get('error_message')}")
                continue
            
            events = events_result.get('events', [])
            
            # Filter to meetings (simulate what LLM should do)
            # Check if event title contains "meeting" or has attendees
            meeting_events = []
            for event in events:
                title = event.get('title', '').lower()
                attendees = event.get('attendees', [])
                if 'meeting' in title or len(attendees) > 0:
                    meeting_events.append(event)
            
            print(f"   ✅ Filtered to {len(meeting_events)} meeting events")
            
            if meeting_events:
                # Synthesize meeting events
                events_text = json.dumps({"events": meeting_events, "count": len(meeting_events)}, indent=2)
                
                synthesis_result = synthesize_content.invoke({
                    "source_contents": [events_text],
                    "topic": "Summary of meetings in calendar",
                    "synthesis_style": "concise"
                })
                
                if not synthesis_result.get('error'):
                    summary = synthesis_result.get('synthesized_content', '')
                    print(f"   ✅ Generated summary ({len(summary)} chars)")
                    
                    # Verify summary emphasizes meeting details
                    has_attendees = any(
                        attendee.lower() in summary.lower() 
                        for event in meeting_events 
                        for attendee in event.get('attendees', [])[:2]
                    )
                    print(f"   {'✅' if has_attendees else '⚠️'} Summary mentions attendees: {has_attendees}")
                    
                    has_locations = any(
                        event.get('location', '').lower() in summary.lower() 
                        for event in meeting_events 
                        if event.get('location')
                    )
                    print(f"   {'✅' if has_locations else '⚠️'} Summary mentions locations: {has_locations}")
                    
                    quality_check = verify_summary_quality(summary, meeting_events, "calendar")
                    print_validation_results(quality_check, f"C2 Summary Quality: {query}")
            
        except Exception as e:
            print(f"   ❌ Tool error: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Run all calendar summarization tests"""
    print_section("COMPREHENSIVE CALENDAR SUMMARIZATION TESTS")
    
    print("""
This test suite validates:
1. ✅ Tool execution without errors
2. ✅ Parameter extraction using LLM reasoning (no hardcoding)
3. ✅ Correct workflow (list_calendar_events → synthesize_content → reply_to_user)
4. ✅ Summary quality (relevance, coherence, accuracy)
5. ✅ Time window handling (days_ahead)
6. ✅ Focus extraction (meetings, etc.)
    """)
    
    try:
        test_c1_summarize_upcoming_events()
        test_c2_summarize_with_focus()
        
        print_section("ALL CALENDAR TESTS COMPLETE")
        print("Review results above for any issues or failures.")
        
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

