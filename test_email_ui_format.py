"""
Test email message format for UI compatibility.

Verifies that messages received through WebSocket are properly formatted
for display in UI components (MessageBubble, FileList, etc.).
"""

import asyncio
import json
import sys
from typing import Dict, Any, List, Optional
import websockets

WS_URL = "ws://localhost:8000/ws/chat"
TIMEOUT = 120


async def test_email_ui_format():
    """Test that email messages are properly formatted for UI display."""
    print("=" * 80)
    print("EMAIL UI FORMAT VERIFICATION")
    print("=" * 80)
    
    try:
        async with websockets.connect(WS_URL) as websocket:
            # Receive welcome message
            welcome_msg = await asyncio.wait_for(websocket.recv(), timeout=10)
            
            # Send email read request
            request_message = {
                "type": "user",
                "message": "Read my latest 3 emails"
            }
            await websocket.send(json.dumps(request_message))
            
            # Collect messages
            messages: List[Dict[str, Any]] = []
            start_time = asyncio.get_event_loop().time()
            
            while (asyncio.get_event_loop().time() - start_time) < TIMEOUT:
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=5)
                    msg_data = json.loads(msg)
                    messages.append(msg_data)
                    
                    if msg_data.get("type") in ["error", "completion"]:
                        break
                    
                    # Check if we have assistant response
                    if msg_data.get("type") == "assistant":
                        await asyncio.sleep(2)  # Wait for any final messages
                        break
                        
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    break
            
            # Analyze UI format compatibility
            print("\n1. Analyzing message format for UI compatibility...")
            
            assistant_messages = [m for m in messages if m.get("type") == "assistant"]
            tool_result_messages = [m for m in messages if m.get("type") == "tool_result" and "email" in m.get("tool_name", "").lower()]
            
            if not assistant_messages:
                print("   ✗ No assistant messages found")
                return False
            
            assistant_msg = assistant_messages[-1]  # Get last assistant message
            
            print("\n2. Checking MessageBubble component compatibility...")
            
            # Required fields for MessageBubble
            required_fields = ["type", "message", "timestamp"]
            missing_fields = []
            
            for field in required_fields:
                if field not in assistant_msg:
                    missing_fields.append(field)
                else:
                    print(f"   ✓ Has {field} field")
            
            if missing_fields:
                print(f"   ✗ Missing required fields: {missing_fields}")
                return False
            
            # Check message type
            msg_type = assistant_msg.get("type")
            if msg_type != "assistant":
                print(f"   ✗ Unexpected message type: {msg_type} (expected 'assistant')")
                return False
            print(f"   ✓ Message type is 'assistant'")
            
            # Check message content
            message_text = assistant_msg.get("message", "")
            if not message_text:
                print("   ✗ Message text is empty")
                return False
            print(f"   ✓ Message text present ({len(message_text)} chars)")
            
            # Check if email information is in message
            email_keywords = ["email", "sender", "subject", "from"]
            has_email_info = any(keyword in message_text.lower() for keyword in email_keywords)
            if has_email_info:
                print("   ✓ Message contains email information")
            else:
                print("   ⚠️  Message may not contain email information")
            
            # Check timestamp format
            timestamp = assistant_msg.get("timestamp", "")
            if timestamp:
                print(f"   ✓ Timestamp present: {timestamp[:20]}...")
            else:
                print("   ⚠️  Timestamp missing")
            
            # Check optional fields
            print("\n3. Checking optional UI fields...")
            
            optional_fields = {
                "files": "FileList component",
                "completion_event": "TaskCompletionCard",
                "plan": "Plan display",
                "status": "Status indicator"
            }
            
            for field, component in optional_fields.items():
                if field in assistant_msg:
                    print(f"   ✓ Has {field} field (for {component})")
                else:
                    print(f"   - No {field} field (optional for {component})")
            
            # Check tool result for email data structure
            print("\n4. Verifying email data structure from tool result...")
            
            if tool_result_messages:
                tool_result = tool_result_messages[0]
                result = tool_result.get("result", {})
                
                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except:
                        result = {}
                
                if isinstance(result, dict):
                    emails = result.get("emails", [])
                    if emails:
                        first_email = emails[0]
                        print(f"   ✓ Email data available ({len(emails)} emails)")
                        
                        # Check email structure
                        email_fields = ["sender", "subject", "date", "content"]
                        for field in email_fields:
                            if field in first_email:
                                print(f"   ✓ Email has {field} field")
                            else:
                                print(f"   ⚠️  Email missing {field} field")
                    else:
                        print("   ⚠️  No emails in tool result")
                else:
                    print("   ⚠️  Tool result is not a dictionary")
            else:
                print("   ⚠️  No tool result message found")
            
            # UI Component Compatibility Summary
            print("\n" + "=" * 80)
            print("UI COMPONENT COMPATIBILITY SUMMARY")
            print("=" * 80)
            
            compatibility = {
                "MessageBubble": all(field in assistant_msg for field in required_fields),
                "Email Display": has_email_info,
                "Timestamp Display": bool(timestamp),
                "Email Data Structure": bool(tool_result_messages and emails if tool_result_messages else False)
            }
            
            all_compatible = all(compatibility.values())
            
            for component, is_compatible in compatibility.items():
                status = "✓" if is_compatible else "✗"
                print(f"{status} {component}: {'Compatible' if is_compatible else 'Not compatible'}")
            
            print("\n" + "=" * 80)
            if all_compatible:
                print("✅ SUCCESS: Message format is fully compatible with UI components!")
                print("\nThe message can be displayed in:")
                print("  - MessageBubble component (main message display)")
                print("  - Email list rendering (if emails are formatted as list)")
                print("  - Summary canvas (if emails are summarized)")
            else:
                print("⚠️  PARTIAL: Some compatibility issues found")
                print("Message may not display correctly in all UI components")
            
            return all_compatible
            
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_email_ui_format())
    sys.exit(0 if result else 1)

