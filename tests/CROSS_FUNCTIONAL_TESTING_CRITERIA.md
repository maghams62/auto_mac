# Cross-Functional Query Testing Criteria

## Overview

This document defines testing criteria for cross-functional queries that combine multiple agents/data sources. These queries test the orchestrator's ability to coordinate multi-step workflows across different domains.

## Test Scenarios

### CF1: Reminders + Calendar Combined Summary

**Queries**:
- `"summarize my reminders and calendar for the next week"`
- `"what do I have coming up - reminders and calendar events"`
- `"show me my todos and calendar events"`

**Expected Workflow**:
1. `list_reminders()` → Get reminders
2. `list_calendar_events(days_ahead=7)` → Get calendar events
3. `synthesize_content(source_contents=[reminders, calendar], topic="Combined summary")` → Combine both sources
4. `reply_to_user(message="$step3.synthesized_content")` → Return summary

**Success Criteria**:
- ✅ Both reminders and calendar events retrieved
- ✅ Summary mentions both sources
- ✅ Summary length >= 200 characters
- ✅ Source coverage >= 50% (both sources mentioned)
- ✅ No errors or skipped steps

**Mock Data**:
- Uses `CALENDAR_FAKE_DATA_PATH` for calendar events
- Relies on real reminders (may be empty in test environment)

### CF2: Email + Calendar Combined Summary

**Queries**:
- `"summarize my emails and calendar for today"`
- `"what's in my inbox and on my calendar this week"`
- `"show me my recent emails and upcoming calendar events"`

**Expected Workflow**:
1. `read_emails_by_time(hours=24)` or `read_latest_emails(count=N)` → Get emails
2. `list_calendar_events(days_ahead=7)` → Get calendar events
3. `synthesize_content(source_contents=[emails, calendar])` → Combine sources
4. `reply_to_user(message="$step3.synthesized_content")` → Return summary

**Success Criteria**:
- ✅ Both emails and calendar events retrieved
- ✅ Summary mentions both sources
- ✅ Summary length >= 200 characters
- ✅ Source coverage >= 50%
- ✅ No errors

### CF3: Bluesky Summary + Email

**Queries**:
- `"summarize recent Bluesky posts about AI and email them to me"`
- `"get my last 10 Bluesky posts and send them via email"`
- `"summarize Bluesky posts from the past hour and email the summary"`

**Expected Workflow**:
1. `summarize_bluesky_posts(query="...", max_items=N)` → Get posts summary
2. `compose_email(subject="Bluesky Summary", body="$step1.summary", send=true)` → Email summary
3. `reply_to_user(message="Emailed Bluesky summary")` → Confirm

**Success Criteria**:
- ✅ Bluesky posts retrieved and summarized
- ✅ Email sent (send=true)
- ✅ Email confirmation in response
- ✅ Summary included in email body
- ✅ No errors

**Note**: Email sending requires proper email configuration.

### CF4: News Summary + Email

**Queries**:
- `"summarize news about AI and email it to me"`
- `"get recent tech news and send it via email"`
- `"summarize today's news and email the summary"`

**Expected Workflow**:
1. `google_search(query="...", max_results=10)` → Search news
2. `synthesize_content(source_contents=[search_results], topic="News summary")` → Summarize
3. `compose_email(subject="News Summary", body="$step2.synthesized_content", send=true)` → Email
4. `reply_to_user(message="Emailed news summary")` → Confirm

**Success Criteria**:
- ✅ News articles retrieved via search
- ✅ Summary generated
- ✅ Email sent with summary
- ✅ Email confirmation in response
- ✅ No errors

### CF5: Reminders + Calendar + Email (Multi-Source)

**Queries**:
- `"summarize my reminders, calendar, and emails for this week and email it to me"`
- `"give me a complete summary of my todos, calendar events, and recent emails"`
- `"what do I have coming up - combine reminders, calendar, and emails"`

**Expected Workflow**:
1. `list_reminders()` → Get reminders
2. `list_calendar_events(days_ahead=7)` → Get calendar events
3. `read_emails_by_time(hours=168)` or `read_latest_emails(count=N)` → Get emails
4. `synthesize_content(source_contents=[reminders, calendar, emails])` → Combine all
5. `compose_email(subject="Complete Summary", body="$step4.synthesized_content", send=true)` → Email
6. `reply_to_user(message="Emailed complete summary")` → Confirm

**Success Criteria**:
- ✅ All three sources retrieved
- ✅ Summary mentions all sources
- ✅ Summary length >= 300 characters
- ✅ Source coverage >= 50% (at least 2 of 3 sources)
- ✅ Email sent if query includes email action
- ✅ No errors

### CF6: Calendar + Meeting Preparation

**Queries**:
- `"prepare a brief for Team Standup"`
- `"prep me for Product Review Meeting"`
- `"create a meeting brief for [event]"`

**Expected Workflow**:
1. `get_calendar_event_details(event_title="...")` → Get event details
2. `prepare_meeting_brief(event_title="...", save_to_note=False)` → Generate brief
   - This internally uses document search
3. `reply_to_user(message="$step2.brief")` → Return brief

**Success Criteria**:
- ✅ Calendar event found
- ✅ Meeting brief generated
- ✅ Brief includes meeting context
- ✅ Brief mentions relevant documents (if found)
- ✅ Response length >= 150 characters
- ✅ No errors

**Mock Data**: Uses calendar mock data for event lookup.

### CF7: Full Day Summary

**Queries**:
- `"give me a summary of my day - emails, calendar, and reminders"`
- `"what's on my plate today - combine everything"`
- `"summarize my complete day: emails, meetings, and todos"`

**Expected Workflow**:
1. `read_emails_by_time(hours=24)` → Get today's emails
2. `list_calendar_events(days_ahead=1)` → Get today's events
3. `list_reminders()` → Get reminders
4. `synthesize_content(source_contents=[emails, calendar, reminders], topic="Daily summary")` → Combine
5. `reply_to_user(message="$step4.synthesized_content")` → Return summary

**Success Criteria**:
- ✅ All three sources retrieved
- ✅ Summary mentions all sources
- ✅ Summary length >= 300 characters
- ✅ Source coverage >= 50%
- ✅ Chronologically organized (today's activities)
- ✅ No errors

## Quality Metrics

### Response Length
- **CF1-CF2**: Minimum 200 characters
- **CF3-CF4**: Minimum 150 characters (email confirmation)
- **CF5-CF7**: Minimum 300 characters (multi-source)

### Source Coverage
- **Minimum**: 50% of expected sources mentioned
- **Target**: 70-100% of expected sources mentioned
- **Calculation**: `found_sources / expected_sources`

### Synthesis Quality
- Summary combines multiple sources coherently
- Uses connecting words ("and", "also", "additionally")
- Not just concatenated lists
- Maintains context across sources

### Error Handling
- No error messages in response
- No "skipped" or "timeout" messages
- Graceful handling of empty sources
- Informative messages when data unavailable

## LLM Reasoning Validation

### Parameter Extraction
- ✅ Time windows extracted from natural language
- ✅ Query parameters inferred correctly
- ✅ No hardcoded defaults
- ✅ Flexible interpretation allowed

### Workflow Planning
- ✅ Correct tool sequence
- ✅ Proper dependencies
- ✅ Data flow between steps
- ✅ Email actions detected correctly

### Data Synthesis
- ✅ Multiple sources combined intelligently
- ✅ Redundancy removed
- ✅ Context preserved
- ✅ Coherent narrative

## Test Execution

### Prerequisites
1. API server running on `http://localhost:8000`
2. Mock calendar data configured (`CALENDAR_FAKE_DATA_PATH`)
3. Email configuration (for email tests)
4. Bluesky credentials (for Bluesky tests)

### Running Tests
```bash
# Run all cross-functional tests
python3 tests/test_cross_functional_queries_comprehensive.py

# Run specific test
python3 -c "
from tests.test_cross_functional_queries_comprehensive import test_cf1_reminders_and_calendar
test_cf1_reminders_and_calendar()
"
```

### Expected Output
- Test results printed to console
- JSON results file saved: `tests/cross_functional_test_results_{timestamp}.json`
- Success rate calculated
- Failed tests listed

## Troubleshooting

### Common Issues

**Issue**: Sources not combined
- **Cause**: `synthesize_content` not called or called incorrectly
- **Fix**: Verify workflow includes synthesis step

**Issue**: Email not sent
- **Cause**: `send=true` not set or email configuration missing
- **Fix**: Check delivery intent detection and email config

**Issue**: Empty sources
- **Cause**: No data available (reminders, emails, etc.)
- **Fix**: Use mock data or accept informative empty-state messages

**Issue**: Timeout errors
- **Cause**: Tools taking too long (reminders, calendar)
- **Fix**: Increase timeout or use mock data

### Debugging Steps

1. **Check API Availability**:
   ```bash
   curl http://localhost:8000/health
   ```

2. **Verify Mock Data**:
   ```python
   from fixtures.calendar_fixtures import get_mock_calendar_events
   events = get_mock_calendar_events()
   print(f"Loaded {len(events)} events")
   ```

3. **Test Individual Tools**:
   ```python
   from src.agent.calendar_agent import list_calendar_events
   result = list_calendar_events.invoke({"days_ahead": 7})
   print(result)
   ```

4. **Check Orchestrator Planning**:
   ```python
   from src.orchestrator.main_orchestrator import MainOrchestrator
   orchestrator = MainOrchestrator(config)
   plan = orchestrator.planner.create_plan(
       goal="summarize reminders and calendar",
       available_tools=orchestrator.tool_catalog
   )
   print(json.dumps(plan, indent=2))
   ```

## Success Criteria Summary

A test passes if:
1. ✅ All expected sources retrieved
2. ✅ Summary generated (meets length requirement)
3. ✅ Source coverage >= 50%
4. ✅ Synthesis indicators present
5. ✅ No errors or timeouts
6. ✅ Email confirmation (if email action requested)
7. ✅ LLM reasoning validated (no hardcoding)

## References

- Test File: `tests/test_cross_functional_queries_comprehensive.py`
- Mock Data: `tests/fixtures/calendar_events_mock.json`
- Calendar Fixtures: `tests/fixtures/calendar_fixtures.py`
- Planner Guidance: `src/orchestrator/planner.py` (line 287)

