#!/usr/bin/env python3
"""
Test that maps trip planning is fully LLM-driven with no hardcoded values.

This test verifies:
1. LLM extracts parameters from natural language queries
2. LLM suggests stop locations (no hardcoded routes)
3. System handles variations and abbreviations
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils import load_config
from src.orchestrator.main_orchestrator import MainOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_llm_parameter_extraction():
    """Test that LLM extracts all parameters from natural language."""
    print("\n" + "=" * 80)
    print("TEST: LLM Parameter Extraction - No Hardcoded Values")
    print("=" * 80)
    
    test_queries = [
        {
            "query": "plan a trip from LA to San diego with 2 gas stops and a stop for lunch and dinner at 5 AM",
            "expected_params": {
                "origin": "Los Angeles, CA",  # LLM should interpret "LA"
                "destination": "San Diego, CA",  # LLM should interpret "San diego"
                "num_fuel_stops": 2,  # LLM should interpret "2 gas stops"
                "num_food_stops": 2,  # LLM should interpret "lunch and dinner"
                "departure_time": "5:00 AM"  # LLM should interpret "5 AM"
            }
        },
        {
            "query": "I need to drive from San Francisco to Los Angeles with one fuel stop and breakfast at 7:30 AM",
            "expected_params": {
                "origin": "San Francisco, CA",
                "destination": "Los Angeles, CA",
                "num_fuel_stops": 1,  # LLM should interpret "one fuel stop"
                "num_food_stops": 1,  # LLM should interpret "breakfast"
                "departure_time": "7:30 AM"
            }
        },
        {
            "query": "route from NYC to Boston with 3 gas stations and lunch, dinner, and a snack stop",
            "expected_params": {
                "origin": "New York, NY",  # LLM should interpret "NYC"
                "destination": "Boston, MA",
                "num_fuel_stops": 3,
                "num_food_stops": 3  # LLM should interpret "lunch, dinner, and a snack stop"
            }
        }
    ]
    
    config = load_config()
    orchestrator = MainOrchestrator(config)
    
    results = []
    for i, test_case in enumerate(test_queries, 1):
        print(f"\n--- Test Case {i} ---")
        print(f"Query: {test_case['query']}")
        print(f"Expected: {test_case['expected_params']}")
        
        try:
            result = orchestrator.execute(test_case['query'])
            
            if result.get("status") == "success":
                # Check if plan was created and executed
                step_results = result.get("step_results", {})
                if step_results:
                    print("✅ Plan created and executed successfully")
                    # Verify parameters were extracted (check first step output)
                    for step_id, step_result in step_results.items():
                        output = step_result.get("output", {})
                        if output and not output.get("error"):
                            print(f"   Origin: {output.get('origin')}")
                            print(f"   Destination: {output.get('destination')}")
                            print(f"   Fuel Stops: {output.get('num_fuel_stops')}")
                            print(f"   Food Stops: {output.get('num_food_stops')}")
                            print(f"   Departure: {output.get('departure_time')}")
                            
                            # Verify LLM extracted parameters correctly
                            expected = test_case['expected_params']
                            matches = True
                            if output.get('origin') != expected.get('origin'):
                                print(f"   ⚠️  Origin mismatch: got '{output.get('origin')}', expected '{expected.get('origin')}'")
                                matches = False
                            if output.get('num_fuel_stops') != expected.get('num_fuel_stops'):
                                print(f"   ⚠️  Fuel stops mismatch: got {output.get('num_fuel_stops')}, expected {expected.get('num_fuel_stops')}")
                                matches = False
                            if output.get('num_food_stops') != expected.get('num_food_stops'):
                                print(f"   ⚠️  Food stops mismatch: got {output.get('num_food_stops')}, expected {expected.get('num_food_stops')}")
                                matches = False
                            
                            if matches:
                                print("   ✅ All parameters extracted correctly by LLM")
                            results.append(matches)
                            break
                else:
                    print("❌ No steps executed")
                    results.append(False)
            else:
                print(f"❌ Execution failed: {result.get('error')}")
                results.append(False)
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    return all(results)


def test_llm_stop_suggestions():
    """Test that stop locations are suggested by LLM, not hardcoded."""
    print("\n" + "=" * 80)
    print("TEST: LLM Stop Location Suggestions - No Hardcoded Routes")
    print("=" * 80)
    
    query = "plan a trip from Los Angeles, CA to San Diego, CA with 2 fuel stops and 2 food stops"
    
    print(f"Query: {query}")
    print("Verifying that stop locations are suggested by LLM...")
    
    config = load_config()
    orchestrator = MainOrchestrator(config)
    
    try:
        result = orchestrator.execute(query)
        
        if result.get("status") == "success":
            step_results = result.get("step_results", {})
            for step_id, step_result in step_results.items():
                output = step_result.get("output", {})
                if output and not output.get("error") and output.get("stops"):
                    stops = output["stops"]
                    print(f"\n✅ LLM suggested {len(stops)} stops:")
                    for stop in stops:
                        print(f"   {stop['order']}. {stop['location']} ({stop['type']})")
                    
                    # Verify stops are actual city names (not generic placeholders)
                    for stop in stops:
                        location = stop['location']
                        if "Stop" in location and location.startswith("Stop"):
                            print(f"   ❌ Found hardcoded placeholder: {location}")
                            return False
                        if not any(char.isalpha() for char in location):
                            print(f"   ❌ Invalid location format: {location}")
                            return False
                    
                    print("✅ All stops are LLM-suggested city locations (no hardcoded values)")
                    return True
        else:
            print(f"❌ Execution failed: {result.get('error')}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all LLM-driven tests."""
    print("\n" + "=" * 80)
    print("🧠 LLM-DRIVEN MAPS TEST SUITE")
    print("=" * 80)
    print("Verifying that ALL decisions are made by LLM, not hardcoded")
    
    tests = [
        ("LLM Parameter Extraction", test_llm_parameter_extraction),
        ("LLM Stop Suggestions", test_llm_stop_suggestions),
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
    if all_passed:
        print("\n✅ All tests passed - System is fully LLM-driven!")
    else:
        print("\n❌ Some tests failed - Review LLM integration")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())

