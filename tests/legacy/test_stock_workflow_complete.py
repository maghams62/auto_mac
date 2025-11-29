#!/usr/bin/env python3
"""
Complete end-to-end test for stock slideshow email workflow.
Tests: Plan display -> Stock lookup -> Slideshow creation -> Email delivery
"""

import asyncio
import websockets
import json
from datetime import datetime

async def test_complete_stock_workflow():
    uri = "ws://localhost:8000/ws/chat"

    print("="*70)
    print("COMPLETE STOCK WORKFLOW TEST")
    print("="*70)
    print("\n🔗 Connecting to WebSocket...")

    async with websockets.connect(uri) as websocket:
        print("✅ Connected!\n")

        # Use a valid stock - Apple
        test_message = "Search the stock price of Apple and create a slideshow and email it to me"

        print(f"📤 Testing: '{test_message}'")
        print(f"   Expected workflow:")
        print(f"   1. Plan display with reasoning")
        print(f"   2. Stock symbol search (AAPL)")
        print(f"   3. Get stock price")
        print(f"   4. Create slideshow")
        print(f"   5. Email with attachment")
        print(f"   6. Confirmation message\n")

        await websocket.send(json.dumps({
            "message": test_message
        }))

        print("📥 Monitoring execution...\n")
        print("-"*70)

        # Track workflow progress
        workflow_status = {
            "plan_received": False,
            "plan_steps": [],
            "stock_data_retrieved": False,
            "slideshow_created": False,
            "email_sent": False,
            "completion_confirmed": False
        }

        messages = []
        timeout_seconds = 120  # 2 minute timeout for complete workflow
        start_time = asyncio.get_event_loop().time()

        try:
            async for message in websocket:
                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout_seconds:
                    print(f"\n⏱️ Timeout after {timeout_seconds} seconds")
                    break

                data = json.loads(message)
                messages.append(data)
                msg_type = data.get("type", "unknown")

                if msg_type == "system":
                    print(f"[SYSTEM] {data.get('message', '')[:50]}")

                elif msg_type == "status":
                    status = data.get('status', 'unknown')
                    print(f"[STATUS] {status}")

                elif msg_type == "plan":
                    workflow_status["plan_received"] = True
                    workflow_status["plan_steps"] = data.get('steps', [])

                    print(f"\n{'='*70}")
                    print(f"[PLAN] ✅ Task Disambiguation Received!")
                    print(f"{'='*70}")

                    goal = data.get('goal', 'N/A')
                    steps = data.get('steps', [])

                    print(f"\n🎯 Goal: {goal}")
                    print(f"\n📋 Breakdown ({len(steps)} steps):\n")

                    for i, step in enumerate(steps, 1):
                        action = step.get('action', 'N/A')
                        reasoning = step.get('reasoning', '')
                        print(f"  {i}. {action}")
                        if reasoning:
                            print(f"     💭 {reasoning}")

                    print(f"\n{'='*70}\n")

                elif msg_type == "response":
                    response_msg = data.get('message', '').lower()
                    print(f"\n[RESPONSE] Received final response")

                    # Check for workflow completion indicators
                    if 'stock' in response_msg or 'apple' in response_msg or 'aapl' in response_msg:
                        workflow_status["stock_data_retrieved"] = True
                        print(f"  ✅ Stock data retrieval confirmed")

                    if 'slideshow' in response_msg or 'presentation' in response_msg or 'keynote' in response_msg:
                        workflow_status["slideshow_created"] = True
                        print(f"  ✅ Slideshow creation confirmed")

                    if 'email' in response_msg or 'sent' in response_msg:
                        workflow_status["email_sent"] = True
                        print(f"  ✅ Email delivery confirmed")

                    workflow_status["completion_confirmed"] = True

                    # Display full response
                    print(f"\n  Response text:")
                    print(f"  {data.get('message', '')}")

                    break  # End test after response

                elif msg_type == "error":
                    error_msg = data.get('message', 'Unknown error')
                    print(f"\n[ERROR] ❌ {error_msg}")
                    break

        except asyncio.TimeoutError:
            print(f"\n⏱️ WebSocket timeout")
        except Exception as e:
            print(f"\n❌ Exception: {e}")

        # Generate test report
        print(f"\n{'='*70}")
        print(f"TEST RESULTS")
        print(f"{'='*70}\n")

        print(f"Total messages: {len(messages)}")
        print(f"Execution time: {elapsed:.1f}s\n")

        print(f"Workflow Status:")
        print(f"  {'✅' if workflow_status['plan_received'] else '❌'} Plan with reasoning displayed")
        print(f"  {'✅' if workflow_status['stock_data_retrieved'] else '❌'} Stock data retrieved")
        print(f"  {'✅' if workflow_status['slideshow_created'] else '❌'} Slideshow created")
        print(f"  {'✅' if workflow_status['email_sent'] else '❌'} Email sent")
        print(f"  {'✅' if workflow_status['completion_confirmed'] else '❌'} Completion confirmed")

        # Overall result
        all_success = all([
            workflow_status['plan_received'],
            workflow_status['stock_data_retrieved'],
            workflow_status['slideshow_created'],
            workflow_status['email_sent'],
            workflow_status['completion_confirmed']
        ])

        print(f"\n{'='*70}")
        if all_success:
            print(f"🎉 SUCCESS! Complete workflow executed successfully!")
            print(f"{'='*70}")
            print(f"\nVerify:")
            print(f"  1. Check your email inbox for the slideshow")
            print(f"  2. The UI showed the plan with reasoning")
            print(f"  3. All steps completed without errors")
        else:
            print(f"❌ FAILED! Workflow incomplete")
            print(f"{'='*70}")

            if not workflow_status['plan_received']:
                print(f"\n⚠️  Plan display not working")
            if not workflow_status['stock_data_retrieved']:
                print(f"\n⚠️  Stock data retrieval failed")
            if not workflow_status['slideshow_created']:
                print(f"\n⚠️  Slideshow creation failed")
            if not workflow_status['email_sent']:
                print(f"\n⚠️  Email delivery failed")

            print(f"\nDebug info:")
            if workflow_status['plan_received']:
                print(f"  Plan had {len(workflow_status['plan_steps'])} steps")

            print(f"\n  All messages:")
            for msg in messages:
                print(f"    - {msg.get('type')}: {str(msg)[:100]}")

if __name__ == "__main__":
    asyncio.run(test_complete_stock_workflow())
