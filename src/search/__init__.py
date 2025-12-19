"""
Search package - universal search + indexing helpers.
"""

from .config import (
    load_search_config,
    ModalityConfig,
    PlannerConfig,
    PlannerRule,
    SearchConfig,
    SearchDefaults,
)
from .registry import ModalityState, SearchRegistry
from .schema import UniversalEmbeddingPayload, build_context_chunk
from .modalities import BaseModalityHandler
from .bootstrap import build_search_system
from .query_planner import plan_modalities

__all__ = [
    "load_search_config",
    "ModalityConfig",
    "PlannerConfig",
    "PlannerRule",
    "SearchConfig",
    "SearchDefaults",
    "SearchRegistry",
    "ModalityState",
    "BaseModalityHandler",
    "build_search_system",
    "UniversalEmbeddingPayload",
    "build_context_chunk",
    "plan_modalities",
]

