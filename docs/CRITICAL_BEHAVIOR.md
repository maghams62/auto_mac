# CRITICAL BEHAVIORS - DO NOT MODIFY WITHOUT CAREFUL REVIEW

This document describes core behaviors that **MUST NOT** be changed without understanding the full system architecture. These behaviors were carefully designed and any modifications can break the application.

## ⚠️ FOR AI AGENTS & DEVELOPERS

**READ THIS FIRST** before making ANY changes to window visibility, lock/unlock, or opacity-related code.

---

## 1. Window Visibility Lock System

### Overview
The visibility lock prevents the window from being hidden by blur events during async operations (query processing, voice recording, API calls).

### Critical Contract

**RULE**: Every `lockWindow()` call **MUST** have a matching `unlockWindow()` call.

**When to Lock:**
- Before starting query submission
- Before starting voice recording
- Before any async operation that should keep window visible

**When to Unlock:**
- After receiving response (success OR error)
- After stopping voice recording
- On window-hidden event (fail-safe)
- On window-shown event (fail-safe reset)

### All Lock/Unlock Call Sites

#### Main Process (`desktop/src/main.ts`)

**Lock Functions:**
- Line 253-259: `lockWindowVisibility()` - Sets `windowVisibilityLocked = true`
- Line 1206: Called in `showWindow()` - Locks during show process

**Unlock Functions:**
- Line 265-276: `unlockWindowVisibility()` - Sets `windowVisibilityLocked = false`
- Line 359: Called in `startShowGracePeriod()` - Unlocks after grace period

**IPC Handlers:**
- Line 1449-1451: `lock-window` IPC handler
- Line 1453-1455: `unlock-window` IPC handler

#### Frontend (`frontend/app/launcher/page.tsx`)

**Unlock Calls (Fail-Safes):**
- Line 34: On `window-shown` event - **CRITICAL FAIL-SAFE**
- Line 48: On `window-hidden` event - **CRITICAL FAIL-SAFE**

#### Frontend (`frontend/components/CommandPalette.tsx`)

**Lock Calls:**
- Line 170: Voice recording start
- Line 362: Query submission

**Unlock Calls:**
- Line 138: After transcription complete
- Line 164: Voice recording error
- Line 175: Voice recording start error
- Line 298: Status complete/error/cancelled
- Line 308: Assistant response received
- Lines 385, 391, 397, 405, 413, 422, 430, 434: Early returns from routing

### Common Pitfalls

❌ **WRONG:**
```typescript
lockWindow();
await someAsyncOperation();
// Forgot to unlock - window stuck locked!
```

✅ **CORRECT:**
```typescript
lockWindow();
try {
  await someAsyncOperation();
  unlockWindow();
} catch (error) {
  unlockWindow(); // MUST unlock even on error
  throw error;
}
```

❌ **WRONG:**
```typescript
if (condition) {
  unlockWindow();
  return;
}
// More code that might also unlock
unlockWindow(); // Double unlock (harmless but indicates logic error)
```

✅ **CORRECT:**
```typescript
lockWindow();
try {
  if (condition) {
    return; // Early return
  }
  // More logic
} finally {
  unlockWindow(); // Always unlocks
}
```

---

## 2. Window Opacity Management

### Critical Rule: Opacity Order Matters

**RULE**: `setOpacity(1)` **MUST** be called **AFTER** `show()`, not before.

### Why This Matters

On some Electron versions and macOS versions, setting opacity before show() doesn't persist. The window may appear invisible (opacity 0) even though state shows it as visible.

### Correct Implementation

**File**: `desktop/src/main.ts:1240-1241`

```typescript
// CRITICAL: Set opacity AFTER show() for better persistence
mainWindow.show();
mainWindow.setOpacity(1);  // After show(), not before
mainWindow.focus();
```

**DO NOT CHANGE THIS ORDER**

### Fail-Safe

A fail-safe timer (Line 1263-1275) force-corrects opacity to 1 after 300ms if it's somehow < 1. This should never trigger in normal operation - if it does, there's a bug.

### Opacity Rules

1. Window created with `transparent: true` (Line 896)
2. Opacity MUST be explicitly set to 1 when showing
3. Opacity set AFTER show(), not before
4. Opacity should never be < 1 when window is visible
5. Animations must not reset opacity (verify `animateShowWindow()`)

---

## 3. Window Positioning Rules

### Critical Rule: Position on Active Display

**RULE**: Window **MUST** appear on the display where the cursor is located.

### Implementation

**File**: `desktop/src/main.ts:1210-1225`

```typescript
const cursor = screen.getCursorScreenPoint();
const activeDisplay = screen.getDisplayNearestPoint(cursor);
// Center on active display
```

**DO NOT** use `screen.getPrimaryDisplay()` - this breaks multi-monitor setups.

### Why This Matters

Users expect Spotlight-like behavior: press hotkey, window appears WHERE YOU ARE, not on some other monitor.

---

## 4. Grace Period Mechanism

### Overview

The grace period prevents the blur event from hiding the window immediately after showing it. This prevents flicker and race conditions.

### Constants

```typescript
SHOW_GRACE_PERIOD_MS = 250;  // Line 230
TOGGLE_DEBOUNCE_MS = 220;    // Line 231
```

**DO NOT** reduce these values without extensive testing. They were chosen to work across different system speeds.

### How It Works

1. `showWindow()` called → starts grace period (Line 1256)
2. For 250ms, `showGraceActive = true`
3. Blur events check `showGraceActive` (Line 959) and skip hiding
4. After 250ms, grace period ends, normal blur behavior resumes

### Critical Points

- Grace period starts AFTER window is shown
- Blur event has TWO checks: initial (Line 959) and delayed (Line 979)
- Unlock is called when grace period ends (Line 364)

---

## 5. Blur Event Handling

### The Three Guards

**File**: `desktop/src/main.ts:957-988`

Every blur event checks THREE conditions before hiding:

```typescript
if (showGraceActive) return;        // Guard 1: Grace period
if (!hideOnBlur) return;            // Guard 2: User setting
if (windowVisibilityLocked) return; // Guard 3: Lock state
```

**DO NOT** remove any of these guards. They prevent:
1. Immediate hide after show (flicker)
2. Hide when user disabled it
3. Hide during processing

### Delay Before Hide

After passing all guards, there's a 150ms delay before hiding:

```typescript
setTimeout(() => {
  // Final checks, then hide
}, 150);
```

This delay is **CRITICAL** for multi-monitor focus transitions. DO NOT remove it.

---

## 6. Hotkey and Tray Behavior

### Hotkey Registration

**File**: `desktop/src/main.ts:1415-1430`

```typescript
globalShortcut.register(hotkey, () => {
  toggleWindow('globalShortcut');
});
```

**DO NOT**:
- Call `showWindow()` directly from hotkey
- Skip the `toggleWindow()` wrapper
- Remove debouncing logic in `toggleWindow()`

### Toggle Debouncing

**File**: `desktop/src/main.ts:1272-1279`

```typescript
const now = Date.now();
const lastToggle = lastToggleBySource[source] || 0;

if (now - lastToggle < TOGGLE_DEBOUNCE_MS) {
  return; // Debounced
}
```

This prevents:
- Double-firing from key repeat
- Race conditions from multiple triggers
- Flicker from rapid toggle

**DO NOT** remove this debouncing.

---

## 7. macOS-Specific Behavior

### Dock Icon

**File**: `desktop/src/main.ts:1651-1655`

```typescript
if (process.platform === 'darwin') {
  app.dock.hide();
}
```

The dock icon is **ALWAYS** hidden. This is Spotlight-like behavior. DO NOT show it.

### App Activation

**File**: `desktop/src/main.ts:1232-1236`

```typescript
if (process.platform === 'darwin') {
  app.show();
  app.focus({ steal: true });
}
```

On macOS, `app.show()` + `app.focus({steal: true})` is required to bring window to foreground. DO NOT remove either call.

---

## 8. Window Creation Sequence

### The Order Matters

**File**: `desktop/src/main.ts:891-905`

```typescript
mainWindow = new BrowserWindow({
  show: false,           // Start hidden
  transparent: true,     // Allow opacity control
  alwaysOnTop: true,     // Spotlight behavior
  skipTaskbar: true,     // Don't show in taskbar
  // ...
});
```

**Critical Points**:
1. `show: false` - Window starts hidden (Spotlight behavior)
2. `transparent: true` - Required for opacity management
3. `alwaysOnTop: true` - Required for Spotlight UX
4. Window only shows on user trigger (hotkey/tray)

**DO NOT**:
- Set `show: true` on creation
- Remove `transparent: true`
- Remove `alwaysOnTop: true`
- Call `show()` immediately after creation

---

## 9. Frontend Render Blocking

### History Loading Must Not Block Render

**File**: `frontend/components/CommandPalette.tsx:212-221`

```typescript
// CRITICAL: Don't block on historyLoaded - allow window to render
if (!wsConnected || mode !== "launcher") {
  return;
}
// Skip if already loaded
if (historyLoaded) {
  return;
}
```

**RULE**: History loading should NEVER prevent window from displaying.

### Common Mistake

❌ **WRONG:**
```typescript
if (!wsConnected || historyLoaded || mode !== "launcher") {
  return; // Blocks if historyLoaded is false!
}
```

✅ **CORRECT:**
```typescript
if (!wsConnected || mode !== "launcher") {
  return; // Doesn't block on historyLoaded
}
if (historyLoaded) {
  return; // Separate check
}
```

---

## 10. State Machine Invariants

### Window States

```
HIDDEN → SHOWING → VISIBLE → HIDING → HIDDEN
```

### Invariants (MUST always be true)

1. **If visible=true, opacity MUST be 1**
2. **If locked=true, blur MUST NOT hide**
3. **If graceActive=true, blur MUST NOT hide**
4. **Show MUST be followed by unlock (via grace period)**
5. **Hide MUST unlock (via frontend event listener)**

### Checking Invariants

Use the diagnostic tools:

```javascript
// In browser console (DevTools on Electron window)
const state = await window.electronAPI.getWindowState();
console.table({
  'Visible': state.visible,
  'Opacity': mainWindow.getOpacity(), // Should be 1 if visible
  'Locked': state.locked,
  'Grace Active': state.graceActive
});
```

If any invariant is violated, there's a bug.

---

## 11. Emergency Recovery

### Force Window Visible

If window is completely invisible despite all triggers:

```javascript
// In browser console at http://localhost:3000/launcher
await window.electronAPI.forceWindowVisible();
```

This diagnostic function:
1. Shows window
2. Sets opacity to 1
3. Focuses window
4. Unlocks visibility
5. Returns before/after state for debugging

**DO NOT** remove this function - it's critical for debugging production issues.

---

## 12. Testing Required After Changes

If you modify ANY code mentioned in this document, you **MUST** test:

- [ ] Hotkey (⌘ + Option + K) shows window
- [ ] Tray icon click shows window
- [ ] Window is fully opaque (not ghost/transparent)
- [ ] Window hides on blur when unlocked
- [ ] Window stays visible when locked during query
- [ ] Voice recording locks window
- [ ] Rapid hotkey presses are debounced
- [ ] Multi-monitor: window appears on active display
- [ ] Expanded view works
- [ ] No "opacity < 1" warnings in logs

---

## 13. Files Containing Critical Code

| File | Lines | What NOT to Change |
|------|-------|-------------------|
| `desktop/src/main.ts` | 253-276 | Lock/unlock functions |
| `desktop/src/main.ts` | 1239-1243 | Opacity ordering |
| `desktop/src/main.ts` | 1190-1276 | showWindow/toggleWindow |
| `desktop/src/main.ts` | 942-989 | Blur event handler |
| `desktop/src/main.ts` | 1415-1430 | Hotkey registration |
| `desktop/src/main.ts` | 346-364 | Grace period |
| `frontend/app/launcher/page.tsx` | 28-61 | Window event handlers |
| `frontend/components/CommandPalette.tsx` | 362 | Lock on submit |
| `frontend/components/CommandPalette.tsx` | 212-221 | History non-blocking |

---

## Summary

**The Golden Rules:**
1. ✅ Every lock has an unlock (including error paths)
2. ✅ Opacity set AFTER show(), not before
3. ✅ Position on active display, not primary
4. ✅ Three blur guards: grace, setting, lock
5. ✅ Debounce all toggles
6. ✅ History never blocks render
7. ✅ Test everything after changes

**When in Doubt:**
- Read this document
- Check the logs
- Use `forceWindowVisible()` to diagnose
- Ask before modifying critical sections

---

**Last Updated**: 2025-11-28
**Reason for Creation**: Multiple AI agents broke window visibility during Spotify/history feature additions
