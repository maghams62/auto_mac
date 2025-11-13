"""
Test script for email content verification.

Tests the LLM-based email content verifier with the trip planning + email scenario.
"""

import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agent.email_content_verifier import verify_compose_email_content

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_trip_planning_with_email():
    """
    Test scenario: User asks to plan a trip and send links to email.
    
    This is the exact scenario reported by the user where links were
    missing from the email body.
    """
    print("\n" + "="*80)
    print("TEST 1: Trip Planning with Email (Missing Links)")
    print("="*80)
    
    user_request = "Plan a trip from L.A. to Las Vegas and send the links to my email please."
    
    # Simulate step results from plan_trip_with_stops
    step_results = {
        1: {
            "tool": "plan_trip_with_stops",
            "origin": "Los Angeles, CA",
            "destination": "Las Vegas, NV",
            "maps_url": "https://maps.apple.com/?saddr=Los%20Angeles%2C%20CA&daddr=restaurant%20near%20Barstow%2C%20CA%2C%20USA&daddr=gas%20station%20near%20Baker%2C%20CA%2C%20USA&daddr=Las%20Vegas%2C%20NV&dirflg=d",
            "message": "Here's your trip, enjoy! Apple Maps opened with your route: https://maps.apple.com/?saddr=Los%20Angeles%2C%20CA&daddr=restaurant%20near%20Barstow%2C%20CA%2C%20USA&daddr=gas%20station%20near%20Baker%2C%20CA%2C%20USA&daddr=Las%20Vegas%2C%20NV&dirflg=d",
            "total_stops": 2,
            "maps_opened": True
        }
    }
    
    # Test Case 1: Email body is missing the link
    print("\n--- Case 1a: Email body WITHOUT link (should FAIL verification) ---")
    compose_email_params_bad = {
        "subject": "Your trip from L.A. to Las Vegas",
        "body": "Here's your trip plan. Have a great journey!",
        "recipient": "me",
        "send": True
    }
    
    result = verify_compose_email_content(
        user_request=user_request,
        compose_email_params=compose_email_params_bad,
        step_results=step_results,
        current_step_id="step_2"
    )
    
    print(f"\nVerification Result:")
    print(f"  Verified: {result.get('verified')}")
    print(f"  Missing Items: {result.get('missing_items', [])}")
    print(f"  Reasoning: {result.get('reasoning', '')}")
    if not result.get('verified'):
        print(f"\n  Suggested Corrections:")
        suggestions = result.get('suggestions', {})
        if 'body' in suggestions:
            print(f"    New Body: {suggestions['body'][:200]}...")
        if 'attachments' in suggestions:
            print(f"    New Attachments: {suggestions['attachments']}")
    
    assert not result.get('verified'), "Should detect missing link in email body"
    assert len(result.get('missing_items', [])) > 0, "Should list missing items"
    assert 'suggestions' in result, "Should provide suggestions"
    print("\n✅ Case 1a PASSED: Detected missing link")
    
    # Test Case 2: Email body includes the link
    print("\n--- Case 1b: Email body WITH link (should PASS verification) ---")
    compose_email_params_good = {
        "subject": "Your trip from L.A. to Las Vegas",
        "body": "Here's your trip plan: https://maps.apple.com/?saddr=Los%20Angeles%2C%20CA&daddr=restaurant%20near%20Barstow%2C%20CA%2C%20USA&daddr=Las%20Vegas%2C%20NV&dirflg=d\n\nHave a great journey!",
        "recipient": "me",
        "send": True
    }
    
    result = verify_compose_email_content(
        user_request=user_request,
        compose_email_params=compose_email_params_good,
        step_results=step_results,
        current_step_id="step_2"
    )
    
    print(f"\nVerification Result:")
    print(f"  Verified: {result.get('verified')}")
    print(f"  Reasoning: {result.get('reasoning', '')}")
    
    assert result.get('verified'), "Should verify email contains the link"
    print("\n✅ Case 1b PASSED: Verified link is present")


def test_file_attachment_scenario():
    """
    Test scenario: User asks to email a report as attachment.
    """
    print("\n" + "="*80)
    print("TEST 2: Email Report as Attachment (Missing Attachment)")
    print("="*80)
    
    user_request = "Create a stock report for Tesla and email it to me"
    
    # Simulate step results from report creation
    step_results = {
        1: {
            "tool": "create_detailed_report",
            "report_content": "Tesla Stock Analysis\n\nTesla (TSLA) is currently trading at $225.50...",
            "message": "Report created successfully"
        },
        2: {
            "tool": "create_pages_doc",
            "pages_path": "/Users/test/Documents/tesla_report.pages",
            "message": "Document created at /Users/test/Documents/tesla_report.pages"
        }
    }
    
    # Test Case 1: Email is missing the attachment
    print("\n--- Case 2a: Email WITHOUT attachment (should FAIL verification) ---")
    compose_email_params_bad = {
        "subject": "Tesla Stock Report",
        "body": "Please find attached the Tesla stock analysis report.",
        "recipient": "me",
        "send": True,
        "attachments": []
    }
    
    result = verify_compose_email_content(
        user_request=user_request,
        compose_email_params=compose_email_params_bad,
        step_results=step_results,
        current_step_id="step_3"
    )
    
    print(f"\nVerification Result:")
    print(f"  Verified: {result.get('verified')}")
    print(f"  Missing Items: {result.get('missing_items', [])}")
    print(f"  Reasoning: {result.get('reasoning', '')}")
    if not result.get('verified'):
        print(f"\n  Suggested Corrections:")
        suggestions = result.get('suggestions', {})
        if 'attachments' in suggestions:
            print(f"    New Attachments: {suggestions['attachments']}")
    
    assert not result.get('verified'), "Should detect missing attachment"
    assert len(result.get('missing_items', [])) > 0, "Should list missing items"
    print("\n✅ Case 2a PASSED: Detected missing attachment")
    
    # Test Case 2: Email includes the attachment
    print("\n--- Case 2b: Email WITH attachment (should PASS verification) ---")
    compose_email_params_good = {
        "subject": "Tesla Stock Report",
        "body": "Please find attached the Tesla stock analysis report.",
        "recipient": "me",
        "send": True,
        "attachments": ["/Users/test/Documents/tesla_report.pages"]
    }
    
    result = verify_compose_email_content(
        user_request=user_request,
        compose_email_params=compose_email_params_good,
        step_results=step_results,
        current_step_id="step_3"
    )
    
    print(f"\nVerification Result:")
    print(f"  Verified: {result.get('verified')}")
    print(f"  Reasoning: {result.get('reasoning', '')}")
    
    assert result.get('verified'), "Should verify email contains attachment"
    print("\n✅ Case 2b PASSED: Verified attachment is present")


def test_links_in_body_scenario():
    """
    Test scenario: User asks to send search results via email.
    """
    print("\n" + "="*80)
    print("TEST 3: Send Search Results via Email (Missing Results)")
    print("="*80)
    
    user_request = "Search for Tesla news and email me the results"
    
    # Simulate step results from google_search
    step_results = {
        1: {
            "tool": "google_search",
            "results": [
                {
                    "title": "Tesla announces new model",
                    "url": "https://example.com/tesla-news-1",
                    "snippet": "Tesla today announced..."
                },
                {
                    "title": "Tesla stock surges",
                    "url": "https://example.com/tesla-news-2",
                    "snippet": "Tesla stock rose by 5%..."
                }
            ],
            "summary": "Found 2 results about Tesla news"
        }
    }
    
    # Test Case 1: Email body doesn't include search results
    print("\n--- Case 3a: Email WITHOUT search results (should FAIL verification) ---")
    compose_email_params_bad = {
        "subject": "Tesla News Search Results",
        "body": "Here are the search results you requested.",
        "recipient": "me",
        "send": True
    }
    
    result = verify_compose_email_content(
        user_request=user_request,
        compose_email_params=compose_email_params_bad,
        step_results=step_results,
        current_step_id="step_2"
    )
    
    print(f"\nVerification Result:")
    print(f"  Verified: {result.get('verified')}")
    print(f"  Missing Items: {result.get('missing_items', [])}")
    print(f"  Reasoning: {result.get('reasoning', '')}")
    
    assert not result.get('verified'), "Should detect missing search results"
    print("\n✅ Case 3a PASSED: Detected missing search results")
    
    # Test Case 2: Email body includes search results
    print("\n--- Case 3b: Email WITH search results (should PASS verification) ---")
    compose_email_params_good = {
        "subject": "Tesla News Search Results",
        "body": """Here are the search results you requested:

1. Tesla announces new model
   https://example.com/tesla-news-1
   Tesla today announced...

2. Tesla stock surges
   https://example.com/tesla-news-2
   Tesla stock rose by 5%...""",
        "recipient": "me",
        "send": True
    }
    
    result = verify_compose_email_content(
        user_request=user_request,
        compose_email_params=compose_email_params_good,
        step_results=step_results,
        current_step_id="step_2"
    )
    
    print(f"\nVerification Result:")
    print(f"  Verified: {result.get('verified')}")
    print(f"  Reasoning: {result.get('reasoning', '')}")
    
    assert result.get('verified'), "Should verify email contains search results"
    print("\n✅ Case 3b PASSED: Verified search results are present")


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("EMAIL CONTENT VERIFICATION TESTS")
    print("="*80)
    print("\nThese tests verify that the LLM-based email content verifier correctly")
    print("detects when requested content (links, attachments, results) is missing")
    print("from compose_email parameters and suggests corrections.")
    
    try:
        # Check if OpenAI API key is set
        if not os.getenv("OPENAI_API_KEY"):
            print("\n❌ ERROR: OPENAI_API_KEY environment variable not set")
            print("Please set it and try again.")
            return 1
        
        test_trip_planning_with_email()
        test_file_attachment_scenario()
        test_links_in_body_scenario()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED!")
        print("="*80)
        print("\nThe email content verifier successfully:")
        print("  1. Detects missing links in email body")
        print("  2. Detects missing file attachments")
        print("  3. Detects missing search results/content")
        print("  4. Suggests corrections with proper content")
        print("\nThe verification system is working correctly! 🎉")
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

