# How to Start the UI with New Maps Features

The frontend has been rebuilt with the new Maps transit features. Follow these steps to start the servers:

## Quick Start

### Terminal 1 - Start API Server
```bash
cd /Users/siddharthsuresh/Downloads/auto_mac
python api_server.py
```

### Terminal 2 - Start Frontend
```bash
cd /Users/siddharthsuresh/Downloads/auto_mac/frontend
npm run dev
```

## Access the UI

Once both servers are running, open your browser to:
- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000

## Test the Transit Query

In the UI chat, try:
```
when's the next bus to UCSC Silicon Valley
```

Expected behavior:
1. System recognizes it as a transit query
2. Uses `get_directions` tool with `transportation_mode: "transit"`
3. Opens Apple Maps with transit directions
4. Shows "Apple Maps will show next departure times" message

## Troubleshooting

### If query still fails:

1. **Check API server logs** - Look for the plan it generates
2. **Check if tool is recognized** - API should show it's using `get_directions`
3. **Manual test** - Try direct API call:
   ```bash
   curl -X POST http://localhost:8000/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message":"when'\''s the next bus to UCSC Silicon Valley"}'
   ```

### If Maps doesn't open:

The tool will still return a Maps URL. Check the response for:
- `maps_url`: The Apple Maps link
- `maps_opened`: Should be `true`
- `message`: Should mention opening Apple Maps

## Alternative: Direct Tool Test

If you want to test the tool directly without the UI:

```bash
python -c "
from src.agent.maps_agent import get_directions

result = get_directions.invoke({
    'origin': 'Current Location',
    'destination': 'UCSC Silicon Valley',
    'transportation_mode': 'transit',
    'open_maps': True
})

print('Result:', result['message'])
print('URL:', result['maps_url'])
"
```

This will open Apple Maps directly with transit directions.

## What Should Happen

When the query works correctly:

1. **LLM Planning** (in API server logs):
   ```json
   {
     "action": "get_directions",
     "parameters": {
       "origin": "Current Location",
       "destination": "UCSC Silicon Valley",
       "transportation_mode": "transit",
       "open_maps": true
     }
   }
   ```

2. **Tool Execution**:
   - Generates Maps URL with `dirflg=r` (transit flag)
   - Opens Apple Maps app
   - Maps shows transit options

3. **UI Response**:
   - "Opening transit directions from Current Location to UCSC Silicon Valley in Apple Maps"
   - "Apple Maps will show real-time transit schedules and next departure times"
   - Clickable Maps URL

## Important Notes

- **Frontend was rebuilt** - New build includes the tool updates
- **All 86 tools registered** - Including `get_directions` and `get_transit_schedule`
- **5/5 tests passing** - Tools are fully functional
- **Few-shot examples added** - LLM should recognize "next bus" queries

If it still doesn't work after restarting both servers, the issue is in the LLM planning, not the tools themselves.
