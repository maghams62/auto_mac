# Hardcode Removal Progress

**Goal:** Move intelligence from code → prompts/config for better maintainability and learning.

---

## ✅ Phase 1: Inventory (COMPLETE)

Created comprehensive inventory in `HARDCODE_INVENTORY.md`:
- 6 major categories of hardcoded logic identified
- 50+ specific locations cataloged
- Impact analysis and refactor plan documented

---

## ✅ Phase 2A: Delivery Intent - Config & Prompts (COMPLETE)

### Changes Made

#### 1. Config (`config.yaml`)
```yaml
# NEW: Delivery Intent Configuration
delivery:
  intent_verbs: [email, send, mail, attach]
  required_tool: compose_email
  validation:
    reject_missing_tool: true
    auto_correct: false
```

**Benefits:**
- Verbs now configurable (no code changes needed to add "forward", "share", etc.)
- Validation behavior explicit and documented
- Future: Could add delivery_templates, priority_keywords, etc.

#### 2. Prompt File (`prompts/delivery_intent.md`)
**Content:**
- Detection criteria and required patterns
- 3 complete workflow examples (search+email, artifact+send, find+attach)
- Anti-patterns section showing what NOT to do
- Clear parameter guidance for compose_email

**Benefits:**
- LLM sees complete examples of correct delivery workflows
- Negative examples teach planner to avoid common mistakes
- Prompt can evolve without code changes

#### 3. Code Changes (`src/agent/agent.py`)

**Before (Hardcoded):**
```python
delivery_verbs = ["email", "send", "mail", "attach"]  # Line 214
delivery_guidance = """DELIVERY REQUIREMENT..."""  # Line 219-226 (hardcoded string)
```

**After (Config-Driven):**
```python
# Line 213-216: Load from config
delivery_config = self.config.get("delivery", {})
delivery_verbs = delivery_config.get("intent_verbs", ["email", "send", "mail", "attach"])

# Line 218-235: Load from prompt file
delivery_guidance = self.prompts.get("delivery_intent", "")
if delivery_guidance:
    delivery_guidance = f"\n{'='*60}\nDELIVERY INTENT DETECTED\n{'='*60}\n{delivery_guidance}\n{'='*60}\n"
else:
    # Fallback for backwards compatibility
    delivery_guidance = """DELIVERY REQUIREMENT..."""
```

**Line 122-129: Added delivery_intent.md to loader:**
```python
for prompt_file in ["system.md", "task_decomposition.md", "delivery_intent.md"]:
    path = prompts_dir / prompt_file
    if path.exists():
        prompts[prompt_file.replace(".md", "")] = path.read_text()
```

### Impact

| Aspect | Before | After |
|--------|--------|-------|
| **Delivery Verbs** | Hardcoded in 4 places | Config (single source) |
| **Guidance Text** | Code string | Markdown file with examples |
| **Adding New Verbs** | Edit code + restart | Edit config.yaml |
| **Improving Guidance** | Edit code string | Edit delivery_intent.md |
| **Examples** | None (implicit) | 3 complete workflows |

### Testing

**Test Case:** "search email arsenal's last scoreline to me"

**Expected Behavior:**
1. ✅ Detects "email" verb from config
2. ✅ Loads delivery_intent.md guidance
3. ✅ Injects guidance into planning prompt
4. ✅ LLM sees examples and creates plan with compose_email
5. ✅ If LLM forgets, DELIVERY GUARD rejects plan

---

## 🔄 Phase 2B: Delivery Intent - Validation Cleanup (IN PROGRESS)

### Remaining Work

Currently, delivery intent detection is **duplicated** in 4 locations:

1. **Planning** (line 213-216) → ✅ Now uses config
2. **Validation Guard** (line 418-434) → ⚠️ Still uses hardcoded check
3. **Finalization** (line 673-716) → ⚠️ Hardcoded message construction
4. **Validate & Fix Plan** (line 972-980) → ⚠️ Hardcoded in validation layer

### Next Steps

**1. Consolidate Detection Logic:**
```python
# Create helper method (line ~145)
def _detect_delivery_intent(self, user_request: str) -> Dict[str, Any]:
    """
    Detect delivery intent using config-driven verbs.

    Returns:
        {
            "has_intent": bool,
            "detected_verbs": List[str],
            "required_tool": str
        }
    """
    delivery_config = self.config.get("delivery", {})
    verbs = delivery_config.get("intent_verbs", [])
    required_tool = delivery_config.get("required_tool", "compose_email")

    user_lower = user_request.lower()
    detected = [v for v in verbs if v in user_lower]

    return {
        "has_intent": len(detected) > 0,
        "detected_verbs": detected,
        "required_tool": required_tool
    }
```

**2. Update All Callsites:**
```python
# Planning (line 213)
delivery_check = self._detect_delivery_intent(full_user_request)
needs_email_delivery = delivery_check["has_intent"]

# Validation Guard (line 418)
delivery_check = self._detect_delivery_intent(state["user_request"])
if delivery_check["has_intent"] and not has_compose_email_step:
    # Reject plan

# Finalization (line 673)
delivery_check = self._detect_delivery_intent(state.get("user_request"))
# Use for message construction

# Validate & Fix Plan (line 972)
delivery_check = self._detect_delivery_intent(user_request)
# Use in validation
```

---

## 📋 Phase 3: Auto-Corrections Removal (PENDING)

**Target:** `_validate_and_fix_plan()` in agent.py (lines 784-995)

### Current Auto-Corrections to Remove

1. **VALIDATION 0** (line 832-845): Clean search_documents queries
   - ❌ Remove regex-based query cleaning
   - ✅ Add prompt examples showing correct query format

2. **VALIDATION 1** (line 848-877): Fix invalid placeholders
   - ❌ Remove auto-replacement of {file1.name} → $step1.duplicates
   - ✅ Add negative examples in prompts

3. **VALIDATION 2** (line 880-901): Add keynote attachments
   - ❌ Remove auto-injection of attachments parameter
   - ✅ Enhance keynote workflow examples in prompts

4. **VALIDATION 2b** (line 904-914): Force send=true
   - ❌ Remove auto-correction of send flag
   - ✅ Already covered by delivery_intent.md examples

5. **VALIDATION 2c** (line 916-941): Add email body
   - ❌ Remove auto-injection of body from previous steps
   - ✅ Enhance compose_email examples in prompts

### Strategy

**Instead of:**
```python
if invalid_pattern:
    params["details"] = f"$step{dup_step_id}.duplicates"
    corrections_made.append(...)
```

**Do:**
```python
if invalid_pattern:
    raise PlanValidationError(
        f"Step {step_id} uses invalid placeholder pattern {invalid_pattern}. "
        f"Use $stepN.field syntax instead. "
        f"Example: '$step{dup_step_id}.duplicates'"
    )
```

**Result:** Planner learns from rejection → improves prompts → succeeds on retry

---

## 📋 Phase 4: Slash Command Alignment (PENDING)

### Current Problems

**1. Agent-Specific Code Paths:**
- `if agent_name == "bluesky"` (line 829)
- `if agent_name == "google"` (line 1540)
- Direct task parsing instead of using planner

**2. LLM-Based Routing:**
- `_execute_agent_task()` duplicates planner's job
- Hardcoded tool selection logic

### Refactor Plan

**A. Complex Tasks → Route to Planner**
```python
def _is_complex_task(self, task: str) -> bool:
    """Determine if task needs full planning."""
    # Multi-step indicators
    keywords = ["and", "then", "after", "email", "send"]
    return any(kw in task.lower() for kw in keywords)

def handle(self, message: str, session_id: Optional[str] = None):
    parsed = self.parser.parse(message)
    if not parsed or not parsed["is_command"]:
        return False, None

    command = parsed["command"]
    task = parsed["task"]

    # Check complexity
    if self._is_complex_task(task):
        # Use full planner for multi-step workflows
        return True, self.agent.run(f"{task}", session_id=session_id)

    # Otherwise direct single-tool execution...
```

**B. Single-Tool → Use reply_to_user**
```python
# Agent executes tool
result = agent.execute(tool_name, params)

# Format via reply_to_user (not code)
reply_payload = self.registry.execute_tool("reply_to_user", {
    "message": result.get("summary", result.get("message")),
    "details": result.get("details"),
    "artifacts": result.get("file_paths", []),
    "status": "success" if not result.get("error") else "error"
}, session_id=session_id)

return True, {"type": "result", "result": reply_payload}
```

**C. Remove Special Cases**
- ❌ `_parse_bluesky_task()`
- ❌ `_summarize_google_results()`
- ❌ `_get_llm_response_for_blocked_search()`

---

## 📋 Phase 5: Temperature Centralization (PENDING)

### Goal
Move all temperature settings to config, create ModelManager to handle constraints.

**Current State:** 20+ files with hardcoded temperatures

**Target State:**
```yaml
# config.yaml
models:
  constraints:
    - pattern: "^o[134]-"
      temperature: 1.0
      reason: "o-series only supports temperature=1"

  agent_defaults:
    vision: {temperature: 0.0}
    planner: {temperature: 0.2}
    verifier: {temperature: 0.0}
    writing: {temperature: 0.3}
```

**Code:**
```python
class ModelManager:
    def __init__(self, config: Dict):
        self.config = config
        self.constraints = config.get("models", {}).get("constraints", [])
        self.defaults = config.get("models", {}).get("agent_defaults", {})

    def get_temperature(self, model_name: str, agent_type: str) -> float:
        # 1. Check model constraints first
        for constraint in self.constraints:
            if re.match(constraint["pattern"], model_name):
                return constraint["temperature"]

        # 2. Check agent-specific default
        if agent_type in self.defaults:
            return self.defaults[agent_type].get("temperature", 0.7)

        # 3. Global default
        return self.config.get("openai", {}).get("temperature", 0.7)
```

---

## 📊 Progress Summary

| Phase | Status | Files Changed | Lines Removed | Lines Added |
|-------|--------|---------------|---------------|-------------|
| 1. Inventory | ✅ Complete | 1 | 0 | 400 |
| 2A. Delivery Config/Prompts | ✅ Complete | 3 | 15 | 200 |
| 2B. Delivery Consolidation | 🔄 Next | 1 | ~40 | ~20 |
| 3. Auto-Corrections | 📋 Planned | 1 | ~200 | ~50 |
| 4. Slash Commands | 📋 Planned | 1 | ~150 | ~80 |
| 5. Temperature Manager | 📋 Planned | 20+ | ~30 | ~60 |

---

## 🎯 Next Actions

1. **Consolidate Delivery Detection** (30 min)
   - Create `_detect_delivery_intent()` helper
   - Replace 4 callsites with helper
   - Test: "search email X to me" should work identically

2. **Remove First Auto-Correction** (1 hour)
   - Pick VALIDATION 2b (force send=true) - already covered by prompts
   - Convert to rejection with helpful error
   - Test: Plan without send=true should be rejected

3. **Enhance Prompts** (2 hours)
   - Add negative examples for each validation
   - Test: LLM should generate correct plans without auto-corrections

4. **Iterate** (ongoing)
   - Remove one auto-correction at a time
   - Monitor rejection logs
   - Improve prompts based on common failures

---

## 🎓 Key Principles

1. **Code Validates, Prompts Teach**
   - Code checks correctness → rejects bad plans
   - Prompts show examples → LLM learns patterns

2. **Single Source of Truth**
   - Config for runtime behaviors (verbs, tools)
   - Prompts for planning patterns (workflows, examples)
   - Code for execution and validation only

3. **Graceful Degradation**
   - Keep fallbacks for backwards compatibility
   - Log when fallbacks are used
   - Remove fallbacks once confident

4. **Measurable Progress**
   - Track rejections → improve prompts
   - Fewer rejections over time = better prompts
   - Zero auto-corrections = prompt-driven system
