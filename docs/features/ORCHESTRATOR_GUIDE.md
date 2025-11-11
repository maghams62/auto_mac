# LangGraph Orchestrator - Complete Guide

## Overview

The LangGraph Orchestrator is a sophisticated multi-agent system that implements a **Plan → Execute → Evaluate → Replan** loop for automating complex macOS workflows. It combines:

- **LangGraph** for stateful workflow orchestration and control flow
- **LlamaIndex** for RAG-powered atomic tasks and complex reasoning
- **OpenAI GPT-4o** for planning, evaluation, and synthesis
- **Existing tools** (document search, Mail.app, Keynote, Pages, etc.)

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────────┐
│                     LangGraph Orchestrator                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│  │ Planner  │───▶│Evaluator │───▶│ Executor │───▶│Synthesis │ │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘ │
│       │               │                 │                       │
│       │               │                 │                       │
│       └───────────────┴─────────────────┘                       │
│                    Replan Loop                                  │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                      State Management                            │
│  • Plan (DAG of steps)    • Artifacts (results)                 │
│  • Budget tracking        • Notes (critiques)                   │
│  • Metadata              • Persistence                          │
├─────────────────────────────────────────────────────────────────┤
│                      Tool Layer                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐               │
│  │  Document  │  │    Mail    │  │  Keynote   │               │
│  │   Search   │  │  Composer  │  │  Creator   │  ...           │
│  └────────────┘  └────────────┘  └────────────┘               │
│                                                                  │
│  ┌────────────────────────────────────────┐                    │
│  │      LlamaIndex Worker (RAG)           │                    │
│  │  - Complex reasoning                   │                    │
│  │  - Document analysis                   │                    │
│  │  - Iterative micro-planning            │                    │
│  └────────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

### Control Flow

```
UserInput
    │
    ▼
┌─────────┐
│ Planner │ ◀──────────┐
└────┬────┘            │
     │                 │
     ▼                 │
┌──────────┐           │
│Evaluator │           │
│(Validate)│           │
└────┬────┘            │
     │                 │
     ├──[invalid]──────┘ (Replan)
     │
     ▼ [valid]
┌──────────┐
│ Executor │ ◀────┐
│(Execute  │      │
│  Steps)  │      │
└────┬────┘       │
     │            │
     ▼            │
┌──────────┐      │
│Evaluator │      │
│  (Check  │      │
│ Results) │      │
└────┬────┘       │
     │            │
     ├──[retry]───┘
     │
     ├──[replan]──────┐
     │                │
     ▼ [done]         │
┌───────────┐         │
│ Synthesis │         │
└─────┬─────┘         │
      │               │
      ▼               │
     END              │
                      │
     ┌────────────────┘
     │
     ▼
   Planner (Repair)
```

## Shared State

The orchestrator maintains a single, comprehensive state throughout execution:

```python
{
    # Goal and context
    "goal": "High-level objective",
    "context": {"user_constraints": "...", "preferences": "..."},

    # Tool catalog
    "tool_specs": [
        {
            "name": "search_documents",
            "kind": "tool",
            "io": {"in": [...], "out": [...]},
            "strengths": [...],
            "limits": [...]
        }
    ],

    # Plan (DAG of steps)
    "plan": [
        {
            "id": "step1",
            "title": "Search for document",
            "type": "tool",
            "tool": "search_documents",
            "inputs": {"query": "fingerstyle guitar"},
            "deps": [],
            "success_criteria": ["doc_path exists", "relevance > 0.7"],
            "max_retries": 3,
            "timeout_s": 60,
            "status": "completed"
        }
    ],

    # Execution state
    "cursor": 0,  # Current step index
    "artifacts": {
        "step1": {"doc_path": "/path/to/doc.pdf", ...}
    },
    "completed_steps": ["step1"],
    "failed_steps": [],

    # Evaluation and replanning
    "notes": [
        {"severity": "warning", "message": "..."}
    ],
    "need_replan": false,
    "validation_passed": true,

    # Budget tracking
    "budget": {
        "tokens": 50000,
        "tokens_used": 1234,
        "time_s": 300,
        "time_used": 45.6,
        "steps": 20,
        "steps_used": 5
    },

    # Metadata
    "metadata": {
        "run_id": "uuid",
        "created_at": "2025-...",
        "version": "1.0"
    },

    # Output
    "status": "executing",
    "final_result": null
}
```

## Nodes

### 1. Planner

**Responsibility:** Create or repair execution plans.

**Input:**
- Goal
- Context
- Tool specifications
- Notes (critiques from evaluator)
- Existing plan (if replanning)

**Output:**
- DAG of steps with:
  - Unique IDs
  - Tool/action specification
  - Input parameters (can reference `$stepN.field`)
  - Dependencies
  - Success criteria
  - Retry/timeout bounds

**Key Features:**
- Uses GPT-4o with structured prompts
- Only uses tools from catalog (never invents)
- Creates measurable success criteria
- Supports local and global repair strategies

### 2. Evaluator

**Responsibility:** Validate plans and check step results.

**Two Modes:**

#### Pre-Execution Validation (Full)
- DAG soundness (no cycles, valid dependencies)
- Tool validity (all tools exist)
- IO completeness (all inputs provided)
- Budget feasibility
- Safety checks

**Output:**
```json
{
  "valid": true/false,
  "issues": [
    {
      "severity": "error",
      "step_id": "step1",
      "type": "missing_tool",
      "message": "...",
      "suggestion": "..."
    }
  ],
  "can_patch": true/false,
  "patches": [...]
}
```

#### Mid-Execution Check (Light)
- Compare outputs to success criteria
- Determine if retry or replan needed

**Output:**
```json
{
  "success": true/false,
  "criteria_met": [...],
  "criteria_failed": [...],
  "should_retry": true/false,
  "should_replan": true/false,
  "notes": "..."
}
```

### 3. Executor

**Responsibility:** Dispatch and execute steps.

**Algorithm:**
1. Check budget
2. Find next ready step (all deps completed)
3. Resolve parameters (`$stepN.field` → actual values)
4. Route by type:
   - `type="atomic"` or `tool="llamaindex_worker"` → LlamaIndex worker
   - `type="tool"` → Direct tool call
5. Store result in artifacts
6. Update budget
7. Evaluate result

**Step Routing:**
- **Simple tools:** Direct invocation (search, email, screenshot)
- **Complex tasks:** LlamaIndex worker with RAG

### 4. Synthesis

**Responsibility:** Create final result summary.

**Output:**
```json
{
  "success": true/false,
  "summary": "Brief description",
  "key_outputs": {
    "email_sent": true,
    "presentation_path": "/path/to/file.key"
  },
  "next_actions": ["suggestion1", "suggestion2"]
}
```

## LlamaIndex Worker

**Purpose:** Handle atomic tasks requiring:
- Document analysis
- Iterative reasoning
- RAG (Retrieval Augmented Generation)
- Content transformation

**Features:**
- Automatic RAG detection (keywords: search, find, analyze, extract, etc.)
- Semantic search over indexed documents
- Structured JSON output
- Token usage tracking

**Example Tasks:**
- "Analyze document and summarize key points"
- "Find pages containing specific information"
- "Compare two documents and highlight differences"

## Tool Catalog

Each tool in the catalog includes:

```python
ToolSpec(
    name="search_documents",
    kind="tool",  # "tool" or "worker"
    io={
        "in": ["query: str"],
        "out": ["doc_path", "doc_title", "relevance_score"]
    },
    strengths=[
        "Semantic search",
        "Fast retrieval",
        "Metadata included"
    ],
    limits=[
        "Requires indexed documents",
        "Single result only"
    ],
    description="Search for documents using semantic similarity"
)
```

**Available Tools:**
- `search_documents`: Semantic document search
- `extract_section`: Extract pages/sections from documents
- `take_screenshot`: Capture page images
- `compose_email`: Create/send emails via Mail.app
- `create_keynote`: Generate Keynote presentations
- `create_pages_doc`: Generate Pages documents
- `llamaindex_worker`: RAG-powered atomic task execution

## Replan Loop

**Triggers:**
1. Pre-execution validation fails
2. Step fails with no retries left
3. Step evaluation indicates fundamental issue
4. Budget/latency overrun risk
5. New constraints added mid-execution

**Behavior:**
- Pass current plan, completed steps, and critique to Planner
- Planner chooses strategy:
  - **Local repair:** Minimal changes, preserve completed steps
  - **Global repair:** Redesign DAG, reuse completed outputs via `$stepN.field`

**Example:**
```
Original Plan:
  step1: search_documents ✓ COMPLETED
  step2: extract_section (FAILED - invalid page)
  step3: compose_email (PENDING)

Replanned:
  step1: (reused from artifacts)
  step2_v2: extract_section (fixed page parameter)
  step3: compose_email (uses $step2_v2.extracted_text)
```

## Budget Tracking

Three dimensions:
1. **Tokens:** LLM API usage
2. **Time:** Wall-clock execution time
3. **Steps:** Number of steps executed

**Enforcement:**
- Checked before each step execution
- Graceful partial completion on exhaustion
- Tracked in metadata for analysis

## State Persistence

**Capabilities:**
- Save state at any point
- Resume from saved state
- Named checkpoints
- Auto-cleanup of old states

**Usage:**
```python
# Save current state
orchestrator.save_state(state, "checkpoint_after_step3")

# Resume execution
result = orchestrator.resume("path/to/state.json")

# List saved states
persistence.list_states(run_id="abc123")
```

## Usage Examples

### Basic Execution

```python
from src.orchestrator import LangGraphOrchestrator
from src.orchestrator.state import Budget
from src.documents import DocumentIndexer
from src.utils import load_config

# Initialize
config = load_config()
indexer = DocumentIndexer(config)
orchestrator = LangGraphOrchestrator(config, indexer)

# Execute
result = orchestrator.execute(
    goal="Find guitar tabs and email to user@example.com",
    context={"user_preference": "fingerstyle"},
    budget=Budget(tokens=50000, time_s=300, steps=20)
)

print(result["summary"])
```

### With Custom Context

```python
result = orchestrator.execute(
    goal="Create a technical presentation from AI research paper",
    context={
        "presentation_style": "academic",
        "max_slides": 15,
        "include_references": True
    },
    budget=Budget(tokens=100000, time_s=600, steps=30)
)
```

### Resume from Saved State

```python
from src.orchestrator.persistence import create_persistence

persistence = create_persistence(config)

# Resume
result = orchestrator.resume(
    state_path="data/orchestrator_states/run_abc123.json"
)
```

## Configuration

Add to `config.yaml`:

```yaml
orchestrator:
  state_storage_dir: "data/orchestrator_states"
  max_replans: 3
  checkpoint_every_n_steps: 5
```

## Testing

Run the test suite:

```bash
# Batch mode with predefined tests
python main_orchestrator.py

# Interactive mode
python main_orchestrator.py --interactive
```

## Best Practices

### 1. Define Clear Success Criteria

❌ Bad:
```python
"success_criteria": ["document found"]
```

✅ Good:
```python
"success_criteria": [
    "doc_path is a valid file path",
    "relevance_score > 0.7",
    "file_type is PDF or DOCX"
]
```

### 2. Use Appropriate Tool Types

- **Simple operations:** Use direct tools
- **Complex reasoning:** Use LlamaIndex worker
- **Multi-step sub-tasks:** Consider subplan type

### 3. Set Realistic Budgets

```python
# Light task
Budget(tokens=10000, time_s=60, steps=5)

# Medium task
Budget(tokens=50000, time_s=300, steps=20)

# Complex task
Budget(tokens=100000, time_s=600, steps=40)
```

### 4. Leverage Context

```python
context = {
    "user_preference": "detailed",
    "output_format": "markdown",
    "language": "en",
    "safety_checks_enabled": True
}
```

### 5. Monitor Budget Usage

```python
result = orchestrator.execute(...)

metadata = result["metadata"]
print(f"Tokens used: {metadata['budget_used']['tokens']}")
print(f"Time: {metadata['budget_used']['time_s']:.2f}s")
print(f"Steps: {metadata['budget_used']['steps']}")
```

## Troubleshooting

### Issue: Plan validation fails repeatedly

**Solution:** Check tool_specs are loaded correctly. Ensure planner isn't inventing tools.

### Issue: Steps retry infinitely

**Solution:** Set appropriate `max_retries` and `timeout_s`. Add better success criteria.

### Issue: Budget exhausted too quickly

**Solution:** Increase budget limits or optimize prompts. Use direct tools instead of LlamaIndex worker when possible.

### Issue: Replanning doesn't preserve completed steps

**Solution:** Check that step IDs are consistent. Verify artifacts are being stored correctly.

## Advanced Features

### Custom Tools

Add new tools to the catalog:

```python
from src.orchestrator.tools_catalog import ToolSpec

custom_tool = ToolSpec(
    name="custom_analyzer",
    kind="tool",
    io={
        "in": ["data: str"],
        "out": ["analysis: Dict"]
    },
    strengths=["Fast analysis", "Structured output"],
    limits=["JSON input only"],
    description="Analyze data and return insights"
)

# Add to catalog
tool_catalog.append(custom_tool)
```

### Checkpoints

```python
from src.orchestrator.persistence import CheckpointManager

checkpoint_mgr = CheckpointManager(persistence)

# Create checkpoint
checkpoint_mgr.create_checkpoint(
    state=current_state,
    name="before_email_send",
    description="Save before sending email"
)

# Restore if needed
state = checkpoint_mgr.restore_checkpoint("before_email_send")
```

### Custom Evaluators

Extend the EvaluatorNode for domain-specific validation:

```python
class CustomEvaluator(EvaluatorNode):
    def validate_plan(self, state):
        state = super().validate_plan(state)

        # Add custom checks
        if self._check_security_policy(state):
            state["validation_passed"] = True
        else:
            state["need_replan"] = True
            state["notes"].append({
                "severity": "error",
                "message": "Security policy violation"
            })

        return state
```

## Comparison to Original Agent

| Feature | Original Agent | LangGraph Orchestrator |
|---------|---------------|----------------------|
| Planning | Single-shot | Iterative with validation |
| Error Handling | Step-level retries | Step retries + full replanning |
| State Management | In-memory dict | Persistent, resumable |
| Evaluation | None | Pre + post execution |
| Budget Tracking | None | Multi-dimensional |
| Tool Routing | Static | Dynamic (LlamaIndex for complex) |
| Dependency Management | Linear | DAG-based |

## Next Steps

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run tests:
   ```bash
   python main_orchestrator.py
   ```

3. Try interactive mode:
   ```bash
   python main_orchestrator.py --interactive
   ```

4. Integrate into your application:
   ```python
   from src.orchestrator import LangGraphOrchestrator
   ```

## Summary

The LangGraph Orchestrator provides:

✅ **Robust planning** with validation and repair
✅ **Budget-aware execution** with multi-dimensional tracking
✅ **State persistence** for resumability
✅ **Intelligent routing** (direct tools vs. LlamaIndex)
✅ **DAG-based dependencies** for parallel execution
✅ **Comprehensive evaluation** at every stage
✅ **Automatic replanning** on failures

Perfect for complex, multi-step macOS automation workflows!
