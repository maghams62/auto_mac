"""
Lightweight re-export helpers for config context access.

We defer importing the heavy `context` module until callers request it to
avoid circular-import issues with `config_validator`.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .context import ConfigContext as _ConfigContext


def get_config_context():
    from .context import get_config_context as _get_config_context

    return _get_config_context()


if TYPE_CHECKING:
    ConfigContext = _ConfigContext  # type: ignore[misc,assignment]
else:
    ConfigContext = "ConfigContext"

__all__ = ["ConfigContext", "get_config_context"]
