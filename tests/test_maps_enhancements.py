"""
Test script for Maps Agent enhancements.

Tests:
1. Location Service - current location detection
2. get_directions tool - multi-modal transportation
3. get_transit_schedule tool - transit-specific queries
4. URL generation with different transportation modes
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.location_service import LocationService, get_location_service
from src.agent.maps_agent import MapsAgent, get_directions, get_transit_schedule
from src.utils import load_config


def test_location_service():
    """Test 1: Location Service"""
    print("\n" + "="*60)
    print("TEST 1: Location Service")
    print("="*60)

    service = LocationService()

    # Test 1a: Check availability
    print(f"\n1a. Location service availability:")
    print(f"   Shortcuts available: {service._shortcuts_available}")
    print(f"   CoreLocationCLI available: {service._corelocationcli_available}")

    # Test 1b: Check aliases
    print(f"\n1b. Current location aliases:")
    test_aliases = ["here", "current", "current location", "my location"]
    for alias in test_aliases:
        is_alias = service.is_current_location_alias(alias)
        print(f"   '{alias}' → {is_alias}")

    # Test 1c: Parse coordinates
    print(f"\n1c. Parse coordinates:")
    test_coords = [
        "37.7749,-122.4194",
        "37.7749, -122.4194",
        "Lat: 37.7749, Lon: -122.4194"
    ]
    for coord in test_coords:
        parsed = service.parse_location(coord)
        if parsed:
            print(f"   '{coord}' → {parsed['formatted']} (source: {parsed['source']})")
        else:
            print(f"   '{coord}' → None (place name)")

    # Test 1d: Parse place names
    print(f"\n1d. Parse place names (should return None for geocoding):")
    test_places = ["Berkeley, CA", "San Francisco", "Office"]
    for place in test_places:
        parsed = service.parse_location(place)
        print(f"   '{place}' → {parsed}")

    # Test 1e: Get setup instructions
    print(f"\n1e. Setup instructions:")
    instructions = service.get_setup_instructions()
    print(f"   {instructions[:200]}...")

    print("\n✅ TEST 1 COMPLETE: Location Service")
    return True


def test_get_directions():
    """Test 2: get_directions tool"""
    print("\n" + "="*60)
    print("TEST 2: get_directions Tool")
    print("="*60)

    # Test 2a: Transit directions
    print("\n2a. Transit directions (bus query):")
    result = get_directions.invoke({
        "origin": "Current Location",
        "destination": "Berkeley, CA",
        "transportation_mode": "transit",
        "open_maps": False  # Don't actually open Maps during test
    })
    print(f"   Mode: {result['transportation_mode']}")
    print(f"   URL: {result['maps_url'][:80]}...")
    print(f"   Has transit note: {'note' in result}")
    assert result['transportation_mode'] == 'transit', "Should be transit mode"
    assert 'dirflg=r' in result['maps_url'], "URL should have transit flag"

    # Test 2b: Bicycle directions
    print("\n2b. Bicycle directions:")
    result = get_directions.invoke({
        "origin": "Home",
        "destination": "Office",
        "transportation_mode": "bicycle",
        "open_maps": False
    })
    print(f"   Mode: {result['transportation_mode']}")
    print(f"   URL: {result['maps_url'][:80]}...")
    assert result['transportation_mode'] == 'bicycle', "Should be bicycle mode"
    assert 'dirflg=b' in result['maps_url'], "URL should have bicycle flag"

    # Test 2c: Walking directions
    print("\n2c. Walking directions:")
    result = get_directions.invoke({
        "origin": "Current Location",
        "destination": "Coffee Shop",
        "transportation_mode": "walking",
        "open_maps": False
    })
    print(f"   Mode: {result['transportation_mode']}")
    print(f"   URL: {result['maps_url'][:80]}...")
    assert result['transportation_mode'] == 'walking', "Should be walking mode"
    assert 'dirflg=w' in result['maps_url'], "URL should have walking flag"

    # Test 2d: Driving directions (default)
    print("\n2d. Driving directions:")
    result = get_directions.invoke({
        "origin": "San Francisco",
        "destination": "Los Angeles",
        "transportation_mode": "driving",
        "open_maps": False
    })
    print(f"   Mode: {result['transportation_mode']}")
    print(f"   URL: {result['maps_url'][:80]}...")
    assert result['transportation_mode'] == 'driving', "Should be driving mode"
    assert 'dirflg=d' in result['maps_url'], "URL should have driving flag"

    # Test 2e: Transportation mode aliases
    print("\n2e. Transportation mode aliases:")
    aliases = {
        "bus": "transit",
        "bike": "bicycle",
        "walk": "walking",
        "car": "driving"
    }
    for alias, expected in aliases.items():
        result = get_directions.invoke({
            "origin": "A",
            "destination": "B",
            "transportation_mode": alias,
            "open_maps": False
        })
        print(f"   '{alias}' → {result['transportation_mode']}")
        assert result['transportation_mode'] == expected, f"'{alias}' should map to '{expected}'"

    print("\n✅ TEST 2 COMPLETE: get_directions Tool")
    return True


def test_get_transit_schedule():
    """Test 3: get_transit_schedule tool"""
    print("\n" + "="*60)
    print("TEST 3: get_transit_schedule Tool")
    print("="*60)

    # Test 3a: Transit schedule query
    print("\n3a. Transit schedule query:")
    result = get_transit_schedule.invoke({
        "origin": "Current Location",
        "destination": "Downtown Berkeley",
        "open_maps": False
    })
    print(f"   Mode: {result['transportation_mode']}")
    print(f"   URL: {result['maps_url'][:80]}...")
    print(f"   Has note: {'note' in result}")
    print(f"   Note preview: {result['note'][:60]}...")
    assert result['transportation_mode'] == 'transit', "Should be transit mode"
    assert 'dirflg=r' in result['maps_url'], "URL should have transit flag"
    assert 'note' in result, "Should have explanatory note"

    print("\n✅ TEST 3 COMPLETE: get_transit_schedule Tool")
    return True


def test_maps_agent_integration():
    """Test 4: Maps Agent integration"""
    print("\n" + "="*60)
    print("TEST 4: Maps Agent Integration")
    print("="*60)

    # Test 4a: Initialize Maps Agent
    print("\n4a. Initialize Maps Agent:")
    config = load_config()
    agent = MapsAgent(config)
    print(f"   Tools available: {len(agent.tools)}")
    print(f"   Tool names: {list(agent.tools.keys())}")
    assert len(agent.tools) == 4, "Should have 4 tools"
    assert 'get_directions' in agent.tools, "Should have get_directions"
    assert 'get_transit_schedule' in agent.tools, "Should have get_transit_schedule"

    # Test 4b: Execute get_directions via agent
    print("\n4b. Execute get_directions via Maps Agent:")
    result = agent.execute('get_directions', {
        "origin": "Current Location",
        "destination": "Berkeley",
        "transportation_mode": "transit",
        "open_maps": False
    })
    print(f"   Result has error: {'error' in result}")
    print(f"   Mode: {result.get('transportation_mode')}")
    assert 'error' not in result, "Should not have error"
    assert result['transportation_mode'] == 'transit', "Should be transit"

    # Test 4c: Execute get_transit_schedule via agent
    print("\n4c. Execute get_transit_schedule via Maps Agent:")
    result = agent.execute('get_transit_schedule', {
        "origin": "Current Location",
        "destination": "Downtown",
        "open_maps": False
    })
    print(f"   Result has error: {'error' in result}")
    print(f"   Mode: {result.get('transportation_mode')}")
    assert 'error' not in result, "Should not have error"
    assert result['transportation_mode'] == 'transit', "Should be transit"

    # Test 4d: Get hierarchy
    print("\n4d. Get Maps Agent hierarchy:")
    hierarchy = agent.get_hierarchy()
    print(f"   Hierarchy length: {len(hierarchy)} chars")
    print(f"   Mentions get_directions: {'get_directions' in hierarchy}")
    print(f"   Mentions transit: {'transit' in hierarchy}")
    print(f"   Mentions bicycle: {'bicycle' in hierarchy}")
    assert 'get_directions' in hierarchy, "Should mention get_directions"
    assert 'Multi-modal' in hierarchy or 'Multi-Modal' in hierarchy, "Should mention multi-modal"

    print("\n✅ TEST 4 COMPLETE: Maps Agent Integration")
    return True


def test_url_generation():
    """Test 5: URL generation with different modes"""
    print("\n" + "="*60)
    print("TEST 5: URL Generation")
    print("="*60)

    from src.agent.maps_agent import _generate_apple_maps_url

    # Test 5a: Transit URL
    print("\n5a. Transit URL:")
    url = _generate_apple_maps_url(
        origin="San Francisco",
        destination="Berkeley",
        stops=[],
        transportation_mode="r"
    )
    print(f"   URL: {url}")
    assert 'dirflg=r' in url, "Should have transit flag"
    assert 'San' in url and ('Francisco' in url or '%20Francisco' in url or '+Francisco' in url), "Should have origin"
    assert 'Berkeley' in url, "Should have destination"

    # Test 5b: Bicycle URL
    print("\n5b. Bicycle URL:")
    url = _generate_apple_maps_url(
        origin="Home",
        destination="Office",
        stops=[],
        transportation_mode="b"
    )
    print(f"   URL: {url}")
    assert 'dirflg=b' in url, "Should have bicycle flag"

    # Test 5c: Walking URL
    print("\n5c. Walking URL:")
    url = _generate_apple_maps_url(
        origin="A",
        destination="B",
        stops=[],
        transportation_mode="w"
    )
    print(f"   URL: {url}")
    assert 'dirflg=w' in url, "Should have walking flag"

    # Test 5d: Driving URL (default)
    print("\n5d. Driving URL:")
    url = _generate_apple_maps_url(
        origin="A",
        destination="B",
        stops=[],
        transportation_mode="d"
    )
    print(f"   URL: {url}")
    assert 'dirflg=d' in url, "Should have driving flag"

    # Test 5e: URL with stops (driving)
    print("\n5e. URL with stops:")
    url = _generate_apple_maps_url(
        origin="LA",
        destination="SF",
        stops=["Bakersfield", "Fresno"],
        transportation_mode="d"
    )
    print(f"   URL: {url[:100]}...")
    assert 'dirflg=d' in url, "Should have driving flag"
    assert url.count('daddr') >= 3, "Should have at least 3 daddr (stops + destination)"

    print("\n✅ TEST 5 COMPLETE: URL Generation")
    return True


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("MAPS ENHANCEMENTS TEST SUITE")
    print("="*60)

    tests = [
        test_location_service,
        test_get_directions,
        test_get_transit_schedule,
        test_maps_agent_integration,
        test_url_generation,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"\n❌ FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nMaps enhancements are working:")
        print("  • Location service with auto-detection")
        print("  • Multi-modal transportation (driving, walking, transit, bicycle)")
        print("  • get_directions tool for simple point-to-point queries")
        print("  • get_transit_schedule tool for transit-specific queries")
        print("  • URL generation with transportation mode flags")
        print("  • Full Maps Agent integration with 4 tools")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
