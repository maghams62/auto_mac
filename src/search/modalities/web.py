from __future__ import annotations

import logging
from typing import Any, Dict, List

from ...agent.google_agent import google_search
from ..config import ModalityConfig
from .base import BaseModalityHandler

logger = logging.getLogger(__name__)


class WebSearchModalityHandler(BaseModalityHandler):
    """
    Web search fallback modality that wraps the existing google_search tool.
    """

    def __init__(self, modality_config: ModalityConfig):
        super().__init__(modality_config)

    def can_ingest(self) -> bool:
        return False

    def ingest(self, *, scope_override=None) -> Dict[str, Any]:
        raise RuntimeError("Web search modality does not support ingestion.")

    def query(self, query_text: str, *, limit: int | None = None) -> List[Dict[str, Any]]:
        num_results = min(limit or self.modality_config.max_results, 10)
        payload = google_search.invoke({"query": query_text, "num_results": num_results})
        if payload.get("error"):
            logger.warning("[SEARCH][WEB] Search failed: %s", payload.get("error_message"))
            return []
        results = payload.get("results") or []
        formatted = []
        for item in results[:num_results]:
            formatted.append(
                {
                    "modality": self.modality_config.modality_id,
                    "source_type": "web",
                    "title": item.get("title") or item.get("display_link"),
                    "text": item.get("snippet") or item.get("summary") or "",
                    "score": self.modality_config.weight,  # treat all as equal weight
                    "raw_score": 1.0,
                    "url": item.get("link"),
                    "metadata": {
                        "display_link": item.get("display_link"),
                        "source": payload.get("source"),
                    },
                }
            )
        return formatted

