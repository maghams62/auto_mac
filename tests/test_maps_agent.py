"""
Test script for Maps Agent - Trip planning with Apple Maps integration.

This script tests the Maps Agent's ability to:
1. Plan trips from origin to destination
2. Add stops for food and gas
3. Generate Maps URLs with waypoints
4. Support departure time specification
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import load_config
from src.agent.maps_agent import MapsAgent


def test_basic_trip():
    """Test basic trip planning."""
    print("\n" + "=" * 80)
    print("TEST 1: Basic Trip Planning (San Francisco to Los Angeles)")
    print("=" * 80)

    config = load_config()
    maps_agent = MapsAgent(config)

    result = maps_agent.execute("plan_trip", {
        "origin": "San Francisco, CA",
        "destination": "Los Angeles, CA",
        "add_food_stop": True,
        "add_gas_stop": True,
        "departure_time": "5:00 AM"
    })

    print(f"\nResult: {result}")
    print(f"\nMessage: {result.get('message')}")
    print(f"Maps URL: {result.get('maps_url')}")
    print(f"Total Stops: {result.get('total_stops')}")

    if result.get('stops'):
        print("\nStops:")
        for stop in result['stops']:
            print(f"  {stop['order']}. {stop['location']} ({stop['type']})")

    return result


def test_google_maps():
    """Test Google Maps URL generation."""
    print("\n" + "=" * 80)
    print("TEST 2: Google Maps URL Generation")
    print("=" * 80)

    config = load_config()
    maps_agent = MapsAgent(config)

    result = maps_agent.execute("plan_trip", {
        "origin": "San Francisco, CA",
        "destination": "Los Angeles, CA",
        "add_food_stop": True,
        "add_gas_stop": True,
        "departure_time": "5:00 AM",
        "use_google_maps": True
    })

    print(f"\nResult: {result}")
    print(f"\nMessage: {result.get('message')}")
    print(f"Maps Service: {result.get('maps_service')}")
    print(f"Maps URL: {result.get('maps_url')}")

    return result


def test_no_stops():
    """Test trip planning without stops."""
    print("\n" + "=" * 80)
    print("TEST 3: Trip Without Stops")
    print("=" * 80)

    config = load_config()
    maps_agent = MapsAgent(config)

    result = maps_agent.execute("plan_trip", {
        "origin": "San Francisco, CA",
        "destination": "San Jose, CA",
        "add_food_stop": False,
        "add_gas_stop": False
    })

    print(f"\nResult: {result}")
    print(f"\nMessage: {result.get('message')}")
    print(f"Maps URL: {result.get('maps_url')}")
    print(f"Total Stops: {result.get('total_stops')}")

    return result


def test_only_food_stop():
    """Test trip planning with only food stop."""
    print("\n" + "=" * 80)
    print("TEST 4: Trip With Only Food Stop")
    print("=" * 80)

    config = load_config()
    maps_agent = MapsAgent(config)

    result = maps_agent.execute("plan_trip", {
        "origin": "San Francisco, CA",
        "destination": "Los Angeles, CA",
        "add_food_stop": True,
        "add_gas_stop": False,
        "departure_time": "6:30 AM"
    })

    print(f"\nResult: {result}")
    print(f"\nMessage: {result.get('message')}")
    print(f"Maps URL: {result.get('maps_url')}")
    print(f"Total Stops: {result.get('total_stops')}")

    if result.get('stops'):
        print("\nStops:")
        for stop in result['stops']:
            print(f"  {stop['order']}. {stop['location']} ({stop['type']})")

    return result


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("MAPS AGENT TEST SUITE")
    print("=" * 80)

    try:
        # Test 1: Basic trip planning
        result1 = test_basic_trip()

        # Test 2: Google Maps URL
        result2 = test_google_maps()

        # Test 3: No stops
        result3 = test_no_stops()

        # Test 4: Only food stop
        result4 = test_only_food_stop()

        print("\n" + "=" * 80)
        print("ALL TESTS COMPLETED")
        print("=" * 80)

        # Show final URL from test 1
        print("\n" + "=" * 80)
        print("EXAMPLE OUTPUT - San Francisco to Los Angeles Trip")
        print("=" * 80)
        print(f"\nOrigin: {result1.get('origin')}")
        print(f"Destination: {result1.get('destination')}")
        print(f"Departure Time: {result1.get('departure_time')}")
        print(f"\nStops:")
        for stop in result1.get('stops', []):
            print(f"  {stop['order']}. {stop['location']} - {stop['type'].upper()} STOP")
        print(f"\nMaps URL:")
        print(result1.get('maps_url'))

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
