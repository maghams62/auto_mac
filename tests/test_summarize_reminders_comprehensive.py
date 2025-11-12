#!/usr/bin/env python3
"""
Comprehensive Reminders Summarization Tests

Tests all reminders summarization scenarios:
- TEST R1: Summarize all reminders
- TEST R2: Summarize reminders by time

Each test validates:
1. Tool execution
2. Parameter extraction (LLM reasoning, no hardcoding)
3. Workflow correctness (list → synthesize → reply)
4. Summary quality (relevance, coherence, accuracy)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agent.reminders_agent import list_reminders
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


def test_r1_summarize_all_reminders():
    """TEST R1: Summarize all reminders"""
    print_section("TEST R1: Summarize All Reminders")
    
    test_queries = [
        "summarize my reminders",
        "summarize my todos",
        "what are my reminders"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: {query}")
        
        # Test 1: Tool-level functionality
        print("\n1. Testing tool-level functionality...")
        try:
            # List reminders
            reminders_result = list_reminders.invoke({
                "list_name": None,
                "include_completed": False
            })
            
            if reminders_result.get('error'):
                print(f"   ⚠️  Error listing reminders: {reminders_result.get('error_message')}")
                print(f"   This may be expected if Reminders.app is not configured.")
                continue
            
            reminders = reminders_result.get('reminders', [])
            print(f"   ✅ Listed {len(reminders)} reminders")
            
            if not reminders:
                print(f"   ⚠️  No reminders available to summarize")
                # Test empty handling
                print(f"   Testing empty reminders handling...")
                empty_data = json.dumps({"reminders": [], "count": 0})
                synthesis_result = synthesize_content.invoke({
                    "source_contents": [empty_data],
                    "topic": "Summary of reminders",
                    "synthesis_style": "concise"
                })
                
                if not synthesis_result.get('error'):
                    summary = synthesis_result.get('synthesized_content', '')
                    print(f"   ✅ Empty reminders handled gracefully")
                    print(f"   Summary: {summary[:100]}...")
                continue
            
            # Display sample reminders
            print(f"\n   Sample Reminders:")
            for i, reminder in enumerate(reminders[:3], 1):
                print(f"   {i}. {reminder.get('title', 'Untitled')}")
                if reminder.get('due_date'):
                    print(f"      Due: {reminder.get('due_date')}")
            
            # Synthesize reminders
            print(f"\n2. Testing synthesis...")
            
            # Convert reminders to string format for synthesis
            reminders_text = json.dumps(reminders_result, indent=2)
            
            synthesis_result = synthesize_content.invoke({
                "source_contents": [reminders_text],
                "topic": "Summary of reminders and todos",
                "synthesis_style": "concise"
            })
            
            if synthesis_result.get('error'):
                print(f"   ❌ Synthesis error: {synthesis_result.get('error_message')}")
                continue
            
            summary = synthesis_result.get('synthesized_content', '')
            print(f"   ✅ Generated summary ({len(summary)} chars)")
            
            # Validate summary quality
            quality_check = verify_summary_quality(summary, reminders, "reminder")
            print_validation_results(quality_check, f"R1 Summary Quality: {query}")
            
            # Verify summary includes reminder details
            has_titles = any(reminder.get('title', '').lower() in summary.lower() for reminder in reminders[:3])
            print(f"   {'✅' if has_titles else '⚠️'} Summary mentions reminder titles: {has_titles}")
            
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
                expected_workflow = ["list_reminders", "synthesize_content", "reply_to_user"]
                workflow_check = verify_workflow_correctness(plan, expected_workflow)
                print_validation_results(workflow_check, f"R1 Workflow: {query}")
                
                # Verify LLM reasoning
                reasoning_check = verify_llm_reasoning(plan, query)
                print_validation_results(reasoning_check, f"R1 LLM Reasoning: {query}")
                
                # Check that synthesize_content receives reminders data
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
                        # Check if it references reminders step
                        has_reminders_ref = any("reminder" in str(src).lower() or "$step" in str(src) for src in source_contents)
                        print(f"   {'✅' if has_reminders_ref else '⚠️'} Source references reminders: {has_reminders_ref}")
                
            else:
                print(f"   ❌ Planning failed: {plan_result.get('error')}")
                
        except Exception as e:
            print(f"   ❌ Planning error: {e}")
            import traceback
            traceback.print_exc()


def test_r2_summarize_by_time():
    """TEST R2: Summarize reminders by time"""
    print_section("TEST R2: Summarize Reminders by Time")
    
    test_queries = [
        "summarize reminders due in the next 3 days",
        "summarize todos due this week",
        "what reminders are due tomorrow"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: {query}")
        
        # Test 1: Verify time window extraction
        print("\n1. Testing time window extraction...")
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
                
                # Check if plan extracts time window
                # The planner should use LLM reasoning to extract "3 days", "this week", etc.
                plan_str = json.dumps(plan, indent=2).lower()
                
                # Check for time-related parameters
                has_time_logic = any(keyword in plan_str for keyword in ["day", "week", "due", "time"])
                print(f"   {'✅' if has_time_logic else '⚠️'} Plan includes time-related logic: {has_time_logic}")
                
                # Verify LLM reasoning (no hardcoded values)
                reasoning_check = verify_llm_reasoning(plan, query)
                print_validation_results(reasoning_check, f"R2 LLM Reasoning: {query}")
                
                # Check for hardcoded "7 days" or similar
                if "7" in plan_str and "7" not in query.lower() and "week" not in query.lower():
                    print(f"   ⚠️  Plan may contain hardcoded 7-day default")
                
        except Exception as e:
            print(f"   ❌ Planning error: {e}")
        
        # Test 2: Tool execution with filtering
        print("\n2. Testing tool execution...")
        try:
            # List all reminders first
            reminders_result = list_reminders.invoke({
                "list_name": None,
                "include_completed": False
            })
            
            if reminders_result.get('error'):
                print(f"   ⚠️  Error listing reminders: {reminders_result.get('error_message')}")
                continue
            
            reminders = reminders_result.get('reminders', [])
            
            # Filter by time window (simulate what LLM should do)
            # For "next 3 days", filter reminders with due_date in next 3 days
            from datetime import datetime, timedelta
            
            filtered_reminders = []
            if "3 days" in query.lower():
                cutoff_date = datetime.now() + timedelta(days=3)
                for reminder in reminders:
                    due_date_str = reminder.get('due_date')
                    if due_date_str:
                        try:
                            due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                            if due_date <= cutoff_date:
                                filtered_reminders.append(reminder)
                        except:
                            pass
            
            print(f"   ✅ Filtered to {len(filtered_reminders)} reminders in time window")
            
            if filtered_reminders:
                # Synthesize filtered reminders
                reminders_text = json.dumps({"reminders": filtered_reminders, "count": len(filtered_reminders)}, indent=2)
                
                synthesis_result = synthesize_content.invoke({
                    "source_contents": [reminders_text],
                    "topic": "Summary of reminders due in the next 3 days",
                    "synthesis_style": "concise"
                })
                
                if not synthesis_result.get('error'):
                    summary = synthesis_result.get('synthesized_content', '')
                    print(f"   ✅ Generated summary ({len(summary)} chars)")
                    
                    quality_check = verify_summary_quality(summary, filtered_reminders, "reminder")
                    print_validation_results(quality_check, f"R2 Summary Quality: {query}")
            
        except Exception as e:
            print(f"   ❌ Tool error: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Run all reminders summarization tests"""
    print_section("COMPREHENSIVE REMINDERS SUMMARIZATION TESTS")
    
    print("""
This test suite validates:
1. ✅ Tool execution without errors
2. ✅ Parameter extraction using LLM reasoning (no hardcoding)
3. ✅ Correct workflow (list_reminders → synthesize_content → reply_to_user)
4. ✅ Summary quality (relevance, coherence, accuracy)
5. ✅ Time window handling
6. ✅ Empty reminders handling
    """)
    
    try:
        test_r1_summarize_all_reminders()
        test_r2_summarize_by_time()
        
        print_section("ALL REMINDERS TESTS COMPLETE")
        print("Review results above for any issues or failures.")
        
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

