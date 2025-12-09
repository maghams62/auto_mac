"""
Project-local site customizations.

Provides a tiny shim for `packaging.licenses`, which was removed in packaging 24+ but
is still imported by some third-party tooling (pip, poetry plugins, etc.). The shim
unblocks local tooling without mutating the virtualenv.
"""

from __future__ import annotations

import importlib
import sys
import types
from typing import NamedTuple, Optional


def _ensure_packaging_licenses_stub() -> None:
    if "packaging.licenses" in sys.modules:
        return
    try:
        importlib.import_module("packaging.licenses")
        return
    except ModuleNotFoundError:
        pass

    module = types.ModuleType("packaging.licenses")

    class License(NamedTuple):
        key: str
        category: Optional[str] = None
        short_identifier: Optional[str] = None
        long_identifier: Optional[str] = None

    module.License = License
    module.LICENSES: dict[str, License] = {}

    class InvalidLicenseExpression(Exception):
        """Raised when a legacy license expression cannot be parsed."""

    module.InvalidLicenseExpression = InvalidLicenseExpression

    def by_spdx(identifier: str) -> Optional[License]:
        return module.LICENSES.get(identifier)

    module.by_spdx = by_spdx  # type: ignore[attr-defined]

    def canonicalize_license_expression(expression: str) -> str:
        if not isinstance(expression, str):
            raise InvalidLicenseExpression("License expression must be a string.")
        return expression.strip()

    module.canonicalize_license_expression = canonicalize_license_expression  # type: ignore[attr-defined]

    sys.modules["packaging.licenses"] = module


_ensure_packaging_licenses_stub()

