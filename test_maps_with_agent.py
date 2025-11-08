"""
Test Maps Agent integration with the main agent system.
"""

import sys
from pathlib import Path
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from src.agent.agent import AutomationAgent
from src.utils import load_config


def test_maps_query():
    """Test the maps query through the main agent."""
    print("\n" + "=" * 80)
    print("🚗 TESTING MAPS AGENT VIA MAIN ORCHESTRATOR")
    print("=" * 80)

    query = "plan a trip from santa clara to san diego with 2 fuel stops and a place for breakfast and lunch we leave at 7 AM"

    print(f"\n📝 Query: {query}")
    print("\n" + "-" * 80)

    config = load_config()
    agent = AutomationAgent(config)

    result = agent.run(query)

    print("\n" + "=" * 80)
    print("📊 AGENT RESULT")
    print("=" * 80)
    print(f"Status: {result.get('status')}")
    print(f"Goal: {result.get('goal')}")
    print(f"Steps Executed: {result.get('steps_executed')}")

    # Extract step results
    if result.get('step_results'):
        for step_result in result['step_results']:
            if step_result.get('result') and not step_result.get('result', {}).get('error'):
                output = step_result['result']
                print(f"\n✅ Final Output:")
                print(f"   Origin: {output.get('origin')}")
                print(f"   Destination: {output.get('destination')}")
                print(f"   Departure: {output.get('departure_time')}")
                print(f"   Total Stops: {output.get('total_stops')}")
                print(f"   Fuel Stops: {output.get('num_fuel_stops')}")
                print(f"   Food Stops: {output.get('num_food_stops')}")

                if output.get('stops'):
                    print(f"\n   📍 Stops:")
                    for stop in output['stops']:
                        icon = "🍴" if stop['type'] == "food" else "⛽" if stop['type'] == "fuel" else "🛑"
                        print(f"      {stop['order']}. {icon} {stop['location']} ({stop['type'].upper()})")

                print(f"\n   🗺️  Maps Service: {output.get('maps_service')}")
                print(f"\n   🔗 Maps URL:")
                print(f"      {output.get('maps_url')}")

    return result


if __name__ == "__main__":
    try:
        result = test_maps_query()
        print("\n" + "=" * 80)
        print("✅ TEST COMPLETED")
        print("=" * 80)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
