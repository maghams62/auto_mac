# Legacy Test Scripts

This folder contains test scripts that were previously in the project root directory. They have been moved here for organization purposes.

## Purpose

These tests were created during various development phases for:
- Manual testing of specific features
- Debugging specific issues
- One-off verification scripts
- Integration testing during development

## Usage

Most of these scripts can be run directly:

```bash
python tests/legacy/test_<feature>.py
```

## Categories

### Email Tests
- `test_email_*.py` - Email reading, sending, and UI tests
- `test_read_email_*.py` - Email reading API tests

### Spotify Tests
- `test_spotify_*.py` - Spotify playback and API tests
- `test_play_song.py` - Music playback tests
- `test_vision_spotify.py` - Vision-based Spotify control

### Stock/Finance Tests
- `test_stock_*.py` - Stock workflow and report tests

### UI/Frontend Tests
- `test_frontend_backend_connection.py` - Frontend-backend integration
- `test_plan_*.py` - Plan visualization tests
- `test_mountain_image_*.py` - Image display tests

### Integration Tests
- `test_websocket_integration.py` - WebSocket tests
- `test_slack_integration.py` - Slack integration tests
- `test_universal_search_api.py` - Search API tests

### Utility Tests
- `test_reminders_fix.py` - Reminders functionality
- `test_folder_functionality.py` - Folder operations
- `test_file_*.py` - File operations tests

## Note

For new tests, please add them to the appropriate subfolder in `tests/`:
- `tests/unit/` - Unit tests
- `tests/e2e/` - End-to-end tests
- `tests/regression/` - Regression tests
- `tests/integration/` - Integration tests

These legacy tests are preserved for reference and may still be useful for manual testing scenarios.

