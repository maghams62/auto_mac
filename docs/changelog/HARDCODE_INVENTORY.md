# Hardcode Inventory & Removal Plan

**Goal:** Move intelligence from code into prompts/config, keeping code as pure execution + validation.

---

## 1. DELIVERY INTENT DETECTION (agent.py)

### Current Hardcodes

**Location:** `src/agent/agent.py:213-225, 417-434, 673-716, 972-980`

```python
# Planning phase (line 214)
delivery_verbs = ["email", "send", "mail", "attach"]
needs_email_delivery = any(verb in user_request_lower for verb in delivery_verbs)

# Delivery guidance injection (line 218-225)
if needs_email_delivery:
    delivery_guidance = """
DELIVERY REQUIREMENT (AUTO-DETECTED):
- The user explicitly asked to email or send the results.
- Your plan MUST include a `compose_email` step...
"""

# DELIVERY GUARD (line 418-434)
if needs_email_delivery and not has_compose_email_step:
    # Reject plan with error

# Finalization messaging (line 673-716)
if email_result:
    if email_status_value == "sent":
        summary["message"] = f"{base_message}. Email sent as requested."
    elif email_status_value in {"draft", "drafted"}:
        summary["message"] = f"{base_message}. {draft_note}"
```

### Problems
- **4 separate locations** check for delivery verbs
- Hardcoded verb list duplicated across code
- Manual message construction based on email status
- Delivery guidance is code string, not prompt file

### Refactor Plan
1. **Move to Config** → `config.yaml`:
   ```yaml
   delivery:
     intent_verbs: [email, send, mail, attach]
     required_tool: compose_email
   ```

2. **Move to Prompts** → `prompts/task_decomposition.md`:
   - Add **"Delivery Intent Rule"** section (already exists, enhance it)
   - Provide few-shot examples for each verb pattern

3. **Code Changes**:
   - **Planning:** Load delivery verbs from config, inject prompt section
   - **Validation:** Check if plan violates delivery rule → reject (no auto-fix)
   - **Finalization:** Use `reply_to_user` outputs directly (no status inspection)

---

## 2. AUTO-CORRECTIONS IN PLAN VALIDATION (agent.py)

### Current Hardcodes

**Location:** `src/agent/agent.py:784-995` (`_validate_and_fix_plan`)

```python
# VALIDATION 0: Clean search_documents queries (line 832-845)
cleaned_query = re.sub(r'\b(files?|documents?|docs)\b', '', query_value, flags=re.IGNORECASE)
params["query"] = cleaned_query
corrections_made.append(...)

# VALIDATION 1: Fix invalid placeholders (line 848-877)
if invalid_pattern:
    params["details"] = f"$step{dup_step_id}.duplicates"
    corrections_made.append(...)

# VALIDATION 2: Add keynote attachments (line 880-901)
if not has_keynote_ref:
    params["attachments"] = [f"$step{keynote_step_id}.file_path"]
    corrections_made.append(...)

# VALIDATION 2b: Force send=true (line 904-914)
if send_flag is None or send_flag is False:
    params["send"] = True
    corrections_made.append(...)

# VALIDATION 2c: Add email body from previous steps (line 916-941)
if not body_value.strip():
    params["body"] = f"$step{candidate_step_id}.{field}"
    corrections_made.append(...)
```

### Problems
- **Code is modifying plans** instead of rejecting them
- Planner never learns from mistakes (corrections mask prompt issues)
- 5+ different auto-correction heuristics

### Refactor Plan
1. **Prompts Enhancement**:
   - Add **negative examples** showing what NOT to do
   - Expand few-shot examples to demonstrate correct patterns

2. **Validation → Rejection Only**:
   ```python
   # Instead of auto-fixing:
   if invalid_pattern:
       raise PlanValidationError("Plan uses invalid placeholder...")

   # Let planner retry with better guidance
   ```

3. **Remove All Auto-Corrections**:
   - ❌ Remove `corrections_made` list
   - ❌ Remove parameter modifications
   - ✅ Keep validation checks, change to raise errors

---

## 3. IMPOSSIBLE TASK GUARDS (agent.py)

### Current Hardcodes

**Location:** `src/agent/agent.py:357-396`

```python
# Check for common false negatives (line 362-378)
if ('duplicate' in user_request_lower and 'email' in user_request_lower):
    if 'folder_find_duplicates' in available_tools and 'compose_email' in available_tools:
        logger.warning("[GUARD] LLM incorrectly marked duplicate-email workflow as impossible...")
        false_negative = True

if ('duplicate' in user_request_lower and 'send' in user_request_lower):
    if 'folder_find_duplicates' in available_tools and 'compose_email' in available_tools:
        logger.warning("[GUARD] LLM incorrectly marked duplicate-send workflow as impossible...")
        false_negative = True
```

### Problems
- Hardcoded workflow patterns (`duplicate + email`)
- Code knows which workflows should work (should be in prompts)
- Manual override of planner's "impossible" decision

### Refactor Plan
1. **Prompt Enhancement** → `prompts/few_shot_examples.md`:
   - Add **"duplicate + email"** workflow example
   - Add **"search + send"** workflow example

2. **Remove Guards**:
   - If planner says "impossible", trust it
   - If prompt has examples, planner should succeed
   - Track failures → improve prompts, don't add code guards

---

## 4. SLASH COMMAND SPECIAL HANDLING

### Current Hardcodes

**Location:** `src/ui/slash_commands.py`

#### A. Bluesky Direct Routing (line 829-857)
```python
if agent_name == "bluesky":
    mode, params = self._parse_bluesky_task(task)
    tool_name = tool_map[mode]  # search/summary/post
    result = self.registry.execute_tool(tool_name, params)
```

#### B. Google Summarization (line 1540-1571)
```python
if agent_name == "google" and not result.get("error") and "results" in result:
    summary = self._summarize_google_results(search_results, query, agent)
    if summary:
        return {"summary": summary, "results": search_results}
```

#### C. LLM Fallback for Blocked Search (line 1341-1393, 1562-1570)
```python
def _get_llm_response_for_blocked_search(self, query: str, agent) -> str:
    # Use LLM to answer query when DuckDuckGo is blocked
    llm_response = llm.invoke(messages)
    return llm_response.content
```

### Problems
- **Agent-specific code paths** in slash command handler
- LLM routing logic (`_execute_agent_task`) duplicates planner's job
- Post-processing results instead of letting agents handle it

### Refactor Plan
1. **Multi-Step Slash Commands → Route to Planner**:
   ```python
   # Instead of direct execution:
   if self._is_complex_task(task):
       # Use full planner for multi-step workflows
       return agent.run(f"/{command} {task}")
   ```

2. **Single-Tool Calls → Use reply_to_user**:
   ```python
   # Agent returns result
   result = agent.execute(tool_name, params)

   # Format via reply_to_user (not code logic)
   return self.registry.execute_tool("reply_to_user", {
       "message": result.get("summary"),
       "details": result.get("details"),
       "artifacts": result.get("file_paths")
   })
   ```

3. **Remove Special Cases**:
   - ❌ Remove Bluesky task parsing (let planner decide)
   - ❌ Remove Google summarization (let Writing Agent handle)
   - ❌ Remove LLM fallback (let planner handle search failures)

---

## 5. TEMPERATURE OVERRIDES

### Current Hardcodes

**Location:** Multiple files

```python
# agent.py:86-89
if model and model.startswith(("o1", "o3", "o4")):
    temperature = 1
    logger.info(f"Using temperature=1 for o-series model: {model}")

# Various agents have hardcoded temperatures:
- vision_agent.py:74 → temperature=0.0
- planner.py:54 → temperature=0.2
- verifier.py:34 → temperature=0.0
- writing_agent.py:69 → temperature=0.3
- etc. (20+ locations)
```

### Problems
- **Model capabilities hardcoded** in multiple files
- No central source of truth for model requirements
- Temperature scattered across 20+ agent files

### Refactor Plan
1. **Move to Config** → `config.yaml`:
   ```yaml
   models:
     o_series:
       pattern: "^o[134]-"
       required_temperature: 1.0
       reason: "o-series models only support temperature=1"

     agents:
       vision: {temperature: 0.0}
       planner: {temperature: 0.2}
       writing: {temperature: 0.3}
   ```

2. **Centralized Model Manager**:
   ```python
   class ModelManager:
       def get_temperature(self, model_name: str, agent_type: str) -> float:
           # Check model constraints first
           # Then check agent-specific settings
           # Return validated temperature
   ```

3. **Remove Inline Overrides**:
   - All agents read from config via ModelManager
   - No hardcoded temperature values in agent files

---

## 6. MESSAGE FORMATTING HEURISTICS

### Current Hardcodes

**Location:** `src/agent/agent.py:596-753` (finalize), `api_server.py:174-200`

```python
# agent.py:672-716 - Email status messaging
if email_status_value == "sent":
    summary["message"] = f"{base_message}. Email sent as requested."
elif email_status_value in {"draft", "drafted"}:
    summary["message"] = f"{base_message}. {draft_note}"

# agent.py:652-670 - Extract message from step results
extracted_message = (
    step_result.get("summary") or
    step_result.get("message") or
    step_result.get("content") or
    step_result.get("response") or
    None
)

# api_server.py:179-186 - Maps URL detection
if "maps_url" in result:
    if "message" in result:
        return result["message"]
    else:
        return f"Here's your trip, enjoy: {maps_url}"
```

### Problems
- **Code constructs user-facing messages** instead of using tool outputs
- Multiple places inspect result structure and build strings
- Field priority hardcoded (`summary > message > content`)

### Refactor Plan
1. **Standardize via reply_to_user**:
   - **All tools** should call `reply_to_user` as final step
   - `reply_to_user` formats messages consistently

2. **Remove Message Construction**:
   ```python
   # Instead of:
   if email_status == "sent":
       message = f"{base}. Email sent."

   # Do:
   # email_agent calls reply_to_user with status
   # finalize() uses reply payload directly
   ```

3. **Template-Based Responses** (optional):
   ```yaml
   # config/message_templates.yaml
   email_sent: "{work_summary}. Email sent successfully."
   email_drafted: "{work_summary}. Email drafted for review."
   ```

---

## Summary: Removal Priority

### Phase 1 (High Impact)
- [ ] **Auto-corrections in validation** → Reject instead of fix
- [ ] **Delivery intent guards** → Move to prompts + config
- [ ] **Slash command special cases** → Route complex to planner

### Phase 2 (Medium Impact)
- [ ] **Temperature overrides** → Centralize in config + ModelManager
- [ ] **Message formatting** → Standardize via reply_to_user
- [ ] **Impossible task guards** → Remove, improve prompts

### Phase 3 (Polish)
- [ ] **Regression tests** → Verify prompt-driven planning works
- [ ] **Logging instrumentation** → Track prompt failures
- [ ] **Documentation** → Update prompts with all patterns

---

## Implementation Strategy

1. **Start with Validation** → Remove auto-corrections first
2. **Enhance Prompts** → Add examples for common patterns
3. **Test Failures** → When planner fails, improve prompts (not code)
4. **Iterate** → Gradually remove hardcodes, strengthen prompts
5. **Monitor** → Log rejection reasons to find prompt gaps

**Core Principle:** Code validates correctness. Prompts teach behavior.
