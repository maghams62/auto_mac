## Example 17: MAPS AGENT - Open Maps with Existing Route (NEW!)

### User Request
"Open Maps with a route from Chicago to Detroit via Toledo"

### Decomposition
```json
{
  "goal": "Open Maps app with specific route and waypoints",
  "steps": [
    {
      "id": 1,
      "action": "open_maps_with_route",
      "parameters": {
        "origin": "Chicago, IL",
        "destination": "Detroit, MI",
        "stops": ["Toledo, OH"],
        "start_navigation": false
      },
      "dependencies": [],
      "reasoning": "User wants to open Maps with specific route. Use open_maps_with_route when route is already known",
      "expected_output": "Apple Maps opened with route, waypoint shown"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: open_maps_with_route Pattern**
- ✅ Use `open_maps_with_route` when route/stops are already known
- ✅ Use `plan_trip_with_stops` when you need LLM to suggest stops
- ✅ `stops` parameter: List of waypoint locations (e.g., `["Toledo, OH", "Cleveland, OH"]`)
- ✅ `start_navigation: false` = Just open directions (default)
- ✅ `start_navigation: true` = Automatically start navigation

---
