# Multi-Agent System Quick Start

## Overview

The system now uses **5 specialized agents** instead of a monolithic tool collection:

- **FILE AGENT** - Documents and files
- **BROWSER AGENT** - Web browsing
- **PRESENTATION AGENT** - Keynote/Pages creation
- **EMAIL AGENT** - Email operations
- **CRITIC AGENT** - Verification and QA

Each agent is a **mini-orchestrator** for its domain.

## Quick Start

### 1. Using the Agent Registry

```python
from src.agent import AgentRegistry
from src.utils import load_config

config = load_config()
registry = AgentRegistry(config)

# Execute any tool - automatically routed to correct agent
result = registry.execute_tool("search_documents", {
    "query": "quarterly report"
})
```

### 2. Direct Agent Access

```python
# Get a specific agent
file_agent = registry.get_agent("file")

# Use the agent
result = file_agent.execute("search_documents", {"query": "report"})

# Get agent info
tools = file_agent.get_tools()
hierarchy = file_agent.get_hierarchy()
```

### 3. Multi-Agent Workflow

```python
# Coordinate multiple agents
registry = AgentRegistry(config)

# 1. Browser Agent: Find information
search = registry.execute_tool("google_search", {"query": "Python async"})
content = registry.execute_tool("extract_page_content", {
    "url": search["results"][0]["link"]
})

# 2. Presentation Agent: Create presentation
keynote = registry.execute_tool("create_keynote", {
    "title": "Python Async",
    "content": content["content"]
})

# 3. Email Agent: Send it
email = registry.execute_tool("compose_email", {
    "subject": "Python Async Presentation",
    "attachments": [keynote["keynote_path"]],
    "send": True
})

# 4. Critic Agent: Verify
verification = registry.execute_tool("verify_output", {
    "step_description": "Send presentation via email",
    "user_intent": "Create and send Python async presentation",
    "actual_output": email
})
```

## Agent Reference

### FILE AGENT
```python
# Available tools
registry.execute_tool("search_documents", {"query": "..."})
registry.execute_tool("extract_section", {"doc_path": "...", "section": "..."})
registry.execute_tool("take_screenshot", {"doc_path": "...", "pages": [1, 2]})
registry.execute_tool("organize_files", {"category": "...", "target_folder": "..."})
```

### BROWSER AGENT
```python
# Available tools
registry.execute_tool("google_search", {"query": "...", "num_results": 5})
registry.execute_tool("navigate_to_url", {"url": "..."})
registry.execute_tool("extract_page_content", {"url": "..."})
registry.execute_tool("take_web_screenshot", {"url": "...", "full_page": True})
registry.execute_tool("close_browser", {})
```

### PRESENTATION AGENT
```python
# Available tools
registry.execute_tool("create_keynote", {"title": "...", "content": "..."})
registry.execute_tool("create_keynote_with_images", {"title": "...", "image_paths": [...]})
registry.execute_tool("create_pages_doc", {"title": "...", "content": "..."})
```

### EMAIL AGENT
```python
# Available tools
registry.execute_tool("compose_email", {
    "subject": "...",
    "body": "...",
    "recipient": "user@example.com",
    "attachments": ["path/to/file"],
    "send": True
})
```

### CRITIC AGENT
```python
# Available tools
registry.execute_tool("verify_output", {
    "step_description": "...",
    "user_intent": "...",
    "actual_output": {...}
})

registry.execute_tool("reflect_on_failure", {
    "step_description": "...",
    "error_message": "...",
    "context": {...}
})

registry.execute_tool("validate_plan", {
    "plan": [...],
    "goal": "...",
    "available_tools": [...]
})

registry.execute_tool("check_quality", {
    "output": {...},
    "quality_criteria": {"min_word_count": 100}
})
```

## Using with Main Orchestrator

The main orchestrator automatically uses the agent registry:

```python
from src.orchestrator.main_orchestrator import MainOrchestrator

orchestrator = MainOrchestrator(config)

# Orchestrator coordinates all agents automatically
result = orchestrator.run(
    goal="Search for Python docs, create presentation, and email it"
)

# Behind the scenes:
# 1. Planner sees all 17 tools from 5 agents
# 2. Creates plan: google_search → extract_page_content → create_keynote → compose_email
# 3. Executor routes each tool to its agent
# 4. Agents execute their tools
# 5. Critic validates outputs
```

## Checking Agent Status

```python
registry = AgentRegistry(config)

# Get statistics
stats = registry.get_agent_stats()
print(f"Total agents: {stats['total_agents']}")
print(f"Total tools: {stats['total_tools']}")

# Tool distribution
for agent_name, tool_count in stats['agents'].items():
    print(f"{agent_name}: {tool_count} tools")

# Get tool-to-agent mapping
from src.agent import get_agent_tool_mapping
mapping = get_agent_tool_mapping()
print(f"search_documents → {mapping['search_documents']} agent")
```

## Debugging

### Print Agent Hierarchy
```python
from src.agent import print_agent_hierarchy

print_agent_hierarchy()
```

### Get Agent Info
```python
registry = AgentRegistry(config)

file_agent = registry.get_agent("file")
print(file_agent.get_hierarchy())
```

### Test Tool Routing
```python
registry = AgentRegistry(config)

tool_name = "google_search"
agent = registry.get_agent_for_tool(tool_name)

if agent:
    print(f"✅ {tool_name} routes to {agent.__class__.__name__}")
else:
    print(f"❌ {tool_name} has no agent")
```

## Common Patterns

### Pattern 1: File-Only Workflow
```python
# All file operations
registry.execute_tool("search_documents", {"query": "report"})
registry.execute_tool("extract_section", {...})
registry.execute_tool("take_screenshot", {...})
```

### Pattern 2: Web Research
```python
# Browser agent workflow
registry.execute_tool("google_search", {"query": "..."})
registry.execute_tool("extract_page_content", {"url": "..."})
registry.execute_tool("close_browser", {})
```

### Pattern 3: Create & Send
```python
# Presentation + Email agents
registry.execute_tool("create_keynote", {...})
registry.execute_tool("compose_email", {
    "attachments": [keynote_path],
    "send": True
})
```

### Pattern 4: With Verification
```python
# Use critic agent for validation
result = registry.execute_tool("compose_email", {...})

verification = registry.execute_tool("verify_output", {
    "step_description": "Send email",
    "user_intent": "Email presentation to user",
    "actual_output": result
})

if not verification["valid"]:
    print(f"Issues: {verification['issues']}")
    print(f"Suggestions: {verification['suggestions']}")
```

## Migration from Old System

### Before (Monolithic Tools)
```python
from src.agent.tools import ALL_TOOLS

# Tools were flat list
for tool in ALL_TOOLS:
    tool.invoke(inputs)
```

### After (Agent Hierarchy)
```python
from src.agent import AgentRegistry

registry = AgentRegistry(config)

# Tools are organized by agent
registry.execute_tool("search_documents", inputs)
```

### Backwards Compatibility
```python
# Old code still works
from src.agent import ALL_TOOLS, BROWSER_TOOLS

# ALL_TOOLS now contains file + presentation + email tools
# BROWSER_TOOLS contains browser tools
# Both work as before
```

## Error Handling

All agents return consistent error format:

```python
result = registry.execute_tool("search_documents", {"query": "test"})

if result.get("error"):
    print(f"Error type: {result['error_type']}")
    print(f"Message: {result['error_message']}")
    print(f"Retryable: {result['retry_possible']}")

    # Use critic agent to analyze
    reflection = registry.execute_tool("reflect_on_failure", {
        "step_description": "search_documents",
        "error_message": result['error_message'],
        "context": {}
    })
    print(f"Root cause: {reflection['root_cause']}")
    print(f"Fix: {reflection['corrective_actions']}")
else:
    print("Success!")
```

## Next Steps

1. Read [MULTI_AGENT_HIERARCHY.md](MULTI_AGENT_HIERARCHY.md) for complete documentation
2. See [ARCHITECTURE.md](ARCHITECTURE.md) for system design
3. Check individual agent files in `src/agent/` for details

## Testing

```bash
# Test agent imports
python -c "from src.agent import AgentRegistry; print('✅ Agents ready')"

# Test registry
python -c "
from src.agent import AgentRegistry
from src.utils import load_config

registry = AgentRegistry(load_config())
stats = registry.get_agent_stats()
print(f'✅ {stats[\"total_agents\"]} agents, {stats[\"total_tools\"]} tools')
"

# Test orchestrator integration
python -c "
from src.orchestrator.tools_catalog import generate_tool_catalog

catalog = generate_tool_catalog()
print(f'✅ Tool catalog: {len(catalog)} tools')
"
```

## Summary

**5 Specialized Agents** → Clear responsibilities
**17 Total Tools** → Organized hierarchically
**Automatic Routing** → Tools route to correct agent
**Mini-Orchestrators** → Each agent manages its domain
**Backwards Compatible** → Old code still works

The multi-agent system provides better organization, maintainability, and scalability while maintaining full backwards compatibility.
