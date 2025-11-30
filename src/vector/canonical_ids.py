from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Set

import yaml

DEFAULT_CANONICAL_PATH = Path("config/canonical_ids.yaml")


@dataclass
class CanonicalIdRegistry:
    """Lightweight helper that loads and validates canonical identifiers."""

    services: Set[str]
    components: Set[str]
    apis: Set[str]
    docs: Set[str]

    @classmethod
    def from_file(cls, path: Optional[Path] = None) -> "CanonicalIdRegistry":
        path = path or DEFAULT_CANONICAL_PATH
        data = yaml.safe_load(path.read_text())
        return cls(
            services=set(data.get("services", [])),
            components=set(data.get("components", [])),
            apis=set(data.get("apis", [])),
            docs=set(data.get("docs", [])),
        )

    def snapshot(self) -> str:
        """Return JSON-encoded snapshot (useful for logging)."""
        return json.dumps(
            {
                "services": sorted(self.services),
                "components": sorted(self.components),
                "apis": sorted(self.apis),
                "docs": sorted(self.docs),
            },
            indent=2,
        )

    def assert_valid(
        self,
        *,
        services: Optional[Iterable[str]] = None,
        components: Optional[Iterable[str]] = None,
        apis: Optional[Iterable[str]] = None,
        docs: Optional[Iterable[str]] = None,
        context: str = "",
    ) -> None:
        """Validate provided identifiers against the canonical registry."""

        def _assert(values: Optional[Iterable[str]], allowed: Set[str], label: str) -> None:
            if not values:
                return
            unknown = sorted(set(values) - allowed)
            if unknown:
                raise ValueError(f"{label} contains non-canonical IDs {unknown} (context={context})")

        _assert(services, self.services, "service_ids")
        _assert(components, self.components, "component_ids")
        _assert(apis, self.apis, "apis")
        _assert(docs, self.docs, "docs")

