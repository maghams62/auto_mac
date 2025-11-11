# Testing Methodology - Browser-Based UI Testing

## ⚠️ CRITICAL: All Feature Testing Must Use This Approach

**This is the ONLY acceptable way to test features.** All agents and developers MUST follow this methodology when testing any feature, command, or functionality.

## Standard Testing Workflow

### 1. Start Required Services

```bash
# Start API server
cd /Users/siddharthsuresh/Downloads/auto_mac
source venv/bin/activate
python3 api_server.py > /dev/null 2>&1 &
echo $! > api_server.pid

# Start frontend
cd frontend
npm run dev > /dev/null 2>&1 &
echo $! > ../frontend.pid

# Wait for services to be ready
sleep 6
```

### 2. Open Browser and Navigate

```python
# Use browser automation tools
browser_navigate("http://localhost:3000")
browser_wait_for(time=3)  # Wait for page to load
browser_snapshot()  # Verify page loaded correctly
```

### 3. Verify Initial State

- Check that WebSocket connection is established
- Verify "Connected to Mac Automation Assistant" message appears
- Confirm input field is enabled and ready

### 4. Execute Test Command

```python
# Click on input field
browser_click(element="Message input textbox", ref="e74")

# Type the command
browser_type(element="Message input textbox", ref="e74", text="/your-command")

# Wait for UI to update
browser_wait_for(time=1)

# Send the command (either click Send button or press Enter)
browser_click(element="Send button", ref="e75")
# OR
browser_press_key(key="Enter")
```

### 5. Wait for Response

```python
# Wait for processing to complete
browser_wait_for(time=5)  # Adjust based on expected response time

# Take snapshot to see results
browser_snapshot()
```

### 6. Verify Results

**CRITICAL CHECKS:**

1. **Success Case:**
   - ✅ Verify the response message appears in the chat
   - ✅ Check that the message contains expected content
   - ✅ Confirm NO "Unknown error" messages appear
   - ✅ Verify status changes from "processing" to "idle" or "success"

2. **Error Case:**
   - ✅ Verify error message is displayed
   - ✅ Check that error message is specific and informative
   - ✅ Confirm NO "Unknown error" messages appear
   - ✅ Verify error is displayed with proper error styling

3. **Console Checks:**
   ```python
   browser_console_messages()  # Check for JavaScript errors
   ```

### 7. Clean Up

```bash
# Stop test servers
kill $(cat api_server.pid 2>/dev/null) 2>/dev/null
kill $(cat frontend.pid 2>/dev/null) 2>/dev/null
rm -f api_server.pid frontend.pid
```

## Example: Testing /confetti Command

```python
# 1. Start services (see above)

# 2. Navigate
browser_navigate("http://localhost:3000")
browser_wait_for(time=3)
browser_snapshot()

# 3. Type command
browser_click(element="Message input textbox", ref="e74")
browser_type(element="Message input textbox", ref="e74", text="/confetti")
browser_wait_for(time=1)

# 4. Send command
browser_click(element="Send button", ref="e75")
browser_wait_for(time=5)

# 5. Verify results
snapshot = browser_snapshot()
# Check snapshot for:
# - User message: "/confetti"
# - Status: "Processing your request..."
# - Response: "Confetti celebration triggered! 🎉" (or specific error message)
# - NO "Unknown error" messages

# 6. Check console
console = browser_console_messages()
# Verify WebSocket messages received correctly
# Check for: type=response, message contains expected content

# 7. Clean up
```

## What to Verify

### ✅ Success Indicators:
- Command appears in chat history
- Status shows "processing" then completes
- Response message appears with correct content
- No error messages
- Console shows successful WebSocket messages

### ❌ Failure Indicators:
- "Unknown error" message appears
- No response after reasonable timeout
- Error message is generic or unhelpful
- Console shows WebSocket errors
- Status stuck on "processing"

## Important Notes

1. **Always test in the actual browser UI** - Never rely solely on:
   - Direct API calls
   - Unit tests
   - WebSocket tests without browser
   - Command-line tests

2. **Verify the full user experience:**
   - User types command
   - Command is sent via WebSocket
   - Response is received
   - UI displays the response correctly
   - Error handling works properly

3. **Check both success and error paths:**
   - Test when feature works correctly
   - Test when feature fails (simulate failures if needed)
   - Verify error messages are helpful

4. **Document test results:**
   - Screenshot or snapshot of results
   - Console messages
   - Any errors encountered
   - Whether test passed or failed

## Browser Tool Reference

Available browser automation tools:
- `browser_navigate(url)` - Navigate to URL
- `browser_snapshot()` - Get current page state
- `browser_click(element, ref)` - Click an element
- `browser_type(element, ref, text)` - Type text into input
- `browser_press_key(key)` - Press a key
- `browser_wait_for(time=N)` - Wait N seconds
- `browser_console_messages()` - Get console logs
- `browser_network_requests()` - Check network activity

## When to Use This Methodology

**ALWAYS use this approach for:**
- Testing new slash commands (`/confetti`, `/maps`, etc.)
- Testing agent functionality
- Testing error handling
- Testing UI features
- Verifying fixes work in production-like environment
- Before marking any feature as "complete"

**DO NOT skip browser testing for:**
- "Quick fixes"
- "Simple changes"
- "Backend-only" features
- "Already tested in unit tests"

## Integration with Agent System

When an agent is asked to test a feature, it MUST:
1. Reference this document
2. Follow the exact workflow described
3. Use browser automation tools
4. Verify results in the UI
5. Report findings with evidence (snapshots, console logs)

## File Location

This document is located at: `/Users/siddharthsuresh/Downloads/auto_mac/TESTING_METHODOLOGY.md`

All agents should reference this file when asked to test features.

