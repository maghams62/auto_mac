# Spotify Mini Player & Conversation Memory Implementation Plan

## Current Status

### Spotify Player
✅ **Web UI**: SpotifyPlayer component exists and works in browser ([frontend/components/SpotifyPlayer.tsx](frontend/components/SpotifyPlayer.tsx))
✅ **Mini Player Component**: SpotifyMiniPlayer exists with multiple variants ([frontend/components/SpotifyMiniPlayer.tsx](frontend/components/SpotifyMiniPlayer.tsx))
✅ **Electron Integration**: Player is referenced in ClientLayout but NOT visible in launcher mode
❌ **Electron Visibility**: Player is NOT showing in the Electron app launcher window

### Conversation Memory
❌ **No Persistence**: Conversations are lost when closing the web view
✅ **Session Manager Exists**: Backend has SessionManager ([src/memory/__init__.py](src/memory/__init__.py))
❌ **History Not Retrieved**: Frontend doesn't load previous conversations on mount

---

## Part 1: Spotify Mini Player in Electron

### Problem Analysis

1. **Current Implementation** ([ClientLayout.tsx:136-146](frontend/app/ClientLayout.tsx#L136-L146)):
   ```tsx
   {isElectron() && !isCommandPaletteOpen && (
     <div className="fixed bottom-0 left-0 right-0 z-40">
       <SpotifyMiniPlayer variant="launcher" onAction={() => {}} />
     </div>
   )}
   ```
   - This shows SpotifyMiniPlayer ONLY when `!isCommandPaletteOpen`
   - The launcher mode ALWAYS has CommandPalette open
   - **Result**: Player never renders in launcher mode!

2. **SpotifyMiniPlayer Variants** ([SpotifyMiniPlayer.tsx](frontend/components/SpotifyMiniPlayer.tsx)):
   - `launcher`: Compact bar at bottom (lines 650-716)
   - `launcher-footer`: Embedded at bottom (lines 525-581)
   - `launcher-full`: Larger with time display (lines 416-522)
   - `launcher-expanded`: Large centered artwork (lines 211-413)

### Solution Design

#### Option A: Integrate into CommandPalette (Recommended for Raycast-like UI)
Embed the Spotify mini player **inside** the CommandPalette component as a footer, similar to how Raycast shows controls at the bottom of the launcher window.

**Pros**:
- Matches Raycast UX pattern
- Always visible when launcher is open
- Clean integration
- No z-index conflicts

**Cons**:
- Requires modifying CommandPalette component

#### Option B: Separate Fixed Footer (Alternative)
Render the Spotify player outside CommandPalette with proper z-index layering.

**Pros**:
- Simpler to implement
- Player stays even when palette closes

**Cons**:
- May have positioning conflicts
- Less integrated feel

### Recommended Implementation: Option A

#### Step 1: Modify CommandPalette to Include Spotify Footer
**File**: [frontend/components/CommandPalette.tsx](frontend/components/CommandPalette.tsx)

Add SpotifyMiniPlayer at the bottom of the launcher modal:

```tsx
// Add import at top
import SpotifyMiniPlayer from "@/components/SpotifyMiniPlayer";

// Inside the modal div (around line 800-900), add footer before closing </motion.div>:
{mode === "launcher" && (
  <div className="border-t border-glass/30">
    <SpotifyMiniPlayer
      variant="launcher-footer"
      onAction={() => {
        // Keep window open during Spotify interaction
      }}
    />
  </div>
)}
```

#### Step 2: Update ClientLayout to Remove Duplicate Player
**File**: [frontend/app/ClientLayout.tsx](frontend/app/ClientLayout.tsx)

Remove the conditional Spotify player (lines 135-146) since it's now inside CommandPalette:

```tsx
// DELETE THIS BLOCK:
{/* Spotify mini-player (Electron only) */}
{isElectron() && !isCommandPaletteOpen && (
  <div className="fixed bottom-0 left-0 right-0 z-40">
    <SpotifyMiniPlayer
      variant="launcher"
      onAction={() => {}}
    />
  </div>
)}
```

#### Step 3: Adjust CommandPalette Layout
**File**: [frontend/components/CommandPalette.tsx](frontend/components/CommandPalette.tsx)

Ensure the Spotify footer doesn't overlap with results:

```tsx
// Adjust results container max-height to account for Spotify footer
// Find the results list div and update max-height calculation
className="overflow-y-auto max-h-[calc(100%-220px)]" // Adjust based on Spotify player height
```

#### Step 4: Style the Spotify Footer
The `launcher-footer` variant already exists and is perfect for this use case:
- Compact height (~64px)
- Album art thumbnail
- Track info
- Play/pause/next/previous controls
- Progress bar

**No additional styling needed** - variant is already optimized!

---

## Part 2: Conversation Memory Persistence

### Problem Analysis

1. **Backend**:
   - ✅ SessionManager exists and stores conversations ([src/memory/__init__.py](src/memory/__init__.py))
   - ✅ Conversations are logged to trajectories ([data/trajectories/](data/trajectories/))
   - ✅ WebSocket sends messages to frontend

2. **Frontend**:
   - ❌ CommandPalette doesn't load conversation history on mount
   - ❌ No API endpoint called to retrieve previous messages
   - ❌ Messages list starts empty every time

### Solution Design

#### Architecture Overview

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  Frontend   │ ◄─────► │  Backend    │ ◄─────► │  Storage    │
│             │         │ (FastAPI)   │         │ (JSONL)     │
│ CommandP... │         │             │         │             │
│             │   GET   │ /history    │  READ   │ sessions/   │
│ • Loads     │ ───────►│ endpoint    │ ───────►│ {id}.jsonl  │
│   history   │         │             │         │             │
│   on mount  │         │ Returns     │         │             │
│             │ ◄───────│ messages[]  │         │             │
└─────────────┘         └─────────────┘         └─────────────┘
```

### Implementation Steps

#### Step 1: Add Backend API Endpoint for History Retrieval
**File**: [api_server.py](api_server.py)

Add new endpoint after existing routes:

```python
# Conversation History Models
class ConversationMessage(BaseModel):
    role: str  # 'user' | 'assistant' | 'system'
    content: str
    timestamp: Optional[str] = None
    message_id: Optional[str] = None

class ConversationHistoryResponse(BaseModel):
    session_id: str
    messages: List[ConversationMessage]
    total_messages: int

@app.get("/api/conversation/history/{session_id}", response_model=ConversationHistoryResponse)
async def get_conversation_history(session_id: str, limit: int = 100):
    """
    Retrieve conversation history for a given session.
    Returns the most recent messages in chronological order.
    """
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("get_conversation_history") as span:
        span.set_attribute("session_id", session_id)
        span.set_attribute("limit", limit)

        try:
            # Get session from SessionManager
            session = session_manager.get_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

            # Get conversation history from session
            history = session.get_conversation_history(limit=limit)

            # Convert to API format
            messages = []
            for msg in history:
                messages.append(ConversationMessage(
                    role=msg.get("role", "assistant"),
                    content=msg.get("content", ""),
                    timestamp=msg.get("timestamp"),
                    message_id=msg.get("message_id")
                ))

            span.set_attribute("messages_count", len(messages))
            logger.info(f"Retrieved {len(messages)} messages for session {session_id}")

            return ConversationHistoryResponse(
                session_id=session_id,
                messages=messages,
                total_messages=len(messages)
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}", exc_info=True)
            set_span_error(span, e)
            raise HTTPException(status_code=500, detail=str(e))
```

#### Step 2: Add Session Storage Method (if not exists)
**File**: [src/memory/__init__.py](src/memory/__init__.py)

Ensure SessionManager has a method to retrieve conversation history:

```python
def get_conversation_history(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Retrieve conversation history for a session.
    Returns messages in chronological order (oldest first).
    """
    session = self.get_session(session_id)
    if not session:
        return []

    # Get messages from conversation history
    history = session.conversation_history[-limit:] if session.conversation_history else []

    return history
```

#### Step 3: Update Session Model to Include get_conversation_history
**File**: [src/memory/__init__.py](src/memory/__init__.py)

Add method to Session class:

```python
class Session:
    def get_conversation_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent conversation history."""
        return self.conversation_history[-limit:] if self.conversation_history else []
```

#### Step 4: Frontend - Load History on Mount
**File**: [frontend/components/CommandPalette.tsx](frontend/components/CommandPalette.tsx)

Add history loading in the WebSocket connection logic:

```tsx
// Add state for history loading
const [historyLoaded, setHistoryLoaded] = useState(false);

// Add function to load history
const loadConversationHistory = useCallback(async (sessionId: string) => {
  try {
    logger.info('[HISTORY] Loading conversation history', { sessionId });
    const response = await fetch(`${baseUrl}/api/conversation/history/${sessionId}`);

    if (!response.ok) {
      throw new Error(`Failed to load history: ${response.status}`);
    }

    const data = await response.json();
    logger.info('[HISTORY] Loaded messages', { count: data.messages.length });

    // Add messages to chat history
    if (data.messages && data.messages.length > 0) {
      // Convert backend format to frontend Message format
      const historicalMessages: Message[] = data.messages.map((msg: any) => ({
        id: msg.message_id || `hist-${Date.now()}-${Math.random()}`,
        type: msg.role === 'user' ? 'user_message' : 'assistant_message',
        content: msg.content,
        timestamp: msg.timestamp || new Date().toISOString()
      }));

      // Prepend historical messages to chat
      setMessages(prev => [...historicalMessages, ...prev]);
      setHistoryLoaded(true);
    }
  } catch (error) {
    logger.error('[HISTORY] Failed to load conversation history', { error });
    // Don't throw - gracefully continue without history
  }
}, [baseUrl]);

// In the WebSocket connection useEffect, load history after connection
useEffect(() => {
  if (!isOpen || mode !== "launcher") return;

  // ... existing WebSocket connection code ...

  // After WebSocket connects successfully, load history
  if (socket && !historyLoaded) {
    loadConversationHistory(sessionId);
  }
}, [isOpen, mode, sessionId, historyLoaded, loadConversationHistory]);
```

#### Step 5: Prevent Duplicate History Loading
**File**: [frontend/components/CommandPalette.tsx](frontend/components/CommandPalette.tsx)

Add guard to prevent re-loading history:

```tsx
// Reset history loaded flag when session changes
useEffect(() => {
  setHistoryLoaded(false);
  setMessages([]); // Clear messages on session change
}, [sessionId]);
```

#### Step 6: Add Clear History Button (Optional)
**File**: [frontend/components/CommandPalette.tsx](frontend/components/CommandPalette.tsx)

Add button to clear conversation and start fresh:

```tsx
// In the launcher header, add a clear button
<button
  onClick={() => {
    setMessages([]);
    setHistoryLoaded(false);
    // Optionally notify backend to clear session
  }}
  className="text-muted hover:text-text-primary"
  title="Clear conversation"
>
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
  </svg>
</button>
```

---

## Testing Plan

### Spotify Player Testing

1. **Launch Electron App**
   ```bash
   cd desktop
   npm run dev
   ```

2. **Verify Player Visibility**
   - Press `Cmd+Option+K` to open launcher
   - **Expected**: Spotify player visible at bottom of launcher window
   - **Expected**: Album art, track info, and controls displayed

3. **Test Controls**
   - Click play/pause button
   - **Expected**: Music starts/stops playing
   - Click next/previous
   - **Expected**: Track changes

4. **Test Collapsed State**
   - Click collapse button (if using launcher-expanded variant)
   - **Expected**: Player collapses to mini bar

### Conversation Memory Testing

1. **Start Conversation**
   - Open launcher
   - Send message: "Hello, how are you?"
   - **Expected**: Assistant responds

2. **Close and Reopen**
   - Close launcher window
   - Reopen launcher
   - **Expected**: Previous "Hello, how are you?" message visible in history

3. **Continue Conversation**
   - Send follow-up: "Tell me a joke"
   - **Expected**: Assistant responds with context from previous message

4. **Verify Backend Storage**
   - Check `data/sessions/{session_id}.jsonl`
   - **Expected**: All messages logged

---

## File Summary

### Files to Modify

1. **[frontend/components/CommandPalette.tsx](frontend/components/CommandPalette.tsx)**
   - Add SpotifyMiniPlayer import
   - Add Spotify footer in launcher mode
   - Add conversation history loading
   - Adjust layout for player height

2. **[frontend/app/ClientLayout.tsx](frontend/app/ClientLayout.tsx)**
   - Remove duplicate Spotify player rendering

3. **[api_server.py](api_server.py)**
   - Add `/api/conversation/history/{session_id}` endpoint
   - Add ConversationMessage and ConversationHistoryResponse models

4. **[src/memory/__init__.py](src/memory/__init__.py)** (if needed)
   - Add `get_conversation_history` method to Session class
   - Add `get_conversation_history` method to SessionManager class

### Files to Create

None - all modifications to existing files.

---

## Implementation Priority

### Phase 1: Spotify Player (High Priority)
1. Modify CommandPalette to include Spotify footer
2. Remove duplicate player from ClientLayout
3. Test in Electron app

### Phase 2: Conversation Memory (High Priority)
1. Add backend API endpoint for history retrieval
2. Add history loading in CommandPalette
3. Test persistence across sessions

### Phase 3: Polish (Medium Priority)
1. Add clear conversation button
2. Add loading states for history
3. Handle edge cases (no history, failed loads, etc.)

---

## Visual Reference

### Spotify Player in Launcher
Based on Raycast's design pattern:

```
┌────────────────────────────────────────┐
│  Cerebros Launcher                  [x]│
├────────────────────────────────────────┤
│  Search or ask anything...             │
│                                        │
│  [Results or conversation here]        │
│                                        │
│                                        │
├────────────────────────────────────────┤
│  🎵 [Album]  Song Name         ⏮ ⏸ ⏭  │
│              Artist Name                │
│              ─────●────────── 2:30      │
└────────────────────────────────────────┘
```

### Conversation Persistence Flow
```
Session 1:
User: "Hello"
Assistant: "Hi there!"

[Window closes]

[Window reopens with same session ID]

Session 1 (continued):
User: "Hello"              ← Loaded from history
Assistant: "Hi there!"     ← Loaded from history
User: "Tell me a joke"     ← New message
Assistant: "Why did..."    ← New response
```

---

## References

### Raycast Spotify Player Patterns
- [Raycast Store: Spotify Player](https://www.raycast.com/mattisssa/spotify-player)
- [Spotify Controls | Raycast API](https://developers.raycast.com/examples/spotify-controls)
- [Raycast Store: Spotify Controls](https://www.raycast.com/thomas/spotify-controls)

### Implementation Inspiration
- Spotify mini player should be **always visible** in launcher mode
- Controls should be **keyboard accessible** (Space for play/pause, Cmd+Left/Right for prev/next)
- Design should be **minimal and clean**, matching the Raycast aesthetic

---

## Next Steps

1. Review this plan
2. Confirm architecture decisions (Option A vs Option B for Spotify)
3. Begin implementation starting with Spotify player
4. Test thoroughly in Electron environment
5. Implement conversation memory
6. Deploy and gather user feedback

---

**Created**: 2025-11-27
**Status**: Ready for Implementation
**Priority**: High (Both Features)
