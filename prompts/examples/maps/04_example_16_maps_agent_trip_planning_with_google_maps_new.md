## Example 16: MAPS AGENT - Trip Planning with Google Maps (NEW!)

### User Request
"Plan a trip from Seattle to Portland with 2 fuel stops using Google Maps"

### Decomposition
```json
{
  "goal": "Plan route using Google Maps instead of Apple Maps",
  "steps": [
    {
      "id": 1,
      "action": "plan_trip_with_stops",
      "parameters": {
        "origin": "Seattle, WA",
        "destination": "Portland, OR",
        "num_fuel_stops": 2,
        "num_food_stops": 0,
        "departure_time": null,
        "use_google_maps": true,
        "open_maps": true
      },
      "dependencies": [],
      "reasoning": "User explicitly requested Google Maps. Opens in browser instead of Maps app",
      "expected_output": "Route with stops, Google Maps URL, opens in browser"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Maps Service Selection**
- ✅ Default: `use_google_maps: false` → Apple Maps (native macOS integration)
- ✅ If user requests Google Maps: `use_google_maps: true` → Opens in browser
- ✅ Apple Maps preferred for macOS (better integration, AppleScript automation)
- ✅ Google Maps available as alternative (better waypoint support for complex routes)

---
