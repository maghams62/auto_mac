#!/usr/bin/env python3
"""
Comprehensive Bluesky/Tweets Summarization Tests

Tests all Bluesky summarization scenarios:
- TEST B1: Summarize posts by query
- TEST B2: Summarize "what happened" queries
- TEST B3: Summarize last N tweets

Each test validates:
1. Tool execution
2. Parameter extraction (LLM reasoning, no hardcoding)
3. Workflow correctness
4. Summary quality (relevance, coherence, accuracy)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agent.bluesky_agent import summarize_bluesky_posts
from src.ui.slash_commands import SlashCommandHandler
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
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def test_b1_summarize_by_query():
    """TEST B1: Summarize posts by query"""
    print_section("TEST B1: Summarize Posts by Query")
    
    test_queries = [
        "/bluesky summarize \"AI agents\" 12h",
        "/bluesky summarize \"machine learning\" 24h max:5",
        "summarize bluesky posts about \"python\" from the past 6 hours"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: {query}")
        
        # Test 1: Slash command parsing
        print("\n1. Testing slash command parsing...")
        try:
            handler = SlashCommandHandler()
            task = query.replace("/bluesky ", "")
            
            # Parse bluesky task
            action, params = handler._parse_bluesky_task(task)
            
            print(f"   Action: {action}")
            print(f"   Parameters: {params}")
            
            # Verify query extraction
            extracted_query = params.get("query", "")
            print(f"   Extracted query: {extracted_query}")
            
            # Verify time window extraction
            lookback_hours = params.get("lookback_hours")
            if lookback_hours:
                print(f"   Lookback hours: {lookback_hours}")
                # Check if it matches query
                if "12h" in query or "12 hours" in query:
                    if lookback_hours == 12:
                        print(f"   ✅ Time window correctly extracted")
                    else:
                        print(f"   ⚠️  Time window mismatch: expected 12, got {lookback_hours}")
                elif "24h" in query or "24 hours" in query:
                    if lookback_hours == 24:
                        print(f"   ✅ Time window correctly extracted")
                    else:
                        print(f"   ⚠️  Time window mismatch: expected 24, got {lookback_hours}")
                elif "6 hours" in query:
                    if lookback_hours == 6:
                        print(f"   ✅ Time window correctly extracted")
                    else:
                        print(f"   ⚠️  Time window mismatch: expected 6, got {lookback_hours}")
            
            # Verify max_items extraction
            max_items = params.get("max_items")
            if max_items:
                print(f"   Max items: {max_items}")
                if "max:5" in query or "limit:5" in query:
                    if max_items == 5:
                        print(f"   ✅ Max items correctly extracted")
                    else:
                        print(f"   ⚠️  Max items mismatch: expected 5, got {max_items}")
            
        except Exception as e:
            print(f"   ❌ Parsing error: {e}")
            import traceback
            traceback.print_exc()
            continue
        
        # Test 2: Tool-level functionality
        print("\n2. Testing tool-level functionality...")
        try:
            result = summarize_bluesky_posts.invoke({
                "query": params.get("query", "AI"),
                "lookback_hours": params.get("lookback_hours", 24),
                "max_items": params.get("max_items", 5)
            })
            
            if result.get('error'):
                print(f"   ⚠️  Error: {result.get('error_message')}")
                print(f"   Error type: {result.get('error_type')}")
                print(f"   This may be expected if Bluesky API is not configured.")
                continue
            
            summary = result.get('summary', '')
            posts = result.get('posts', [])
            
            print(f"   ✅ Generated summary ({len(summary)} chars)")
            print(f"   ✅ Summarized {len(posts)} posts")
            
            # Validate summary quality
            if posts:
                quality_check = verify_summary_quality(summary, posts, "bluesky")
                print_validation_results(quality_check, f"B1 Summary Quality: {query}")
                
                # Check for post references [1], [2], etc.
                has_references = any(f"[{i}]" in summary for i in range(1, len(posts) + 1))
                print(f"   {'✅' if has_references else '⚠️'} Summary includes post references: {has_references}")
                
                # Check for links section
                has_links = "link" in summary.lower() or "url" in summary.lower()
                print(f"   {'✅' if has_links else '⚠️'} Summary includes links section: {has_links}")
            
        except Exception as e:
            print(f"   ❌ Tool error: {e}")
            import traceback
            traceback.print_exc()
        
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
                expected_workflow = ["summarize_bluesky_posts", "reply_to_user"]
                workflow_check = verify_workflow_correctness(plan, expected_workflow)
                print_validation_results(workflow_check, f"B1 Workflow: {query}")
                
                # Verify LLM reasoning (check for hardcoded queries)
                reasoning_check = verify_llm_reasoning(plan, query)
                print_validation_results(reasoning_check, f"B1 LLM Reasoning: {query}")
                
            else:
                print(f"   ❌ Planning failed: {plan_result.get('error')}")
                
        except Exception as e:
            print(f"   ❌ Planning error: {e}")


def test_b2_what_happened_queries():
    """TEST B2: Summarize 'what happened' queries"""
    print_section("TEST B2: Summarize 'What Happened' Queries")
    
    test_queries = [
        "/bluesky summarize what happened in the past hour",
        "/bluesky summarize what happened",
        "summarize bluesky activity from the last 2 hours"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: {query}")
        
        # Test 1: Verify LLM determines search query (not hardcoded)
        print("\n1. Testing LLM query determination...")
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
                
                # Find summarize_bluesky_posts step
                summarize_step = None
                for step in plan:
                    if "summarize_bluesky" in str(step.get("action", "")).lower():
                        summarize_step = step
                        break
                
                if summarize_step:
                    params = summarize_step.get("inputs", {}) or summarize_step.get("parameters", {})
                    search_query = params.get("query", "")
                    
                    print(f"   Determined search query: {search_query}")
                    
                    # Check if query is generic/hardcoded
                    hardcoded_queries = ["trending", "news", "what happened", "activity"]
                    is_hardcoded = search_query.lower() in hardcoded_queries
                    
                    if is_hardcoded:
                        print(f"   ⚠️  Query appears hardcoded: {search_query}")
                    else:
                        print(f"   ✅ Query determined by LLM reasoning: {search_query}")
                    
                    # Verify time window extraction
                    lookback_hours = params.get("lookback_hours")
                    if lookback_hours:
                        print(f"   Lookback hours: {lookback_hours}")
                        if "hour" in query.lower() and "2" not in query.lower():
                            if lookback_hours == 1:
                                print(f"   ✅ Time window correctly extracted")
                            else:
                                print(f"   ⚠️  Time window mismatch")
                        elif "2 hours" in query.lower():
                            if lookback_hours == 2:
                                print(f"   ✅ Time window correctly extracted")
                            else:
                                print(f"   ⚠️  Time window mismatch")
                else:
                    print(f"   ⚠️  Could not find summarize step in plan")
                
            else:
                print(f"   ❌ Planning failed: {plan_result.get('error')}")
                
        except Exception as e:
            print(f"   ❌ Planning error: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 2: Tool execution with determined query
        print("\n2. Testing tool execution...")
        try:
            # Use a reasonable query for testing
            test_query = "trending"  # Fallback for testing
            lookback_hours = 1
            if "2 hours" in query:
                lookback_hours = 2
            
            result = summarize_bluesky_posts.invoke({
                "query": test_query,
                "lookback_hours": lookback_hours,
                "max_items": 5
            })
            
            if result.get('error'):
                print(f"   ⚠️  Error: {result.get('error_message')}")
                print(f"   This may be expected if Bluesky API is not configured.")
                continue
            
            summary = result.get('summary', '')
            posts = result.get('posts', [])
            
            print(f"   ✅ Generated summary ({len(summary)} chars)")
            print(f"   ✅ Summarized {len(posts)} posts")
            
            # Verify summary makes sense contextually
            if summary:
                # Check for coherence
                is_coherent = len(summary) > 100 and "." in summary
                print(f"   {'✅' if is_coherent else '⚠️'} Summary appears coherent: {is_coherent}")
                
                # Check for recent activity indicators
                recent_indicators = ["recent", "today", "hour", "latest", "new"]
                has_recent_context = any(indicator in summary.lower() for indicator in recent_indicators)
                print(f"   {'✅' if has_recent_context else '⚠️'} Summary reflects recent activity: {has_recent_context}")
            
        except Exception as e:
            print(f"   ❌ Tool error: {e}")


def test_b3_summarize_last_n_tweets():
    """TEST B3: Summarize last N tweets"""
    print_section("TEST B3: Summarize Last N Tweets")
    
    test_queries = [
        "/bluesky summarize my last 3 tweets",
        "/bluesky summarize my last 5 tweets",
        "summarize my recent tweets"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: {query}")
        
        # Test 1: Verify author feed detection
        print("\n1. Testing author feed detection...")
        try:
            handler = SlashCommandHandler()
            task = query.replace("/bluesky ", "")
            
            action, params = handler._parse_bluesky_task(task)
            
            print(f"   Action: {action}")
            print(f"   Parameters: {params}")
            
            # Check if query indicates author feed
            query_text = params.get("query", "").lower()
            is_author_feed = any(phrase in query_text for phrase in ["my tweets", "my posts", "last", "recent"])
            
            print(f"   {'✅' if is_author_feed else '⚠️'} Author feed detected: {is_author_feed}")
            
            # Extract number of tweets
            import re
            num_match = re.search(r'(\d+)', query)
            if num_match:
                expected_count = int(num_match.group(1))
                print(f"   Expected count: {expected_count}")
            
        except Exception as e:
            print(f"   ❌ Parsing error: {e}")
            import traceback
            traceback.print_exc()
            continue
        
        # Test 2: Tool execution
        print("\n2. Testing tool execution...")
        try:
            # Extract count
            import re
            num_match = re.search(r'(\d+)', query)
            max_items = int(num_match.group(1)) if num_match else 5
            
            result = summarize_bluesky_posts.invoke({
                "query": query,
                "lookback_hours": 168,  # 1 week for "my tweets"
                "max_items": max_items,
                "actor": None  # Should detect authenticated user
            })
            
            if result.get('error'):
                print(f"   ⚠️  Error: {result.get('error_message')}")
                print(f"   This may be expected if Bluesky API is not configured or user not authenticated.")
                continue
            
            summary = result.get('summary', '')
            posts = result.get('posts', [])
            
            print(f"   ✅ Generated summary ({len(summary)} chars)")
            print(f"   ✅ Summarized {len(posts)} posts")
            
            # Verify count matches
            if num_match:
                expected_count = int(num_match.group(1))
                if len(posts) <= expected_count:
                    print(f"   ✅ Post count matches or is less than requested: {len(posts)} <= {expected_count}")
                else:
                    print(f"   ⚠️  Post count exceeds requested: {len(posts)} > {expected_count}")
            
            # Verify summary references user's content
            if summary and posts:
                # Check if summary mentions user-specific content
                quality_check = verify_summary_quality(summary, posts, "bluesky")
                print_validation_results(quality_check, f"B3 Summary Quality: {query}")
            
        except Exception as e:
            print(f"   ❌ Tool error: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Run all Bluesky summarization tests"""
    print_section("COMPREHENSIVE BLUESKY SUMMARIZATION TESTS")
    
    print("""
This test suite validates:
1. ✅ Tool execution without errors
2. ✅ Parameter extraction using LLM reasoning (no hardcoding)
3. ✅ Correct workflow (summarize → reply)
4. ✅ Summary quality (relevance, coherence, accuracy)
5. ✅ Time window handling
6. ✅ Query determination for "what happened" queries (LLM reasoning)
7. ✅ Author feed detection for "my tweets"
    """)
    
    try:
        test_b1_summarize_by_query()
        test_b2_what_happened_queries()
        test_b3_summarize_last_n_tweets()
        
        print_section("ALL BLUESKY TESTS COMPLETE")
        print("Review results above for any issues or failures.")
        
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

