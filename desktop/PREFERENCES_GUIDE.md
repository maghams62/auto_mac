# Cerebros Preferences Guide

## Overview

Cerebros now has a fully functional preferences system using `electron-store` for persistent settings across app restarts.

## Features

### ✅ Implemented Settings

1. **Global Hotkey** - Customize the keyboard shortcut to show/hide launcher
2. **Hide on Blur** - Toggle whether window hides when it loses focus
3. **Start at Login** - Automatically launch Cerebros when you log in
4. **Theme** - Choose between Dark, Light, or Auto (system)

### 🎯 Default Settings

```typescript
{
  hotkey: 'CommandOrControl+Alt+Space',  // Cmd+Option+Space on macOS
  hideOnBlur: true,                      // Hide when window loses focus
  startAtLogin: false,                   // Don't start automatically
  theme: 'dark'                          // Dark mode by default
}
```

## How to Access Preferences

### Method 1: Keyboard Shortcut
Press **`Cmd+,`** (Command + Comma) while the launcher is open

### Method 2: Tray Menu
Right-click the Cerebros icon in the menu bar → **Preferences...**

### Method 3: Programmatic (Event Bus)
```typescript
eventBus.publish("open-preferences");
```

## Settings Reference

### Global Hotkey

**Format**: Electron accelerator string

**Examples**:
- `CommandOrControl+Space` - Cmd+Space (macOS) or Ctrl+Space (Windows/Linux)
- `CommandOrControl+Alt+Space` - Cmd+Option+Space (default)
- `CommandOrControl+Shift+L` - Cmd+Shift+L
- `Alt+Space` - Option+Space

**Note**: Avoid conflicts with system shortcuts:
- `CommandOrControl+Space` conflicts with Spotlight on macOS
- Use `CommandOrControl+Alt+Space` as safe default

### Hide on Blur

**Type**: Boolean toggle

**When Enabled** (default):
- Launcher hides automatically when you click outside
- Raycast/Spotlight-like behavior
- Quick access, minimal distraction

**When Disabled**:
- Launcher stays visible until explicitly closed
- Useful for multi-monitor setups
- Better for extended work sessions

### Start at Login

**Type**: Boolean toggle

**When Enabled**:
- Cerebros launches automatically when you log in
- Opens hidden in background (menu bar only)
- Ready to use immediately with hotkey

**When Disabled** (default):
- Must manually start Cerebros
- Saves system resources if not used daily

### Theme

**Options**: Dark | Light | Auto

**Dark Mode**:
- Dark background, light text
- Reduces eye strain in low light
- Default for most users

**Light Mode**:
- Light background, dark text
- Better for bright environments

**Auto Mode**:
- Follows system appearance settings
- Switches automatically with macOS theme
- Recommended for adaptive workflows

## Implementation Details

### Storage Location

Settings are stored using `electron-store` at:
```
~/Library/Application Support/cerebros-launcher/config.json
```

On macOS, this follows Apple's standard app preferences location.

### IPC Architecture

```
┌─────────────────────────────────────────────────┐
│  Renderer (React/Next.js)                       │
│  - PreferencesModal component                   │
│  - Calls window.electronAPI.getSettings()       │
│  - Calls window.electronAPI.updateSettings()    │
└─────────────────────────────────────────────────┘
                    ↕ (IPC)
┌─────────────────────────────────────────────────┐
│  Preload Script (Bridge)                        │
│  - Exposes safe APIs via contextBridge          │
│  - getSettings() → ipcRenderer.invoke()         │
│  - updateSettings() → ipcRenderer.send()        │
└─────────────────────────────────────────────────┘
                    ↕ (IPC)
┌─────────────────────────────────────────────────┐
│  Main Process (Electron)                        │
│  - ipcMain.handle('get-settings')               │
│  - ipcMain.on('update-settings')                │
│  - Reads/writes from electron-store             │
│  - Re-registers hotkeys on change               │
│  - Updates login items on change                │
└─────────────────────────────────────────────────┘
```

### Hot Reload Behavior

When settings change:

1. **Hotkey Change**:
   - Unregisters old hotkey
   - Saves new hotkey to store
   - Registers new hotkey immediately
   - No app restart required

2. **Start at Login Change**:
   - Calls `app.setLoginItemSettings()`
   - Updates macOS login items immediately
   - Takes effect on next login

3. **Hide on Blur Change**:
   - Updates store value
   - Applied on next blur event
   - No restart required

4. **Theme Change**:
   - Updates store value
   - Frontend reads theme on mount
   - May require page refresh for full effect

## Usage Examples

### Change Hotkey to Cmd+Space

1. Open Preferences (Cmd+,)
2. Click in "Global Hotkey" field
3. Type: `CommandOrControl+Space`
4. Click **Save**
5. Test: Press Cmd+Space → Launcher should appear

### Enable Start at Login

1. Open Preferences
2. Toggle **Start at Login** switch ON
3. Click **Save**
4. Log out and log back in → Cerebros starts automatically

### Disable Hide on Blur (Keep Window Open)

1. Open Preferences
2. Toggle **Hide on Blur** switch OFF
3. Click **Save**
4. Click outside launcher → Window stays open

## Keyboard Shortcuts in Preferences

| Shortcut | Action |
|----------|--------|
| `Cmd+,` | Open preferences |
| `Escape` | Close preferences |
| `Tab` | Navigate between fields |
| `Enter` | Save changes |

## Troubleshooting

### Preferences Won't Open

**Check**:
1. Is Cerebros running in Electron mode? (not browser)
2. Check console for errors: `Cmd+Option+I` (DevTools)

**Solution**:
```bash
cd desktop
npm run dev
```

### Hotkey Not Working After Change

**Check**:
1. Did you click **Save**?
2. Is another app using that hotkey?
3. Check System Settings → Keyboard → Shortcuts

**Solution**:
- Restart Cerebros
- Choose a different hotkey
- Remove conflicting shortcuts

### Settings Not Persisting

**Check**:
```bash
cat ~/Library/Application\ Support/cerebros-launcher/config.json
```

**Should show**:
```json
{
  "hotkey": "CommandOrControl+Alt+Space",
  "hideOnBlur": true,
  "startAtLogin": false,
  "theme": "dark"
}
```

**If empty or missing**:
- electron-store may not have write permissions
- Check app sandbox settings

### Start at Login Not Working

**Check macOS Login Items**:
1. System Settings → General → Login Items
2. Look for "Cerebros" in list

**If missing**:
- electron-store may not have permissions
- Try toggling off and on again in Preferences

## Development Notes

### Adding New Settings

1. **Update Settings interface** in `main.ts`:
```typescript
interface Settings {
  hotkey: string;
  hideOnBlur: boolean;
  startAtLogin: boolean;
  theme: 'dark' | 'light' | 'auto';
  newSetting: string;  // Add here
}
```

2. **Add default value**:
```typescript
const store = new Store<Settings>({
  defaults: {
    // ...
    newSetting: 'default value'
  }
});
```

3. **Handle updates** in `setupIPC()`:
```typescript
if (newSettings.newSetting !== undefined) {
  store.set('newSetting', newSettings.newSetting);
  // Apply changes immediately if needed
}
```

4. **Update UI** in `PreferencesModal.tsx`:
```tsx
const handleNewSettingChange = (value: string) => {
  if (!settings) return;
  setSettings({ ...settings, newSetting: value });
};
```

5. **Update TypeScript types** in `frontend/types/electron.d.ts`

## API Reference

### Electron Main Process

```typescript
// Get all settings
const settings = store.store;

// Get single setting
const hotkey = store.get('hotkey');

// Set single setting
store.set('hotkey', 'CommandOrControl+Space');

// Set multiple settings
store.set({
  hotkey: 'CommandOrControl+Space',
  hideOnBlur: false
});

// Reset to defaults
store.clear();
```

### Renderer Process

```typescript
// Get settings
const settings = await window.electronAPI.getSettings();
console.log(settings.hotkey); // "CommandOrControl+Alt+Space"

// Update settings
await window.electronAPI.updateSettings({
  hotkey: 'CommandOrControl+Space',
  startAtLogin: true
});
```

## Security Considerations

- Settings stored in user's Application Support folder (secure)
- No sensitive data stored (only UI preferences)
- IPC handlers validate input before applying
- Hotkeys validated against Electron accelerator format
- No arbitrary code execution

## Future Enhancements

Potential additions for Phase 8+:

- [ ] Custom launcher width/height
- [ ] Results limit (max items to show)
- [ ] Animation speed preferences
- [ ] Indexed folders configuration
- [ ] Excluded file types
- [ ] Custom CSS/themes
- [ ] Backup/restore settings
- [ ] Import/export preferences
- [ ] Multi-profile support

## Related Files

- Main implementation: [desktop/src/main.ts](src/main.ts)
- Preload bridge: [desktop/src/preload.ts](src/preload.ts)
- UI component: [frontend/components/PreferencesModal.tsx](../frontend/components/PreferencesModal.tsx)
- Integration: [frontend/app/ClientLayout.tsx](../frontend/app/ClientLayout.tsx)
- Type definitions: [frontend/types/electron.d.ts](../frontend/types/electron.d.ts)

## Support

For issues with preferences:
1. Check console logs
2. Verify file permissions
3. Reset to defaults: Delete `~/Library/Application Support/cerebros-launcher/config.json`
4. Report bugs in GitHub issues

---

**Last Updated**: November 26, 2024
**Status**: ✅ Fully Implemented (P1 HIGH complete)
