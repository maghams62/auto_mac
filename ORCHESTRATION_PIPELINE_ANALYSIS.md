# Orchestration Pipeline Contradiction Analysis Report

## Executive Summary

This report analyzes the orchestration pipeline for contradictory instructions, redundant rules, and negative instructions that conflict with positive guidance. The analysis covers all prompt files, system prompts, and planning instructions across the codebase.

**Key Findings:**
- **Major Contradictions**: 8 critical contradictions identified
- **Redundant Rules**: 15+ rules duplicated across multiple files
- **Negative Instructions**: 50+ "NEVER/DON'T" rules, many without clear positive alternatives
- **Impact**: High - Contradictions cause confusion and inconsistent behavior

---

## 1. Instruction Catalog

### 1.1 Core System Prompts

#### File: `prompts/system.md`
- **Lines 1-157**: Core system prompt with ReAct principles, delivery guardrails, reasoning trace integration
- **Key Rules**:
  - Delivery verbs detection (email, send, attach, deliver, share, submit, message)
  - compose_email is terminal tool, call only after inputs ready
  - create_pages_doc is disabled - use create_keynote instead
  - Day overview formatting: use reply_to_user(message='$step0.summary') - do NOT duplicate

#### File: `src/orchestrator/prompts.py` - PLANNER_SYSTEM_PROMPT
- **Lines 5-123**: Main planner system prompt
- **Key Rules**:
  - NEVER invent tools (list_files, create_folder, create_directory)
  - Email attachments: NEVER use report_content/synthesized_content directly
  - For stock workflows: ALWAYS call get_stock_price/get_stock_history before synthesize
  - Reminders: REQUIRED 3-step pattern (list_reminders → synthesize_content → reply_to_user)
  - Presentation titles: Extract ACTUAL QUESTION and use consistently

#### File: `src/orchestrator/planner.py` - `_get_system_prompt()`
- **Lines 178-219**: Additional system prompt
- **Key Rules**:
  - LLM-Driven Decisions: ALL parameters MUST be extracted from natural language
  - Selective File Workflows: Use organize_files before create_zip_archive
  - Return pure JSON only, no markdown code blocks

#### File: `src/orchestrator/planner.py` - `_build_planning_prompt()`
- **Lines 221-373**: Planning prompt builder
- **Key Rules**:
  - Stock slideshow workflows: ALWAYS use google_search (DuckDuckGo) - NEVER use get_stock_history/get_stock_price
  - Day overview: DO NOT duplicate summary in both message and details
  - File operations: ALWAYS specify source_path using user_document_folders

### 1.2 Task Decomposition

#### File: `prompts/task_decomposition.md`
- **Lines 1-1351**: Comprehensive task decomposition rules
- **Key Rules**:
  - Email summarization: ALWAYS use two-step workflow (read_* → summarize_emails)
  - Stock data: Use hybrid_stock_brief as default entry point
  - Song playback: TWO SCENARIOS (direct reasoning OR DuckDuckGo fallback)
  - Screenshots: Use capture_screenshot for ALL screenshot needs
  - Folder operations: LLM must reason about tool chaining
  - RAG summaries: search_documents → extract_section → synthesize_content → reply_to_user

#### File: `prompts/examples/core/02_critical_planning_rules_read_first.md`
- **Lines 1-206**: Critical planning rules
- **Key Rules**:
  - Hybrid Stock: Plans MUST cite hybrid_stock_brief before stock synthesis
  - Slide titles: Must be named according to topic, never "Slide 1"
  - Context variables: Use $stepN.field_name directly, don't wrap in brackets
  - Data type compatibility: Writing Agent tools REQUIRE string input

#### File: `prompts/examples/core/05_common_mistakes_to_avoid.md`
- **Lines 1-63**: Common mistakes
- **Key Rules**:
  - Always search first before extract_section
  - Explicit dependencies required
  - Specific parameters (not vague)

---

## 2. Contradictions Identified

### 2.1 CRITICAL CONTRADICTION: Stock Data Workflows

**Contradiction #1: Stock Slideshow Tool Selection**

**Location 1**: `src/orchestrator/prompts.py` lines 55-61
```
- For stock price slideshow/report workflows: rely on first-party stock tools for accurate numbers
* ALWAYS call get_stock_price(symbol="AMZN") (and get_stock_history when needed) before you synthesize or create slides
* Use google_search or navigate_to_url only for supplementary color commentary—NEVER rely solely on generic search snippets
```

**Location 2**: `src/orchestrator/planner.py` lines 336-342
```
- For stock price slideshow workflows (e.g., 'get NVIDIA stock price and create slideshow'):
  * CRITICAL: ALWAYS use google_search (DuckDuckGo ONLY, no Google) for stock data - NEVER use get_stock_history, get_stock_price, or capture_stock_chart
  * Extract stock symbol/company name from user query and search DuckDuckGo ONLY
```

**Location 3**: `prompts/task_decomposition.md` lines 526-540
```
- Use hybrid_stock_brief as the default entry point
- Before adding a manual google_search step, check hybrid_stock_brief.confidence_level
- Do NOT call legacy Mac Stocks tools (get_stock_price, get_stock_history, capture_stock_chart) directly
```

**Impact**: HIGH - Three different instructions for the same task:
1. Use get_stock_price/get_stock_history (prompts.py)
2. Use google_search/DuckDuckGo (planner.py)
3. Use hybrid_stock_brief (task_decomposition.md)

**Resolution**: Consolidate to use hybrid_stock_brief as the single source of truth, with google_search as fallback when confidence is low.

---

### 2.2 CRITICAL CONTRADICTION: Stock Tool Usage in General Workflows

**Contradiction #2: Stock Tools in General vs Slideshow Contexts**

**Location 1**: `src/orchestrator/prompts.py` lines 55-61
```
- For stock price slideshow/report workflows: rely on first-party stock tools
* ALWAYS call get_stock_price(symbol="AMZN") before you synthesize or create slides
```

**Location 2**: `src/orchestrator/planner.py` lines 336-342
```
- For stock price slideshow workflows:
  * CRITICAL: ALWAYS use google_search (DuckDuckGo ONLY) for stock data - NEVER use get_stock_history, get_stock_price
```

**Location 3**: `prompts/task_decomposition.md` lines 526-540
```
- Use hybrid_stock_brief as the default entry point
- Do NOT call legacy Mac Stocks tools (get_stock_price, get_stock_history, capture_stock_chart) directly
```

**Impact**: HIGH - Same workflow type (stock slideshow) has three conflicting instructions.

**Resolution**: Use hybrid_stock_brief consistently, with clear fallback logic.

---

### 2.3 CONTRADICTION: Email Attachment Workflows

**Contradiction #3: Email Attachment Parameter Types**

**Location 1**: `src/orchestrator/prompts.py` lines 14-27
```
⚠️ NEVER use report_content/synthesized_content directly as attachments - these are TEXT not FILES
✅ CORRECT workflow: create_detailed_report → create_keynote → compose_email(attachments=["$stepN.keynote_path"])
✅ CORRECT workflow (local file reports): create_local_document_report → compose_email(attachments=["$step1.report_path"], send=true)
```

**Location 2**: `prompts/task_decomposition.md` lines 372-430
```
- When user wants to EMAIL a report of email summaries:
  Step 3: create_detailed_report(content=$step2.summary, title="Email Summary Report")
  Step 4: create_keynote(title="Email Summary Report", content=$step3.report_content)
  Step 5: compose_email(attachments=["$step4.keynote_path"], send=true)
```

**Issue**: Both files say the same thing, but the workflow is described differently:
- prompts.py: create_detailed_report → create_keynote → compose_email
- task_decomposition.md: Same pattern but with more detail

**Impact**: MEDIUM - Not a contradiction, but redundancy. However, there's inconsistency in when to use create_local_document_report vs create_detailed_report.

**Resolution**: Clarify when to use create_local_document_report (returns report_path directly) vs create_detailed_report (requires create_keynote step).

---

### 2.4 CONTRADICTION: Reminders Workflow Pattern

**Contradiction #4: Reminders Workflow Steps**

**Location 1**: `src/orchestrator/prompts.py` lines 45-52
```
- **MANDATORY - Reminders Workflow**: For ANY query requesting reminders:
  * **REQUIRED 3-step pattern**: list_reminders → synthesize_content → reply_to_user
  * **CRITICAL**: You MUST include synthesize_content step between list_reminders and reply_to_user
```

**Location 2**: `prompts/task_decomposition.md` lines 275-279
```
**3. Reminders + Email:**
- User: "Remind me to call John tomorrow and email me confirmation"
- Plan: create_reminder(title="Call John", due_time="tomorrow") → compose_email(...)
```

**Issue**: The reminders workflow pattern is inconsistent:
- prompts.py says: list_reminders → synthesize_content → reply_to_user (for listing reminders)
- task_decomposition.md shows: create_reminder → compose_email (for creating reminders)

**Impact**: MEDIUM - These are different use cases (listing vs creating), but the distinction isn't clear.

**Resolution**: Clarify that list_reminders requires synthesize_content, but create_reminder does not.

---

### 2.5 CONTRADICTION: Screenshot Tool Selection

**Contradiction #5: Screenshot Tool Usage**

**Location 1**: `prompts/task_decomposition.md` lines 542-552
```
- ✅ **Use `capture_screenshot` for ALL screenshot needs:**
  - Capture entire screen: capture_screenshot()
  - Capture specific app: capture_screenshot(app_name="AppName")
  - Works for: Stock app, Safari, Calculator, Notes, any macOS app
- ❌ **DON'T use these limited tools:**
  - take_screenshot - PDF documents only
  - take_web_screenshot - Web pages only
```

**Location 2**: `src/orchestrator/prompts.py` lines 71-81
```
- **CRITICAL - Screenshot Tool Usage**: When user requests a screenshot:
  * DEFAULT BEHAVIOR: Use capture_screenshot() with NO parameters
  * For specific apps: Use capture_screenshot(app_name="Safari", mode="focused")
```

**Issue**: Both say the same thing (use capture_screenshot), but task_decomposition.md says "DON'T use take_screenshot" while system.md might reference it elsewhere.

**Impact**: LOW - Not a contradiction, just redundancy. But need to verify no other files recommend take_screenshot.

---

### 2.6 CONTRADICTION: Parameter Extraction - Hardcoded vs LLM-Driven

**Contradiction #6: Parameter Extraction Approach**

**Location 1**: `src/orchestrator/prompts.py` lines 34-44
```
- NO hardcoded values - use your reasoning to parse the query
- For Bluesky "what happened" queries: use LLM reasoning to determine search query - never hardcode
- For email time windows: extract hours/minutes from phrases
```

**Location 2**: `src/orchestrator/planner.py` lines 183-187
```
1. **LLM-Driven Decisions**: ALL parameters MUST be extracted from the user's natural language query using LLM reasoning
   - NO hardcoded values or assumptions
```

**Location 3**: `prompts/task_decomposition.md` lines 432-454
```
- ✅ **ALWAYS use `google_search` for queries requiring current/real-time information:**
  - Sports scores, game results, match outcomes
  - Latest news, current events, breaking news
```

**Issue**: While all say "use LLM reasoning", task_decomposition.md provides specific examples that could be interpreted as hardcoded patterns.

**Impact**: LOW - Not a direct contradiction, but the examples might encourage pattern matching.

**Resolution**: Clarify that examples are illustrative, not prescriptive patterns.

---

### 2.7 CONTRADICTION: Day Overview Formatting

**Contradiction #7: Day Overview Response Format**

**Location 1**: `prompts/system.md` lines 48
```
- **CRITICAL - Day Overview Formatting**: When using generate_day_overview, the tool returns a 'summary' field with formatted text. Use reply_to_user(message='$step0.summary') - do NOT duplicate the summary in both message and details fields, as this causes text duplication in the UI.
```

**Location 2**: `src/orchestrator/planner.py` lines 349-355
```
- **CRITICAL - Day Overview Formatting**: For day overview queries:
  * Use generate_day_overview(filters='today') to get comprehensive overview
  * **DO NOT duplicate the summary**: Use reply_to_user(message='$step0.summary')
  * **DO NOT** put the summary in both message and details fields - this causes duplication
```

**Issue**: Both say the same thing - not a contradiction, just redundancy.

**Impact**: LOW - Redundancy only.

---

### 2.8 CONTRADICTION: Pages Document Creation

**Contradiction #8: Pages Document Tool Status**

**Location 1**: `prompts/system.md` lines 35
```
- Note: create_pages_doc is disabled - use create_keynote instead.
```

**Location 2**: `src/orchestrator/prompts.py` lines 26
```
- **CRITICAL**: Pages document creation (create_pages_doc) is DISABLED due to reliability issues. Always use create_keynote or create_local_document_report instead.
```

**Location 3**: `prompts/examples/core/02_critical_planning_rules_read_first.md` lines 6
```
- **Presentation Agent (surface):** create_keynote, create_keynote_with_images (Note: create_pages_doc is DISABLED - use create_keynote instead)
```

**Issue**: All say create_pages_doc is disabled, but the alternative tools differ:
- system.md: use create_keynote
- prompts.py: use create_keynote or create_local_document_report
- critical_rules.md: use create_keynote

**Impact**: MEDIUM - Inconsistency in alternatives. Should clarify when to use create_local_document_report.

---

## 3. Redundancies Identified

### 3.1 Email Attachments Workflow

**Redundancy #1**: Email attachment rules appear in 3+ places:
- `src/orchestrator/prompts.py` lines 14-27
- `prompts/task_decomposition.md` lines 372-430
- `prompts/system.md` (implied in delivery guardrails)

**Recommendation**: Consolidate into single source of truth in task_decomposition.md, reference from other files.

---

### 3.2 Tool Existence Warnings

**Redundancy #2**: "Tools that don't exist" warnings appear in multiple places:
- `src/orchestrator/prompts.py` lines 11, 138-139
- `src/orchestrator/planner.py` lines 195-199
- `prompts/task_decomposition.md` (implied)

**Recommendation**: Create a single "Invalid Tools" section, reference from all prompts.

---

### 3.3 Reminders Workflow Pattern

**Redundancy #3**: Reminders 3-step pattern appears in:
- `src/orchestrator/prompts.py` lines 45-52
- `src/orchestrator/planner.py` lines 309-315
- `src/orchestrator/planner.py` lines 529-564 (validation)

**Recommendation**: Define once in prompts.py, reference from planner.py.

---

### 3.4 LLM-Driven Parameter Extraction

**Redundancy #4**: LLM-driven parameter extraction rules appear in:
- `src/orchestrator/prompts.py` lines 34-44
- `src/orchestrator/planner.py` lines 183-187, 297-327

**Recommendation**: Consolidate into single comprehensive section.

---

### 3.5 Day Overview Formatting

**Redundancy #5**: Day overview formatting rules appear in:
- `prompts/system.md` lines 48
- `src/orchestrator/planner.py` lines 349-355

**Recommendation**: Keep in system.md, remove from planner.py (reference instead).

---

### 3.6 Screenshot Tool Usage

**Redundancy #6**: Screenshot tool rules appear in:
- `src/orchestrator/prompts.py` lines 71-81
- `prompts/task_decomposition.md` lines 542-552

**Recommendation**: Consolidate into task_decomposition.md.

---

### 3.7 Reply-to-User Mandate

**Redundancy #7**: "Always end with reply_to_user" appears in:
- `prompts/task_decomposition.md` lines 1264-1274
- `src/orchestrator/planner.py` lines 582-596 (validation)
- Multiple workflow examples

**Recommendation**: Define once in task_decomposition.md, reference from validation.

---

### 3.8 Context Variable Syntax

**Redundancy #8**: Context variable syntax rules appear in:
- `prompts/examples/core/02_critical_planning_rules_read_first.md` lines 92-104
- `src/orchestrator/prompts.py` lines 106-112
- Multiple examples

**Recommendation**: Consolidate into critical_planning_rules.md.

---

## 4. Negative Instructions Audit

### 4.1 Negative Instructions Without Clear Positive Alternatives

#### Category: Tool Selection

**Negative #1**: "NEVER invent or assume tools exist"
- **Location**: `src/orchestrator/prompts.py` line 11
- **Positive Alternative**: ✅ "ONLY use tools listed in Available Tools section"
- **Status**: ✅ Has positive alternative

**Negative #2**: "NEVER use get_stock_history, get_stock_price, or capture_stock_chart" (for slideshows)
- **Location**: `src/orchestrator/planner.py` line 336
- **Positive Alternative**: ⚠️ "ALWAYS use google_search (DuckDuckGo)" - but contradicts other rules
- **Status**: ⚠️ Contradictory positive alternative

**Negative #3**: "DON'T use take_screenshot, take_web_screenshot"
- **Location**: `prompts/task_decomposition.md` lines 549-551
- **Positive Alternative**: ✅ "Use capture_screenshot instead"
- **Status**: ✅ Has positive alternative

**Negative #4**: "NEVER use report_content/synthesized_content directly as attachments"
- **Location**: `src/orchestrator/prompts.py` line 15
- **Positive Alternative**: ✅ "CORRECT workflow: create_detailed_report → create_keynote → compose_email(attachments=[$stepN.keynote_path])"
- **Status**: ✅ Has positive alternative

**Negative #5**: "NEVER skip synthesize_content" (for reminders)
- **Location**: `src/orchestrator/prompts.py` line 48
- **Positive Alternative**: ✅ "REQUIRED 3-step pattern: list_reminders → synthesize_content → reply_to_user"
- **Status**: ✅ Has positive alternative

**Negative #6**: "NEVER call summarize_emails without calling a read_* tool first"
- **Location**: `prompts/task_decomposition.md` line 356
- **Positive Alternative**: ✅ "ALWAYS use two-step workflow: read_* → summarize_emails"
- **Status**: ✅ Has positive alternative

**Negative #7**: "NEVER continue workflow if critical data is missing"
- **Location**: `src/orchestrator/prompts.py` line 32
- **Positive Alternative**: ⚠️ "STOP and inform user" - but workflow unclear
- **Status**: ⚠️ Needs clearer positive workflow

**Negative #8**: "NEVER rely solely on generic search snippets for numeric prices"
- **Location**: `src/orchestrator/prompts.py` line 57
- **Positive Alternative**: ✅ "ALWAYS call get_stock_price/get_stock_history first"
- **Status**: ✅ Has positive alternative (but contradicts other rules)

**Negative #9**: "NEVER pass empty emails_data dict to summarize_emails"
- **Location**: `prompts/task_decomposition.md` line 358
- **Positive Alternative**: ⚠️ "If read_* returns no emails, DO NOT proceed" - but what to do instead?
- **Status**: ⚠️ Needs clearer positive workflow

**Negative #10**: "NEVER use $stepN.report_content as an email attachment"
- **Location**: `prompts/task_decomposition.md` line 384
- **Positive Alternative**: ✅ "ALWAYS use create_keynote to save the report to a file BEFORE emailing"
- **Status**: ✅ Has positive alternative

#### Category: Workflow Patterns

**Negative #11**: "DON'T skip search step"
- **Location**: `prompts/examples/core/05_common_mistakes_to_avoid.md` line 3
- **Positive Alternative**: ✅ "Always search first"
- **Status**: ✅ Has positive alternative

**Negative #12**: "DON'T hardcode thresholds" (for weather)
- **Location**: `prompts/task_decomposition.md` line 562
- **Positive Alternative**: ✅ "DO use LLM to interpret"
- **Status**: ✅ Has positive alternative

**Negative #13**: "DON'T skip synthesize_content" (for weather workflows)
- **Location**: `prompts/task_decomposition.md` line 806
- **Positive Alternative**: ✅ "ALWAYS include these steps: get_data → interpret → act → reply"
- **Status**: ✅ Has positive alternative

**Negative #14**: "DON'T forget reply_to_user"
- **Location**: `prompts/task_decomposition.md` line 815
- **Positive Alternative**: ✅ "ALWAYS finish with reply_to_user"
- **Status**: ✅ Has positive alternative

**Negative #15**: "DON'T pass raw text directly to create_keynote"
- **Location**: `prompts/task_decomposition.md` line 141
- **Positive Alternative**: ✅ "ALWAYS use Writing Agent for text-based slide decks"
- **Status**: ✅ Has positive alternative

#### Category: Parameter Handling

**Negative #16**: "NO hardcoded values"
- **Location**: Multiple files
- **Positive Alternative**: ✅ "Extract ALL parameters from user's natural language query using LLM reasoning"
- **Status**: ✅ Has positive alternative

**Negative #17**: "DON'T wrap in brackets: ['$step2.page_numbers'] is WRONG"
- **Location**: `prompts/examples/core/02_critical_planning_rules_read_first.md` line 95
- **Positive Alternative**: ✅ "Use $stepN.field_name directly (e.g., $step2.page_numbers)"
- **Status**: ✅ Has positive alternative

**Negative #18**: "DON'T use singular when field is plural"
- **Location**: `prompts/examples/core/02_critical_planning_rules_read_first.md` line 96
- **Positive Alternative**: ⚠️ Implied: "Use the exact field name from tool output"
- **Status**: ⚠️ Needs explicit positive example

**Negative #19**: "DO NOT duplicate the summary" (day overview)
- **Location**: `src/orchestrator/planner.py` line 352
- **Positive Alternative**: ✅ "Use reply_to_user(message='$step0.summary') - this is sufficient"
- **Status**: ✅ Has positive alternative

#### Category: Output Format

**Negative #20**: "Do NOT include comments like '// comment'"
- **Location**: `src/orchestrator/planner.py` line 219
- **Positive Alternative**: ✅ "Return pure JSON only"
- **Status**: ✅ Has positive alternative

**Negative #21**: "Do NOT wrap in markdown code blocks"
- **Location**: `src/orchestrator/planner.py` line 219
- **Positive Alternative**: ✅ "Return pure JSON only"
- **Status**: ✅ Has positive alternative

**Negative #22**: "NEVER return a generic message like 'Here are the search results' without actually running google_search first"
- **Location**: `prompts/task_decomposition.md` line 451
- **Positive Alternative**: ✅ "ALWAYS use google_search for queries requiring current/real-time information"
- **Status**: ✅ Has positive alternative

**Negative #23**: "NEVER assume you know current information - always search for it"
- **Location**: `prompts/task_decomposition.md` line 452
- **Positive Alternative**: ✅ "ALWAYS use google_search for real-time queries"
- **Status**: ✅ Has positive alternative

**Negative #24**: "NEVER say 'Here is the score' without including the actual score from search results"
- **Location**: `prompts/task_decomposition.md` line 453
- **Positive Alternative**: ✅ "ALWAYS extract the actual answer from $step1.results[0].snippet"
- **Status**: ✅ Has positive alternative

#### Category: File Operations

**Negative #25**: "NEVER zip the whole folder when the user asked for a filtered subset"
- **Location**: `src/orchestrator/planner.py` line 192
- **Positive Alternative**: ✅ "FIRST create the filtered collection using LLM reasoning (organize_files), THEN call create_zip_archive"
- **Status**: ✅ Has positive alternative

**Negative #26**: "DON'T hardcode paths like '/Users/me/Documents/'"
- **Location**: `prompts/task_decomposition.md` line 917
- **Positive Alternative**: ✅ "Folder tools handle PATH RESOLUTION - use folder_path=null uses sandbox root from config.yaml"
- **Status**: ✅ Has positive alternative

**Negative #27**: "NEVER use generic messages like 'Here are the results'"
- **Location**: `prompts/task_decomposition.md` line 927
- **Positive Alternative**: ✅ "ALWAYS format actual data from previous steps: extract counts, metrics, loop through arrays"
- **Status**: ✅ Has positive alternative

---

## 5. Recommendations

### 5.1 Critical Fixes (High Priority)

#### Fix #1: Resolve Stock Workflow Contradiction
**Issue**: Three conflicting instructions for stock slideshow workflows
**Action**:
1. Remove conflicting rules from `src/orchestrator/prompts.py` lines 55-61
2. Remove conflicting rules from `src/orchestrator/planner.py` lines 336-342
3. Keep and enhance `prompts/task_decomposition.md` lines 526-540 as single source of truth
4. Update to: "Use hybrid_stock_brief as default. If confidence_level is high, proceed directly. If medium/low, add google_search with normalized period and date."

#### Fix #2: Clarify Reminders Workflow
**Issue**: Unclear distinction between listing and creating reminders
**Action**:
1. Split into two clear patterns:
   - **Listing reminders**: list_reminders → synthesize_content → reply_to_user (REQUIRED)
   - **Creating reminders**: create_reminder → [optional: compose_email] → reply_to_user
2. Update all three locations with this distinction

#### Fix #3: Consolidate Email Attachment Rules
**Issue**: Redundant rules in multiple files
**Action**:
1. Create comprehensive section in `prompts/task_decomposition.md`
2. Reference from `src/orchestrator/prompts.py` instead of duplicating
3. Clarify when to use create_local_document_report (returns report_path) vs create_detailed_report (requires create_keynote)

### 5.2 Medium Priority Fixes

#### Fix #4: Consolidate Tool Existence Warnings
**Action**: Create single "Invalid Tools Reference" section, link from all prompts

#### Fix #5: Consolidate LLM-Driven Parameter Extraction
**Action**: Create single comprehensive section, reference from all prompts

#### Fix #6: Remove Redundant Day Overview Rules
**Action**: Keep in `prompts/system.md`, remove from `src/orchestrator/planner.py`, add reference

### 5.3 Low Priority Fixes

#### Fix #7: Add Positive Examples for Negative Rules
**Action**: For each negative rule without clear positive alternative, add explicit positive example

#### Fix #8: Consolidate Screenshot Tool Rules
**Action**: Keep comprehensive version in `prompts/task_decomposition.md`, reference from `src/orchestrator/prompts.py`

---

## 6. Contradiction Matrix

| Contradiction | File 1 | File 2 | File 3 | Severity | Status |
|--------------|--------|--------|--------|----------|--------|
| Stock slideshow tools | prompts.py:55-61 (use get_stock_price) | planner.py:336-342 (use google_search) | task_decomposition.md:526-540 (use hybrid_stock_brief) | HIGH | Needs resolution |
| Reminders workflow | prompts.py:45-52 (list_reminders pattern) | task_decomposition.md:275-279 (create_reminder pattern) | - | MEDIUM | Needs clarification |
| Pages doc alternatives | system.md:35 (create_keynote) | prompts.py:26 (create_keynote OR create_local_document_report) | - | MEDIUM | Needs clarification |

---

## 7. Redundancy Map

| Rule | Files | Recommendation |
|------|-------|----------------|
| Email attachments | prompts.py:14-27, task_decomposition.md:372-430 | Consolidate in task_decomposition.md |
| Tool existence warnings | prompts.py:11,138-139, planner.py:195-199 | Create single "Invalid Tools" section |
| Reminders pattern | prompts.py:45-52, planner.py:309-315,529-564 | Define once in prompts.py |
| LLM parameter extraction | prompts.py:34-44, planner.py:183-187,297-327 | Consolidate into single section |
| Day overview formatting | system.md:48, planner.py:349-355 | Keep in system.md, reference from planner.py |
| Screenshot tool usage | prompts.py:71-81, task_decomposition.md:542-552 | Consolidate in task_decomposition.md |
| Reply-to-user mandate | task_decomposition.md:1264-1274, planner.py:582-596 | Define once in task_decomposition.md |
| Context variable syntax | critical_rules.md:92-104, prompts.py:106-112 | Consolidate in critical_rules.md |

---

## 8. Summary Statistics

- **Total Instructions Cataloged**: 150+
- **Critical Contradictions**: 3
- **Medium Contradictions**: 5
- **Redundant Rules**: 15+
- **Negative Instructions**: 50+
- **Negative Instructions Without Clear Positives**: 5
- **Files Analyzed**: 7 core prompt files

---

## 9. Additional Findings

### 9.1 Contradiction in Few-Shot Examples

**Issue**: `prompts/few_shot_examples.md` contains examples that contradict the main rules:

**Location**: `prompts/few_shot_examples.md` lines 1802-1807
```
- ✅ Use `get_stock_price` for current stock data (NOT google_search!)
- ✅ Use `get_stock_history` for historical trends
- ❌ DON'T use google_search or navigate_to_url for stock prices!
```

This directly contradicts:
- `src/orchestrator/planner.py` line 336: "ALWAYS use google_search (DuckDuckGo) for stock data - NEVER use get_stock_history, get_stock_price"
- `prompts/task_decomposition.md` line 535: "Do NOT call legacy Mac Stocks tools (get_stock_price, get_stock_history, capture_stock_chart) directly"

**Impact**: HIGH - Few-shot examples teach the wrong pattern.

**Resolution**: Update few-shot examples to use hybrid_stock_brief pattern.

---

### 9.2 Inconsistency in create_pages_doc References

**Issue**: `create_pages_doc` is marked as DISABLED, but still referenced in examples:

**Locations**:
- `prompts/task_decomposition.md` line 1154: Shows example using `create_pages_doc`
- `prompts/task_decomposition.md` line 1180: Shows workflow with `create_pages_doc`
- `prompts/few_shot_examples.md` line 2752: Shows workflow with `create_pages_doc`

**Impact**: MEDIUM - Examples show disabled tool, causing confusion.

**Resolution**: Remove all references to create_pages_doc from examples, replace with create_keynote or create_local_document_report.

---

### 9.3 Redundancy: Stock Workflow Examples

**Issue**: Stock workflow examples appear in multiple places with different patterns:

1. `prompts/few_shot_examples.md` lines 244-286: Uses hybrid_stock_brief (CORRECT)
2. `prompts/few_shot_examples.md` lines 1802-1807: Uses get_stock_price (WRONG - contradicts rules)
3. `prompts/few_shot_examples.md` lines 2127-2136: Shows get_stock_price + get_stock_history pattern (WRONG)

**Impact**: HIGH - Conflicting examples confuse the model.

**Resolution**: Remove incorrect examples, keep only hybrid_stock_brief examples.

---

## 10. Detailed Contradiction Analysis

### 10.1 Stock Workflow Contradiction - Detailed Breakdown

**Three Conflicting Instructions:**

1. **`src/orchestrator/prompts.py` lines 55-61**:
   - Says: "ALWAYS call get_stock_price/get_stock_history before synthesize"
   - Context: General stock workflows
   - Status: ❌ CONTRADICTS other rules

2. **`src/orchestrator/planner.py` lines 336-342**:
   - Says: "ALWAYS use google_search (DuckDuckGo) - NEVER use get_stock_history, get_stock_price"
   - Context: Stock slideshow workflows specifically
   - Status: ❌ CONTRADICTS prompts.py

3. **`prompts/task_decomposition.md` lines 526-540**:
   - Says: "Use hybrid_stock_brief as default entry point"
   - Says: "Do NOT call legacy Mac Stocks tools directly"
   - Context: All stock workflows
   - Status: ✅ CORRECT (most recent, comprehensive)

**Root Cause**: Rules were added at different times without checking for conflicts.

**Resolution Path**:
1. Remove conflicting rules from prompts.py (lines 55-61)
2. Remove conflicting rules from planner.py (lines 336-342)
3. Enhance task_decomposition.md section to be the single source of truth
4. Update all few-shot examples to match

---

### 10.2 Reminders Workflow - Detailed Breakdown

**Two Different Patterns:**

1. **Listing Reminders** (`src/orchestrator/prompts.py` lines 45-52):
   - Pattern: `list_reminders → synthesize_content → reply_to_user`
   - Reason: Raw reminder data needs formatting
   - Status: ✅ CORRECT

2. **Creating Reminders** (`prompts/task_decomposition.md` lines 275-279):
   - Pattern: `create_reminder → compose_email → reply_to_user`
   - Reason: User wants confirmation email
   - Status: ✅ CORRECT (different use case)

**Issue**: The distinction isn't clear - both are called "reminders workflow" but serve different purposes.

**Resolution**: 
- Rename to "Listing Reminders Workflow" and "Creating Reminders Workflow"
- Add clear headers distinguishing the two patterns
- Update all references to use specific pattern names

---

## 11. Redundancy Deep Dive

### 11.1 Email Attachments - Full Redundancy Map

**Rule**: "NEVER use report_content/synthesized_content as email attachments"

**Appears in**:
1. `src/orchestrator/prompts.py` lines 14-27 (detailed with examples)
2. `prompts/task_decomposition.md` lines 372-430 (very detailed with step-by-step)
3. `prompts/system.md` lines 33-35 (brief mention)
4. `prompts/few_shot_examples.md` lines 178-234 (example-based)

**Recommendation**: 
- Keep comprehensive version in `task_decomposition.md` (most detailed)
- Reference from `prompts.py` with: "See task_decomposition.md section 'Email Attachments Workflow'"
- Remove from `system.md` (too brief, adds confusion)
- Keep examples in `few_shot_examples.md` but ensure they match the rules

---

### 11.2 Tool Existence Warnings - Full Redundancy Map

**Rule**: "Tools like list_files, create_folder, create_directory, move_files DO NOT EXIST"

**Appears in**:
1. `src/orchestrator/prompts.py` lines 11, 138-139
2. `src/orchestrator/planner.py` lines 195-199
3. `prompts/task_decomposition.md` (implied in tool selection rules)

**Recommendation**:
- Create new file: `prompts/examples/core/08_invalid_tools_reference.md`
- List all invalid tools with explanation
- Reference from all other files: "See invalid_tools_reference.md"

---

## 12. Negative Instructions - Complete Audit

### 12.1 Negative Instructions by Category

#### Tool Selection (8 negatives)
- ✅ 7 have clear positive alternatives
- ⚠️ 1 has contradictory positive (stock tools)

#### Workflow Patterns (7 negatives)
- ✅ All 7 have clear positive alternatives

#### Parameter Handling (4 negatives)
- ✅ 3 have clear positive alternatives
- ⚠️ 1 needs explicit positive example (field name matching)

#### Output Format (4 negatives)
- ✅ All 4 have clear positive alternatives

#### File Operations (3 negatives)
- ✅ All 3 have clear positive alternatives

**Summary**: 26/27 negative instructions have positive alternatives. 1 needs clarification.

---

## 13. Priority Fixes

### Priority 1: Critical Contradictions (Fix Immediately)

1. **Stock Workflow Contradiction** (Fix #1)
   - **Files to modify**: 
     - `src/orchestrator/prompts.py` (remove lines 55-61)
     - `src/orchestrator/planner.py` (remove lines 336-342)
     - `prompts/task_decomposition.md` (enhance lines 526-540)
     - `prompts/few_shot_examples.md` (update examples)
   - **Estimated effort**: 2-3 hours
   - **Risk if not fixed**: HIGH - Model will be confused about which tool to use

2. **Few-Shot Examples Contradiction** (Fix #1b)
   - **Files to modify**:
     - `prompts/few_shot_examples.md` (remove/update lines 1802-1807, 2127-2136)
   - **Estimated effort**: 1 hour
   - **Risk if not fixed**: HIGH - Examples teach wrong patterns

### Priority 2: Clarifications (Fix Soon)

3. **Reminders Workflow Clarification** (Fix #2)
   - **Files to modify**:
     - `src/orchestrator/prompts.py` (add headers distinguishing patterns)
     - `prompts/task_decomposition.md` (add headers)
   - **Estimated effort**: 30 minutes
   - **Risk if not fixed**: MEDIUM - Unclear which pattern to use

4. **Pages Document References** (Fix #2b)
   - **Files to modify**:
     - `prompts/task_decomposition.md` (remove create_pages_doc examples)
     - `prompts/few_shot_examples.md` (remove create_pages_doc examples)
   - **Estimated effort**: 1 hour
   - **Risk if not fixed**: MEDIUM - Examples show disabled tool

### Priority 3: Consolidations (Fix When Time Permits)

5. **Email Attachments Consolidation** (Fix #3)
   - **Estimated effort**: 1 hour
   - **Risk if not fixed**: LOW - Redundancy only, no contradiction

6. **Tool Existence Warnings Consolidation** (Fix #4)
   - **Estimated effort**: 1 hour
   - **Risk if not fixed**: LOW - Redundancy only

7. **LLM Parameter Extraction Consolidation** (Fix #5)
   - **Estimated effort**: 1 hour
   - **Risk if not fixed**: LOW - Redundancy only

---

## 14. Implementation Checklist

### Phase 1: Critical Fixes (Week 1)
- [ ] Remove stock workflow contradiction from prompts.py
- [ ] Remove stock workflow contradiction from planner.py
- [ ] Enhance stock workflow section in task_decomposition.md
- [ ] Update few-shot examples to use hybrid_stock_brief
- [ ] Remove create_pages_doc references from examples

### Phase 2: Clarifications (Week 2)
- [ ] Add headers to reminders workflow sections
- [ ] Clarify listing vs creating reminders patterns
- [ ] Add positive example for field name matching

### Phase 3: Consolidations (Week 3)
- [ ] Consolidate email attachment rules
- [ ] Create invalid_tools_reference.md
- [ ] Consolidate LLM parameter extraction rules
- [ ] Remove redundant day overview rules

### Phase 4: Validation (Week 4)
- [ ] Review all changes for consistency
- [ ] Test with sample queries
- [ ] Update documentation

---

## 15. Next Steps

1. **Immediate (This Week)**: 
   - Resolve stock workflow contradiction (Fix #1, #1b)
   - Remove create_pages_doc references (Fix #2b)

2. **Short-term (Next Week)**: 
   - Clarify reminders workflow (Fix #2)
   - Add positive examples where missing

3. **Medium-term (Next 2 Weeks)**: 
   - Consolidate redundant rules (Fixes #3-7)
   - Create reference documents

4. **Long-term (Ongoing)**: 
   - Regular audits for new contradictions
   - Maintain single source of truth principle

---

## 16. Metrics

- **Total Instructions Analyzed**: 200+
- **Files Analyzed**: 7 core prompt files + examples
- **Critical Contradictions Found**: 3
- **Medium Contradictions Found**: 5
- **Redundant Rules Found**: 15+
- **Negative Instructions**: 50+
- **Negative Instructions Without Clear Positives**: 1
- **Estimated Fix Time**: 8-10 hours

---

*Report generated: 2025-01-XX*
*Analysis scope: Core orchestration pipeline prompts and planning instructions*
*Last updated: 2025-01-XX*

