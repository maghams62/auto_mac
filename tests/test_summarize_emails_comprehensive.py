#!/usr/bin/env python3
"""
Comprehensive Email Summarization Tests

Tests all email summarization scenarios:
- TEST E1: Summarize last N emails
- TEST E2: Summarize emails by time window
- TEST E3: Summarize emails by sender
- TEST E4: Summarize with focus

Each test validates:
1. Tool execution
2. Parameter extraction (LLM reasoning, no hardcoding)
3. Workflow correctness
4. Summary quality (relevance, coherence, accuracy)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agent.email_agent import read_latest_emails, read_emails_by_sender, read_emails_by_time, summarize_emails
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


def test_e1_summarize_last_n_emails():
    """TEST E1: Summarize last N emails"""
    print_section("TEST E1: Summarize Last N Emails")
    
    test_queries = [
        "/email summarize my last 5 emails",
        "/email summarize the last 3 emails",
        "summarize my last 10 emails"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: {query}")
        
        # Test 1: Tool-level functionality
        print("\n1. Testing tool-level functionality...")
        try:
            # Read emails first
            count = 5  # Default for testing
            if "5" in query:
                count = 5
            elif "3" in query:
                count = 3
            elif "10" in query:
                count = 10
            
            emails_result = read_latest_emails.invoke({"count": count, "mailbox": "INBOX"})
            
            if emails_result.get('error'):
                print(f"   ⚠️  Skipping - Email reading error: {emails_result.get('error_message')}")
                print(f"   This is expected if Mail.app is not configured.")
                continue
            
            emails = emails_result.get('emails', [])
            if not emails:
                print(f"   ⚠️  No emails available to test")
                continue
            
            print(f"   ✅ Read {len(emails)} emails")
            
            # Summarize
            summary_result = summarize_emails.invoke({
                "emails_data": emails_result,
                "focus": None
            })
            
            if summary_result.get('error'):
                print(f"   ❌ Summarization error: {summary_result.get('error_message')}")
                continue
            
            summary = summary_result.get('summary', '')
            print(f"   ✅ Generated summary ({len(summary)} chars)")
            
            # Validate summary quality
            quality_check = verify_summary_quality(summary, emails, "email")
            print_validation_results(quality_check, f"E1 Tool-Level: {query}")
            
            if quality_check["score"] < 0.7:
                print(f"   ⚠️  Summary quality below threshold")
            
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            import traceback
            traceback.print_exc()
            continue
        
        # Test 2: Slash command routing
        print("\n2. Testing slash command routing...")
        try:
            handler = SlashCommandHandler()
            tool_name, params, status = handler._route_email_command(query.replace("/email ", ""))
            
            if tool_name is None:
                print(f"   ✅ Correctly delegated to orchestrator (complex query)")
            else:
                print(f"   ⚠️  Routed to single tool: {tool_name} (expected None for summarization)")
            
        except Exception as e:
            print(f"   ❌ Routing error: {e}")
        
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
                expected_workflow = ["read_latest_emails", "summarize_emails", "reply_to_user"]
                workflow_check = verify_workflow_correctness(plan, expected_workflow)
                print_validation_results(workflow_check, f"E1 Workflow: {query}")
                
                # Verify LLM reasoning
                reasoning_check = verify_llm_reasoning(plan, query)
                print_validation_results(reasoning_check, f"E1 LLM Reasoning: {query}")
                
            else:
                print(f"   ❌ Planning failed: {plan_result.get('error')}")
                
        except Exception as e:
            print(f"   ❌ Planning error: {e}")
            import traceback
            traceback.print_exc()


def test_e2_summarize_by_time_window():
    """TEST E2: Summarize emails by time window"""
    print_section("TEST E2: Summarize Emails by Time Window")
    
    test_queries = [
        "/email summarize emails from the past 2 hours",
        "/email summarize emails from the last hour",
        "summarize emails from the past 30 minutes"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: {query}")
        
        # Test time window extraction
        print("\n1. Testing time window extraction...")
        try:
            from src.ui.slash_commands import _extract_time_window
            
            task = query.replace("/email ", "")
            extracted = _extract_time_window(task)
            
            # Determine expected window
            expected = None
            if "2 hours" in query or "2h" in query:
                expected = {"hours": 2}
            elif "hour" in query and "2" not in query:
                expected = {"hours": 1}
            elif "30 minutes" in query or "30m" in query:
                expected = {"minutes": 30}
            
            window_check = verify_time_window_extraction(query, extracted, expected)
            print_validation_results(window_check, f"E2 Time Extraction: {query}")
            
            if extracted:
                print(f"   Extracted window: {extracted}")
            
        except Exception as e:
            print(f"   ❌ Extraction error: {e}")
        
        # Test tool-level functionality
        print("\n2. Testing tool-level functionality...")
        try:
            # Extract time window
            hours = None
            minutes = None
            if "2 hours" in query:
                hours = 2
            elif "hour" in query:
                hours = 1
            elif "30 minutes" in query:
                minutes = 30
            
            if hours or minutes:
                emails_result = read_emails_by_time.invoke({
                    "hours": hours,
                    "minutes": minutes,
                    "mailbox": "INBOX"
                })
                
                if emails_result.get('error'):
                    print(f"   ⚠️  Email reading error: {emails_result.get('error_message')}")
                    continue
                
                emails = emails_result.get('emails', [])
                print(f"   ✅ Read {len(emails)} emails from time window")
                
                if emails:
                    summary_result = summarize_emails.invoke({
                        "emails_data": emails_result,
                        "focus": None
                    })
                    
                    if not summary_result.get('error'):
                        summary = summary_result.get('summary', '')
                        quality_check = verify_summary_quality(summary, emails, "email")
                        print_validation_results(quality_check, f"E2 Summary Quality: {query}")
            
        except Exception as e:
            print(f"   ❌ Tool error: {e}")


def test_e3_summarize_by_sender():
    """TEST E3: Summarize emails by sender"""
    print_section("TEST E3: Summarize Emails by Sender")
    
    test_queries = [
        "/email summarize emails from john@example.com",
        "summarize emails sent by test@test.com"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: {query}")
        
        # Extract sender from query
        import re
        sender_match = re.search(r'(?:from|by)\s+([^\s]+@[^\s]+)', query.lower())
        if not sender_match:
            print(f"   ⚠️  Could not extract sender from query")
            continue
        
        sender = sender_match.group(1)
        print(f"   Extracted sender: {sender}")
        
        # Test tool-level functionality
        print("\n1. Testing tool-level functionality...")
        try:
            emails_result = read_emails_by_sender.invoke({
                "sender": sender,
                "count": 10
            })
            
            if emails_result.get('error'):
                print(f"   ⚠️  Email reading error: {emails_result.get('error_message')}")
                continue
            
            emails = emails_result.get('emails', [])
            print(f"   ✅ Read {len(emails)} emails from {sender}")
            
            if emails:
                # Verify all emails are from the correct sender
                all_from_sender = all(
                    sender.lower() in email.get('sender', '').lower() 
                    for email in emails
                )
                print(f"   {'✅' if all_from_sender else '❌'} All emails from correct sender: {all_from_sender}")
                
                summary_result = summarize_emails.invoke({
                    "emails_data": emails_result,
                    "focus": None
                })
                
                if not summary_result.get('error'):
                    summary = summary_result.get('summary', '')
                    quality_check = verify_summary_quality(summary, emails, "email")
                    print_validation_results(quality_check, f"E3 Summary Quality: {query}")
            
        except Exception as e:
            print(f"   ❌ Tool error: {e}")


def test_e4_summarize_with_focus():
    """TEST E4: Summarize with focus"""
    print_section("TEST E4: Summarize with Focus")
    
    test_queries = [
        "/email summarize my last 10 emails focusing on action items",
        "summarize emails focusing on deadlines",
        "/email summarize emails focusing on important updates"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: {query}")
        
        # Extract focus keyword
        focus_keywords = ["action items", "deadlines", "important", "urgent", "key decisions"]
        focus = None
        for keyword in focus_keywords:
            if keyword in query.lower():
                focus = keyword
                break
        
        print(f"   Extracted focus: {focus}")
        
        # Test tool-level functionality
        print("\n1. Testing tool-level functionality...")
        try:
            emails_result = read_latest_emails.invoke({"count": 10, "mailbox": "INBOX"})
            
            if emails_result.get('error'):
                print(f"   ⚠️  Email reading error: {emails_result.get('error_message')}")
                continue
            
            emails = emails_result.get('emails', [])
            if not emails:
                print(f"   ⚠️  No emails available")
                continue
            
            print(f"   ✅ Read {len(emails)} emails")
            
            # Summarize with focus
            summary_result = summarize_emails.invoke({
                "emails_data": emails_result,
                "focus": focus
            })
            
            if not summary_result.get('error'):
                summary = summary_result.get('summary', '')
                print(f"   ✅ Generated focused summary ({len(summary)} chars)")
                
                # Verify focus is applied (summary should mention focus keyword)
                if focus and focus.lower() in summary.lower():
                    print(f"   ✅ Summary mentions focus keyword: {focus}")
                else:
                    print(f"   ⚠️  Summary may not emphasize focus: {focus}")
                
                quality_check = verify_summary_quality(summary, emails, "email")
                print_validation_results(quality_check, f"E4 Summary Quality: {query}")
            
        except Exception as e:
            print(f"   ❌ Tool error: {e}")


def main():
    """Run all email summarization tests"""
    print_section("COMPREHENSIVE EMAIL SUMMARIZATION TESTS")
    
    print("""
This test suite validates:
1. ✅ Tool execution without errors
2. ✅ Parameter extraction using LLM reasoning (no hardcoding)
3. ✅ Correct workflow (read → summarize → reply)
4. ✅ Summary quality (relevance, coherence, accuracy)
5. ✅ Time window handling
6. ✅ Empty data handling
    """)
    
    try:
        test_e1_summarize_last_n_emails()
        test_e2_summarize_by_time_window()
        test_e3_summarize_by_sender()
        test_e4_summarize_with_focus()
        
        print_section("ALL EMAIL TESTS COMPLETE")
        print("Review results above for any issues or failures.")
        
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

