"""
Test the improved Maps Agent with the user's query:
"plan a trip from santa clara to san diego with 2 fuel stops and a place for breakfast and lunch we leave at 7 AM"
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import load_config
from src.agent.maps_agent import MapsAgent


def test_user_query():
    """Test the exact user query."""
    print("\n" + "=" * 80)
    print("TEST: User Query - Santa Clara to San Diego")
    print("Query: plan a trip from santa clara to san diego with 2 fuel stops")
    print("       and a place for breakfast and lunch we leave at 7 AM")
    print("=" * 80)

    config = load_config()
    maps_agent = MapsAgent(config)

    result = maps_agent.execute("plan_trip_with_stops", {
        "origin": "Santa Clara, CA",
        "destination": "San Diego, CA",
        "num_fuel_stops": 2,
        "num_food_stops": 2,  # breakfast and lunch
        "departure_time": "7:00 AM"
    })

    print(f"\n✅ Result:")
    print(f"   Origin: {result.get('origin')}")
    print(f"   Destination: {result.get('destination')}")
    print(f"   Departure: {result.get('departure_time')}")
    print(f"   Total Stops: {result.get('total_stops')}")
    print(f"   Fuel Stops: {result.get('num_fuel_stops')}")
    print(f"   Food Stops: {result.get('num_food_stops')}")

    print(f"\n📍 Stops:")
    for stop in result.get('stops', []):
        icon = "🍴" if stop['type'] == "food" else "⛽" if stop['type'] == "fuel" else "🛑"
        print(f"   {stop['order']}. {icon} {stop['location']} ({stop['type'].upper()})")

    print(f"\n🗺️  Maps Service: {result.get('maps_service')}")
    print(f"\n🔗 Maps URL:")
    print(f"   {result.get('maps_url')}")

    print(f"\n💬 Message:")
    print(f"   {result.get('message')}")

    return result


def test_google_maps_version():
    """Test with Google Maps for better waypoint support."""
    print("\n" + "=" * 80)
    print("TEST: Same Query with Google Maps")
    print("=" * 80)

    config = load_config()
    maps_agent = MapsAgent(config)

    result = maps_agent.execute("plan_trip_with_stops", {
        "origin": "Santa Clara, CA",
        "destination": "San Diego, CA",
        "num_fuel_stops": 2,
        "num_food_stops": 2,
        "departure_time": "7:00 AM",
        "use_google_maps": True
    })

    print(f"\n🗺️  Maps Service: {result.get('maps_service')}")
    print(f"\n🔗 Google Maps URL:")
    print(f"   {result.get('maps_url')}")

    return result


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🚗 MAPS AGENT - IMPROVED VERSION TEST")
    print("=" * 80)

    try:
        # Test 1: User's exact query with Apple Maps
        result1 = test_user_query()

        # Test 2: Same with Google Maps
        result2 = test_google_maps_version()

        print("\n" + "=" * 80)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
