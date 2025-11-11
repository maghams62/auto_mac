## Example 20c: MAPS AGENT - Walking Directions (NEW! Multi-Modal)

### User Request
"Walk me to the nearest coffee shop"

### Decomposition
```json
{
  "goal": "Get walking directions to nearest coffee shop",
  "steps": [
    {
      "id": 1,
      "action": "get_directions",
      "parameters": {
        "origin": "Current Location",
        "destination": "nearest coffee shop",
        "transportation_mode": "walking",
        "open_maps": true
      },
      "dependencies": [],
      "reasoning": "User wants walking directions. Use walking mode for pedestrian paths",
      "expected_output": "Maps opens with walking directions showing pedestrian routes and time"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Walking Directions Pattern**
- ✅ Use `get_directions` with `transportation_mode: "walking"`
- ✅ Maps will show pedestrian-friendly routes, sidewalks, crosswalks
- ✅ Provides walking time estimates
- ✅ Aliases: "walking", "walk" map to walking mode
- ✅ "nearest coffee shop" → Maps will find closest match

**Walking Query Variations:**
- "walk to the park" → `transportation_mode: "walking"`
- "how far is it on foot" → `transportation_mode: "walking"`
- "walking directions to downtown" → `transportation_mode: "walking"`

---
