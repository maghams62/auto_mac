## Example 20: MAPS AGENT - International Trip Planning (NEW!)

### User Request
"Plan a trip from London to Paris with 2 fuel stops"

### Decomposition
```json
{
  "goal": "Plan international route with fuel stops",
  "steps": [
    {
      "id": 1,
      "action": "plan_trip_with_stops",
      "parameters": {
        "origin": "London, UK",
        "destination": "Paris, France",
        "num_fuel_stops": 2,
        "num_food_stops": 0,
        "departure_time": null,
        "use_google_maps": false,
        "open_maps": true
      },
      "dependencies": [],
      "reasoning": "International route - LLM handles geographic knowledge for any country. Works worldwide",
      "expected_output": "Route with 2 fuel stops between London and Paris, Maps URL, Apple Maps opened"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: International Routes**
- ✅ Works for ANY route worldwide (not limited to US)
- ✅ LLM uses geographic knowledge for international routes
- ✅ No hardcoded geographic assumptions
- ✅ Supports cities in any country (UK, France, Germany, Japan, etc.)

---
