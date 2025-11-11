# LLM-Driven Decisions Architecture

This document describes how the system ensures all decisions are made by the LLM, with no hardcoded logic.

## Core Principles

1. **No Hardcoded Values**: All parameter extraction and decision-making is performed by LLM reasoning
2. **Natural Language Understanding**: The system interprets user queries using LLM to extract parameters
3. **Dynamic Stop Suggestions**: Route stops are suggested by LLM based on geographic knowledge, not hardcoded lists
4. **Flexible Parameter Parsing**: Handles variations, abbreviations, and different phrasings

## Architecture Flow

### 1. User Query → Planner (LLM)

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

### 2. Planner → Tool Execution

```
Planner creates plan:
{
  "action": "plan_trip_with_stops",
  "parameters": {
    "origin": "Los Angeles, CA",  // Extracted by LLM
    "destination": "San Diego, CA",  // Extracted by LLM
    "num_fuel_stops": 2,  // Extracted by LLM
    "num_food_stops": 2,  // Extracted by LLM
    "departure_time": "5:00 AM",  // Extracted by LLM
    "use_google_maps": true  // Decided by LLM (better waypoint support)
  }
}
```

### 3. Maps Agent → Stop Location LLM

```
Maps Agent calls LLM to suggest stops:
Input: origin="Los Angeles, CA", destination="San Diego, CA", 
       num_stops=4, stop_types=["food", "food", "fuel", "fuel"]
         ↓
    Stop Location LLM uses geographic knowledge to suggest:
    - Optimal cities/towns along I-5 route
    - Evenly distributed stops
    - Cities with gas stations and restaurants
    - Actual locations like "Irvine, CA", "Oceanside, CA", etc.
```

## Key Components

### Planner (src/orchestrator/planner.py)

**Responsibilities:**
- Parse natural language queries using LLM reasoning
- Extract all parameters from user's query text
- Handle variations and abbreviations
- Create execution plans with extracted parameters

**LLM Prompts:**
- Emphasize extracting ALL parameters from natural language
- Provide examples of parameter extraction
- Instruct to handle variations and abbreviations

### Maps Agent (src/agent/maps_agent.py)

**Responsibilities:**
- Receive parameters from planner
- Use LLM to suggest optimal stop locations
- Generate Maps URLs with waypoints
- No hardcoded routes or stop locations

**LLM Integration:**
- `_calculate_stop_points_with_llm()` uses GPT-4 to suggest stops
- LLM uses geographic knowledge to determine optimal locations
- No fallback to hardcoded locations (raises error instead)

### Tool Definitions (prompts/tool_definitions.md)

**Responsibilities:**
- Document parameter extraction guidelines
- Provide examples of LLM-driven extraction
- Emphasize no hardcoded values

## Parameter Extraction Examples

### City Name Variations

| User Input | LLM Extracts |
|------------|--------------|
| "LA" | "Los Angeles, CA" |
| "San diego" | "San Diego, CA" |
| "SF" | "San Francisco, CA" |
| "NYC" | "New York, NY" |

### Stop Count Extraction

| User Input | LLM Extracts |
|------------|--------------|
| "2 gas stops" | num_fuel_stops=2 |
| "two fuel stops" | num_fuel_stops=2 |
| "a gas stop" | num_fuel_stops=1 |
| "lunch and dinner" | num_food_stops=2 |
| "breakfast, lunch, and dinner" | num_food_stops=3 |

### Time Format Parsing

| User Input | LLM Extracts |
|------------|--------------|
| "5 AM" | "5:00 AM" |
| "7:30 PM" | "7:30 PM" |
| "noon" | "12:00 PM" |
| "midnight" | "12:00 AM" |

## Error Handling

### LLM Failure Scenarios

1. **Stop Location LLM Fails**:
   - System raises exception (no hardcoded fallback)
   - Orchestrator can retry or report error to user
   - Maintains LLM-driven approach

2. **Parameter Extraction Fails**:
   - Planner can ask for clarification
   - Replanning loop handles errors
   - No assumptions or defaults

## Testing

### Test Queries

```python
# Test 1: Abbreviations
"plan a trip from LA to SD with 2 gas stops"

# Test 2: Natural language variations
"plan a trip from Los Angeles to San Diego with two fuel stops and lunch and dinner"

# Test 3: Time variations
"plan a trip from LA to San diego with 2 gas stops and a stop for lunch and dinner at 5 AM"

# Test 4: Different phrasings
"I need to drive from LA to San Diego. I'll need 2 gas stops and want to stop for lunch and dinner. Leaving at 5 AM."
```

## Benefits

1. **Flexibility**: Handles user queries in various formats
2. **Accuracy**: LLM understands context and variations
3. **Maintainability**: No hardcoded logic to update
4. **Scalability**: Works for any route, not just common ones
5. **Intelligence**: LLM uses geographic knowledge for optimal stops

## Future Enhancements

1. **Multi-language Support**: LLM can handle queries in different languages
2. **Context Awareness**: LLM can consider user preferences and history
3. **Dynamic Routing**: LLM can suggest routes based on traffic, weather, etc.
4. **Personalization**: LLM can learn user preferences over time

