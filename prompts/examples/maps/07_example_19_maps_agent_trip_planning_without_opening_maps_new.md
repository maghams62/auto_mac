## Example 19: MAPS AGENT - Trip Planning Without Opening Maps (NEW!)

### User Request
"Plan a trip from Miami to Key West with 1 fuel stop and give me the link"

### Decomposition
```json
{
  "goal": "Plan route and return URL without opening Maps",
  "steps": [
    {
      "id": 1,
      "action": "plan_trip_with_stops",
      "parameters": {
        "origin": "Miami, FL",
        "destination": "Key West, FL",
        "num_fuel_stops": 1,
        "num_food_stops": 0,
        "departure_time": null,
        "use_google_maps": false,
        "open_maps": false
      },
      "dependencies": [],
      "reasoning": "User wants 'the link' = URL only, not auto-opening. Set open_maps=false",
      "expected_output": "Route with 1 fuel stop, Maps URL in response (maps_opened: false)"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: open_maps Parameter**
- ✅ `open_maps: true` (default) → Automatically opens Maps app/browser
- ✅ `open_maps: false` → Returns URL only, doesn't open Maps
- ✅ Use `false` when user says "give me the link" or "just the URL"
- ✅ Use `true` when user says "open it in Maps" or "show me the route"
- ✅ Maps URL is ALWAYS provided in response, regardless of `open_maps` value

---
