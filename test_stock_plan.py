#!/usr/bin/env python3
"""
Test script to verify plan display for stock request.
"""

import asyncio
import websockets
import json

async def test_stock_plan():
    uri = "ws://localhost:8000/ws/chat"

    print("🔗 Connecting to WebSocket...")
    async with websockets.connect(uri) as websocket:
        print("✅ Connected!\n")

        # Test the stock request that should show plan
        test_message = "Search the stock price of Meta and create a slideshow and email it to me"

        print(f"📤 Sending: '{test_message}'\n")
        await websocket.send(json.dumps({
            "message": test_message
        }))

        print("📥 Waiting for messages...\n")
        print("="*60)

        plan_received = False
        messages = []

        try:
            async for message in websocket:
                data = json.loads(message)
                messages.append(data)

                msg_type = data.get("type", "unknown")

                if msg_type == "system":
                    print(f"✓ System message received")

                elif msg_type == "status":
                    status = data.get('status', 'N/A')
                    print(f"✓ Status: {status}")

                elif msg_type == "plan":
                    plan_received = True
                    print("\n" + "="*60)
                    print("🎯 PLAN MESSAGE RECEIVED!")
                    print("="*60)
                    goal = data.get('goal', 'N/A')
                    steps = data.get('steps', [])
                    print(f"\nGoal: {goal}")
                    print(f"\nSteps ({len(steps)}):")
                    for i, step in enumerate(steps, 1):
                        action = step.get('action', 'N/A')
                        reasoning = step.get('reasoning', '')
                        print(f"\n  {i}. {action}")
                        if reasoning:
                            print(f"     → {reasoning}")
                    print("\n" + "="*60 + "\n")

                elif msg_type == "response":
                    print(f"✓ Response received (stopping test)")
                    break

                elif msg_type == "error":
                    print(f"✗ Error: {data.get('message', 'N/A')}")
                    break

        except Exception as e:
            print(f"\n❌ Error: {e}")

        print(f"\n{'='*60}")
        print(f"TEST RESULTS")
        print(f"{'='*60}")
        print(f"Total messages: {len(messages)}")
        print(f"Plan message received: {'✅ YES' if plan_received else '❌ NO'}")

        if plan_received:
            print("\n🎉 SUCCESS! Plan with reasoning is being displayed!")
            print("\nThe UI should now show:")
            print("  1. Task goal")
            print("  2. Step-by-step breakdown")
            print("  3. Reasoning for each step (in italic gray text)")
        else:
            print("\n❌ FAILED! Plan message was not received")
            print("\nMessages received:")
            for msg in messages:
                print(f"  - {msg.get('type')}")

if __name__ == "__main__":
    asyncio.run(test_stock_plan())
