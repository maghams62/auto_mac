# Browser-Based UI Testing Guide

**This is the authoritative testing guide. All agents MUST follow this methodology.**

## Quick Reference

See **[../../TESTING_METHODOLOGY.md](../../TESTING_METHODOLOGY.md)** for the complete testing workflow.

## Key Points

1. **Always test in the actual browser UI** - Never skip browser testing
2. **Use browser automation tools** - Navigate, type, click, verify
3. **Check both success and error paths** - Verify proper error messages
4. **Document results** - Include snapshots and console logs
5. **Clean up** - Stop test servers after testing

## Standard Workflow

1. Start API server and frontend
2. Navigate to http://localhost:3000
3. Execute command in UI
4. Wait for response
5. Verify results in browser
6. Check console for errors
7. Clean up servers

## Browser Tools Available

- `browser_navigate(url)` - Navigate to page
- `browser_snapshot()` - Get page state
- `browser_click(element, ref)` - Click element
- `browser_type(element, ref, text)` - Type text
- `browser_press_key(key)` - Press key
- `browser_wait_for(time=N)` - Wait N seconds
- `browser_console_messages()` - Get console logs

## What to Verify

✅ Success: Response appears, correct content, no errors
❌ Failure: "Unknown error" appears, no response, generic errors

See **[../../TESTING_METHODOLOGY.md](../../TESTING_METHODOLOGY.md)** for complete details.

