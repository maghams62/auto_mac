#!/usr/bin/env python3
"""
Test comprehensive trip planning query: LA to San Diego with stops.

Tests the specific query:
"plan a trip from LA to San diego with 2 gas stops and a stop for lunch and dinner at 5 AM"
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils import load_config
from src.agent.agent_registry import AgentRegistry
from src.orchestrator.main_orchestrator import MainOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_direct_maps_agent():
    """Test maps agent directly with LA to San Diego trip."""
    print("\n" + "=" * 80)
    print("TEST 1: Direct Maps Agent - LA to San Diego")
    print("=" * 80)
    
    config = load_config()
    registry = AgentRegistry(config)
    maps_agent = registry.get_agent("maps")
    
    result = maps_agent.execute("plan_trip_with_stops", {
        "origin": "Los Angeles, CA",
        "destination": "San Diego, CA",
        "num_fuel_stops": 2,
        "num_food_stops": 2,  # lunch and dinner
        "departure_time": "5:00 AM",
        "use_google_maps": True  # Better waypoint support
    })
    
    if result.get("error"):
        print(f"❌ Error: {result.get('error_message')}")
        return False
    
    print(f"\n✅ Trip Planned Successfully!")
    print(f"\n📍 Route:")
    print(f"   Origin: {result.get('origin')}")
    print(f"   Destination: {result.get('destination')}")
    print(f"   Departure: {result.get('departure_time')}")
    print(f"   Total Stops: {result.get('total_stops')}")
    print(f"   Fuel Stops: {result.get('num_fuel_stops')}")
    print(f"   Food Stops: {result.get('num_food_stops')}")
    
    if result.get("stops"):
        print(f"\n🛑 Stops:")
        for stop in result["stops"]:
            icon = "🍴" if stop['type'] == "food" else "⛽"
            print(f"   {stop['order']}. {icon} {stop['location']} ({stop['type'].upper()})")
    
    print(f"\n🗺️  Maps Service: {result.get('maps_service')}")
    print(f"\n🔗 Maps URL (ALWAYS provided):")
    print(f"   {result.get('maps_url')}")
    print(f"\n💡 You can:")
    print(f"   - Copy this URL and open it in your browser/Maps app")
    print(f"   - Or set open_maps=true to automatically open Maps")
    if result.get('maps_opened'):
        print(f"   ✅ Maps was automatically opened!")
    
    return True


def test_via_orchestrator_natural_language():
    """Test the query through orchestrator with natural language - verifies LLM extracts all parameters."""
    print("\n" + "=" * 80)
    print("TEST 2: Via Orchestrator - Natural Language Query (LLM-Driven)")
    print("=" * 80)
    
    # This query tests LLM's ability to extract:
    # - "LA" → "Los Angeles, CA"
    # - "San diego" → "San Diego, CA"
    # - "2 gas stops" → num_fuel_stops=2
    # - "lunch and dinner" → num_food_stops=2
    # - "5 AM" → departure_time="5:00 AM"
    query = "plan a trip from LA to San diego with 2 gas stops and a stop for lunch and dinner at 5 AM"
    
    print(f"\n📝 Query: {query}")
    print("🔍 Testing LLM parameter extraction:")
    print("   - 'LA' should be interpreted as 'Los Angeles, CA'")
    print("   - 'San diego' should be interpreted as 'San Diego, CA'")
    print("   - '2 gas stops' should be interpreted as num_fuel_stops=2")
    print("   - 'lunch and dinner' should be interpreted as num_food_stops=2")
    print("   - '5 AM' should be interpreted as departure_time='5:00 AM'")
    print("\n" + "-" * 80)
    
    config = load_config()
    orchestrator = MainOrchestrator(config)
    
    result = orchestrator.execute(query)
    
    print("\n" + "=" * 80)
    print("📊 ORCHESTRATOR RESULT")
    print("=" * 80)
    print(f"Status: {result.get('status')}")
    
    if result.get("status") == "success":
        print("✅ Plan executed successfully!")
        
        # Extract step results
        step_results = result.get("step_results", {})
        for step_id, step_result in step_results.items():
            output = step_result.get("output", {})
            if output and not output.get("error"):
                print(f"\n📍 Route Details:")
                print(f"   Origin: {output.get('origin')}")
                print(f"   Destination: {output.get('destination')}")
                print(f"   Departure: {output.get('departure_time')}")
                print(f"   Total Stops: {output.get('total_stops')}")
                print(f"   Fuel Stops: {output.get('num_fuel_stops')}")
                print(f"   Food Stops: {output.get('num_food_stops')}")
                
                if output.get("stops"):
                    print(f"\n🛑 Stops:")
                    for stop in output["stops"]:
                        icon = "🍴" if stop['type'] == "food" else "⛽"
                        print(f"   {stop['order']}. {icon} {stop['location']} ({stop['type'].upper()})")
                
                print(f"\n🗺️  Maps Service: {output.get('maps_service')}")
                print(f"\n🔗 Maps URL (ALWAYS provided):")
                print(f"   {output.get('maps_url')}")
                print(f"\n💡 You can:")
                print(f"   - Copy this URL and open it in your browser/Maps app")
                print(f"   - Or set open_maps=true to automatically open Maps")
                if output.get('maps_opened'):
                    print(f"   ✅ Maps was automatically opened!")
    else:
        print(f"❌ Error: {result.get('error')}")
        if result.get("step_results"):
            for step_id, step_result in result["step_results"].items():
                if step_result.get("output", {}).get("error"):
                    print(f"   Step {step_id}: {step_result['output'].get('error_message')}")
    
    return result.get("status") == "success"


def test_variations():
    """Test various trip planning variations."""
    print("\n" + "=" * 80)
    print("TEST 3: Trip Planning Variations")
    print("=" * 80)
    
    config = load_config()
    registry = AgentRegistry(config)
    maps_agent = registry.get_agent("maps")
    
    test_cases = [
        {
            "name": "LA to SD - Morning Departure",
            "params": {
                "origin": "Los Angeles, CA",
                "destination": "San Diego, CA",
                "num_fuel_stops": 1,
                "num_food_stops": 1,
                "departure_time": "8:00 AM"
            }
        },
        {
            "name": "LA to SD - Evening Departure",
            "params": {
                "origin": "Los Angeles, CA",
                "destination": "San Diego, CA",
                "num_fuel_stops": 2,
                "num_food_stops": 1,
                "departure_time": "6:00 PM"
            }
        },
        {
            "name": "SF to LA - Multiple Stops",
            "params": {
                "origin": "San Francisco, CA",
                "destination": "Los Angeles, CA",
                "num_fuel_stops": 2,
                "num_food_stops": 2,
                "departure_time": "7:00 AM",
                "use_google_maps": True
            }
        }
    ]
    
    results = []
    for test_case in test_cases:
        print(f"\n--- {test_case['name']} ---")
        result = maps_agent.execute("plan_trip_with_stops", test_case["params"])
        
        if not result.get("error"):
            print(f"✅ Success: {result.get('total_stops')} stops planned")
            results.append(True)
        else:
            print(f"❌ Error: {result.get('error_message')}")
            results.append(False)
    
    return all(results)


def test_edge_cases():
    """Test edge cases for trip planning."""
    print("\n" + "=" * 80)
    print("TEST 4: Edge Cases")
    print("=" * 80)
    
    config = load_config()
    registry = AgentRegistry(config)
    maps_agent = registry.get_agent("maps")
    
    # Test with abbreviated city names
    print("\n--- Test: Abbreviated City Names (LA, SD) ---")
    result = maps_agent.execute("plan_trip_with_stops", {
        "origin": "LA",
        "destination": "San Diego",
        "num_fuel_stops": 1,
        "num_food_stops": 1,
        "departure_time": "5:00 AM"
    })
    
    if not result.get("error"):
        print(f"✅ Success: {result.get('origin')} → {result.get('destination')}")
        return True
    else:
        print(f"❌ Error: {result.get('error_message')}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("🗺️  TRIP PLANNING TEST SUITE - LA TO SAN DIEGO")
    print("=" * 80)
    
    tests = [
        ("Direct Maps Agent", test_direct_maps_agent),
        ("Via Orchestrator (Natural Language)", test_via_orchestrator_natural_language),
        ("Variations", test_variations),
        ("Edge Cases", test_edge_cases),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n❌ Test '{test_name}' failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())

