## Example 15: MAPS AGENT - Trip with Fuel and Food Stops (NEW!)

### User Request
"Plan a trip from Los Angeles to Las Vegas with 2 gas stops and a lunch stop, leaving at 8 AM"

### Decomposition
```json
{
  "goal": "Plan route with fuel stops, food stop, and departure time",
  "steps": [
    {
      "id": 1,
      "action": "plan_trip_with_stops",
      "parameters": {
        "origin": "Los Angeles, CA",
        "destination": "Las Vegas, NV",
        "num_fuel_stops": 2,
        "num_food_stops": 1,
        "departure_time": "8:00 AM",
        "use_google_maps": false,
        "open_maps": true
      },
      "dependencies": [],
      "reasoning": "2 fuel stops + 1 food stop = 3 total stops. Departure time helps with traffic-aware routing",
      "expected_output": "Route with stops, departure time, Maps URL, Apple Maps opened"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Combined Stops Pattern**
- ✅ Count fuel stops separately: "2 gas stops" = `num_fuel_stops: 2`
- ✅ Count food stops separately: "a lunch stop" = `num_food_stops: 1`
- ✅ Departure time format: "8 AM" → "8:00 AM" (flexible parsing)
- ✅ Total stops = fuel + food (e.g., 2 + 1 = 3 stops)

---
