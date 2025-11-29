# Cerebros Launcher - Build & Deployment Guide

**Last Updated**: November 26, 2024
**Status**: ✅ Production Packaging Complete

## Overview

This guide covers building and deploying Cerebros as a standalone macOS application. The production build uses:
- **Frontend**: Next.js static export (served from `file://`)
- **Backend**: Python with auto-generated venv on first run
- **Packaging**: Electron Builder for .app and .dmg

## Prerequisites

### Development Machine

1. **Node.js 18+**
   ```bash
   node --version  # Should be v18.0.0 or higher
   ```

2. **npm** (comes with Node.js)
   ```bash
   npm --version
   ```

3. **Python 3.8+**
   ```bash
   python3 --version  # Should be 3.8 or higher
   ```

4. **macOS** (for building macOS apps)
   - Xcode Command Line Tools recommended
   - macOS 10.15+ (Catalina or later)

## Build Process

### Step 1: Install Dependencies

```bash
# Root directory
cd /Users/siddharthsuresh/Downloads/auto_mac

# Install Python dependencies (for development)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install

# Install desktop (Electron) dependencies
cd ../desktop
npm install
```

### Step 2: Build Frontend (Static Export)

```bash
cd /Users/siddharthsuresh/Downloads/auto_mac/frontend
npm run build
```

**Output**: `frontend/out/` directory with static HTML/CSS/JS

**Verify**:
```bash
ls -la frontend/out/
# Should see: index.html, _next/, etc.
```

### Step 3: Build Electron App

```bash
cd /Users/siddharthsuresh/Downloads/auto_mac/desktop
npm run build:electron
```

**Output**: `desktop/dist/` directory with compiled JavaScript

**Verify**:
```bash
ls -la desktop/dist/
# Should see: main.js, preload.js
```

### Step 4: Create Distribution Package

```bash
cd /Users/siddharthsuresh/Downloads/auto_mac/desktop

# Create macOS .app and .dmg
npm run dist:mac
```

**Output**: `desktop/dist-app/` directory with:
- `Cerebros.app` - The application bundle
- `Cerebros-1.0.0.dmg` - DMG installer
- `Cerebros-1.0.0-mac.zip` - ZIP archive

**Build Time**: ~2-5 minutes (depending on machine)

## What Gets Packaged

### Bundled Files

The production .app includes:

```
Cerebros.app/
├── Contents/
│   ├── MacOS/
│   │   └── Cerebros (Electron binary)
│   ├── Resources/
│   │   ├── app/
│   │   │   ├── frontend/
│   │   │   │   └── out/          # Static Next.js files
│   │   │   ├── src/              # Python source code
│   │   │   ├── prompts/          # AI prompts
│   │   │   ├── data/             # Data files
│   │   │   ├── api_server.py     # FastAPI server
│   │   │   ├── config.yaml       # Configuration
│   │   │   └── requirements.txt  # Python deps
│   │   ├── electron.asar         # Electron app code
│   │   └── ...
│   └── Info.plist
```

### NOT Bundled (Created on First Run)

```
~/Library/Application Support/cerebros-launcher/
├── config.json              # electron-store settings
└── python-venv/             # Python virtual environment
    ├── bin/
    │   ├── python
    │   └── pip
    └── lib/
        └── python3.x/
            └── site-packages/  # Installed dependencies
```

## First-Run Experience

### On User's Machine (Fresh Mac)

1. User double-clicks `Cerebros.app` or installs from DMG
2. App starts, shows in menu bar
3. Backend detects no venv exists
4. **Automatic setup** (1-3 minutes):
   - Creates `~/Library/Application Support/cerebros-launcher/python-venv/`
   - Installs Python dependencies from `requirements.txt`
   - Shows progress in console (future: show UI progress dialog)
5. Backend starts successfully
6. Frontend loads from static files
7. User can press global hotkey (Cmd+Option+Space)

### Subsequent Runs

- Instant startup (venv already exists)
- No installation phase

## File Size Breakdown

### Development Build
- Next.js dev server: N/A (runs separately)
- Python venv: ~150 MB
- Total: Varies

### Production Build
- Cerebros.app: ~220 MB
  - Electron framework: ~200 MB
  - Static frontend: ~10 MB
  - Python source: ~5 MB
  - Config/data: ~5 MB
- First-run venv install: ~100 MB (in user's home directory)

### DMG Installer
- Size: ~225 MB compressed

## Distribution Checklist

### Before Building

- [ ] Update version in `desktop/package.json`
- [ ] Update `config.yaml` with production settings
- [ ] Test all features in development mode
- [ ] Verify Python dependencies in `requirements.txt`
- [ ] Clean previous builds: `npm run clean`

### Build Commands

```bash
# Full build process
cd /Users/siddharthsuresh/Downloads/auto_mac/desktop
npm run clean                # Remove old builds
npm run build                # Build frontend + electron
npm run dist:mac             # Create .app and .dmg
```

### After Building

- [ ] Test .app on your machine
- [ ] Test .app on a **fresh Mac without dev tools**
- [ ] Verify first-run Python setup works
- [ ] Test all features (commands, preferences, file search)
- [ ] Check app size is reasonable
- [ ] Test DMG installer

## Testing the Build

### On Development Machine

```bash
cd /Users/siddharthsuresh/Downloads/auto_mac/desktop/dist-app
open Cerebros.app
```

### On Fresh Mac (Recommended)

1. **Copy to another Mac** (or use a VM)
2. **Requirements on test machine**:
   - macOS 10.15+ (Catalina or newer)
   - Python 3.8+ (macOS ships with Python 3)
3. **Install from DMG**:
   ```bash
   open Cerebros-1.0.0.dmg
   # Drag Cerebros to Applications
   ```
4. **Launch and test**:
   - Open from Applications folder
   - Wait for first-run setup (1-3 min)
   - Press Cmd+Option+Space
   - Test all features

### Test Checklist

- [ ] App launches without errors
- [ ] First-run Python setup completes successfully
- [ ] Menu bar icon appears
- [ ] Global hotkey works (Cmd+Option+Space)
- [ ] Command palette opens with actions
- [ ] File search works
- [ ] Preferences open (Cmd+,)
- [ ] Settings persist across restarts
- [ ] Backend API responds on localhost:8000
- [ ] No console errors in DevTools (if enabled)

## Troubleshooting Builds

### Build Fails: "Frontend not found"

**Problem**: `frontend/out/` doesn't exist

**Solution**:
```bash
cd frontend
npm run build
# Verify output
ls -la out/
```

### Build Fails: "TypeScript errors"

**Problem**: TypeScript compilation failed

**Solution**:
```bash
cd desktop
npx tsc
# Fix any errors reported
```

### App Won't Start: "Python not found"

**Problem**: Target Mac doesn't have Python 3

**Solution**:
- User needs to install Python 3.8+
- Or: Bundle Python with the app (increases size by ~50-100 MB)

### App Won't Start: "Permission denied"

**Problem**: macOS Gatekeeper blocking unsigned app

**Solution** (for users):
```bash
# Right-click app, select "Open", click "Open" in dialog
# Or: In Security & Privacy settings, allow the app
```

**Solution** (for distribution):
- Sign the app with Apple Developer certificate
- Notarize with Apple (see P3 task)

## Advanced: Code Signing

### Requirements

- Apple Developer Account ($99/year)
- Developer ID Application certificate
- macOS machine with Xcode

### Enable Signing

1. **Update `desktop/electron-builder.json`**:
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

2. **Create `desktop/entitlements.mac.plist`**:
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

3. **Build with signing**:
```bash
export CSC_LINK=/path/to/certificate.p12
export CSC_KEY_PASSWORD=your_password
npm run dist:mac
```

### Notarization

After signing:

```bash
# Submit to Apple for notarization
xcrun notarytool submit Cerebros-1.0.0.dmg \
  --apple-id your@email.com \
  --team-id TEAM_ID \
  --password app-specific-password \
  --wait

# Staple the notarization ticket
xcrun stapler staple Cerebros.app
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Build Cerebros

on:
  push:
    tags:
      - 'v*'

jobs:
  build-macos:
    runs-on: macos-latest

    steps:
    - uses: actions/checkout@v3

    - name: Setup Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '18'

    - name: Install dependencies
      run: |
        cd frontend && npm install
        cd ../desktop && npm install

    - name: Build
      run: |
        cd desktop
        npm run build
        npm run dist:mac

    - name: Upload artifacts
      uses: actions/upload-artifact@v3
      with:
        name: Cerebros-macOS
        path: desktop/dist-app/*.dmg
```

## Release Process

### Version Bump

1. Update `desktop/package.json`:
   ```json
   {
     "version": "1.1.0"
   }
   ```

2. Update changelog (if exists)

3. Commit and tag:
   ```bash
   git add desktop/package.json
   git commit -m "Bump version to 1.1.0"
   git tag v1.1.0
   git push origin main --tags
   ```

### Build Release

```bash
cd desktop
npm run clean
npm run build
npm run dist:mac
```

### Distribute

Upload to:
- GitHub Releases
- Company server
- Direct download link

### Release Checklist

- [ ] Version bumped
- [ ] Changelog updated
- [ ] Clean build completed
- [ ] Tested on fresh Mac
- [ ] DMG installer created
- [ ] Release notes written
- [ ] Tagged in git
- [ ] Uploaded to distribution channel

## Support & Debugging

### Logs Location

**Development**:
- Electron: Console output
- Backend: Terminal where app started
- Frontend: Browser DevTools

**Production**:
- Electron: `~/Library/Logs/Cerebros/main.log`
- Backend: Check Console.app, filter for "Cerebros"
- Frontend: N/A (static files)

### Common User Issues

**"App won't open"**:
- Check macOS version (need 10.15+)
- Check Security & Privacy settings
- Try right-click → Open

**"Commands not working"**:
- Check if backend started (port 8000)
- Check Python installation
- Review first-run setup logs

**"Hotkey not working"**:
- Check for conflicts in System Settings → Keyboard → Shortcuts
- Try changing hotkey in Preferences

### Debug Mode

To enable DevTools in production:

Edit `desktop/src/main.ts`:
```typescript
const isDev = process.env.NODE_ENV === 'development' || true; // Force dev mode
```

Rebuild and DevTools will open automatically.

## Performance Optimization

### Reduce App Size

1. **Minimize frontend assets**:
   - Optimize images
   - Remove unused dependencies
   - Use tree shaking

2. **Prune Python dependencies**:
   ```bash
   pip freeze > requirements.txt
   # Remove unused packages
   ```

3. **Enable compression** in electron-builder:
   ```json
   {
     "compression": "maximum"
   }
   ```

### Improve Startup Time

1. **Lazy load Python modules** in `api_server.py`
2. **Precompile Python** (`.pyc` files)
3. **Cache static assets**
4. **Optimize venv creation** (use `--copies` instead of symlinks)

## Summary

### Quick Build

```bash
# From project root
cd desktop
npm run clean
npm run build      # Builds frontend + electron
npm run dist:mac   # Creates .app and .dmg
```

### Quick Test

```bash
cd desktop/dist-app
open Cerebros.app
```

### File Locations

- **Source**: `/Users/siddharthsuresh/Downloads/auto_mac/`
- **Build output**: `desktop/dist-app/`
- **Packaged app**: `desktop/dist-app/Cerebros.app`
- **DMG installer**: `desktop/dist-app/Cerebros-1.0.0.dmg`
- **User data**: `~/Library/Application Support/cerebros-launcher/`

---

**Questions?** Check:
- [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for feature status
- [PREFERENCES_GUIDE.md](PREFERENCES_GUIDE.md) for settings
- [PRODUCTION_PACKAGING_PLAN.md](PRODUCTION_PACKAGING_PLAN.md) for architecture

**Ready to build!** 🚀
