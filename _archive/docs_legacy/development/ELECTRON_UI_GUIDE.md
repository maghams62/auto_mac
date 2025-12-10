# Electron UI Development Guide

> **For Future LLMs and Engineers:** This guide provides a complete reference for safely modifying the Cerebro launcher UI without breaking the Electron integration.

## Quick Start

**Most common workflow:**
```bash
# 1. Edit React components in /frontend/components/
# 2. Rebuild frontend
cd frontend && npm run build

# 3. Test in Electron
cd ../desktop && npm run dev
```

**That's it!** This guide explains the "why" and "how" in detail below.

---

## Architecture Overview

### The Two-Process Model

Cerebro uses Electron's standard architecture:

| Process | Tech | Files | Purpose |
|---------|------|-------|---------|
| **Main** | Node.js | `desktop/src/main.ts` | Window management, system APIs, spawns servers |
| **Renderer** | React | `frontend/app/`, `frontend/components/` | UI display, user interactions |
| **Bridge** | IPC | `desktop/src/preload.ts` | Secure communication channel |

**Key Concept:** The renderer (frontend) CANNOT access Node.js APIs directly. It must use IPC to ask the main process to do things like file I/O, system calls, etc.

### Loading Strategy

**Dev Mode** (`npm run dev`):
- Frontend: `http://localhost:3000/launcher` (Next.js dev server)
- Hot reload works
- Faster iteration

**Production** (`electron app.dmg`):
- Frontend: `file:///app/frontend/out/launcher.html` (static files)
- No dev server needed
- Must rebuild after changes

---

## Critical File Map

### Where to Edit UI

| What You Want | File to Edit | Lines (approx) |
|---------------|--------------|----------------|
| Launcher search box | `/frontend/app/launcher/page.tsx` | All |
| Command palette UI | `/frontend/components/CommandPalette.tsx` | 360-2000+ |
| Spotify widget | `/frontend/components/SpotifyMiniPlayer.tsx` | 684-778 (launcher-mini variant) |
| Full chat interface | `/frontend/app/desktop/page.tsx` | All |
| Chat messages | `/frontend/components/ChatInterface.tsx` | All |
| File previews | `/frontend/components/ArtifactCard.tsx` | All |

### Where Electron Lives

| What | File | Key Functions |
|------|------|---------------|
| Window creation | `/desktop/src/main.ts` | `createWindow()` (line ~1070) |
| Window sizing | `/desktop/src/main.ts` | Constants at line 551-554 |
| IPC handlers | `/desktop/src/preload.ts` | `electronAPI` object |
| Build config | `/desktop/electron-builder.json` | Resource bundling |

---

## How to Modify UI (Step-by-Step)

### Step 1: Edit React Component

Example: Change Spotify player size

```tsx
// File: /frontend/components/SpotifyMiniPlayer.tsx
if (variant === "launcher-mini") {
  return (
    <motion.div
      className="w-[400px] ...">  {/* Changed from 320px to 400px */}
      {/* Rest of component */}
    </motion.div>
  );
}
```

### Step 2: Rebuild Frontend

**CRITICAL STEP** - Never skip this!

```bash
cd /Users/siddharthsuresh/Downloads/auto_mac/frontend
npm run build
```

This creates `/frontend/out/` with HTML/JS/CSS that Electron loads.

### Step 3: Test in Electron

```bash
cd /Users/siddharthsuresh/Downloads/auto_mac/desktop
npm run dev
```

Press your hotkey (default: `Cmd+Alt+K`) to see changes.

---

## Common Scenarios

### Scenario 1: Modify Spotify Player

**Goal:** Change layout, colors, or controls

**Steps:**
1. Edit `/frontend/components/SpotifyMiniPlayer.tsx`
2. Find `variant === "launcher-mini"` (line ~684)
3. Modify JSX and Tailwind classes
4. `cd frontend && npm run build`
5. `cd desktop && npm run dev`

**Tip:** Use Tailwind classes like `w-[320px]`, `bg-black/95`, `rounded-xl`

### Scenario 2: Add Widget to Launcher

**Goal:** Show weather, calendar, etc. in spotlight view

**Steps:**
1. Create `/frontend/components/MyWidget.tsx`:
   ```tsx
   export function MyWidget() {
     return <div className="w-full p-4">Hello!</div>;
   }
   ```
2. Edit `/frontend/components/CommandPalette.tsx`:
   ```tsx
   import { MyWidget } from '@/components/MyWidget';

   // In render (after Spotify player):
   <MyWidget />
   ```
3. Rebuild and test

### Scenario 3: Change Window Size

**Goal:** Make launcher wider/taller

**Steps:**
1. Edit `/desktop/src/main.ts` (line ~551):
   ```typescript
   const WINDOW_WIDTH = 900;   // Was 800
   const WINDOW_HEIGHT = 600;  // Was 520
   ```
2. `cd desktop && npm run build:electron`
3. `cd desktop && npm run dev`

---

## Rules for Frontend Code

### ✅ DO This

```tsx
// Use Tailwind CSS
<div className="flex items-center gap-2 p-4 bg-black rounded-lg">

// Use path aliases
import { MyComponent } from '@/components/MyComponent';
import { logger } from '@/lib/logger';

// Use IPC for Electron features
import { isElectron } from '@/lib/electron';
if (isElectron()) {
  window.electronAPI?.hideWindow();
}

// Log important events
logger.info('[MY-COMPONENT] User clicked button', { id: 123 });
```

### ❌ DON'T Do This

```tsx
// ❌ Don't use inline styles
<div style={{ display: 'flex' }}>

// ❌ Don't import Node.js modules
import fs from 'fs';  // Crashes in renderer!

// ❌ Don't import from desktop
import { something } from '../../../desktop/src/main';  // Won't work

// ❌ Don't hardcode paths
const filePath = '/Users/me/Documents/file.txt';  // Use config instead
```

---

## Build Process

### Frontend Build

```bash
cd frontend
npm run build        # Production build → /frontend/out/
npm run dev          # Dev server → localhost:3000
npm run lint         # Check for errors
```

### Electron Build

```bash
cd desktop
npm run build:electron    # Compile TypeScript → /desktop/dist/
npm run dev              # Launch app
npm run dist:mac         # Package .dmg for distribution
```

### Full Pipeline

```bash
cd desktop
npm run build    # Does frontend + electron builds
```

---

## Debugging

### Open DevTools

**In Electron window:** Press `Cmd+Option+I`

**Or add to code:**
```typescript
// In desktop/src/main.ts after window creation:
mainWindow.webContents.openDevTools();
```

### Check Logs

```bash
# Electron logs
tail -f logs/electron/cerebros-*.log

# Backend API
tail -f logs/api_server.log

# Frontend console
# Open DevTools in Electron window
```

### Common Debugging Steps

1. **Blank screen?**
   - Check DevTools Console for errors
   - Check DevTools Network for 404s
   - Verify `/frontend/out/launcher/index.html` exists
   - Rebuild: `cd frontend && npm run build`

2. **Styles broken?**
   - Check DevTools Network for CSS 404s
   - Verify Tailwind compiled: `ls frontend/out/_next/static/css/`
   - Rebuild frontend

3. **Component not updating?**
   - Did you rebuild? (`npm run build`)
   - Are you in dev mode? (should auto-update)
   - Check you're editing the right file

---

## Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| Blank screen | Frontend not built | `cd frontend && npm run build` |
| Styles missing | CSS not compiled | `cd frontend && npm run build` |
| "Cannot find module" | Wrong file path | Check paths use `app/frontend/out/` |
| Component unchanged | Forgot to rebuild | `cd frontend && npm run build` |
| IPC undefined | Preload not loaded | Check `preload` path in BrowserWindow |
| Hot reload broken | Not in dev mode | `cd frontend && npm run dev` |

---

## IPC Communication

### Available APIs

From React components, you can call:

```tsx
// Hide launcher window
window.electronAPI?.hideWindow();

// Prevent auto-hide during processing
window.electronAPI?.lockWindow();
window.electronAPI?.unlockWindow();

// Open full desktop view
window.electronAPI?.openExpandedWindow();

// Return to launcher
window.electronAPI?.collapseToSpotlight();

// Get diagnostic info
const state = await window.electronAPI?.getWindowState();

// Open file in Finder
window.electronAPI?.revealInFinder('/path/to/file');

// Open URL in browser
window.electronAPI?.openExternal('https://example.com');

// Launch macOS app
const result = await window.electronAPI?.openApp('Spotify');
```

### Adding New APIs

1. **Define in preload** (`/desktop/src/preload.ts`):
   ```typescript
   const electronAPI = {
     myNewAPI: () => ipcRenderer.invoke('my-new-api'),
   };
   ```

2. **Add type** (`/frontend/types/electron.d.ts`):
   ```typescript
   export interface ElectronAPI {
     myNewAPI: () => Promise<void>;
   }
   ```

3. **Use in React**:
   ```tsx
   window.electronAPI?.myNewAPI();
   ```

---

## File Paths (CRITICAL)

### Development Mode

```typescript
// Launcher window loads from:
http://localhost:3000/launcher

// Desktop window loads from:
http://localhost:3000/desktop
```

### Production Mode

```typescript
// Launcher window loads from:
file://[resourcesPath]/app/frontend/out/launcher.html

// Desktop window loads from:
file://[resourcesPath]/app/frontend/out/desktop.html
```

**⚠️ IMPORTANT:** Both paths MUST use `app/frontend/out/` prefix.

The `electron-builder.json` config bundles frontend to `app/frontend/out/`, so paths must match.

---

## File Structure

```
auto_mac/
├── frontend/              # React/Next.js app
│   ├── app/
│   │   ├── launcher/     # Spotlight view
│   │   └── desktop/      # Chat view
│   ├── components/       # UI components
│   ├── lib/              # Utilities
│   ├── out/              # BUILD OUTPUT (git-ignored)
│   └── package.json
│
├── desktop/              # Electron app
│   ├── src/
│   │   ├── main.ts      # Main process
│   │   └── preload.ts   # IPC bridge
│   ├── dist/            # BUILD OUTPUT (git-ignored)
│   └── package.json
│
└── docs/
    └── development/
        └── ELECTRON_UI_GUIDE.md  # This file
```

---

## Quick Reference

### Most Common Workflow

```bash
# 1. Edit React component
vim frontend/components/MyComponent.tsx

# 2. Rebuild frontend
cd frontend && npm run build

# 3. Test in Electron
cd ../desktop && npm run dev
```

### Less Common Workflows

**Change Electron window behavior:**
```bash
# 1. Edit main.ts
vim desktop/src/main.ts

# 2. Rebuild Electron
cd desktop && npm run build:electron

# 3. Test
npm run dev
```

**Add new IPC API:**
```bash
# 1. Edit preload.ts
vim desktop/src/preload.ts

# 2. Edit electron.d.ts
vim frontend/types/electron.d.ts

# 3. Rebuild Electron
cd desktop && npm run build:electron

# 4. Use in React
vim frontend/components/MyComponent.tsx

# 5. Rebuild frontend
cd frontend && npm run build

# 6. Test
cd ../desktop && npm run dev
```

---

## Best Practices

1. **Always rebuild** after changes (`npm run build`)
2. **Test in both modes** (dev and production)
3. **Use TypeScript** (proper types prevent bugs)
4. **Follow patterns** (look at existing components)
5. **Log events** (`logger.info()` for debugging)
6. **Check DevTools** (Console + Network tabs)

---

## Getting Help

**Read the docs:**
- Next.js: https://nextjs.org/docs
- Electron: https://www.electronjs.org/docs
- Tailwind: https://tailwindcss.com/docs

**Check existing code:**
- Look at similar components for patterns
- Search codebase for examples: `grep -r "pattern" frontend/`

**Common mistakes:**
- Forgot to rebuild (`npm run build`)
- Editing wrong file (check file path)
- Wrong path prefix (use `app/frontend/out/`)
- Using Node.js in renderer (use IPC instead)

---

## Summary

**The Golden Rule:** Frontend changes require `npm run build`

**The Process:**
1. Edit React component in `/frontend/`
2. Run `cd frontend && npm run build`
3. Run `cd desktop && npm run dev`
4. Test changes

**Remember:**
- Use Tailwind CSS for styling
- Use IPC for Electron features
- Check DevTools for errors
- Read existing code for patterns

That's it! You're now ready to safely modify the UI. 🚀

---

## Electron Contribution Checklist (For Coding LLMs)

1. **Initialize Electron code only after `app.ready`**
   - Use helpers like `getStore()`/`getLogger()` which lazy-load inside `app.on('ready')`.
   - Any new singleton should follow the same pattern; never call `app.getPath()` or create `BrowserWindow` instances at module load time.

2. **Preserve the instant-start experience**
   - `createWindow()` runs as soon as the app is ready; backend/frontend health checks happen in the background.  
   - Do not block the UI on server readiness; record timing via `markStartup()` logs instead.

3. **Respect the window visibility state machine**
   - Read `CRITICAL_BEHAVIOR.md` and `docs/WINDOW_VISIBILITY_STATE_MACHINE.md` before changing `lockWindowVisibility()`, blur handlers, or `windowState`.
   - Renderer code should use the wrappers in `frontend/lib/electron.ts` (`lockWindow`, `unlockWindow`, etc.) rather than ad-hoc IPC.

4. **Settings must go through IPC**
   - `window.electronAPI.getSettings()` / `updateSettings()` are the only sanctioned paths for the renderer.  
   - Keep `electron-store` usage confined to `desktop/src/main.ts` (via `getStore()`).

5. **Avoid hydration mismatches**
   - Use the `useIsElectronRuntime()` hook when branching on Electron-specific UI so SSR markup matches the first client render.
   - Don’t inline `typeof window !== 'undefined'` checks inside JSX render paths.

6. **Multi-monitor window positioning**
   - `showWindow()` centers the launcher on the cursor’s display, falling back to the primary monitor only if needed (with a warning log).  
   - Preserve the diagnostic logs so we can trace which monitor was used.

7. **Safe testing workflow**
   - To run Electron briefly without leaving it running:
     ```bash
     cd desktop
     (npm run dev & pid=$!; sleep 25; kill $pid >/dev/null 2>&1)
     ```
   - Inspect `logs/electron/cerebros-*.log` for `[STARTUP]` timelines, blur events, and diagnostics before modifying behavior.

8. **Renderer ↔ main communication**
   - Add new IPC methods in `desktop/src/preload.ts`, extend `frontend/types/electron.d.ts`, and consume via `window.electronAPI`.  
   - Never import Node/Electron modules directly into React components.
