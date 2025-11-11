# LLM-Driven Architecture Changes

## Summary

All hardcoded logic has been removed and replaced with LLM-driven decision-making. The system now uses LLM reasoning for all parameter extraction and route planning decisions.

## Changes Made

### 1. Maps Agent (src/agent/maps_agent.py)

**Before:**
- Had hardcoded fallback logic that created generic stop descriptions if LLM failed

**After:**
- Removed hardcoded fallback
- Raises exception if LLM fails (maintains LLM-driven approach)
- All stop locations are suggested by LLM using geographic knowledge

**Key Change:**
```python
# Before: Hardcoded fallback
fallback_stops = [{"location": f"Stop {i+1} along route...", "type": stop_type}]
return fallback_stops

# After: LLM-driven only
raise Exception(f"Failed to calculate stop locations using LLM: {e}...")
```

### 2. Planner (src/orchestrator/planner.py)

**Enhanced Prompts:**
- Added explicit instructions for LLM-driven parameter extraction
- Emphasizes extracting ALL parameters from natural language queries
- Provides examples of parameter extraction patterns
- Instructs LLM to handle variations and abbreviations

**Key Additions:**
- Parameter extraction guidelines in system prompt
- Examples of how to interpret variations ("LA" → "Los Angeles, CA")
- Instructions to parse time formats, stop counts, meal requests

### 3. Tool Definitions (prompts/tool_definitions.md)

**Added:**
- Parameter extraction section for `plan_trip_with_stops`
- Examples of LLM-driven extraction patterns
- Guidelines for handling variations and abbreviations
- Emphasis on NO hardcoded values

### 4. Tools Catalog (src/orchestrator/tools_catalog.py)

**Added:**
- `plan_trip_with_stops` tool specification
- `open_maps_with_route` tool specification
- Descriptions emphasize LLM-driven approach
- Notes about NO hardcoded routes or stops

### 5. Orchestrator Prompts (src/orchestrator/prompts.py)

**Enhanced:**
- Added LLM-driven parameter extraction to critical rules
- Provided example of parameter extraction
- Emphasized handling variations and abbreviations

## LLM-Driven Flow

### 1. User Query → Planner LLM
```
User: "plan a trip from LA to San diego with 2 gas stops and a stop for lunch and dinner at 5 AM"
         ↓
Planner LLM extracts:
- origin: "Los Angeles, CA" (interprets "LA")
- destination: "San Diego, CA" (interprets "San diego")
- num_fuel_stops: 2 (interprets "2 gas stops")
- num_food_stops: 2 (interprets "lunch and dinner")
- departure_time: "5:00 AM" (interprets "5 AM")
```

### 2. Planner → Maps Agent
```
Maps Agent receives parameters:
- origin, destination, num_fuel_stops, num_food_stops, departure_time
```

### 3. Maps Agent → Stop Location LLM
```
Stop Location LLM suggests optimal stops:
- Uses geographic knowledge
- Considers route (I-5 for LA to San Diego)
- Suggests actual cities/towns
- Distributes stops evenly
- NO hardcoded routes or locations
```

## Testing

### New Tests Created

1. **test_trip_planning_la_sd.py**
   - Tests LA to San Diego trip with specific requirements
   - Verifies LLM parameter extraction
   - Tests via orchestrator with natural language

2. **test_llm_driven_maps.py**
   - Verifies LLM extracts all parameters from queries
   - Tests multiple query variations
   - Verifies stop locations are LLM-suggested (not hardcoded)
   - Validates no hardcoded placeholders

### Test Coverage

- ✅ Parameter extraction from natural language
- ✅ Handling of abbreviations ("LA", "SD", "NYC")
- ✅ Parsing stop counts ("2 gas stops", "one fuel stop")
- ✅ Parsing meal requests ("lunch and dinner", "breakfast")
- ✅ Time format parsing ("5 AM", "7:30 PM")
- ✅ LLM-suggested stop locations
- ✅ No hardcoded routes or locations

## Documentation

### New Documentation

1. **docs/LLM_DRIVEN_DECISIONS.md**
   - Complete architecture documentation
   - Flow diagrams
   - Parameter extraction examples
   - Error handling approach

2. **LLM_DRIVEN_CHANGES.md** (this file)
   - Summary of changes
   - Before/after comparisons
   - Testing approach

## Benefits

1. **Flexibility**: Handles user queries in various formats
2. **Intelligence**: Uses LLM's geographic knowledge for optimal stops
3. **Accuracy**: Understands context and variations
4. **Maintainability**: No hardcoded logic to update
5. **Scalability**: Works for any route, not just common ones

## Verification

To verify LLM-driven behavior:

```bash
# Test parameter extraction
python tests/test_llm_driven_maps.py

# Test trip planning
python tests/test_trip_planning_la_sd.py
```

## Future Enhancements

1. Multi-language support
2. Context awareness (user preferences, history)
3. Dynamic routing (traffic, weather considerations)
4. Personalization (learning user preferences)

## Notes

- All parameter extraction is now LLM-driven
- No hardcoded city mappings or route suggestions
- Stop locations are always suggested by LLM
- System fails gracefully if LLM cannot determine parameters (no assumptions)

