# Multi-Agent Hierarchy System

## Overview

The system is organized into **5 specialized agents**, each acting as a **mini-orchestrator** for its domain. This creates atomic, focused agents with clear responsibilities that can be coordinated by the main orchestrator.

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    MAIN ORCHESTRATOR                            │
│            (Plan-Execute-Replan Loop - LangGraph)               │
└────────────────────────┬───────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┬───────────────────┐
         │               │               │                    │
         ↓               ↓               ↓                    ↓
    ┌─────────┐    ┌──────────┐   ┌──────────┐        ┌──────────┐
    │  FILE   │    │ BROWSER  │   │PRESENTA- │        │  EMAIL   │
    │  AGENT  │    │  AGENT   │   │   TION   │   ...  │  AGENT   │
    │         │    │          │   │  AGENT   │        │          │
    └────┬────┘    └────┬─────┘   └────┬─────┘        └────┬─────┘
         │              │              │                     │
    ┌────▼─────────┐   ┌▼─────────┐  ┌▼──────────┐    ┌────▼────┐
    │ 4 tools      │   │ 5 tools  │  │ 3 tools   │    │ 1 tool  │
    │ LEVEL 1-4    │   │ LEVEL 1-4│  │ LEVEL 1-3 │    │ LEVEL 1 │
    └──────────────┘   └──────────┘  └───────────┘    └─────────┘
```

## Agent Hierarchy

### 1. FILE AGENT (4 tools)
**Domain**: Document and file operations
**Mini-Orchestrator for**: File discovery, content extraction, file organization

```
LEVEL 1: Document Discovery
└─ search_documents → Find relevant documents using semantic search

LEVEL 2: Content Extraction
└─ extract_section → Extract specific sections from documents (LLM-based interpretation)

LEVEL 3: Visual Capture
└─ take_screenshot → Capture page images from documents

LEVEL 4: File Organization
└─ organize_files → Organize files into folders (COMPLETE standalone tool)
```

**Tools**:
- `search_documents(query, user_request)`
- `extract_section(doc_path, section)`
- `take_screenshot(doc_path, pages)`
- `organize_files(category, target_folder, move_files)`

**Location**: `src/agent/file_agent.py`

---

### 2. BROWSER AGENT (5 tools)
**Domain**: Web browsing and content extraction
**Mini-Orchestrator for**: Web search, navigation, content extraction with langextract

```
LEVEL 1: Primary Search
└─ google_search → Search Google for information

LEVEL 2: Navigation & Content Extraction
├─ navigate_to_url → Go to a specific webpage
└─ extract_page_content → Get clean text from webpage (uses langextract)

LEVEL 3: Visual Capture
└─ take_web_screenshot → Capture webpage as image

LEVEL 4: Cleanup
└─ close_browser → Close browser and free resources
```

**Tools**:
- `google_search(query, num_results)`
- `navigate_to_url(url, wait_until)`
- `extract_page_content(url)`
- `take_web_screenshot(url, full_page)`
- `close_browser()`

**Location**: `src/agent/browser_agent.py`

---

### 3. PRESENTATION AGENT (3 tools)
**Domain**: Presentation and document creation
**Mini-Orchestrator for**: Keynote presentations, Pages documents

```
LEVEL 1: Text-based Presentations
└─ create_keynote → Create Keynote from text content

LEVEL 2: Image-based Presentations
└─ create_keynote_with_images → Create Keynote from screenshots/images

LEVEL 3: Document Creation
└─ create_pages_doc → Create Pages documents
```

**Tools**:
- `create_keynote(title, content, output_path)`
- `create_keynote_with_images(title, image_paths, output_path)`
- `create_pages_doc(title, content, output_path)`

**Location**: `src/agent/presentation_agent.py`

---

### 4. EMAIL AGENT (1 tool)
**Domain**: Email operations
**Mini-Orchestrator for**: Email composition and sending

```
LEVEL 1: Email Composition
└─ compose_email → Create and send emails via Mail.app
```

**Tools**:
- `compose_email(subject, body, recipient, attachments, send)`

**Location**: `src/agent/email_agent.py`

---

### 5. CRITIC AGENT (4 tools)
**Domain**: Verification, reflection, and quality assurance
**Mini-Orchestrator for**: Output validation, failure analysis, plan validation

```
LEVEL 1: Output Verification
└─ verify_output → Verify outputs match user intent and constraints

LEVEL 2: Failure Reflection
└─ reflect_on_failure → Analyze failures and generate corrective actions

LEVEL 3: Plan Validation
└─ validate_plan → Validate plans before execution (anti-hallucination)

LEVEL 4: Quality Assurance
└─ check_quality → Check outputs meet quality criteria
```

**Tools**:
- `verify_output(step_description, user_intent, actual_output, constraints)`
- `reflect_on_failure(step_description, error_message, context)`
- `validate_plan(plan, goal, available_tools)`
- `check_quality(output, quality_criteria)`

**Location**: `src/agent/critic_agent.py`

---

## Agent Registry

The `AgentRegistry` provides unified access to all agents:

```python
from src.agent import AgentRegistry
from src.utils import load_config

config = load_config()
registry = AgentRegistry(config)

# Get a specific agent
file_agent = registry.get_agent("file")

# Route tool execution to appropriate agent
result = registry.execute_tool("search_documents", {"query": "test"})

# Get statistics
stats = registry.get_agent_stats()
# {
#   "total_agents": 5,
#   "total_tools": 17,
#   "agents": {
#     "file": 4,
#     "browser": 5,
#     "presentation": 3,
#     "email": 1,
#     "critic": 4
#   }
# }
```

**Location**: `src/agent/agent_registry.py`

---

## Key Features

### 1. Atomic Agent Units
Each agent is self-contained and focused:
- **Clear domain boundaries**: File operations vs web browsing vs presentations
- **Independent lifecycle**: Browser agent can be initialized/closed independently
- **Separate error handling**: Network errors vs file errors vs email errors

### 2. Mini-Orchestrators
Each agent acts as a mini-orchestrator for its tools:
- **Tool routing**: Agent routes tool calls to appropriate tool implementations
- **Domain-specific logic**: Each agent can add domain-specific processing
- **Resource management**: Browser agent manages browser instance, file agent manages file handles

### 3. Hierarchical Tool Organization
Tools are organized by LEVEL within each agent:
- **LEVEL 1**: Primary/entry-point tools
- **LEVEL 2**: Secondary/processing tools
- **LEVEL 3**: Visual/capture tools
- **LEVEL 4**: Cleanup/organization tools

This guides the planner on natural tool sequences.

### 4. Separation of Concerns
```
FILE AGENT          → Local documents and files
BROWSER AGENT       → Web-based content
PRESENTATION AGENT  → macOS application integration (Keynote, Pages)
EMAIL AGENT         → Communication
CRITIC AGENT        → Quality assurance and validation
```

### 5. Anti-Hallucination Protection
All agents protected by the 3-layer defense system:
1. **Prompt Engineering**: Clear tool lists in prompts
2. **Programmatic Validation**: PlanValidator checks all tools exist
3. **Execution-Time Validation**: Agents verify tools before execution

---

## Usage Patterns

### Pattern 1: Single Agent Workflow
```python
# File-only workflow
registry = AgentRegistry(config)

# All operations handled by File Agent
search_result = registry.execute_tool("search_documents", {"query": "report"})
extract_result = registry.execute_tool("extract_section", {
    "doc_path": search_result["doc_path"],
    "section": "last page"
})
```

### Pattern 2: Multi-Agent Workflow
```python
# Combine multiple agents
registry = AgentRegistry(config)

# 1. Browser Agent: Research web
web_result = registry.execute_tool("google_search", {"query": "Python docs"})
content_result = registry.execute_tool("extract_page_content", {
    "url": web_result["results"][0]["link"]
})

# 2. Presentation Agent: Create presentation
keynote_result = registry.execute_tool("create_keynote", {
    "title": "Python Documentation",
    "content": content_result["content"]
})

# 3. Email Agent: Send presentation
email_result = registry.execute_tool("compose_email", {
    "subject": "Python Docs Presentation",
    "body": "Here's the presentation",
    "attachments": [keynote_result["keynote_path"]],
    "send": True
})

# 4. Critic Agent: Verify completion
verification_result = registry.execute_tool("verify_output", {
    "step_description": "Email sent with presentation",
    "user_intent": "Create and send presentation about Python docs",
    "actual_output": email_result
})
```

### Pattern 3: Agent-Specific Interface
```python
# Direct agent access
registry = AgentRegistry(config)

file_agent = registry.get_agent("file")
browser_agent = registry.get_agent("browser")

# Use agent-specific methods
file_tools = file_agent.get_tools()
file_hierarchy = file_agent.get_hierarchy()

# Execute through agent
result = file_agent.execute("search_documents", {"query": "test"})
```

---

## Integration with Main Orchestrator

The main orchestrator coordinates all agents:

```python
from src.orchestrator.main_orchestrator import MainOrchestrator

orchestrator = MainOrchestrator(config)

# Orchestrator automatically routes tools to agents
result = orchestrator.run(
    goal="Search for Python docs, create a presentation, and email it"
)

# Behind the scenes:
# 1. Planner sees all 17 tools from 5 agents
# 2. Planner creates plan with tools from multiple agents
# 3. Executor routes each tool to its agent
# 4. Critic Agent validates outputs
# 5. Orchestrator coordinates replanning if needed
```

---

## Agent Coordination

### Automatic Routing
```python
# AgentRegistry automatically routes tools to agents
registry.execute_tool("search_documents", {...})  → FILE AGENT
registry.execute_tool("google_search", {...})     → BROWSER AGENT
registry.execute_tool("create_keynote", {...})    → PRESENTATION AGENT
registry.execute_tool("compose_email", {...})     → EMAIL AGENT
registry.execute_tool("verify_output", {...})     → CRITIC AGENT
```

### Tool-to-Agent Mapping
```python
from src.agent import get_agent_tool_mapping

mapping = get_agent_tool_mapping()
# {
#   "search_documents": "file",
#   "extract_section": "file",
#   "take_screenshot": "file",
#   "organize_files": "file",
#   "google_search": "browser",
#   ...
# }
```

---

## File Structure

```
src/agent/
├── agent_registry.py         → Central registry for all agents
├── file_agent.py             → File operations agent
├── browser_agent.py          → Web browsing agent
├── presentation_agent.py     → Presentation creation agent
├── email_agent.py            → Email operations agent
├── critic_agent.py           → Verification/QA agent
├── __init__.py               → Exports all agents and tools
│
├── verifier.py               → Shared verification logic (used by Critic Agent)
├── parameter_resolver.py     → LLM-driven parameter resolution
├── section_interpreter.py    → LLM-driven section interpretation
│
└── (legacy)
    ├── tools.py              → Legacy tool definitions (now in agents)
    └── agent.py              → Legacy single agent (now orchestrator)
```

---

## Benefits

### 1. Modularity
- Each agent can be developed/tested independently
- Easy to add new agents (e.g., Database Agent, API Agent)
- Clear interfaces between agents

### 2. Maintainability
- Domain logic encapsulated in agents
- Easy to understand responsibilities
- Reduced coupling between components

### 3. Scalability
- Agents can be distributed across processes/machines
- Parallel execution of independent agents
- Resource isolation (browser instance, file handles)

### 4. Testability
- Test each agent independently
- Mock agents for integration testing
- Clear boundaries for unit tests

### 5. Extensibility
- Add new tools to existing agents
- Create new specialized agents
- Compose agents into workflows

---

## Future Enhancements

### 1. Agent Parallelization
```python
# Execute independent agents in parallel
async def parallel_workflow():
    file_task = registry.execute_tool_async("search_documents", {...})
    web_task = registry.execute_tool_async("google_search", {...})

    file_result, web_result = await asyncio.gather(file_task, web_task)
```

### 2. Agent State Management
```python
# Agents maintain internal state
browser_agent.navigate(url)
browser_agent.extract_content()  # Uses current page
browser_agent.take_screenshot()  # Uses current page
browser_agent.close()
```

### 3. Agent Communication
```python
# Agents can communicate directly
file_agent.send_to_agent("presentation", {
    "tool": "create_keynote",
    "data": extracted_content
})
```

### 4. New Specialized Agents
- **Database Agent**: SQL queries, data manipulation
- **API Agent**: REST API calls, authentication
- **Calendar Agent**: Schedule management, reminders
- **Notification Agent**: System notifications, alerts

---

## Testing

```python
# Test individual agents
def test_file_agent():
    config = load_config()
    file_agent = FileAgent(config)

    result = file_agent.execute("search_documents", {"query": "test"})
    assert not result.get("error")

# Test agent registry
def test_agent_registry():
    registry = AgentRegistry(config)

    stats = registry.get_agent_stats()
    assert stats["total_agents"] == 5
    assert stats["total_tools"] == 17

# Test tool routing
def test_tool_routing():
    registry = AgentRegistry(config)

    agent = registry.get_agent_for_tool("google_search")
    assert agent == registry.get_agent("browser")
```

---

## Summary

The multi-agent hierarchy system provides:

✅ **5 Specialized Agents** - Each with clear domain responsibilities
✅ **17 Total Tools** - Organized hierarchically within agents
✅ **Mini-Orchestrators** - Each agent manages its own tools
✅ **Atomic Operations** - Clear, focused tool implementations
✅ **Automatic Routing** - Tools automatically routed to agents
✅ **Anti-Hallucination** - Protected by 3-layer defense system
✅ **Modular Architecture** - Easy to extend and maintain
✅ **Coordinated Workflows** - Main orchestrator coordinates agents

This creates a clean, scalable architecture where responsibilities are clearly separated and agents can work independently or be coordinated for complex workflows.
