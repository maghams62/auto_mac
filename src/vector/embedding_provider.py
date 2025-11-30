from __future__ import annotations

import logging
import math
from typing import List, Optional, Sequence

from ..utils.openai_client import PooledOpenAIClient

logger = logging.getLogger(__name__)


class EmbeddingProvider:
    """Thin wrapper around OpenAI embeddings with batching + normalization."""

    def __init__(self, config, *, client=None):
        self.config = config
        self.embedding_model = (
            config.get("vectordb", {}).get("embedding_model")
            or config.get("openai", {}).get("embedding_model")
            or "text-embedding-3-small"
        )
        self.client = client or PooledOpenAIClient.get_client(config)

    def embed(self, text: str) -> Optional[List[float]]:
        embeddings = self.embed_batch([text])
        return embeddings[0] if embeddings else None

    def embed_batch(self, texts: Sequence[str], batch_size: int = 32) -> List[Optional[List[float]]]:
        cleaned = [(text or "").strip() for text in texts]
        results: List[Optional[List[float]]] = [None] * len(cleaned)
        if not cleaned:
            return results

        max_chars = 8000
        for start in range(0, len(cleaned), batch_size):
            batch = cleaned[start : start + batch_size]
            try:
                response = self.client.embeddings.create(
                    model=self.embedding_model,
                    input=[text[:max_chars] for text in batch],
                )
            except Exception as exc:
                logger.warning("[EMBEDDINGS] Batch generation failed (%s); falling back per-text", exc)
                for idx, text in enumerate(batch, start=start):
                    results[idx] = self._embed_single(text[:max_chars])
                continue

            for offset, item in enumerate(response.data):
                normalized = self._normalize(item.embedding)
                results[start + offset] = normalized

        return results

    def _embed_single(self, text: str) -> Optional[List[float]]:
        if not text:
            return None
        try:
            resp = self.client.embeddings.create(model=self.embedding_model, input=text)
            return self._normalize(resp.data[0].embedding)
        except Exception as exc:
            logger.error("[EMBEDDINGS] Failed to embed text: %s", exc)
            return None

    @staticmethod
    def _normalize(vector: Sequence[float]) -> List[float]:
        norm = math.sqrt(sum(v * v for v in vector))
        if norm <= 0:
            return list(vector)
        return [v / norm for v in vector]

