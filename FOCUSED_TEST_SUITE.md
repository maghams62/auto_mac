# Focused Multi-Step Test Suite
## Core Workflow Quality Assurance

**Date**: 2025-11-10
**Focus**: Financial, Document, Email, Folder, File, Writing, Presentation workflows
**Excluded**: WhatsApp, Twitter, Reddit, Maps (as requested)
**Complexity Benchmark**: NVIDIA stock → report → PDF → zip → email (5-step flow)

---

## Test Priority

**Testing**: Browser, File, Folder, Email, Writing, Presentation, Google Finance, Voice, Spotify, Notifications, Micro Actions, Vision

**Skipping**: WhatsApp, Twitter, Reddit, Maps

---

## FOCUSED TEST CASES

---

## Category A: Financial Data → Document Workflows

### TEST A1: Stock Analysis Full Pipeline ⭐ BENCHMARK
**User Query**: "Find the stock price of NVIDIA, create a report, turn it into a PDF, zip it, and email it to me"

**Expected Flow**:
1. `search_google_finance_stock` → Find NVDA ticker
2. `extract_google_finance_data` → Get stock price & data
3. `create_stock_report` → Generate report document
4. `create_zip_archive` → Zip the report
5. `compose_email` → Send email with ZIP attachment
6. `reply_to_user` → Confirm completion

**Success Criteria**:
- ✅ Finds NVDA ticker correctly
- ✅ Extracts current stock price
- ✅ Creates coherent report with data
- ✅ ZIP file created successfully
- ✅ Email sent with attachment
- ✅ User receives confirmation

**Execution**: AUTOMATED TEST
**Priority**: CRITICAL

---

### TEST A2: Multi-Stock Comparison Report
**User Query**: "Compare Apple, Microsoft, and Google stock prices, create a detailed report, and email it to me"

**Expected Flow**:
1. `search_google_finance_stock` (AAPL)
2. `extract_google_finance_data` (AAPL)
3. `search_google_finance_stock` (MSFT)
4. `extract_google_finance_data` (MSFT)
5. `search_google_finance_stock` (GOOGL)
6. `extract_google_finance_data` (GOOGL)
7. `create_detailed_report` → Synthesize comparison
8. `compose_email` → Send report
9. `reply_to_user` → Confirm

**Success Criteria**:
- ✅ Finds all 3 tickers
- ✅ Extracts data for each
- ✅ Report compares all 3 stocks
- ✅ Email delivered successfully

**Execution**: AUTOMATED TEST
**Priority**: HIGH
**Complexity**: 9 steps

---

### TEST A3: Stock Chart Capture with Report
**User Query**: "Get the stock chart for Tesla, create a report about it, and notify me"

**Expected Flow**:
1. `search_google_finance_stock` → TSLA
2. `capture_google_finance_chart` → Screenshot chart
3. `create_stock_report_from_google_finance` → Generate report
4. `send_notification` → Notify completion
5. `reply_to_user` → Show results

**Success Criteria**:
- ✅ Finds TSLA ticker
- ✅ Captures chart screenshot
- ✅ Creates report with chart reference
- ✅ Notification sent
- ✅ User sees results

**Execution**: AUTOMATED TEST
**Priority**: MEDIUM

---

## Category B: Folder Organization & File Management

### TEST B1: Organize Files by Type ⭐ NEW
**User Query**: "Organize files in my Downloads folder by type"

**Expected Flow**:
1. `folder_list` → List Downloads contents
2. `folder_organize_by_type` → Organize into categories
3. `reply_to_user` → Show organization results

**Success Criteria**:
- ✅ Lists all files in Downloads
- ✅ Organizes by type (documents, images, videos, etc.)
- ✅ Files moved to appropriate subfolders
- ✅ User sees clear summary

**Execution**: AUTOMATED TEST
**Priority**: HIGH
**Complexity**: 3 steps

---

### TEST B2: Find and Move Guitar Tab Files ⭐ NEW
**User Query**: "Move all guitar tab files into a folder called 'Guitar Tabs'"

**Expected Flow**:
1. `folder_list` → List current directory
2. `folder_apply` → Find files matching guitar tab pattern (*.gp*, *.tab, *.txt with "tab")
3. `folder_organize_by_type` OR custom organization → Move to "Guitar Tabs" folder
4. `reply_to_user` → Confirm files moved

**Success Criteria**:
- ✅ Finds all guitar tab files (.gp, .gp3, .gp4, .gp5, .tab, .txt)
- ✅ Creates "Guitar Tabs" folder if not exists
- ✅ Moves all matching files
- ✅ Reports number of files moved

**Execution**: AUTOMATED TEST
**Priority**: HIGH
**Complexity**: 4 steps

---

### TEST B3: Summarize Files in Folder ⭐ NEW
**User Query**: "Summarize all files in my Documents/Reports folder"

**Expected Flow**:
1. `folder_list` → List files in Documents/Reports
2. `search_documents` → Get file metadata
3. `extract_section` → Extract content from each file
4. `synthesize_content` → Create summary
5. `reply_to_user` → Deliver summary

**Success Criteria**:
- ✅ Lists all files in folder
- ✅ Extracts content from readable files
- ✅ Creates coherent summary
- ✅ Summary covers all files
- ✅ User receives summary

**Execution**: AUTOMATED TEST
**Priority**: HIGH
**Complexity**: 5 steps

---

### TEST B4: Summarize Folder and Email ⭐ NEW
**User Query**: "Summarize my Documents folder and email the summary to me"

**Expected Flow**:
1. `folder_list` → List Documents contents
2. `explain_folder` → Get folder analysis
3. `create_detailed_report` → Format as report
4. `compose_email` → Send summary
5. `reply_to_user` → Confirm sent

**Success Criteria**:
- ✅ Lists folder contents
- ✅ Analyzes folder structure and contents
- ✅ Creates detailed summary report
- ✅ Email sent with report
- ✅ User confirmation

**Execution**: AUTOMATED TEST
**Priority**: HIGH
**Complexity**: 5 steps

---

### TEST B5: Organize and Zip Files
**User Query**: "Organize files in my Downloads by type, then zip each category"

**Expected Flow**:
1. `folder_list` → List Downloads
2. `folder_organize_by_type` → Organize into categories
3. `create_zip_archive` × N → Zip each category folder
4. `reply_to_user` → Show results

**Success Criteria**:
- ✅ Organizes files by type
- ✅ Creates separate ZIP for each category
- ✅ All files included
- ✅ ZIPs created successfully

**Execution**: AUTOMATED TEST
**Priority**: MEDIUM
**Complexity**: 4+ steps

---

## Category C: Document Research & Content Creation

### TEST C1: Web Research to Presentation
**User Query**: "Search for 'AI trends 2024', extract the top 3 articles, create a slide deck about them"

**Expected Flow**:
1. `google_search` → Find articles
2. `navigate_to_url` × 3 → Visit top 3
3. `extract_page_content` × 3 → Get content
4. `create_slide_deck_content` → Create slides
5. `create_keynote` → Make presentation
6. `reply_to_user` → Deliver presentation path

**Success Criteria**:
- ✅ Finds relevant articles
- ✅ Extracts content from 3 sites
- ✅ Creates coherent slide deck
- ✅ Keynote file generated
- ✅ User gets file path

**Execution**: AUTOMATED TEST
**Priority**: HIGH
**Complexity**: 8 steps

---

### TEST C2: Document Search to Report
**User Query**: "Search my documents for files about 'quarterly results', synthesize the content, and create a detailed report"

**Expected Flow**:
1. `search_documents` → Find relevant docs
2. `extract_section` × N → Get content from found files
3. `synthesize_content` → Combine information
4. `create_detailed_report` → Format as report
5. `reply_to_user` → Deliver report

**Success Criteria**:
- ✅ Finds relevant documents
- ✅ Extracts key content
- ✅ Synthesizes coherently
- ✅ Creates well-formatted report
- ✅ User receives report

**Execution**: AUTOMATED TEST
**Priority**: HIGH
**Complexity**: 5+ steps

---

### TEST C3: Multi-Source Content Aggregation
**User Query**: "Search Google for 'electric vehicles', search my documents for EV reports, and create a comprehensive report combining both"

**Expected Flow**:
1. `google_search` → Web search
2. `navigate_to_url` → Visit top result
3. `extract_page_content` → Get web content
4. `search_documents` → Find local docs
5. `extract_section` → Get local content
6. `synthesize_content` → Combine sources
7. `create_detailed_report` → Create unified report
8. `reply_to_user` → Deliver report

**Success Criteria**:
- ✅ Searches web and local
- ✅ Extracts from both sources
- ✅ Creates unified report
- ✅ Report cites sources
- ✅ Content coherent

**Execution**: AUTOMATED TEST
**Priority**: MEDIUM
**Complexity**: 8 steps

---

## Category D: Email & Communication Workflows

### TEST D1: Email Read and Reply with Report
**User Query**: "Read my latest email, create a detailed response report, and reply with the report attached"

**Expected Flow**:
1. `read_latest_emails` → Get recent email
2. `create_detailed_report` → Create response
3. `reply_to_email` → Reply with attachment
4. `reply_to_user` → Confirm sent

**Success Criteria**:
- ✅ Reads latest email
- ✅ Understands email topic
- ✅ Creates relevant report
- ✅ Reply sent with attachment
- ✅ User confirmation

**Execution**: AUTOMATED TEST
**Priority**: HIGH
**Complexity**: 4 steps

---

### TEST D2: Email Summary and Forward
**User Query**: "Summarize all emails from the last 24 hours and email the summary to me"

**Expected Flow**:
1. `read_emails_by_time` → Get emails from last 24h
2. `summarize_emails` → Create summary
3. `compose_email` → Send summary
4. `reply_to_user` → Confirm

**Success Criteria**:
- ✅ Gets emails from correct timeframe
- ✅ Summarizes all emails
- ✅ Summary is coherent
- ✅ Email sent
- ✅ User confirmation

**Execution**: AUTOMATED TEST
**Priority**: MEDIUM
**Complexity**: 4 steps

---

### TEST D3: Selective Email Digest
**User Query**: "Read emails from john@example.com, summarize them, create a report, and email it back to him"

**Expected Flow**:
1. `read_emails_by_sender` → Get John's emails
2. `summarize_emails` → Summarize
3. `create_detailed_report` → Format as report
4. `compose_email` → Send to john@example.com
5. `reply_to_user` → Confirm

**Success Criteria**:
- ✅ Finds John's emails
- ✅ Summarizes correctly
- ✅ Creates report
- ✅ Sends to correct recipient
- ✅ User confirmation

**Execution**: AUTOMATED TEST
**Priority**: MEDIUM
**Complexity**: 5 steps

---

## Category E: Multi-Modal & Utility Workflows

### TEST E1: Voice Transcription to Document
**User Query**: "Transcribe the audio file at [path], create meeting notes from it, and email it to me"

**Expected Flow**:
1. `transcribe_audio_file` → Get transcription
2. `create_meeting_notes` → Format as notes
3. `compose_email` → Send notes
4. `reply_to_user` → Confirm

**Success Criteria**:
- ✅ Transcribes audio correctly
- ✅ Creates formatted notes
- ✅ Email sent with notes
- ✅ Notes are readable

**Execution**: MANUAL TEST (requires audio file)
**Priority**: MEDIUM
**Complexity**: 4 steps

---

### TEST E2: Screenshot Analysis to Report
**User Query**: "Take a screenshot, analyze what's on screen, create a report about it"

**Expected Flow**:
1. `take_screenshot` → Capture screen
2. `analyze_ui_screenshot` → Vision analysis
3. `create_detailed_report` → Create report
4. `reply_to_user` → Deliver report

**Success Criteria**:
- ✅ Screenshot captured
- ✅ Vision analysis works
- ✅ Report created from analysis
- ✅ Report is meaningful

**Execution**: AUTOMATED TEST
**Priority**: LOW
**Complexity**: 4 steps

---

### TEST E3: Text to Speech with Notification
**User Query**: "Create a voice message saying 'Your report is ready' and play it, then notify me"

**Expected Flow**:
1. `text_to_speech` → Generate audio
2. `launch_app` → Open audio player or play
3. `send_notification` → System notification
4. `reply_to_user` → Confirm

**Success Criteria**:
- ✅ TTS audio generated
- ✅ Audio file created
- ✅ Notification sent
- ✅ User confirmation

**Execution**: AUTOMATED TEST
**Priority**: LOW
**Complexity**: 4 steps

---

### TEST E4: Music Control with Timer
**User Query**: "Play music, set a timer for 10 minutes, then pause the music"

**Expected Flow**:
1. `play_music` → Start Spotify
2. `set_timer` → Set 10 min timer
3. *(Wait for timer - not testable immediately)*
4. `pause_music` → Stop music
5. `reply_to_user` → Confirm all set

**Success Criteria**:
- ✅ Music starts playing
- ✅ Timer set correctly
- ✅ Music pauses (manual verification)
- ✅ User confirmation

**Execution**: SEMI-AUTOMATED TEST
**Priority**: LOW
**Complexity**: 4 steps

---

## Category F: File Operations & Archives

### TEST F1: Document Archive with Email
**User Query**: "Find all PDFs in Documents, create a zip file, and email it to me"

**Expected Flow**:
1. `search_documents` → Find PDFs
2. `create_zip_archive` → Zip all PDFs
3. `compose_email` → Send with attachment
4. `reply_to_user` → Confirm

**Success Criteria**:
- ✅ Finds all PDF files
- ✅ Creates ZIP archive
- ✅ Email sent with ZIP
- ✅ User receives file

**Execution**: AUTOMATED TEST
**Priority**: MEDIUM
**Complexity**: 4 steps

---

### TEST F2: Screenshot Capture and Archive
**User Query**: "Take a screenshot, organize it into a Screenshots folder, and notify me"

**Expected Flow**:
1. `take_screenshot` → Capture screen
2. `organize_files` → Move to Screenshots folder
3. `send_notification` → Notify
4. `reply_to_user` → Confirm

**Success Criteria**:
- ✅ Screenshot captured
- ✅ Moved to Screenshots folder
- ✅ Notification sent
- ✅ User confirmation

**Execution**: AUTOMATED TEST
**Priority**: LOW
**Complexity**: 4 steps

---

### TEST F3: Bulk File Organization
**User Query**: "Organize all files in Downloads by date, create a report about what was organized, and email it"

**Expected Flow**:
1. `folder_list` → List Downloads
2. `folder_plan_alpha` → Plan organization
3. `folder_apply` → Execute organization
4. `explain_folder` → Analyze results
5. `create_detailed_report` → Create report
6. `compose_email` → Send report
7. `reply_to_user` → Confirm

**Success Criteria**:
- ✅ Lists all files
- ✅ Organizes by date
- ✅ Creates organization report
- ✅ Email sent
- ✅ User confirmation

**Execution**: AUTOMATED TEST
**Priority**: MEDIUM
**Complexity**: 7 steps

---

## Category G: Edge Cases & Error Handling

### TEST G1: Ambiguous Query Handling
**User Query**: "Email me about the stocks" (ambiguous)

**Expected Behavior**:
- System asks: "Which stocks would you like information about?"
- Should NOT proceed without clarification

**Success Criteria**:
- ✅ Detects ambiguity
- ✅ Asks clarifying question
- ❌ Does NOT proceed blindly

**Execution**: MANUAL TEST
**Priority**: CRITICAL

---

### TEST G2: Missing File Handling
**User Query**: "Create a report from the file 'nonexistent.pdf' and email it"

**Expected Behavior**:
- System responds: "File 'nonexistent.pdf' not found"
- Should NOT create empty report

**Success Criteria**:
- ✅ Detects missing file
- ✅ Returns clear error
- ❌ Does NOT continue with bad data

**Execution**: AUTOMATED TEST
**Priority**: CRITICAL

---

### TEST G3: Dependency Chain Failure
**User Query**: "Search Google Finance for INVALID_TICKER, create report, email it"

**Expected Behavior**:
- Step 1 fails → Stop execution
- Clear error message to user

**Success Criteria**:
- ✅ Detects step 1 failure
- ✅ Stops execution gracefully
- ✅ Reports clear error
- ❌ Does NOT continue

**Execution**: AUTOMATED TEST
**Priority**: CRITICAL

---

## Category H: Executive Briefing Workflows *(NEW)*

### TEST H1: Cross-Source Executive Briefing Pack
**User Query**: "Create an executive briefing on Project Atlas by combining my internal docs and the latest web coverage, build slides, and email them to leadership"

**Expected Flow**:
1. `search_documents` → Locate internal Project Atlas docs
2. `extract_section` → Pull critical sections for briefing
3. `google_search` → Identify recent public coverage
4. `navigate_to_url` + `extract_page_content` → Capture article content
5. `synthesize_content` → Merge internal and external insights
6. `create_slide_deck_content` → Draft slide narrative
7. `create_keynote` → Generate deck
8. `compose_email` → Email deck to leadership
9. `reply_to_user` → Provide confirmation and artifact path

**Success Criteria**:
- ✅ Both internal and external sources harvested
- ✅ Insights synthesized into cohesive storyline
- ✅ Slide deck generated and accessible
- ✅ Email drafted/sent with deck attached
- ✅ User receives final confirmation with artifact info

**Execution**: AUTOMATED TEST  
**Priority**: HIGH  
**Complexity**: 9 steps

---

### TEST H2: Meeting Recap Package with Audio Briefing
**User Query**: "Read emails from the past hour, summarize action items, save them as meeting notes, generate an audio briefing, and notify me"

**Expected Flow**:
1. `read_emails_by_time` → Fetch past-hour emails
2. `summarize_emails` → Extract action items
3. `create_meeting_notes` → Produce structured notes document
4. `text_to_speech` → Generate audio briefing
5. `send_notification` → Alert user that assets are ready
6. `reply_to_user` → Share document/audio locations

**Success Criteria**:
- ✅ Correct timeframe processed
- ✅ Action-oriented summary created
- ✅ Meeting notes document generated
- ✅ Audio briefing produced
- ✅ Notification + user confirmation delivered

**Execution**: AUTOMATED TEST  
**Priority**: HIGH  
**Complexity**: 6 steps

---

### TEST H3: Screenshot Intelligence Digest
**User Query**: "Capture a screenshot of the current dashboard, analyze it, create a report, zip all evidence, and email it to me"

**Expected Flow**:
1. `take_screenshot` → Capture dashboard
2. `analyze_ui_screenshot` → Summarize on-screen content
3. `create_detailed_report` → Document findings
4. `create_zip_archive` → Bundle screenshot + report
5. `compose_email` → Email archive
6. `reply_to_user` → Confirm completion with artifact path

**Success Criteria**:
- ✅ Screenshot captured and analyzed
- ✅ Report references analysis
- ✅ ZIP archive includes both assets
- ✅ Email sent with archive
- ✅ Final confirmation returned

**Execution**: AUTOMATED TEST  
**Priority**: MEDIUM  
**Complexity**: 6 steps

---

## Test Execution Summary

### Test Count by Category
- **Category A** (Financial): 3 tests
- **Category B** (Folder/Files): 5 tests
- **Category C** (Research/Content): 3 tests
- **Category D** (Email): 3 tests
- **Category E** (Multi-Modal): 4 tests
- **Category F** (File Ops): 3 tests
- **Category G** (Edge Cases): 3 tests
- **Category H** (Executive Workflows): 3 tests

**Total**: 27 focused tests

### Priority Breakdown
- **CRITICAL**: 4 tests (edge cases + benchmark)
- **HIGH**: 12 tests
- **MEDIUM**: 9 tests
- **LOW**: 2 tests

### Execution Type
- **AUTOMATED**: 23 tests
- **SEMI-AUTOMATED**: 1 test
- **MANUAL**: 3 tests

---

## Next Steps

1. ✅ Create automated test execution script
2. ✅ Run CRITICAL and HIGH priority tests first
3. ✅ Document all results
4. ✅ Generate comprehensive quality report
5. ✅ Provide fix recommendations for failures

Ready to execute these tests and generate the quality report!
