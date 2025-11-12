# Screenshot Pipeline Audit

## Current Architecture

### Entry Point: Screen Agent Tool
- **File:** `src/agent/screen_agent.py`
- **Tool:** `capture_screenshot(app_name?, output_name?)`
- **Purpose:** Universal screenshot capture for any visible content on screen

### Core Implementation
- **File:** `src/automation/screen_capture.py`
- **Class:** `ScreenCapture`
- **Method:** `capture_screen(app_name?, window_title?, output_path?)`
- **macOS Integration:** Uses `screencapture` command with various flags

### Output Management
- **File:** `src/utils/screenshot.py`
- **Function:** `get_screenshot_dir(config)`
- **Default:** `data/screenshots`
- **Configurable:** Via `config.yaml: screenshots.base_dir`

## Current Behavior

### Capture Modes

#### Full Screen Capture
```bash
screencapture -x -C -t png output_path
```
- Captures entire desktop
- Includes cursor (-C)
- Silent (-x)
- PNG format (-t png)

#### Focused Window Capture (NEW)
**Strategy 1: Quartz CGWindowID (Preferred)**
```bash
screencapture -l <CGWindowID> -x -o -t png output_path
```
- Uses Quartz to find specific window by CGWindowID
- Removes window shadow (-o)
- Captures exact window boundaries

**Strategy 2: AppleScript Bounds (Fallback)**
```bash
screencapture -x -R x,y,width,height -t png output_path
```
- Gets window bounds via AppleScript
- Captures rectangular region
- Works when Quartz unavailable

**Strategy 3: App Activation (Last Resort)**
```bash
screencapture -x -C -t png output_path
```
- Activates app, captures full screen
- App appears prominent in foreground

#### Region Capture (NEW)
```bash
screencapture -x -R x,y,width,height -t png output_path
```
- Captures specific rectangular area
- Coordinates: x,y,width,height from top-left

### Output Path Logic
- **Auto-generated**: `{app_name}_{timestamp}.png` (focused), `region_{timestamp}.png` (region), `screen_{timestamp}.png` (full)
- **Custom**: `{output_name}.png` when `output_name` parameter provided
- **Config-driven**: Always saved to `screenshots.base_dir` from config.yaml
- **macOS default**: Desktop folder (independent of tool paths)

## Implementation Status

### ✅ COMPLETED: Universal Focused-Window Capture
- **File:** `src/automation/screen_capture.py`
- **Method:** `_capture_focused_window()`
- **Fallback Chain:**
  1. Quartz CGWindowID (preferred, shadow-free)
  2. AppleScript bounds (region-based fallback)
  3. App activation (full-screen last resort)
- **Available for all apps:** Weather, Safari, Stocks, any macOS application

## Configuration

### Default Paths
- **Repo screenshot directory**: `data/screenshots` (configured via `screenshots.base_dir` in `config.yaml`)
- **macOS system default**: Desktop folder (check with `defaults read com.apple.screencapture location`)
- Config key: `screenshots.base_dir` in `config.yaml`

### Claude Integration
- **Tool:** `capture_screenshot`
- **Parameters:**
  - `app_name` (string, optional): App name for focused capture (e.g., "Weather")
  - `mode` (string, enum): "full", "focused", "region" (default: "full")
  - `output_name` (string, optional): Custom filename prefix
  - `window_title` (string, optional): Window title filter
  - `region` (object, optional): {x, y, width, height} for region mode
- **Returns:** `{screenshot_path, app_name, mode, message}`
- **Weather example:** `capture_screenshot({app_name: "Weather", mode: "focused"})`
- **Paths returned** for downstream use (presentations, etc.)

## Permissions

### macOS Requirements
- **Screen Recording Permission**: Required for `screencapture` command
  - First run may prompt for approval in System Settings > Privacy & Security
  - Grant to your Python/Terminal application
- **Accessibility Permission**: May be needed for AppleScript window bounds
  - System Settings > Privacy & Security > Accessibility

### Verifying Permissions
```bash
# Test basic screencapture
screencapture -x test.png && echo "Permissions OK" || echo "Check Screen Recording permissions"

# Check screenshot directory
ls -la data/screenshots/
```
