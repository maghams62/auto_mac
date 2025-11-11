# Maps URL Guide

## Overview

The trip planning system **ALWAYS provides a Maps URL** that you can use to view the route. You can either:
1. **Use the URL manually** - Copy and paste it into your browser or Maps app
2. **Open automatically** - Set `open_maps=true` to have the system open Maps for you

## How It Works

### 1. Trip Planning Returns URL

When you use `plan_trip_with_stops`, the response **always includes** a `maps_url` field:

```python
result = plan_trip_with_stops(
    origin="Los Angeles, CA",
    destination="San Diego, CA",
    num_fuel_stops=2,
    num_food_stops=2,
    departure_time="5:00 AM"
)

# The URL is always in the response
maps_url = result["maps_url"]
print(f"Maps URL: {maps_url}")
```

### 2. URL Types

**Apple Maps URL** (default):
- Format: `maps://?saddr=...&daddr=...`
- Opens in: macOS Maps app
- Use when: You want native macOS integration

**Google Maps URL** (set `use_google_maps=true`):
- Format: `https://www.google.com/maps/dir/?api=1&origin=...&destination=...&waypoints=...`
- Opens in: Web browser
- Use when: You need better waypoint support for multiple stops

### 3. Automatic Opening (Optional)

You can set `open_maps=true` to automatically open Maps:

```python
result = plan_trip_with_stops(
    origin="Los Angeles, CA",
    destination="San Diego, CA",
    num_fuel_stops=2,
    num_food_stops=2,
    departure_time="5:00 AM",
    open_maps=True  # Automatically opens Maps app/browser
)
```

The response will include:
- `maps_url`: The URL (always provided)
- `maps_opened`: `true` if Maps was successfully opened
- `message`: Includes status about Maps opening

## Example Responses

### With URL Only (default)

```json
{
  "origin": "Los Angeles, CA",
  "destination": "San Diego, CA",
  "stops": [...],
  "maps_url": "maps://?saddr=Los+Angeles%2C+CA&daddr=San+Diego%2C+CA&dirflg=d",
  "maps_service": "Apple Maps",
  "maps_opened": false,
  "message": "Trip planned from Los Angeles, CA to San Diego, CA with 2 food stop(s) and 2 fuel stop(s): ... Maps URL: maps://?..."
}
```

### With Automatic Opening

```json
{
  "origin": "Los Angeles, CA",
  "destination": "San Diego, CA",
  "stops": [...],
  "maps_url": "maps://?saddr=Los+Angeles%2C+CA&daddr=San+Diego%2C+CA&dirflg=d",
  "maps_service": "Apple Maps",
  "maps_opened": true,
  "message": "Trip planned from Los Angeles, CA to San Diego, CA with 2 food stop(s) and 2 fuel stop(s): ... Apple Maps opened with route."
}
```

## Using the URL

### Option 1: Copy and Paste

1. Get the `maps_url` from the response
2. Copy it
3. Paste into:
   - Browser address bar (for Google Maps URLs)
   - Maps app (for Apple Maps URLs)
   - Or use: `open <maps_url>` in terminal

### Option 2: Programmatic Opening

```python
import subprocess

# Open Apple Maps URL
subprocess.run(["open", maps_url])

# Or open in default browser (for Google Maps)
subprocess.run(["open", google_maps_url])
```

### Option 3: Automatic Opening

Set `open_maps=True` when calling the tool - Maps will open automatically.

## Natural Language Queries

The LLM planner can interpret requests to open Maps:

- "plan a trip and open it in Maps" → `open_maps=true`
- "plan a trip and show me the route" → `open_maps=true`
- "plan a trip and give me the link" → `open_maps=false` (just return URL)

## Best Practices

1. **Always check for `maps_url`** - It's always provided, even if Maps opening fails
2. **Use Google Maps for multiple stops** - Better waypoint support
3. **Use Apple Maps for native integration** - Opens directly in Maps app
4. **Handle opening failures gracefully** - The URL is still available even if auto-opening fails

## Troubleshooting

### Maps doesn't open automatically

- Check that `maps_opened` is `false` in the response
- The `maps_url` is still available - you can open it manually
- Try using `open_maps_with_route` tool separately

### URL doesn't work

- Apple Maps URLs require macOS Maps app
- Google Maps URLs work in any browser
- Check that the URL is properly encoded

### Multiple stops not showing

- Use `use_google_maps=true` for better waypoint support
- Google Maps handles multiple waypoints better than Apple Maps URLs

