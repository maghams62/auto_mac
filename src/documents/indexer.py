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
from .image_indexer import ImageIndexer
from src.utils.openai_client import PooledOpenAIClient


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
        # Use pooled client for connection reuse (20-40% faster)
        self.client = PooledOpenAIClient.get_client(config)
        self.embedding_model = config['openai']['embedding_model']
        logger.info("[DOCUMENT INDEXER] Using pooled OpenAI client for connection reuse")

        # Read batch embeddings config
        perf_config = config.get("performance", {})
        batch_config = perf_config.get("batch_embeddings", {})
        if batch_config.get("enabled", True):
            self.batch_size = batch_config.get("batch_size", 100)
        else:
            self.batch_size = 1  # Disable batching if disabled

        # FAISS index
        self.index: Optional[faiss.Index] = None
        self.documents: List[Dict[str, Any]] = []
        self.dimension = 1536  # text-embedding-3-small dimension

        # Paths
        self.index_path = Path("data/embeddings/faiss.index")
        self.metadata_path = Path("data/embeddings/metadata.pkl")

        # Document parser
        self.parser = DocumentParser(config)

        # Image indexer (only if images are enabled)
        self.image_indexer = None
        if config.get('images', {}).get('enabled', False):
            try:
                self.image_indexer = ImageIndexer(config)
                logger.info("Image indexer initialized")
            except Exception as e:
                logger.error(f"Failed to initialize image indexer: {e}")

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
    
    def get_embeddings_batch(self, texts: List[str], batch_size: Optional[int] = None) -> np.ndarray:
        """
        Generate embeddings for multiple texts in batches (10-20x faster).
        
        OpenAI supports up to 2048 inputs per request. We use configurable
        batch size from performance.batch_embeddings.batch_size.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call (uses config default if None)
            
        Returns:
            Array of embeddings (shape: [len(texts), dimension])
        """
        # Use instance batch_size from config if not provided
        if batch_size is None:
            batch_size = self.batch_size
        if not texts:
            return np.array([])
        
        logger.info(f"[BATCH EMBEDDINGS] Processing {len(texts)} texts in batches of {batch_size}")
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            
            # Truncate each text
            batch = [text[:30000] if len(text) > 30000 else text for text in batch]
            
            try:
                response = self.client.embeddings.create(
                    model=self.embedding_model,
                    input=batch  # List of texts
                )
                
                # Extract embeddings in order
                batch_embeddings = [
                    np.array(item.embedding, dtype=np.float32) 
                    for item in response.data
                ]
                
                # Normalize each embedding
                batch_embeddings = [
                    emb / np.linalg.norm(emb) for emb in batch_embeddings
                ]
                
                all_embeddings.extend(batch_embeddings)
                
                logger.debug(f"[BATCH EMBEDDINGS] Processed batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")
                
            except Exception as e:
                logger.error(f"[BATCH EMBEDDINGS] Batch {i//batch_size + 1} failed: {e}")
                # Fallback to individual calls for failed batch
                logger.info(f"[BATCH EMBEDDINGS] Falling back to individual calls for batch {i//batch_size + 1}")
                for text in batch:
                    try:
                        embedding = self.get_embedding(text)
                        all_embeddings.append(embedding)
                    except Exception as e2:
                        logger.error(f"[BATCH EMBEDDINGS] Individual embedding failed: {e2}")
                        # Use zero vector as fallback
                        all_embeddings.append(np.zeros(self.dimension, dtype=np.float32))
        
        return np.array(all_embeddings)

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

        # PHASE 1: Parse all documents and collect chunks (without embeddings)
        all_chunks = []
        skipped_count = 0
        updated_count = 0

        logger.info("Phase 1: Parsing documents...")
        for file_path in tqdm(all_files, desc="Parsing documents"):
            # Check for cancellation
            if cancel_event and cancel_event.is_set():
                logger.info("Indexing cancelled during parsing phase")
                return 0
            
            file_path_str = str(file_path)
            
            # Check if file is already indexed
            if file_path_str in indexed_files:
                try:
                    file_mtime = os.path.getmtime(file_path_str)
                    indexed_mtime = indexed_files[file_path_str]
                    
                    # If file hasn't changed, skip it
                    if indexed_mtime and abs(file_mtime - indexed_mtime) < 1.0:
                        skipped_count += 1
                        continue
                    else:
                        # File modified - remove old chunks
                        logger.info(f"File modified, re-indexing: {file_path.name}")
                        self._remove_file_from_index(file_path_str)
                        updated_count += 1
                except OSError:
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

                # Create chunks
                chunks = self._create_chunks(parsed_doc)

                # Add file mtime to each chunk
                for chunk in chunks:
                    chunk['file_mtime'] = file_mtime
                    all_chunks.append(chunk)

            except Exception as e:
                logger.error(f"Error parsing {file_path}: {e}")
                continue
        
        # PHASE 2: Generate embeddings in batch (10-20x faster!)
        logger.info(f"Phase 2: Generating embeddings for {len(all_chunks)} chunks (batch mode)...")
        if all_chunks:
            # Check for cancellation before batch embedding
            if cancel_event and cancel_event.is_set():
                logger.info("Indexing cancelled before embedding generation")
                return 0
            
            # Extract all text content
            chunk_texts = [chunk['content'] for chunk in all_chunks]
            
            # Generate embeddings in batches
            embeddings = self.get_embeddings_batch(chunk_texts)  # Uses batch_size from config
            
            # Track batch operation
            try:
                from src.utils.performance_monitor import get_performance_monitor
                get_performance_monitor().record_batch_operation("embeddings", len(chunk_texts))
            except Exception:
                pass
            
            # PHASE 3: Add to FAISS index
            logger.info(f"Phase 3: Adding {len(embeddings)} embeddings to FAISS index...")
            if len(embeddings) > 0:
                self.index.add(embeddings)
                self.documents.extend(all_chunks)
            
            indexed_count = len(all_chunks)
        else:
            indexed_count = 0
        
        logger.info(f"Indexing complete: {indexed_count} new/updated, {skipped_count} skipped (unchanged), {updated_count} updated")

        logger.info(f"Successfully indexed {indexed_count} documents")

        # Index images if enabled
        images_indexed = 0
        if self.image_indexer:
            logger.info("Starting image indexing...")
            for folder in folders:
                if cancel_event and cancel_event.is_set():
                    logger.info("Indexing cancelled during image indexing")
                    break

                images_indexed += self.image_indexer.index_folder(folder)

            # Save image index
            self.image_indexer.save_index()
            logger.info(f"Successfully indexed {images_indexed} images")

        # Save document index
        self.save_index()

        logger.info(f"Indexing complete: {indexed_count} documents, {images_indexed} images")
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
