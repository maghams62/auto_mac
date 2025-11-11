# LangGraph Agent Architecture

## Overview

The Mac Automation Assistant now uses **LangGraph** for intelligent task decomposition and long-horizon planning. The agent analyzes complex user requests, breaks them down into sequential steps, manages dependencies, and executes them using available tools.

## Architecture Decision

After evaluating MCP servers vs custom AppleScript, we decided to:
- ✅ **Keep custom AppleScript implementations** (Mail, Keynote, Pages)
- ✅ **Add LangGraph for task decomposition** (the real value-add)
- ✅ **Maintain existing FAISS search** (already optimized)

**Rationale:** MCP servers add complexity without significant benefit for this use case. LangGraph's task decomposition provides the intelligence we need.

---

## System Components

### 1. LangGraph Agent ([src/agent/agent.py](src/agent/agent.py))

**Core Responsibilities:**
- Task decomposition (breaking complex requests into steps)
- Dependency management (ensuring correct execution order)
- State management (passing context between steps)
- Error handling and recovery

**Graph Structure:**
```
┌─────────┐
│  Start  │
└────┬────┘
     │
     ▼
┌─────────┐
│  Plan   │  ← Parse intent, decompose into steps
└────┬────┘
     │
     ▼
┌──────────────┐
│ Execute Step │  ← Run tool, store result
└──────┬───────┘
       │
       ▼
   [More steps?]
       │
       ├─ Yes → Loop back to Execute Step
       │
       └─ No ──▼
            ┌──────────┐
            │ Finalize │  ← Summarize results
            └─────┬────┘
                  │
                  ▼
               [END]
```

**State Management:**
```python
class AgentState(TypedDict):
    user_request: str                  # Original request
    goal: str                          # High-level objective
    steps: List[Dict[str, Any]]        # Execution plan
    current_step: int                  # Progress tracker
    step_results: Dict[int, Any]       # Outputs from each step
    messages: List[Any]                # LLM conversation history
    final_result: Optional[Dict]       # Summary of execution
    status: str                        # "planning" | "executing" | "completed"
```

### 2. Tool Registry ([src/agent/tools.py](src/agent/tools.py))

**Available Tools:**

#### `search_documents(query: str)`
- Semantic search using FAISS + OpenAI embeddings
- Returns: doc_path, doc_title, relevance_score, metadata

#### `extract_section(doc_path: str, section: str)`
- Extract content from PDFs/DOCX
- Supports: "all", "page N", "pages N-M", "summary", "introduction", etc.
- Returns: extracted_text, page_numbers, word_count

#### `take_screenshot(doc_path: str, pages: List[int])`
- Capture page images from PDFs
- Returns: screenshot_paths, pages_captured

#### `compose_email(subject, body, recipient, attachments, send)`
- Create/send emails via Mail.app (AppleScript)
- Returns: status ("sent" | "draft")

#### `create_keynote(title, content, output_path)`
- Generate Keynote presentations (AppleScript)
- Returns: keynote_path, slide_count

#### `create_pages_doc(title, content, output_path)`
- Generate Pages documents (AppleScript)
- Returns: pages_path

**Tool Wrapping Pattern:**
```python
@tool
def tool_name(param: type) -> Dict[str, Any]:
    """Tool description for LLM."""
    try:
        # Call existing component
        result = existing_component.method(param)
        return {"success": True, "data": result}
    except Exception as e:
        return {"error": True, "message": str(e)}
```

### 3. Prompt Templates ([prompts/](prompts/))

**Modular Prompt Structure:**

#### [system.md](prompts/system.md)
- Agent persona and capabilities
- Available tools overview
- Response format specification
- Key operational principles

#### [task_decomposition.md](prompts/task_decomposition.md)
- Detailed decomposition instructions
- Complexity categorization (simple/medium/complex)
- Output format (JSON plan)
- Guidelines for each complexity level

#### [few_shot_examples.md](prompts/few_shot_examples.md)
- 5 detailed examples with increasing complexity
- Pattern recognition (linear, sequential, multi-stage, parallel)
- Common mistakes to avoid
- Context variable syntax (`$stepN.field`)

#### [tool_definitions.md](prompts/tool_definitions.md)
- Complete tool specifications
- Parameter schemas
- Return value formats
- Tool chaining patterns

---

## Execution Flow

### Example: Complex Request

**User Request:**
```
"Find the Tesla Autopilot doc, send me a screenshot of page 3,
and create a Keynote presentation from the summary section"
```

### 1. Planning Phase

**LLM analyzes request using:**
- `system.md` - Understand capabilities
- `task_decomposition.md` - Decomposition rules
- `few_shot_examples.md` - Similar patterns

**Generated Plan:**
```json
{
  "goal": "Find document, capture screenshot, create presentation",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {"query": "Tesla Autopilot"},
      "dependencies": [],
      "reasoning": "Locate the document first"
    },
    {
      "id": 2,
      "action": "take_screenshot",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "pages": [3]
      },
      "dependencies": [1],
      "reasoning": "Capture page 3 for user"
    },
    {
      "id": 3,
      "action": "compose_email",
      "parameters": {
        "subject": "Tesla Autopilot - Page 3",
        "body": "Screenshot of page 3",
        "attachments": ["$step2.screenshot_paths"],
        "send": false
      },
      "dependencies": [2],
      "reasoning": "Email screenshot to user"
    },
    {
      "id": 4,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "section": "summary"
      },
      "dependencies": [1],
      "reasoning": "Extract summary for presentation"
    },
    {
      "id": 5,
      "action": "create_keynote",
      "parameters": {
        "title": "Tesla Autopilot Summary",
        "content": "$step4.extracted_text"
      },
      "dependencies": [4],
      "reasoning": "Create presentation from summary"
    },
    {
      "id": 6,
      "action": "reply_to_user",
      "parameters": {
        "message": "Presentation created and email drafted.",
        "details": "- Draft email ready in Mail.app\n- Keynote saved with summary content",
        "artifacts": ["$step2.screenshot_paths", "$step5.keynote_path"],
        "status": "success"
      },
      "dependencies": [2, 5],
      "reasoning": "Deliver a polished update with links to generated assets"
    }
  ]
}
```

### 2. Execution Phase

**Step-by-step execution with dependency resolution:**

```
Step 1: search_documents("Tesla Autopilot")
  ✓ Result: {doc_path: "/Documents/tesla.pdf", doc_title: "Tesla Autopilot"}

Step 2: take_screenshot("/Documents/tesla.pdf", [3])
  ✓ Depends on: Step 1 ✓
  ✓ Resolved: $step1.doc_path → "/Documents/tesla.pdf"
  ✓ Result: {screenshot_paths: ["/tmp/page3.png"]}

Step 3: compose_email(...)
  ✓ Depends on: Step 2 ✓
  ✓ Resolved: $step2.screenshot_paths → ["/tmp/page3.png"]
  ✓ Result: {status: "draft"}

Step 4: extract_section("/Documents/tesla.pdf", "summary")
  ✓ Depends on: Step 1 ✓
  ✓ Resolved: $step1.doc_path → "/Documents/tesla.pdf"
  ✓ Result: {extracted_text: "Summary content..."}

Step 5: create_keynote("Tesla Autopilot Summary", ...)
  ✓ Depends on: Step 4 ✓
  ✓ Resolved: $step4.extracted_text → "Summary content..."
  ✓ Result: {keynote_path: "/Documents/presentation.key"}

Step 6: reply_to_user(...)
  ✓ Depends on: Steps 2 & 5 ✓
  ✓ Resolved: $step2.screenshot_paths → ["/tmp/page3.png"]
              $step5.keynote_path → "/Documents/presentation.key"
  ✓ Result: {
      type: "reply",
      message: "Presentation created and email drafted.",
      artifacts: ["/tmp/page3.png", "/Documents/presentation.key"]
    }
```

### 3. Finalization

**Summary:**
```json
{
  "goal": "Find document, capture screenshot, create presentation",
  "steps_executed": 6,
  "results": {
    "1": {"doc_path": "/Documents/tesla.pdf"},
    "2": {"screenshot_paths": ["/tmp/page3.png"]},
    "3": {"status": "draft"},
    "4": {"extracted_text": "..."},
    "5": {"keynote_path": "/Documents/presentation.key"},
    "6": {
      "type": "reply",
      "message": "Presentation created and email drafted.",
      "artifacts": ["/tmp/page3.png", "/Documents/presentation.key"],
      "status": "success"
    }
  },
  "status": "success",
  "message": "Presentation created and email drafted.",
  "artifacts": ["/tmp/page3.png", "/Documents/presentation.key"]
}
```

---

## Context Variable Resolution

**Syntax:** `$stepN.field`

**Example:**
```json
{
  "action": "compose_email",
  "parameters": {
    "attachments": ["$step2.screenshot_paths", "$step1.doc_path"]
  }
}
```

**Resolution Logic:**
```python
def _resolve_parameters(self, params, step_results):
    resolved = {}
    for key, value in params.items():
        if isinstance(value, str) and value.startswith("$step"):
            # Parse: $step2.screenshot_paths
            step_ref, field = value[1:].split(".")
            step_id = int(step_ref.replace("step", ""))
            resolved[key] = step_results[step_id].get(field, value)
        else:
            resolved[key] = value
    return resolved
```

---

## Dependency Management

**Rules:**
1. Steps with `dependencies: []` can run first
2. Steps with `dependencies: [1, 2]` wait for steps 1 and 2
3. Steps with same dependencies can theoretically run in parallel (not yet implemented)

**Execution Order:**
```
Step 1 (no deps) → Execute immediately
  ↓
Step 2 (deps: [1]) → Wait for Step 1
  ↓
Step 3 (deps: [2]) → Wait for Step 2
  ↓
Step 4 (deps: [1]) → Can start after Step 1 (parallel with Steps 2-3)
  ↓
Step 5 (deps: [4]) → Wait for Step 4
```

---

## Error Handling

**Tool Error Format:**
```json
{
  "error": true,
  "error_type": "NotFoundError | PermissionError | ValidationError",
  "error_message": "Detailed description",
  "retry_possible": true
}
```

**Agent Behavior on Error:**
1. Log error details
2. Store error in step results
3. Continue to next step (don't crash entire workflow)
4. Mark final status as "partial_success" if some steps failed

---

## Integration Points

### Terminal UI (main.py)

```python
from src.agent import AutomationAgent

agent = AutomationAgent(config)
result = agent.run(user_input)

# Display results
if result.get("status") == "success":
    print(f"✅ Goal: {result['goal']}")
    print(f"Steps: {result['steps_executed']}")
```

### Web UI (app.py)

```python
from src.agent import AutomationAgent

agent = AutomationAgent(config)
result = agent.run(message)

# Format for Gradio
response = f"**Goal:** {result['goal']}\n"
response += f"**Steps:** {result['steps_executed']}\n"
```

---

## File Structure

```
mac_auto/
├── src/
│   ├── agent/
│   │   ├── __init__.py           # Module exports
│   │   ├── agent.py              # LangGraph agent (320 lines)
│   │   └── tools.py              # Tool definitions (350 lines)
│   │
│   ├── automation/               # AppleScript integrations
│   │   ├── mail_composer.py
│   │   ├── keynote_composer.py
│   │   └── pages_composer.py
│   │
│   ├── documents/                # Search & parsing
│   │   ├── indexer.py
│   │   ├── search.py
│   │   └── parser.py
│   │
│   └── workflow.py               # Legacy orchestrator (kept for /index)
│
├── prompts/                      # Prompt templates
│   ├── README.md
│   ├── system.md
│   ├── task_decomposition.md
│   ├── few_shot_examples.md
│   └── tool_definitions.md
│
├── main.py                       # Terminal UI (updated)
├── app.py                        # Web UI (updated)
└── requirements.txt              # Dependencies (includes langgraph)
```

---

## Key Benefits

### 1. **Intelligent Task Decomposition**
- LLM understands complex multi-step requests
- Automatically determines execution order
- Handles dependencies correctly

### 2. **Context Passing**
- Outputs from earlier steps feed into later steps
- No manual state management needed
- `$stepN.field` syntax is intuitive

### 3. **Maintainable Prompts**
- Prompts are in markdown files (easy to edit)
- Few-shot examples clearly documented
- Tool definitions separate from code

### 4. **Extensible Architecture**
- Add new tools by creating `@tool` functions
- Update prompts to include new capabilities
- No changes to graph structure needed

### 5. **Observability**
- Step-by-step logging
- Clear success/error reporting
- Execution history in state

---

## Usage Examples

### Simple Request
```
User: "Send me the Tesla document"

Plan:
  Step 1: search_documents("Tesla")
  Step 2: compose_email(attachments=[$step1.doc_path])

Result: Email draft with document attached
```

### Medium Request
```
User: "Create a Keynote from the Q3 earnings summary"

Plan:
  Step 1: search_documents("Q3 earnings")
  Step 2: extract_section(section="summary")
  Step 3: create_keynote(content=$step2.extracted_text)

Result: Keynote presentation created
```

### Complex Request
```
User: "Find the marketing doc, screenshot pages with 'ROI',
       and make a slide deck from those sections"

Plan:
  Step 1: search_documents("marketing doc")
  Step 2: extract_section(section="pages containing 'ROI'")
  Step 3: take_screenshot(pages=$step2.page_numbers)
  Step 4: compose_email(attachments=$step3.screenshot_paths)
  Step 5: extract_section(section="text from pages...")
  Step 6: create_keynote(content=$step5.extracted_text)

Result: Screenshots emailed + Keynote created
```

---

## Future Enhancements

### Potential Improvements
- [ ] Parallel step execution (steps with same dependencies)
- [ ] Retry logic with exponential backoff
- [ ] Persistent memory across sessions
- [ ] User confirmation before sending emails
- [ ] Cost tracking (OpenAI API calls)
- [ ] Streaming progress updates

### Advanced Features
- [ ] Multi-document workflows
- [ ] Conditional branching (if/else in plans)
- [ ] Loop support (for batch operations)
- [ ] Human-in-the-loop approval steps
- [ ] Integration with Calendar/Reminders
- [ ] Voice input support

---

## Testing

### Manual Testing

```bash
# Terminal UI
python main.py

# Web UI
python app.py
# Open http://localhost:7860
```

### Test Cases

1. **Simple Search + Email**
   ```
   "Send me the Tesla Autopilot document"
   Expected: Email draft with PDF attached
   ```

2. **Screenshot + Email**
   ```
   "Send me a screenshot of page 5 from the Q3 report"
   Expected: Email with screenshot attached
   ```

3. **Extract + Keynote**
   ```
   "Create a presentation from the AI research paper summary"
   Expected: Keynote file created
   ```

4. **Complex Multi-Step**
   ```
   "Find the Tesla doc, screenshot page 3, and make a slide deck from the introduction"
   Expected: Email with screenshot + Keynote created
   ```

### Check Logs

```bash
tail -f data/app.log | grep -E "(Planning|Executing|Step)"
```

---

## Troubleshooting

### Issue: "Tool not found"
**Cause:** Tool name in plan doesn't match registered tool
**Fix:** Check tool names in `src/agent/tools.py` match prompt examples

### Issue: "Context variable not resolved"
**Cause:** `$stepN.field` references non-existent step or field
**Fix:** Verify step IDs are correct and result contains expected fields

### Issue: "Plan parsing failed"
**Cause:** LLM returned invalid JSON
**Fix:** Check prompts for clarity, ensure examples are valid JSON

### Issue: "Step execution error"
**Cause:** Tool invocation failed
**Fix:** Check tool implementation, verify parameters are correct

---

## Conclusion

The LangGraph agent architecture provides:
- ✅ Intelligent task decomposition
- ✅ Dependency management
- ✅ State management
- ✅ Error handling
- ✅ Maintainable prompts
- ✅ Extensible design

**Result:** A powerful automation assistant that understands complex requests and executes them reliably through multi-step workflows.
