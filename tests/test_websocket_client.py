"""
Simple WebSocket client to test the UI backend integration with agents.
"""
import asyncio
import websockets
import json
import sys

async def test_websocket():
    uri = "ws://localhost:8000/ws/chat"

    print("🔌 Connecting to WebSocket server...")

    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected successfully!")

            # Wait for welcome message
            welcome = await websocket.recv()
            welcome_data = json.loads(welcome)
            print(f"\n📨 Server says: {welcome_data['message']}")

            # Test message 1: Simple request
            test_message = "Hello, can you help me?"
            print(f"\n📤 Sending test message: '{test_message}'")

            await websocket.send(json.dumps({"message": test_message}))

            # Receive responses
            print("\n📥 Receiving responses...")

            response_count = 0
            while response_count < 5:  # Wait for up to 5 messages
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    response_data = json.loads(response)

                    msg_type = response_data.get('type', 'unknown')
                    message = response_data.get('message', '')
                    status = response_data.get('status', '')

                    print(f"\n[{msg_type.upper()}] {message}")
                    if status:
                        print(f"  Status: {status}")

                    response_count += 1

                    # If we got a completed response, we're done
                    if status == "completed" or msg_type == "response":
                        print("\n✅ Test completed successfully!")
                        break

                except asyncio.TimeoutError:
                    print("\n⏱️  Timeout waiting for response")
                    break
                except Exception as e:
                    print(f"\n❌ Error receiving message: {e}")
                    break

    except Exception as e:
        print(f"\n❌ Connection error: {e}")
        print("\nMake sure the backend server is running:")
        print("  python api_server.py")
        sys.exit(1)

if __name__ == "__main__":
    print("="*60)
    print("WebSocket Client Test - Agent Integration")
    print("="*60)

    asyncio.run(test_websocket())

    print("\n" + "="*60)
    print("Test completed!")
    print("="*60)
