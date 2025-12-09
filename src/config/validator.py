"""Thin compatibility layer for the config validator."""

from src.config_validator import ConfigAccessor, ConfigValidationError

__all__ = ["ConfigAccessor", "ConfigValidationError"]
