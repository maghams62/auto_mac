"""
Test the UI with a real agent request - document search.
"""
import asyncio
import websockets
import json

async def test_document_search():
    uri = "ws://localhost:8000/ws/chat"

    print("🔌 Connecting to WebSocket server...")

    async with websockets.connect(uri) as websocket:
        print("✅ Connected!")

        # Wait for welcome message
        welcome = await websocket.recv()
        print(f"📨 {json.loads(welcome)['message']}\n")

        # Test with a real document search request
        test_message = "Search my documents for Tesla"
        print(f"📤 Sending: '{test_message}'")

        await websocket.send(json.dumps({"message": test_message}))

        # Receive responses
        print("\n📥 Responses:\n")

        timeout_count = 0
        while timeout_count < 3:
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=15.0)
                data = json.loads(response)

                msg_type = data.get('type', 'unknown')
                message = data.get('message', '')
                status = data.get('status', '')

                if msg_type == 'status':
                    print(f"⏳ Status: {status}")
                elif msg_type == 'response':
                    print(f"\n✅ Agent Response:\n{message}")
                    if status == 'completed':
                        break
                elif msg_type == 'error':
                    print(f"\n⚠️  Error: {message}")
                    break

            except asyncio.TimeoutError:
                timeout_count += 1
                print("⏱️  Waiting for response...")

        print("\n✅ Test completed!")

if __name__ == "__main__":
    print("="*60)
    print("Testing Document Search via WebSocket")
    print("="*60 + "\n")

    asyncio.run(test_document_search())
