# Maps Trip Planner - LLM & Agent-Driven Summary

## What We're Building

A trip planner that uses **LLM reasoning** and **agent tools** to plan routes with fuel/food stops. **Zero hardcoding** - everything is LLM-driven and tool-based.

## Core Principle

**LLM reasons → Agent tools execute → Apple Maps finds actual POIs**

### ❌ NOT Hardcoded
- No hardcoded cities: `if origin == "LA": stops = ["Irvine"]` ❌
- No hardcoded routes: `route = "I-5"` ❌  
- No hardcoded distances: `if miles > 500: add_stop()` ❌

### ✅ LLM & Agent-Driven
- LLM reasons about route, distance, highway access
- LLM understands "fuel stops" = actual gas stations needed
- LLM understands "food stops" = actual restaurants needed
- Agent tools query Apple Maps for real POIs
- Everything configurable via `config.yaml`

## How It Works

1. **User**: "Plan trip from NYC to SF with 2 fuel stops"
2. **LLM Reasons**:
   - Route: ~2,900 miles
   - Optimal spacing: ~1,450 miles apart
   - Considers: I-80 route, major cities, gas station availability
   - Suggests: "Columbus, OH" and "North Platte, NE"
3. **System Converts to POI Queries**:
   - `"gas station near Columbus, OH, USA"`
   - `"gas station near North Platte, NE, USA"`
4. **Apple Maps Finds Actual POIs**:
   - Searches for real gas stations near those locations
   - Creates route with waypoints at actual businesses
5. **UI Displays**:
   - Terminal: Clickable URL, auto-opens Maps
   - Web: Formatted route with clickable URL

## Key Components

### LLM Reasoning (`_calculate_stop_points_with_llm`)
- Understands what "fuel stops" means (actual gas stations)
- Understands what "food stops" means (actual restaurants)
- Reasons about optimal locations (distance, highway access, refueling ranges)
- **NO hardcoded knowledge** - uses LLM's geographic understanding

### POI Integration (`_find_pois_via_applescript`)
- Converts city suggestions to POI search queries
- `"gas station near City, State"` → Apple Maps finds actual businesses
- Can be extended to use AppleScript for real POI discovery

### URL Generation (`_generate_apple_maps_url`)
- Creates Apple Maps URLs with POI queries as waypoints
- Format: `https://maps.apple.com/?saddr=ORIGIN&daddr=POI_QUERY&daddr=DEST`

### UI Integration
- **Terminal**: Extracts URL, converts format, displays clickable link, auto-opens
- **Web**: Formats route, displays clickable URL, auto-detects Maps URLs

## Example

**Input**: "Plan trip from LA to San Diego with 2 fuel stops"

**LLM Output**:
```json
[
  {"location": "Irvine, CA", "type": "fuel", "reasoning": "~40 miles from LA, major highway intersection"},
  {"location": "Oceanside, CA", "type": "fuel", "reasoning": "~90 miles from LA, good spacing"}
]
```

**POI Queries**:
```
"gas station near Irvine, CA, USA"
"gas station near Oceanside, CA, USA"
```

**Maps URL**:
```
https://maps.apple.com/?saddr=Los%20Angeles%2C%20CA
&daddr=gas%20station%20near%20Irvine%2C%20CA%2C%20USA
&daddr=gas%20station%20near%20Oceanside%2C%20CA%2C%20USA
&daddr=San%20Diego%2C%20CA
&dirflg=d
```

**Result**: Apple Maps opens with route showing actual gas stations along the way

## Architecture Principles

1. **LLM-Driven**: All location decisions by LLM reasoning
2. **Agent-Driven**: Uses agent tools (Maps automation, URL generation)
3. **POI-Focused**: Finds actual businesses, not just cities
4. **Configurable**: All parameters from `config.yaml`
5. **UI-Agnostic**: Works in terminal and web UI
6. **Extensible**: Easy to add stop types, filters, optimizations

## Files

- `src/agent/maps_agent.py` - LLM reasoning + POI integration
- `src/automation/maps_automation.py` - Apple Maps AppleScript integration
- `main.py` - Terminal UI with URL extraction/display
- `api_server.py` - Web UI with result formatting
- `frontend/components/MessageBubble.tsx` - Frontend URL detection/rendering

## Testing Checklist

- [ ] LLM suggests different stops for different routes (not hardcoded)
- [ ] POI queries include "gas station" or "restaurant" keywords
- [ ] URLs work in both terminal and web UI
- [ ] Maps opens automatically with correct route
- [ ] No hardcoded cities or routes in code
- [ ] All parameters come from config

## Future Enhancements

1. Use AppleScript to get actual POI names/addresses (not just search queries)
2. Filter POIs by ratings, hours, amenities
3. LLM optimizes stop order
4. Check POI availability at departure time
5. Suggest alternative routes

