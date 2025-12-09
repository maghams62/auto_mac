from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ...synthetic.mappings import DOC_API_MAP, DOC_COMPONENT_MAP, services_for_components
from ..canonical_ids import CanonicalIdRegistry
from ..embedding_provider import EmbeddingProvider
from ..vector_event import VectorEvent
from ..vector_store_factory import create_vector_store

logger = logging.getLogger(__name__)


class DocVectorIndexer:
    """Embeds synthetic documentation pages for vector retrieval."""

    def __init__(
        self,
        config,
        *,
        docs_root: Optional[Path] = None,
        output_path: Optional[Path] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        vector_store=None,
        canonical_registry: Optional[CanonicalIdRegistry] = None,
    ):
        self.config = config
        self.docs_root = (docs_root or Path("data/synthetic_git")).resolve()
        self.output_path = output_path or Path("data/vector_index/doc_index.json")
        self.embedding_provider = embedding_provider or EmbeddingProvider(config)
        self.vector_store = vector_store or create_vector_store(
            "docs",
            local_path=self.output_path,
            config=config,
        )
        self.registry = canonical_registry or CanonicalIdRegistry.from_file()
        backend = os.getenv("VECTOR_BACKEND") or (config.get("vectordb") or {}).get("backend") or "local"
        backend = backend.strip().lower()
        target = getattr(self.vector_store, "collection", str(self.output_path))
        logger.info("[DOC INDEXER] Using vector backend='%s' target='%s'", backend, target)

    def build(self) -> Dict[str, int]:
        docs = [self._build_vector_event(doc_id) for doc_id in sorted(self.registry.docs)]
        docs = [event for event in docs if event is not None]
        if not docs:
            logger.warning("[DOC INDEXER] No documentation events were generated.")
            return {"indexed": 0}

        texts = [event.text for event in docs]
        embeddings = self.embedding_provider.embed_batch(texts, batch_size=16)
        for event, embedding in zip(docs, embeddings):
            event.embedding = embedding

        ready = [event for event in docs if event.embedding]
        if not ready:
            logger.error("[DOC INDEXER] No documentation embeddings were produced.")
            return {"indexed": 0}

        self.vector_store.upsert(ready)
        logger.info("[DOC INDEXER] Indexed %s doc sections", len(ready))
        return {"indexed": len(ready)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_vector_event(self, doc_id: str) -> Optional[VectorEvent]:
        path = self._resolve_doc_path(doc_id)
        if not path:
            logger.warning("[DOC INDEXER] Missing doc file for %s", doc_id)
            return None

        text = path.read_text(encoding="utf-8")
        title = self._extract_title(text) or doc_id
        timestamp = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

        components = DOC_COMPONENT_MAP.get(doc_id, [])
        services = services_for_components(components)
        apis = DOC_API_MAP.get(doc_id, [])

        metadata = {
            "doc_path": doc_id,
            "components": components,
            "services": services,
        }

        vector_event = VectorEvent(
            event_id=f"doc:{doc_id}",
            source_type="doc",
            text=f"{title}\n\n{text.strip()}",
            timestamp=timestamp,
            service_ids=services,
            component_ids=components,
            apis=apis,
            labels=["doc_section"],
            metadata=metadata,
        )
        return vector_event

    def _resolve_doc_path(self, doc_rel_path: str) -> Optional[Path]:
        """
        Resolve a canonical doc path (from canonical_ids.yaml) to a concrete file.

        We only ever return real files – not directories – to avoid crashes when a
        path like 'src/pages/Pricing.tsx' happens to exist as a directory in a
        built site tree (e.g. docs-portal/site/src/pages/Pricing.tsx).
        """
        candidate = self.docs_root / doc_rel_path
        if candidate.is_file():
            return candidate

        # Fallback: search recursively, but only return files.
        matches = [path for path in self.docs_root.glob(f"**/{doc_rel_path}") if path.is_file()]
        return matches[0] if matches else None

    @staticmethod
    def _extract_title(text: str) -> Optional[str]:
        for line in text.splitlines():
            line = line.strip()
            if line:
                return line.lstrip("# ").strip()
        return None

