# Session Memory System

## Overview

The Session Memory System provides robust, session-scoped contextual memory for the multi-agent architecture. It maintains conversation history, shared context, and user preferences across multiple interactions within a session, with clean reset capabilities via the `/clear` command.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface                          │
│  - Terminal UI (ChatUI)                                     │
│  - WebSocket API (api_server.py)                           │
│  - Session Status Indicators                                │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                   SessionManager                            │
│  - Create/retrieve sessions                                 │
│  - Persist to disk                                          │
│  - Handle /clear command                                    │
│  - Thread-safe access                                       │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                   SessionMemory                             │
│  - Conversation history                                     │
│  - Shared context (key-value store)                        │
│  - User preferences                                         │
│  - Metadata (usage statistics)                             │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              Agent Layer Integration                        │
│  - AutomationAgent (LangGraph)                             │
│  - MainOrchestrator                                         │
│  - AgentRegistry                                            │
│  - Individual Agents                                        │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. SessionMemory (`src/memory/session_memory.py`)

The core memory component that stores session-scoped context.

**Key Features:**
- Stores conversation history (user requests + agent responses)
- Maintains shared context across all agents
- Tracks usage statistics (tools used, agents invoked)
- Supports serialization to/from JSON
- Provides context summaries for LLM injection

**Data Structure:**
```python
SessionMemory:
  - session_id: str
  - status: SessionStatus (ACTIVE/CLEARED/ARCHIVED)
  - created_at: datetime
  - last_active_at: datetime
  - interactions: List[Interaction]
  - shared_context: Dict[str, Any]
  - user_context: UserContext
  - metadata: Dict[str, Any]
```

**Usage:**
```python
from src.memory import SessionMemory

# Create session
memory = SessionMemory()

# Add interaction
memory.add_interaction(
    user_request="Create a presentation",
    agent_response={"status": "success", "file_path": "/path/to/file.key"},
    plan=[...],
    step_results={...}
)

# Store shared context
memory.set_context("last_presentation_path", "/path/to/file.key")

# Retrieve context
path = memory.get_context("last_presentation_path")

# Get conversation history
history = memory.get_conversation_history(max_interactions=5)

# Clear session
memory.clear()
```

### 2. SessionManager (`src/memory/session_manager.py`)

Manages session lifecycle, persistence, and retrieval.

**Key Features:**
- Create and retrieve sessions
- Persist sessions to disk (JSON)
- Load sessions from disk
- Thread-safe session access
- Session archival for old sessions

**Usage:**
```python
from src.memory import SessionManager

# Initialize
manager = SessionManager(storage_dir="data/sessions")

# Get or create session
memory = manager.get_or_create_session("user_session_id")

# Save session
manager.save_session("user_session_id")

# Clear session
manager.clear_session("user_session_id")

# List all sessions
sessions = manager.list_sessions()
```

### 3. Agent Integration

#### AutomationAgent Integration

The LangGraph-based agent now accepts session context:

```python
from src.agent import AutomationAgent
from src.memory import SessionManager

session_manager = SessionManager()
agent = AutomationAgent(config, session_manager=session_manager)

# Run with session context
result = agent.run("Create a presentation", session_id="user_session")
```

**What happens:**
1. Agent loads session context before planning
2. Context is injected into LangGraph state
3. After execution, interaction is recorded
4. Session is saved to disk

#### AgentRegistry Integration

Tool execution now tracks session context:

```python
from src.agent.agent_registry import AgentRegistry
from src.memory import SessionManager

session_manager = SessionManager()
registry = AgentRegistry(config, session_manager=session_manager)

# Execute tool with session tracking
result = registry.execute_tool(
    "take_screenshot",
    {"page": 1},
    session_id="user_session"
)
```

**Automatic Context Storage:**
- Screenshots: Stores `last_screenshot_path`
- Presentations: Stores `last_presentation_path`
- Document searches: Stores `last_search_results`

#### MainOrchestrator Integration

The orchestrator merges session context with execution context:

```python
from src.orchestrator.main_orchestrator import MainOrchestrator
from src.memory import SessionManager

session_manager = SessionManager()
orchestrator = MainOrchestrator(config, session_manager=session_manager)

# Execute with session context
result = orchestrator.execute(
    "Create stock report for AAPL",
    context={...},
    session_id="user_session"
)
```

## User Interface

### Terminal UI (ChatUI)

The terminal UI displays session status indicators:

**Session States:**
- 🆕 **New Session** - No previous context loaded
- 💬 **Session Active** - Context from previous interactions available
- 🧹 **Session Cleared** - Context just reset

**Visual Indicators:**
```
You (new)        # New session, no history
You (#3)         # Active session, 3rd interaction
```

**Example Flow:**
```
🆕 New Session - No context loaded

You (new): Create a presentation about AI

✅ Task completed successfully!

You (#2): Add more slides

💬 Session Active - 1 interaction | Last: 2025-11-10

You (#2): /clear

🧹 Session Cleared - Starting fresh

You (new): Start over
```

### WebSocket API

The WebSocket endpoint supports session management:

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat?session_id=user123');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'system') {
    console.log('Session ID:', data.session_id);
    console.log('Session status:', data.session_status);  // "new" or "resumed"
    console.log('Interactions:', data.interactions);
  }

  if (data.type === 'clear') {
    console.log('Session cleared!');
  }

  if (data.type === 'response') {
    console.log('Result:', data.message);
    console.log('Interaction count:', data.interaction_count);
  }
};
```

**Sending /clear command:**
```javascript
ws.send(JSON.stringify({
  message: "/clear"
}));

// Or via command field:
ws.send(JSON.stringify({
  command: "clear"
}));
```

## Slash Commands

### `/clear` Command

Resets all session memory instantly.

**Behavior:**
- Clears conversation history
- Clears shared context
- Resets metadata
- Preserves session ID
- Updates UI to show fresh state

**Usage:**
```bash
# Terminal
You (#5): /clear
🧹 Session Cleared - Starting fresh

# WebSocket
{"message": "/clear"}
```

**Implementation:**
```python
# In slash_commands.py
if parsed["command"] == "clear":
    memory = self.session_manager.clear_session(session_id)
    return True, {
        "type": "clear",
        "content": "✨ Context cleared. Starting a new session.",
        "session_id": memory.session_id,
        "new_session": True
    }
```

## Context Propagation Flow

```
User Request
    │
    ▼
┌─────────────────────┐
│  SessionManager     │ ← Load session context
│  get_session()      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Planner            │ ← Inject context into prompts
│  (with history)     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Executor           │ ← Access shared context
│  (with references)  │   (e.g., $last_file_path)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Store Results      │ ← Update shared context
│  in Session Memory  │   Record interaction
└─────────────────────┘
```

## Example Use Cases

### 1. Multi-Step Workflow with Context

```python
# Session 1
User: "Take a screenshot of Google Finance for AAPL"
Agent: ✅ Screenshot saved to /path/to/screenshot.png
[Context stored: last_screenshot_path]

# Session 2 (same session)
User: "Create a Keynote presentation with that screenshot"
Agent: [Retrieves last_screenshot_path from context]
       ✅ Presentation created at /path/to/presentation.key
[Context stored: last_presentation_path]

# Session 3 (same session)
User: "Email that presentation to team@company.com"
Agent: [Retrieves last_presentation_path from context]
       ✅ Email sent with attachment
```

### 2. Conversational Context

```python
# Session 1
User: "Search for documents about AI"
Agent: ✅ Found 15 documents
[Context stored: last_search_results]

# Session 2
User: "Create a summary of the top 3"
Agent: [Retrieves last_search_results from context]
       ✅ Summary created
```

### 3. Session Reset

```python
# Active session with history
User: /clear
System: 🧹 Context cleared. Starting a new session.

# Fresh start
User: "New task"
Agent: [No previous context loaded]
```

## Persistence

Sessions are automatically saved to disk after each interaction:

**Storage Location:** `data/sessions/`

**File Format:** JSON
```json
{
  "session_id": "default",
  "status": "active",
  "created_at": "2025-11-10T10:00:00",
  "last_active_at": "2025-11-10T10:15:00",
  "interactions": [
    {
      "interaction_id": "int_1",
      "timestamp": "2025-11-10T10:05:00",
      "user_request": "Create a presentation",
      "agent_response": {...},
      "plan": [...],
      "step_results": {...}
    }
  ],
  "shared_context": {
    "last_presentation_path": "/path/to/file.key"
  },
  "user_context": {
    "preferences": {},
    "frequently_used_tools": ["create_keynote", "take_screenshot"]
  },
  "metadata": {
    "total_requests": 5,
    "total_steps_executed": 12,
    "tools_used": ["create_keynote", "take_screenshot"],
    "agents_used": ["presentation", "file"]
  }
}
```

## Testing

Run the comprehensive test suite:

```bash
# All tests
pytest tests/test_session_memory.py -v

# Specific test class
pytest tests/test_session_memory.py::TestSessionMemory -v

# Specific test
pytest tests/test_session_memory.py::TestSessionMemory::test_session_creation -v
```

**Test Coverage:**
- ✅ Session creation and initialization
- ✅ Memory persistence across interactions
- ✅ Session context propagation to agents
- ✅ /clear command functionality
- ✅ Session state UI indicators
- ✅ Multi-session management
- ✅ Serialization/deserialization
- ✅ Context sharing between agents

## Configuration

### Default Settings

```python
# Single-user mode (default)
session_id = "default"

# Multi-user mode
session_id = user_specific_id  # e.g., username, UUID
```

### Storage Configuration

```python
# Default
SessionManager(storage_dir="data/sessions")

# Custom location
SessionManager(storage_dir="/custom/path/sessions")
```

### Archival

Archive old sessions:

```python
# Archive sessions inactive for 30+ days
manager.archive_old_sessions(days=30)
```

## Best Practices

1. **Session IDs:**
   - Use consistent session IDs for the same user
   - For CLI: Single "default" session
   - For WebSocket: User-specific IDs (username, UUID)

2. **Context Storage:**
   - Store commonly referenced results (file paths, IDs)
   - Avoid storing large data structures
   - Use meaningful context keys

3. **Clear Command:**
   - Inform users about `/clear` availability
   - Confirm before clearing in critical workflows
   - Show visual feedback after clearing

4. **Persistence:**
   - Sessions auto-save after each interaction
   - Manual save not required
   - Survives application restarts

5. **UI Feedback:**
   - Always show session status indicators
   - Update UI after `/clear`
   - Display interaction counts

## Troubleshooting

### Session not persisting

**Issue:** Changes not saved between runs

**Solution:**
```python
# Ensure session manager is initialized
session_manager = SessionManager(storage_dir="data/sessions")

# Verify storage directory exists
Path("data/sessions").mkdir(parents=True, exist_ok=True)
```

### Context not propagating

**Issue:** Agents can't access previous results

**Solution:**
```python
# Ensure session_id is passed to agent.run()
result = agent.run(user_request, session_id=session_id)

# Verify context is being stored
memory.set_context("key", "value")
assert memory.get_context("key") == "value"
```

### /clear command not working

**Issue:** Session not clearing

**Solution:**
```python
# Ensure SessionManager is passed to SlashCommandHandler
slash_handler = create_slash_command_handler(
    agent_registry,
    session_manager=session_manager
)

# Verify clear implementation
memory = session_manager.clear_session(session_id)
assert len(memory.interactions) == 0
```

## Future Enhancements

- 📊 Session analytics dashboard
- 🔍 Session search and filtering
- 📤 Session export/import
- 🤖 LLM-powered session summarization
- 🔄 Session branching (save checkpoints)
- 👥 Multi-user session sharing
- 🔐 Session encryption
- ☁️ Cloud session storage

## API Reference

### SessionMemory

```python
class SessionMemory:
    def __init__(session_id: Optional[str] = None)
    def add_interaction(...) -> str
    def set_context(key: str, value: Any)
    def get_context(key: str, default: Any = None) -> Any
    def get_conversation_history(max_interactions: int = 10) -> List[Dict]
    def get_langgraph_context() -> Dict[str, Any]
    def clear()
    def is_active() -> bool
    def is_new_session() -> bool
    def to_dict() -> Dict[str, Any]
    @classmethod from_dict(data: Dict) -> SessionMemory
```

### SessionManager

```python
class SessionManager:
    def __init__(storage_dir: str = "data/sessions")
    def get_or_create_session(session_id: Optional[str]) -> SessionMemory
    def get_session(session_id: str) -> Optional[SessionMemory]
    def save_session(session_id: Optional[str]) -> bool
    def clear_session(session_id: Optional[str]) -> SessionMemory
    def delete_session(session_id: str) -> bool
    def list_sessions() -> List[Dict]
    def archive_old_sessions(days: int = 30) -> int
```

## Summary

The Session Memory System provides:

✅ **Persistent session memory** - Context maintained across interactions
✅ **Clean reset capability** - `/clear` command for fresh starts
✅ **UI feedback** - Visual indicators of session state
✅ **Agent propagation** - Context flows through all agents
✅ **Disk persistence** - Survives restarts
✅ **Thread-safe** - Concurrent access support
✅ **Easy integration** - Drop-in to existing architecture

The system is production-ready and requires minimal configuration for single-user CLI usage or multi-user WebSocket scenarios.
