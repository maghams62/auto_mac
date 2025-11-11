"""
Test the UI with a simple web search request.
"""
import asyncio
import websockets
import json

async def test_web_search():
    uri = "ws://localhost:8000/ws/chat"

    print("🔌 Connecting to WebSocket server...")

    async with websockets.connect(uri) as websocket:
        print("✅ Connected!")

        # Wait for welcome message
        welcome = await websocket.recv()
        print(f"📨 {json.loads(welcome)['message']}\n")

        # Test with a web search (doesn't require document indexing)
        test_message = "Search Google for Python programming tutorials"
        print(f"📤 Sending: '{test_message}'")

        await websocket.send(json.dumps({"message": test_message}))

        # Receive responses
        print("\n📥 Responses:\n")

        response_count = 0
        while response_count < 10:
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                data = json.loads(response)

                msg_type = data.get('type', 'unknown')
                message = data.get('message', '')
                status = data.get('status', '')

                if msg_type == 'status':
                    print(f"⏳ Status: {status}")
                elif msg_type == 'response':
                    print(f"\n✅ Agent Response:")
                    print(f"{message}\n")
                    if status == 'completed':
                        print("🎉 Task completed successfully!")
                        break
                elif msg_type == 'error':
                    print(f"\n⚠️  Error: {message}")
                    break

                response_count += 1

            except asyncio.TimeoutError:
                print("⏱️  Timeout - task may still be running")
                break

        print("\n✅ Test completed!")

if __name__ == "__main__":
    print("="*60)
    print("Testing Web Search via WebSocket")
    print("="*60 + "\n")

    asyncio.run(test_web_search())
