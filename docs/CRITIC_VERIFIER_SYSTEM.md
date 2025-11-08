# Critic/Verifier System - Comprehensive Quality Assurance

## Overview

The system now has **comprehensive critic/verification** for ALL crucial steps across all agents, ensuring output quality and automatic error recovery.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         EXECUTION FLOW                           │
└─────────────────────────────────────────────────────────────────┘

Step Execution → Check Success/Failure
     │                    │
     │                    ↓
     │            ┌──────────────────┐
     │            │   STEP FAILED?   │
     │            └────────┬─────────┘
     │                     │
     │                     ↓ YES
     │            ┌──────────────────────────┐
     │            │  CRITIC AGENT:           │
     │            │  reflect_on_failure()    │
     │            │  - Root cause analysis   │
     │            │  - Corrective actions    │
     │            │  - Retry recommendation  │
     │            └────────┬─────────────────┘
     │                     │
     │                     ↓
     │            ┌──────────────────────────┐
     │            │  Include reflection in   │
     │            │  replan request          │
     │            └──────────────────────────┘
     │
     ↓ SUCCESS
┌──────────────────────────┐
│  STEP SUCCEEDED?         │
│  Is it critical?         │
└────────┬─────────────────┘
         │
         ↓ YES (critical step)
┌──────────────────────────────┐
│  OUTPUT VERIFIER:            │
│  verify_step_output()        │
│  - Check against user intent │
│  - Verify constraints        │
│  - Confidence score          │
└────────┬─────────────────────┘
         │
         ↓
   ┌─────────────┐
   │ Valid?      │
   └─────┬───────┘
         │
         ↓ NO (confidence > 0.8)
┌──────────────────────────┐
│  Trigger replan with     │
│  verification issues     │
└──────────────────────────┘
```

## Critical Steps Verified

### FILE AGENT (3/4 tools)
```python
"extract_section"            # ✅ Verify correct section extracted
"take_screenshot"            # ✅ Verify correct pages captured
"organize_files"             # ✅ Verify correct files moved
# search_documents - not verified (search results inherently correct)
```

### BROWSER AGENT (3/5 tools)
```python
"google_search"              # ✅ Verify search results relevant
"extract_page_content"       # ✅ Verify content extracted correctly
"take_web_screenshot"        # ✅ Verify screenshot captured
# navigate_to_url - not verified (simple navigation)
# close_browser - not verified (cleanup only)
```

### PRESENTATION AGENT (3/3 tools)
```python
"create_keynote"             # ✅ Verify presentation created
"create_keynote_with_images" # ✅ Verify images included
"create_pages_doc"           # ✅ Verify document created
```

### EMAIL AGENT (1/1 tool)
```python
"compose_email"              # ✅ Verify email sent/drafted
```

### CRITIC AGENT
Critic tools are not verified (they are the verifiers!)

**Total: 10 out of 13 actionable tools verified (77% coverage)**

## Two-Stage Verification

### Stage 1: Failure Reflection (CRITIC AGENT)
**When**: Step fails with error
**Tool**: `reflect_on_failure()`
**Purpose**: Root cause analysis and corrective suggestions

```python
# Automatic on ALL step failures
if step_result.get("error"):
    reflection = critic_agent.reflect_on_failure({
        "step_description": "Tool: search_documents with inputs: {...}",
        "error_message": "File not found",
        "context": {
            "previous_steps": [...],
            "dependencies": [...]
        }
    })

    # Result includes:
    {
        "root_cause": "Document not indexed yet",
        "corrective_actions": [
            "Run indexer to update document index",
            "Check if file path is correct",
            "Try alternative search terms"
        ],
        "retry_recommended": True,
        "alternative_approach": "Use organize_files to find document by category"
    }
```

### Stage 2: Output Verification (OUTPUT VERIFIER)
**When**: Step succeeds but output needs validation
**Tool**: `verify_step_output()`
**Purpose**: Semantic validation against user intent

```python
# Automatic on critical steps
if step_succeeded and is_critical_step:
    verification = verifier.verify_step_output({
        "user_request": "Extract the last page from the report",
        "step": {
            "action": "extract_section",
            "inputs": {"section": "last page"}
        },
        "step_result": {
            "page_numbers": [6],  # Single page
            "extracted_text": "..."
        },
        "context": {...}
    })

    # Result includes:
    {
        "valid": True,
        "confidence": 0.95,
        "issues": [],
        "suggestions": [],
        "reasoning": "Output matches user intent: extracted exactly 1 page (the last)"
    }
```

## Verification Logic

### What Gets Verified

1. **Content Extraction Steps**
   - `extract_section`: Verify correct section/pages extracted
   - `extract_page_content`: Verify web content extracted

2. **File Operations**
   - `organize_files`: Verify correct files moved/copied
   - `take_screenshot`: Verify correct pages captured
   - `take_web_screenshot`: Verify screenshot captured

3. **Creation Steps**
   - `create_keynote`: Verify presentation exists
   - `create_keynote_with_images`: Verify images included
   - `create_pages_doc`: Verify document created

4. **Communication**
   - `compose_email`: Verify email sent/drafted
   - `google_search`: Verify search results relevant

### What Doesn't Get Verified

- **Simple operations**: navigate_to_url (just navigation)
- **Cleanup operations**: close_browser (no output to verify)
- **Discovery operations**: search_documents (search results are inherently correct)

## Verification Triggers

### Automatic Triggers

1. **On Step Failure** → Reflection
   ```python
   if step_result.get("error"):
       reflection = self._reflect_on_failure(step, step_result, state)
   ```

2. **On Critical Step Success** → Verification
   ```python
   if self.verifier and self._should_verify_step(step):
       verification = self.verifier.verify_step_output(...)
   ```

### Manual Triggers (via Critic Agent)

```python
# Manual verification through Critic Agent
from src.agent import AgentRegistry

registry = AgentRegistry(config)

# Verify any output manually
verification = registry.execute_tool("verify_output", {
    "step_description": "Created presentation",
    "user_intent": "Create presentation about Python",
    "actual_output": {"keynote_path": "/path/to/file.key"},
    "constraints": {"slide_count": {"min": 5}}
})
```

## Confidence Thresholds

### High Confidence Issues (> 0.8)
**Action**: Trigger immediate replan
```python
if not verification["valid"] and verification["confidence"] > 0.8:
    logger.warning("High confidence verification failure")
    return NEEDS_REPLAN
```

### Medium Confidence Issues (0.5 - 0.8)
**Action**: Log warning, continue execution
```python
if not verification["valid"] and 0.5 < verification["confidence"] <= 0.8:
    logger.warning("Medium confidence issue detected")
    # Continue but note the issue
```

### Low Confidence Issues (< 0.5)
**Action**: Ignore (likely false positive)

## Reflection-Driven Replanning

When a step fails, the reflection is included in the replan request:

```python
replan_reason = f"Step extract_section failed: File not found"
replan_reason += f"\nRoot cause: {reflection['root_cause']}"
replan_reason += f"\nSuggested fixes: {', '.join(reflection['corrective_actions'])}"

# Planner receives:
"""
REPLAN REASON:
Step extract_section failed: File not found
Root cause: Document not indexed yet
Suggested fixes: Run indexer to update document index, Check if file path is correct, Try alternative search terms
"""
```

The planner can use this information to create a better plan.

## Example Workflows

### Workflow 1: Successful Execution with Verification

```
User: "Extract the last page from report.pdf"

1. Planner creates plan:
   Step 1: search_documents(query="report.pdf")
   Step 2: extract_section(doc_path=$step1.doc_path, section="last page")

2. Executor runs Step 1:
   ✅ SUCCESS: Found report.pdf
   ⏭️  No verification (search_documents not critical)

3. Executor runs Step 2:
   ✅ SUCCESS: Extracted page 6
   🔍 VERIFICATION: verify_step_output()
      → valid=True, confidence=0.95
      → "Extracted exactly 1 page (the last)"
   ✅ VERIFIED

4. Result: SUCCESS
```

### Workflow 2: Failure with Reflection

```
User: "Extract the chorus from song.pdf"

1. Planner creates plan:
   Step 1: search_documents(query="song.pdf")
   Step 2: extract_section(doc_path=$step1.doc_path, section="chorus")

2. Executor runs Step 1:
   ❌ FAILURE: File not found

3. Critic Agent reflects:
   🤔 REFLECTION:
      Root cause: "Document not indexed yet"
      Corrective actions: ["Run indexer", "Check file path", "Try alternative search"]
      Retry recommended: True

4. Replan with reflection feedback:
   → Planner sees root cause and suggestions
   → Creates new plan with indexer step first

5. Second attempt:
   Step 1: [Run indexer]
   Step 2: search_documents(query="song.pdf")
   Step 3: extract_section(...)
   ✅ SUCCESS
```

### Workflow 3: Verification Failure

```
User: "Extract the first 3 pages from document.pdf"

1. Executor runs:
   extract_section(doc_path="document.pdf", section="first 3 pages")
   ✅ SUCCESS: Extracted pages [1, 2, 3, 4, 5]

2. Verification:
   🔍 VERIFICATION: verify_step_output()
      user_intent: "first 3 pages"
      actual_output: page_numbers=[1,2,3,4,5]
      → valid=False, confidence=0.9
      → "Expected 3 pages, got 5 pages"

3. High confidence failure (0.9 > 0.8):
   ⚠️  TRIGGER REPLAN
   Reason: "Output doesn't match user intent: Expected 3 pages, got 5"

4. Planner adjusts:
   → Add explicit constraint: max_pages=3
   → Retry with corrected parameters
```

## Integration with Main Orchestrator

```python
from src.orchestrator.main_orchestrator import MainOrchestrator

orchestrator = MainOrchestrator(config)

result = orchestrator.run(goal="Extract last page and email it")

# Behind the scenes:
# 1. Plan created
# 2. Steps executed
# 3. Critical steps VERIFIED automatically
# 4. Failures REFLECTED on automatically
# 5. Replanning triggered if needed
# 6. Final output validated
```

## Configuration

Enable/disable verification in executor:

```python
from src.orchestrator.executor import PlanExecutor

# With verification (default)
executor = PlanExecutor(config, enable_verification=True)

# Without verification (faster but less safe)
executor = PlanExecutor(config, enable_verification=False)
```

## Monitoring

### Logs Show Verification

```
[EXECUTOR] Executing step: extract_section
[FILE AGENT] Tool: extract_section(doc_path='...', section='last page')
[EXECUTOR] Step completed successfully
[EXECUTOR] Verifying step output...
[VERIFIER] Checking if output matches user intent...
[VERIFIER] ✅ Valid: True, Confidence: 0.95
[EXECUTOR] Step verified successfully
```

### Logs Show Reflection

```
[EXECUTOR] Step failed: File not found
[EXECUTOR] Reflecting on failure...
[CRITIC] Analyzing failure...
[CRITIC] Root cause: Document not indexed yet
[CRITIC] Corrective actions: Run indexer to update document index
[EXECUTOR] Triggering replan with reflection feedback
```

## Testing

```python
# Test verification
def test_verification():
    verifier = OutputVerifier(config)

    verification = verifier.verify_step_output(
        user_request="Extract last page",
        step={"action": "extract_section", "inputs": {"section": "last page"}},
        step_result={"page_numbers": [6]},
        context={}
    )

    assert verification["valid"] == True
    assert verification["confidence"] > 0.8

# Test reflection
def test_reflection():
    critic = CriticAgent(config)

    reflection = critic.execute("reflect_on_failure", {
        "step_description": "search_documents",
        "error_message": "File not found",
        "context": {}
    })

    assert "root_cause" in reflection
    assert "corrective_actions" in reflection
```

## Summary

✅ **77% Tool Coverage** - 10 out of 13 actionable tools verified
✅ **Automatic Verification** - Critical steps verified without manual intervention
✅ **Failure Reflection** - ALL failures analyzed by Critic Agent
✅ **Root Cause Analysis** - Intelligent error understanding
✅ **Corrective Suggestions** - Actionable fixes for failures
✅ **Confidence-Based** - Only high-confidence issues trigger replanning
✅ **Seamless Integration** - Works automatically with orchestrator

The system now has comprehensive quality assurance covering all crucial operations across all 5 agents!
