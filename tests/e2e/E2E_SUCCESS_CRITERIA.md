# End-to-End Test Success Criteria

## Overview

This document defines **comprehensive success criteria** for all end-to-end test scenarios. Each test must meet **ALL criteria** in its respective section to be considered passing. Tests are designed to validate the complete user workflow from query to UI rendering.

## General Success Criteria (Apply to All Tests)

All tests must meet these **baseline requirements**:
- ✅ **No Errors**: No error messages, exceptions, or "failed" status in response
- ✅ **Response Substance**: Response has meaningful content (meets minimum length requirement)
- ✅ **Expected Sources**: All expected data sources mentioned in response
- ✅ **No Parameter Errors**: Tools receive correct parameter types (no string/dict validation errors)
- ✅ **Workflow Completion**: All workflow steps executed successfully
- ✅ **UI Rendering**: Results properly displayed in UI with correct status indicators
- ✅ **Telemetry Capture**: Execution traces, tool calls, and artifacts properly recorded

---

## Test Scenario Success Criteria

### 🎯 **FINANCE-PRESENTATION-EMAIL** (Highest Priority - Multi-Step Complex Workflow)

**Test Query**: `"Fetch NVIDIA stock price, create a presentation, email it to me"`

**Winning Criteria** (ALL must pass):

#### 1. ✅ **Stock Data Retrieval** (Backend)
- Google Finance API called successfully
- Stock price, change, and trend data retrieved
- No API errors or timeouts
- Data includes: current price, change %, market cap, volume

#### 2. ✅ **Presentation Creation** (Backend)
- Presentation agent invoked with stock data
- Slides created with: title slide, data slide, analysis slide
- Chart/image included in presentation
- Presentation saved to `data/presentations/nvidia_stock.pptx`
- File exists and is > 100KB (indicating content)

#### 3. ✅ **Email Composition & Attachment** (Backend)
- Email agent invoked with presentation attachment
- `compose_email` called with `body` as string (not dict)
- `attachment_path` parameter correctly set to presentation file
- Email sent successfully (SMTP confirmation)

#### 4. ✅ **Email Delivery Verification** (Backend)
- Email appears in sent mailbox with correct subject
- Attachment present with filename `nvidia_stock.pptx`
- Attachment MIME type is `application/vnd.openxmlformats-officedocument.presentationml.presentation`
- Email body contains presentation reference

#### 5. ✅ **UI Timeline Display** (Frontend)
- Conversation shows "Presentation emailed" status card
- Attachment badge visible on message
- Download link functional
- Timeline shows all workflow steps: fetch → analyze → create → email

#### 6. ✅ **Workflow Telemetry** (System)
- Tool chain: `get_stock_price` → `create_presentation` → `compose_email`
- All steps marked as completed
- Execution time < 90 seconds
- No step failures or retries

**Failure Indicators**:
- ❌ Email sent without attachment → Critical failure
- ❌ Presentation creation fails → Workflow stops
- ❌ Stock data not retrieved → No content to present
- ❌ UI shows error state instead of success
- ❌ Attachment missing in sent email

---

### 📧 **EMAIL WORKFLOWS**

#### **Compose Email with Attachment**
**Query**: `"Compose an email to john@example.com about the quarterly report and attach the Q3_results.pdf"`

**Winning Criteria**:
- ✅ Email sent with subject "Quarterly Report"
- ✅ Attachment `Q3_results.pdf` present and valid
- ✅ Recipient `john@example.com` correct
- ✅ UI shows email sent confirmation

**Negative Test**: `"Send email without attachment"`
- ❌ Email sent without attachment → Should fail gracefully

#### **Reply to Email**
**Query**: `"Reply to the email from sarah about the meeting"`

**Winning Criteria**:
- ✅ Original email thread identified
- ✅ Reply sent with context preservation
- ✅ UI shows reply in conversation thread

#### **Forward Email**
**Query**: `"Forward the project update email to the team"`

**Winning Criteria**:
- ✅ Original email located
- ✅ Forwarded with original content
- ✅ Team recipients added correctly

#### **Email Search & Summarize**
**Query**: `"Find emails from last week about budget and summarize them"`

**Winning Criteria**:
- ✅ Search executed across email store
- ✅ Relevant emails found (> 0 results)
- ✅ Summary generated (> 200 characters)
- ✅ UI displays summary with email links

---

### 📅 **REMINDERS AUTOMATION**

#### **Create Reminder**
**Query**: `"Remind me to call Alex at 4pm tomorrow"`

**Winning Criteria**:
- ✅ Reminder stored in `data/recurring_tasks.json`
- ✅ Time parsed correctly (4:00 PM tomorrow)
- ✅ UI shows reminder created confirmation
- ✅ Scheduler entry created

#### **List Reminders**
**Query**: `"What reminders do I have?"`

**Winning Criteria**:
- ✅ All active reminders retrieved
- ✅ Chronological ordering
- ✅ UI displays reminder list with times

#### **Mark Done & Edit**
**Query**: `"Mark the Alex call reminder as done"` / `"Change the meeting time to 5pm"`

**Winning Criteria**:
- ✅ Reminder status updated
- ✅ Changes persisted to storage
- ✅ UI reflects updated state

---

### 🦋 **BLUESKY INTEGRATION**

#### **Post Update**
**Query**: `"Post 'Excited for the weekend!' to Bluesky"`

**Winning Criteria**:
- ✅ Post published successfully
- ✅ API call succeeds with valid auth
- ✅ UI shows post confirmation
- ✅ Post appears in feed

#### **Fetch Feed**
**Query**: `"Show me my recent Bluesky posts"`

**Winning Criteria**:
- ✅ Posts retrieved from API
- ✅ Timeline displays posts chronologically
- ✅ UI renders posts with proper formatting

#### **Summarize Notifications**
**Query**: `"Summarize my Bluesky notifications"`

**Winning Criteria**:
- ✅ Notifications fetched
- ✅ Summary generated (> 150 characters)
- ✅ UI shows notification summary

---

### ❓ **EXPLAIN COMMAND**

#### **Explain File**
**Query**: `"Explain src/agent/agent.py"`

**Winning Criteria**:
- ✅ File retrieved from repository
- ✅ Structured explanation with sections
- ✅ Key functions/classes documented
- ✅ UI displays formatted explanation

#### **Explain Functionality**
**Query**: `"Explain how reminders work"`

**Winning Criteria**:
- ✅ Relevant code sections found
- ✅ Process explanation provided
- ✅ Examples included in response

#### **Explain with Context**
**Query**: `"Explain the calendar integration"`

**Winning Criteria**:
- ✅ Multiple files analyzed
- ✅ Integration points explained
- ✅ Dependencies documented

---

### 📁 **FILE/FOLDER OPERATIONS**

#### **Search Files**
**Query**: `"Find all PDF files in the documents folder"`

**Winning Criteria**:
- ✅ Search executed recursively
- ✅ Correct files found
- ✅ UI displays file list with previews

#### **Organize Files**
**Query**: `"Group project files by type into folders"`

**Winning Criteria**:
- ✅ Files analyzed by extension/type
- ✅ Folders created with correct structure
- ✅ Files moved successfully
- ✅ UI updates file tree

#### **File Actions with Confirmation**
**Query**: `"Move the report.pdf to Archive folder"`

**Winning Criteria**:
- ✅ User confirmation requested
- ✅ Action only executed after confirmation
- ✅ File movement completed
- ✅ UI reflects new location

---

### 📆 **CALENDAR DAY VIEW** ("How's my day?")

#### **Multi-Source Synthesis**
**Query**: `"How's my day looking?"`

**Winning Criteria**:
- ✅ **Calendar Events**: Retrieved and listed chronologically
- ✅ **Email Context**: Recent relevant emails included
- ✅ **Reminders**: Active reminders for today
- ✅ **Synthesis**: Coherent day overview (> 300 characters)
- ✅ **Time-based Structure**: Morning/afternoon/evening sections
- ✅ **UI Timeline**: Visual calendar with events/reminders

#### **Complex Day Query**
**Query**: `"What's on my calendar and inbox today?"`

**Winning Criteria**:
- ✅ Both calendar and email sources retrieved
- ✅ Events and emails correlated by time/topic
- ✅ Summary mentions both sources
- ✅ No source conflicts or missing data

---

### 🎵 **SPOTIFY PLAYBACK**

#### **Play Track**
**Query**: `"Play 'Blinding Lights' by The Weeknd"`

**Winning Criteria**:
- ✅ Track located via Spotify API
- ✅ Playback started on active device
- ✅ UI shows current track info
- ✅ Player controls functional

#### **Queue Management**
**Query**: `"Queue the entire 'After Hours' playlist"`

**Winning Criteria**:
- ✅ Playlist found and loaded
- ✅ All tracks added to queue
- ✅ Playback continues seamlessly

#### **Playback Status**
**Query**: `"What's currently playing?"`

**Winning Criteria**:
- ✅ Current track information retrieved
- ✅ Progress and queue status shown
- ✅ UI displays player card with controls

#### **Device Handling**
**Query**: `"Play on my phone"` (when no device available)

**Winning Criteria**:
- ✅ Device selection prompted
- ✅ Playback starts on selected device
- ✅ No crash when device unavailable

---

### 🖼️ **IMAGE UNDERSTANDING**

#### **Pull Up Image**
**Query**: `"Pull up the mountain landscape image"`

**Winning Criteria**:
- ✅ Image located in document store
- ✅ Preview displayed in UI
- ✅ Full-size view available
- ✅ Image metadata shown

#### **Describe Document**
**Query**: `"Describe this PDF page"`

**Winning Criteria**:
- ✅ OCR executed successfully
- ✅ Text content extracted
- ✅ Summary generated from content
- ✅ UI shows description with preview

#### **Visual Search**
**Query**: `"Find images of charts"`

**Winning Criteria**:
- ✅ Visual search across documents
- ✅ Relevant images found
- ✅ Thumbnails displayed in results

---

## UI Regression Criteria

### **Conversational Cards**
- ✅ Message bubbles render correctly
- ✅ Status indicators show proper state
- ✅ Attachment badges appear for files
- ✅ Timeline shows workflow progress
- ✅ Error states display actionable messages

### **Toast Notifications**
- ✅ Success toasts for completed actions
- ✅ Error toasts for failures
- ✅ Progress indicators during execution
- ✅ Dismissible notifications

### **Sidebar Components**
- ✅ File tree updates after operations
- ✅ Recent conversations listed
- ✅ Search results properly formatted

---

## Telemetry & Debugging Criteria

### **Execution Traces**
- ✅ All tool calls recorded
- ✅ Parameter values captured
- ✅ Execution times measured
- ✅ Error stack traces preserved

### **Artifact Storage**
- ✅ Generated files saved to correct directories
- ✅ Email attachments preserved
- ✅ Screenshots captured on failures

### **Performance Metrics**
- ✅ End-to-end execution < 2 minutes for complex workflows
- ✅ API response times < 30 seconds
- ✅ UI rendering < 5 seconds

---

## Negative Test Criteria

### **Failure Scenarios**
- ✅ **Attachment Missing**: Email sent without attachment → Error surfaced, email not sent
- ✅ **API Failure**: Service down → Graceful degradation, user notification
- ✅ **Permission Denied**: File access blocked → Clear error message, no crash
- ✅ **Invalid Input**: Bad parameters → Validation error, helpful suggestions
- ✅ **Timeout**: Long-running operation → Progress indicator, eventual timeout message

### **Error Recovery**
- ✅ Failed operations retried when appropriate
- ✅ Partial success states handled gracefully
- ✅ User data preserved during failures
- ✅ Clear recovery instructions provided

---

## Test Execution Checklist

**Before marking any test as passing, verify:**
- [ ] All success criteria met for the specific scenario
- [ ] No errors in logs or responses
- [ ] Response meets minimum length requirements
- [ ] Expected sources mentioned in response
- [ ] UI renders results correctly
- [ ] Attachments/emails delivered properly
- [ ] Telemetry data captured
- [ ] Performance within acceptable limits
- [ ] Negative test cases also validated

---

## Success Rate Targets

- **Current Target**: 90% of criteria passing across all scenarios
- **Stretch Goal**: 100% of criteria passing
- **Critical Path**: Finance-Presentation-Email workflow must achieve 100%

---

## Failure Analysis Framework

When tests fail, categorize and fix in this order:

1. **Critical Failures** (Block all functionality)
   - API authentication issues
   - Core service unavailability
   - Data corruption

2. **Workflow Breaks** (Break specific flows)
   - Tool chaining failures
   - Parameter validation errors
   - State management issues

3. **UI/UX Issues** (Degrade user experience)
   - Rendering problems
   - Missing status indicators
   - Navigation issues

4. **Performance Issues** (Slow operation)
   - Timeouts
   - Memory leaks
   - Resource exhaustion

This framework ensures systematic fixing from most to least critical impact.
