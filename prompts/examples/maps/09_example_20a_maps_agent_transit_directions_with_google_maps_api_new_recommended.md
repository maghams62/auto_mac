## Example 20a: MAPS AGENT - Transit Directions with Google Maps API (NEW! RECOMMENDED)

### User Request
"When's the next bus to Berkeley"

### Decomposition
```json
{
  "goal": "Get real-time transit directions with actual departure times using Google Maps API",
  "steps": [
    {
      "id": 1,
      "action": "get_google_transit_directions",
      "parameters": {
        "origin": "Current Location",
        "destination": "Berkeley, CA",
        "departure_time": "now"
      },
      "dependencies": [],
      "reasoning": "User asking for next bus time. Use Google Maps API to get PROGRAMMATIC transit schedule with actual departure times that can be returned in chat response",
      "expected_output": "Returns actual next departure time (e.g., 'Next departure: 3:45 PM') in chat, plus Google Maps URL"
    },
    {
      "id": 2,
      "action": "reply_to_user",
      "parameters": {
        "message": "[Generated based on step 1 result with actual departure time]"
      },
      "dependencies": [1],
      "reasoning": "Format the transit schedule response for UI display",
      "expected_output": "User sees 'Next bus at 3:45 PM' directly in chat"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Transit Directions Pattern (GOOGLE MAPS RECOMMENDED)**
- ✅ **ALWAYS use `get_google_transit_directions` for transit queries** - Returns actual times programmatically
- ✅ Returns "Next departure: 3:45 PM" directly in chat response
- ✅ Opens Google Maps in browser with full transit directions
- ✅ Provides step-by-step transit details with line numbers and stops
- ✅ Requires GOOGLE_MAPS_API_KEY in .env file
- ⚠️ If Google Maps API not configured, fallback to `get_directions` with Apple Maps (but no programmatic times)

**Transit Query Variations:**
- "when's the next bus to [place]" → `get_google_transit_directions`
- "show me the train schedule to [place]" → `get_google_transit_directions`
- "what time is the next BART to [place]" → `get_google_transit_directions`
- "when's the next bus to UCSC Silicon Valley" → `get_google_transit_directions`

**Fallback Pattern (if Google Maps API not available):**
```json
{
  "action": "get_directions",
  "parameters": {
    "origin": "Current Location",
    "destination": "Berkeley, CA",
    "transportation_mode": "transit",
    "open_maps": true
  }
}
```
Note: Fallback opens Apple Maps but cannot return programmatic departure times

---
