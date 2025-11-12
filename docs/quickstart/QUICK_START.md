# Quick Start - Testing Your Changes

## The One Command You Need

```bash
./start_ui.sh
```

This script does **everything** to give you a clean testing environment:

## What Happens Automatically

```
✓ Kills old servers (no stale code)
✓ Clears Python cache (__pycache__, .pyc files)
✓ Clears frontend cache (.next directory)
✓ Frees ports 3000 & 8000
✓ Checks for import errors
✓ Starts fresh servers with your latest code
```

## After Running

- **Backend API:** http://localhost:8000
- **Frontend UI:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs

## Your Workflow

```bash
# 1. Make your changes
vim src/agent/file_agent.py
# or
vim prompts/task_decomposition.md
# or
vim frontend/components/ChatInterface.tsx

# 2. Run the script
./start_ui.sh

# 3. Test immediately
# All your changes are now active!
```

## Stop Servers

Press `Ctrl+C` in the terminal running start_ui.sh

## View Logs

```bash
# Backend logs
tail -f api_server.log

# Frontend logs
tail -f frontend.log
```

## That's It!

No manual steps. No cache issues. No stale code. Just test!

---

## Common Commands

```bash
# Start everything (clean state)
./start_ui.sh

# Check for import issues (runs automatically in start_ui.sh)
python tests/import_checks/check_all_imports.py

# Test critical imports (runs automatically in start_ui.sh)
python tests/import_checks/test_critical_imports.py

# View backend logs
tail -f api_server.log

# View frontend logs
tail -f frontend.log
```

## Files You'll Edit Most

```
src/agent/          # Agent logic
prompts/            # LLM prompts
frontend/           # React UI
config.yaml         # Configuration
```

After editing any of these, just run `./start_ui.sh` to test!
