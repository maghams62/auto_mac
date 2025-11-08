# System Architecture: Separated Responsibilities

## Overview

This system uses a **two-layer architecture** with clear separation of concerns:

### Layer 1: High-Level Planning (LangGraph)
**Purpose**: Strategic planning and replanning
- Creates high-level execution plans
- Manages plan-execute-replan loop
- Handles strategic decisions

### Layer 2: Low-Level Execution (LlamaIndex + Verification)
**Purpose**: Tactical execution and verification
- Executes individual steps
- Iterative micro-planning within steps
- Verification and reflection
- Error handling and retries

---

## Architecture Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                        USER REQUEST                             │
└────────────────────┬───────────────────────────────────────────┘
                     │
                     v
┌────────────────────────────────────────────────────────────────┐
│               LAYER 1: LangGraph Orchestrator                   │
│                  (High-Level Planning)                          │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐             │
│  │  PLANNER │─────>│ VALIDATE │─────>│ EXECUTOR │             │
│  └──────────┘      └──────────┘      └────┬─────┘             │
│       ↑                                    │                    │
│       │                                    v                    │
│       │              ┌──────────┐    ┌──────────┐             │
│       └──────────────│  REPLAN  │<───│ EVALUATE │             │
│                      └──────────┘    └──────────┘             │
│                                                                 │
│  Responsibilities:                                             │
│  - Create step-by-step plans                                  │
│  - Validate plan feasibility                                  │
│  - Decide when to replan                                      │
│  - Manage overall workflow                                    │
│                                                                 │
└─────────────────────────┬──────────────────────────────────────┘
                          │
                          v
┌────────────────────────────────────────────────────────────────┐
│          LAYER 2: LlamaIndex + Verification Layer              │
│             (Low-Level Execution & Iteration)                   │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  For each step from Layer 1:                                  │
│                                                                 │
│  ┌────────────────────────────────────────────────────┐       │
│  │   Step Executor                                     │       │
│  │   ┌───────────────────────────────────┐            │       │
│  │   │  1. LlamaIndex Worker             │            │       │
│  │   │     - RAG-powered reasoning       │            │       │
│  │   │     - Iterative micro-planning    │            │       │
│  │   │     - Tool execution              │            │       │
│  │   └───────────┬───────────────────────┘            │       │
│  │               v                                     │       │
│  │   ┌───────────────────────────────────┐            │       │
│  │   │  2. Output Verifier (LLM)         │            │       │
│  │   │     - Check output vs intent      │            │       │
│  │   │     - Verify constraints         │            │       │
│  │   │     - Flag issues                │            │       │
│  │   └───────────┬───────────────────────┘            │       │
│  │               v                                     │       │
│  │   ┌───────────────────────────────────┐            │       │
│  │   │  3. Reflection Engine (LLM)       │            │       │
│  │   │     - Analyze failures            │            │       │
│  │   │     - Generate corrections        │            │       │
│  │   │     - Retry with fixes            │            │       │
│  │   └───────────────────────────────────┘            │       │
│  └────────────────────────────────────────────────────┘       │
│                                                                 │
│  Responsibilities:                                             │
│  - Execute individual tool calls                              │
│  - Verify outputs match user intent                           │
│  - Reflect and correct errors                                 │
│  - Iterative refinement within steps                          │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. **Planner (LLM-based)**
Location: `src/orchestrator/planner.py`

**Responsibilities**:
- Analyze user request
- Select appropriate tools from catalog
- Create step-by-step plan with dependencies
- Consider tool capabilities and constraints

**Key Features**:
- LLM determines ALL parameters (no hardcoding)
- Understands tool capabilities (e.g., "organize_files is standalone")
- Creates dependency graphs
- Supports replanning with feedback

**NOT Responsible For**:
- Executing steps
- Managing execution state
- Error handling
- Verification

---

### 2. **Executor (Orchestrator)**
Location: `src/orchestrator/executor.py`

**Responsibilities**:
- Execute plan steps in dependency order
- Manage execution state
- Resolve parameter references ($stepN.field)
- Track step results
- Handle step failures

**Key Features**:
- Dependency checking before execution
- Parameter resolution between steps
- Error classification (retryable vs fatal)
- Integration with verification layer

**NOT Responsible For**:
- Creating plans
- Deciding which tools to use
- Strategic replanning

---

### 3. **Verifier (LLM-based)**
Location: `src/agent/verifier.py`

**Responsibilities**:
- Verify step outputs match user intent
- Check quantitative constraints (e.g., "last page" = exactly 1)
- Flag mismatches between plan and reality
- Provide confidence scores

**Key Features**:
- LLM-based semantic verification
- Context-aware checking
- Detailed issue reporting
- Suggestions for corrections

---

### 4. **Reflection Engine (LLM-based)**
Location: `src/agent/verifier.py` (ReflectionEngine class)

**Responsibilities**:
- Analyze why verification failed
- Generate corrected approach
- Create micro-plans for fixes
- Learn from errors

**Key Features**:
- Root cause analysis
- Adaptive correction strategies
- Integration with verification feedback

---

### 5. **LlamaIndex Worker**
Location: `src/orchestrator/llamaindex_worker.py`

**Responsibilities**:
- Handle complex atomic tasks
- RAG-powered reasoning
- Iterative micro-planning within a step
- Access to document index

**Use Cases**:
- Research and analysis tasks
- Complex decision-making
- Tasks requiring document knowledge
- Multi-step atomic operations

---

### 6. **Parameter Resolver (LLM-based)**
Location: `src/agent/parameter_resolver.py`

**Responsibilities**:
- Determine ALL tool parameters using LLM
- No hardcoded values (top_k, thresholds, timeouts, etc.)
- Context-aware parameter selection

**Examples**:
- Search parameters: LLM decides top_k based on query
- Page selection: LLM interprets "last page" vs "first 3 pages"
- Retry strategies: LLM decides if/how to retry
- Timeouts: LLM sets appropriate timeouts per operation

---

### 7. **Section Interpreter (LLM-based)**
Location: `src/agent/section_interpreter.py`

**Responsibilities**:
- Interpret section queries without hardcoded patterns
- Map user intent to extraction strategy
- Determine exact pages vs semantic search

**Examples**:
- "last page" → exact_pages strategy with [last_page_num]
- "chorus" → semantic_search strategy
- "first 3 pages" → page_range strategy with [1, 2, 3]

---

## Workflow Example

### Request: "Organize all my music notes to a single folder called music stuff"

#### Layer 1: LangGraph Planning
1. **Planner** analyzes request
   - Sees `organize_files` tool in catalog
   - Reads tool description: "COMPLETE standalone tool"
   - Creates 1-step plan (not 3 steps with folder creation!)

2. **Validator** checks plan
   - Verifies `organize_files` exists
   - Checks parameters are valid
   - Approves plan

#### Layer 2: LlamaIndex Execution
3. **Executor** runs step 1
   - Calls `organize_files(category="music notes", target_folder="music stuff")`
   - Tool internally uses FileOrganizer

4. **FileOrganizer** (with LLM)
   - Scans directory for files
   - LLM categorizes each file based on semantic understanding
   - Creates folder automatically
   - Moves matching files
   - Returns detailed reasoning

5. **Verifier** checks output
   - Verifies correct files were moved
   - Checks WebAgents-Oct30th.pdf was excluded
   - Confirms music files were included
   - Returns validation result

6. **If verification fails**:
   - Reflection Engine analyzes why
   - Generates corrected parameters
   - Layer 1 decides whether to replan

---

## Key Principles

### 1. **Separation of Concerns**
- **Planner**: WHAT to do (strategic)
- **Executor**: HOW to do it (tactical)
- **Verifier**: DID we do it right? (quality)
- **Reflector**: WHAT went wrong? (learning)

### 2. **LLM-Driven Everything**
- No hardcoded parameters
- No pattern matching
- Semantic understanding throughout
- Adaptive decision-making

### 3. **Transparency**
- Every decision has LLM reasoning
- Full audit trail
- Detailed verification feedback
- Clear error messages

### 4. **Iterative Refinement**
- High-level replanning (Layer 1)
- Low-level retries (Layer 2)
- Verification-driven corrections
- Learning from failures

---

## Future Enhancements

1. **Memory System**: Store successful plans for similar requests
2. **Streaming**: Real-time progress updates
3. **Parallel Execution**: Run independent steps concurrently
4. **Cost Optimization**: Cache LLM decisions when appropriate
5. **Tool Learning**: Improve tool selection based on historical success
