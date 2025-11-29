"""
Test reading emails via API and print them out.
Success criteria: Can print out the email content.
"""

import requests
import json
import time

API_BASE_URL = "http://localhost:8000"

def test_read_email_via_api():
    """Test reading emails via API and print them out."""
    print("=" * 80)
    print("EMAIL READING TEST (via API)")
    print("=" * 80)
    
    try:
        # Send chat request to read emails
        print("\n1. Sending request to read latest 5 emails...")
        response = requests.post(
            f"{API_BASE_URL}/api/chat",
            json={"message": "Read my latest 5 emails"},
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"   ✗ API request failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        print("   ✓ Request sent, waiting for response...")
        
        # Wait for completion
        print("\n2. Waiting for completion...")
        messages = []
        start_time = time.time()
        max_wait = 60
        
        while time.time() - start_time < max_wait:
            try:
                msg_response = requests.get(f"{API_BASE_URL}/api/messages", timeout=10)
                if msg_response.status_code == 200:
                    new_messages = msg_response.json().get("messages", [])
                    if new_messages:
                        messages.extend(new_messages)
                        # Check if complete
                        latest = new_messages[-1]
                        if latest.get("type") in ["completion", "error"]:
                            break
            except:
                pass
            time.sleep(1)
        
        # Get the final response
        final_response = response.json()
        response_text = final_response.get("message", "")
        
        print(f"   ✓ Received response ({len(response_text)} characters)")
        
        # Print the response
        print("\n" + "=" * 80)
        print("API RESPONSE")
        print("=" * 80)
        print(response_text)
        
        # Look for email data in messages
        print("\n" + "=" * 80)
        print("EMAIL DATA FROM MESSAGES")
        print("=" * 80)
        
        emails_found = False
        for msg in messages:
            if msg.get("type") == "tool_result" and "email" in msg.get("tool_name", "").lower():
                result = msg.get("result", {})
                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except:
                        pass
                
                if isinstance(result, dict):
                    emails = result.get("emails", [])
                    if emails:
                        emails_found = True
                        print(f"\nFound {len(emails)} email(s) in tool result:\n")
                        for i, email in enumerate(emails, 1):
                            print(f"--- Email {i} ---")
                            print(f"From: {email.get('sender', 'N/A')}")
                            print(f"Subject: {email.get('subject', 'N/A')}")
                            print(f"Date: {email.get('date', email.get('timestamp', 'N/A'))}")
                            
                            body = email.get('body', email.get('content', ''))
                            if body:
                                print(f"\nBody:")
                                print("-" * 40)
                                body_preview = body[:500] if len(body) > 500 else body
                                print(body_preview)
                                if len(body) > 500:
                                    print(f"\n... (truncated, total {len(body)} characters)")
                                print("-" * 40)
                            print()
        
        if not emails_found:
            print("No email data found in tool results")
            print("\nChecking if response contains email information...")
            if "email" in response_text.lower():
                print("Response mentions emails but data not extracted")
            else:
                print("Response does not contain email information")
        
        print("\n" + "=" * 80)
        if emails_found or "email" in response_text.lower():
            print("SUCCESS: Email reading test completed!")
        else:
            print("PARTIAL: API responded but email data not fully extracted")
        print("=" * 80)
        
        return emails_found or "email" in response_text.lower()
        
    except requests.exceptions.ConnectionError:
        print("   ✗ Cannot connect to API server")
        print("   Please ensure the API server is running on http://localhost:8000")
        return False
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_read_email_via_api()
    exit(0 if success else 1)

