import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.automation import stocks_app_automation as saa


def _dummy_run(*args, **kwargs):
    """Stub subprocess.run that always succeeds."""
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def test_capture_stocks_window_uses_focused_window(monkeypatch):
    """Ensure StocksAppAutomation delegates to ScreenCapture for focused-window grabs."""
    capture_calls = []

    class FakeScreenCapture:
        def __init__(self, config):
            capture_calls.append(("init", config))

        def capture_screen(self, app_name=None, output_path=None):
            capture_calls.append(("capture", app_name, output_path))
            # Return success without touching the filesystem
            return {"success": True, "screenshot_path": output_path}

    monkeypatch.setattr(saa, "ScreenCapture", FakeScreenCapture)
    monkeypatch.setattr(saa.subprocess, "run", _dummy_run)
    monkeypatch.setattr(saa.time, "sleep", lambda *_: None)

    automation = saa.StocksAppAutomation(config={})
    result_path = automation._capture_stocks_window("focus_test")

    assert isinstance(result_path, Path)
    assert result_path.name.startswith("focus_test")
    # Ensure capture_screen was invoked specifically for the Stocks app
    capture_entries = [call for call in capture_calls if call[0] == "capture"]
    assert capture_entries, "ScreenCapture.capture_screen was never called"
    assert capture_entries[0][1] == "Stocks"
