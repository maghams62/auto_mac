## Example 18: MAPS AGENT - Complex Trip Planning (NEW!)

### User Request
"Plan a cross-country trip from Boston to San Francisco with 5 fuel stops, breakfast, lunch, and dinner stops, leaving tomorrow at 6 AM"

### Decomposition
```json
{
  "goal": "Plan complex cross-country route with multiple stops and departure time",
  "steps": [
    {
      "id": 1,
      "action": "plan_trip_with_stops",
      "parameters": {
        "origin": "Boston, MA",
        "destination": "San Francisco, CA",
        "num_fuel_stops": 5,
        "num_food_stops": 3,
        "departure_time": "6:00 AM",
        "use_google_maps": false,
        "open_maps": true
      },
      "dependencies": [],
      "reasoning": "5 fuel + 3 food = 8 total stops. LLM will suggest optimal locations across the country. Departure time helps with traffic routing",
      "expected_output": "Route with 8 stops distributed across cross-country route, Maps URL, Apple Maps opened"
    }
  ],
  "complexity": "medium"
}
```

**CRITICAL: Complex Trip Planning**
- ✅ Supports any reasonable number of stops (typically 0-20 total)
- ✅ LLM distributes stops evenly along route
- ✅ Works for ANY route worldwide (not just US)
- ✅ Departure time helps with traffic-aware routing
- ✅ LLM uses geographic knowledge - no hardcoded routes

---
