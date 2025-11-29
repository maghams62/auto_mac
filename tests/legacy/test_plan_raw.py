#!/usr/bin/env python3
"""
Test script to see the raw plan message data.
"""

import asyncio
import websockets
import json

async def test_plan_raw():
    uri = "ws://localhost:8000/ws/chat"

    print("🔗 Connecting to WebSocket...")
    async with websockets.connect(uri) as websocket:
        print("✅ Connected!\n")

        test_message = "Find all duplicate files in my Documents folder and send me a report"

        print(f"📤 Sending: '{test_message}'\n")
        await websocket.send(json.dumps({"message": test_message}))

        print("📥 Waiting for plan message...\n")

        async for message in websocket:
            data = json.loads(message)

            if data.get("type") == "plan":
                print("=" * 60)
                print("RAW PLAN MESSAGE:")
                print("=" * 60)
                print(json.dumps(data, indent=2))
                print("=" * 60)
                break

            elif data.get("type") == "response":
                print("Response received without plan message!")
                break

if __name__ == "__main__":
    asyncio.run(test_plan_raw())
