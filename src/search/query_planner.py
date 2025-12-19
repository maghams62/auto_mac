from __future__ import annotations

from typing import List

from .config import SearchConfig


def plan_modalities(question: str, config: SearchConfig, *, include_fallback: bool = False) -> List[str]:
    """
    Determine which modalities should run for a /cerebros query.

    For fallback runs we always return the fallback-only modalities (e.g. web search).
    For primary runs we evaluate the configured planner rules and return either the
    matching modality subset or all enabled modalities if no rule matches.
    """

    fallback_modalities = [
        modality_id
        for modality_id, modality in config.modalities.items()
        if modality.enabled and modality.fallback_only
    ]
    if include_fallback:
        return fallback_modalities

    primary_modalities = [
        modality_id
        for modality_id, modality in config.modalities.items()
        if modality.enabled and not modality.fallback_only
    ]
    planner = getattr(config, "planner", None)
    if not planner or not planner.enabled:
        return primary_modalities

    normalized_query = (question or "").lower()
    primary_set = set(primary_modalities)
    for rule in planner.rules:
        if not rule.matches(normalized_query):
            continue
        planned = [modality_id for modality_id in rule.include if modality_id in primary_set]
        if planned:
            return planned

    return primary_modalities

