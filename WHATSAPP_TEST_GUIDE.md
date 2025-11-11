# WhatsApp Integration Test Guide

## Quick Start

### Prerequisites Checklist

- [ ] WhatsApp Desktop is installed
- [ ] WhatsApp Desktop is running
- [ ] You are logged in (QR code scanned)
- [ ] Accessibility permissions granted (System Preferences → Security & Privacy → Privacy → Accessibility)

### Run the Test

```bash
# Simple test script
python3 tests/test_whatsapp_simple.py

# Or use the shell script
./scripts/test_whatsapp.sh
```

## What the Test Does

1. **Session Verification** - Checks if WhatsApp is running and logged in
2. **List Chats** - Shows all available chats/groups
3. **Detect Unread** - Finds chats with unread messages
4. **Navigation** - Navigates to a specific chat/group (interactive)
5. **Read Messages** - Extracts messages from the chat
6. **Summarization** - Uses AI to summarize the conversation
7. **Sender Filtering** - Filters messages by sender (for groups)

## Testing Scenarios

### Scenario 1: Read Messages from a Contact

```python
from src.utils import load_config
from src.automation.whatsapp_controller import WhatsAppController

config = load_config()
controller = WhatsAppController(config)

# Navigate and read
result = controller.read_messages("John Doe", limit=10, is_group=False)
print(result.get("messages"))
```

### Scenario 2: Summarize Group Chat

```python
from src.agent.whatsapp_agent import WhatsAppAgent

agent = WhatsAppAgent(config)
result = agent.execute("whatsapp_summarize_messages", {
    "contact_name": "Work Team",
    "is_group": True,
    "limit": 50
})
print(result.get("summary"))
```

### Scenario 3: Filter by Sender

```python
agent = WhatsAppAgent(config)
result = agent.execute("whatsapp_read_messages_from_sender", {
    "contact_name": "Project Team",
    "sender_name": "Alice",
    "limit": 10
})
print(result.get("messages"))
```

## Expected Behavior

### Successful Test Output

```
✅ Session verified
✅ Found X chats/groups
✅ Successfully navigated to [contact]
✅ Read X messages
✅ Summary generated
```

### Common Issues

1. **"ProcessNotFound"** → WhatsApp Desktop not running
2. **"NotLoggedIn"** → Need to scan QR code
3. **"No accessible messages"** → Check Accessibility permissions or UI structure
4. **Navigation fails** → Use exact contact/group name as shown in WhatsApp

## UI Structure Notes

WhatsApp Desktop uses:
- Scroll areas for message containers
- Groups for individual messages
- Static text elements for message content
- First static text often contains sender name (for groups)

If reading fails, the AppleScript may need adjustment for your WhatsApp version.

## Next Steps After Testing

1. Verify message extraction works correctly
2. Test with different chat types (individual vs group)
3. Verify summarization quality
4. Test sender filtering in groups
5. Adjust UI selectors if needed based on your WhatsApp version

## Integration with Main System

Once tested, you can use WhatsApp tools in your automation workflows:

```python
# Via orchestrator
from src.agent.agent_registry import AgentRegistry

registry = AgentRegistry(config)
result = registry.execute_tool("whatsapp_summarize_messages", {
    "contact_name": "Team Chat",
    "is_group": True
})
```

