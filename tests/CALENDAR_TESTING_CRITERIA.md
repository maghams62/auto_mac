# Calendar Summarization Testing Criteria

## Overview

This document defines the testing criteria, success metrics, and validation requirements for calendar summarization functionality. Tests use mock calendar event data to ensure consistent, reliable testing.

## Mock Data Structure

### File Location
- **Path**: `tests/fixtures/calendar_events_mock.json`
- **Format**: JSON array of calendar event objects

### Event Structure
```json
{
  "title": "Event Title",
  "start_time": "2025-11-13T10:00:00",  // ISO format datetime
  "end_time": "2025-11-13T10:30:00",    // ISO format datetime
  "location": "Location Name",           // Optional, can be null
  "attendees": ["email@example.com"],    // Optional, empty array if none
  "notes": "Event notes",                // Optional
  "calendar_name": "Work",               // Calendar name
  "event_id": "event_1"                  // Unique identifier
}
```

### Mock Data Coverage
- **Total Events**: 15 events
- **Time Range**: Spread across next 7-30 days
- **Event Types**:
  - Meeting events (with attendees)
  - Personal events (no attendees)
  - All-day events
  - Multi-day events
  - Work calendar events
  - Personal calendar events

## Test Scenarios

### C-M1: Basic Calendar Summarization

**Query**: `"summarize my calendar for the next week"`

**Test Steps**:
1. Set `CALENDAR_FAKE_DATA_PATH` environment variable
2. Call `list_calendar_events(days_ahead=7)`
3. Verify events are retrieved from mock data
4. Call `synthesize_content` with events
5. Verify summary quality

**Success Criteria**:
- ✅ Events retrieved successfully (count > 0)
- ✅ Summary length >= 200 characters
- ✅ Summary mentions at least 1 event title
- ✅ Summary includes event times
- ✅ Summary quality score >= 0.5

**Expected Output**:
- Summary contains event titles from mock data
- Summary includes dates/times
- Summary is coherent and relevant

### C-M2: Time Window Extraction

**Queries**:
- `"summarize my calendar this month"` → days_ahead=30
- `"summarize my calendar for the next week"` → days_ahead=7
- `"summarize my calendar for the next 3 days"` → days_ahead=3

**Test Steps**:
1. Create plan using orchestrator
2. Extract `days_ahead` parameter from plan
3. Verify parameter matches expected value

**Success Criteria**:
- ✅ `days_ahead` parameter extracted from query
- ✅ Parameter value matches expected (within ±2 days tolerance)
- ✅ No hardcoded values (uses LLM reasoning)

**Expected Output**:
- Plan includes `list_calendar_events` step
- `days_ahead` parameter correctly extracted
- Parameter value appropriate for query

### C-M3: Meeting-Focused Summarization

**Query**: `"summarize meetings in my calendar"`

**Test Steps**:
1. Retrieve all calendar events
2. Filter to meeting events (events with attendees)
3. Synthesize only meeting events
4. Verify summary focuses on meetings

**Success Criteria**:
- ✅ Only meeting events included in summary
- ✅ Summary mentions attendees
- ✅ Summary includes meeting-related keywords
- ✅ Summary quality score >= 0.5

**Expected Output**:
- Summary contains only meeting events
- Attendee names mentioned
- Meeting context emphasized

### C-M4: Summary Completeness

**Query**: `"summarize my calendar for the next week"`

**Test Steps**:
1. Generate comprehensive summary
2. Verify all key event details included

**Success Criteria**:
- ✅ Event titles mentioned
- ✅ Event times mentioned
- ✅ Locations mentioned (if available)
- ✅ Attendees mentioned (for meetings)
- ✅ Chronological organization
- ✅ Event coverage >= 30%

**Expected Output**:
- Complete summary with all relevant details
- Well-organized chronologically
- Covers significant portion of events

### C-M5: Empty Result Handling

**Query**: `"summarize my calendar for next year"`

**Test Steps**:
1. Request events for far future (365 days)
2. Handle empty or filtered results
3. Generate informative empty-state message

**Success Criteria**:
- ✅ Empty results handled gracefully
- ✅ Informative message generated
- ✅ Message length > 20 characters
- ✅ Message contains informative keywords

**Expected Output**:
- Clear message indicating no events found
- Helpful context about time range

## Quality Metrics

### Summary Length
- **Minimum**: 200 characters
- **Target**: 300-500 characters
- **Maximum**: No strict limit (but should be concise)

### Event Coverage
- **Minimum**: 30% of events mentioned
- **Target**: 50-70% of events mentioned
- **Note**: Not all events need to be mentioned in concise summaries

### Detail Coverage
- **Required**: Event titles, times
- **Preferred**: Locations, attendees (for meetings)
- **Optional**: Notes, calendar names

### Coherence Indicators
- Summary has structure (sentences, paragraphs)
- Not just "Here is a summary" placeholder
- Contains actual event information
- No error messages or placeholders

## LLM Reasoning Validation

### Parameter Extraction
- ✅ `days_ahead` extracted from natural language
- ✅ No hardcoded default values
- ✅ Handles variations ("this week", "next week", "7 days")

### Event Filtering
- ✅ Meeting filtering uses LLM reasoning
- ✅ Focus extraction (meetings, personal, work) uses LLM
- ✅ No hardcoded keyword matching

### Time Window Reasoning
- ✅ "this month" → ~30 days
- ✅ "next week" → ~7 days
- ✅ "next 3 days" → 3 days
- ✅ Flexible interpretation allowed (±2 days tolerance)

## Workflow Validation

### Correct Tool Chain
1. `list_calendar_events` → Retrieve events
2. `synthesize_content` → Generate summary
3. `reply_to_user` → Return summary

### Data Flow
- Events converted to JSON string before synthesis
- Empty results handled gracefully
- Error states properly handled

## Integration Testing

### Browser-Based Tests
- Use mock data via `CALENDAR_FAKE_DATA_PATH`
- Verify API responses include event content
- Check response length and quality

### Unit Tests
- Direct tool invocation with mock data
- Isolated testing of synthesis
- Quality validation

## Troubleshooting

### Common Issues

**Issue**: Summary too short (< 200 chars)
- **Cause**: Events not properly passed to synthesis
- **Fix**: Verify events JSON conversion

**Issue**: No event titles in summary
- **Cause**: Events not included in synthesis input
- **Fix**: Check `source_contents` parameter

**Issue**: Time window extraction incorrect
- **Cause**: LLM not reasoning correctly
- **Fix**: Check planner prompts and few-shot examples

**Issue**: Mock data not loading
- **Cause**: `CALENDAR_FAKE_DATA_PATH` not set or invalid path
- **Fix**: Verify environment variable and file path

### Debugging Steps

1. **Check Mock Data Loading**:
   ```python
   from fixtures.calendar_fixtures import get_mock_calendar_events
   events = get_mock_calendar_events()
   print(f"Loaded {len(events)} events")
   ```

2. **Verify Environment Variable**:
   ```python
   import os
   print(os.environ.get('CALENDAR_FAKE_DATA_PATH'))
   ```

3. **Check Event Format**:
   ```python
   from fixtures.calendar_fixtures import create_mock_calendar_response
   response = create_mock_calendar_response(days_ahead=7)
   print(json.dumps(response, indent=2))
   ```

4. **Test Synthesis Directly**:
   ```python
   from src.agent.writing_agent import synthesize_content
   events_text = json.dumps({"events": events, "count": len(events)}, indent=2)
   result = synthesize_content.invoke({
       "source_contents": [events_text],
       "topic": "Summary of calendar events",
       "synthesis_style": "concise"
   })
   ```

## Examples

### Good Summary Example
```
Your calendar for the next week includes several important meetings:

- Team Standup on November 13 at 10:00 AM in Conference Room A with Alice, Bob, and Charlie
- Product Review Meeting on November 13 at 2:00 PM via Zoom with David, Eve, and Frank
- Doctor Appointment on November 14 at 9:00 AM at Medical Center
- All Hands Meeting on November 15 at 3:00 PM in Main Auditorium

You also have personal events including lunch with Sarah on November 14 and a weekend trip starting November 20.
```

**Why it's good**:
- Mentions specific event titles
- Includes times and locations
- Mentions attendees for meetings
- Chronologically organized
- Substantial length (>200 chars)

### Bad Summary Example
```
I've summarized your calendar events for the next week.
```

**Why it's bad**:
- Too short (< 200 chars)
- No actual event details
- Just a placeholder message
- Doesn't address the query

## Success Criteria Summary

A test passes if:
1. ✅ Mock data loads correctly
2. ✅ Events retrieved successfully
3. ✅ Summary generated (length >= 200 chars)
4. ✅ Summary mentions event titles
5. ✅ Summary includes event times
6. ✅ Summary quality score >= 0.5
7. ✅ No errors or placeholders
8. ✅ LLM reasoning validated (no hardcoding)

## References

- Mock Data: `tests/fixtures/calendar_events_mock.json`
- Test Utilities: `tests/fixtures/calendar_fixtures.py`
- Unit Tests: `tests/test_summarize_calendar_with_mocks.py`
- Browser Tests: `tests/test_summarize_browser_comprehensive.py`
- Validation Utils: `tests/test_summarize_utils.py`

