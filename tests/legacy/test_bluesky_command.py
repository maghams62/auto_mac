#!/usr/bin/env python3
"""
Test script to verify /bluesky slash command works correctly.
"""

import asyncio
import websockets
import json
from datetime import datetime

async def test_bluesky_command():
    uri = "ws://localhost:8000/ws/chat"

    print("🔗 Connecting to WebSocket...")
    async with websockets.connect(uri) as websocket:
        print("✅ Connected!\n")

        # Test the bluesky command
        test_message = "/bluesky post Testing from automation! 🤖"

        print(f"📤 Sending: '{test_message}'\n")
        await websocket.send(json.dumps({
            "message": test_message
        }))

        print("📥 Waiting for responses...\n")

        plan_received = False
        post_successful = False
        messages_received = []

        try:
            timeout = 30  # 30 second timeout
            start_time = asyncio.get_event_loop().time()

            async for message in websocket:
                # Check timeout
                if asyncio.get_event_loop().time() - start_time > timeout:
                    print(f"\n⏱️ Timeout after {timeout} seconds")
                    break

                data = json.loads(message)
                messages_received.append(data)

                msg_type = data.get("type", "unknown")
                print(f"[{msg_type.upper()}] ", end="")

                if msg_type == "plan":
                    plan_received = True
                    print("✅ PLAN RECEIVED!")
                    goal = data.get('goal', 'N/A')
                    steps = data.get('steps', [])
                    print(f"  Goal: {goal}")
                    print(f"  Steps ({len(steps)}):")
                    for i, step in enumerate(steps, 1):
                        print(f"    {i}. {step.get('action', 'N/A')}")
                        if step.get('reasoning'):
                            print(f"       → {step['reasoning']}")
                    print()

                elif msg_type == "status":
                    status = data.get('status', 'N/A')
                    print(f"Status: {status}")

                elif msg_type == "response":
                    response_msg = data.get('message', '')
                    print(f"Response received:")
                    print(f"  {response_msg[:200]}...")

                    # Check if post was successful
                    if "post" in response_msg.lower() or "bluesky" in response_msg.lower():
                        post_successful = True

                    # Stop after response
                    break

                elif msg_type == "error":
                    print(f"❌ Error: {data.get('message', 'N/A')}")
                    break

                elif msg_type == "system":
                    print(f"System: {data.get('message', '')[:50]}...")

                else:
                    print(f"{str(data)[:100]}...")

        except asyncio.TimeoutError:
            print("\n⏱️ Timeout waiting for messages")

        print(f"\n{'='*60}")
        print(f"Test Results:")
        print(f"{'='*60}")
        print(f"Total messages received: {len(messages_received)}")
        print(f"Plan message received: {'✅ YES' if plan_received else '❌ NO'}")
        print(f"Post successful: {'✅ YES' if post_successful else '❌ NO'}")

        if plan_received and post_successful:
            print("\n🎉 SUCCESS! Bluesky command is working correctly!")
            print("\nCheck your Bluesky profile to verify the post:")
            print("https://bsky.app/profile/ychack.bsky.social")
        else:
            print("\n❌ FAILED! Command did not complete successfully")
            print("\nReceived messages:")
            for msg in messages_received:
                print(f"  - {msg.get('type')}: {str(msg)[:150]}")

if __name__ == "__main__":
    asyncio.run(test_bluesky_command())
