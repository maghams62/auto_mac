# Server Restart Instructions

## The Issue

The API server is still running with old code that had import errors. Even though we fixed the imports, the running server hasn't reloaded the changes.

## How to Restart the Server

### Option 1: Kill and Restart

```bash
# 1. Find and kill the running server
ps aux | grep "api_server.py" | grep -v grep
kill 45532  # Replace with the actual PID

# 2. Start the server again
python api_server.py
```

### Option 2: Use the PID file (if available)

```bash
# Kill using PID file
kill $(cat api_server.pid)

# Start the server
python api_server.py
```

### Option 3: Kill all Python processes (nuclear option)

```bash
pkill -f api_server.py
python api_server.py
```

## Verify the Server Restarted

After restarting, check that it's running:
```bash
ps aux | grep "api_server.py" | grep -v grep
```

You should see a new process with a different timestamp.

## Test the Fixed Workflow

After the server restarts, try your command again:
```
send the doc with the song Photograph to my email
```

It should now:
1. ✅ Search for the document successfully (no import error)
2. ✅ Attach it to an email
3. ✅ Automatically send it (`send: true` because you said "send")

## Why This Happened

Python caches imported modules in memory. When you run a long-lived server like `api_server.py`, it loads all the modules once at startup. Even if you fix the code files, the server won't see the changes until it restarts.

## Prevent This in the Future

For development, consider using auto-reload:
- Use `uvicorn` with `--reload` flag
- Or manually restart the server after code changes

