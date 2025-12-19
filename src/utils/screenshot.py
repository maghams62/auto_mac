"""
Utilities for working with screenshot output paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any


DEFAULT_SCREENSHOT_DIR = "data/screenshots"


def get_screenshot_dir(config: Dict[str, Any], ensure_exists: bool = True) -> Path:
    """
    Resolve the base directory for storing screenshots.

    Args:
        config: Loaded configuration dictionary.
        ensure_exists: When True, create the directory if it does not exist.

    Returns:
        Path object pointing to the screenshot directory.
    """
    screenshots_config = (config or {}).get("screenshots", {})
    path_str = screenshots_config.get("base_dir") or DEFAULT_SCREENSHOT_DIR
    path = Path(path_str).expanduser()

    if ensure_exists:
        path.mkdir(parents=True, exist_ok=True)

    return path

