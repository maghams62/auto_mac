# WhatsApp Integration Guide

## Overview

WhatsApp integration allows you to read messages from WhatsApp Desktop using macOS UI automation (AppleScript/System Events). This showcases AppleScript integration skills similar to the Discord agent pattern.

## Features

- ✅ Read messages from individual chats
- ✅ Read messages from groups
- ✅ Filter messages by sender (in groups)
- ✅ Detect unread chats
- ✅ List all available chats/groups
- ✅ AI-powered message summarization
- ✅ Extract action items from conversations

## Prerequisites

1. **WhatsApp Desktop** must be installed and running
2. **Accessibility Permissions** must be granted:
   - System Preferences → Security & Privacy → Privacy → Accessibility
   - Add Terminal/Python to allowed apps
3. **Logged in** to WhatsApp Desktop (QR code scanned)

## Testing

### Quick Test

Run the simple test script:

```bash
python3 tests/test_whatsapp_simple.py
```

Or use the shell script:

```bash
./scripts/test_whatsapp.sh
```

### Manual Testing via Python

```python
from src.utils import load_config
from src.automation.whatsapp_controller import WhatsAppController

config = load_config()
controller = WhatsAppController(config)

# 1. Verify session
result = controller.ensure_session()
print(result)

# 2. List all chats
chats = controller.get_chat_list()
print(f"Available chats: {chats.get('chats', [])}")

# 3. Navigate to a chat
controller.navigate_to_chat("John Doe", is_group=False)

# 4. Read messages
messages = controller.read_messages("John Doe", limit=10)
print(f"Messages: {messages.get('messages', [])}")

# 5. Summarize (requires agent)
from src.agent.whatsapp_agent import WhatsAppAgent
agent = WhatsAppAgent(config)
summary = agent.execute("whatsapp_summarize_messages", {
    "contact_name": "John Doe",
    "limit": 30
})
print(summary.get("summary"))
```

## Usage Examples

### Example 1: Read Unread Messages

```python
# Detect unread chats
unread = controller.detect_unread_chats()
for chat in unread.get("unread_chats", []):
    messages = controller.read_messages(chat, limit=20)
    print(f"{chat}: {len(messages.get('messages', []))} messages")
```

### Example 2: Summarize Group Chat

```python
agent = WhatsAppAgent(config)
result = agent.execute("whatsapp_summarize_messages", {
    "contact_name": "Work Team",
    "is_group": True,
    "limit": 50
})
print(result.get("summary"))
```

### Example 3: Filter by Sender

```python
agent = WhatsAppAgent(config)
result = agent.execute("whatsapp_read_messages_from_sender", {
    "contact_name": "Project Team",
    "sender_name": "Alice",
    "limit": 10
})
print(result.get("messages"))
```

## Troubleshooting

### "ProcessNotFound" Error

- **Problem**: WhatsApp Desktop is not running
- **Solution**: Open WhatsApp Desktop application

### "NotLoggedIn" or "QR_CODE_REQUIRED" Error

- **Problem**: Not logged in to WhatsApp Desktop
- **Solution**: 
  1. Open WhatsApp Desktop
  2. Scan QR code with your phone
  3. Wait for login to complete

### "No accessible messages detected"

- **Problem**: UI element extraction failed
- **Possible causes**:
  - Accessibility permissions not granted
  - WhatsApp Desktop UI structure changed
  - Chat is empty
- **Solution**:
  1. Check Accessibility permissions
  2. Try with a chat that has messages
  3. May need to adjust AppleScript for your WhatsApp version

### Navigation Fails

- **Problem**: Cannot find contact/group
- **Solution**:
  - Use exact name as shown in WhatsApp
  - Check spelling
  - Try listing chats first to see exact names

## UI Structure Notes

WhatsApp Desktop UI structure may vary by version. The current implementation:

1. Uses search (Cmd+F) to navigate to chats
2. Extracts messages from scroll areas and groups
3. Looks for static text elements containing message content
4. Identifies sender names for group messages

If message reading fails, you may need to:
1. Inspect WhatsApp UI with Accessibility Inspector
2. Adjust AppleScript selectors in `whatsapp_controller.py`
3. Test with different WhatsApp Desktop versions

## Integration with Orchestrator

The WhatsApp agent is fully integrated into the agent registry and can be used in workflows:

```python
from src.agent.agent_registry import AgentRegistry

registry = AgentRegistry(config)

# Read messages
result = registry.execute_tool("whatsapp_read_messages", {
    "contact_name": "Team Chat",
    "limit": 20,
    "is_group": True
})

# Summarize
result = registry.execute_tool("whatsapp_summarize_messages", {
    "contact_name": "Team Chat",
    "is_group": True,
    "limit": 50
})
```

## Available Tools

1. `whatsapp_ensure_session` - Verify WhatsApp is running
2. `whatsapp_navigate_to_chat` - Navigate to chat/group
3. `whatsapp_read_messages` - Read recent messages
4. `whatsapp_read_messages_from_sender` - Filter by sender
5. `whatsapp_read_group_messages` - Read group messages
6. `whatsapp_detect_unread` - Find unread chats
7. `whatsapp_list_chats` - List all chats
8. `whatsapp_summarize_messages` - AI summary
9. `whatsapp_extract_action_items` - Extract tasks

## Limitations

- **Read-only**: Cannot send messages (by design)
- **UI-dependent**: Requires WhatsApp Desktop UI structure
- **Version-specific**: May need adjustments for different WhatsApp versions
- **Permissions**: Requires Accessibility permissions

## Future Enhancements

- Real-time message monitoring
- Message search by keyword
- Media detection and handling
- Better UI element detection
- Support for WhatsApp Web

