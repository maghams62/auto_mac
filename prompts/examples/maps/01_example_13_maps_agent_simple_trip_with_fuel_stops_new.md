## Example 13: MAPS AGENT - Simple Trip with Fuel Stops (NEW!)

### User Request
"Plan a trip from New York to Los Angeles with 3 fuel stops"

### Decomposition
```json
{
  "goal": "Plan route from New York to Los Angeles with 3 fuel stops and open Maps",
  "steps": [
    {
      "id": 1,
      "action": "plan_trip_with_stops",
      "parameters": {
        "origin": "New York, NY",
        "destination": "Los Angeles, CA",
        "num_fuel_stops": 3,
        "num_food_stops": 0,
        "departure_time": null,
        "use_google_maps": false,
        "open_maps": true
      },
      "dependencies": [],
      "reasoning": "Plan trip with 3 fuel stops. Maps will open automatically (open_maps=true by default)",
      "expected_output": "Route with 3 fuel stops, Maps URL, and Apple Maps opened automatically"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Maps Agent Pattern**
- ✅ Use `plan_trip_with_stops` for ALL trip planning (it's the PRIMARY tool)
- ✅ `open_maps` defaults to `true` - Maps opens automatically
- ✅ LLM automatically suggests optimal fuel stop locations along the route
- ✅ Returns `maps_url` (always provided) and `maps_opened` status
- ✅ Works for ANY route worldwide (not limited to US)

---
