# Profile Implementation Verification Guide

## Overview

This document describes how to verify that the Profile UI implementation is working correctly, including:
1. UI can load and display config
2. UI can update config values
3. Config saves to `config.yaml`
4. Backend components use updated config without restart

## Implementation Summary

### Backend Changes

1. **ConfigManager** (`api_server.py`)
   - Singleton pattern for global config access
   - `update_config()` - Merges updates and saves to file
   - `update_components()` - Updates all component references
   - Handles redacted values (won't overwrite with "***REDACTED***")

2. **API Endpoints**
   - `GET /api/config` - Returns sanitized config
   - `PUT /api/config` - Updates config and hot-reloads
   - `POST /api/config/reload` - Force reload from file

3. **Component Updates**
   - AutomationAgent: Config and ConfigAccessor updated
   - AgentRegistry: Config updated, agents updated if instantiated
   - WorkflowOrchestrator: Config and sub-components updated

### Frontend Changes

1. **Profile Component** (`frontend/components/Profile.tsx`)
   - Form sections for all configurable values
   - Deep cloning for state updates
   - Save button with loading states
   - Success/error notifications

2. **Sidebar** (`frontend/components/Sidebar.tsx`)
   - Added "Profile" tab
   - Integrated Profile component

## Verification Steps

### Step 1: Start the Backend

```bash
# In project root
python api_server.py
```

Verify:
- Server starts without errors
- Log shows "ConfigManager initialized"
- Log shows "Component configs updated"

### Step 2: Start the Frontend

```bash
# In frontend directory
cd frontend
npm run dev
```

Verify:
- Frontend starts on http://localhost:3000
- No console errors

### Step 3: Test Profile UI

1. Open http://localhost:3000
2. Click "Profile" tab in sidebar
3. Verify config loads (check browser console for errors)
4. Verify fields are populated with current values

### Step 4: Test Config Update

1. Change "Default Email" field
2. Click "Save" button
3. Verify:
   - Success message appears
   - Config reloads with new value
   - No errors in console

### Step 5: Verify Backend Uses Updated Config

**Option A: Use Test Script**

```bash
python test_config_update.py
```

This will:
- Read config via API
- Update email address
- Verify update persisted
- Restore original value

**Option B: Manual Verification**

1. Update email in Profile UI
2. Check `config.yaml` file - should have new email
3. Send a test email command via chat: "email to me test"
4. Verify email goes to updated address

### Step 6: Test Nested Updates

1. Add a folder in Profile UI
2. Click Save
3. Verify folder appears in list
4. Check `config.yaml` - folder should be added
5. Remove folder
6. Click Save
7. Verify folder removed from list and file

### Step 7: Test Redacted Values

1. In Profile UI, Discord password field should show as empty (if redacted)
2. Enter a new password
3. Click Save
4. Reload Profile tab
5. Password should still be there (not redacted in UI state, but will be redacted in API response)

## Known Limitations

1. **Tools calling `load_config()` directly**: Some tools (like `email_agent.compose_email`) call `load_config()` directly. These will read from file, so updates work but aren't true hot-reload. The file is updated immediately, so next call will use new values.

2. **Agent lazy initialization**: Agents are created lazily. When config is updated, already-instantiated agents are updated, but new agents will use the updated config when created.

3. **ConfigAccessor recreation**: ConfigAccessor is recreated in AutomationAgent and agents that have it. This ensures they use the latest config.

## Troubleshooting

### Config not updating in backend

1. Check backend logs for "[CONFIG MANAGER] Component configs updated"
2. Verify `config.yaml` file was updated
3. Check if components need full reinitialization (some might)

### UI not saving

1. Check browser console for errors
2. Verify API endpoint is accessible: `curl http://localhost:8000/api/config`
3. Check network tab in browser devtools for API call status

### Redacted values overwriting real values

- The deep merge logic skips "***REDACTED***" values
- If you see this issue, check the `deep_merge` function in ConfigManager

## Testing Checklist

- [ ] Profile tab loads config
- [ ] Email field updates and saves
- [ ] Folders can be added/removed
- [ ] Phone number updates
- [ ] Twitter settings update
- [ ] Discord settings update (password handling)
- [ ] Maps settings update
- [ ] Browser settings update
- [ ] Config persists to `config.yaml`
- [ ] Backend uses updated config (test with email command)
- [ ] No backend restart required

## Next Steps for Full Hot-Reload

To achieve true hot-reload for all tools:

1. Create a global ConfigManager singleton that can be imported
2. Update all tools to use `config_manager.get_config()` instead of `load_config()`
3. This is a larger refactoring but would ensure all components use live config

For now, the critical path (AutomationAgent, AgentRegistry, WorkflowOrchestrator) is updated, and file-based tools will pick up changes on next call.

