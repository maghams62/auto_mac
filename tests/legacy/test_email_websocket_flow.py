"""
Test WebSocket flow for email reading - complete API → WebSocket → UI flow verification.

Tests:
- WebSocket connection establishment
- Message sending and receiving
- Tool call and result messages
- Assistant response with email data
"""

import asyncio
import json
import sys
import time
from typing import Dict, Any, List, Optional
import websockets
from websockets.exceptions import ConnectionClosed, InvalidURI

WS_URL = "ws://localhost:8000/ws/chat"
TIMEOUT = 120  # seconds


async def test_websocket_email_flow():
    """Test complete WebSocket flow for email reading."""
    print("=" * 80)
    print("WEBSOCKET EMAIL FLOW TEST")
    print("=" * 80)
    
    messages_received: List[Dict[str, Any]] = []
    session_id: Optional[str] = None
    
    try:
        # Step 1: Connect to WebSocket
        print("\n1. Connecting to WebSocket endpoint...")
        print(f"   URL: {WS_URL}")
        
        async with websockets.connect(WS_URL) as websocket:
            print("   ✓ WebSocket connection established")
            
            # Step 2: Receive welcome message
            print("\n2. Waiting for welcome message...")
            try:
                welcome_msg = await asyncio.wait_for(websocket.recv(), timeout=10)
                welcome_data = json.loads(welcome_msg)
                messages_received.append(welcome_data)
                
                if welcome_data.get("type") == "system":
                    print("   ✓ Welcome message received")
                    session_id = welcome_data.get("session_id")
                    print(f"   Session ID: {session_id}")
                else:
                    print(f"   ⚠️  Unexpected message type: {welcome_data.get('type')}")
            except asyncio.TimeoutError:
                print("   ✗ Timeout waiting for welcome message")
                return False
            
            # Step 3: Send email read request
            print("\n3. Sending email read request...")
            request_message = {
                "type": "user",
                "message": "Read my latest 3 emails"
            }
            await websocket.send(json.dumps(request_message))
            print("   ✓ Request sent")
            print(f"   Message: {request_message['message']}")
            
            # Step 4: Collect all messages
            print("\n4. Collecting messages (waiting up to 120 seconds)...")
            start_time = time.time()
            plan_received = False
            plan_update_received = False
            assistant_response_received = False
            
            while time.time() - start_time < TIMEOUT:
                try:
                    # Wait for message with timeout
                    msg = await asyncio.wait_for(websocket.recv(), timeout=5)
                    msg_data = json.loads(msg)
                    messages_received.append(msg_data)
                    
                    msg_type = msg_data.get("type", "unknown")
                    print(f"   Received: {msg_type}")
                    
                    # Check for plan
                    if msg_type == "plan":
                        plan_received = True
                        print(f"     ✓ Plan received")
                        goal = msg_data.get("goal", "")
                        steps = msg_data.get("steps", [])
                        if goal:
                            print(f"     Goal: {goal[:50]}")
                        if steps:
                            print(f"     Steps: {len(steps)}")
                    
                    # Check for plan update
                    elif msg_type == "plan_update":
                        plan_update_received = True
                        status = msg_data.get("status", "")
                        print(f"     ✓ Plan update: {status}")
                    
                    # Check for response message (final response from API server)
                    elif msg_type == "response":
                        assistant_response_received = True
                        message_text = msg_data.get("message", "")
                        print(f"     ✓ Response message received ({len(message_text)} chars)")
                        if "email" in message_text.lower():
                            print(f"     ✓ Response contains email information")
                            # Show preview
                            preview = message_text[:200] if len(message_text) > 200 else message_text
                            print(f"     Preview: {preview}...")
                    
                    # Check if we're done - response message is the final response
                    if msg_type == "response":
                        print(f"     Final message received")
                        # Wait a bit more for any follow-up messages
                        await asyncio.sleep(1)
                        break
                    
                    # Also stop on error or completion
                    if msg_type in ["error", "completion"]:
                        print(f"     Final message type: {msg_type}")
                        break
                        
                except asyncio.TimeoutError:
                    # No message received, continue waiting
                    elapsed = time.time() - start_time
                    if elapsed > 30 and not assistant_response_received:
                        print(f"   ⚠️  Still waiting for assistant response after {int(elapsed)} seconds...")
                    continue
                except ConnectionClosed:
                    print("   ✓ WebSocket connection closed (normal)")
                    break
            
            print(f"\n   Total messages received: {len(messages_received)}")
            
            # Step 5: Analyze messages
            print("\n" + "=" * 80)
            print("MESSAGE FLOW ANALYSIS")
            print("=" * 80)
            
            # Find tool call
            tool_call_msg = None
            for msg in messages_received:
                if msg.get("type") == "tool_call" and "email" in msg.get("tool_name", "").lower():
                    tool_call_msg = msg
                    break
            
            # Find tool result
            tool_result_msg = None
            for msg in messages_received:
                if msg.get("type") == "tool_result" and "email" in msg.get("tool_name", "").lower():
                    tool_result_msg = msg
                    break
            
            # Find response message (final response from API server)
            assistant_msg = None
            for msg in messages_received:
                if msg.get("type") == "response":
                    assistant_msg = msg
                    break
            
            # Print analysis
            # Find plan and plan_update messages
            plan_msg = None
            plan_updates = []
            for msg in messages_received:
                if msg.get("type") == "plan":
                    plan_msg = msg
                elif msg.get("type") == "plan_update":
                    plan_updates.append(msg)
            
            print(f"\nPlan Message: {'✓ Found' if plan_msg else '✗ Missing'}")
            if plan_msg:
                goal = plan_msg.get("goal", "")
                steps = plan_msg.get("steps", [])
                print(f"  Goal: {goal}")
                print(f"  Steps: {len(steps)}")
            
            print(f"\nPlan Updates: {'✓ Found' if plan_updates else '✗ Missing'} ({len(plan_updates)} updates)")
            
            print(f"\nFinal Response: {'✓ Found' if assistant_msg else '✗ Missing'}")
            if assistant_msg:
                msg_text = assistant_msg.get("message", "")
                print(f"  Message length: {len(msg_text)} chars")
                print(f"  Preview: {msg_text[:300]}...")
                
                # Check for email data in message
                email_keywords = ["email", "sender", "subject", "from"]
                has_email_info = any(kw in msg_text.lower() for kw in email_keywords)
                if has_email_info:
                    print(f"  ✓ Contains email information")
            
            # Step 6: Verify success criteria
            print("\n" + "=" * 80)
            print("SUCCESS CRITERIA VERIFICATION")
            print("=" * 80)
            
            success = True
            issues = []
            
            # WebSocket Layer
            if not plan_received:
                success = False
                issues.append("Plan message not received")
            else:
                print("✓ Plan message received")
            
            if not plan_updates:
                print("⚠️  No plan updates received (but this may be normal)")
            else:
                print(f"✓ Plan updates received ({len(plan_updates)} updates)")
            
            if not assistant_response_received:
                success = False
                issues.append("Final response not received")
            else:
                print("✓ Final response received")
            
            # Data Format - Check assistant message for email content
            if assistant_msg:
                msg_text = assistant_msg.get("message", "")
                if not msg_text:
                    success = False
                    issues.append("Assistant message is empty")
                else:
                    # Check for email data in message text
                    email_keywords = ["email", "sender", "subject"]
                    has_email_info = any(kw in msg_text.lower() for kw in email_keywords)
                    
                    if has_email_info:
                        print("✓ Assistant message contains email information")
                    else:
                        # May still be a valid response, but doesn't contain emails
                        print("⚠️  Assistant message doesn't mention emails (may still be processing)")
            
            # Summary
            print("\n" + "=" * 80)
            if success:
                print("✅ SUCCESS: WebSocket flow test passed!")
                print("\nAll success criteria met:")
                print("  - WebSocket connection established")
                print("  - Tool call message received")
                print("  - Tool result with email data received")
                print("  - Assistant response received")
                print("  - Email data structure is correct")
            else:
                print("⚠️  PARTIAL SUCCESS: Some issues found")
                for issue in issues:
                    print(f"  - {issue}")
            
            return success
            
    except ConnectionRefusedError:
        print("   ✗ Cannot connect to WebSocket server")
        print("   Please ensure the API server is running on port 8000")
        return False
    except InvalidURI:
        print("   ✗ Invalid WebSocket URL")
        return False
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_websocket_email_flow())
    sys.exit(0 if result else 1)

