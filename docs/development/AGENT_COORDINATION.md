# Agent Coordination Protocol

This document describes the coordination mechanism for multiple agents working on the same codebase simultaneously.

## Overview

When multiple coding agents work on the same codebase, they need to coordinate to prevent:
- File conflicts
- Code overwrites
- Race conditions
- Lost work

## Coordination System

### Components

1. **Lock Files** (`data/.agent_locks/*.lock`)
   - Created when an agent starts working on a file
   - Contains agent ID, timestamp, file path, and status
   - Automatically cleaned up when work completes or becomes stale

2. **Status Board** (`data/.agent_locks/status_board.json`)
   - Central registry of all active locks
   - Tracks agent assignments
   - Records file modification history
   - Logs conflicts

3. **Message System** (`data/.agent_locks/messages/`)
   - Agents can leave messages for each other
   - Used for handoffs, status updates, coordination

## Protocol

### Before Starting Work

1. **Check for conflicts**
   ```python
   from src.utils.agent_coordination import check_conflicts, acquire_lock
   
   files_to_modify = ["src/agent/enriched_stock_agent.py"]
   conflicts = check_conflicts(files_to_modify, agent_id="my_agent_id")
   
   if conflicts:
       # Wait or request handoff
       for conflict in conflicts:
           print(f"File {conflict['file_path']} is locked by {conflict['locked_by']}")
   ```

2. **Acquire locks**
   ```python
   if acquire_lock("src/agent/enriched_stock_agent.py", agent_id="my_agent_id"):
       try:
           # Do work here
           pass
       finally:
           release_lock("src/agent/enriched_stock_agent.py", agent_id="my_agent_id")
   ```

### During Work

1. **Update status periodically**
   ```python
   from src.utils.agent_coordination import update_status_board
   
   update_status_board(
       agent_id="my_agent_id",
       status="in_progress",
       files=["src/agent/enriched_stock_agent.py"]
   )
   ```

2. **Check for messages**
   ```python
   from src.utils.agent_coordination import read_messages
   
   messages = read_messages(agent_id="my_agent_id")
   for msg in messages:
       print(f"From {msg['from']}: {msg['message']}")
   ```

### After Completing Work

1. **Release locks**
   ```python
   from src.utils.agent_coordination import release_lock
   
   release_lock("src/agent/enriched_stock_agent.py", agent_id="my_agent_id")
   ```

2. **Update status board**
   ```python
   update_status_board(
       agent_id="my_agent_id",
       status="completed",
       files=["src/agent/enriched_stock_agent.py"]
   )
   ```

## Conflict Resolution

### If Conflicts Detected

1. **Wait**: If other agent is actively working (recent lock timestamp)
2. **Request Handoff**: Send message asking other agent to release lock
3. **Work on Different Files**: If possible, modify different files/modules
4. **Stale Locks**: If lock is older than 1 hour, it's considered stale and can be ignored

### Example: Requesting Handoff

```python
from src.utils.agent_coordination import send_message, check_conflicts

conflicts = check_conflicts(["src/agent/enriched_stock_agent.py"])
if conflicts:
    for conflict in conflicts:
        send_message(
            target_agent_id=conflict["locked_by"],
            message="Requesting handoff of enriched_stock_agent.py - need to make enhancements",
            agent_id="my_agent_id"
        )
```

## Best Practices

1. **Always acquire locks before modifying files**
2. **Release locks immediately after work completes**
3. **Check for conflicts before starting**
4. **Update status board during long-running tasks**
5. **Clean up stale locks periodically**
6. **Communicate with other agents via messages when needed**

## Lock Timeout

Locks automatically expire after 1 hour (3600 seconds). This prevents:
- Deadlocks from crashed agents
- Abandoned locks
- Stale state

## Agent ID

Each agent should have a unique identifier:
- Set via `AGENT_ID` environment variable
- Or passed explicitly to coordination functions
- Default: "unknown_agent" (not recommended for production)

## Example: Full Workflow

```python
from src.utils.agent_coordination import (
    check_conflicts, acquire_lock, release_lock,
    update_status_board, read_messages
)

agent_id = "stock_presentation_agent"
files = ["src/agent/enriched_stock_agent.py"]

# Step 1: Check for conflicts
conflicts = check_conflicts(files, agent_id)
if conflicts:
    print(f"Conflicts detected: {conflicts}")
    # Handle conflicts (wait, request handoff, etc.)
    exit(1)

# Step 2: Acquire locks
if not acquire_lock(files[0], agent_id):
    print("Failed to acquire lock")
    exit(1)

try:
    # Step 3: Do work
    update_status_board(agent_id, "in_progress", files)
    
    # ... modify files ...
    
    # Step 4: Update status
    update_status_board(agent_id, "completed", files)
    
finally:
    # Step 5: Release locks
    release_lock(files[0], agent_id)
```

## Maintenance

### Cleanup Stale Locks

```python
from src.utils.agent_coordination import cleanup_stale_locks

cleaned = cleanup_stale_locks()
print(f"Cleaned up {cleaned} stale locks")
```

This should be run periodically (e.g., before starting work) to ensure the lock system stays clean.

