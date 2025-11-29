#!/usr/bin/env python3
"""
Simple WebSocket test with better timeout handling
"""

import asyncio
import json
import websockets
from websockets.exceptions import ConnectionClosed
import signal
import sys

TIMEOUT = 120  # Allow time for agent execution (no server-side timeout anymore)

def timeout_handler(signum, frame):
    print("\n⚠️  Test timed out!")
    sys.exit(1)

async def test_websocket():
    print("=" * 80)
    print("SIMPLE WEBSOCKET EMAIL TEST")
    print("=" * 80)
    
    try:
        # Step 1: Check connection
        print("\n1. Attempting to connect to WebSocket...")
        try:
            websocket = await asyncio.wait_for(
                websockets.connect("ws://localhost:8000/ws/chat"),
                timeout=5
            )
            print("   ✓ Connected successfully")
        except asyncio.TimeoutError:
            print("   ✗ Connection timed out after 5 seconds")
            print("   Is the API server running on port 8000?")
            return False
        except Exception as e:
            print(f"   ✗ Connection failed: {e}")
            return False
        
        async with websocket:
            # Step 2: Send request
            print("\n2. Sending email reading request...")
            request = {
                "message": "Read my latest 2 emails",
                "conversation_id": "test-email-ws-simple",
                "stream": True
            }
            await websocket.send(json.dumps(request))
            print("   ✓ Request sent")
            
            # Step 3: Collect messages with timeout
            print(f"\n3. Collecting messages ({TIMEOUT} second timeout)...")
            messages = []
            start_time = asyncio.get_event_loop().time()
            
            try:
                while True:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    remaining = TIMEOUT - elapsed
                    
                    if remaining <= 0:
                        print(f"\n   ⚠️  Timeout reached after {TIMEOUT} seconds")
                        break
                    
                    try:
                        msg = await asyncio.wait_for(websocket.recv(), timeout=min(5, remaining))
                        msg_data = json.loads(msg)
                        messages.append(msg_data)
                        
                        msg_type = msg_data.get("type", "unknown")
                        print(f"   [{int(elapsed)}s] Received: {msg_type}")
                        
                        # Stop on response message (final response from API server)
                        if msg_type == "response":
                            print("   ✓ Final response received")
                            break
                        
                        # Also stop on error or completion
                        if msg_type in ["error", "completion"]:
                            print(f"   ✓ Final message: {msg_type}")
                            break
                            
                    except asyncio.TimeoutError:
                        # No message in last 5 seconds
                        print(f"   [{int(elapsed)}s] Still waiting...")
                        continue
                        
            except ConnectionClosed:
                print("   ✓ Connection closed by server")
            
            # Step 4: Report results
            print(f"\n4. Results:")
            print(f"   Total messages: {len(messages)}")
            print(f"   Message types: {[m.get('type') for m in messages]}")
            
            # Find response message
            response_msg = None
            for msg in messages:
                if msg.get("type") == "response":
                    response_msg = msg
                    break
            
            if response_msg:
                msg_text = response_msg.get("message", "")
                print(f"\n   ✓ Response message length: {len(msg_text)} chars")
                print(f"   Preview: {msg_text[:200]}...")
                
                # Check for email content - should NOT be a timeout message
                if "timed out" in msg_text.lower() or "timeout" in msg_text.lower():
                    print(f"   ✗ Response is a timeout message (not expected after fix)")
                    print(f"   Message: {msg_text[:200]}")
                    return False
                
                # Should contain actual email information
                if any(kw in msg_text.lower() for kw in ["email", "sender", "subject", "retrieved", "latest"]):
                    print(f"   ✓ Response contains email information")
                    return True
                else:
                    print(f"   ⚠️  Response doesn't mention emails")
                    print(f"   Message preview: {msg_text[:200]}")
                    return False
            else:
                print(f"\n   ✗ No response message received")
                return False
                
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Set up timeout signal
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(180)  # Kill the script after 180 seconds total (generous for agentic tasks)
    
    try:
        success = asyncio.run(test_websocket())
        signal.alarm(0)  # Cancel the alarm
        
        print("\n" + "=" * 80)
        if success:
            print("✅ TEST PASSED")
            sys.exit(0)
        else:
            print("❌ TEST FAILED")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)

