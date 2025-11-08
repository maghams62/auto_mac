"""
Test Phoenix to Los Angeles trip planning.
Query: Plan a trip from Phoenix to Los Angeles with 1 fuel stop and
       places for breakfast and lunch, departing at 4 AM
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.utils import load_config
from src.agent.maps_agent import MapsAgent


def test_phoenix_to_la():
    """Test Phoenix to LA trip."""
    print("\n" + "=" * 80)
    print("🚗 PHOENIX TO LOS ANGELES TRIP")
    print("=" * 80)
    print("Query: Plan a trip from Phoenix to Los Angeles with 1 fuel stop")
    print("       and places for breakfast and lunch, departing at 4 AM")
    print("=" * 80)

    config = load_config()
    maps_agent = MapsAgent(config)

    result = maps_agent.execute("plan_trip_with_stops", {
        "origin": "Phoenix, AZ",
        "destination": "Los Angeles, CA",
        "num_fuel_stops": 1,
        "num_food_stops": 2,  # breakfast and lunch
        "departure_time": "4:00 AM"
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
    print(f"\n🔗 Apple Maps URL:")
    print(f"   {result.get('maps_url')}")

    print(f"\n💬 Message:")
    print(f"   {result.get('message')}")

    # Also show Google Maps version
    print("\n" + "-" * 80)
    print("Google Maps Version (with departure time in URL):")
    print("-" * 80)

    result_google = maps_agent.execute("plan_trip_with_stops", {
        "origin": "Phoenix, AZ",
        "destination": "Los Angeles, CA",
        "num_fuel_stops": 1,
        "num_food_stops": 2,
        "departure_time": "4:00 AM",
        "use_google_maps": True
    })

    print(f"\n🔗 Google Maps URL:")
    print(f"   {result_google.get('maps_url')}")

    return result


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🗺️  MAPS AGENT - PHOENIX TO LA TEST")
    print("=" * 80)

    try:
        result = test_phoenix_to_la()
        print("\n" + "=" * 80)
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("=" * 80)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
