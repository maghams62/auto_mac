"""
Test that the agent automatically sends Maps URL via iMessage when planning a trip.
"""

import sys
from pathlib import Path
import logging

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from src.agent.agent import AutomationAgent
from src.utils import load_config


def test_auto_send():
    """Test that Maps URL is automatically sent via iMessage."""
    print("\n" + "="*80)
    print("TEST: Auto-send Maps URL via iMessage")
    print("="*80)

    # Query that requests trip planning - should automatically send via iMessage
    query = "plan a trip from Phoenix to Los Angeles with 1 fuel stop and places for breakfast and lunch, departing at 4 AM and send me the maps url"

    print(f"\n📝 Query: {query}")
    print("\n" + "-"*80)

    config = load_config()
    agent = AutomationAgent(config)

    result = agent.run(query)

    print("\n" + "="*80)
    print("📊 AGENT EXECUTION SUMMARY")
    print("="*80)
    print(f"Status: {result.get('status')}")
    print(f"Goal: {result.get('goal')}")
    print(f"Steps Executed: {result.get('steps_executed')}")

    # Check if both tools were used
    if result.get('step_results'):
        tools_used = []
        maps_result = None
        imessage_result = None

        for step in result['step_results']:
            if step.get('tool'):
                tools_used.append(step['tool'])

                if step['tool'] == 'plan_trip_with_stops':
                    maps_result = step.get('result')
                elif step['tool'] == 'send_imessage':
                    imessage_result = step.get('result')

        print(f"\n🔧 Tools Used: {', '.join(tools_used)}")

        # Verify Maps agent was called
        if maps_result:
            print(f"\n✅ Maps Agent:")
            print(f"   Origin: {maps_result.get('origin')}")
            print(f"   Destination: {maps_result.get('destination')}")
            print(f"   Stops: {maps_result.get('total_stops')}")
            if maps_result.get('stops'):
                for stop in maps_result['stops']:
                    icon = "🍴" if stop['type'] == "food" else "⛽"
                    print(f"     {icon} {stop['location']}")
            print(f"   Maps URL: {maps_result.get('maps_url')[:80]}...")
        else:
            print(f"\n❌ Maps Agent was NOT called")

        # Verify iMessage agent was called
        if imessage_result:
            print(f"\n✅ iMessage Agent:")
            print(f"   Status: {imessage_result.get('status')}")
            print(f"   Recipient: {imessage_result.get('recipient')}")
            print(f"   Message Length: {imessage_result.get('message_length')} chars")
            if imessage_result.get('error'):
                print(f"   ⚠️  Error: {imessage_result.get('error_message')}")
        else:
            print(f"\n❌ iMessage Agent was NOT called")

        # Final verdict
        print("\n" + "="*80)
        if 'plan_trip_with_stops' in tools_used and 'send_imessage' in tools_used:
            print("✅ SUCCESS: Both Maps and iMessage agents were invoked!")
            print("   The agent correctly planned the trip AND sent it via iMessage")
        elif 'plan_trip_with_stops' in tools_used:
            print("⚠️  PARTIAL: Maps agent called but iMessage NOT called")
            print("   The agent may need explicit instruction to send via iMessage")
        else:
            print("❌ FAILED: Maps agent was not called")
        print("="*80)

    return result


if __name__ == "__main__":
    try:
        result = test_auto_send()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
