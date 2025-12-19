"""
Compatibility helpers for running with Pydantic v2 while depending on
libraries (e.g., langchain) that still rely on the deprecated v1 APIs.

LangChain < 0.2 continues to use ``@root_validator`` without setting
``skip_on_failure=True`` which Pydantic v2 now requires. Rather than force
the entire project to downgrade to Pydantic v1, we patch the decorator to
default the flag for post-validation validators. This mirrors the historic
behavior and prevents import-time crashes until upstream dependencies are
fully v2-compatible.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _get_major_version() -> int:
    try:
        import pydantic  # type: ignore
    except Exception:
        return 0

    version = getattr(pydantic, "__version__", "0")
    try:
        return int(version.split(".", 1)[0])
    except (ValueError, TypeError):
        return 0


def _patch_root_validator() -> None:
    """Patch pydantic's root_validator to default skip_on_failure."""
    major = _get_major_version()
    if major < 2:
        return

    try:
        from pydantic import root_validator as public_root_validator  # type: ignore
        from pydantic.deprecated import class_validators  # type: ignore
    except Exception:
        return

    original_root_validator: Callable[..., Any] = class_validators.root_validator

    def patched_root_validator(*args: Any, **kwargs: Any):
        if "skip_on_failure" not in kwargs and not kwargs.get("pre", False):
            kwargs["skip_on_failure"] = True
        return original_root_validator(*args, **kwargs)

    class_validators.root_validator = patched_root_validator
    try:
        import pydantic

        pydantic.root_validator = patched_root_validator  # type: ignore[attr-defined]
    except Exception:
        pass

    logger.info("[PYDANTIC COMPAT] Enabled root_validator compatibility shim")


def _patch_smart_deepcopy() -> None:
    """Handle deepcopy failures for callables/classmethods in pydantic.v1."""
    major = _get_major_version()
    if major < 2:
        return

    try:
        from pydantic.v1 import utils as v1_utils  # type: ignore
    except Exception:
        try:
            from pydantic import utils as v1_utils  # type: ignore
        except Exception:
            return

    original_smart_deepcopy = v1_utils.smart_deepcopy

    def patched_smart_deepcopy(obj: Any):
        try:
            return original_smart_deepcopy(obj)
        except TypeError:
            logger.debug(
                "[PYDANTIC COMPAT] smart_deepcopy fallback for %s",
                type(obj).__name__,
                exc_info=True,
            )
            return obj

    v1_utils.smart_deepcopy = patched_smart_deepcopy
    try:
        from pydantic.v1 import fields as v1_fields  # type: ignore

        v1_fields.smart_deepcopy = patched_smart_deepcopy
    except Exception:
        pass

    logger.info("[PYDANTIC COMPAT] Enabled smart_deepcopy compatibility shim")


_patch_root_validator()
_patch_smart_deepcopy()
