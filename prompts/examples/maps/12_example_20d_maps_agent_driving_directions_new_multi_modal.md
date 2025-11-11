## Example 20d: MAPS AGENT - Driving Directions (NEW! Multi-Modal)

### User Request
"Drive me to San Francisco"

### Decomposition
```json
{
  "goal": "Get driving directions to San Francisco",
  "steps": [
    {
      "id": 1,
      "action": "get_directions",
      "parameters": {
        "origin": "Current Location",
        "destination": "San Francisco, CA",
        "transportation_mode": "driving",
        "open_maps": true
      },
      "dependencies": [],
      "reasoning": "User wants driving route. Driving is default but explicit for clarity",
      "expected_output": "Maps opens with driving directions showing route, traffic, and time"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Driving Directions Pattern**
- ✅ Use `get_directions` with `transportation_mode: "driving"` (or omit, it's default)
- ✅ Maps will show fastest driving route with real-time traffic
- ✅ Provides driving time with traffic conditions
- ✅ Aliases: "driving", "car" map to driving mode
- ✅ Default mode if not specified

**Driving Query Variations:**
- "directions to the airport" → `transportation_mode: "driving"` (or omit)
- "drive to Los Angeles" → `transportation_mode: "driving"`
- "how do I get there by car" → `transportation_mode: "car"`

---
