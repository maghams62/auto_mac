"""
Demo: LLM-Powered Maps Agent
Shows how the agent uses LLM to intelligently select waypoints for any route.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.utils import load_config
from src.agent.maps_agent import MapsAgent


def demo_route(origin, destination, fuel_stops, food_stops, departure_time):
    """Demo a route with the Maps Agent."""
    print(f"\n{'='*80}")
    print(f"🗺️  ROUTE: {origin} → {destination}")
    print(f"{'='*80}")
    print(f"   Fuel Stops: {fuel_stops}")
    print(f"   Food Stops: {food_stops}")
    print(f"   Departure: {departure_time}")
    print()

    config = load_config()
    maps_agent = MapsAgent(config)

    result = maps_agent.execute("plan_trip_with_stops", {
        "origin": origin,
        "destination": destination,
        "num_fuel_stops": fuel_stops,
        "num_food_stops": food_stops,
        "departure_time": departure_time
    })

    if result.get('error'):
        print(f"   ❌ Error: {result.get('error_message')}")
        return

    print(f"   📍 LLM Selected Stops:")
    for stop in result.get('stops', []):
        icon = "🍴" if stop['type'] == "food" else "⛽"
        print(f"      {stop['order']}. {icon} {stop['location']} ({stop['type'].upper()})")

    print(f"\n   🔗 Apple Maps URL:")
    print(f"      {result.get('maps_url')}")
    print()


def main():
    print("\n" + "="*80)
    print("🤖 LLM-POWERED MAPS AGENT DEMONSTRATION")
    print("="*80)
    print("\nThe agent uses GPT-4 to intelligently select waypoints based on:")
    print("  • Actual geography and highway routes")
    print("  • Optimal distribution of stops")
    print("  • Towns/cities with amenities (gas, food, etc.)")
    print("\nNo hardcoded routes - works for ANY origin and destination!")
    print("="*80)

    # Demo 1: Phoenix to LA
    demo_route(
        origin="Phoenix, AZ",
        destination="Los Angeles, CA",
        fuel_stops=1,
        food_stops=2,
        departure_time="4:00 AM"
    )

    # Demo 2: San Francisco to Seattle
    demo_route(
        origin="San Francisco, CA",
        destination="Seattle, WA",
        fuel_stops=2,
        food_stops=3,
        departure_time="6:00 AM"
    )

    # Demo 3: Denver to Chicago
    demo_route(
        origin="Denver, CO",
        destination="Chicago, IL",
        fuel_stops=2,
        food_stops=2,
        departure_time="5:00 AM"
    )

    print("="*80)
    print("✅ DEMONSTRATION COMPLETE")
    print("="*80)
    print("\nKey Features:")
    print("  ✓ LLM selects real cities along actual routes")
    print("  ✓ No hardcoded route data needed")
    print("  ✓ Works for any US road trip")
    print("  ✓ Apple Maps handles final routing")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
