"""Settings package exposing high-level helpers."""

from .manager import (
    SettingsManager,
    get_global_settings_manager,
    set_global_settings_manager,
)

__all__ = [
    "SettingsManager",
    "get_global_settings_manager",
    "set_global_settings_manager",
]
