# Cerebros Desktop - Setup Instructions

## ✅ Phase 0 Complete!

The Electron launcher structure has been created. Here's what we've built:

### Created Files

```
desktop/
├── src/
│   ├── main.ts           ✅ Electron main process (window, tray, hotkey, spawns backend)
│   └── preload.ts        ✅ IPC bridge for secure communication
├── assets/               ✅ Directory for app icon
├── package.json          ✅ Dependencies and build scripts
├── tsconfig.json         ✅ TypeScript configuration
├── electron-builder.json ✅ App packaging configuration
└── README.md             ✅ Documentation
```

### Backend Enhancement

- ✅ Added `/health` endpoint to [api_server.py](../api_server.py:1305) for launcher health checks

## 🚀 Next Steps

### 1. Install Node.js (if not already installed)

```bash
# Install Node.js via Homebrew (recommended)
brew install node

# Or download from https://nodejs.org/ (LTS version recommended)
```

Verify installation:
```bash
node --version  # Should show v18.x or higher
npm --version   # Should show v9.x or higher
```

### 2. Install Desktop App Dependencies

```bash
cd desktop
npm install
```

This will install:
- `electron` - Desktop app framework
- `electron-builder` - App packaging tool
- `electron-store` - Settings persistence
- `typescript` - TypeScript compiler
- `@types/node` - TypeScript types

### 3. Test the Launcher (Development Mode)

```bash
# Terminal 1: Ensure backend is running
cd /Users/siddharthsuresh/Downloads/auto_mac
source venv/bin/activate
python api_server.py

# Terminal 2: Ensure frontend is running
cd /Users/siddharthsuresh/Downloads/auto_mac/frontend
npm run dev

# Terminal 3: Start Electron launcher
cd /Users/siddharthsuresh/Downloads/auto_mac/desktop
npm run dev
```

**OR** use the launcher's auto-start feature:

```bash
cd /Users/siddharthsuresh/Downloads/auto_mac/desktop
npm run dev
```

The Electron app will automatically:
1. Start Python backend (port 8000)
2. Start Next.js frontend (port 3000)
3. Wait for health checks to pass
4. Show the launcher window

### 4. Use the Launcher

- **Press `Cmd+Option+Space` (⌥⌘Space)** to show/hide the launcher
- **Press `Escape`** to hide the launcher
- **Click the tray icon** to show launcher or access menu
- **Right-click tray icon** for settings (coming in Phase 7)

## 🎨 What's Next?

### Current Status

✅ **Phase 0: Setup** - COMPLETE
- Electron structure created
- TypeScript configured
- Build scripts ready
- Health check endpoint added

### Remaining Phases

📋 **Phase 1: Basic Window** (Next)
- Test Electron window with existing UI
- Verify hotkey works
- Verify backend/frontend auto-start

🎭 **Phase 2: Window Behavior**
- Hide on blur
- Escape key handling
- Tray menu improvements

🎯 **Phase 3: Unified Palette**
- Add `/api/commands` endpoint
- Merge agents + files in CommandPalette
- Action execution flow

🖥️ **Phase 4: System Actions**
- Open app command
- Reveal in Finder
- Smart command matching

🔧 **Phase 5: Auto-Start**
- Already implemented in Phase 0!
- Just needs testing

📦 **Phase 6: Production Build**
- Package as .dmg
- Bundle Python + Next.js
- Create app icon

⚙️ **Phase 7: Settings**
- Customizable hotkey
- Start at login
- Preferences UI

## 🐛 Troubleshooting

### "npm: command not found"

Install Node.js:
```bash
brew install node
# or download from https://nodejs.org/
```

### "Cannot find module 'electron'"

Install dependencies:
```bash
cd desktop
npm install
```

### "Python backend failed to start"

Ensure venv exists and dependencies are installed:
```bash
cd /Users/siddharthsuresh/Downloads/auto_mac
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### "Frontend failed to start"

Install frontend dependencies:
```bash
cd /Users/siddharthsuresh/Downloads/auto_mac/frontend
npm install
```

### Hotkey doesn't work

The default hotkey is `Cmd+Option+Space` to avoid conflicting with Spotlight.
You can change this in [desktop/src/main.ts:367](desktop/src/main.ts:367)

## 📊 Architecture

```
┌─────────────────────────────────────────┐
│  Electron App (Cerebros.app)            │
├─────────────────────────────────────────┤
│                                         │
│  main.ts (Main Process)                 │
│  ├─ Spawns Python backend (port 8000)  │
│  ├─ Spawns Next.js frontend (port 3000)│
│  ├─ Creates launcher window             │
│  ├─ Registers Cmd+Option+Space hotkey   │
│  └─ Creates tray icon                   │
│                                         │
│  preload.ts (IPC Bridge)                │
│  └─ Exposes safe APIs to renderer       │
│                                         │
│  Renderer (Browser Context)             │
│  └─ Loads http://localhost:3000         │
│     (Existing Next.js UI)               │
│                                         │
└─────────────────────────────────────────┘
```

## 🎉 What We've Accomplished

1. **Electron Structure** ✅
   - Main process with window management
   - Preload script for secure IPC
   - TypeScript configuration

2. **Auto-Start Services** ✅
   - Python backend spawning
   - Next.js frontend spawning
   - Health check polling

3. **Native Features** ✅
   - Global hotkey (Cmd+Option+Space)
   - System tray icon
   - Frameless, transparent window
   - Hide from dock

4. **IPC Handlers** ✅
   - Hide window
   - Open app
   - Reveal in Finder
   - Open external URL

5. **Backend Integration** ✅
   - Added /health endpoint
   - Ready for unified commands API

## 📚 Resources

- **Plan**: [RAYCAST_LAUNCHER_CONVERSION_PLAN.md](../RAYCAST_LAUNCHER_CONVERSION_PLAN.md)
- **Desktop README**: [README.md](README.md)
- **Electron Docs**: https://www.electronjs.org/docs/latest
- **electron-builder**: https://www.electron.build/

---

**Ready to continue?** Once Node.js is installed, run:

```bash
cd desktop
npm install
npm run dev
```

Press `Cmd+Option+Space` and watch your Cerebros launcher come to life! 🚀
