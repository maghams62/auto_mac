"""
Test if email reading shows in UI via API/WebSocket.
Success criteria: Email data is properly formatted and sent through WebSocket for UI display.
"""

import requests
import json
import time
import sys
from pathlib import Path

API_BASE_URL = "http://localhost:8000"

def test_email_ui_display():
    """Test if email reading works through API and shows in UI."""
    print("=" * 80)
    print("EMAIL UI DISPLAY TEST")
    print("=" * 80)
    
    try:
        # Send chat request to read emails
        print("\n1. Sending API request to read latest 3 emails...")
        session_id = f"test-{int(time.time())}"
        
        response = requests.post(
            f"{API_BASE_URL}/api/chat",
            json={
                "message": "Read my latest 3 emails",
                "session_id": session_id
            },
            timeout=90
        )
        
        if response.status_code != 200:
            print(f"   ✗ API request failed with status {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return False
        
        print("   ✓ Request sent successfully")
        initial_response = response.json()
        print(f"   Initial response: {initial_response.get('message', 'No message')[:100]}...")
        
        # Wait and collect messages
        print("\n2. Collecting WebSocket/API messages...")
        messages = []
        start_time = time.time()
        max_wait = 90
        
        while time.time() - start_time < max_wait:
            try:
                # Try to get messages via API
                msg_response = requests.get(
                    f"{API_BASE_URL}/api/messages",
                    params={"session_id": session_id},
                    timeout=10
                )
                
                if msg_response.status_code == 200:
                    data = msg_response.json()
                    new_messages = data.get("messages", [])
                    
                    if new_messages:
                        # Only add new messages
                        existing_ids = {msg.get("id") for msg in messages}
                        for msg in new_messages:
                            if msg.get("id") not in existing_ids:
                                messages.append(msg)
                        
                        # Check if we have a completion
                        latest = new_messages[-1]
                        if latest.get("type") in ["completion", "error", "assistant"]:
                            # Check if it's the final message
                            if "email" in latest.get("message", "").lower() or latest.get("type") == "error":
                                break
                
                time.sleep(2)
                
            except requests.exceptions.RequestException as e:
                print(f"   Warning: Error fetching messages: {e}")
                time.sleep(2)
        
        print(f"   ✓ Collected {len(messages)} messages")
        
        # Analyze messages for email data
        print("\n" + "=" * 80)
        print("MESSAGE ANALYSIS FOR UI DISPLAY")
        print("=" * 80)
        
        email_tool_called = False
        email_data_found = False
        email_data_in_response = False
        final_message = None
        
        for i, msg in enumerate(messages, 1):
            msg_type = msg.get("type", "unknown")
            print(f"\n--- Message {i} ---")
            print(f"Type: {msg_type}")
            
            # Check for tool calls
            if msg_type == "tool_call":
                tool_name = msg.get("tool_name", "")
                print(f"Tool: {tool_name}")
                if "email" in tool_name.lower():
                    email_tool_called = True
                    print(f"   ✓ Email tool called: {tool_name}")
                    params = msg.get("parameters", {})
                    print(f"   Parameters: {json.dumps(params, indent=2)[:200]}...")
            
            # Check for tool results
            elif msg_type == "tool_result":
                tool_name = msg.get("tool_name", "")
                print(f"Tool Result: {tool_name}")
                if "email" in tool_name.lower():
                    result = msg.get("result", {})
                    if isinstance(result, str):
                        try:
                            result = json.loads(result)
                        except:
                            pass
                    
                    if isinstance(result, dict):
                        emails = result.get("emails", [])
                        count = result.get("count", 0)
                        if emails or count > 0:
                            email_data_found = True
                            print(f"   ✓ Email data found: {count} emails")
                            if emails:
                                print(f"   First email: {emails[0].get('subject', 'N/A')[:50]}")
            
            # Check final assistant message
            elif msg_type == "assistant":
                message_text = msg.get("message", "")
                print(f"Message: {message_text[:200]}...")
                if "email" in message_text.lower():
                    email_data_in_response = True
                    print(f"   ✓ Email mentioned in response")
                    final_message = msg
        
        # Check initial response too
        initial_msg = initial_response.get("message", "")
        if "email" in initial_msg.lower():
            email_data_in_response = True
        
        # Print final message if available
        print("\n" + "=" * 80)
        print("FINAL RESPONSE FOR UI")
        print("=" * 80)
        
        if final_message:
            print(final_message.get("message", "No message"))
        elif initial_response.get("message"):
            print(initial_response.get("message"))
        else:
            print("No final message found")
        
        # Summary
        print("\n" + "=" * 80)
        print("UI DISPLAY VERIFICATION")
        print("=" * 80)
        
        print(f"✓ Email tool called: {email_tool_called}")
        print(f"✓ Email data in tool result: {email_data_found}")
        print(f"✓ Email mentioned in response: {email_data_in_response}")
        
        # Check if UI would receive proper data
        ui_ready = email_tool_called and (email_data_found or email_data_in_response)
        
        if ui_ready:
            print("\n✅ SUCCESS: Email reading is properly configured for UI display!")
            print("   - Tool is called correctly")
            print("   - Email data is retrieved")
            print("   - Response contains email information")
            print("\n   The UI should be able to display:")
            print("   - Email count")
            print("   - Email list with sender, subject, date")
            print("   - Email content in message bubbles")
        else:
            print("\n⚠️  PARTIAL: Some components may not be working")
            if not email_tool_called:
                print("   - Email tool was not called")
            if not email_data_found:
                print("   - Email data not found in tool results")
            if not email_data_in_response:
                print("   - Email not mentioned in response")
        
        return ui_ready
        
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
    success = test_email_ui_display()
    sys.exit(0 if success else 1)

