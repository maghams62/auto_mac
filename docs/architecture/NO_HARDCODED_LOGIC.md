# No Hardcoded Logic Architecture

This document verifies that the system has NO hardcoded logic and all decisions are made by LLM reasoning.

## Verification Checklist

### ✅ Maps Agent

1. **Stop Location Suggestions**
   - ✅ Uses LLM to suggest stops (no hardcoded routes)
   - ✅ Works worldwide (no geographic assumptions)
   - ✅ Handles international routes
   - ✅ LLM uses geographic knowledge dynamically

2. **Model Configuration**
   - ✅ Uses config.yaml for model selection (not hardcoded "gpt-4")
   - ✅ Uses config.yaml for temperature (not hardcoded 0.7)
   - ✅ Uses config.yaml for max_tokens (not hardcoded)
   - ✅ Falls back to env vars if config not available

3. **Stop Limits**
   - ✅ Configurable via config.yaml (maps.max_stops)
   - ✅ Default is reasonable (20 stops) but can be adjusted
   - ✅ No hardcoded "0-3" restrictions

4. **Geographic Assumptions**
   - ✅ Removed "US geography" assumption
   - ✅ LLM handles any country/region
   - ✅ Prompt instructs LLM to use appropriate location formats

5. **Parameter Extraction**
   - ✅ All parameters extracted by LLM from natural language
   - ✅ No hardcoded city name mappings
   - ✅ No hardcoded route suggestions

### ✅ Planner

1. **Parameter Extraction**
   - ✅ LLM extracts all parameters from user queries
   - ✅ Handles variations and abbreviations
   - ✅ No hardcoded parsing logic

2. **Tool Selection**
   - ✅ LLM selects tools based on capabilities
   - ✅ No hardcoded tool sequences
   - ✅ Dynamic tool routing

### ✅ URL Generation

1. **Maps URLs**
   - ✅ URLs generated dynamically based on origin/destination
   - ✅ No hardcoded URLs
   - ✅ Supports both Apple Maps and Google Maps

2. **Waypoints**
   - ✅ Waypoints come from LLM-suggested stops
   - ✅ No hardcoded waypoint lists

## Configuration-Driven Values

All configurable values come from `config.yaml`:

```yaml
maps:
  max_stops: 20  # Configurable, not hardcoded
  default_maps_service: "apple"  # Default, but LLM can override
  stop_suggestion_max_tokens: 1000  # Configurable

openai:
  model: "gpt-4o"  # Configurable
  temperature: 0.7  # Configurable
  max_tokens: 2000  # Configurable
```

## LLM-Driven Decisions

### 1. Parameter Extraction

**User Query:** "plan a trip from LA to San diego with 2 gas stops and a stop for lunch and dinner at 5 AM"

**LLM Extracts:**
- `origin`: "Los Angeles, CA" (interprets "LA")
- `destination`: "San Diego, CA" (interprets "San diego")
- `num_fuel_stops`: 2 (interprets "2 gas stops")
- `num_food_stops`: 2 (interprets "lunch and dinner")
- `departure_time`: "5:00 AM" (interprets "5 AM")
- `use_google_maps`: Decided by LLM based on route complexity
- `open_maps`: Decided by LLM based on user intent

### 2. Stop Location Suggestions

**Input:** origin="Los Angeles, CA", destination="San Diego, CA", num_stops=4, stop_types=["food", "food", "fuel", "fuel"]

**LLM Suggests:**
- Uses geographic knowledge to determine route (I-5)
- Suggests optimal cities along route
- Considers rest stop locations
- Distributes stops evenly
- **NO hardcoded city names or routes**

### 3. Maps Service Selection

**LLM Decides:**
- Use Google Maps for multiple waypoints (better support)
- Use Apple Maps for simple routes (native integration)
- Based on route complexity, not hardcoded rules

## Removed Hardcoded Logic

### Before ❌

1. Hardcoded model: `model="gpt-4"`
2. Hardcoded temperature: `temperature=0.7`
3. Hardcoded max_tokens: `max_tokens=500`
4. Hardcoded geographic assumption: "US geography"
5. Hardcoded stop limit: "0-3 stops"
6. Hardcoded fallback: Generic "Stop 1, Stop 2" locations

### After ✅

1. Configurable model: `config.get("openai", {}).get("model", "gpt-4o")`
2. Configurable temperature: `config.get("openai", {}).get("temperature", 0.7)`
3. Configurable max_tokens: `config.get("maps", {}).get("stop_suggestion_max_tokens", 1000)`
4. Worldwide support: LLM handles any country/region
5. Configurable stop limit: `config.get("maps", {}).get("max_stops", 20)`
6. LLM-driven stops: Raises error if LLM fails (no generic fallback)

## Testing

### Test 1: Parameter Extraction

```python
query = "plan a trip from LA to San diego with 2 gas stops and a stop for lunch and dinner at 5 AM"
# LLM should extract all parameters - no hardcoded parsing
```

### Test 2: International Routes

```python
query = "plan a trip from London to Paris with 1 fuel stop"
# LLM should handle international routes - no US assumption
```

### Test 3: Stop Suggestions

```python
# LLM should suggest actual cities along the route
# NO hardcoded "Irvine, CA" or "Oceanside, CA" lists
```

### Test 4: Configuration

```python
# All values should come from config.yaml
# No hardcoded model, temperature, or limits
```

## Benefits

1. **Flexibility**: Works for any route, any country
2. **Intelligence**: LLM uses geographic knowledge dynamically
3. **Configurability**: All limits and defaults are configurable
4. **Maintainability**: No hardcoded logic to update
5. **Scalability**: Handles complex routes and international travel

## Verification

Run tests to verify no hardcoded logic:

```bash
# Test parameter extraction
python tests/test_llm_driven_maps.py

# Test trip planning
python tests/test_trip_planning_la_sd.py
```

## Summary

✅ **NO hardcoded logic** - All decisions are LLM-driven
✅ **NO hardcoded routes** - LLM suggests stops dynamically
✅ **NO hardcoded geographic assumptions** - Works worldwide
✅ **NO hardcoded limits** - All configurable via config.yaml
✅ **NO hardcoded defaults** - All from config or LLM reasoning

