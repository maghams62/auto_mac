#!/usr/bin/env python3
"""
Test script to verify /clear command handling
"""
import asyncio
import json
import websockets
import sys

async def test_clear_command():
    """Test /clear command via WebSocket"""
    uri = "ws://localhost:8000/ws/chat"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket")
            
            # Wait for initial system message
            initial_msg = await websocket.recv()
            print(f"Initial message: {json.loads(initial_msg)}")
            
            # Send /clear command
            clear_msg = json.dumps({"message": "/clear"})
            print(f"\nSending: {clear_msg}")
            await websocket.send(clear_msg)
            
            # Wait for response
            response = await websocket.recv()
            data = json.loads(response)
            print(f"\nResponse: {json.dumps(data, indent=2)}")
            
            # Check if it's a clear message
            if data.get("type") == "clear":
                print("\n✅ SUCCESS: /clear command handled correctly!")
                print(f"   Message: {data.get('message')}")
                return True
            else:
                print(f"\n❌ FAILED: Expected 'clear' type, got '{data.get('type')}'")
                print(f"   Full response: {data}")
                return False
                
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_clear_command())
    sys.exit(0 if success else 1)

