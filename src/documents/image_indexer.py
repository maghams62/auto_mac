"""
Image indexer for semantic search using LLM reasoning and semantic embeddings.
"""

import os
import logging
import pickle
import base64
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import faiss
from PIL import Image
import hashlib
import time
import json
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.utils.openai_client import PooledOpenAIClient
from src.utils import get_temperature_for_model

logger = logging.getLogger(__name__)


class ImageIndexer:
    """
    Indexes images for semantic search using LLM reasoning and semantic embeddings.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the image indexer.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.images_config = config.get('images', {})
        self.documents_config = config.get('documents', {})
        openai_config = config.get('openai', {})

        # Index storage paths
        self.index_path = Path("data/embeddings/image_faiss.index")
        self.metadata_path = Path("data/embeddings/image_metadata.pkl")
        self.thumbnail_dir = Path(self.images_config.get('thumbnail', {}).get('cache_dir', 'data/cache/thumbnails'))

        # Configuration
        self.supported_types = set(self.documents_config.get('supported_image_types', []))
        self.folders = self.documents_config.get('folders', [])

        # Initialize OpenAI client for embeddings and LLM reasoning
        self.client = PooledOpenAIClient.get_client(config)
        self.embedding_model = openai_config.get('embedding_model', 'text-embedding-3-small')
        self.dimension = 1536  # text-embedding-3-small dimension
        
        # Initialize LLM for caption generation and query enhancement
        self.llm = ChatOpenAI(
            model=openai_config.get('model', 'gpt-4o'),
            temperature=get_temperature_for_model(config, default_temperature=0.3),
            api_key=openai_config.get('api_key')
        )
        
        logger.info("[IMAGE INDEXER] Using pooled OpenAI client for embeddings and LLM reasoning")

        # FAISS index and metadata
        self.index = None
        self.metadata: List[Dict[str, Any]] = []
        self._load_or_create_index()


    def _load_or_create_index(self):
        """Load existing index or create new one"""
        try:
            # Ensure directories exist
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            self.thumbnail_dir.mkdir(parents=True, exist_ok=True)

            if self.metadata_path.exists():
                logger.info("Loading existing image index")
                self._load_index()
            else:
                logger.info("Creating new image index")
                self._create_index()
        except Exception as e:
            logger.error(f"Error loading/creating index: {e}")
            self._create_index()

    def _load_index(self):
        """Load existing FAISS index and metadata"""
        try:
            with open(self.metadata_path, 'rb') as f:
                self.metadata = pickle.load(f)

            # Load or create FAISS index
            if self.index_path.exists():
                try:
                    self.index = faiss.read_index(str(self.index_path))
                    logger.info(f"[IMAGE INDEXER] Loaded FAISS index with {self.index.ntotal} vectors")
                except Exception as e:
                    logger.warning(f"[IMAGE INDEXER] Failed to load FAISS index: {e}, creating new one")
                    self._create_faiss_index()
            else:
                self._create_faiss_index()

            # Verify index dimension matches
            if self.index.d != self.dimension:
                logger.warning(
                    f"[IMAGE INDEXER] Index dimension mismatch: expected {self.dimension}, got {self.index.d}. "
                    f"Creating new index."
                )
                self._create_faiss_index()

            # Rebuild index from metadata if needed
            if self.index.ntotal == 0 and len(self.metadata) > 0:
                logger.info(f"[IMAGE INDEXER] Rebuilding FAISS index from {len(self.metadata)} metadata entries")
                restored_embeddings = 0
                for item in self.metadata:
                    embedding = item.get('embedding')
                    if embedding is None:
                        continue
                    try:
                        embedding_array = np.array(embedding, dtype=np.float32)
                        if embedding_array.size == 0 or embedding_array.shape[0] != self.dimension:
                            continue
                        # Normalize for cosine similarity
                        embedding_array = embedding_array / np.linalg.norm(embedding_array)
                        self.index.add(embedding_array.reshape(1, -1))
                        restored_embeddings += 1
                    except Exception as embed_error:
                        logger.warning(f"[IMAGE INDEXER] Failed to restore embedding for {item.get('file_name')}: {embed_error}")

                logger.info(
                    f"[IMAGE INDEXER] Loaded {len(self.metadata)} images from index "
                    f"(restored {restored_embeddings} embedding vectors)"
                )
            else:
                logger.info(
                    f"[IMAGE INDEXER] Loaded {len(self.metadata)} images from index "
                    f"(FAISS index has {self.index.ntotal} vectors)"
                )
        except Exception as e:
            logger.error(f"[IMAGE INDEXER] Error loading index: {e}")
            self._create_index()

    def _create_index(self):
        """Create new empty index"""
        self.metadata = []
        self._create_faiss_index()
    
    def _create_faiss_index(self):
        """Create new FAISS index"""
        # Using IndexFlatIP for inner product (cosine similarity with normalized vectors)
        self.index = faiss.IndexFlatIP(self.dimension)
        logger.info(f"[IMAGE INDEXER] Created new FAISS index with dimension {self.dimension}")

    def index_folder(self, folder_path: str) -> int:
        """
        Index all images in a folder.

        Args:
            folder_path: Path to folder to index

        Returns:
            Number of images indexed
        """
        folder = Path(folder_path)
        if not folder.exists():
            logger.warning(f"Folder does not exist: {folder_path}")
            return 0

        indexed_count = 0
        logger.info(f"Indexing images in: {folder_path}")

        for file_path in folder.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in self.supported_types:
                try:
                    if self._index_image(file_path):
                        indexed_count += 1
                except Exception as e:
                    logger.error(f"Error indexing {file_path}: {e}")

        logger.info(f"Indexed {indexed_count} images from {folder_path}")
        return indexed_count

    def _index_image(self, file_path: Path) -> bool:
        """
        Index a single image file.

        Args:
            file_path: Path to image file

        Returns:
            True if successfully indexed
        """
        # Check if already indexed
        file_path_str = str(file_path)
        file_mtime = file_path.stat().st_mtime

        existing = next((item for item in self.metadata if item['file_path'] == file_path_str), None)
        if existing and existing['file_mtime'] >= file_mtime:
            return False  # Already up to date

        try:
            # Open and validate image
            with Image.open(file_path) as img:
                width, height = img.size

            # Generate caption using LLM reasoning
            logger.info(f"[IMAGE INDEXER] Generating caption for {file_path.name} using LLM reasoning")
            caption = self._generate_caption(file_path)
            logger.debug(f"[IMAGE INDEXER] Generated caption: {caption[:100]}...")

            # Generate embedding using OpenAI embeddings API
            logger.info(f"[IMAGE INDEXER] Generating semantic embedding for {file_path.name}")
            embedding = self._generate_embedding(caption)
            logger.debug(f"[IMAGE INDEXER] Generated embedding with dimension {len(embedding)}")

            # Generate thumbnail
            thumbnail_path = self._generate_thumbnail(file_path)

            # Create metadata entry
            metadata_entry = {
                'file_path': file_path_str,
                'file_name': file_path.name,
                'file_type': file_path.suffix.lower(),
                'file_mtime': file_mtime,
                'caption': caption,
                'width': width,
                'height': height,
                'thumbnail_path': str(thumbnail_path),
                'embedding': embedding,
                'indexed_at': time.time()
            }

            # Remove existing entry if present
            self.metadata = [item for item in self.metadata if item['file_path'] != file_path_str]

            # Add new entry
            self.metadata.append(metadata_entry)

            # Update FAISS index (normalize embedding first)
            embedding_normalized = embedding / np.linalg.norm(embedding)
            self.index.add(embedding_normalized.reshape(1, -1))

            logger.info(f"[IMAGE INDEXER] Successfully indexed image: {file_path.name} (similarity score will be calculated during search)")
            return True

        except Exception as e:
            logger.error(f"Error processing image {file_path}: {e}")
            return False

    def _generate_caption(self, file_path: Path) -> str:
        """
        Generate a semantic caption for the image using LLM reasoning with OpenAI Vision API.

        Args:
            file_path: Path to image

        Returns:
            Caption string optimized for semantic search
        """
        try:
            # Read and encode image
            with open(file_path, 'rb') as image_file:
                image_data = image_file.read()
                base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Determine image format
            image_format = file_path.suffix.lower().replace('.', '')
            if image_format == 'jpg':
                image_format = 'jpeg'
            
            # Use OpenAI Vision API to analyze image
            prompt = """Analyze this image and generate a detailed semantic caption that describes:
- Main subjects and objects
- Scene type (landscape, portrait, nature, urban, etc.)
- Key visual elements (mountains, water, buildings, animals, etc.)
- Colors, composition, mood
- Any text or specific details visible

The caption should be optimized for semantic search matching. Be specific and descriptive.
Respond with ONLY the caption text, no additional explanation."""

            response = self.client.chat.completions.create(
                model="gpt-4o",  # Use vision-capable model
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/{image_format};base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            caption = response.choices[0].message.content.strip()
            logger.info(f"[IMAGE INDEXER] LLM-generated caption for {file_path.name}: {caption[:150]}...")
            return caption
            
        except Exception as e:
            logger.warning(f"[IMAGE INDEXER] Failed to generate LLM caption for {file_path.name}: {e}. Using fallback.")
            # Fallback to filename-based captioning
            filename = file_path.stem.lower()
            words = filename.replace('_', ' ').replace('-', ' ').split()
            if words:
                return f"Image showing {', '.join(words[:3])}"
            else:
                return f"Image file: {file_path.name}"

    def _generate_embedding(self, caption: str) -> np.ndarray:
        """
        Generate semantic embedding for the caption using OpenAI embeddings API.

        Args:
            caption: Image caption text

        Returns:
            Normalized embedding vector (1536 dimensions for text-embedding-3-small)
        """
        try:
            # Truncate caption if too long (max ~8000 tokens for text-embedding-3-small)
            max_chars = 30000
            if len(caption) > max_chars:
                caption = caption[:max_chars]
                logger.debug(f"[IMAGE INDEXER] Truncated caption to {max_chars} characters")

            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=caption
            )

            embedding = np.array(response.data[0].embedding, dtype=np.float32)

            # Normalize for cosine similarity
            embedding = embedding / np.linalg.norm(embedding)

            logger.debug(f"[IMAGE INDEXER] Generated embedding with dimension {len(embedding)}")
            return embedding

        except Exception as e:
            logger.error(f"[IMAGE INDEXER] Error generating embedding: {e}")
            raise

    def _generate_thumbnail(self, file_path: Path) -> Path:
        """
        Generate and save thumbnail for image.

        Args:
            file_path: Path to image

        Returns:
            Path to thumbnail
        """
        max_size = self.images_config.get('thumbnail', {}).get('max_size', 256)
        quality = self.images_config.get('thumbnail', {}).get('quality', 85)

        # Create thumbnail filename
        file_hash = hashlib.md5(str(file_path).encode()).hexdigest()[:8]
        thumbnail_filename = f"{file_hash}_{max_size}x{max_size}.jpg"
        thumbnail_path = self.thumbnail_dir / thumbnail_filename

        try:
            with Image.open(file_path) as img:
                # Create thumbnail
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

                # Save thumbnail
                img.save(thumbnail_path, 'JPEG', quality=quality)

                return thumbnail_path
        except Exception as e:
            logger.error(f"Error generating thumbnail for {file_path}: {e}")
            # Return original file as fallback
            return file_path

    def search_images(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for images semantically similar to the query using LLM-enhanced query and semantic embeddings.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of image results with metadata and similarity scores
        """
        if not self.index or not self.metadata:
            logger.warning("[IMAGE INDEXER] No index or metadata available for search")
            return []

        try:
            logger.info(f"[IMAGE INDEXER] Searching images for query: '{query}'")

            # Enhance query using LLM reasoning
            enhanced_query = self._enhance_query_with_llm(query)
            logger.info(f"[IMAGE INDEXER] Enhanced query: '{enhanced_query}' (original: '{query}')")

            # Generate query embedding using enhanced query
            query_embedding = self._generate_query_embedding(enhanced_query)
            logger.debug(f"[IMAGE INDEXER] Generated query embedding with dimension {len(query_embedding)}")

            # Search FAISS index
            distances, indices = self.index.search(query_embedding.reshape(1, -1), top_k)
            logger.info(f"[IMAGE INDEXER] FAISS search returned {len(indices[0])} candidate results")

            candidate_debug = []
            for idx, distance in zip(indices[0], distances[0]):
                if idx == -1:
                    candidate_debug.append("EMPTY:-1.0000")
                elif 0 <= idx < len(self.metadata):
                    candidate_debug.append(f"{self.metadata[idx]['file_name']}:{float(distance):.4f}")
                else:
                    candidate_debug.append(f"OUT_OF_RANGE({idx}):{float(distance):.4f}")
            if candidate_debug:
                logger.debug(f"[IMAGE INDEXER] Candidate similarity scores: {', '.join(candidate_debug)}")

            results = []
            for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                if idx == -1 or idx >= len(self.metadata):
                    continue

                item = self.metadata[idx].copy()
                # Distance is already similarity (cosine similarity with normalized vectors)
                item['similarity_score'] = float(distance)
                item['rank'] = i + 1

                # Generate breadcrumb
                item['breadcrumb'] = self._generate_breadcrumb(item['file_path'])

                logger.debug(
                    f"[IMAGE INDEXER] Result {i+1}: {item['file_name']} "
                    f"(similarity: {item['similarity_score']:.4f}, caption: {item.get('caption', 'N/A')[:50]}...)"
                )
                results.append(item)

            if results:
                logger.info(
                    f"[IMAGE INDEXER] Found {len(results)} image results for query: '{query}' "
                    f"(top similarity: {results[0]['similarity_score']:.4f})"
                )
            else:
                logger.info(f"[IMAGE INDEXER] No image results found for query: '{query}'")
            return results

        except Exception as e:
            logger.error(f"[IMAGE INDEXER] Error searching images: {e}", exc_info=True)
            return []

    def _enhance_query_with_llm(self, query: str) -> str:
        """
        Enhance user query using LLM reasoning to expand semantic terms and synonyms.

        Args:
            query: Original user query

        Returns:
            Enhanced query optimized for semantic image search
        """
        try:
            prompt = (
                f"User Query: {query}\n\n"
                "Enhance this query for semantic image search by:\n"
                "1. Identifying the main subject or concept.\n"
                "2. Adding related semantic terms and synonyms.\n"
                "3. Expanding with related concepts that might appear in images.\n"
                "4. Maintaining the core intent.\n\n"
                "Examples:\n"
                '- mountain → mountain landscape, peaks, scenic views, nature photography, alpine terrain, mountain ranges\n'
                '- cat → cat, feline, kitten, pet, domestic cat, cat portrait\n'
                '- ocean → ocean, sea, waves, seascape, beach, water, marine\n\n'
                "Return a comma-separated list of descriptive search terms.\n"
                "Do not wrap the response or individual terms in quotes.\n"
                "Avoid adding any commentary or bullet formatting."
            )

            messages = [
                SystemMessage(
                    content=(
                        "You enhance image search queries by expanding semantic terms. "
                        "Respond with ONLY the enhanced query text. "
                        "Do not surround the response in quotes."
                    )
                ),
                HumanMessage(content=prompt)
            ]

            response = self.llm.invoke(messages)
            enhanced_query = response.content.strip()
            sanitized_query = self._sanitize_enhanced_query(enhanced_query, query)

            if not sanitized_query:
                logger.warning(
                    f"[IMAGE INDEXER] Enhanced query was empty or invalid (original LLM output: '{enhanced_query}'). "
                    "Falling back to original query."
                )
                return query

            if sanitized_query != enhanced_query:
                logger.debug(
                    f"[IMAGE INDEXER] Sanitized enhanced query output from '{enhanced_query}' to '{sanitized_query}'"
                )

            logger.info(f"[IMAGE INDEXER] Query enhancement: '{query}' → '{sanitized_query}'")
            return sanitized_query

        except Exception as e:
            logger.warning(f"[IMAGE INDEXER] Failed to enhance query with LLM: {e}. Using original query.")
            return query

    def _sanitize_enhanced_query(self, enhanced_query: str, original_query: str) -> str:
        """
        Clean up LLM-enhanced queries to remove wrapping quotes, stray formatting, and ensure validity.
        Returns empty string if sanitization results in an unusable prompt.
        """
        sanitized = enhanced_query.strip()

        # Remove matching wrapping quotes (including curly quotes)
        quote_chars = "\"'`“”‘’"
        if sanitized and sanitized[0] in quote_chars and sanitized[-1] == sanitized[0]:
            sanitized = sanitized[1:-1].strip()

        # Remove any remaining leading/trailing quote characters
        sanitized = sanitized.strip(quote_chars)

        # Replace newlines with commas to keep embedding stable
        sanitized = re.sub(r"\s*\n+\s*", ", ", sanitized)

        # Normalize whitespace around commas
        sanitized = re.sub(r"\s*,\s*", ", ", sanitized)
        sanitized = re.sub(r"\s+", " ", sanitized).strip()

        # Remove empty segments caused by blank lines or redundant punctuation
        parts = [part.strip() for part in sanitized.split(",") if part.strip()]
        sanitized = ", ".join(parts)

        # Guard against empty or non-alphanumeric output
        if not sanitized:
            return ""
        if not re.search(r"[A-Za-z0-9]", sanitized):
            return ""

        # Avoid returning the original query if enhancement failed silently
        if sanitized == original_query.strip():
            return sanitized  # still valid, just unchanged

        return sanitized

    def _generate_query_embedding(self, query: str) -> np.ndarray:
        """
        Generate semantic embedding for search query using OpenAI embeddings API.

        Args:
            query: Search query (should be enhanced query)

        Returns:
            Normalized embedding vector (1536 dimensions for text-embedding-3-small)
        """
        try:
            # Truncate query if too long
            max_chars = 30000
            if len(query) > max_chars:
                query = query[:max_chars]
                logger.debug(f"[IMAGE INDEXER] Truncated query to {max_chars} characters")

            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=query
            )

            embedding = np.array(response.data[0].embedding, dtype=np.float32)

            # Normalize for cosine similarity
            embedding = embedding / np.linalg.norm(embedding)

            logger.debug(f"[IMAGE INDEXER] Generated query embedding with dimension {len(embedding)}")
            return embedding

        except Exception as e:
            logger.error(f"[IMAGE INDEXER] Error generating query embedding: {e}")
            raise

    def _generate_breadcrumb(self, file_path: str) -> str:
        """Generate a breadcrumb path for display"""
        # Get relative path from configured document directories
        folders = self.documents_config.get('folders', [])

        for folder in folders:
            try:
                folder_path = Path(folder)
                file_path_obj = Path(file_path)
                if file_path_obj.is_relative_to(folder_path):
                    relative_path = file_path_obj.relative_to(folder_path)
                    return str(relative_path)
            except (ValueError, OSError):
                continue

        # Fallback: return just the filename
        return Path(file_path).name

    def save_index(self):
        """Save the FAISS index and metadata to disk"""
        try:
            # Save metadata
            with open(self.metadata_path, 'wb') as f:
                pickle.dump(self.metadata, f)

            # Save FAISS index
            if self.index is not None:
                faiss.write_index(self.index, str(self.index_path))
                logger.info(f"[IMAGE INDEXER] Saved FAISS index with {self.index.ntotal} vectors")

            logger.info(f"[IMAGE INDEXER] Saved image index with {len(self.metadata)} images")
        except Exception as e:
            logger.error(f"[IMAGE INDEXER] Error saving image index: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        return {
            'total_images': len(self.metadata),
            'index_path': str(self.index_path),
            'metadata_path': str(self.metadata_path),
            'supported_types': list(self.supported_types),
            'folders': self.folders
        }
