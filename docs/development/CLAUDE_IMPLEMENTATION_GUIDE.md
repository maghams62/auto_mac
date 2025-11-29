# Claude Implementation Guide – Cerebros Launcher Improvements

**Purpose:** Structured reasoning and implementation guidance for Claude to execute the P0/P1 improvements identified in `CEREBROS_GAP_ANALYSIS.md`.

> **Subsystem context files:** When implementing slash agents, load the relevant context file from `agents/<subsystem>/context.md`. For Slack-specific work, point Claude Code at `agents/slash_slack/context.md` (do not inline its full contents in the system prompt; reference it or summarize key sections instead).

---

## Executive Summary

Cerebros has a solid foundation but the **frontend doesn't surface what the backend already provides**. The four priority improvements are:

| Priority | Feature | Current State | Effort |
|----------|---------|---------------|--------|
| **P0** | Unified Command Palette | `/api/commands` exists, UI shows files only | 2h |
| **P0** | "Open App" Command | IPC handler exists, no UI trigger | 1h |
| **P1** | Quick Calculator | Not implemented | 1h |
| **P1** | Settings UI | Backend ready, no modal | 3h |

---

## 1. File & Entry Point Map

### Feature 1: Unified Command Palette (P0)

| File | Role | Action Needed |
|------|------|---------------|
| `frontend/components/CommandPalette.tsx` | Main palette component | **Already fetching commands** (line 569-585), but needs to display them prominently alongside files |
| `api_server.py` | Backend `/api/commands` endpoint | Already returns 20+ agents with metadata (line 1573-1656) |
| `frontend/lib/useCommandRouter.ts` | Deterministic command routing | May need new patterns for system commands |

**Key Observations:**
- Commands ARE being fetched (line 569-585)
- Commands ARE being filtered (line 610-637)
- Commands ARE in `allItems` (line 640-652)
- The UI renders them but they may be getting buried under file results

**What's Missing:**
- No visual "Actions" section header separating commands from files
- When user types, file results may be overshadowing command results
- Need better command execution for `system_open_app` type

---

### Feature 2: "Open App" Command (P0)

| File | Role | Action Needed |
|------|------|---------------|
| `desktop/src/main.ts` | Electron main process | IPC handler `'open-app'` exists (line 1235-1244) |
| `desktop/src/preload.ts` | IPC bridge | `openApp()` exposed (line 48-60) |
| `frontend/types/electron.d.ts` | TypeScript types | `openApp` typed (line 42) |
| `frontend/lib/useCommandRouter.ts` | Deterministic routing | **ADD pattern for "open X"** |
| `api_server.py` | Backend | **ADD system commands to `/api/commands`** |

**What Exists:**
```typescript
// desktop/src/preload.ts (line 48-60)
openApp: (appName: string) => {
  return new Promise((resolve, reject) => {
    ipcRenderer.send('open-app', appName);
    ipcRenderer.once('open-app-result', (event, result) => {
      if (result.success) resolve(result);
      else reject(new Error(result.error));
    });
  });
}
```

**What's Missing:**
1. No pattern in `useCommandRouter.ts` to detect "open safari" etc.
2. No system commands in `/api/commands` response
3. No handler in `CommandPalette.tsx` for `handler_type === "system_open_app"`

---

### Feature 3: Quick Calculator (P1)

| File | Role | Action Needed |
|------|------|---------------|
| `frontend/components/CommandPalette.tsx` | Palette component | **ADD math detection and inline result display** |
| `frontend/lib/useCalculator.ts` | (NEW) Calculator hook | Create utility for safe eval |

**Implementation Location:**
- Insert before the results section in `CommandPalette.tsx`
- Should trigger when query matches `/^[\d\s+\-*/().%^]+$/`
- Display result inline, copy to clipboard on Enter

---

### Feature 4: Settings UI (P1)

| File | Role | Action Needed |
|------|------|---------------|
| `frontend/components/SettingsModal.tsx` | (NEW) Settings modal | Create preferences UI |
| `frontend/components/CommandPalette.tsx` | Palette component | Add trigger for "settings" or "preferences" |
| `desktop/src/preload.ts` | IPC bridge | `getSettings()` and `updateSettings()` already exist (line 100-114) |
| `desktop/src/main.ts` | Electron main | IPC handlers exist (line 1247-1296) |
| `frontend/types/electron.d.ts` | TypeScript types | `Settings` interface exists (line 6-11) |

**What Exists:**
```typescript
// frontend/types/electron.d.ts
export interface Settings {
  hotkey: string;
  hideOnBlur: boolean;
  startAtLogin: boolean;
  theme: 'dark' | 'light' | 'auto';
}

// Preload exposes:
getSettings: () => Promise<Settings>;
updateSettings: (settings: Partial<Settings>) => Promise<{ success: boolean }>;
```

**What's Missing:**
- No `SettingsModal.tsx` component
- No trigger in CommandPalette to open settings
- No `/settings` slash command

---

## 2. Implementation Guidance

### 2.1 Unified Command Palette (P0)

**Goal:** When user types, show both matching "Actions" and "Files" in distinct sections.

**Step 1: Add visual section headers**

In `CommandPalette.tsx`, modify the render to show clear sections:

```tsx
// Around line 800-900, in the results rendering section

{/* Actions Section */}
{filteredCommands.length > 0 && (
  <div className="mb-2">
    <div className="px-4 py-1 text-xs font-medium text-white/40 uppercase tracking-wide">
      Actions
    </div>
    {filteredCommands.slice(0, 5).map((cmd, idx) => (
      <CommandItem
        key={cmd.id}
        command={cmd}
        isSelected={selectedIndex === idx}
        onSelect={() => handleExecuteCommand(cmd)}
      />
    ))}
  </div>
)}

{/* Files Section */}
{results.length > 0 && (
  <div>
    <div className="px-4 py-1 text-xs font-medium text-white/40 uppercase tracking-wide">
      Files
    </div>
    {results.map((result, idx) => (
      <SearchResultItem
        key={result.file_path}
        result={result}
        isSelected={selectedIndex === filteredCommands.length + idx}
        onSelect={() => handleSelectResult(result)}
      />
    ))}
  </div>
)}
```

**Step 2: Ensure commands appear first when relevant**

The current `filteredCommands` logic (line 610-637) is good. Verify it prioritizes exact matches.

---

### 2.2 "Open App" Command (P0)

**Goal:** User types "open safari" → Safari launches.

**Step 1: Add pattern to useCommandRouter.ts**

```typescript
// In frontend/lib/useCommandRouter.ts, add to commandPatterns array:

{
  patterns: [
    /^open\s+(.+)$/i,
    /^launch\s+(.+)$/i,
    /^start\s+(.+)$/i,
  ],
  action: "open_app",
  handler: async (input: string, ctx: CommandRouterContext) => {
    const match = input.match(/^(?:open|launch|start)\s+(.+)$/i);
    if (match) {
      const appName = match[1].trim();
      // Check if we're in Electron
      if (typeof window !== 'undefined' && window.electronAPI?.openApp) {
        try {
          await window.electronAPI.openApp(appName);
          return {
            handled: true,
            action: "open_app",
            response: `Opening ${appName}...`
          };
        } catch (error) {
          return {
            handled: true,
            action: "open_app_failed",
            response: `Could not open ${appName}`
          };
        }
      }
    }
    return { handled: false };
  }
}
```

**Step 2: Add system commands to backend**

In `api_server.py`, inside `list_commands()` (after line 1656):

```python
# System commands (handled by Electron, not agents)
system_commands = [
    {
        "id": "open_app",
        "title": "Open Application",
        "description": "Launch any macOS app (e.g., 'open Safari')",
        "category": "System",
        "icon": "🚀",
        "keywords": ["open", "launch", "start", "app", "application"],
        "handler_type": "system_open_app"
    },
    {
        "id": "quit_cerebros",
        "title": "Quit Cerebros",
        "description": "Close the Cerebros application",
        "category": "System",
        "icon": "🚪",
        "keywords": ["quit", "exit", "close"],
        "handler_type": "system_quit"
    },
]
commands.extend(system_commands)
```

---

### 2.3 Quick Calculator (P1)

**Goal:** User types "15 * 23" → Shows "345" inline, Enter copies to clipboard.

**Step 1: Create calculator utility**

```typescript
// frontend/lib/useCalculator.ts

export function isCalculation(query: string): boolean {
  // Match expressions with numbers and operators only
  const trimmed = query.trim();
  if (!trimmed) return false;
  
  // Must start with a digit or opening paren
  if (!/^[\d(]/.test(trimmed)) return false;
  
  // Only allow safe characters
  return /^[\d\s+\-*/().%]+$/.test(trimmed);
}

export function evaluateCalculation(query: string): string | null {
  try {
    // Sanitize: only allow digits, operators, spaces, parens, decimal
    const sanitized = query.replace(/[^0-9+\-*/().%\s]/g, '');
    if (!sanitized.trim()) return null;
    
    // Use Function constructor for safe eval (no access to scope)
    const result = new Function(`"use strict"; return (${sanitized})`)();
    
    if (typeof result === 'number' && !isNaN(result) && isFinite(result)) {
      // Format nicely
      return result.toLocaleString('en-US', { maximumFractionDigits: 10 });
    }
    return null;
  } catch {
    return null;
  }
}
```

**Step 2: Add to CommandPalette.tsx render**

```tsx
// At the top of the results area, before Actions/Files sections

import { isCalculation, evaluateCalculation } from "@/lib/useCalculator";

// In component:
const calcResult = isCalculation(query) ? evaluateCalculation(query) : null;

// In render, before Actions section:
{calcResult && (
  <div className="px-4 py-3 border-b border-white/10 bg-white/5">
    <div className="flex items-center justify-between">
      <div>
        <span className="text-2xl font-mono text-white">{calcResult}</span>
        <span className="ml-2 text-xs text-white/40">= {query}</span>
      </div>
      <span className="text-xs text-white/40">↵ to copy</span>
    </div>
  </div>
)}

// In handleKeyDown for Enter:
if (calcResult) {
  navigator.clipboard.writeText(calcResult);
  // Optionally show toast
  return;
}
```

---

### 2.4 Settings UI (P1)

**Goal:** User types "settings" → Opens preferences modal.

**Step 1: Create SettingsModal component**

```tsx
// frontend/components/SettingsModal.tsx

"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { isElectron } from "@/lib/electron";
import type { Settings } from "@/types/electron";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const [settings, setSettings] = useState<Settings>({
    hotkey: "CommandOrControl+Option+K",
    hideOnBlur: true,
    startAtLogin: false,
    theme: "dark",
  });
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (isOpen && isElectron()) {
      window.electronAPI?.getSettings().then(setSettings);
    }
  }, [isOpen]);

  const handleSave = async () => {
    if (!isElectron()) return;
    setIsSaving(true);
    try {
      await window.electronAPI?.updateSettings(settings);
      onClose();
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          className="bg-neutral-900 border border-white/10 rounded-xl p-6 w-[400px] shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          <h2 className="text-xl font-semibold text-white mb-6">Preferences</h2>

          <div className="space-y-4">
            {/* Hotkey */}
            <div>
              <label className="block text-sm text-white/60 mb-1">
                Global Hotkey
              </label>
              <input
                type="text"
                value={settings.hotkey}
                onChange={(e) => setSettings({ ...settings, hotkey: e.target.value })}
                className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white"
                placeholder="CommandOrControl+Option+K"
              />
              <p className="text-xs text-white/40 mt-1">
                Use "CommandOrControl" for cross-platform, "Command" for Mac only
              </p>
            </div>

            {/* Start at Login */}
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.startAtLogin}
                onChange={(e) => setSettings({ ...settings, startAtLogin: e.target.checked })}
                className="w-4 h-4 rounded"
              />
              <span className="text-white">Start Cerebros at login</span>
            </label>

            {/* Hide on Blur */}
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.hideOnBlur}
                onChange={(e) => setSettings({ ...settings, hideOnBlur: e.target.checked })}
                className="w-4 h-4 rounded"
              />
              <span className="text-white">Hide when clicking outside</span>
            </label>
          </div>

          <div className="flex justify-end gap-3 mt-8">
            <button
              onClick={onClose}
              className="px-4 py-2 text-white/60 hover:text-white transition"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition disabled:opacity-50"
            >
              {isSaving ? "Saving..." : "Save"}
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
```

**Step 2: Add trigger in CommandPalette**

```tsx
// In CommandPalette.tsx

import SettingsModal from "./SettingsModal";

// Add state
const [showSettings, setShowSettings] = useState(false);

// Add slash command to /api/commands or handle locally
// Detect "settings" or "preferences" query
useEffect(() => {
  if (query.toLowerCase() === "settings" || query.toLowerCase() === "preferences") {
    setShowSettings(true);
    setQuery("");
  }
}, [query]);

// In render:
<SettingsModal isOpen={showSettings} onClose={() => setShowSettings(false)} />
```

**Step 3: Add /settings slash command to backend**

```python
# In api_server.py, add to slash_commands list (if exists) or create:
{
    "id": "settings",
    "title": "Settings",
    "description": "Open Cerebros preferences",
    "category": "System",
    "icon": "⚙️",
    "keywords": ["settings", "preferences", "config", "options"],
    "handler_type": "slash_command",
    "command_type": "immediate"
}
```

---

## 3. Acceptance Criteria

### Unified Command Palette (P0)
- [ ] When user types, both "Actions" and "Files" sections appear
- [ ] Actions section shows matching agent commands with icons
- [ ] Keyboard navigation (↑↓) works across both sections
- [ ] Selecting an action executes it (sends to WebSocket or calls Spotify API)

### "Open App" Command (P0)
- [ ] Typing "open safari" launches Safari
- [ ] Typing "open slack" launches Slack
- [ ] Works for any app name (case insensitive)
- [ ] Shows feedback "Opening Safari..." in response area
- [ ] Only works in Electron mode (graceful fallback in browser)

### Quick Calculator (P1)
- [ ] Typing "15 * 23" shows "345" inline
- [ ] Typing "100 / 4" shows "25" inline
- [ ] Invalid expressions don't crash (show nothing)
- [ ] Pressing Enter copies result to clipboard
- [ ] Supports: +, -, *, /, (), %, decimals

### Settings UI (P1)
- [ ] Typing "settings" opens modal
- [ ] Modal shows current hotkey, start-at-login, hide-on-blur
- [ ] Changes persist after save
- [ ] Hotkey change takes effect immediately
- [ ] Modal closes on Escape or Cancel

---

## 4. Testing Checklist

### Development Testing
```bash
# 1. Start backend
cd /Users/siddharthsuresh/Downloads/auto_mac
source venv/bin/activate
python api_server.py

# 2. Start frontend
cd frontend
npm run dev

# 3. Start Electron (optional, for full testing)
cd ../desktop
npm run dev
```

### Manual Tests
1. **Commands API**: `curl http://localhost:8000/api/commands | jq`
2. **Open App**: In Electron, type "open safari" → Safari launches
3. **Calculator**: Type "2+2" → Shows "4", Enter copies
4. **Settings**: Type "settings" → Modal opens

### Smoke Tests After Changes
- [ ] File search still works
- [ ] Spotify controls still work
- [ ] Voice input still works
- [ ] Escape closes palette
- [ ] Enter submits to WebSocket
- [ ] Keyboard navigation (↑↓) works

---

## 5. Quick Wins (< 30 min each)

If you have extra time, these are low-effort improvements:

1. **Show Spotify now-playing** in palette header (data already available)
2. **Add "Copy path" action** for file results
3. **Add "Quit Cerebros"** system command
4. **Improve empty state** when no results found
5. **Add loading skeleton** for commands fetch

---

## Summary

The implementation is straightforward because **most infrastructure exists**:

| Feature | Backend | Electron IPC | Frontend UI |
|---------|---------|--------------|-------------|
| Unified Commands | ✅ exists | N/A | ⚠️ needs sections |
| Open App | N/A | ✅ exists | ⚠️ needs router pattern |
| Calculator | N/A | N/A | ❌ create new |
| Settings | N/A | ✅ exists | ❌ create modal |

**Start with "Open App"** (smallest change, biggest impact), then Unified Commands, Calculator, Settings.

