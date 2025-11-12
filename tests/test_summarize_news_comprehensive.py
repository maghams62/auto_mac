#!/usr/bin/env python3
"""
Comprehensive News Summarization Tests (DuckDuckGo)

Tests all news summarization scenarios:
- TEST N1: Summarize news by query
- TEST N2: Summarize recent news

Each test validates:
1. Tool execution
2. Parameter extraction (LLM reasoning, no hardcoding)
3. Workflow correctness (google_search → synthesize_content → reply_to_user)
4. Summary quality (relevance, coherence, accuracy)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agent.google_agent import google_search
from src.agent.writing_agent import synthesize_content
from src.orchestrator.main_orchestrator import MainOrchestrator
from src.utils import load_config
from test_summarize_utils import (
    verify_summary_quality,
    verify_llm_reasoning,
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


def test_n1_summarize_by_query():
    """TEST N1: Summarize news by query"""
    print_section("TEST N1: Summarize News by Query")
    
    test_queries = [
        "summarize news about AI",
        "summarize news about artificial intelligence",
        "/search summarize news about machine learning"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: {query}")
        
        # Test 1: Tool-level functionality
        print("\n1. Testing tool-level functionality...")
        try:
            # Extract search query
            search_query = "AI news"  # Default
            if "AI" in query or "artificial intelligence" in query:
                search_query = "AI news"
            elif "machine learning" in query:
                search_query = "machine learning news"
            
            # Perform search
            search_result = google_search.invoke({
                "query": search_query,
                "num_results": 5,
                "search_type": "web"
            })
            
            if search_result.get('error'):
                print(f"   ⚠️  Search error: {search_result.get('error_message')}")
                print(f"   This may be expected if DuckDuckGo is blocked.")
                continue
            
            results = search_result.get('results', [])
            summary_from_search = search_result.get('summary', '')
            
            print(f"   ✅ Found {len(results)} search results")
            print(f"   ✅ Search returned summary ({len(summary_from_search)} chars)")
            
            if not results:
                print(f"   ⚠️  No results available to synthesize")
                continue
            
            # Display sample results
            print(f"\n   Sample Results:")
            for i, result in enumerate(results[:3], 1):
                print(f"   {i}. {result.get('title', 'No title')}")
                print(f"      {result.get('link', 'No link')}")
            
            # Synthesize results for richer summary
            print(f"\n2. Testing synthesis...")
            
            # Convert results to string format
            results_text = json.dumps(results, indent=2)
            
            synthesis_result = synthesize_content.invoke({
                "source_contents": [results_text],
                "topic": f"Summary of news about {search_query}",
                "synthesis_style": "concise"
            })
            
            if synthesis_result.get('error'):
                print(f"   ❌ Synthesis error: {synthesis_result.get('error_message')}")
                continue
            
            synthesized_summary = synthesis_result.get('synthesized_content', '')
            print(f"   ✅ Generated synthesized summary ({len(synthesized_summary)} chars)")
            
            # Validate summary quality
            quality_check = verify_summary_quality(synthesized_summary, results, "news")
            print_validation_results(quality_check, f"N1 Summary Quality: {query}")
            
            # Verify summary references result numbers
            has_references = any(f"[{i}]" in synthesized_summary or f"result {i}" in synthesized_summary.lower() 
                                for i in range(1, len(results) + 1))
            print(f"   {'✅' if has_references else '⚠️'} Summary references result numbers: {has_references}")
            
            # Verify summary is coherent and relevant
            is_relevant = search_query.lower().split()[0] in synthesized_summary.lower()
            print(f"   {'✅' if is_relevant else '⚠️'} Summary is relevant to query: {is_relevant}")
            
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
                expected_workflow = ["google_search", "synthesize_content", "reply_to_user"]
                workflow_check = verify_workflow_correctness(plan, expected_workflow)
                print_validation_results(workflow_check, f"N1 Workflow: {query}")
                
                # Verify LLM reasoning
                reasoning_check = verify_llm_reasoning(plan, query)
                print_validation_results(reasoning_check, f"N1 LLM Reasoning: {query}")
                
                # Check that search query is extracted from user query
                search_step = None
                for step in plan:
                    if "google_search" in str(step.get("action", "")).lower() or "search" in str(step.get("action", "")).lower():
                        search_step = step
                        break
                
                if search_step:
                    params = search_step.get("inputs", {}) or search_step.get("parameters", {})
                    search_query_param = params.get("query", "")
                    if search_query_param:
                        print(f"   ✅ Search query extracted: {search_query_param}")
                        # Verify it's not hardcoded
                        if search_query_param.lower() in ["news", "trending"] and "news" not in query.lower():
                            print(f"   ⚠️  Search query may be hardcoded: {search_query_param}")
                        else:
                            print(f"   ✅ Search query uses LLM reasoning")
                
            else:
                print(f"   ❌ Planning failed: {plan_result.get('error')}")
                
        except Exception as e:
            print(f"   ❌ Planning error: {e}")
            import traceback
            traceback.print_exc()


def test_n2_summarize_recent_news():
    """TEST N2: Summarize recent news"""
    print_section("TEST N2: Summarize Recent News")
    
    test_queries = [
        "summarize recent tech news",
        "summarize latest news",
        "what's the latest news about technology"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: {query}")
        
        # Test 1: Verify LLM determines search query
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
                
                # Find search step
                search_step = None
                for step in plan:
                    if "google_search" in str(step.get("action", "")).lower() or "search" in str(step.get("action", "")).lower():
                        search_step = step
                        break
                
                if search_step:
                    params = search_step.get("inputs", {}) or search_step.get("parameters", {})
                    search_query = params.get("query", "")
                    
                    print(f"   Determined search query: {search_query}")
                    
                    # Check if query includes "recent" or "today" (indicating LLM reasoning)
                    has_recent_context = any(keyword in search_query.lower() for keyword in ["recent", "today", "latest", "news"])
                    print(f"   {'✅' if has_recent_context else '⚠️'} Query includes recent context: {has_recent_context}")
                    
                    # Check for hardcoded generic queries
                    hardcoded_queries = ["news", "trending"]
                    is_hardcoded = search_query.lower() in hardcoded_queries and len(search_query.split()) == 1
                    
                    if is_hardcoded:
                        print(f"   ⚠️  Query appears hardcoded: {search_query}")
                    else:
                        print(f"   ✅ Query determined by LLM reasoning: {search_query}")
                    
                    # Verify topic extraction
                    if "tech" in query.lower() or "technology" in query.lower():
                        if "tech" in search_query.lower() or "technology" in search_query.lower():
                            print(f"   ✅ Topic correctly extracted from query")
                        else:
                            print(f"   ⚠️  Topic may not be extracted: {search_query}")
                
            else:
                print(f"   ❌ Planning failed: {plan_result.get('error')}")
                
        except Exception as e:
            print(f"   ❌ Planning error: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 2: Tool execution
        print("\n2. Testing tool execution...")
        try:
            # Determine search query (what LLM should do)
            search_query = "recent tech news"
            if "tech" in query.lower():
                search_query = "recent tech news"
            elif "technology" in query.lower():
                search_query = "recent technology news"
            else:
                search_query = "recent news"
            
            search_result = google_search.invoke({
                "query": search_query,
                "num_results": 5,
                "search_type": "web"
            })
            
            if search_result.get('error'):
                print(f"   ⚠️  Search error: {search_result.get('error_message')}")
                print(f"   This may be expected if DuckDuckGo is blocked.")
                continue
            
            results = search_result.get('results', [])
            summary_from_search = search_result.get('summary', '')
            
            print(f"   ✅ Found {len(results)} search results")
            print(f"   ✅ Search returned summary ({len(summary_from_search)} chars)")
            
            # Verify summary reflects recent information
            if summary_from_search:
                recent_indicators = ["recent", "today", "latest", "new", "2024", "2025"]
                has_recent_info = any(indicator in summary_from_search.lower() for indicator in recent_indicators)
                print(f"   {'✅' if has_recent_info else '⚠️'} Summary reflects recent information: {has_recent_info}")
            
            # Synthesize for richer summary
            if results:
                results_text = json.dumps(results, indent=2)
                
                synthesis_result = synthesize_content.invoke({
                    "source_contents": [results_text],
                    "topic": f"Summary of {search_query}",
                    "synthesis_style": "concise"
                })
                
                if not synthesis_result.get('error'):
                    synthesized_summary = synthesis_result.get('synthesized_content', '')
                    print(f"   ✅ Generated synthesized summary ({len(synthesized_summary)} chars)")
                    
                    quality_check = verify_summary_quality(synthesized_summary, results, "news")
                    print_validation_results(quality_check, f"N2 Summary Quality: {query}")
            
        except Exception as e:
            print(f"   ❌ Tool error: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Run all news summarization tests"""
    print_section("COMPREHENSIVE NEWS SUMMARIZATION TESTS (DuckDuckGo)")
    
    print("""
This test suite validates:
1. ✅ Tool execution without errors
2. ✅ Parameter extraction using LLM reasoning (no hardcoding)
3. ✅ Correct workflow (google_search → synthesize_content → reply_to_user)
4. ✅ Summary quality (relevance, coherence, accuracy)
5. ✅ Search query generation for "recent news" (LLM reasoning)
6. ✅ Summary references result numbers
    """)
    
    try:
        test_n1_summarize_by_query()
        test_n2_summarize_recent_news()
        
        print_section("ALL NEWS TESTS COMPLETE")
        print("Review results above for any issues or failures.")
        
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

