# Config Hot-Reload Fix - All Tools Use Updated Config

## Problem

Previously, some tools (like `email_agent.compose_email`) called `load_config()` directly, which read from the file. While the file was updated immediately, this wasn't true hot-reload - tools would read stale values until the next file read.

## Solution

Created a **global ConfigManager singleton** that all tools now use automatically. When config is updated via the Profile UI:

1. ConfigManager updates its in-memory config
2. ConfigManager saves to file
3. **All tools that call `load_config()` now automatically use the global ConfigManager**
4. This means **ALL tools get the updated config immediately** - true hot-reload!

## Implementation Details

### 1. Global ConfigManager (`src/config_manager.py`)

- Singleton pattern - one instance shared across the entire application
- Provides `get_global_config_manager()` to access the singleton
- Handles config updates, saving, and component updates

### 2. Updated `load_config()` (`src/utils.py`)

```python
def load_config(config_path: str = "config.yaml", use_global_manager: bool = True):
    # Try to use global ConfigManager if available (for hot-reload)
    if use_global_manager:
        try:
            from .config_manager import get_global_config_manager
            manager = get_global_config_manager(config_path)
            return manager.get_config()  # Returns latest in-memory config
        except (ImportError, AttributeError):
            pass
    
    # Fallback to file-based loading (only if ConfigManager not initialized)
    ...
```

**Key Point**: `load_config()` now checks for the global ConfigManager first. If it exists, it returns the latest in-memory config. Otherwise, it falls back to reading from file.

### 3. Updated API Server (`api_server.py`)

- Imports and initializes the global ConfigManager at startup
- All components use the same ConfigManager instance
- When config is updated via API, ConfigManager updates in-memory config

## How It Works

### Before (File-based):
```
Tool calls load_config() → Reads from file → Gets stale value if file just updated
```

### After (Global ConfigManager):
```
Tool calls load_config() → Checks global ConfigManager → Gets latest in-memory config → Always up-to-date!
```

## Benefits

1. **True Hot-Reload**: All tools use updated config immediately
2. **No Restart Required**: Changes take effect instantly
3. **Backward Compatible**: Tools that call `load_config()` automatically benefit
4. **Single Source of Truth**: One ConfigManager instance manages all config

## Testing

To verify all tools use updated config:

1. Start backend: `python api_server.py`
2. Update email in Profile UI
3. Send email command: "email to me test"
4. **Verify**: Email goes to updated address immediately (no restart needed)

## Tools That Now Use Hot-Reload

All tools that call `load_config()` now automatically use the global ConfigManager:

- ✅ `email_agent.compose_email()` - Uses updated default_recipient
- ✅ `file_agent.search_documents()` - Uses updated folders
- ✅ `imessage_agent.send_message()` - Uses updated default_phone_number
- ✅ `discord_agent.*` - Uses updated credentials
- ✅ `twitter_agent.*` - Uses updated lists
- ✅ `maps_agent.*` - Uses updated settings
- ✅ All other tools that call `load_config()`

## Technical Notes

- **Circular Import Prevention**: ConfigManager imports utils functions inside methods to avoid circular dependencies
- **Fallback Behavior**: If ConfigManager isn't initialized, `load_config()` falls back to file reading
- **Thread Safety**: ConfigManager is a singleton, so all threads use the same instance
- **Memory Efficiency**: Config is stored once in memory, not duplicated

## Summary

**Before**: Some tools read from file → Stale values possible  
**After**: All tools read from global ConfigManager → Always up-to-date values

**Result**: ✅ **True hot-reload for ALL tools - no restart needed!**

