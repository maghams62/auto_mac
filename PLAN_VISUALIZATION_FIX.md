# Plan Visualization Fix

## Problem

The backend was correctly emitting plan events via WebSocket, but the frontend was dropping them before they reached the UI:

1. **Backend** ([api_server.py:225-236](api_server.py#L225-L236)): Sends `{type: "plan", goal, steps, message: ""}` after generating a plan
2. **Frontend Handler** ([frontend/lib/useWebSocket.ts:109-155](frontend/lib/useWebSocket.ts#L109-L155)):
   - Didn't have a case for `type === "plan"`
   - Defaulted to `type: "assistant"`
   - Filtered out messages with empty `message` field (line 138: `if (!payload && messageType !== "status") { return; }`)
   - Plan messages have `message: ""`, so they were dropped
3. **UI Component** ([frontend/components/MessageBubble.tsx:124-150](frontend/components/MessageBubble.tsx#L124-L150)): Already had beautiful plan rendering JSX that never ran

## Solution

Added an explicit plan handler in the WebSocket message handler **before** the payload logic:

```typescript
// Handle plan messages specially - they have goal/steps instead of message
if (rawType === "plan") {
  setMessages((prev) => [
    ...prev,
    {
      type: "plan",
      message: "",
      goal: data.goal ?? "",
      steps: Array.isArray(data.steps) ? data.steps : [],
      timestamp: data.timestamp || new Date().toISOString(),
    },
  ]);
  return;
}
```

This bypasses the empty payload filter and correctly populates the Message interface with plan data.

## Changes Made

### 1. frontend/lib/useWebSocket.ts (lines 108-121)
- Added plan message handler before the type mapping switch
- Extracts `goal` and `steps` from the WebSocket payload
- Returns early to bypass empty payload check
- Preserves security checks and validation

### 2. frontend/components/ChatInterface.tsx (line 180)
- Fixed TypeScript error: removed check for invalid `"response"` type
- Changed from: `msg.type === "response" || msg.type === "assistant"`
- Changed to: `msg.type === "assistant"`

## Files Modified

- [frontend/lib/useWebSocket.ts](frontend/lib/useWebSocket.ts#L108-L121)
- [frontend/components/ChatInterface.tsx](frontend/components/ChatInterface.tsx#L180)

## Files Unchanged (Already Working)

- [api_server.py](api_server.py#L225-L236) - Backend plan emission ✅
- [frontend/components/MessageBubble.tsx](frontend/components/MessageBubble.tsx#L124-L150) - Plan rendering UI ✅
- [frontend/lib/useWebSocket.ts](frontend/lib/useWebSocket.ts#L4-L17) - Message interface ✅

## Testing

Run the test suite:
```bash
python3 tests/test_plan_visualization.py
```

All tests pass ✅

## What You'll See

When the agent creates a multi-step plan, you'll now see a nicely formatted breakdown in the chat:

```
┌─────────────────────────────────────────┐
│ Plan                              10:30 │
├─────────────────────────────────────────┤
│ 🎯 Research and create presentation     │
│                                         │
│ Breaking down into 2 steps:            │
│                                         │
│ 1. search_web                          │
│    Need to gather current info about   │
│    AI trends                           │
│                                         │
│ 2. create_presentation                 │
│    Organize findings into presentation │
│    Depends on: step 1                  │
└─────────────────────────────────────────┘
```

## Next Steps

1. **Restart the UI**:
   ```bash
   ./start_ui.sh
   ```

2. **Test with a multi-step query**:
   - "Search for AI trends and create a presentation about them"
   - "Email me the latest stock prices for NVDA and create a report"
   - "Find documents about machine learning and organize them"

3. **What to look for**:
   - A "Plan" message appears in the chat before execution
   - Shows the goal with 🎯 emoji
   - Lists all steps with numbers
   - Shows reasoning for each step (if available)
   - Steps with dependencies show which prior steps they rely on

## Technical Details

### Message Flow

1. **Agent generates plan** → calls `on_plan_created` callback
2. **Backend** ([api_server.py:229](api_server.py#L229)) → sends WebSocket message `{type: "plan", ...}`
3. **Frontend handler** ([useWebSocket.ts:109](frontend/lib/useWebSocket.ts#L109)) → detects `rawType === "plan"`
4. **Handler creates Message** → `{type: "plan", message: "", goal, steps, timestamp}`
5. **React state updates** → `setMessages()` adds plan to message array
6. **MessageBubble renders** ([MessageBubble.tsx:124](frontend/components/MessageBubble.tsx#L124)) → shows plan UI

### Why This Fix is Safe

- **No backend changes**: Backend already works correctly
- **No UI component changes**: MessageBubble already had plan rendering
- **Minimal handler change**: Just added early return for plan type
- **Preserves security**: Still validates and sanitizes all data
- **TypeScript safe**: Properly typed using existing Message interface
- **No new dependencies**: Uses existing interfaces and types

## Impact

This gives you the "inner loop" visualization you wanted:
- See what the agent plans to do **before** it executes
- Understand complex multi-step workflows
- Debug planning issues more easily
- Better UX for users waiting on long-running tasks

All with minimal risk and zero hardcoding! 🎉
