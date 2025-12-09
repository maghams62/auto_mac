from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ...vector import get_vector_search_service
from ...vector.context_chunk import ContextChunk
from ..config import ModalityConfig
from ..schema import UniversalEmbeddingPayload, build_context_chunk
from .base import BaseModalityHandler
from ...graph.service import GraphService
from ...graph.universal_nodes import UniversalNodeWriter

logger = logging.getLogger(__name__)


class FilesModalityHandler(BaseModalityHandler):
    """
    Index local documentation folders specified in config.search.modalities.files.roots.
    """

    SUPPORTED_SUFFIXES = (".md", ".txt", ".rst")

    def __init__(
        self,
        modality_config: ModalityConfig,
        app_config: Dict[str, Any],
        *,
        vector_service=None,
    ):
        super().__init__(modality_config)
        self.app_config = app_config
        self.vector_service = vector_service or get_vector_search_service(app_config)
        self.workspace_id = (app_config.get("search") or {}).get("workspace_id") or "default_workspace"
        self.graph_service = GraphService(app_config)
        self.universal_writer = UniversalNodeWriter(self.graph_service)

    def can_ingest(self) -> bool:
        return bool(self.vector_service)

    def ingest(self, *, scope_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.vector_service:
            raise RuntimeError("Vector service unavailable; cannot index files.")

        roots = _resolve_roots(scope_override, self.modality_config.scope)
        if not roots:
            logger.info("[SEARCH][FILES] No roots configured; skipping.")
            return {"files_indexed": 0}

        total_chunks = 0
        for root in roots:
            chunks = self._build_chunks_for_root(root)
            if not chunks:
                continue
            success = self.vector_service.index_chunks(chunks)
            if success:
                total_chunks += len(chunks)
                self.universal_writer.ingest_chunks(chunks)

        return {"files_indexed": total_chunks, "roots": roots}

    def query(self, query_text: str, *, limit: int | None = None) -> List[Dict[str, Any]]:
        if not self.vector_service:
            return []
        from ...vector import VectorSearchOptions

        options = VectorSearchOptions(
            top_k=limit or self.modality_config.max_results,
            source_types=["file"],
        )
        chunks = self.vector_service.semantic_search(query_text, options)
        return [
            _chunk_to_result(chunk, self.modality_config)
            for chunk in chunks
        ]

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _build_chunks_for_root(self, root: str) -> List[ContextChunk]:
        base = Path(root).expanduser()
        if not base.exists():
            logger.warning("[SEARCH][FILES] Root %s does not exist", base)
            return []

        payloads: List[UniversalEmbeddingPayload] = []
        for file_path in base.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in self.SUPPORTED_SUFFIXES:
                continue
            try:
                text = file_path.read_text(encoding="utf-8")
            except Exception as exc:
                logger.warning("[SEARCH][FILES] Failed to read %s: %s", file_path, exc)
                continue
            payloads.extend(self._chunk_file(file_path, text))

        return [build_context_chunk(payload) for payload in payloads]

    def _chunk_file(self, file_path: Path, text: str) -> Iterable[UniversalEmbeddingPayload]:
        normalized = " ".join(text.split())
        if not normalized:
            return []
        chunk_size = 1000
        overlap = 200
        start = 0
        chunks: List[UniversalEmbeddingPayload] = []
        idx = 0
        while start < len(normalized):
            end = min(len(normalized), start + chunk_size)
            chunk_text = normalized[start:end]
            payload = UniversalEmbeddingPayload(
                workspace_id=self.workspace_id,
                source_type="file",
                source_id=f"{file_path}:{idx}",
                parent_id=str(file_path.parent),
                display_name=file_path.name,
                path=str(file_path),
                start_offset=float(start),
                end_offset=float(end),
                url=f"file://{file_path}",
                modality_tags=["files"],
                extra={"root": str(file_path.parent)},
                text=chunk_text,
            )
            chunks.append(payload)
            idx += 1
            if end == len(normalized):
                break
            start = max(end - overlap, start + 1)
        return chunks


def _resolve_roots(scope_override: Optional[Dict[str, Any]], default_scope: Dict[str, Any]) -> List[str]:
    if scope_override and scope_override.get("roots"):
        return [str(Path(root).expanduser()) for root in scope_override["roots"]]
    if default_scope.get("roots"):
        return [str(Path(root).expanduser()) for root in default_scope["roots"]]
    return []


def _chunk_to_result(chunk: ContextChunk, config: ModalityConfig) -> Dict[str, Any]:
    metadata = chunk.metadata or {}
    score = float(metadata.get("_score", 0.0))
    path = metadata.get("path") or chunk.metadata.get("path")
    title = metadata.get("display_name") or path or "file"
    snippet = chunk.text[:400]
    return {
        "modality": config.modality_id,
        "source_type": chunk.source_type,
        "chunk_id": chunk.chunk_id,
        "entity_id": chunk.entity_id,
        "title": title,
        "text": snippet,
        "score": score * config.weight,
        "raw_score": score,
        "url": metadata.get("url"),
        "metadata": metadata,
    }

