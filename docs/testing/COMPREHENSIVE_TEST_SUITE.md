# Comprehensive Multi-Step Test Suite
## System-Wide Quality Assurance

**Date**: 2025-11-10
**System**: Auto Mac Agentic Framework
**Total Agents**: 24
**Total Tools**: 82
**Complexity Benchmark**: NVIDIA stock → report → PDF → zip → email (5-step flow)

---

## Test Design Philosophy

Based on your working NVIDIA example, I'm designing test cases that:
1. **Require 3-7 steps** (similar complexity to your benchmark)
2. **Cross multiple agents** (tests orchestration)
3. **Involve planning and disambiguation** (tests intelligence)
4. **Have clear success/failure criteria** (tests reliability)
5. **Cover all major agent categories** (tests completeness)

---

## Test Categories

### Category A: Financial Data → Document Workflows
*Benchmarked against: NVIDIA stock → report → PDF → zip → email*

### Category B: Research → Content Creation Workflows
*Tests: Browser → Writing → Presentation chains*

### Category C: Communication & Notification Workflows
*Tests: Email → WhatsApp → Discord → iMessage chains*

### Category D: Data Collection → Analysis Workflows
*Tests: Twitter/Bluesky → Report → Email chains*

### Category E: Multi-Modal Workflows
*Tests: Voice → Text → Document → Email chains*

### Category F: Automation & Utility Workflows
*Tests: Maps → Spotify → Notifications chains*

---

## TEST SUITE

---

## Category A: Financial Data → Document Workflows

### TEST A1: Stock Analysis Full Pipeline (BENCHMARK TEST)
**User Query**: "Find the stock price of NVIDIA, create a report, turn it into a PDF, zip it, and email it to me"

**Expected Flow**:
1. `search_google_finance_stock` (Google Finance Agent) → Get NVIDIA ticker
2. `extract_google_finance_data` (Google Finance Agent) → Get stock data
3. `create_stock_report` (Report Agent) → Generate report
4. *(Implied PDF conversion or document creation)*
5. `create_zip_archive` (File Agent) → Zip the report
6. `compose_email` (Email Agent) → Send to user

**Success Criteria**:
- ✅ Finds NVDA ticker correctly
- ✅ Extracts current stock price
- ✅ Creates coherent report
- ✅ Archives report as ZIP
- ✅ Sends email with attachment
- ✅ User receives zip file with report

**Failure Points to Watch**:
- ❌ Ticker disambiguation (NVIDIA vs NVDA)
- ❌ Missing data in report
- ❌ ZIP creation fails
- ❌ Email attachment missing

**Priority**: **CRITICAL** (This is your benchmark)

---

### TEST A2: Multi-Stock Comparison Report
**User Query**: "Compare Apple, Microsoft, and Google stock prices, create a detailed report, and email it to spamstuff062@gmail.com"

**Expected Flow**:
1. `search_google_finance_stock` × 3 (for AAPL, MSFT, GOOGL)
2. `extract_google_finance_data` × 3
3. `create_detailed_report` (Writing Agent) → Synthesize comparison
4. `compose_email` (Email Agent) → Send report

**Success Criteria**:
- ✅ Finds all 3 tickers correctly
- ✅ Extracts data for all 3
- ✅ Creates comparative analysis
- ✅ Email delivered with report

**Complexity**: 7 steps
**Priority**: HIGH

---

### TEST A3: Stock Chart Capture with Report
**User Query**: "Get the stock chart for Tesla, create a report about it, save both as a zip, and notify me"

**Expected Flow**:
1. `search_google_finance_stock` (Google Finance Agent) → TSLA
2. `capture_google_finance_chart` (Google Finance Agent) → Screenshot
3. `create_stock_report_from_google_finance` (Google Finance Agent) → Report
4. `create_zip_archive` (File Agent) → Zip chart + report
5. `send_notification` (Notifications Agent) → Notify user

**Success Criteria**:
- ✅ Finds TSLA ticker
- ✅ Captures chart image
- ✅ Creates report
- ✅ ZIP contains both files
- ✅ Notification sent

**Complexity**: 5 steps
**Priority**: HIGH

---

## Category B: Research → Content Creation Workflows

### TEST B1: Web Research to Presentation
**User Query**: "Search for 'AI trends 2024', extract the top 3 articles, create a slide deck about them, and email it to me"

**Expected Flow**:
1. `google_search` (Browser Agent) → Find articles
2. `navigate_to_url` × 3 (Browser Agent) → Visit top 3
3. `extract_page_content` × 3 (Browser Agent) → Get content
4. `create_slide_deck_content` (Writing Agent) → Create slides content
5. `create_keynote` (Presentation Agent) → Make presentation
6. `compose_email` (Email Agent) → Send presentation

**Success Criteria**:
- ✅ Finds relevant articles
- ✅ Extracts content from 3 sites
- ✅ Creates coherent slide deck
- ✅ Keynote file generated
- ✅ Email with attachment

**Complexity**: 9 steps (high complexity)
**Priority**: HIGH

---

### TEST B2: Document Search to Synthesized Report
**User Query**: "Search my documents for files about 'quarterly results', synthesize the content, and create a meeting notes document"

**Expected Flow**:
1. `search_documents` (File Agent) → Find relevant files
2. `extract_section` (File Agent) → Get content from found files
3. `synthesize_content` (Writing Agent) → Combine information
4. `create_meeting_notes` (Writing Agent) → Format as notes
5. `reply_to_user` (Reply Agent) → Deliver summary

**Success Criteria**:
- ✅ Finds relevant documents
- ✅ Extracts key sections
- ✅ Synthesizes coherently
- ✅ Creates well-formatted notes
- ✅ User receives notes

**Complexity**: 5 steps
**Priority**: MEDIUM

---

### TEST B3: Multi-Source Content Aggregation
**User Query**: "Search Google for 'electric vehicles', search my documents for EV reports, and create a comprehensive report combining both"

**Expected Flow**:
1. `google_search` (Browser Agent) → Web search
2. `navigate_to_url` (Browser Agent) → Visit top result
3. `extract_page_content` (Browser Agent) → Get web content
4. `search_documents` (File Agent) → Find local docs
5. `extract_section` (File Agent) → Get local content
6. `create_detailed_report` (Writing Agent) → Combine all sources
7. `reply_to_user` (Reply Agent) → Deliver report

**Success Criteria**:
- ✅ Searches both web and local sources
- ✅ Extracts content from both
- ✅ Creates unified report
- ✅ Report cites both sources

**Complexity**: 7 steps
**Priority**: MEDIUM

---

## Category C: Communication & Notification Workflows

### TEST C1: Email Read and WhatsApp Notify
**User Query**: "Read my latest emails from john@example.com, summarize them, and send the summary to my Dotards WhatsApp group"

**Expected Flow**:
1. `read_emails_by_sender` (Email Agent) → Get John's emails
2. `summarize_emails` (Email Agent) → Create summary
3. `whatsapp_navigate_to_chat` (WhatsApp Agent) → Open Dotards group
4. *(Note: WhatsApp sending not implemented - would need to show summary)*
5. `reply_to_user` (Reply Agent) → Show what would be sent

**Success Criteria**:
- ✅ Finds John's emails
- ✅ Summarizes correctly
- ✅ Navigates to Dotards group
- ⚠️ Cannot send (read-only limitation)
- ✅ Shows summary to user

**Complexity**: 4-5 steps
**Priority**: MEDIUM
**Note**: Tests read-only limitation handling

---

### TEST C1a: Email Summarization - Last N Emails (NEW)
**User Query**: "summarize my last 3 emails"

**Expected Flow**:
1. `read_latest_emails` (Email Agent, count=3) → Retrieve 3 most recent emails
2. `summarize_emails` (Email Agent, emails_data=$step1) → Generate summary
3. `reply_to_user` (Reply Agent) → Display summary with metadata

**Expected Tool Chain**:
- read_latest_emails → summarize_emails

**Required Inputs**:
- read_latest_emails:
  - count: 3
  - mailbox: "INBOX" (default)
- summarize_emails:
  - emails_data: output from step 1 (dict with 'emails' list)
  - focus: None (optional)

**Expected Output Structure**:
```json
{
  "summary": "Text summary of emails with key points",
  "email_count": 3,
  "focus": null,
  "emails_summarized": [
    {"sender": "...", "subject": "...", "date": "..."},
    {"sender": "...", "subject": "...", "date": "..."},
    {"sender": "...", "subject": "...", "date": "..."}
  ]
}
```

**Success Criteria**:
- ✅ read_latest_emails called with count=3
- ✅ summarize_emails receives full email data structure
- ✅ Summary includes sender, subject, and key points for each email
- ✅ Email metadata (sender, subject, date) included in response
- ✅ UI displays summary headline and bullet points
- ✅ UI shows compact email list with metadata

**Complexity**: 3 steps
**Priority**: HIGH
**Note**: Tests basic email summarization workflow

---

### TEST C1b: Email Summarization - By Sender (NEW)
**User Query**: "summarize the last 3 emails sent by john@example.com"

**Expected Flow**:
1. `read_emails_by_sender` (Email Agent, sender="john@example.com", count=3) → Get John's emails
2. `summarize_emails` (Email Agent, emails_data=$step1) → Generate summary
3. `reply_to_user` (Reply Agent) → Display summary

**Expected Tool Chain**:
- read_emails_by_sender → summarize_emails

**Required Inputs**:
- read_emails_by_sender:
  - sender: "john@example.com" (or partial match like "John Doe")
  - count: 3
- summarize_emails:
  - emails_data: output from step 1
  - focus: None (optional)

**Expected Output Structure**:
```json
{
  "summary": "Text summary focusing on John's emails",
  "email_count": 3,
  "focus": null,
  "sender": "john@example.com",
  "emails_summarized": [
    {"sender": "john@example.com", "subject": "...", "date": "..."},
    {"sender": "john@example.com", "subject": "...", "date": "..."},
    {"sender": "john@example.com", "subject": "...", "date": "..."}
  ]
}
```

**Success Criteria**:
- ✅ read_emails_by_sender called with correct sender parameter
- ✅ Count parameter matches user request
- ✅ summarize_emails receives filtered email list
- ✅ Summary contextualizes that emails are from specific sender
- ✅ All emails in result are from requested sender
- ✅ UI displays sender context in summary

**Complexity**: 3 steps
**Priority**: HIGH
**Note**: Tests sender-specific email summarization

---

### TEST C1c: Email Summarization - Time Window (NEW)
**User Query**: "summarize the emails from the last hour"

**Expected Flow**:
1. `read_emails_by_time` (Email Agent, hours=1) → Get emails from last hour
2. `summarize_emails` (Email Agent, emails_data=$step1, focus="action items") → Summarize with focus
3. `reply_to_user` (Reply Agent) → Display summary

**Expected Tool Chain**:
- read_emails_by_time → summarize_emails

**Required Inputs**:
- read_emails_by_time:
  - hours: 1 (or minutes: 60)
  - mailbox: "INBOX" (default)
- summarize_emails:
  - emails_data: output from step 1
  - focus: "action items" (if user specifies, otherwise None)

**Expected Output Structure**:
```json
{
  "summary": "Time-contextualized summary with focus on action items",
  "email_count": 5,
  "focus": "action items",
  "time_range": "1 hours",
  "emails_summarized": [
    {"sender": "...", "subject": "...", "date": "..."},
    ...
  ]
}
```

**Success Criteria**:
- ✅ read_emails_by_time called with correct time parameter
- ✅ Time parameter correctly parsed from user query (hours vs minutes)
- ✅ summarize_emails receives time-filtered emails
- ✅ Summary mentions time context ("in the last hour")
- ✅ Focus parameter applied if user specified (e.g., "action items")
- ✅ All emails in result are within requested time window
- ✅ UI displays time context

**Complexity**: 3 steps
**Priority**: HIGH
**Note**: Tests time-based email summarization with optional focus

---

### TEST C1d: Slash Command Email Summarization (NEW)
**User Query**: "/email summarize my last 5 emails"

**Expected Flow**:
1. Slash command handler extracts intent_hints: {count: 5, action: "summarize"}
2. Orchestrator receives hints and builds plan
3. `read_latest_emails` (count=5) → `summarize_emails` → `reply_to_user`

**Success Criteria**:
- ✅ Slash handler extracts count from command
- ✅ Intent hints passed to orchestrator via parsed payload
- ✅ Planner chooses correct read tool based on hints
- ✅ Workflow completes with structured summary
- ✅ No "retry" or generic error messages

**Complexity**: 3 steps
**Priority**: HIGH
**Note**: Tests slash command integration with summarization

---

### TEST C2: Multi-Channel Notification Broadcast
**User Query**: "Send a notification saying 'Meeting in 5 min', send it via iMessage to +16618572957, and play music"

**Expected Flow**:
1. `send_notification` (Notifications Agent) → System notification
2. `send_imessage` (iMessage Agent) → Send to phone
3. `play_music` (Spotify Agent) → Start music
4. `reply_to_user` (Reply Agent) → Confirm all sent

**Success Criteria**:
- ✅ Notification appears
- ✅ iMessage sent
- ✅ Music starts playing
- ✅ User confirmation

**Complexity**: 4 steps
**Priority**: MEDIUM

---

### TEST C3: Email Reply with Attached Report
**User Query**: "Read my latest email, create a detailed response report about the topic mentioned, and reply with the report attached"

**Expected Flow**:
1. `read_latest_emails` (Email Agent) → Get recent email
2. `create_detailed_report` (Writing Agent) → Create response
3. `reply_to_email` (Email Agent) → Reply with attachment
4. `reply_to_user` (Reply Agent) → Confirm sent

**Success Criteria**:
- ✅ Reads latest email
- ✅ Understands topic
- ✅ Creates relevant report
- ✅ Reply sent with attachment

**Complexity**: 4 steps
**Priority**: HIGH

---

## Category D: Data Collection → Analysis Workflows

### TEST D1: Twitter List Analysis with Report
**User Query**: "Summarize my Twitter product watch list from the last 24 hours and email me a report"

**Expected Flow**:
1. `summarize_list_activity` (Twitter Agent) → Get list summary
2. `create_detailed_report` (Writing Agent) → Format as report
3. `compose_email` (Email Agent) → Send report
4. `reply_to_user` (Reply Agent) → Confirm sent

**Success Criteria**:
- ✅ Accesses Twitter list
- ✅ Summarizes recent activity
- ✅ Creates formatted report
- ✅ Email sent

**Complexity**: 4 steps
**Priority**: MEDIUM

---

### TEST D2: Bluesky Search and Post Summary
**User Query**: "Search Bluesky for posts about 'AI safety', summarize the findings, and create a report"

**Expected Flow**:
1. `search_bluesky_posts` (Bluesky Agent) → Search posts
2. `summarize_bluesky_posts` (Bluesky Agent) → Summarize results
3. `create_detailed_report` (Writing Agent) → Format report
4. `reply_to_user` (Reply Agent) → Deliver report

**Success Criteria**:
- ✅ Finds relevant Bluesky posts
- ✅ Summarizes content
- ✅ Creates coherent report
- ✅ Report delivered to user

**Complexity**: 4 steps
**Priority**: MEDIUM

---

### TEST D3: Reddit Analysis with Email Digest
**User Query**: "Scan r/technology for hot posts, create a summary report, zip it, and email it to me"

**Expected Flow**:
1. `scan_subreddit_posts` (Reddit Agent) → Get hot posts
2. `create_detailed_report` (Writing Agent) → Create summary
3. `create_zip_archive` (File Agent) → Zip report
4. `compose_email` (Email Agent) → Send zip
5. `reply_to_user` (Reply Agent) → Confirm

**Success Criteria**:
- ✅ Scans r/technology
- ✅ Gets hot posts
- ✅ Creates summary
- ✅ Zips report
- ✅ Email sent with zip

**Complexity**: 5 steps
**Priority**: MEDIUM

---

## Category E: Multi-Modal Workflows

### TEST E1: Voice to Document to Email
**User Query**: "Transcribe the audio file at /path/to/audio.mp3, create a meeting notes document from it, and email it to me"

**Expected Flow**:
1. `transcribe_audio_file` (Voice Agent) → Get transcription
2. `create_meeting_notes` (Writing Agent) → Format as notes
3. `compose_email` (Email Agent) → Send notes
4. `reply_to_user` (Reply Agent) → Confirm

**Success Criteria**:
- ✅ Transcribes audio correctly
- ✅ Creates formatted notes
- ✅ Email sent with notes
- ✅ Notes are readable

**Complexity**: 4 steps
**Priority**: MEDIUM
**Note**: Requires test audio file

---

### TEST E2: Text to Speech Notification
**User Query**: "Create a voice message saying 'Your report is ready' and play it, then send a notification"

**Expected Flow**:
1. `text_to_speech` (Voice Agent) → Generate audio
2. `launch_app` (Micro Actions Agent) → Open audio player
3. `send_notification` (Notifications Agent) → System notification
4. `reply_to_user` (Reply Agent) → Confirm

**Success Criteria**:
- ✅ TTS audio generated
- ✅ Audio plays
- ✅ Notification sent
- ✅ User confirmation

**Complexity**: 4 steps
**Priority**: LOW

---

### TEST E3: Screenshot to Report with Vision
**User Query**: "Take a screenshot, analyze what's on screen, create a report about it, and email it"

**Expected Flow**:
1. `take_screenshot` (File Agent) → Capture screen
2. `analyze_ui_screenshot` (Vision Agent) → Analyze content
3. `create_detailed_report` (Writing Agent) → Create report
4. `compose_email` (Email Agent) → Send report
5. `reply_to_user` (Reply Agent) → Confirm

**Success Criteria**:
- ✅ Screenshot captured
- ✅ Vision analysis works
- ✅ Report created from analysis
- ✅ Email sent

**Complexity**: 5 steps
**Priority**: LOW
**Note**: Tests vision integration

---

## Category F: Automation & Utility Workflows

### TEST F1: Maps Trip with Notification
**User Query**: "Plan a trip from San Francisco to Los Angeles with 2 fuel stops and 1 food stop, then notify me when done"

**Expected Flow**:
1. `plan_trip_with_stops` (Maps Agent) → Plan route
2. `open_maps_with_route` (Maps Agent) → Open in Maps
3. `send_notification` (Notifications Agent) → Notify completion
4. `reply_to_user` (Reply Agent) → Show trip details

**Success Criteria**:
- ✅ Route planned with stops
- ✅ Maps opens with route
- ✅ Notification sent
- ✅ Trip details shown

**Complexity**: 4 steps
**Priority**: MEDIUM

---

### TEST F2: Google Transit with Timer
**User Query**: "When's the next bus to Berkeley, set a timer for 10 minutes before departure, and play music"

**Expected Flow**:
1. `get_google_transit_directions` (Maps Agent) → Get transit time
2. *(Calculate 10 min before)*
3. `set_timer` (Micro Actions Agent) → Set timer
4. `play_music` (Spotify Agent) → Start music
5. `reply_to_user` (Reply Agent) → Confirm all set

**Success Criteria**:
- ✅ Gets next bus time
- ✅ Calculates correct timer
- ✅ Timer set
- ✅ Music playing
- ✅ User confirmation

**Complexity**: 5 steps
**Priority**: HIGH
**Note**: Tests Google Maps integration

---

### TEST F3: File Organization with Celebration
**User Query**: "Organize files in my Downloads folder by type, zip the organized folders, and celebrate when done"

**Expected Flow**:
1. `folder_list` (Folder Agent) → List Downloads
2. `folder_organize_by_type` (Folder Agent) → Organize files
3. `create_zip_archive` (File Agent) → Zip organized folders
4. `trigger_confetti` (Celebration Agent) → Celebrate
5. `reply_to_user` (Reply Agent) → Show results

**Success Criteria**:
- ✅ Lists files
- ✅ Organizes by type
- ✅ Creates zip
- ✅ Confetti triggers
- ✅ User sees results

**Complexity**: 5 steps
**Priority**: LOW

---

## Category G: Edge Cases & Error Handling

### TEST G1: Disambiguation Test
**User Query**: "Email me about the stocks" (ambiguous)

**Expected Behavior**:
- System should ask: "Which stocks do you want information about?"
- Tests: `validate_plan` (Critic Agent) should catch ambiguity

**Success Criteria**:
- ✅ System detects ambiguity
- ✅ Asks clarifying question
- ❌ Does NOT proceed with incomplete info

**Priority**: CRITICAL

---

### TEST G2: Missing Tool Test
**User Query**: "Send a WhatsApp message to John saying 'Hi'" (unsupported - read-only)

**Expected Behavior**:
- System should respond: "WhatsApp integration is read-only, cannot send messages"
- Tests: Capability assessment before planning

**Success Criteria**:
- ✅ System detects missing capability
- ✅ Returns clear error message
- ❌ Does NOT hallucinate fake tool

**Priority**: CRITICAL

---

### TEST G3: Dependency Chain Failure
**User Query**: "Find NVIDIA stock, create report, email it" (but Google Finance is down)

**Expected Behavior**:
- Step 1 fails → System should stop and report error
- Should NOT proceed to create empty report

**Success Criteria**:
- ✅ Detects step 1 failure
- ✅ Stops execution
- ✅ Reports clear error to user
- ❌ Does NOT continue with bad data

**Priority**: CRITICAL

---

## Test Execution Plan

### Phase 1: Benchmark Validation (Day 1)
- [ ] TEST A1 (NVIDIA stock pipeline) - Verify it still works
- [ ] Establish baseline performance metrics

### Phase 2: Critical Path Testing (Day 1-2)
- [ ] All HIGH priority tests
- [ ] All CRITICAL priority tests
- [ ] Focus on multi-agent orchestration

### Phase 3: Comprehensive Testing (Day 2-3)
- [ ] All MEDIUM priority tests
- [ ] Document any failures

### Phase 4: Edge Cases & Polish (Day 3)
- [ ] All LOW priority tests
- [ ] Error handling tests (Category G)
- [ ] Performance optimization if needed

---

## Category H: Executive Briefing Workflows *(NEW)*

### TEST H1: Cross-Source Executive Briefing Pack
**User Query**: "Create an executive briefing on Project Atlas by combining my internal docs and the latest web coverage, build slides, and email them to leadership"

**Expected Flow**:
1. `search_documents` (File Agent) → Locate internal Project Atlas materials
2. `extract_section` (File Agent) → Pull critical sections from those docs
3. `google_search` (Browser Agent) → Discover recent public coverage
4. `navigate_to_url` + `extract_page_content` (Browser Agent) → Capture article content
5. `synthesize_content` (Writing Agent) → Merge internal + external insights
6. `create_slide_deck_content` (Writing Agent) → Draft slide outline
7. `create_keynote` (Presentation Agent) → Produce slide deck
8. `compose_email` (Email Agent) → Send deck to leadership distribution list
9. `reply_to_user` (Reply Agent) → Provide confirmation and artifact path

**Success Criteria**:
- ✅ Internal and external sources identified
- ✅ Insights synthesized into a unified narrative
- ✅ Slide deck generated and accessible
- ✅ Email drafted/sent with deck attached
- ✅ User receives final confirmation with artifact details

**Complexity**: 9 steps  
**Priority**: HIGH

---

### TEST H2: Meeting Recap Package with Audio Briefing
**User Query**: "Read emails from the past hour, summarize action items, save them as meeting notes, generate an audio briefing, and notify me"

**Expected Flow**:
1. `read_emails_by_time` (Email Agent) → Fetch emails from last hour
2. `summarize_emails` (Email Agent) → Extract key actions and decisions
3. `create_meeting_notes` (Writing Agent) → Produce structured meeting notes document
4. `text_to_speech` (Voice Agent) → Generate audio briefing
5. `send_notification` (Notifications Agent) → Alert the user that assets are ready
6. `reply_to_user` (Reply Agent) → Share document/audio locations

**Success Criteria**:
- ✅ Correct timeframe processed
- ✅ Action-oriented summary produced
- ✅ Meeting notes document generated
- ✅ Audio briefing successfully created
- ✅ Notification and final confirmation delivered

**Complexity**: 6 steps  
**Priority**: HIGH

---

### TEST H3: Screenshot Intelligence Digest
**User Query**: "Capture a screenshot of the current dashboard, analyze it, create a report, zip all evidence, and email it to me"

**Expected Flow**:
1. `take_screenshot` (Screen Agent) → Capture current UI state
2. `analyze_ui_screenshot` (Vision Agent) → Summarize notable elements
3. `create_detailed_report` (Writing Agent) → Document findings
4. `create_zip_archive` (File Agent) → Bundle screenshot and report
5. `compose_email` (Email Agent) → Email archive to user
6. `reply_to_user` (Reply Agent) → Confirm completion with artifact path

**Success Criteria**:
- ✅ Screenshot captured and analyzed successfully
- ✅ Report references vision insights
- ✅ ZIP archive contains both screenshot and report
- ✅ Email sent with archive attached
- ✅ Final confirmation returned to user

**Complexity**: 6 steps  
**Priority**: MEDIUM

---

## Success Metrics

### Overall System Health
- **Gold Standard**: ≥90% of HIGH/CRITICAL tests pass
- **Acceptable**: ≥75% of all tests pass
- **Needs Work**: <75% pass rate

### Individual Test Scoring
- **✅ PASS**: All success criteria met
- **⚠️ PARTIAL**: Some criteria met, documented issues
- **❌ FAIL**: Critical criteria failed
- **🔧 BLOCKED**: Cannot test (missing dependencies)

---

## Test Execution Framework

### For Each Test:
1. **Setup**: Document initial state
2. **Execute**: Run the query
3. **Observe**: Monitor each step
4. **Verify**: Check success criteria
5. **Document**: Record results
6. **Debug**: If failed, diagnose root cause

### Documentation Template:
```
TEST ID: [e.g., A1]
STATUS: [PASS/PARTIAL/FAIL/BLOCKED]
EXECUTION TIME: [seconds]
STEPS EXECUTED: [X/Y]
FAILURES: [List any]
ROOT CAUSE: [If failed]
FIX REQUIRED: [Description]
NOTES: [Any observations]
```

---

## Next Steps

1. **Create Test Execution Script** - Automate where possible
2. **Run Phase 1** - Validate benchmark
3. **Generate Detailed Report** - Document all findings
4. **Create Fix Recommendations** - Prioritize repairs
5. **Verify Fixes** - Re-run failed tests

---

**Total Test Cases**: 27 (21 functional + 3 edge cases + 3 utility)
**Estimated Execution Time**: 5-7 hours (manual) or 1.5-2.5 hours (automated)
**Expected Pass Rate**: 80-95% (based on system maturity)

---

*This test suite is designed to comprehensively evaluate your entire agentic system using multi-step workflows of similar complexity to your NVIDIA benchmark.*
