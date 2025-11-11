"""
Test file organization via WebSocket
"""
import asyncio
import websockets
import json

async def test_file_organize():
    uri = "ws://localhost:8000/ws/chat"

    print("🔌 Connecting to WebSocket...")

    async with websockets.connect(uri) as websocket:
        print("✅ Connected!\n")

        # Wait for welcome
        await websocket.recv()

        # Test file organization
        test_message = "Move Tesla documents to the tesla folder"
        print(f"📤 Sending: '{test_message}'\n")

        await websocket.send(json.dumps({"message": test_message}))

        # Receive responses
        response_count = 0
        while response_count < 10:
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                data = json.loads(response)

                msg_type = data.get('type', 'unknown')
                message = data.get('message', '')
                status = data.get('status', '')

                if msg_type == 'status':
                    print(f"⏳ {status}")
                elif msg_type == 'response':
                    print(f"\n✅ Response:\n{json.dumps(message, indent=2)}\n")
                    if status == 'completed':
                        break
                elif msg_type == 'error':
                    print(f"\n❌ Error: {message}")
                    break

                response_count += 1

            except asyncio.TimeoutError:
                print("⏱️  Timeout")
                break

        print("✅ Test done!")

if __name__ == "__main__":
    asyncio.run(test_file_organize())
