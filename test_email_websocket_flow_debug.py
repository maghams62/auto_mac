"""
Debug version to see all messages received.
"""

import asyncio
import json
import sys
import time
import websockets

WS_URL = "ws://localhost:8000/ws/chat"
TIMEOUT = 120


async def test_websocket_debug():
    """Debug test to see all messages."""
    print("=" * 80)
    print("WEBSOCKET DEBUG - ALL MESSAGES")
    print("=" * 80)
    
    try:
        async with websockets.connect(WS_URL) as websocket:
            # Receive welcome
            welcome = await asyncio.wait_for(websocket.recv(), timeout=10)
            welcome_data = json.loads(welcome)
            print(f"\nWelcome: {json.dumps(welcome_data, indent=2)}")
            
            # Send request
            request = {"type": "user", "message": "Read my latest 3 emails"}
            await websocket.send(json.dumps(request))
            print(f"\nSent: {json.dumps(request, indent=2)}")
            
            # Collect all messages
            messages = []
            start = time.time()
            
            print("\nReceiving messages...")
            while time.time() - start < TIMEOUT:
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=5)
                    data = json.loads(msg)
                    messages.append(data)
                    
                    msg_type = data.get("type", "unknown")
                    print(f"\n--- Message {len(messages)}: {msg_type} ---")
                    print(json.dumps(data, indent=2)[:500])
                    
                    if msg_type in ["error", "completion"]:
                        break
                    if msg_type == "assistant" and len(messages) > 5:
                        await asyncio.sleep(3)
                        break
                        
                except asyncio.TimeoutError:
                    if time.time() - start > 60:
                        print("\nTimeout after 60 seconds")
                        break
                    continue
                except Exception as e:
                    print(f"\nError: {e}")
                    break
            
            print(f"\n\nTotal messages: {len(messages)}")
            print("\nMessage types received:")
            types = {}
            for msg in messages:
                msg_type = msg.get("type", "unknown")
                types[msg_type] = types.get(msg_type, 0) + 1
            for msg_type, count in types.items():
                print(f"  {msg_type}: {count}")
            
            # Look for email-related messages
            print("\nEmail-related messages:")
            for i, msg in enumerate(messages):
                msg_str = json.dumps(msg).lower()
                if "email" in msg_str or "read_latest" in msg_str:
                    print(f"\nMessage {i+1}:")
                    print(json.dumps(msg, indent=2))
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_websocket_debug())

