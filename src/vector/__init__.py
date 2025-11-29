"""
Vector search and semantic indexing module.

This module provides VectorDB integration for semantic search across
documentation, issues, and other text-based sources.
"""

from .context_chunk import ContextChunk
from .vector_search_service import (
    VectorSearchOptions,
    VectorSearchService,
    QdrantVectorSearchService,
)
from .service_factory import get_vector_search_service

__all__ = [
    "ContextChunk",
    "VectorSearchOptions",
    "VectorSearchService",
    "QdrantVectorSearchService",
    "get_vector_search_service",
]
