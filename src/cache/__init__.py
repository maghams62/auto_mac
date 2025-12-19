"""
Cache utilities for speeding up launcher + backend startup.

This package currently exposes `StartupCacheManager`, a lightweight helper that
persists warm artifacts (prompt bundles, tool manifests, config snapshots) to
disk so the app can hydrate instantly on the next launch.
"""

from .startup_cache import StartupCacheManager  # noqa: F401


