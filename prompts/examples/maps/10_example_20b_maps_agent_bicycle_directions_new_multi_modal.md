## Example 20b: MAPS AGENT - Bicycle Directions (NEW! Multi-Modal)

### User Request
"How do I bike to the office from here"

### Decomposition
```json
{
  "goal": "Get bicycle directions from current location to office",
  "steps": [
    {
      "id": 1,
      "action": "get_directions",
      "parameters": {
        "origin": "Current Location",
        "destination": "Office",
        "transportation_mode": "bicycle",
        "open_maps": true
      },
      "dependencies": [],
      "reasoning": "User wants bicycle route. Use bicycle mode for bike-friendly paths and lanes",
      "expected_output": "Maps opens with bicycle directions showing bike paths, lanes, and estimated time"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Bicycle Directions Pattern**
- ✅ Use `get_directions` with `transportation_mode: "bicycle"`
- ✅ Maps will show bike-friendly routes, bike lanes, paths
- ✅ Provides elevation info and time estimates
- ✅ Aliases: "bicycle", "bike", "cycling" all map to bicycle mode
- ✅ "from here" → use "Current Location" as origin

**Bicycle Query Variations:**
- "bike to the coffee shop" → `transportation_mode: "bicycle"`
- "cycling directions to downtown" → `transportation_mode: "bicycle"`
- "show me the bike route" → `transportation_mode: "bicycle"`

---
