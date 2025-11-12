# start_ui.sh - Clean Start Guide

## Overview

The `start_ui.sh` script provides a **completely clean state** every time you run it. It ensures all your latest code changes are active and no stale cache interferes with testing.

## What It Does (6 Steps)

### Step 1: Kill Existing Servers ✓
- Finds and kills any running `api_server.py` processes
- Finds and kills any running frontend (`npm run dev`) processes
- Clears port 3000 (frontend)
- Clears port 8000 (backend)
- **Why:** Ensures no old code is running

### Step 2: Clear Python Cache ✓
- Removes all `__pycache__` directories
- Deletes all `.pyc` files (compiled Python)
- Deletes all `.pyo` files (optimized Python)
- **Why:** Forces Python to reload all modules with your latest changes

### Step 3: Clear Frontend Cache ✓
- Removes `.next` build cache
- Removes `node_modules/.cache`
- **Why:** Forces Next.js to rebuild with latest React components

### Step 4: Verify Environment ✓
- Checks if virtual environment exists
- Activates virtual environment
- Checks if Node modules are installed
- **Why:** Ensures dependencies are ready

### Step 5: Run Import Verification ✓
- Runs `check_all_imports.py` if available
- Reports any import issues
- **Why:** Catches import errors before starting servers

### Step 6: Start Servers ✓
- Starts backend API server (port 8000)
- Starts frontend UI server (port 3000)
- Logs output to `api_server.log` and `frontend.log`
- **Why:** Gets everything running with fresh code

## Usage

```bash
./start_ui.sh
```

That's it! The script handles everything else.

## What You'll See

```
========================================
Mac Automation Assistant - Clean Start
========================================

[1/6] Stopping any existing servers...
  - Found running API server(s): 45532
  ✓ Killed API server(s)
  ✓ Cleared port 8000
  ✓ All existing servers stopped

[2/6] Clearing Python cache...
  - Removing 127 __pycache__ directories...
  ✓ Removed __pycache__ directories
  ✓ Python cache cleared

[3/6] Clearing frontend cache...
  - Removing .next build cache...
  ✓ Removed .next cache
  ✓ Frontend cache cleared

[4/6] Verifying environment setup...
  ✓ Virtual environment activated
  ✓ Node modules found
  ✓ Environment verified

[5/6] Running import verification tests...
  - Checking for import issues...
  ✓ No import issues found
  ✓ Verification complete

[6/6] Starting servers with fresh code...
  - Starting backend API server on port 8000...
  ✓ Backend started (PID: 98765)
  - Starting frontend UI on port 3000...
  ✓ Frontend started (PID: 98766)

========================================
✓ ALL SYSTEMS READY - CLEAN STATE
========================================

Backend API:       http://localhost:8000
Frontend UI:       http://localhost:3000
API Docs:          http://localhost:8000/docs

Logs:
  Backend:  tail -f api_server.log
  Frontend: tail -f frontend.log

Clean State Features:
  ✓ All old servers killed
  ✓ Python cache cleared (__pycache__, .pyc, .pyo)
  ✓ Frontend cache cleared (.next)
  ✓ Ports 3000 & 8000 freed
  ✓ Fresh code loaded
  ✓ Import issues checked

Press Ctrl+C to stop both servers
All changes you made are now active!
```

## Stopping Servers

Press `Ctrl+C` in the terminal where start_ui.sh is running. The script will:
- Gracefully stop backend
- Gracefully stop frontend
- Show confirmation

## Logs

If something goes wrong, check the logs:

```bash
# Backend logs
tail -f api_server.log

# Frontend logs
tail -f frontend.log
```

## Why This Guarantees Clean State

### Problem 1: Cached Imports
**Without cache clearing:**
- Python caches imports in `.pyc` files
- Old code runs even after you fix it
- **Solution:** We delete all `__pycache__` and `.pyc` files

### Problem 2: Running Old Servers
**Without killing existing processes:**
- Old server keeps running on port 8000
- New server can't start or conflicts
- **Solution:** We kill all existing processes and clear ports

### Problem 3: Frontend Build Cache
**Without clearing `.next`:**
- Next.js uses cached builds
- React changes don't appear
- **Solution:** We delete `.next` directory

### Problem 4: Port Conflicts
**Without checking ports:**
- Something else might be on port 3000 or 8000
- Servers fail to start
- **Solution:** We kill any process using these ports

## Testing New Features

When you make code changes:

1. **Make your changes** (edit Python, React, prompts, etc.)
2. **Run `./start_ui.sh`** - That's it!
3. **Test your feature** - All changes are now active

No need to:
- ❌ Manually kill servers
- ❌ Clear cache yourself
- ❌ Worry about stale code
- ❌ Debug port conflicts

## Troubleshooting

### "Backend failed to start"
Check `api_server.log` for errors:
```bash
tail api_server.log
```

Common causes:
- Python syntax error
- Missing dependency
- Port 8000 still in use (script should handle this, but check with `lsof -ti:8000`)

### "Frontend failed to start"
Check `frontend.log` for errors:
```bash
tail frontend.log
```

Common causes:
- Node modules missing (script should install them)
- Port 3000 still in use
- React syntax error

### "Import issues detected"
The script found import problems but continued. To see details:
```bash
python tests/import_checks/check_all_imports.py
```

## Benefits

✅ **Guaranteed Fresh State** - Every run is like the first run
✅ **All Changes Active** - Code, prompts, configs - all loaded fresh
✅ **No Manual Steps** - Script handles everything
✅ **Safe Testing** - No stale cache causing confusing bugs
✅ **Fast Iteration** - Make change → Run script → Test
✅ **Automatic Verification** - Import checks run before starting

## Comparison: Before vs After

### Before (Manual Process)
```bash
# Find and kill backend
ps aux | grep api_server
kill <pid>

# Find and kill frontend
ps aux | grep "npm run dev"
kill <pid>

# Clear Python cache
find . -name "__pycache__" -delete
find . -name "*.pyc" -delete

# Clear frontend cache
rm -rf frontend/.next

# Start backend
python api_server.py &

# Start frontend
cd frontend && npm run dev &
```

### After (One Command)
```bash
./start_ui.sh
```

## When to Use

**Use this script when:**
- ✅ Testing new features
- ✅ After making code changes
- ✅ After fixing bugs
- ✅ After updating prompts
- ✅ After pulling new code
- ✅ When you want a clean slate
- ✅ **Every time you start development!**

## Summary

`./start_ui.sh` = **Guaranteed clean state with all your latest changes active**

No more wondering if your changes are being used. No more cache issues. No more manual cleanup. Just run the script and test!
