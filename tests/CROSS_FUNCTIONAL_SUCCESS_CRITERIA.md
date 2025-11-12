# Cross-Functional Query Success Criteria

## Overview

This document defines clear, comprehensive success criteria for all cross-functional query test scenarios. Each test must meet ALL criteria to be considered passing.

## General Success Criteria

All tests must meet these baseline requirements:
- ✅ No errors in response (no "error", "failed", "timeout", "skipped" messages)
- ✅ Response has substance (meets minimum length requirement)
- ✅ Expected sources mentioned in response
- ✅ No parameter validation errors
- ✅ Proper workflow execution (all steps completed)

## Test-Specific Success Criteria

### CF1: Reminders + Calendar Combined Summary

**Test Queries**:
- `"summarize my reminders and calendar for the next week"`
- `"what do I have coming up - reminders and calendar events"`
- `"show me my todos and calendar events"`

**Success Criteria** (ALL must pass):
1. ✅ **Both Sources Retrieved**: Reminders and calendar events successfully retrieved
   - Reminders count > 0 OR informative empty-state message
   - Calendar events count > 0 OR informative empty-state message
   - No "Skipped due to failed dependencies" errors

2. ✅ **Summary Mentions Both Sources**: Response includes references to both reminders and calendar
   - Response contains reminder-related keywords: "reminder", "todo", "task"
   - Response contains calendar-related keywords: "calendar", "event", "meeting", "appointment"
   - Source coverage >= 50% (both sources mentioned)

3. ✅ **Summary Length**: Response is substantial
   - Minimum: 200 characters
   - Contains actual event/reminder details, not just placeholders

4. ✅ **No Errors**: No error messages or skipped steps
   - No "error" in response
   - No "failed" in response
   - No "timeout" in response
   - No "Skipped due to failed dependencies"

5. ✅ **Synthesis Quality**: Summary combines sources coherently
   - Uses connecting words ("and", "also", "additionally")
   - Not just concatenated lists
   - Maintains context across sources

**Failure Indicators**:
- ❌ "Skipped due to failed dependencies" → Reminders timeout
- ❌ Response < 200 chars → Incomplete summary
- ❌ Only one source mentioned → Missing synthesis
- ❌ Error messages present → Tool failure

---

### CF2: Email + Calendar Combined Summary

**Test Queries**:
- `"summarize my emails and calendar for today"`
- `"what's in my inbox and on my calendar this week"`
- `"show me my recent emails and upcoming calendar events"`

**Success Criteria** (ALL must pass):
1. ✅ **Both Sources Retrieved**: Emails and calendar events successfully retrieved
   - Email reading completed (may be empty)
   - Calendar events retrieved (may be empty)
   - No dependency failures

2. ✅ **Summary Mentions Both Sources**: Response includes references to both emails and calendar
   - Response contains email-related keywords: "email", "message", "inbox"
   - Response contains calendar-related keywords: "calendar", "event", "meeting"
   - Source coverage >= 50%

3. ✅ **Summary Length**: Response is substantial
   - Minimum: 200 characters
   - Contains actual content details

4. ✅ **No Parameter Validation Errors**: Tools receive correct parameter types
   - No "Input should be a valid string" errors
   - No "type=string_type" validation errors
   - reply_to_user receives strings, not dicts

5. ✅ **No Errors**: No error messages
   - No validation errors
   - No tool execution errors

**Failure Indicators**:
- ❌ "Input should be a valid string" → Parameter resolution issue
- ❌ "type=string_type" → Dict passed instead of string
- ❌ Response < 200 chars → Incomplete summary

---

### CF3: Bluesky Summary + Email

**Test Queries**:
- `"summarize recent Bluesky posts about AI and email them to me"`
- `"get my last 10 Bluesky posts and send them via email"`
- `"summarize Bluesky posts from the past hour and email the summary"`

**Success Criteria** (ALL must pass):
1. ✅ **Bluesky Posts Retrieved**: Posts successfully fetched and summarized
   - Posts retrieved (may be empty if no posts in timeframe)
   - Summary generated (if posts found)

2. ✅ **Email Sent**: Email delivery confirmed
   - Response contains email confirmation keywords: "sent", "emailed", "email sent", "delivered"
   - send=true parameter set correctly

3. ✅ **Summary in Email**: Summary included in email body
   - Email body contains summary content (as string)
   - No parameter validation errors for compose_email.body

4. ✅ **No Parameter Errors**: Tools receive correct parameter types
   - compose_email.body is a string, not a dict
   - No "type=string_type" validation errors

5. ✅ **Response Length**: Response is informative
   - Minimum: 150 characters (email confirmation)
   - Contains email delivery confirmation

**Failure Indicators**:
- ❌ "Input should be a valid string" for compose_email.body → Parameter resolution issue
- ❌ No email confirmation → Email not sent
- ❌ Parameter validation errors → Dict passed instead of string

---

### CF4: News Summary + Email

**Test Queries**:
- `"summarize news about AI and email it to me"`
- `"get recent tech news and send it via email"`
- `"summarize today's news and email the summary"`

**Success Criteria** (ALL must pass):
1. ✅ **News Retrieved**: News articles retrieved via search
   - Search executed successfully
   - Articles found (may be empty)

2. ✅ **Summary Generated**: News articles synthesized
   - Summary created from search results
   - Summary length >= 200 characters

3. ✅ **Email Sent**: Email delivery confirmed
   - Response contains email confirmation
   - send=true parameter set

4. ✅ **Summary in Email**: Summary included in email body
   - Email body contains summary (as string)
   - No parameter validation errors

5. ✅ **Source Coverage**: Response mentions news sources
   - Response contains news-related keywords: "news", "article", "report"
   - Response contains email-related keywords: "email", "sent"

**Status**: ✅ Currently passing (3/3 tests)

---

### CF5: Reminders + Calendar + Email Multi-Source

**Test Queries**:
- `"summarize my reminders, calendar, and emails for this week and email it to me"`
- `"give me a complete summary of my todos, calendar events, and recent emails"`
- `"what do I have coming up - combine reminders, calendar, and emails"`

**Success Criteria** (ALL must pass):
1. ✅ **All Three Sources Retrieved**: Reminders, calendar, and emails retrieved
   - All three tools executed successfully
   - No dependency failures
   - May have empty results (informative messages acceptable)

2. ✅ **Summary Mentions All Sources**: Response includes references to all three sources
   - Response mentions reminders/todos
   - Response mentions calendar events
   - Response mentions emails
   - Source coverage >= 50% (at least 2 of 3 sources)

3. ✅ **Summary Length**: Response is comprehensive
   - Minimum: 300 characters (multi-source summary)
   - Contains details from multiple sources

4. ✅ **Email Sent** (if query includes email action): Email delivery confirmed
   - Response contains email confirmation
   - Email includes combined summary

5. ✅ **No Errors**: No errors or skipped steps
   - No timeout errors
   - No dependency failures
   - No parameter validation errors

**Failure Indicators**:
- ❌ "Skipped due to failed dependencies" → Reminders timeout
- ❌ Response < 300 chars → Incomplete summary
- ❌ Less than 2 sources mentioned → Missing synthesis

---

### CF6: Calendar + Meeting Preparation

**Test Queries**:
- `"prepare a brief for Team Standup"`
- `"prep me for Team Standup meeting"`
- `"create a meeting brief for Team Standup"`

**Success Criteria** (ALL must pass):
1. ✅ **Event Found**: Calendar event located successfully
   - Event found using fuzzy matching (partial title match)
   - Case-insensitive matching works
   - No "Event not found" errors

2. ✅ **Meeting Brief Generated**: Brief created successfully
   - Brief generated from event details
   - Brief includes meeting context

3. ✅ **Brief Content**: Brief contains relevant information
   - Mentions event title
   - Mentions meeting time/date
   - Mentions attendees (if available)
   - Mentions location (if available)

4. ✅ **Response Length**: Response is informative
   - Minimum: 150 characters
   - Contains actual brief content, not just confirmation

5. ✅ **No Errors**: No lookup or generation errors
   - No "Event not found" errors (with fuzzy matching)
   - No tool execution errors

**Failure Indicators**:
- ❌ "Event 'Team Standup' not found" → Event lookup failed (needs fuzzy matching)
- ❌ Response < 150 chars → Incomplete brief
- ❌ "Skipped due to failed dependencies" → Previous step failed

---

### CF7: Full Day Summary

**Test Queries**:
- `"give me a summary of my day - emails, calendar, and reminders"`
- `"what's on my plate today - combine everything"`
- `"summarize my complete day: emails, meetings, and todos"`

**Success Criteria** (ALL must pass):
1. ✅ **All Sources Retrieved**: Emails, calendar, and reminders retrieved
   - All three tools executed successfully
   - No dependency failures
   - May have empty results (informative messages acceptable)

2. ✅ **Summary Mentions All Sources**: Response includes references to all three sources
   - Response mentions emails
   - Response mentions calendar events/meetings
   - Response mentions reminders/todos
   - Source coverage >= 50%

3. ✅ **Summary Length**: Response is comprehensive
   - Minimum: 300 characters (full day summary)
   - Contains details from multiple sources

4. ✅ **Chronological Organization**: Summary organized by time
   - Mentions time-related keywords: "today", "morning", "afternoon", "evening"
   - Events ordered chronologically
   - Clear time-based structure

5. ✅ **No Errors**: No errors or skipped steps
   - No timeout errors
   - No dependency failures
   - No parameter validation errors

**Failure Indicators**:
- ❌ "Skipped due to failed dependencies" → Reminders timeout
- ❌ Response < 300 chars → Incomplete summary
- ❌ Less than 2 sources mentioned → Missing synthesis

---

## Parameter Validation Success Criteria

### reply_to_user Tool
- ✅ `message` parameter is always a string (never a dict or list)
- ✅ `details` parameter is always a string (never a dict or list)
- ✅ If step result is dict/list, convert to JSON string or extract string field
- ✅ No "Input should be a valid string" validation errors

### compose_email Tool
- ✅ `body` parameter is always a string (never a dict or list)
- ✅ `subject` parameter is always a string
- ✅ If step result is dict/list, convert to JSON string or extract string field
- ✅ No "type=string_type" validation errors

### synthesize_content Tool
- ✅ `source_contents` parameter is always List[str] (list of strings)
- ✅ Dicts/lists converted to JSON strings before passing
- ✅ Empty results converted to "No items found" string

---

## Error Detection Criteria

### Timeout Errors
- ❌ "Timeout after 10s" or "Timeout after 30s"
- ❌ "Skipped due to failed dependencies" (caused by timeout)
- **Fix**: Increase timeout or use mock data

### Parameter Validation Errors
- ❌ "Input should be a valid string [type=string_type, input_value={...}]"
- ❌ "1 validation error for reply_to_user" or "compose_email"
- **Fix**: Ensure parameter resolver converts dicts to strings

### Dependency Failures
- ❌ "Skipped due to failed dependencies: [N]"
- **Fix**: Fix underlying tool failure (timeout, error, etc.)

### Empty Results
- ⚠️ Informative empty-state messages are acceptable
- ❌ Empty responses without explanation are failures
- **Fix**: Ensure tools return informative messages for empty results

---

## Test Execution Checklist

Before marking a test as passing, verify:
- [ ] All success criteria met (check each criterion)
- [ ] No errors in response
- [ ] Response length meets minimum requirement
- [ ] Expected sources mentioned
- [ ] No parameter validation errors
- [ ] No timeout errors
- [ ] No dependency failures
- [ ] Synthesis quality acceptable
- [ ] Email confirmation present (if email action requested)

---

## Success Rate Targets

- **Current**: 14.3% (3/21 tests passing)
- **Target**: >= 80% (17/21 tests passing)
- **Stretch Goal**: 100% (21/21 tests passing)

---

## References

- Test File: `tests/test_cross_functional_queries_comprehensive.py`
- Mock Data: 
  - `tests/fixtures/calendar_events_mock.json`
  - `tests/fixtures/reminders_mock.json`
- Fixtures:
  - `tests/fixtures/calendar_fixtures.py`
  - `tests/fixtures/reminders_fixtures.py`
- Parameter Resolver: `src/utils/template_resolver.py`
- Automation:
  - `src/automation/calendar_automation.py`
  - `src/automation/reminders_automation.py`

