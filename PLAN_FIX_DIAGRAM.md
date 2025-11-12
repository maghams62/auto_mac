# Plan Visualization Fix - Visual Diagram

## Before (Plans were dropped)

```
┌──────────────────────────────────────────────────────────────┐
│ BACKEND (api_server.py:225-236)                              │
├──────────────────────────────────────────────────────────────┤
│ Agent generates plan                                         │
│ Calls send_plan_to_ui({goal, steps})                        │
│ Emits WebSocket: {type: "plan", message: "", goal, steps}   │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ FRONTEND (useWebSocket.ts:109-155) ❌ BROKEN                 │
├──────────────────────────────────────────────────────────────┤
│ 1. Receives: {type: "plan", message: "", ...}               │
│ 2. rawType = "plan" (no case in switch)                     │
│ 3. Defaults to messageType = "assistant"                    │
│ 4. Extracts payload from message field                      │
│ 5. payload = "" (empty!)                                    │
│ 6. Check: if (!payload && type !== "status") return; ❌     │
│ 7. DROPPED - never reaches setMessages()                    │
└──────────────────────────────────────────────────────────────┘
                         │
                         ▼
                    🚫 NOTHING
```

## After (Plans flow through)

```
┌──────────────────────────────────────────────────────────────┐
│ BACKEND (api_server.py:225-236) ✅ UNCHANGED                 │
├──────────────────────────────────────────────────────────────┤
│ Agent generates plan                                         │
│ Calls send_plan_to_ui({goal, steps})                        │
│ Emits WebSocket: {type: "plan", message: "", goal, steps}   │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ FRONTEND (useWebSocket.ts:109-121) ✅ FIXED                  │
├──────────────────────────────────────────────────────────────┤
│ 1. Receives: {type: "plan", message: "", goal, steps}       │
│ 2. rawType = "plan"                                         │
│ 3. NEW: if (rawType === "plan") { ... } ✅                  │
│ 4. Extract goal and steps from data                         │
│ 5. Create Message: {type:"plan", goal, steps, timestamp}    │
│ 6. setMessages() - adds to state                            │
│ 7. return; (bypasses empty payload check)                   │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ REACT STATE (messages array)                                │
├──────────────────────────────────────────────────────────────┤
│ [                                                            │
│   {type: "user", message: "Search and create report"},      │
│   {type: "plan", goal: "...", steps: [...]}, ← NEW!         │
│   {type: "status", message: "Executing step 1..."},         │
│   ...                                                        │
│ ]                                                            │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ UI (MessageBubble.tsx:124-150) ✅ ALREADY READY              │
├──────────────────────────────────────────────────────────────┤
│ if (isPlan && message.steps) {                              │
│   render plan UI:                                           │
│   - Show goal with 🎯                                       │
│   - List all steps with numbers                             │
│   - Display reasoning for each                              │
│   - Show dependencies                                       │
│ }                                                            │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
                    ✅ VISIBLE!
```

## The Fix (One Code Block)

```typescript
// frontend/lib/useWebSocket.ts (lines 108-121)

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
  return;  // ← Bypass empty payload check
}
```

## What You'll See in the UI

```
┌─────────────────────────────────────────────────────────┐
│ Plan                                            22:03   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ 🎯 Search for AI trends and create a presentation      │
│                                                         │
│ Breaking down into 3 steps:                            │
│                                                         │
│ 1. google_search                                        │
│    Need to gather current information about AI trends  │
│                                                         │
│ 2. file_search                                          │
│    Find relevant documents from local files             │
│    Depends on: step 1                                   │
│                                                         │
│ 3. create_presentation                                  │
│    Organize all findings into Keynote slides            │
│    Depends on: steps 1, 2                               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Testing Commands

```bash
# Run tests
python3 tests/test_plan_visualization.py
python3 tests/test_plan_integration.py

# Restart UI with new frontend build
./start_ui.sh

# Test with multi-step query
# Example: "Search for Python tutorials and email me the top 5"
```

## Key Points

1. **Minimal Change**: Only added 13 lines to the WebSocket handler
2. **Zero Backend Changes**: Backend already worked correctly
3. **Zero UI Changes**: MessageBubble already had rendering logic
4. **Type Safe**: Uses existing Message interface
5. **Secure**: Maintains all validation and sanitization
6. **Bypasses Filter**: Plan handler runs BEFORE empty payload check

## Impact

✅ Users see task breakdown BEFORE execution
✅ Better understanding of complex workflows  
✅ Easier debugging of planning issues
✅ Improved UX for multi-step tasks
