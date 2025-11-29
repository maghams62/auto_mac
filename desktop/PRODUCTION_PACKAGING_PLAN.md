# Production Packaging Plan - Cerebros Launcher

## Current Issues

### P0 CRITICAL Problems

1. **Hardcoded localhost URLs**
   - `main.ts` line 161: `const url = isDev ? 'http://localhost:3000' : 'http://localhost:3000';`
   - Production still loads localhost:3000 instead of bundled frontend

2. **Missing Next.js export configuration**
   - Next.js needs `output: 'export'` for static export
   - Currently tries to run dev server in production

3. **Python venv bundling issues**
   - Bundling entire venv is 100+ MB
   - venv paths are machine-specific (won't work on different Macs)
   - Need portable Python distribution or dependency installer

4. **No build script**
   - No automated way to build production app
   - Manual steps required

## Recommended Solution

### Option A: Static Frontend + Portable Backend (Recommended)

**Pros**:
- Smaller app size (~50-80 MB vs 200+ MB)
- Faster startup
- More reliable
- Better security

**Cons**:
- Requires user to install Python dependencies on first run
- More complex initial setup

**Implementation**:

1. **Export Next.js as static HTML**
   ```json
   // frontend/next.config.js
   module.exports = {
     output: 'export',
     distDir: '.next',
     images: {
       unoptimized: true
     }
   }
   ```

2. **Serve static files from Electron**
   ```typescript
   // main.ts
   const url = isDev
     ? 'http://localhost:3000'
     : `file://${path.join(process.resourcesPath, 'frontend', 'out', 'index.html')}`;
   ```

3. **Check Python dependencies on startup**
   ```typescript
   async function ensurePythonDeps() {
     const requirementsPath = path.join(process.resourcesPath, 'requirements.txt');
     const venvPath = path.join(app.getPath('userData'), 'python-venv');

     if (!fs.existsSync(venvPath)) {
       // Create venv and install dependencies
       // Show progress dialog to user
     }
   }
   ```

4. **Bundle only Python source + requirements.txt**
   - Don't bundle venv
   - Create venv in user's Application Support folder
   - Install dependencies on first run

### Option B: Electron Serve (Simpler, Less Optimal)

**Pros**:
- Simpler implementation
- Keep dev workflow mostly the same

**Cons**:
- Larger bundle size
- Still needs to handle Python venv

**Implementation**:

Use `electron-serve` to serve Next.js build:

```typescript
import serve from 'electron-serve';

const loadURL = serve({ directory: 'frontend/out' });

// In createWindow()
if (isDev) {
  mainWindow.loadURL('http://localhost:3000');
} else {
  loadURL(mainWindow);
}
```

## Detailed Implementation Plan (Option A)

### Step 1: Configure Next.js for Static Export

File: `frontend/next.config.mjs`

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  distDir: 'out',
  images: {
    unoptimized: true
  },
  // Base path for production (served from file://)
  basePath: '',
  assetPrefix: ''
};

export default nextConfig;
```

**Test**:
```bash
cd frontend
npm run build
# Should create frontend/out/ directory with static HTML
```

### Step 2: Update Electron to Serve Static Files

File: `desktop/src/main.ts`

```typescript
function createWindow() {
  mainWindow = new BrowserWindow({
    // ... existing config
  });

  const url = isDev
    ? 'http://localhost:3000'
    : `file://${path.join(process.resourcesPath, 'app', 'frontend', 'out', 'index.html')}`;

  console.log('[Window] Loading URL:', url);
  mainWindow.loadURL(url);

  // ... rest
}
```

### Step 3: Update electron-builder Config

File: `desktop/electron-builder.json`

```json
{
  "appId": "com.cerebros.launcher",
  "productName": "Cerebros",
  "directories": {
    "output": "dist-app"
  },
  "mac": {
    "category": "public.app-category.productivity",
    "icon": "assets/icon.icns",
    "target": ["dmg", "zip"],
    "hardenedRuntime": false,
    "gatekeeperAssess": false
  },
  "files": [
    "dist/**/*",
    "assets/**/*",
    "package.json",
    "node_modules/**/*"
  ],
  "extraResources": [
    {
      "from": "../frontend/out",
      "to": "app/frontend/out",
      "filter": ["**/*"]
    },
    {
      "from": "../src",
      "to": "app/src",
      "filter": ["**/*"]
    },
    {
      "from": "../config.yaml",
      "to": "app/config.yaml"
    },
    {
      "from": "../api_server.py",
      "to": "app/api_server.py"
    },
    {
      "from": "../requirements.txt",
      "to": "app/requirements.txt"
    },
    {
      "from": "../prompts",
      "to": "app/prompts",
      "filter": ["**/*"]
    },
    {
      "from": "../data",
      "to": "app/data",
      "filter": ["**/*"]
    }
  ]
}
```

### Step 4: Python Dependency Management

File: `desktop/src/main.ts` (add new function)

```typescript
async function ensurePythonEnvironment(): Promise<boolean> {
  const userDataPath = app.getPath('userData');
  const venvPath = path.join(userDataPath, 'python-venv');
  const requirementsPath = path.join(process.resourcesPath, 'app', 'requirements.txt');

  // Check if venv exists
  if (fs.existsSync(path.join(venvPath, 'bin', 'python'))) {
    console.log('[Python] Virtual environment exists');
    return true;
  }

  console.log('[Python] Creating virtual environment...');

  // Create venv
  try {
    const { exec } = require('child_process');
    await new Promise((resolve, reject) => {
      exec(`python3 -m venv "${venvPath}"`, (error: any) => {
        if (error) reject(error);
        else resolve(null);
      });
    });

    // Install dependencies
    console.log('[Python] Installing dependencies...');
    await new Promise((resolve, reject) => {
      exec(
        `"${path.join(venvPath, 'bin', 'pip')}" install -r "${requirementsPath}"`,
        (error: any) => {
          if (error) reject(error);
          else resolve(null);
        }
      );
    });

    console.log('[Python] Environment ready!');
    return true;
  } catch (error) {
    console.error('[Python] Failed to setup environment:', error);
    return false;
  }
}

// Update startBackend()
function startBackend() {
  const userDataPath = app.getPath('userData');
  const venvPython = isDev
    ? path.join(rootDir, 'venv', 'bin', 'python')
    : path.join(userDataPath, 'python-venv', 'bin', 'python');

  const apiServer = isDev
    ? path.join(rootDir, 'api_server.py')
    : path.join(process.resourcesPath, 'app', 'api_server.py');

  // ... rest of function
}

// Update app.on('ready')
app.on('ready', async () => {
  // ... existing code

  if (!isDev) {
    const pythonReady = await ensurePythonEnvironment();
    if (!pythonReady) {
      console.error('[Cerebros] Failed to setup Python environment');
      // Show error dialog
      return;
    }
  }

  // Start backend and frontend
  startBackend();
  if (isDev) {
    startFrontend(); // Only start Next.js dev server in development
  }

  // ... rest
});
```

### Step 5: Build Script

File: `desktop/package.json`

```json
{
  "scripts": {
    "dev": "tsc && electron .",
    "build": "npm run build:frontend && npm run build:electron && npm run dist",
    "build:frontend": "cd ../frontend && npm run build",
    "build:electron": "tsc",
    "dist": "electron-builder",
    "dist:mac": "electron-builder --mac",
    "clean": "rm -rf dist dist-app ../frontend/out"
  }
}
```

### Step 6: Testing Production Build

```bash
# 1. Build frontend
cd frontend
npm run build
# Verify: frontend/out/ should exist with index.html

# 2. Build Electron
cd ../desktop
npm run build:electron
# Verify: desktop/dist/ should have compiled .js files

# 3. Create distribution
npm run dist:mac
# Verify: desktop/dist-app/Cerebros.app created

# 4. Test the app
open dist-app/Cerebros.app
```

## Size Estimates

### Current (with bundled venv):
- venv: ~150 MB
- Next.js: ~30 MB
- Electron: ~200 MB
- Python source: ~5 MB
- **Total: ~385 MB**

### After optimization (Option A):
- Static frontend: ~10 MB
- Electron: ~200 MB
- Python source: ~5 MB
- Requirements.txt: <1 MB
- **Total: ~215 MB** (43% reduction)
- First-run venv install: ~100 MB in user's home folder

## First-Run Experience

### Current:
1. User opens app
2. App launches immediately
3. (But doesn't work on different machines due to venv paths)

### After Fix:
1. User opens app for first time
2. Shows: "Setting up Python environment... (1-2 minutes)"
3. Progress indicator
4. Environment created in `~/Library/Application Support/cerebros-launcher/python-venv`
5. App launches
6. Subsequent runs: instant (venv already exists)

## Alternative: Use PyInstaller

**Pros**:
- Single binary
- No Python installation required
- Faster startup

**Cons**:
- Complex build process
- Larger size (~300 MB)
- Harder to debug

**Command**:
```bash
pyinstaller --onefile --add-data "src:src" --add-data "prompts:prompts" api_server.py
```

## Migration Path

### Phase 1: Fix Frontend (1-2 hours)
- Configure Next.js static export
- Update Electron to load from file://
- Test locally

### Phase 2: Fix Backend (2-3 hours)
- Implement Python venv setup
- Add progress indicators
- Test on fresh Mac

### Phase 3: Build Scripts (1 hour)
- Automate build process
- Add clean/test commands
- Document for team

### Phase 4: Testing (2 hours)
- Test on fresh Mac without dev tools
- Verify all features work
- Check file sizes

### Phase 5: Distribution (1 hour)
- Code signing (optional)
- Notarization (optional)
- Create DMG installer

**Total Estimated Time: 6-9 hours**

## Risks & Mitigation

### Risk 1: Static export breaks dynamic routes
**Mitigation**: Test all pages after export, use fallback pages

### Risk 2: Python installation fails on user's machine
**Mitigation**:
- Check for Python3 before creating venv
- Show helpful error message with install instructions
- Provide manual setup guide

### Risk 3: File:// protocol breaks API calls
**Mitigation**:
- Use absolute URLs for API calls
- Set base URL in environment variable

## Success Criteria

- [ ] App launches on fresh Mac without dev environment
- [ ] Frontend loads without localhost:3000
- [ ] Backend starts with Python dependencies
- [ ] App size under 250 MB
- [ ] First-run setup completes in under 3 minutes
- [ ] All features work (search, commands, preferences)

## Next Steps

1. Start with Phase 1 (Frontend fix)
2. Test thoroughly before Phase 2
3. Document any issues encountered
4. Get feedback before Phase 3

---

**Status**: 📋 Planning Complete - Ready for Implementation
**Priority**: P0 CRITICAL
**Estimated Effort**: 6-9 hours
**Impact**: Required for production distribution
