"""
Document listing service for /files list functionality.

Provides functionality to list indexed documents with metadata and filtering.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DocumentListingService:
    """
    Service for listing indexed documents with metadata and filtering capabilities.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the document listing service.

        Args:
            config: Application configuration
        """
        self.config = config

    def list_documents(self, filter_text: Optional[str] = None, folder_path: Optional[str] = None,
                      max_results: int = 20) -> Dict[str, Any]:
        """
        List indexed documents with optional filtering.

        Args:
            filter_text: Text to filter documents by (name, content, or folder)
            folder_path: Specific folder to list documents from
            max_results: Maximum number of documents to return

        Returns:
            Dictionary with:
            - type: "document_list"
            - message: Summary message
            - documents: List of document entries
            - total_count: Total number of documents found
            - has_more: Boolean indicating if there are more results
        """
        try:
            from src.documents import DocumentIndexer

            # Initialize indexer and load existing index
            indexer = DocumentIndexer(self.config)

            if not indexer.documents:
                logger.info("No indexed documents found")
                return {
                    "type": "document_list",
                    "message": "No documents indexed yet. Try /files refresh to index documents.",
                    "documents": [],
                    "total_count": 0,
                    "has_more": False
                }

            # Get unique documents from chunks
            unique_docs = self._get_unique_documents(indexer.documents)

            # Apply folder filtering if specified
            if folder_path:
                folder_path_obj = Path(folder_path)
                unique_docs = [doc for doc in unique_docs if Path(doc['path']).parent == folder_path_obj]

            # Apply text filtering
            if filter_text:
                unique_docs = self._filter_documents(unique_docs, filter_text)

            # Sort by modification time (newest first)
            unique_docs.sort(key=lambda x: x.get('modified', datetime.min), reverse=True)

            # Limit results
            total_count = len(unique_docs)
            has_more = total_count > max_results
            limited_docs = unique_docs[:max_results]

            # Add file stats and preview for limited results
            for doc in limited_docs:
                self._enrich_document_metadata(doc)

            message = self._create_summary_message(limited_docs, total_count, has_more, filter_text)

            return {
                "type": "document_list",
                "message": message,
                "documents": limited_docs,
                "total_count": total_count,
                "has_more": has_more
            }

        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return {
                "type": "document_list",
                "message": f"Error listing documents: {str(e)}",
                "documents": [],
                "total_count": 0,
                "has_more": False
            }

    def _get_unique_documents(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract unique documents from document chunks.

        Args:
            chunks: List of document chunks from indexer

        Returns:
            List of unique document dictionaries
        """
        unique_docs = {}
        for chunk in chunks:
            file_path = chunk['file_path']
            if file_path not in unique_docs:
                unique_docs[file_path] = {
                    'path': file_path,
                    'name': chunk['file_name'],
                    'type': chunk.get('file_type', 'unknown'),
                    'total_pages': chunk.get('total_pages', 0),
                    'indexed_at': datetime.now(),  # Placeholder - could be stored in metadata
                }

        return list(unique_docs.values())

    def _filter_documents(self, documents: List[Dict[str, Any]], filter_text: str) -> List[Dict[str, Any]]:
        """
        Filter documents based on filter text.

        Args:
            documents: List of document dictionaries
            filter_text: Filter text (can be folder name, document name, or semantic query)

        Returns:
            Filtered list of documents
        """
        filter_lower = filter_text.lower().strip()

        # Check if it's a folder filter (folder=<name>)
        if filter_lower.startswith('folder='):
            folder_name = filter_lower.split('=', 1)[1].strip()
            return [doc for doc in documents if folder_name.lower() in Path(doc['path']).parent.name.lower()]

        # Check if it's a direct folder name match
        folder_matches = [doc for doc in documents if filter_lower in Path(doc['path']).parent.name.lower()]
        if folder_matches:
            return folder_matches

        # Otherwise, filter by document name
        return [doc for doc in documents if filter_lower in doc['name'].lower()]

    def _enrich_document_metadata(self, doc: Dict[str, Any]) -> None:
        """
        Add additional metadata to a document entry.

        Args:
            doc: Document dictionary to enrich
        """
        try:
            path_obj = Path(doc['path'])

            # Get file stats
            if path_obj.exists():
                stat = path_obj.stat()
                doc['size'] = stat.st_size
                doc['modified'] = datetime.fromtimestamp(stat.st_mtime)
                doc['size_human'] = self._format_file_size(stat.st_size)
            else:
                doc['size'] = 0
                doc['modified'] = datetime.min
                doc['size_human'] = "N/A"

            # Add preview snippet (first few words from first chunk if available)
            doc['preview'] = self._get_document_preview(doc['path'])

        except Exception as e:
            logger.warning(f"Error enriching metadata for {doc['path']}: {e}")
            doc['size'] = 0
            doc['modified'] = datetime.min
            doc['size_human'] = "Error"
            doc['preview'] = ""

    def _get_document_preview(self, file_path: str, max_length: int = 100) -> str:
        """
        Get a preview snippet from a document.

        Args:
            file_path: Path to the document
            max_length: Maximum length of preview text

        Returns:
            Preview text or empty string
        """
        try:
            from src.documents import DocumentIndexer
            indexer = DocumentIndexer(self.config)

            # Find chunks for this document
            doc_chunks = [chunk for chunk in indexer.documents if chunk['file_path'] == file_path]
            if doc_chunks:
                # Get content from first chunk, removing the filename prefix
                content = doc_chunks[0]['content']
                # Remove the "Document: filename" prefix
                lines = content.split('\n', 2)
                if len(lines) >= 3 and lines[0].startswith('Document:'):
                    content = lines[2]  # Skip filename and empty line

                # Truncate to max_length
                if len(content) > max_length:
                    content = content[:max_length].rstrip() + "..."

                return content

        except Exception as e:
            logger.warning(f"Error getting preview for {file_path}: {e}")

        return ""

    def _format_file_size(self, size_bytes: int) -> str:
        """
        Format file size in human-readable format.

        Args:
            size_bytes: Size in bytes

        Returns:
            Human-readable size string
        """
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB"]
        size_index = 0
        size = float(size_bytes)

        while size >= 1024 and size_index < len(size_names) - 1:
            size /= 1024
            size_index += 1

        if size_index == 0:
            return f"{int(size)} {size_names[size_index]}"
        else:
            return f"{size:.1f} {size_names[size_index]}"

    def _create_summary_message(self, documents: List[Dict[str, Any]], total_count: int,
                               has_more: bool, filter_text: Optional[str] = None) -> str:
        """
        Create a summary message for the document list.

        Args:
            documents: List of documents being returned
            total_count: Total number of documents found
            has_more: Whether there are more results
            filter_text: Optional filter text used

        Returns:
            Summary message string
        """
        if not documents:
            if filter_text:
                return f"No documents found matching '{filter_text}'"
            else:
                return "No documents found"

        showing_count = len(documents)
        filter_desc = f" matching '{filter_text}'" if filter_text else ""

        if has_more:
            return f"Showing {showing_count} of {total_count} documents{filter_desc} (showing newest first)"
        else:
            return f"Found {total_count} document{'s' if total_count != 1 else ''}{filter_desc}"


def list_documents(filter: Optional[str] = None, folder_path: Optional[str] = None,
                  max_results: int = 20) -> Dict[str, Any]:
    """
    List indexed documents with optional filtering.

    FILE AGENT - LEVEL 1: Document Discovery
    Use this when the user wants to browse or list their indexed documents.

    Args:
        filter: Text to filter documents by (name, folder, or semantic query)
        folder_path: Specific folder path to list documents from
        max_results: Maximum number of documents to return (default: 20)

    Returns:
        Dictionary with document list and metadata
    """
    from src.utils import load_config

    config = load_config()
    service = DocumentListingService(config)

    return service.list_documents(filter, folder_path, max_results)
