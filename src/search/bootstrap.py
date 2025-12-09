from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .config import SearchConfig, load_search_config
from .registry import SearchRegistry
from .modalities import (
    DocIssuesModalityHandler,
    FilesModalityHandler,
    GitModalityHandler,
    SlackModalityHandler,
    WebSearchModalityHandler,
    YouTubeModalityHandler,
)
from ..vector import get_vector_search_service


def build_search_system(
    app_config: Dict[str, Any],
    *,
    state_path: Optional[str | Path] = None,
    vector_service=None,
) -> Tuple[SearchConfig, SearchRegistry]:
    """
    Convenience helper that builds the search configuration + registry with
    default modality handlers wired up.
    """

    search_config = load_search_config(app_config)
    registry = SearchRegistry(
        search_config,
        state_path=state_path or "data/state/search_registry.json",
    )

    if not search_config.enabled:
        return search_config, registry

    vector_svc = vector_service or get_vector_search_service(app_config)

    def register_if_present(modality_id: str, handler_factory):
        modality_cfg = search_config.modalities.get(modality_id)
        if not modality_cfg:
            return
        handler = handler_factory(modality_cfg)
        registry.register_handler(handler)

    register_if_present(
        "slack",
        lambda cfg: SlackModalityHandler(cfg, app_config, vector_service=vector_svc),
    )
    register_if_present(
        "git",
        lambda cfg: GitModalityHandler(cfg, app_config, vector_service=vector_svc),
    )
    register_if_present(
        "doc_issues",
        lambda cfg: DocIssuesModalityHandler(cfg, app_config),
    )
    register_if_present(
        "files",
        lambda cfg: FilesModalityHandler(cfg, app_config, vector_service=vector_svc),
    )
    register_if_present(
        "youtube",
        lambda cfg: YouTubeModalityHandler(cfg, app_config, vector_service=vector_svc),
    )
    register_if_present(
        "web_search",
        lambda cfg: WebSearchModalityHandler(cfg),
    )

    return search_config, registry

