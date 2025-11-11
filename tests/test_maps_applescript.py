#!/usr/bin/env python3
"""
Test script to verify Apple Maps AppleScript implementation.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from automation.maps_automation import MapsAutomation

def test_maps_directions():
    """Test opening Apple Maps with directions."""
    print("Testing Apple Maps directions with waypoints...")
    print("=" * 60)
    
    automation = MapsAutomation()
    
    result = automation.open_directions(
        origin="New York, NY",
        destination="Los Angeles, CA",
        stops=["Columbus, OH, USA", "St. Louis, MO, USA", "Amarillo, TX, USA"],
        start_navigation=False
    )
    
    print("\nResult:")
    print(f"  Success: {result.get('success')}")
    if result.get('success'):
        print(f"  Message: {result.get('message')}")
    else:
        print(f"  Error: {result.get('error_message')}")
    
    return result.get('success', False)

if __name__ == "__main__":
    success = test_maps_directions()
    sys.exit(0 if success else 1)

