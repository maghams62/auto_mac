"""
Base class for universal search modality handlers.

Handlers encapsulate ingestion and query logic for a modality (Slack, Git,
files, YouTube, etc.).  The registry wires commands to these handlers
based on the declarative config.
"""

from __future__ import annotations

import abc
from typing import Any, Dict, List

from ..config import ModalityConfig


class BaseModalityHandler(abc.ABC):
    """
    Abstract base class for modality handlers.

    Concrete implementations should override ingest/query with modality
    specific behavior.  The default implementations for `can_ingest` and
    `can_query` return True, but handlers may override them (e.g., web
    search might only support querying).
    """

    def __init__(self, modality_config: ModalityConfig):
        self.modality_config = modality_config

    @property
    def modality_id(self) -> str:
        return self.modality_config.modality_id

    def can_ingest(self) -> bool:
        return True

    def can_query(self) -> bool:
        return True

    @abc.abstractmethod
    def ingest(self, *, scope_override: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Execute ingestion for the modality.

        Returns:
            Dict with structured telemetry (e.g., counts, durations).
        """

    @abc.abstractmethod
    def query(self, query_text: str, *, limit: int | None = None) -> List[Dict[str, Any]]:
        """
        Execute a semantic query for the modality.  The handler is
        responsible for filtering results down to `limit` and returning a
        structured list ready for score normalization.
        """

