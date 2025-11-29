# Cerebros Launcher - Electron Desktop App

**Raycast-style AI launcher for macOS**

A native macOS application that provides instant access to Cerebros AI features via global hotkey. Features file search, 20+ agent commands, Spotify control, and full keyboard navigation.

---

## 🚀 Quick Start

### Prerequisites

- **Node.js 18+** - [Download](https://nodejs.org/)
- **Python 3.8+** - Usually pre-installed on macOS
- **npm** - Comes with Node.js

### Installation

```bash
# 1. Clone/navigate to project
cd /Users/siddharthsuresh/Downloads/auto_mac

# 2. Install Python dependencies (for development)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Install frontend dependencies
cd frontend
npm install

# 4. Install desktop (Electron) dependencies
cd ../desktop
npm install
```

### Running the App

**Development Mode** (recommended for testing):

```bash
cd /Users/siddharthsuresh/Downloads/auto_mac/desktop
npm run dev
```

This will:
1. Compile TypeScript → JavaScript
2. Launch Electron app
3. Auto-start Python backend (port 8000)
4. Auto-start Next.js dev server (port 3000)
5. Open DevTools for debugging

**Using the Launcher**:
- Press **`Cmd+Option+Space`** anywhere to show/hide
- Or click the menu bar icon
- Type to search, use arrow keys to navigate
- Press `Enter` to execute

---

## 📦 Building for Distribution

### Full Production Build

```bash
cd /Users/siddharthsuresh/Downloads/auto_mac/desktop

# Build everything and create .dmg installer
npm run dist:mac
```

Output: `desktop/dist-app/Cerebros-1.0.0.dmg`

### Step-by-Step Build

```bash
# 1. Clean previous builds
npm run clean

# 2. Build frontend (static export)
npm run build:frontend

# 3. Build Electron app
npm run build:electron

# 4. Package as macOS app
npm run dist:mac
```

### Testing the Build

```bash
# Open the built app
cd dist-app
open Cerebros.app
```

On **first run**, the app will:
1. Create Python virtual environment in `~/Library/Application Support/cerebros-launcher/`
2. Install dependencies (1-3 minutes)
3. Start backend and frontend
4. Ready to use!

**Subsequent runs** are instant (venv already exists).

---

## 🎯 Features

### Global Hotkey Access
- **`Cmd+Option+Space`** - Show/hide launcher (customizable in Preferences)
- Works from any app, Raycast-style

### Unified Command Palette
- **20+ Agent Commands** - Email, Spotify, Calendar, Maps, Weather, etc.
- **File Search** - Semantic search across indexed documents
- **Smart Filtering** - Searches both commands and files
- **Keyboard Navigation** - Full ↑↓ arrow key support

### Spotify Integration
- **Mini-Player** - Shows current track at bottom of launcher
- **Quick Controls** - Play/pause, next, previous
- **Keyboard Commands** - Type "play", "next", "previous"

### Preferences
- **Customizable Hotkey** - Change global shortcut
- **Hide on Blur** - Auto-hide when window loses focus
- **Start at Login** - Launch Cerebros on macOS startup
- **Theme** - Dark/Light/Auto

### System Integration
- **Menu Bar Icon** - No dock clutter
- **Auto-Start Services** - Backend/frontend launch automatically
- **Settings Persistence** - electron-store for reliable storage

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd+Option+Space` | Show/hide launcher (global) |
| `Escape` | Hide launcher |
| `Cmd+K` | Open palette (browser mode) |
| `Cmd+,` | Open preferences |
| `↑` `↓` | Navigate results |
| `Enter` | Execute command or open file |
| `Cmd+Enter` | Reveal file in Finder |
| `Space` | Quick preview (files only) |

---

## 🛠️ Development

### Project Structure

```
desktop/
├── src/
│   ├── main.ts          # Electron main process
│   └── preload.ts       # IPC bridge
├── dist/                # Compiled JavaScript (generated)
├── assets/
│   └── icon.icns        # App icon
├── package.json         # Dependencies & scripts
├── tsconfig.json        # TypeScript config
├── electron-builder.json # Build config
└── README.md            # This file
```

### npm Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Run in development mode |
| `npm run build` | Build frontend + Electron |
| `npm run build:frontend` | Build Next.js static export |
| `npm run build:electron` | Compile TypeScript |
| `npm run dist` | Create production package |
| `npm run dist:mac` | Create macOS .dmg installer |
| `npm run clean` | Remove build artifacts |

### Debugging

**Enable DevTools in Production**:

Edit `desktop/src/main.ts`:
```typescript
const isDev = true; // Force dev mode
```

Then rebuild: `npm run build:electron && npm run dev`

**Logs Location**:
- Development: Terminal output + Chrome DevTools
- Production: `~/Library/Logs/Cerebros/main.log`

### Making Changes

**Electron Code** (`main.ts`, `preload.ts`):
```bash
# 1. Make changes
# 2. Rebuild TypeScript
npm run build:electron
# 3. Restart app
npm run dev
```

**Frontend Code** (React/Next.js):
```bash
# Changes auto-reload in dev mode
# For production build:
npm run build:frontend
```

---

## 🎨 Creating App Icon

**Prerequisites**: 1024x1024 PNG image

```bash
# 1. Create/obtain your icon (1024x1024 PNG)
# 2. Run icon generator
./create-icon.sh your-icon-1024.png

# This creates: assets/icon.icns
# electron-builder.json already configured to use it
```

**Icon Requirements**:
- **Size**: 1024x1024 pixels
- **Format**: PNG with transparency
- **Design**: Simple, recognizable at small sizes (16x16)

**What the script does**:
1. Validates input is 1024x1024
2. Generates all required sizes (16x16 to 1024x1024)
3. Creates .iconset directory
4. Converts to .icns using `iconutil`
5. Cleans up temporary files

---

## 🔐 Code Signing & Notarization

**For distribution outside development**:

### Requirements
- Apple Developer Account ($99/year)
- Developer ID Application certificate
- macOS with Xcode

### Setup

1. **Get Certificate**:
   - Log in to [Apple Developer](https://developer.apple.com/)
   - Certificates → Create → Developer ID Application
   - Download and install in Keychain

2. **Update `electron-builder.json`**:
```json
{
  "mac": {
    "hardenedRuntime": true,
    "gatekeeperAssess": true,
    "entitlements": "entitlements.mac.plist",
    "entitlementsInherit": "entitlements.mac.plist"
  }
}
```

3. **Create `entitlements.mac.plist`**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.security.cs.allow-jit</key>
  <true/>
  <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
  <true/>
  <key>com.apple.security.cs.allow-dyld-environment-variables</key>
  <true/>
</dict>
</plist>
```

4. **Build with Signing**:
```bash
export CSC_LINK=/path/to/certificate.p12
export CSC_KEY_PASSWORD=your_password
npm run dist:mac
```

5. **Notarize** (optional but recommended):
```bash
xcrun notarytool submit dist-app/Cerebros-1.0.0.dmg \
  --apple-id your@email.com \
  --team-id TEAM_ID \
  --password app-specific-password \
  --wait

xcrun stapler staple dist-app/Cerebros.app
```

---

## 🧪 Testing

### Manual Testing Checklist

**Basic Functionality**:
- [ ] App launches without errors
- [ ] Menu bar icon appears
- [ ] Global hotkey shows/hides launcher
- [ ] Escape key hides launcher
- [ ] Command palette opens

**Features**:
- [ ] File search returns results
- [ ] Commands appear in palette
- [ ] Can execute a command (e.g., Weather)
- [ ] Spotify mini-player shows (if authenticated)
- [ ] Preferences open (Cmd+,)
- [ ] Settings persist across restarts

**Production Build**:
- [ ] Build completes without errors
- [ ] .dmg opens and installs to Applications
- [ ] First-run Python setup completes
- [ ] All features work in packaged app

### Automated Tests (Future)

See [TESTING.md](TESTING.md) for automated test setup.

---

## 📊 Performance

**Development Mode**:
- Cold start: ~3-5 seconds
- Memory: ~300-400 MB
- CPU: <10% average

**Production Mode**:
- Cold start (first run): 60-180 seconds (Python setup)
- Cold start (subsequent): ~2-3 seconds
- Hotkey response: <150ms
- Memory: ~200-300 MB
- CPU: <5% idle

---

## 🐛 Troubleshooting

### "npm not found"
```bash
# Install Node.js from nodejs.org
# Or use Homebrew:
brew install node
```

### "Python not found" (production)
```bash
# macOS comes with Python 3
# Verify:
python3 --version

# If missing, install:
brew install python@3.11
```

### "Backend won't start"
```bash
# Check if port 8000 is already in use
lsof -i :8000

# Kill conflicting process
kill -9 <PID>

# Or change port in config.yaml
```

### "Frontend won't load"
```bash
# Check if port 3000 is in use
lsof -i :3000

# In development, Next.js should auto-start
# If not, manually start:
cd frontend
npm run dev
```

### "Hotkey doesn't work"
1. Check System Settings → Keyboard → Shortcuts
2. Look for conflicts with Cmd+Option+Space
3. Change hotkey in Preferences (Cmd+,)

### "App won't open" (production)
- **macOS Gatekeeper blocking**:
  - Right-click app → Open → Open (confirm)
  - Or: System Settings → Security & Privacy → Allow
- **Python setup failed**:
  - Check logs: `~/Library/Logs/Cerebros/`
  - Verify Python 3.8+ installed

---

## 📁 File Locations

**Source Code**:
- Project: `/Users/siddharthsuresh/Downloads/auto_mac/`
- Desktop app: `desktop/`
- Frontend: `frontend/`
- Backend: `api_server.py`

**Build Output**:
- Compiled JS: `desktop/dist/`
- Static frontend: `frontend/out/`
- Packaged app: `desktop/dist-app/Cerebros.app`
- DMG installer: `desktop/dist-app/Cerebros-1.0.0.dmg`

**User Data** (created on first run):
- Settings: `~/Library/Application Support/cerebros-launcher/config.json`
- Python venv: `~/Library/Application Support/cerebros-launcher/python-venv/`
- Logs: `~/Library/Logs/Cerebros/`

---

## 🔄 Updating the App

### Version Bump

1. Update `desktop/package.json`:
```json
{
  "version": "1.1.0"
}
```

2. Rebuild:
```bash
npm run clean
npm run dist:mac
```

3. Distribute new DMG

---

## 📚 Related Documentation

- **[BUILD_AND_DEPLOY.md](BUILD_AND_DEPLOY.md)** - Comprehensive build guide
- **[PREFERENCES_GUIDE.md](PREFERENCES_GUIDE.md)** - Settings documentation
- **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)** - Feature status
- **[PRODUCTION_PACKAGING_PLAN.md](PRODUCTION_PACKAGING_PLAN.md)** - Architecture details

---

## 💡 Tips & Tricks

**Faster Development**:
- Keep backend/frontend running in separate terminals
- Only rebuild Electron when changing `main.ts` or `preload.ts`

**Reduce Build Time**:
- Use `npm run pack` instead of `dist` for quick testing (creates .app without .dmg)

**Debug Production Issues**:
- Enable DevTools (edit isDev flag)
- Check Console.app for logs
- Verify paths with `console.log(process.resourcesPath)`

**Clean Install**:
```bash
# Remove all build artifacts and dependencies
npm run clean
rm -rf node_modules
rm -rf ../frontend/node_modules
rm -rf ../frontend/out

# Reinstall
npm install
cd ../frontend && npm install
```

---

## 🎉 Success Criteria

Your Cerebros launcher is working correctly if:

✅ Global hotkey shows/hides launcher instantly
✅ Command palette shows both actions and files
✅ Can execute commands (try Weather or Spotify)
✅ File search returns results
✅ Spotify mini-player appears (if authenticated)
✅ Preferences save and persist
✅ App survives restart

---

## 🆘 Getting Help

1. **Check documentation** in `desktop/` folder
2. **Review logs**:
   - Dev: Terminal output
   - Prod: `~/Library/Logs/Cerebros/`
3. **Common issues**: See Troubleshooting section above
4. **File an issue**: Include logs and steps to reproduce

---

**Ready to launch!** 🚀

Press **`Cmd+Option+Space`** and enjoy your Raycast-style AI launcher.
