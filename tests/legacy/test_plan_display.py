#!/usr/bin/env python3
"""
Test script to verify the task disambiguation/plan display feature.
This will send a request to the API and check if the plan message is sent.
"""

import asyncio
import websockets
import json
from datetime import datetime

async def test_plan_display():
    uri = "ws://localhost:8000/ws/chat"

    print("🔗 Connecting to WebSocket...")
    async with websockets.connect(uri) as websocket:
        print("✅ Connected!\n")

        # Send a test message that should trigger task decomposition
        test_message = "Find all duplicate files in my Documents folder and send me a report"

        print(f"📤 Sending test message: '{test_message}'\n")
        await websocket.send(json.dumps({
            "message": test_message
        }))

        # Collect messages
        messages_received = []
        plan_message_found = False

        print("📥 Receiving messages...\n")

        try:
            # Wait for messages for up to 30 seconds
            async for message in websocket:
                data = json.loads(message)
                messages_received.append(data)

                msg_type = data.get("type", "unknown")
                print(f"[{msg_type.upper()}] ", end="")

                if msg_type == "plan":
                    plan_message_found = True
                    print("✅ PLAN MESSAGE RECEIVED!")
                    print(f"  Goal: {data.get('goal', 'N/A')}")
                    steps = data.get('steps', [])
                    print(f"  Steps ({len(steps)}):")
                    for i, step in enumerate(steps, 1):
                        print(f"    {i}. {step.get('action', 'N/A')}")
                        if step.get('reasoning'):
                            print(f"       → {step['reasoning']}")
                    print()

                elif msg_type == "status":
                    print(f"Status: {data.get('status', 'N/A')}")

                elif msg_type == "response":
                    print("Response received")
                    # Stop after response
                    break

                elif msg_type == "error":
                    print(f"❌ Error: {data.get('message', 'N/A')}")
                    break

                else:
                    print(f"{data.get('message', '')[:50]}...")

        except asyncio.TimeoutError:
            print("\n⏱️ Timeout waiting for messages")

        print(f"\n{'='*60}")
        print(f"Test Results:")
        print(f"{'='*60}")
        print(f"Total messages received: {len(messages_received)}")
        print(f"Plan message found: {'✅ YES' if plan_message_found else '❌ NO'}")

        if plan_message_found:
            print("\n🎉 SUCCESS! Task disambiguation display is working!")
        else:
            print("\n❌ FAILED! Plan message was not sent to UI")
            print("\nMessages received:")
            for msg in messages_received:
                print(f"  - {msg.get('type')}: {str(msg)[:100]}")

if __name__ == "__main__":
    asyncio.run(test_plan_display())
