"""
Vector search and semantic indexing module.

This module provides VectorDB integration for semantic search across
documentation, issues, and other text-based sources.
"""

from .canonical_ids import CanonicalIdRegistry
from .context_chunk import ContextChunk
from .embedding_provider import EmbeddingProvider
from .local_vector_store import LocalVectorStore
from .qdrant_vector_store import QdrantVectorStore
from .vector_search_service import (
    VectorSearchOptions,
    VectorSearchService,
    QdrantVectorSearchService,
)
from .service_factory import get_vector_search_service
from .vector_event import VectorEvent
from .vector_store_factory import create_vector_store

__all__ = [
    "CanonicalIdRegistry",
    "ContextChunk",
    "EmbeddingProvider",
    "LocalVectorStore",
    "QdrantVectorStore",
    "VectorEvent",
    "VectorSearchOptions",
    "VectorSearchService",
    "QdrantVectorSearchService",
    "get_vector_search_service",
    "create_vector_store",
]
