"""
Quick verification test for the Maps Agent.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.utils import load_config
from src.agent.maps_agent import MapsAgent


def test_basic():
    """Test basic functionality."""
    print("\n" + "="*80)
    print("VERIFICATION TEST - Phoenix to LA")
    print("="*80)

    config = load_config()
    maps_agent = MapsAgent(config)

    # Test with Phoenix to LA (1 fuel, 2 food)
    result = maps_agent.execute("plan_trip_with_stops", {
        "origin": "Phoenix, AZ",
        "destination": "Los Angeles, CA",
        "num_fuel_stops": 1,
        "num_food_stops": 2,
        "departure_time": "4:00 AM"
    })

    print(f"\n✓ Tool executed successfully")
    print(f"  Origin: {result.get('origin')}")
    print(f"  Destination: {result.get('destination')}")
    print(f"  Total Stops: {result.get('total_stops')}")
    print(f"  Fuel Stops: {result.get('num_fuel_stops')}")
    print(f"  Food Stops: {result.get('num_food_stops')}")

    print(f"\n  LLM-Selected Stops:")
    for stop in result.get('stops', []):
        icon = "🍴" if stop['type'] == "food" else "⛽"
        print(f"    {stop['order']}. {icon} {stop['location']}")

    # Verify stops are real cities (not generic placeholders)
    first_stop = result['stops'][0]['location']
    if "Stop" in first_stop or "stop" in first_stop or "between" in first_stop:
        print(f"\n  ❌ FAILED: Got generic placeholder instead of real city")
        print(f"     Received: {first_stop}")
        return False

    print(f"\n  ✓ PASSED: LLM returned actual cities")
    print(f"\n  Maps URL: {result.get('maps_url')[:80]}...")

    return True


if __name__ == "__main__":
    try:
        success = test_basic()
        print("\n" + "="*80)
        if success:
            print("✅ VERIFICATION PASSED")
        else:
            print("❌ VERIFICATION FAILED")
        print("="*80 + "\n")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
