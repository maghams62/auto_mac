# Session Memory Quick Start Guide

## 5-Minute Setup

### 1. Understanding Session Memory

Session memory lets your multi-agent system "remember" previous conversations and context:

```
Without Session Memory:
User: "Take a screenshot"
Agent: ✅ Screenshot saved
User: "Create a presentation with it"
Agent: ❌ "What screenshot?"

With Session Memory:
User: "Take a screenshot"
Agent: ✅ Screenshot saved [stored in context]
User: "Create a presentation with it"
Agent: ✅ Retrieved screenshot from context, presentation created!
```

### 2. How It Works

```
┌────────────┐     ┌─────────────┐     ┌──────────────┐
│   User     │────▶│  Session    │────▶│   Agents     │
│  Request   │     │  Memory     │     │  (Planner,   │
└────────────┘     │  - History  │     │   Executor)  │
                   │  - Context  │     └──────────────┘
                   │  - State    │
                   └─────────────┘
```

### 3. Using the System

#### Terminal (CLI)

```bash
# Start the app
python main.py

# Session starts automatically
🆕 New Session - No context loaded

You (new): Take a screenshot of page 1
✅ Task completed successfully!

# Context is maintained
You (#2): Create a Keynote with that screenshot
💬 Session Active - 1 interaction
✅ Task completed successfully!

# Clear session when needed
You (#3): /clear
🧹 Session Cleared - Starting fresh

You (new): New task
```

#### WebSocket API

```javascript
// Connect with session ID
const ws = new WebSocket('ws://localhost:8000/ws/chat');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Session ID:', data.session_id);
  console.log('Status:', data.session_status);  // "new" or "resumed"
};

// Send requests
ws.send(JSON.stringify({ message: "Take a screenshot" }));

// Clear session
ws.send(JSON.stringify({ message: "/clear" }));
```

### 4. Key Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/clear` | Reset session memory | `/clear` |
| `/help` | Show available commands | `/help` |
| `/agents` | List all agents | `/agents` |

### 5. Visual Indicators

#### Terminal UI

```
🆕 New Session          # No previous context
💬 Session Active       # Has context from previous interactions
🧹 Session Cleared      # Just reset

You (new)              # First interaction in session
You (#5)               # Fifth interaction (has context)
```

#### Session States

- **New Session**: No previous interactions
- **Active Session**: Has conversation history and context
- **Cleared Session**: Just reset, ready for fresh start

### 6. What Gets Remembered?

✅ **Remembered:**
- Conversation history (requests + responses)
- File paths (screenshots, presentations, reports)
- Search results
- User preferences
- Tools used

❌ **Not Remembered:**
- After `/clear` command
- After explicit session deletion
- Across different session IDs

### 7. Common Patterns

#### Pattern 1: Multi-Step Workflow
```
1. Take screenshot → [path stored]
2. Create presentation → [uses stored path]
3. Email presentation → [uses stored path]
```

#### Pattern 2: Conversational Context
```
User: "Search for AI documents"
[Results stored in context]

User: "Summarize the top 3"
[Retrieves results from context]
```

#### Pattern 3: Fresh Start
```
User: "Old task with context"
User: "/clear"
[All context cleared]
User: "New independent task"
```

### 8. Code Examples

#### Python Script

```python
from src.agent import AutomationAgent
from src.memory import SessionManager
from src.utils import load_config

# Initialize
config = load_config()
session_manager = SessionManager()
agent = AutomationAgent(config, session_manager=session_manager)

# Run with session
session_id = "user123"
result = agent.run("Take a screenshot", session_id=session_id)

# Context is automatically stored
result = agent.run("Create a Keynote with that", session_id=session_id)
# Agent retrieves screenshot path from session context

# Clear when needed
session_manager.clear_session(session_id)
```

#### Direct Access to Memory

```python
from src.memory import SessionManager

manager = SessionManager()

# Get session
memory = manager.get_or_create_session("user123")

# Check status
print(memory.is_new_session())  # True if brand new

# Access context
last_file = memory.get_context("last_screenshot_path")

# View history
history = memory.get_conversation_history(max_interactions=5)
for turn in history:
    print(f"User: {turn['user']}")
    print(f"Assistant: {turn['assistant']}")

# Clear
manager.clear_session("user123")
```

### 9. Best Practices

✅ **DO:**
- Use `/clear` when starting unrelated tasks
- Check session indicators to know your context state
- Let the system store common results automatically

❌ **DON'T:**
- Manually manage file paths (let context handle it)
- Worry about saving (auto-saves after each interaction)
- Mix unrelated tasks in the same session

### 10. Troubleshooting

#### "Agent doesn't remember previous results"

**Check:**
- Session ID is being passed to `agent.run()`
- Same session ID is used across interactions
- Session wasn't cleared between requests

**Fix:**
```python
# Correct ✅
result1 = agent.run("Request 1", session_id="user123")
result2 = agent.run("Request 2", session_id="user123")  # Same session

# Wrong ❌
result1 = agent.run("Request 1", session_id="user123")
result2 = agent.run("Request 2", session_id="user456")  # Different session!
```

#### "Session cleared unexpectedly"

**Check:**
- No accidental `/clear` commands
- Session files in `data/sessions/` directory exist
- Permissions allow writing to `data/sessions/`

#### "UI not showing session status"

**Check:**
```python
# Ensure UI has session manager
ui = ChatUI(session_manager=session_manager)
ui.set_session_id(session_id)
```

### 11. Testing

Quick test to verify everything works:

```bash
# Run test suite
pytest tests/test_session_memory.py -v

# Should see:
# ✅ test_session_creation
# ✅ test_add_interaction
# ✅ test_shared_context
# ✅ test_clear_session
# ... and more
```

### 12. Next Steps

- 📖 Read full documentation: [SESSION_MEMORY_SYSTEM.md](../SESSION_MEMORY_SYSTEM.md)
- 🧪 Run tests: `pytest tests/test_session_memory.py`
- 🚀 Start using in your app: `python main.py`
- 🔌 Integrate with WebSocket: See [api_server.py](../../api_server.py)

## Summary

You now have:
- ✅ Session memory that persists across interactions
- ✅ `/clear` command for fresh starts
- ✅ Visual UI indicators showing session state
- ✅ Automatic context propagation to all agents
- ✅ Disk persistence surviving restarts

Start using it with:
```bash
python main.py
```

Then try:
```
You (new): Take a screenshot of page 1
You (#2): Create a Keynote with that screenshot
You (#3): /clear
```

That's it! 🎉
