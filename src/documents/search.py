"""
Semantic search engine using FAISS.
"""

import logging
from typing import List, Dict, Any
import numpy as np

from .indexer import DocumentIndexer


logger = logging.getLogger(__name__)


class SemanticSearch:
    """
    Performs semantic search over indexed documents using FAISS.
    """

    def __init__(self, indexer: DocumentIndexer, config: Dict[str, Any]):
        """
        Initialize the search engine.

        Args:
            indexer: Document indexer with FAISS index
            config: Configuration dictionary
        """
        self.indexer = indexer
        self.config = config
        self.top_k = config['search']['top_k']
        self.similarity_threshold = config['search']['similarity_threshold']

    def search(self, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        """
        Search for documents semantically similar to the query.

        Args:
            query: Search query
            top_k: Number of results to return (uses config default if None)

        Returns:
            List of search results with metadata and scores
        """
        if top_k is None:
            top_k = self.top_k

        logger.info(f"Searching for: {query}")

        try:
            # Get query embedding
            query_embedding = self.indexer.get_embedding(query)

            # Search FAISS index
            distances, indices = self.indexer.index.search(
                query_embedding.reshape(1, -1), top_k
            )

            # Process results
            results = []
            for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                if idx == -1:  # FAISS returns -1 for missing results
                    continue

                # Convert distance to similarity score (for cosine similarity)
                similarity = float(distance)

                # Filter by threshold
                if similarity < self.similarity_threshold:
                    continue

                # Get document metadata
                doc_metadata = self.indexer.documents[idx]

                results.append({
                    'rank': i + 1,
                    'similarity': similarity,
                    'file_path': doc_metadata['file_path'],
                    'file_name': doc_metadata['file_name'],
                    'file_type': doc_metadata['file_type'],
                    'page_number': doc_metadata.get('page_number'),
                    'total_pages': doc_metadata.get('total_pages', 0),
                    'content_preview': doc_metadata['content'][:300] + '...',
                    'full_content': doc_metadata['content'],
                    'file_mtime': doc_metadata.get('file_mtime'),
                })

            logger.info(f"Found {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Error during search: {e}")
            return []

    def search_and_group(self, query: str) -> List[Dict[str, Any]]:
        """
        Search and group results by document (combining chunks from same file).

        Args:
            query: Search query

        Returns:
            List of documents with aggregated relevance scores
        """
        # Get all matching chunks
        chunk_results = self.search(query, top_k=20)

        # Group by file
        file_groups = {}
        for result in chunk_results:
            file_path = result['file_path']

            if file_path not in file_groups:
                file_groups[file_path] = {
                    'file_path': file_path,
                    'file_name': result['file_name'],
                    'file_type': result['file_type'],
                    'total_pages': result['total_pages'],
                    'chunks': [],
                    'max_similarity': 0.0,
                    'avg_similarity': 0.0,
                }

            file_groups[file_path]['chunks'].append(result)
            file_groups[file_path]['max_similarity'] = max(
                file_groups[file_path]['max_similarity'],
                result['similarity']
            )

        # Calculate average similarity and sort
        grouped_results = []
        for file_data in file_groups.values():
            file_data['avg_similarity'] = np.mean([
                chunk['similarity'] for chunk in file_data['chunks']
            ])
            grouped_results.append(file_data)

        # Sort by max similarity (most relevant chunk in document)
        grouped_results.sort(key=lambda x: x['max_similarity'], reverse=True)

        logger.info(f"Grouped into {len(grouped_results)} documents")
        return grouped_results

    def get_best_match(self, query: str) -> Dict[str, Any]:
        """
        Get the single best matching document.

        Args:
            query: Search query

        Returns:
            Best matching document or None
        """
        results = self.search(query, top_k=1)
        return results[0] if results else None

    def search_pages_in_document(self, query: str, doc_path: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for pages within a specific document using semantic search.

        Args:
            query: Search query (e.g., "pre-chorus")
            doc_path: Path to the document
            top_k: Number of results to return

        Returns:
            List of page results sorted by relevance
        """
        logger.info(f"Searching for '{query}' in document: {doc_path}")

        try:
            # Get query embedding
            query_embedding = self.indexer.get_embedding(query)

            # Search all chunks
            distances, indices = self.indexer.index.search(
                query_embedding.reshape(1, -1), len(self.indexer.documents)
            )

            # Filter results to only this document, track seen pages to avoid duplicates
            results = []
            seen_pages = set()

            for distance, idx in zip(distances[0], indices[0]):
                if idx == -1:
                    continue

                doc_metadata = self.indexer.documents[idx]

                # Only include pages from the target document
                if doc_metadata['file_path'] != doc_path:
                    continue

                # Skip if no page number (shouldn't happen for PDFs)
                page_num = doc_metadata.get('page_number')
                if page_num is None:
                    continue

                # Skip duplicates (same page indexed multiple times)
                if page_num in seen_pages:
                    continue
                seen_pages.add(page_num)

                similarity = float(distance)

                results.append({
                    'page_number': page_num,
                    'similarity': similarity,
                    'content_preview': doc_metadata['content'][:200] + '...',
                })

                # Stop once we have enough unique results from this document
                if len(results) >= top_k:
                    break

            # Sort by similarity (descending)
            results.sort(key=lambda x: x['similarity'], reverse=True)

            logger.info(f"Found {len(results)} pages in document")
            return results

        except Exception as e:
            logger.error(f"Error during page search: {e}")
            return []
