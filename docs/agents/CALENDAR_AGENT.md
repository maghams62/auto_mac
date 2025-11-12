# Calendar Agent

## Overview

The Calendar Agent provides integration with macOS Calendar.app, allowing you to read calendar events and generate intelligent meeting briefs by searching indexed documents.

## Integration Architecture

```
src/agent/
└── calendar_agent.py         → Calendar agent with tools

src/automation/
└── calendar_automation.py    → AppleScript integration with Calendar.app
```

## Calendar Tool Hierarchy

```
Calendar Tools
│
├─ LEVEL 1: Event Reading
│  ├─ list_calendar_events
│  │  ├─ Input: days_ahead (int, default: 7)
│  │  ├─ Output: events (list), count, days_ahead
│  │  └─ Purpose: Retrieve upcoming calendar events
│  │
│  └─ get_calendar_event_details
│     ├─ Input: event_title (str), start_time_window (Optional[str])
│     ├─ Output: event (dict), found (bool)
│     └─ Purpose: Get detailed information about a specific event
│
└─ LEVEL 2: Meeting Preparation
   └─ prepare_meeting_brief
      ├─ Input: event_title (str), start_time_window (Optional[str]), save_to_note (bool)
      ├─ Output: brief (str), event (dict), relevant_docs (list), talking_points (list), note_saved (bool)
      ├─ Workflow:
      │  1. Fetches event details from Calendar.app
      │  2. Uses LLM to generate semantic search queries from event metadata
      │  3. Searches indexed documents using DocumentIndexer/SemanticSearch
      │  4. Synthesizes brief with relevant docs and talking points
      │  5. Optionally saves to Notes Agent
      └─ Purpose: Generate intelligent meeting briefs by searching indexed documents
```

## Tool Details

### list_calendar_events

List upcoming calendar events from macOS Calendar.app.

**Parameters:**
- `days_ahead` (int, optional): Number of days to look ahead (default: 7, max: 30)

**Returns:**
- `events`: List of event dictionaries with title, start_time, end_time, location, notes, attendees, calendar_name, event_id
- `count`: Number of events found
- `days_ahead`: Number of days queried

**Example:**
```python
list_calendar_events(days_ahead=7)
```

### get_calendar_event_details

Get detailed information about a specific calendar event.

**Parameters:**
- `event_title` (string, required): Title/summary of event (partial match supported)
- `start_time_window` (string, optional): ISO format datetime to narrow search

**Returns:**
- `event`: Event dictionary with full details
- `found`: Boolean indicating if event was found

**Example:**
```python
get_calendar_event_details(event_title="Q4 Review", start_time_window="2024-12-20T14:00:00")
```

### prepare_meeting_brief

Generate a meeting brief by searching indexed documents for relevant information.

**How it works:**
1. Fetches event details from Calendar.app using `get_calendar_event_details`
2. Extracts event metadata: title, notes, attendees, location, start_time
3. Uses LLM (gpt-4o-mini) to generate 3-5 semantic search queries from event metadata
4. For each query, searches indexed documents using `SemanticSearch.search()`
5. Aggregates and deduplicates results by file_path
6. Uses Writing Agent's `synthesize_content()` or direct LLM call to create brief
7. Optionally saves brief to Notes Agent if `save_to_note=True`

**Parameters:**
- `event_title` (string, required): Title/summary of event to prepare for
- `start_time_window` (string, optional): ISO format datetime to narrow event search
- `save_to_note` (bool, optional): If True, save brief to Apple Notes (default: False)

**Returns:**
- `brief`: Generated meeting brief text
- `event`: Event details dictionary
- `relevant_docs`: List of relevant documents found (file_path, file_name, similarity)
- `talking_points`: List of key talking points extracted from documents
- `note_saved`: Boolean indicating if brief was saved to note
- `search_queries`: List of search queries used

**Example:**
```python
prepare_meeting_brief(event_title="Q4 Review Meeting", save_to_note=True)
```

## LLM-Driven Query Generation

The `prepare_meeting_brief` tool uses LLM to intelligently generate search queries from event metadata. This ensures no hard-coded keyword lists and adapts to different meeting types.

**Example Query Generation:**
- Event: "Q4 Review Meeting"
- Notes: "Discuss revenue, marketing strategy"
- Attendees: ["John Doe", "Jane Smith"]
- Location: "Conference Room A"

**LLM Generates Queries:**
- "Q4 revenue report"
- "marketing strategy 2024"
- "quarterly financials"
- "Q4 performance metrics"

These queries are then used to search indexed documents semantically.

## Integration Patterns

### Pattern 1: Simple Event Listing
```
User: "Show my upcoming events"
→ list_calendar_events(days_ahead=7)
→ reply_to_user
```

### Pattern 2: Event Details
```
User: "Get details for Q4 Review meeting"
→ get_calendar_event_details(event_title="Q4 Review")
→ reply_to_user
```

### Pattern 3: Meeting Brief Preparation
```
User: "Prepare a brief for Q4 Review meeting"
→ prepare_meeting_brief(event_title="Q4 Review", save_to_note=False)
→ reply_to_user
```

### Pattern 4: Brief with Note Saving
```
User: "Prep for Team Standup and save to notes"
→ prepare_meeting_brief(event_title="Team Standup", save_to_note=True)
→ reply_to_user
```

## Slash Command Support

The Calendar Agent is accessible via slash commands:

```
/calendar List my upcoming events
/calendar prep for Q4 Review meeting
/calendar brief docs for Team Standup
/calendar details for "Project Kickoff"
```

## Testing Support

For testing, the Calendar Agent supports fake data via the `CALENDAR_FAKE_DATA_PATH` environment variable:

```bash
export CALENDAR_FAKE_DATA_PATH=/path/to/fake_calendar_data.json
```

The JSON file should contain an array of event dictionaries:
```json
[
  {
    "title": "Q4 Review Meeting",
    "start_time": "2024-12-20T14:00:00",
    "end_time": "2024-12-20T15:00:00",
    "location": "Conference Room A",
    "notes": "Discuss revenue and marketing strategy",
    "attendees": ["John Doe", "Jane Smith"],
    "calendar_name": "Work",
    "event_id": "12345"
  }
]
```

## Key Features

- **No Hard-coded Filters**: All event filtering/logic driven by LLM or user parameters
- **LLM-Driven Search**: Query generation uses LLM to expand event metadata into search terms
- **Normalized Data**: All calendar data returned as structured dictionaries
- **Error Handling**: Follows existing patterns with structured error responses
- **Integration**: Leverages existing DocumentIndexer and SemanticSearch for document retrieval
- **Writing Agent**: Uses Writing Agent for brief synthesis, or lightweight prompt if unavailable

## Error Handling

All tools return structured error dictionaries:

```python
{
    "error": True,
    "error_type": "CalendarReadError" | "EventNotFound" | "BriefGenerationError",
    "error_message": "Descriptive error message",
    "retry_possible": bool
}
```

## Dependencies

- macOS Calendar.app (via AppleScript)
- DocumentIndexer (for document indexing)
- SemanticSearch (for semantic document search)
- Writing Agent (for brief synthesis, optional fallback to direct LLM)
- Notes Agent (for saving briefs, optional)

