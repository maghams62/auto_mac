# Cerebros vs Raycast/Spotlight: Gap Analysis

**Date:** November 27, 2024  
**Purpose:** Identify where Cerebros falls short of Raycast/Spotlight UX and define immediate improvements.

---

## 1. Current Cerebros Capabilities

### Launcher Infrastructure (Electron)
| Feature | Status | Notes |
|---------|--------|-------|
| Global hotkey | ✅ | `Cmd+Option+K` (configurable via electron-store) |
| Frameless window | ✅ | Transparent, always-on-top, centered on active display |
| System tray icon | ✅ | Menubar only, no dock icon |
| Auto-start services | ✅ | Python backend + Next.js spawned on launch |
| Health check polling | ✅ | Waits for servers before showing window |
| IPC bridge | ✅ | hideWindow, revealInFinder, openApp, openExternal |
| Window locking | ✅ | Prevents blur-hide during voice/processing |

### Command Palette (`CommandPalette.tsx`)
| Feature | Status | Notes |
|---------|--------|-------|
| File search | ✅ | Semantic search via `/api/universal-search` |
| Keyboard navigation | ✅ | Arrow keys, Enter, Escape |
| Document preview | ✅ | Space to preview, Enter to open |
| Voice input | ✅ | VAD with 5s silence auto-stop |
| Deterministic routing | ✅ | Fast path for Spotify, clear, help |
| Agent commands display | ❌ | Backend returns them but UI doesn't show |

### Backend Agents (50+ in `src/agent/`)
| Category | Agents |
|----------|--------|
| Files | FileAgent, FolderAgent |
| Communication | EmailAgent, iMessageAgent, DiscordAgent, WhatsAppAgent |
| Web | BrowserAgent, GoogleAgent |
| Productivity | CalendarAgent, NotesAgent, RemindersAgent, WritingAgent, PresentationAgent |
| Media | SpotifyAgent, VoiceAgent, ScreenAgent, VisionAgent |
| Social | BlueskyAgent, TwitterAgent, RedditAgent |
| Information | WeatherAgent, MapsAgent, KnowledgeAgent, StockAgent |
| System | ShortcutsAgent, SystemControlAgent |

### APIs
| Endpoint | Purpose |
|----------|---------|
| `GET /api/commands` | Returns 20+ agent commands with metadata |
| `GET /api/universal-search` | Semantic document search (FAISS) |
| `WS /ws/chat` | Streaming chat with LLM orchestration |
| `POST /api/spotify/*` | Playback controls |
| `GET /health` | Electron readiness check |

---

## 2. Raycast/Spotlight Must-Have Behaviors

### Core UX Expectations

| Behavior | Raycast | Spotlight | Cerebros |
|----------|---------|-----------|----------|
| **Instant hotkey response (<150ms)** | ✅ | ✅ | ✅ |
| **Unified actions + files in one list** | ✅ | ❌ | ❌ |
| **Fuzzy search with ranking** | ✅ | ✅ | Partial (semantic only) |
| **Open any app by name** | ✅ | ✅ | ❌ (IPC exists, no UI) |
| **Quick calculator / unit conversion** | ✅ | ✅ | ❌ |
| **Dictionary / define word** | ✅ | ✅ | ❌ |
| **Clipboard history** | ✅ | ❌ | ❌ |
| **Window management (resize, tile)** | ✅ | ❌ | ❌ |
| **Emoji picker** | ✅ | ✅ | ❌ |
| **Customizable hotkey** | ✅ | ❌ | ✅ (backend only) |
| **Settings UI** | ✅ | ✅ | ❌ |

### Extension / Workflow System

| Behavior | Raycast | Spotlight | Cerebros |
|----------|---------|-----------|----------|
| **Extension store / API** | ✅ | ❌ | ❌ |
| **Script commands** | ✅ | ❌ | Partial (ShortcutsAgent) |
| **Quicklinks (URL shortcuts)** | ✅ | ❌ | ❌ |
| **Snippets (text expansion)** | ✅ | ❌ | ❌ |
| **Floating notes** | ✅ | ❌ | ❌ |

### AI / Voice Features

| Behavior | Raycast | Spotlight | Cerebros |
|----------|---------|-----------|----------|
| **Raycast AI (LLM chat)** | ✅ Pro | ❌ | ✅ |
| **Voice input** | ❌ | Siri | ✅ (VAD) |
| **Siri trigger ("Hey Siri, Cerebros")** | ❌ | ✅ | ❌ |
| **Natural language commands** | ✅ | ❌ | ✅ |
| **AI quick actions (summarize, translate)** | ✅ Pro | ❌ | Partial |

### System Integration

| Behavior | Raycast | Spotlight | Cerebros |
|----------|---------|-----------|----------|
| **System Preferences search** | ✅ | ✅ | ❌ |
| **Contacts search** | ✅ | ✅ | ❌ |
| **Music/Podcast controls** | ✅ | ✅ | ✅ (Spotify only) |
| **Reveal file in Finder** | ✅ | ✅ | ✅ |
| **Quick Look preview** | ✅ | ✅ | ✅ |

---

## 3. Gap Analysis Summary

### Critical Gaps (Must Fix)

| Gap | Impact | Effort | Priority |
|-----|--------|--------|----------|
| **Unified command palette** (actions + files) | High - users expect Raycast behavior | Low | P0 |
| **"Open App" command** | High - basic launcher expectation | Low | P0 |
| **Settings UI** (hotkey, startup) | Medium - power users blocked | Medium | P1 |
| **Quick calculator** | Medium - frequent use case | Low | P1 |

### Important Gaps (Should Fix)

| Gap | Impact | Effort | Priority |
|-----|--------|--------|----------|
| **Clipboard history** | Medium | Medium | P2 |
| **Emoji picker** | Low | Low | P2 |
| **System Preferences search** | Medium | High | P2 |
| **Contacts integration** | Low | Medium | P3 |

### Nice-to-Have (Future)

| Gap | Impact | Effort | Priority |
|-----|--------|--------|----------|
| **Siri trigger** | Medium | High | P3 |
| **Extension API** | High | Very High | P4 |
| **Window management** | Medium | High | P4 |
| **Snippets / text expansion** | Medium | Medium | P4 |

---

## 4. Immediate Improvements (P0 + P1)

### 4.1 Unified Command Palette (P0) - ~2 hours

**Current State:** `/api/commands` returns 20+ agents, but `CommandPalette.tsx` only shows file search results.

**Required Changes:**

1. **Fetch commands on mount:**
```tsx
// In CommandPalette.tsx
useEffect(() => {
  fetch(`${baseUrl}/api/commands`)
    .then(r => r.json())
    .then(data => setCommands(data.commands));
}, []);
```

2. **Filter and display commands alongside files:**
```tsx
const filteredCommands = commands.filter(cmd =>
  cmd.title.toLowerCase().includes(query.toLowerCase()) ||
  cmd.keywords.some(kw => kw.toLowerCase().includes(query.toLowerCase()))
);

// In render:
{filteredCommands.length > 0 && (
  <section>
    <h3 className="text-xs text-muted mb-2">Actions</h3>
    {filteredCommands.slice(0, 5).map(cmd => (
      <CommandItem key={cmd.id} command={cmd} onSelect={executeCommand} />
    ))}
  </section>
)}
```

3. **Execute command on select:**
```tsx
const executeCommand = (cmd: Command) => {
  if (cmd.handler_type === "spotify_control") {
    fetch(`${baseUrl}${cmd.endpoint}`, { method: 'POST' });
  } else if (cmd.handler_type === "agent") {
    wsSendMessage(`Use ${cmd.id} to: ${query}`);
  }
};
```

**Files to modify:**
- `frontend/components/CommandPalette.tsx`

---

### 4.2 "Open App" Command (P0) - ~1 hour

**Current State:** `main.ts` has `ipcMain.on('open-app')` handler, but no UI trigger.

**Required Changes:**

1. **Add system commands to `/api/commands`:**
```python
# In api_server.py, inside list_commands()
system_commands = [
    {
        "id": "open_app",
        "title": "Open Application",
        "description": "Launch any macOS app",
        "category": "System",
        "icon": "🚀",
        "keywords": ["open", "launch", "app", "application"],
        "handler_type": "system_open_app"
    },
    {
        "id": "search_web",
        "title": "Search Web",
        "description": "Search Google in browser",
        "category": "Web",
        "icon": "🔍",
        "keywords": ["google", "search", "web", "browse"],
        "handler_type": "system_search_web"
    }
]
commands.extend(system_commands)
```

2. **Handle in frontend:**
```tsx
// In CommandPalette.tsx
const executeCommand = (cmd: Command) => {
  if (cmd.handler_type === "system_open_app") {
    // Extract app name from query (e.g., "open safari" → "Safari")
    const appName = query.replace(/^open\s+/i, '').trim();
    if (isElectron()) {
      window.electronAPI?.openApp(appName);
    }
  }
  // ... other handlers
};
```

3. **Smart pattern matching in deterministic router:**
```tsx
// In useCommandRouter.ts, add pattern:
{
  patterns: [/^open\s+(.+)$/i],
  action: "open_app",
  handler: async (input: string) => {
    const match = input.match(/^open\s+(.+)$/i);
    if (match && isElectron()) {
      window.electronAPI?.openApp(match[1]);
      return { handled: true, action: "open_app", response: `Opening ${match[1]}...` };
    }
    return { handled: false };
  }
}
```

**Files to modify:**
- `api_server.py` (add system commands)
- `frontend/lib/useCommandRouter.ts` (add open app pattern)
- `frontend/components/CommandPalette.tsx` (handle new command type)

---

### 4.3 Settings UI (P1) - ~3 hours

**Current State:** Settings stored in electron-store but no UI to change them.

**Required Changes:**

1. **Create Settings modal component:**
```tsx
// frontend/components/SettingsModal.tsx
export default function SettingsModal({ isOpen, onClose }) {
  const [settings, setSettings] = useState({ hotkey: '', hideOnBlur: true, startAtLogin: false });

  useEffect(() => {
    if (isElectron()) {
      window.electronAPI?.getSettings().then(setSettings);
    }
  }, [isOpen]);

  const saveSettings = () => {
    window.electronAPI?.updateSettings(settings);
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent>
        <h2>Preferences</h2>
        <label>
          Global Hotkey
          <input value={settings.hotkey} onChange={e => setSettings({...settings, hotkey: e.target.value})} />
        </label>
        <label>
          <input type="checkbox" checked={settings.startAtLogin} onChange={e => setSettings({...settings, startAtLogin: e.target.checked})} />
          Start at login
        </label>
        <label>
          <input type="checkbox" checked={settings.hideOnBlur} onChange={e => setSettings({...settings, hideOnBlur: e.target.checked})} />
          Hide when clicking outside
        </label>
        <button onClick={saveSettings}>Save</button>
      </DialogContent>
    </Dialog>
  );
}
```

2. **Expose getSettings in preload:**
```typescript
// desktop/src/preload.ts
getSettings: () => ipcRenderer.invoke('get-settings'),
updateSettings: (settings) => ipcRenderer.send('update-settings', settings),
```

3. **Add trigger to CommandPalette:**
- Type "preferences" or "settings" → show modal
- Or add gear icon to header

**Files to modify:**
- `frontend/components/SettingsModal.tsx` (new)
- `frontend/components/CommandPalette.tsx` (trigger)
- `desktop/src/preload.ts` (expose APIs - already partially done)
- `frontend/types/electron.d.ts` (type definitions)

---

### 4.4 Quick Calculator (P1) - ~1 hour

**Required Changes:**

1. **Detect math expressions in query:**
```tsx
// In CommandPalette.tsx or new useCalculator.ts hook
const isCalculation = (query: string) => /^[\d\s+\-*/().%^]+$/.test(query.trim());

const evaluateCalculation = (query: string): string | null => {
  try {
    // Safe eval using Function constructor
    const sanitized = query.replace(/[^0-9+\-*/().%\s]/g, '');
    const result = new Function(`return ${sanitized}`)();
    return typeof result === 'number' ? result.toString() : null;
  } catch {
    return null;
  }
};
```

2. **Show result inline:**
```tsx
{isCalculation(query) && (
  <div className="p-4 border-b border-white/10">
    <span className="text-2xl font-mono">{evaluateCalculation(query) || 'Invalid'}</span>
    <span className="text-xs text-muted ml-2">Press Enter to copy</span>
  </div>
)}
```

3. **Copy result on Enter:**
```tsx
if (isCalculation(query)) {
  const result = evaluateCalculation(query);
  if (result) {
    navigator.clipboard.writeText(result);
    // Show toast "Copied to clipboard"
  }
}
```

**Files to modify:**
- `frontend/components/CommandPalette.tsx`
- `frontend/lib/useCalculator.ts` (new, optional)

---

## 5. Siri Integration Roadmap (P3)

Since you mentioned interest in Siri, here's the path forward:

### Option A: macOS Shortcuts Integration (Recommended)

1. **Create Siri Shortcut that opens Cerebros:**
   - User creates Shortcut: "Open Cerebros"
   - Shortcut runs AppleScript: `tell application "Cerebros" to activate`
   - User says "Hey Siri, open Cerebros"

2. **Pass command via URL scheme:**
   - Register custom URL scheme: `cerebros://`
   - Shortcut opens: `cerebros://command?q=play%20spotify`
   - Electron handles URL and executes command

3. **Implementation:**
```typescript
// In main.ts
app.setAsDefaultProtocolClient('cerebros');

app.on('open-url', (event, url) => {
  event.preventDefault();
  const parsed = new URL(url);
  const query = parsed.searchParams.get('q');
  if (query && mainWindow) {
    mainWindow.show();
    mainWindow.webContents.send('execute-command', query);
  }
});
```

### Option B: Direct Siri Intent (Requires Native Extension)

- Would need a native macOS extension (Swift) with SiriKit intents
- High effort, Apple review required
- Not recommended for MVP

---

## 6. Implementation Priority Order

| Phase | Task | Effort | Outcome |
|-------|------|--------|---------|
| **Week 1** | Unified command palette | 2h | Users see actions + files together |
| **Week 1** | "Open App" command | 1h | Basic launcher parity |
| **Week 2** | Quick calculator | 1h | Common use case covered |
| **Week 2** | Settings UI | 3h | Users can customize hotkey |
| **Week 3** | Emoji picker | 2h | Nice polish |
| **Week 3** | Clipboard history | 4h | Power user feature |
| **Week 4** | Siri Shortcuts integration | 4h | Voice activation |

---

## 7. Quick Wins (< 30 min each)

1. **Show "Actions" section header** in CommandPalette (already fetching commands)
2. **Add `/settings` slash command** to open preferences
3. **Add "Copy to clipboard" action** for search results
4. **Show Spotify now-playing** in command palette header
5. **Add "Quit Cerebros" command** to system commands

---

## Summary

**Cerebros is 70% of the way to Raycast parity.** The core infrastructure (Electron, hotkey, agents, LLM) is solid. The main gaps are:

1. **Unified UI** - The backend has everything, frontend just needs to display it
2. **System commands** - "Open App" is the biggest miss
3. **Settings UI** - Users can't customize without editing code
4. **Quick utilities** - Calculator, emoji picker, clipboard

Fixing these 4 areas would make Cerebros feel like a complete Raycast alternative. The LLM integration (which Raycast only offers in Pro) is already Cerebros' differentiator.

