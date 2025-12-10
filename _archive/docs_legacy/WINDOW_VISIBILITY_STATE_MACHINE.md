# Window Visibility State Machine

This document describes the complete state machine for the Cerebros launcher window visibility system.

---

## State Diagram

```
                    ┌─────────────────────┐
                    │                     │
                    │      HIDDEN         │ ← Initial State
                    │                     │
                    │  visible: false     │
                    │  locked: false      │
                    │  graceActive: false │
                    │  opacity: 0         │
                    └─────────────────────┘
                              │
                              │ Trigger: Hotkey/Tray/IPC
                              │ Action: toggleWindow()
                              ↓
                    ┌─────────────────────┐
                    │                     │
                    │     SHOWING         │
                    │                     │
                    │  visible: false→true│
                    │  locked: true       │ ← Locked during transition
                    │  graceActive: false │
                    │  opacity: 0→1       │
                    └─────────────────────┘
                              │
                              │ Duration: ~50-100ms
                              │ Actions: show(), setOpacity(1), focus()
                              ↓
                    ┌─────────────────────┐
                    │                     │
                    │      VISIBLE        │
                    │                     │
                    │  visible: true      │
                    │  locked: false*     │ ← *Can be locked during processing
                    │  graceActive: true  │ ← For 250ms grace period
                    │  opacity: 1         │
                    └─────────────────────┘
                         │           │
              User Click │           │ Query/Voice/Processing
              Away       │           │ → lock()
                         │           ↓
                         │    ┌─────────────────────┐
                         │    │                     │
                         │    │  VISIBLE (Locked)   │
                         │    │                     │
                         │    │  visible: true      │
                         │    │  locked: true       │ ← Blur cannot hide
                         │    │  graceActive: false │
                         │    │  opacity: 1         │
                         │    └─────────────────────┘
                         │             │
                         │             │ Response received
                         │             │ → unlock()
                         │             ↓
                         │    ┌─────────────────────┐
                         │    │                     │
                         │    │  VISIBLE (Unlocked) │
                         │    │                     │
                         │    │  visible: true      │
                         │    │  locked: false      │
                         │    │  graceActive: false │
                         │    │  opacity: 1         │
                         │    └─────────────────────┘
                         │             │
                         └─────────────┘
                              │
                              │ Trigger: Blur event (if unlocked)
                              │ Action: hideLauncherWindow()
                              ↓
                    ┌─────────────────────┐
                    │                     │
                    │      HIDING         │
                    │                     │
                    │  visible: true→false│
                    │  locked: false      │
                    │  graceActive: false │
                    │  opacity: 1→0       │
                    └─────────────────────┘
                              │
                              │ Duration: ~120ms (animation)
                              │ Action: hide()
                              ↓
                    ┌─────────────────────┐
                    │                     │
                    │      HIDDEN         │
                    │                     │
                    └─────────────────────┘
```

---

## State Definitions

### HIDDEN

**Description**: Window is not visible, waiting for user trigger.

**Properties**:
- `visible`: `false`
- `locked`: `false`
- `graceActive`: `false`
- `opacity`: 0 (or N/A since not shown)

**Valid Transitions**:
- → `SHOWING` (via hotkey, tray click, IPC show)

**Actions in This State**:
- Window not rendered/shown
- No blur events (window has no focus)
- Idle CPU usage

---

### SHOWING

**Description**: Transition state while window is being positioned and shown.

**Properties**:
- `visible`: `false` → `true` (during transition)
- `locked`: `true` (prevents premature blur)
- `graceActive`: `false` (grace starts AFTER showing)
- `opacity`: 0 → 1 (critical: set AFTER show())

**Duration**: ~50-100ms

**Actions**:
1. `lockWindowVisibility()` (Line 1206 in main.ts)
2. Position on active display (Lines 1210-1225)
3. `mainWindow.show()` (Line 1240)
4. `mainWindow.setOpacity(1)` (Line 1241) ← **After show()**
5. `mainWindow.focus()` (Line 1242)
6. `animateShowWindow()` (Line 1243)
7. `startShowGracePeriod()` (Line 1256)
8. Send `window-shown` IPC (Line 1259)

**Valid Transitions**:
- → `VISIBLE` (automatic after show completes)

**Critical Point**: Opacity MUST be set after show(), not before.

---

### VISIBLE

**Description**: Window is shown and can receive input. Can be in locked or unlocked sub-state.

**Sub-States**:

#### VISIBLE (Unlocked) - Default

**Properties**:
- `visible`: `true`
- `locked`: `false`
- `graceActive`: `true` (for first 250ms), then `false`
- `opacity`: 1

**Actions**:
- User can type in input
- Blur events CAN hide (after grace period, if hideOnBlur enabled)
- Frontend focused on input field

**Valid Transitions**:
- → `VISIBLE (Locked)` (via query submission, voice recording)
- → `HIDING` (via blur event, ESC key, hide IPC)

#### VISIBLE (Locked) - During Processing

**Properties**:
- `visible`: `true`
- `locked`: `true`
- `graceActive`: `false`
- `opacity`: 1

**Actions**:
- Processing query/voice/command
- Blur events CANNOT hide (blocked by lock)
- Showing loading spinner or response stream

**Valid Transitions**:
- → `VISIBLE (Unlocked)` (via unlock after processing completes)
- → `HIDING` (only via explicit hide IPC, ESC key - NOT via blur)

**Lock Triggers**:
- Query submission (CommandPalette.tsx:362)
- Voice recording start (CommandPalette.tsx:170)
- Any async operation requiring visible window

**Unlock Triggers**:
- Response received (CommandPalette.tsx:298, 308)
- Voice recording stop (CommandPalette.tsx:138)
- Error in processing (CommandPalette.tsx:164, 175)
- Window hidden event (launcher/page.tsx:48)
- Window shown event (launcher/page.tsx:34) ← Fail-safe

---

### HIDING

**Description**: Transition state while window is being hidden with animation.

**Properties**:
- `visible`: `true` → `false` (during transition)
- `locked`: `false` (should always be unlocked when hiding)
- `graceActive`: `false`
- `opacity`: 1 → 0 (fade animation)

**Duration**: ~120ms (`WINDOW_FADE_DURATION_MS`)

**Actions**:
1. `animateHideWindow()` (Line 399 in main.ts)
2. `mainWindow.hide()` (Line 406)
3. Send `window-hidden` IPC (Line 409)

**Valid Transitions**:
- → `HIDDEN` (automatic after hide completes)

**Critical Point**: Always unlock when hiding (done via `window-hidden` event handler in frontend).

---

## State Invariants

These conditions MUST ALWAYS be true:

### Invariant 1: Visibility-Opacity Consistency
```
IF visible === true THEN opacity === 1
IF visible === false THEN opacity === 0 (or undefined)
```

**Violation Symptom**: Window appears invisible despite state showing visible.

**Fix**: Run `forceWindowVisible()` to correct.

### Invariant 2: Lock Prevents Blur
```
IF locked === true AND blur event occurs THEN window MUST NOT hide
```

**Violation Symptom**: Window hides during processing.

**Fix**: Check blur event handler (main.ts:972).

### Invariant 3: Grace Prevents Blur
```
IF graceActive === true AND blur event occurs THEN window MUST NOT hide
```

**Violation Symptom**: Window flickers after showing.

**Fix**: Check grace period duration (230ms constant).

### Invariant 4: Lock/Unlock Symmetry
```
FOR EACH lockWindow() call THERE EXISTS EXACTLY ONE unlockWindow() call
```

**Violation Symptom**: Window stuck in locked state.

**Fix**: Add `unlockWindow()` to error paths and cleanup handlers.

### Invariant 5: Position on Active Display
```
IF window shown THEN window.bounds MUST be on display with cursor
```

**Violation Symptom**: Window appears on wrong monitor.

**Fix**: Check `showWindow()` positioning logic (main.ts:1210-1225).

---

## Transition Triggers

### User Triggers

| Trigger | Source | Function Called | State Transition |
|---------|--------|-----------------|------------------|
| Hotkey (⌘+Option+K) | Global shortcut | `toggleWindow('globalShortcut')` | HIDDEN → SHOWING or VISIBLE → HIDING |
| Tray Click | Tray menu | `toggleWindow('tray')` | HIDDEN → SHOWING or VISIBLE → HIDING |
| ESC Key | Frontend keyboard | `hideWindow()` IPC | VISIBLE → HIDING |
| Click Away | Window blur event | `hideLauncherWindow('blur')` | VISIBLE (Unlocked) → HIDING |

### Programmatic Triggers

| Trigger | Source | Function Called | State Transition |
|---------|--------|-----------------|------------------|
| Query Submit | Frontend | `lockWindow()` IPC | VISIBLE (Unlocked) → VISIBLE (Locked) |
| Response Received | Frontend | `unlockWindow()` IPC | VISIBLE (Locked) → VISIBLE (Unlocked) |
| Voice Start | Frontend | `lockWindow()` IPC | VISIBLE (Unlocked) → VISIBLE (Locked) |
| Voice Stop | Frontend | `unlockWindow()` IPC | VISIBLE (Locked) → VISIBLE (Unlocked) |
| Window Shown Event | Electron | Frontend handler | Sets unlocked (fail-safe) |
| Window Hidden Event | Electron | Frontend handler | Sets unlocked (fail-safe) |

---

## Timing Constants

| Constant | Value | Purpose | File:Line |
|----------|-------|---------|-----------|
| `SHOW_GRACE_PERIOD_MS` | 250ms | Prevent blur immediately after show | main.ts:230 |
| `TOGGLE_DEBOUNCE_MS` | 220ms | Prevent double hotkey firing | main.ts:231 |
| `WINDOW_FADE_DURATION_MS` | 120ms | Hide animation duration | main.ts:232 |
| Blur delay | 150ms | Delay before blur hides window | main.ts:977 |
| Opacity fail-safe | 300ms | Force opacity=1 if < 1 | main.ts:1263 |

**DO NOT** modify these values without extensive testing across different system speeds.

---

## Recovery Procedures

### Window Invisible (State says visible=true)

**Diagnosis**:
```javascript
const state = await window.electronAPI.getWindowState();
console.log('Visible:', state.visible);  // true
console.log('Opacity:', /* check via IPC */);  // Likely 0
```

**Recovery**:
```javascript
await window.electronAPI.forceWindowVisible();
```

**Root Cause**: Opacity set before show(), or animation reset opacity.

**Permanent Fix**: Ensure opacity set AFTER show() (main.ts:1241).

---

### Window Stuck Locked

**Diagnosis**:
```javascript
const state = await window.electronAPI.getWindowState();
console.log('Locked:', state.locked);  // true (should be false when idle)
```

**Symptoms**:
- Window doesn't hide on blur
- Blur events logged but no hide action

**Recovery**:
```javascript
window.electronAPI.unlockWindow();
```

**Root Cause**: Missing `unlockWindow()` in error path or cleanup.

**Permanent Fix**: Add unlock to all error handlers and window-hidden event.

---

### Window Flickers After Show

**Diagnosis**:
- Window appears for <100ms then disappears
- Logs show: show event → blur event → hide

**Root Cause**: Grace period too short or blur event firing immediately.

**Recovery**: Increase `SHOW_GRACE_PERIOD_MS` from 250ms to 500ms temporarily.

**Permanent Fix**:
1. Check no code calls `hide()` directly after `show()`
2. Verify grace period starts (Line 1256)
3. Verify blur checks grace (Line 959)

---

### Window Appears on Wrong Monitor

**Diagnosis**:
- User on Monitor B, presses hotkey
- Window appears on Monitor A

**Root Cause**: Using `screen.getPrimaryDisplay()` instead of cursor position.

**Fix**: Verify showWindow() uses `screen.getDisplayNearestPoint(cursor)` (Line 1215).

---

## Event Flow Example

### Scenario: User Submits Query

```
1. [VISIBLE (Unlocked)] User types query
2. [VISIBLE (Unlocked)] User presses Enter
3. → Frontend: handleSubmitQuery() called
4. → Frontend: lockWindow() called (Line 362)
5. [VISIBLE (Locked)] State transitions to locked
6. → Main: IPC 'lock-window' received
7. → Main: lockWindowVisibility() called
8. → Main: windowVisibilityLocked = true
9. [VISIBLE (Locked)] User clicks away
10. → Main: blur event fires
11. → Main: Check if locked (Line 972) - YES
12. → Main: Skip hide (locked)
13. [VISIBLE (Locked)] Still visible, processing
14. → Backend: Response sent via WebSocket
15. → Frontend: Response received in useWebSocket
16. → Frontend: unlockWindow() called (Line 308)
17. [VISIBLE (Unlocked)] State transitions to unlocked
18. → Main: IPC 'unlock-window' received
19. → Main: unlockWindowVisibility() called
20. → Main: windowVisibilityLocked = false
21. [VISIBLE (Unlocked)] User clicks away again
22. → Main: blur event fires
23. → Main: Check if locked (Line 972) - NO
24. → Main: Check grace active (Line 959) - NO
25. → Main: Check hideOnBlur (Line 966) - YES
26. → Main: setTimeout 150ms
27. → Main: hideLauncherWindow('blur') called
28. [HIDING] Window fades out
29. → Main: hide() called after animation
30. [HIDDEN] Window hidden, ready for next trigger
```

---

## Debugging State Issues

### Log State Transitions

Add to showWindow(), hideLauncherWindow(), lock/unlock:

```typescript
const state = getWindowState();
log.info('[STATE] Transitioning', {
  from: previousState,
  to: newState,
  visible: state.visible,
  locked: state.locked,
  graceActive: state.graceActive
});
```

### Monitor State in Real-Time

```javascript
// In browser console
setInterval(async () => {
  const state = await window.electronAPI.getWindowState();
  console.table({
    'Visible': state.visible,
    'Locked': state.locked,
    'Grace': state.graceActive,
    'Show Count': state.showCount,
    'Hide Count': state.hideCount,
    'Blur Count': state.blurCount
  });
}, 1000);
```

### Check Invariants

```javascript
async function checkInvariants() {
  const state = await window.electronAPI.getWindowState();
  const violations = [];

  // Invariant 1: visible implies opacity=1
  if (state.visible && /* opacity < 1 */) {
    violations.push('Opacity < 1 while visible');
  }

  // Invariant 2: locked prevents hide
  if (state.locked && !state.visible) {
    violations.push('Window hidden while locked');
  }

  // More checks...

  if (violations.length > 0) {
    console.error('INVARIANT VIOLATIONS:', violations);
  } else {
    console.log('✅ All invariants satisfied');
  }
}
```

---

## Testing State Machine

### Manual Test Cases

1. **Show/Hide Cycle**
   - Press hotkey → window shows → click away → window hides → ✅

2. **Lock During Query**
   - Show window → type query → press Enter → click away → window stays → wait for response → click away → window hides → ✅

3. **Grace Period**
   - Press hotkey → immediately click away → window stays for 250ms → then hides → ✅

4. **Multi-Monitor**
   - Move cursor to Monitor B → press hotkey → window appears on Monitor B → ✅

5. **Rapid Toggle**
   - Press hotkey 5x rapidly → window toggles but stabilizes → no flicker → ✅

### Automated Checks

See `CRITICAL_BEHAVIOR.md` Section 12 for complete testing checklist.

---

**Last Updated**: 2025-11-28
**Related Documentation**: `CRITICAL_BEHAVIOR.md`, `docs/README.md`
