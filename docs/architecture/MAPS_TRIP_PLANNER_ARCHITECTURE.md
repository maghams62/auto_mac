# Maps Trip Planner Architecture - LLM & Agent-Driven Design

## Overview

The Maps Trip Planner enables users to plan road trips with fuel and food stops via:
- **Slash command**: `/maps plan a trip from LA to San Diego with 2 fuel stops and 1 breakfast stop`
- **Natural language**: "Plan a trip from LA to San Diego with two fuel stops and one breakfast stop"

## Core Principle: LLM & Agent-Driven, Zero Hardcoding

### ❌ What We DON'T Do (Hardcoded Approach)

```python
# BAD: Hardcoded cities/routes
if origin == "LA" and destination == "San Diego":
    stops = ["Irvine, CA", "Oceanside, CA"]  # Hardcoded!
```

### ✅ What We DO (LLM & Agent-Driven Approach)

```python
# GOOD: LLM reasons about optimal stops
LLM analyzes:
- Route distance and highway system
- Typical refueling ranges (200-300 miles)
- Meal timing and spacing
- Geographic knowledge of the region
- Actual road network

Then:
- Creates POI search queries for ACTUAL gas stations/restaurants
- Uses Apple Maps to find real businesses
- No hardcoded cities or routes
```

## Architecture Flow

### 1. User Intent → LLM Reasoning

**User says**: "Plan a trip from New York to San Francisco with 2 fuel stops"

**LLM reasons**:
- "fuel stops" = user needs to refuel vehicle → requires ACTUAL gas stations
- Route: ~2,900 miles (NYC to SF)
- Optimal spacing: ~1,450 miles apart for 2 stops
- Considers: I-80 route, major cities along highway, gas station availability
- Suggests: "Columbus, OH" and "North Platte, NE" as optimal areas

**Key**: LLM uses geographic knowledge, NOT hardcoded routes

### 2. LLM Suggestions → POI Search Queries

**LLM suggests**: `["Columbus, OH, USA", "North Platte, NE, USA"]`

**System converts to POI queries**:
- `"gas station near Columbus, OH, USA"`
- `"gas station near North Platte, NE, USA"`

**Why**: We need prompts that steer Apple Maps toward ACTUAL gas stations, not just city centroids. The agent currently returns search queries that Apple Maps resolves to real businesses when the route opens.

### 3. POI Queries → Apple Maps Integration

**Apple Maps URLs**:
```
https://maps.apple.com/?saddr=New%20York%2C%20NY
&daddr=gas%20station%20near%20Columbus%2C%20OH%2C%20USA
&daddr=gas%20station%20near%20North%20Platte%2C%20NE%2C%20USA
&daddr=San%20Francisco%2C%20CA
&dirflg=d
```

**Apple Maps**:
- When opened, resolves each search query into nearby gas stations
- Finds real businesses along the route dynamically
- Creates a route with waypoints using those results (or the closest matches it can identify)
- If Google Maps is requested, we build the same waypoint list with a Google Maps URL instead

### 4. Result → UI Display

**Terminal UI**:
- Extracts Maps URL from nested results
- Converts `maps://` to `https://maps.apple.com/`
- Fixes URL format (handles `via` parameter issues)
- Displays clickable URL
- Attempts to open the route via `open <url>` as a safety net (the agent already tries earlier)

**Web UI**:
- Formats Maps results with route summary
- Displays clickable URL in frontend
- Auto-detects Maps URLs, renders them as links, and opens in a new tab when clicked

## Key Components

### 1. LLM Reasoning (`_calculate_stop_points_with_llm`)

**Responsibilities**:
- Understands what "fuel stops" means (actual gas stations)
- Understands what "food stops" means (actual restaurants)
- Reasons about optimal locations based on:
  - Driving distance
  - Highway/road network
  - Typical refueling ranges
  - Meal timing
  - Geographic knowledge

**NO hardcoded**:
- Cities
- Routes
- Distances
- Stop locations

**Everything is LLM-reasoned**:
```python
prompt = f"""You are a travel route planning expert...

CRITICAL: Understand what each stop type means:
- "fuel" means the user needs to refuel their vehicle - suggest locations 
  where they can find ACTUAL GAS STATIONS
- "food" means the user needs to eat - suggest locations where they can 
  find ACTUAL RESTAURANTS

Requirements:
- Reason about the route: What highways/roads connect these locations?
- For FUEL stops: Suggest locations where gas stations are readily available
- Distribute stops evenly based on driving distance
- Consider typical refueling ranges (every 200-300 miles)
..."""
```

### 2. POI Search Integration (`_find_pois_via_applescript`)

**Responsibilities**:
- Converts city suggestions to POI search queries
- Creates queries like "gas station near City, State"
- Returns search-query strings (e.g., `"gas station near Bakersfield, CA, USA"`) that Apple Maps resolves at runtime
- Provides the hook we will extend with deeper AppleScript-powered POI discovery

**Current Implementation**:
```python
def _find_pois_via_applescript(location: str, poi_type: str) -> Optional[str]:
    # Map stop types to search queries
    search_queries = {
        "fuel": ["gas station", "fuel", "gas", "petrol"],
        "food": ["restaurant", "food", "dining"]
    }
    
    # Create POI search query
    query = search_queries.get(poi_type.lower(), [poi_type])[0]
    return f"{query} near {location}"
```

**Future Enhancement**:
- Use AppleScript (via `MapsAutomation`) to query Maps ahead of opening the URL
- Fetch real POI names and addresses for each stop
- Return actual business locations, not just search-query strings

### 3. URL Generation (`_generate_apple_maps_url`)

**Responsibilities**:
- Creates Apple Maps URLs with repeated `daddr` waypoints
- Reuses POI search queries as waypoints
- Generates Google Maps URLs when `use_google_maps=True`

**Format**:
```
https://maps.apple.com/
?saddr=ORIGIN
&daddr=POI_QUERY_1
&daddr=POI_QUERY_2
&daddr=DESTINATION
&dirflg=d
```

### 4. AppleScript Automation (`MapsAutomation`)

**Responsibilities**:
- Uses `osascript` to execute `open location "https://maps.apple.com/..."` so the Maps app opens natively
- Adds waypoints (and can optionally start navigation) inside Apple Maps
- Falls back to the standard `open` shell command if AppleScript fails
- Keeps macOS-specific logic isolated from the core agent planning code
- Exposed via the standalone `open_maps_with_route` tool for workflows that only need to launch Maps

```python
result = maps_automation.open_directions(
    origin=origin,
    destination=destination,
    stops=stop_locations_list,
    start_navigation=False
)
```

If the automation runs successfully, Maps opens with the route preloaded; otherwise we still launch the generated URL.
`plan_trip_with_stops` calls this helper whenever `open_maps=True`, so automation happens before the UI layer gets the response.

### 5. Planner Output (`plan_trip_with_stops`)

**Returned fields**:
- `maps_url` – always `https://maps.apple.com/...` when using Apple Maps (or a Google Maps directions URL if `use_google_maps=True`)
- `maps_service` – `"Apple Maps"` or `"Google Maps"` so clients know which URL was produced
- `maps_opened` – boolean flag indicating whether automation successfully launched the route
- `message` – short human-friendly summary that already contains the clickable URL
- `origin`, `destination`, `departure_time` – echoed back for UI display
- `num_fuel_stops`, `num_food_stops`, `total_stops` – counts for downstream validation

**Stop metadata** (each entry in `stops`):
- `location` – POI search query such as `"gas station near Bakersfield, CA, USA"`
- `original_location` – raw city/area suggested by the LLM before POI enrichment
- `type` – `"fuel"` or `"food"` (matches the requested order)
- `reasoning` – concise explanation of why the location works
- `order` – 1-based ordering so the UI can label Stop 1, Stop 2, etc.

### 6. UI Integration

**Terminal UI** (`main.py`):
- Extracts Maps URLs from nested `results` structure
- Converts `maps://` to `https://maps.apple.com/`
- Fixes URL format (handles `via` parameter issues)
- Displays clickable Rich link
- Auto-opens Maps using `subprocess.run(["open", url])`

**Web UI** (`api_server.py`):
- Formats Maps results with route summary
- Extracts Maps URLs from nested results
- Sends formatted message to frontend

**Frontend** (`MessageBubble.tsx`):
- Auto-detects Maps URLs in messages
- Renders as clickable links
- Opens in Maps app when clicked

## Example Flow

### User Request
```
"Plan a trip from Los Angeles to San Francisco with 2 fuel stops"
```

### Step 1: LLM Reasoning
```json
{
  "location": "Bakersfield, CA, USA",
  "type": "fuel",
  "reasoning": "Approximately 100 miles from LA, major highway intersection with gas stations"
},
{
  "location": "Kettleman City, CA, USA",
  "type": "fuel",
  "reasoning": "Approximately halfway point, known rest stop area with multiple gas stations"
}
```

### Step 2: POI Query Creation
```python
"gas station near Bakersfield, CA, USA"
"gas station near Kettleman City, CA, USA"
```

In the returned payload, these appear as the `location` field while `original_location` keeps `"Bakersfield, CA, USA"` and `"Kettleman City, CA, USA"` along with the stop `order` and LLM `reasoning`.

### Step 3: URL Generation
```
https://maps.apple.com/?saddr=Los%20Angeles%2C%20CA
&daddr=gas%20station%20near%20Bakersfield%2C%20CA%2C%20USA
&daddr=gas%20station%20near%20Kettleman%20City%2C%20CA%2C%20USA
&daddr=San%20Francisco%2C%20CA
&dirflg=d
```

### Step 4: UI Display
- Terminal: Shows the "Here's your trip..." message, clickable URL, and runs `open <url>` as a fallback
- Web: Shows the same short message with a clickable URL

## Configuration

All parameters come from `config.yaml`:
```yaml
maps:
  max_stops: 20  # Maximum stops supported
  default_maps_service: "apple"  # Prefer Apple Maps URLs (set to "google" for Google by default)
  stop_suggestion_max_tokens: 1000  # LLM token limit for stop suggestions

openai:
  model: "gpt-4o"  # LLM model for reasoning
  temperature: 0.7  # LLM temperature
  max_tokens: 2000  # LLM max tokens
```

**NO hardcoded values** - everything is configurable.

## Testing

### Verify LLM Reasoning
```python
# Test that LLM suggests different stops for different routes
result1 = plan_trip_with_stops("NYC", "Miami", num_fuel_stops=2)
result2 = plan_trip_with_stops("NYC", "Seattle", num_fuel_stops=2)

# Stops should be different (different routes)
assert result1["stops"] != result2["stops"]
```

### Verify POI Integration
```python
# Test that stops include POI queries
result = plan_trip_with_stops("LA", "SF", num_fuel_stops=2)
for stop in result["stops"]:
    assert "gas station" in stop["location"].lower() or "near" in stop["location"].lower()
```

### Verify UI Integration
```python
# Test that URLs are extracted and displayed
# Terminal UI should show clickable URL and attempt an `open <url>` fallback
# Web UI should show the short "Here's your trip..." message with link
# maps_opened flag tells us if automation launched the route successfully
```

### Verify Response Metadata
```python
result = plan_trip_with_stops("LA", "SF", num_fuel_stops=2)
first_stop = result["stops"][0]
assert "original_location" in first_stop
assert "order" in first_stop and first_stop["order"] == 1
assert result["maps_service"] in {"Apple Maps", "Google Maps"}
```

## Future Enhancements

1. **Actual POI Discovery**: Use AppleScript to query Maps app for real POI names/addresses
2. **POI Filtering**: Filter by ratings, hours, amenities (24-hour gas stations, etc.)
3. **Route Optimization**: LLM reasons about optimal stop order
4. **Real-time Availability**: Check if POIs are open at departure time
5. **Alternative Routes**: LLM suggests alternative routes with different stops

## Key Takeaways

1. **LLM-Driven**: All location decisions made by LLM reasoning, not hardcoded
2. **Agent-Driven**: Uses agent tools (Maps automation, URL generation) - no hardcoded logic
3. **POI-Focused**: Finds actual gas stations/restaurants, not just cities
4. **Configurable**: All parameters from config, no hardcoded values
5. **UI-Agnostic**: Works in terminal and web UI
6. **Extensible**: Easy to add new stop types, filters, optimizations

## Anti-Patterns to Avoid

❌ **Hardcoded Routes**:
```python
if origin == "LA" and destination == "SF":
    stops = ["Bakersfield", "Kettleman City"]  # BAD!
```

❌ **Hardcoded Distances**:
```python
if distance > 500:
    num_stops = 2  # BAD! Should be LLM-reasoned
```

❌ **Hardcoded Cities**:
```python
fuel_stops = ["Irvine", "Oceanside"]  # BAD! Should be LLM-suggested
```

✅ **LLM Reasoning**:
```python
# LLM reasons about route, distance, highway access, etc.
# Suggests optimal locations
# System converts to POI queries
# Maps finds actual businesses
```
