from __future__ import annotations

from functools import lru_cache
from typing import Iterable, List, Optional

from src.graph.dependency_graph import DependencyGraphBuilder
from src.slash_git.models import normalize_alias_token


class ComponentIdResolver:
    """Normalizes component identifiers using dependency map aliases."""

    def __init__(self):
        builder = DependencyGraphBuilder()
        graph = builder.build(write_to_graph=False)
        self._alias_map: dict[str, str] = {}
        for component_id, metadata in graph.components.items():
            self._register(component_id, component_id)
            self._register(metadata.get("name"), component_id)
            for alias in metadata.get("aliases", []) or []:
                self._register(alias, component_id)

    def _register(self, alias: Optional[str], component_id: str) -> None:
        if not alias:
            return
        trimmed = alias.strip()
        if not trimmed:
            return
        self._alias_map.setdefault(trimmed.lower(), component_id)
        normalized = normalize_alias_token(trimmed)
        if normalized:
            self._alias_map.setdefault(normalized, component_id)

    def resolve(self, raw_id: Optional[str]) -> Optional[str]:
        if raw_id is None:
            return None
        trimmed = raw_id.strip()
        if not trimmed:
            return trimmed
        key = trimmed.lower()
        return self._alias_map.get(key, trimmed)


@lru_cache(maxsize=1)
def get_component_id_resolver() -> ComponentIdResolver:
    return ComponentIdResolver()


def resolve_component_id(raw_id: Optional[str]) -> Optional[str]:
    """Return the canonical component identifier for a single raw ID."""
    resolver = get_component_id_resolver()
    return resolver.resolve(raw_id)


def normalize_component_ids(ids: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for raw in ids or []:
        canonical = resolve_component_id(raw)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        normalized.append(canonical)
    return normalized

