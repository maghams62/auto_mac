## Maps Agent Tool Selection Decision Tree

### When to Use Each Tool

**Use `plan_trip_with_stops` when:**
- ✅ User wants to plan a trip with stops
- ✅ User specifies number of fuel/food stops needed
- ✅ You need LLM to suggest optimal stop locations
- ✅ User provides origin and destination

**Use `open_maps_with_route` when:**
- ✅ Route and stops are already known/determined
- ✅ User wants to open Maps with specific waypoints
- ✅ You have a pre-planned route to display

### Parameter Extraction Guide

**Origin/Destination:**
- Extract from query: "from X to Y" → `origin: "X"`, `destination: "Y"`
- Handle abbreviations: "LA" → "Los Angeles, CA", "NYC" → "New York, NY"
- International: "London" → "London, UK", "Paris" → "Paris, France"

**Fuel Stops:**
- "3 fuel stops" → `num_fuel_stops: 3`
- "2 gas stops" → `num_fuel_stops: 2`
- "one fuel stop" → `num_fuel_stops: 1`
- "no fuel stops" → `num_fuel_stops: 0`

**Food Stops:**
- "breakfast and lunch" → `num_food_stops: 2`
- "breakfast, lunch, and dinner" → `num_food_stops: 3`
- "a lunch stop" → `num_food_stops: 1`
- "no food stops" → `num_food_stops: 0`

**Departure Time:**
- "leaving at 8 AM" → `departure_time: "8:00 AM"`
- "departure at 7:30 PM" → `departure_time: "7:30 PM"`
- "tomorrow at 6 AM" → `departure_time: "6:00 AM"` (or parse relative date)
- Flexible format parsing supported

**Maps Service:**
- Default: `use_google_maps: false` (Apple Maps)
- If user says "Google Maps" → `use_google_maps: true`
- If user says "Apple Maps" → `use_google_maps: false` (explicit)

**Auto-Open:**
- Default: `open_maps: true` (opens automatically)
- If user says "give me the link" → `open_maps: false`
- If user says "open it in Maps" → `open_maps: true`
- If user says "show me the route" → `open_maps: true`

### Common Patterns

**Simple Trip:**
```
plan_trip_with_stops(origin, destination, num_fuel_stops=X, open_maps=true)
```

**Trip with Food:**
```
plan_trip_with_stops(origin, destination, num_food_stops=X, open_maps=true)
```

**Complex Trip:**
```
plan_trip_with_stops(origin, destination, num_fuel_stops=X, num_food_stops=Y, departure_time="...", open_maps=true)
```

**Open Existing Route:**
```
open_maps_with_route(origin, destination, stops=[...], start_navigation=false)
```

---
