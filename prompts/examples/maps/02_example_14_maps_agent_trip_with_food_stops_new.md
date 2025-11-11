## Example 14: MAPS AGENT - Trip with Food Stops (NEW!)

### User Request
"Plan a trip from San Francisco to San Diego with stops for breakfast and lunch"

### Decomposition
```json
{
  "goal": "Plan route with 2 food stops (breakfast and lunch)",
  "steps": [
    {
      "id": 1,
      "action": "plan_trip_with_stops",
      "parameters": {
        "origin": "San Francisco, CA",
        "destination": "San Diego, CA",
        "num_fuel_stops": 0,
        "num_food_stops": 2,
        "departure_time": null,
        "use_google_maps": false,
        "open_maps": true
      },
      "dependencies": [],
      "reasoning": "User wants breakfast and lunch stops = 2 food stops. LLM will suggest optimal locations",
      "expected_output": "Route with 2 food stops, Maps URL, Apple Maps opened"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Food Stops Pattern**
- ✅ Count food stops: "breakfast and lunch" = 2 food stops
- ✅ "breakfast, lunch, and dinner" = 3 food stops
- ✅ LLM suggests optimal cities/towns along route for meals
- ✅ No hardcoded locations - LLM uses geographic knowledge

---
