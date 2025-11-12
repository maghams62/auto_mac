"""
Document indexer using OpenAI embeddings and FAISS for vector storage.
"""

import os
import json
import pickle
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
import faiss
from openai import OpenAI
from tqdm import tqdm

from .parser import DocumentParser


logger = logging.getLogger(__name__)


class DocumentIndexer:
    """
    Indexes documents using OpenAI embeddings and FAISS for fast similarity search.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the document indexer.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.client = OpenAI(api_key=config['openai']['api_key'])
        self.embedding_model = config['openai']['embedding_model']

        # FAISS index
        self.index: Optional[faiss.Index] = None
        self.documents: List[Dict[str, Any]] = []
        self.dimension = 1536  # text-embedding-3-small dimension

        # Paths
        self.index_path = Path("data/embeddings/faiss.index")
        self.metadata_path = Path("data/embeddings/metadata.pkl")

        # Document parser
        self.parser = DocumentParser(config)

        # Initialize index
        self._initialize_index()

    def _initialize_index(self):
        """Initialize or load existing FAISS index."""
        if self.index_path.exists() and self.metadata_path.exists():
            logger.info("Loading existing FAISS index")
            self.load_index()
        else:
            logger.info("Creating new FAISS index")
            # Using IndexFlatIP for inner product (cosine similarity with normalized vectors)
            self.index = faiss.IndexFlatIP(self.dimension)
            self.documents = []

    def get_embedding(self, text: str) -> np.ndarray:
        """
        Get embedding for text using OpenAI API.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as numpy array
        """
        try:
            # Truncate text if too long (max ~8000 tokens for text-embedding-3-small)
            max_chars = 30000
            if len(text) > max_chars:
                text = text[:max_chars]

            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )

            embedding = np.array(response.data[0].embedding, dtype=np.float32)

            # Normalize for cosine similarity
            embedding = embedding / np.linalg.norm(embedding)

            return embedding

        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            raise

    def index_documents(self, folders: Optional[List[str]] = None, cancel_event=None) -> int:
        """
        Index all documents in specified folders.

        Args:
            folders: List of folder paths to index. If None, uses folders from config.yaml.
                     IMPORTANT: Only folders specified in config.yaml will be indexed.
            cancel_event: Optional asyncio.Event to signal cancellation

        Returns:
            Number of documents indexed
        """
        # Always use config folders - ignore any passed folders parameter for /index command
        # This ensures /index only indexes what's configured in config.yaml
        if folders is None:
            folders = self.config['documents']['folders']
            logger.info(f"Using folders from config.yaml: {folders}")
        else:
            # If folders are explicitly passed (e.g., from report_agent), use them
            logger.info(f"Using explicitly provided folders: {folders}")

        # Expand paths
        folders = [os.path.expanduser(folder) for folder in folders]

        logger.info(f"Starting indexing for {len(folders)} folder(s): {folders}")

        # Find all supported documents
        supported_types = self.config['documents']['supported_types']
        all_files = []

        for folder in folders:
            # Check for cancellation during file discovery
            if cancel_event and cancel_event.is_set():
                logger.info("Indexing cancelled during file discovery")
                return 0
                
            folder_path = Path(folder)
            if not folder_path.exists():
                logger.warning(f"Folder not found: {folder}")
                continue

            for ext in supported_types:
                all_files.extend(folder_path.rglob(f"*{ext}"))

        logger.info(f"Found {len(all_files)} documents to index")

        # Get set of already indexed file paths and their modification times
        indexed_files = {}
        for doc in self.documents:
            file_path = doc.get('file_path')
            if file_path:
                # Store modification time if available, or use None to force re-index
                indexed_files[file_path] = doc.get('file_mtime')

        logger.info(f"Already indexed: {len(indexed_files)} files")

        # Parse and index each document
        indexed_count = 0
        skipped_count = 0
        updated_count = 0

        for file_path in tqdm(all_files, desc="Indexing documents"):
            # Check for cancellation before processing each file
            if cancel_event and cancel_event.is_set():
                logger.info(f"Indexing cancelled after processing {indexed_count} documents")
                return indexed_count
            
            file_path_str = str(file_path)
            
            # Check if file is already indexed
            if file_path_str in indexed_files:
                # Check if file has been modified
                try:
                    file_mtime = os.path.getmtime(file_path_str)
                    indexed_mtime = indexed_files[file_path_str]
                    
                    # If file hasn't changed, skip it
                    if indexed_mtime and abs(file_mtime - indexed_mtime) < 1.0:  # 1 second tolerance
                        skipped_count += 1
                        continue
                    else:
                        # File has been modified - remove old chunks and re-index
                        logger.info(f"File modified, re-indexing: {file_path.name}")
                        self._remove_file_from_index(file_path_str)
                        updated_count += 1
                except OSError:
                    # File might have been deleted, skip
                    skipped_count += 1
                    continue
                
            try:
                # Parse document
                parsed_doc = self.parser.parse_document(file_path_str)

                if not parsed_doc or not parsed_doc.get('content'):
                    logger.warning(f"Skipping empty document: {file_path}")
                    skipped_count += 1
                    continue

                # Get file modification time
                try:
                    file_mtime = os.path.getmtime(file_path_str)
                except OSError:
                    file_mtime = None

                # Create chunks for long documents (chunk by page or by size)
                chunks = self._create_chunks(parsed_doc)

                for chunk in chunks:
                    # Check for cancellation before each embedding call
                    if cancel_event and cancel_event.is_set():
                        logger.info(f"Indexing cancelled during chunk processing")
                        return indexed_count
                    
                    # Get embedding
                    embedding = self.get_embedding(chunk['content'])

                    # Add file modification time to chunk metadata
                    chunk['file_mtime'] = file_mtime

                    # Add to FAISS index
                    self.index.add(embedding.reshape(1, -1))

                    # Store metadata
                    self.documents.append(chunk)

                indexed_count += 1

            except Exception as e:
                logger.error(f"Error indexing {file_path}: {e}")
                continue
        
        logger.info(f"Indexing complete: {indexed_count} new/updated, {skipped_count} skipped (unchanged), {updated_count} updated")

        logger.info(f"Successfully indexed {indexed_count} documents")

        # Save index
        self.save_index()

        return indexed_count

    def _create_chunks(self, parsed_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Create searchable chunks from a parsed document.

        Args:
            parsed_doc: Parsed document dictionary

        Returns:
            List of document chunks with metadata
        """
        chunks = []

        # If document has pages, create chunks per page
        if parsed_doc.get('pages'):
            for page_num, page_content in parsed_doc['pages'].items():
                if not page_content.strip():
                    continue

                # Prepend filename to content for better semantic search (especially for docs with minimal text)
                filename_without_ext = parsed_doc['file_name'].rsplit('.', 1)[0]
                enriched_content = f"Document: {filename_without_ext}\n\n{page_content}"

                chunks.append({
                    'file_path': parsed_doc['file_path'],
                    'file_name': parsed_doc['file_name'],
                    'file_type': parsed_doc['file_type'],
                    'content': enriched_content,
                    'page_number': page_num,
                    'total_pages': parsed_doc.get('page_count', 0),
                    'chunk_type': 'page',
                })
        else:
            # For documents without pages, use full content or split by size
            content = parsed_doc['content']
            max_chunk_size = 4000  # characters

            # Prepend filename for better semantic search
            filename_without_ext = parsed_doc['file_name'].rsplit('.', 1)[0]
            enriched_content = f"Document: {filename_without_ext}\n\n{content}"

            if len(enriched_content) <= max_chunk_size:
                chunks.append({
                    'file_path': parsed_doc['file_path'],
                    'file_name': parsed_doc['file_name'],
                    'file_type': parsed_doc['file_type'],
                    'content': enriched_content,
                    'page_number': None,
                    'total_pages': parsed_doc.get('page_count', 0),
                    'chunk_type': 'full',
                })
            else:
                # Split into chunks
                for i in range(0, len(content), max_chunk_size):
                    chunk_content = content[i:i + max_chunk_size]
                    # Add filename to first chunk only to avoid repetition
                    if i == 0:
                        chunk_content = f"Document: {filename_without_ext}\n\n{chunk_content}"

                    chunks.append({
                        'file_path': parsed_doc['file_path'],
                        'file_name': parsed_doc['file_name'],
                        'file_type': parsed_doc['file_type'],
                        'content': chunk_content,
                        'page_number': None,
                        'total_pages': parsed_doc.get('page_count', 0),
                        'chunk_type': f'chunk_{i // max_chunk_size}',
                    })

        return chunks

    def save_index(self):
        """Save FAISS index and metadata to disk."""
        logger.info("Saving FAISS index")

        # Create directory if needed
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        faiss.write_index(self.index, str(self.index_path))

        # Save metadata
        with open(self.metadata_path, 'wb') as f:
            pickle.dump(self.documents, f)

        logger.info(f"Saved {len(self.documents)} document chunks")

    def load_index(self):
        """Load FAISS index and metadata from disk."""
        logger.info("Loading FAISS index")

        # Load FAISS index
        self.index = faiss.read_index(str(self.index_path))

        # Load metadata
        with open(self.metadata_path, 'rb') as f:
            self.documents = pickle.load(f)

        logger.info(f"Loaded {len(self.documents)} document chunks")

    def _remove_file_from_index(self, file_path: str):
        """Remove all chunks for a specific file from the index."""
        # Find indices of chunks to remove
        indices_to_remove = []
        for i, doc in enumerate(self.documents):
            if doc.get('file_path') == file_path:
                indices_to_remove.append(i)
        
        if not indices_to_remove:
            return
        
        # Remove from documents list (in reverse order to maintain indices)
        for i in reversed(indices_to_remove):
            self.documents.pop(i)
        
        # Rebuild FAISS index (FAISS doesn't support removal, so we rebuild)
        logger.info(f"Rebuilding index after removing {len(indices_to_remove)} chunks for {Path(file_path).name}")
        
        # Create new index
        new_index = faiss.IndexFlatIP(self.dimension)
        new_documents = []
        
        # Re-add all remaining documents
        for doc in self.documents:
            try:
                embedding = self.get_embedding(doc['content'])
                new_index.add(embedding.reshape(1, -1))
                new_documents.append(doc)
            except Exception as e:
                logger.warning(f"Error re-indexing chunk: {e}")
                continue
        
        self.index = new_index
        self.documents = new_documents
        
        logger.info(f"Index rebuilt: {len(self.documents)} chunks remaining")

    def get_stats(self) -> Dict[str, Any]:
        """Get indexing statistics."""
        return {
            'total_chunks': len(self.documents),
            'index_size': self.index.ntotal if self.index else 0,
            'unique_files': len(set(doc['file_path'] for doc in self.documents)),
        }
