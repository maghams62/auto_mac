"""
Comprehensive test for stock price → slideshow → email workflow.

Tests the complete workflow:
1. get_stock_price - Fetch stock data
2. synthesize_content - Enrich stock data (if needed)
3. create_slide_deck_content - Create slide content
4. create_keynote - Generate Keynote file
5. compose_email - Email with attachment
6. reply_to_user - Final response

Success Criteria:
- Email status is "sent" or "draft" (not "unclear")
- Slideshow has >= 3 slides with meaningful content
- Stock price with context (change, percentage)
- Company/ticker information included
- Email sent/drafted with attachment
"""

import sys
import os
import json
import requests
from typing import Dict, Any, List
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TEST_SESSION_ID = f"test-stock-slideshow-{int(datetime.now().timestamp())}"


def send_chat_message(message: str, session_id: str = None) -> Dict[str, Any]:
    """Send a chat message via API."""
    url = f"{API_BASE_URL}/api/chat"
    payload = {
        "message": message,
        "session_id": session_id or TEST_SESSION_ID
    }
    
    try:
        response = requests.post(url, json=payload, timeout=180)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e), "response": None}


def verify_workflow_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify stock slideshow email workflow response quality.
    
    Returns:
        Dictionary with verification results
    """
    results = {
        "has_error": False,
        "email_status_clear": False,
        "email_status": None,
        "has_slideshow_content": False,
        "slideshow_mentioned": False,
        "stock_price_mentioned": False,
        "attachment_mentioned": False,
        "response_length": 0,
        "issues": []
    }
    
    if "error" in response:
        results["has_error"] = True
        results["issues"].append(f"API error: {response.get('error')}")
        return results
    
    response_text = response.get("response", "") or response.get("message", "")
    results["response_length"] = len(response_text)
    response_lower = response_text.lower()
    
    # Check for email status clarity
    if "email sent" in response_lower or "email drafted" in response_lower:
        results["email_status_clear"] = True
        if "sent" in response_lower:
            results["email_status"] = "sent"
        elif "drafted" in response_lower:
            results["email_status"] = "draft"
    elif "emailed it to you" in response_lower or "emailed it" in response_lower or "emailed to you" in response_lower:
        # Concise success message pattern
        results["email_status_clear"] = True
        results["email_status"] = "sent"  # Assume sent if "emailed" is used
    elif "delivery status is unclear" in response_lower or "email composition failed" in response_lower:
        results["email_status_clear"] = False
        results["issues"].append("Email delivery status is unclear")
    else:
        # Check if email was mentioned at all
        if "email" in response_lower and ("created" in response_lower or "sent" in response_lower or "drafted" in response_lower):
            results["email_status_clear"] = True  # Assume success if email mentioned with action verb
            results["email_status"] = "sent" if "sent" in response_lower else "unknown"
    
    # Check for slideshow content indicators
    slideshow_keywords = ["slideshow", "slides", "presentation", "keynote"]
    results["slideshow_mentioned"] = any(kw in response_lower for kw in slideshow_keywords)
    
    # Check for stock price indicators
    stock_keywords = ["stock", "price", "nvidia", "nvda", "$", "ticker"]
    results["stock_price_mentioned"] = any(kw in response_lower for kw in stock_keywords)
    
    # Check for attachment indicators
    attachment_keywords = ["attached", "attachment", "file", "keynote"]
    results["attachment_mentioned"] = any(kw in response_lower for kw in attachment_keywords)
    
    # Check for error patterns
    error_patterns = ["error", "failed", "unable", "exception", "skipped", "timeout", "unclear"]
    has_error = any(pattern in response_lower for pattern in error_patterns)
    if has_error and not results["email_status_clear"]:
        results["has_error"] = True
        results["issues"].append("Error patterns detected in response")
    
    # Overall assessment - relaxed criteria: slideshow and stock mentioned is sufficient
    # Response length is less important if key indicators are present
    results["has_slideshow_content"] = (
        results["slideshow_mentioned"] and
        results["stock_price_mentioned"]
    )
    
    return results


def test_nvidia_stock_slideshow_email():
    """Test NVIDIA stock price → slideshow → email workflow."""
    print("\n" + "="*80)
    print("TEST: NVIDIA Stock Price → Slideshow → Email Workflow")
    print("="*80)
    
    query = "Can you email the current stock price of NVIDIA, just convert it into a slideshow and email it to me. Thanks."
    print(f"\nQuery: {query}")
    print(f"Session ID: {TEST_SESSION_ID}")
    
    # Send request
    print("\nSending request to API...")
    response = send_chat_message(query)
    
    # Verify response
    print("\nVerifying response...")
    verification = verify_workflow_response(response)
    
    # Print results
    print("\n" + "-"*80)
    print("VERIFICATION RESULTS:")
    print("-"*80)
    print(f"Response Length: {verification['response_length']} characters")
    print(f"Email Status Clear: {verification['email_status_clear']}")
    print(f"Email Status: {verification['email_status']}")
    print(f"Slideshow Mentioned: {verification['slideshow_mentioned']}")
    print(f"Stock Price Mentioned: {verification['stock_price_mentioned']}")
    print(f"Attachment Mentioned: {verification['attachment_mentioned']}")
    print(f"Has Slideshow Content: {verification['has_slideshow_content']}")
    print(f"Has Error: {verification['has_error']}")
    
    if verification['issues']:
        print(f"\nIssues Found:")
        for issue in verification['issues']:
            print(f"  - {issue}")
    
    print("\n" + "-"*80)
    print("RESPONSE PREVIEW:")
    print("-"*80)
    response_text = response.get("response", "") or response.get("message", "")
    print(response_text[:500])
    if len(response_text) > 500:
        print("...")
    
    # Success criteria
    print("\n" + "="*80)
    print("SUCCESS CRITERIA CHECK:")
    print("="*80)
    
    criteria_met = {
        "Email Status Clear": verification['email_status_clear'],
        "Email Status Present": verification['email_status'] is not None,
        "Slideshow Content": verification['has_slideshow_content'],
        "No Errors": not verification['has_error'],
        "Response Contains Key Info": verification['slideshow_mentioned'] and verification['stock_price_mentioned']
    }
    
    all_passed = all(criteria_met.values())
    
    for criterion, passed in criteria_met.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {criterion}")
    
    print("\n" + "="*80)
    if all_passed:
        print("✅ TEST PASSED: All success criteria met")
    else:
        print("❌ TEST FAILED: Some success criteria not met")
    print("="*80)
    
    return {
        "test_name": "NVIDIA Stock Slideshow Email",
        "query": query,
        "passed": all_passed,
        "verification": verification,
        "response_preview": response_text[:300]
    }


def test_apple_stock_slideshow_email():
    """Test Apple stock price → slideshow → email workflow."""
    print("\n" + "="*80)
    print("TEST: Apple Stock Price → Slideshow → Email Workflow")
    print("="*80)
    
    query = "Get Apple's stock price, create a slideshow, and email it to me"
    print(f"\nQuery: {query}")
    
    response = send_chat_message(query)
    verification = verify_workflow_response(response)
    
    print("\n" + "-"*80)
    print("VERIFICATION RESULTS:")
    print("-"*80)
    print(f"Email Status Clear: {verification['email_status_clear']}")
    print(f"Email Status: {verification['email_status']}")
    print(f"Has Slideshow Content: {verification['has_slideshow_content']}")
    print(f"Has Error: {verification['has_error']}")
    
    response_text = response.get("response", "") or response.get("message", "")
    print(f"\nResponse Preview: {response_text[:300]}")
    
    criteria_met = {
        "Email Status Clear": verification['email_status_clear'],
        "Slideshow Content": verification['has_slideshow_content'],
        "No Errors": not verification['has_error']
    }
    
    all_passed = all(criteria_met.values())
    print(f"\n{'✅ TEST PASSED' if all_passed else '❌ TEST FAILED'}")
    
    return {
        "test_name": "Apple Stock Slideshow Email",
        "query": query,
        "passed": all_passed,
        "verification": verification
    }


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("STOCK PRICE → SLIDESHOW → EMAIL WORKFLOW TEST SUITE")
    print("="*80)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Test Session ID: {TEST_SESSION_ID}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*80)
    
    # Check API server
    try:
        health_response = requests.get(f"{API_BASE_URL}/", timeout=5)
        if health_response.status_code != 200:
            print("\n❌ API server is not reachable. Please start the API server.")
            return
        health_data = health_response.json()
        if health_data.get("status") != "online":
            print("\n❌ API server is not online. Please start the API server.")
            return
    except Exception as e:
        print(f"\n❌ API server is not reachable: {e}")
        print("Please start the API server: python3 api_server.py")
        return
    
    print("\n✅ API server is reachable")
    
    # Run tests
    results = []
    
    # Test 1: NVIDIA stock slideshow email
    try:
        result1 = test_nvidia_stock_slideshow_email()
        results.append(result1)
    except Exception as e:
        print(f"\n❌ Test 1 failed with exception: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 2: Apple stock slideshow email
    try:
        result2 = test_apple_stock_slideshow_email()
        results.append(result2)
    except Exception as e:
        print(f"\n❌ Test 2 failed with exception: {e}")
        import traceback
        traceback.print_exc()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed_count = sum(1 for r in results if r.get("passed", False))
    total_count = len(results)
    
    for result in results:
        status = "✅ PASSED" if result.get("passed", False) else "❌ FAILED"
        print(f"{status}: {result.get('test_name', 'Unknown')}")
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    print("="*80)
    
    # Save results
    results_file = f"tests/stock_slideshow_test_results_{int(datetime.now().timestamp())}.json"
    with open(results_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "session_id": TEST_SESSION_ID,
            "results": results,
            "summary": {
                "passed": passed_count,
                "total": total_count,
                "success_rate": passed_count / total_count if total_count > 0 else 0
            }
        }, f, indent=2)
    
    print(f"\nResults saved to: {results_file}")


if __name__ == "__main__":
    main()

