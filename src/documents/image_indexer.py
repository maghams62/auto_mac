"""
Image indexer for semantic search using CLIP embeddings.
"""

import os
import logging
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from PIL import Image
import hashlib
import time

logger = logging.getLogger(__name__)


class ImageIndexer:
    """
    Indexes images for semantic search using CLIP embeddings.
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

        # Index storage paths
        self.index_path = Path("data/embeddings/image_faiss.index")
        self.metadata_path = Path("data/embeddings/image_metadata.pkl")
        self.thumbnail_dir = Path(self.images_config.get('thumbnail', {}).get('cache_dir', 'data/cache/thumbnails'))

        # Configuration
        self.supported_types = set(self.documents_config.get('supported_image_types', []))
        self.folders = self.documents_config.get('folders', [])

        # Initialize CLIP model (simplified for MVP)
        self.clip_model = None
        self.clip_processor = None
        self._init_clip_model()

        # FAISS index and metadata
        self.index = None
        self.metadata: List[Dict[str, Any]] = []
        self._load_or_create_index()

    def _init_clip_model(self):
        """Initialize CLIP model for MVP - simplified version"""
        try:
            # For MVP, we'll use a simplified approach
            # In production, this would load actual CLIP model
            logger.info("Initializing CLIP model (MVP simplified version)")
            self.clip_model = "mock_clip_model"
            self.clip_processor = "mock_processor"
        except Exception as e:
            logger.error(f"Failed to initialize CLIP model: {e}")
            raise

    def _load_or_create_index(self):
        """Load existing index or create new one"""
        try:
            # Ensure directories exist
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            self.thumbnail_dir.mkdir(parents=True, exist_ok=True)

            if self.index_path.exists() and self.metadata_path.exists():
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
            # For MVP, we'll use a simple in-memory approach
            with open(self.metadata_path, 'rb') as f:
                self.metadata = pickle.load(f)

            # Create mock FAISS index
            self.index = MockFAISSIndex(dimension=512, metadata=self.metadata)

            logger.info(f"Loaded {len(self.metadata)} images from index")
        except Exception as e:
            logger.error(f"Error loading index: {e}")
            self._create_index()

    def _create_index(self):
        """Create new empty index"""
        self.metadata = []
        self.index = MockFAISSIndex(dimension=512, metadata=self.metadata)

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

            # Generate caption (MVP simplified)
            caption = self._generate_caption(file_path)

            # Generate embedding (MVP simplified)
            embedding = self._generate_embedding(file_path, caption)

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

            # Update index
            self.index.add_embedding(embedding, metadata_entry)

            logger.debug(f"Indexed image: {file_path.name}")
            return True

        except Exception as e:
            logger.error(f"Error processing image {file_path}: {e}")
            return False

    def _generate_caption(self, file_path: Path) -> str:
        """
        Generate a caption for the image (MVP simplified).

        Args:
            file_path: Path to image

        Returns:
            Caption string
        """
        # MVP: Use filename and basic image analysis
        filename = file_path.stem.lower()

        # Simple keyword-based captioning
        if 'mountain' in filename or 'landscape' in filename:
            return "A beautiful mountain landscape with scenic views"
        elif 'cat' in filename or 'kitten' in filename:
            return "An adorable cat in a cute pose"
        elif 'dog' in filename or 'puppy' in filename:
            return "A friendly dog playing outdoors"
        elif 'ocean' in filename or 'sea' in filename:
            return "Peaceful ocean waves and seascape"
        elif 'city' in filename or 'urban' in filename:
            return "Urban cityscape with buildings and streets"
        else:
            # Try to extract meaningful words from filename
            words = filename.replace('_', ' ').replace('-', ' ').split()
            if words:
                return f"Image showing {', '.join(words[:3])}"
            else:
                return f"Image file: {file_path.name}"

    def _generate_embedding(self, file_path: Path, caption: str) -> np.ndarray:
        """
        Generate CLIP embedding for the image (MVP simplified).

        Args:
            file_path: Path to image
            caption: Generated caption

        Returns:
            Embedding vector
        """
        # MVP: Create a simple hash-based embedding from caption
        # Use the same method as query embedding for comparability
        text_to_embed = f"{caption} {file_path.stem}".lower()
        text_hash = hashlib.md5(text_to_embed.encode()).hexdigest()

        # Create deterministic "embedding" from text hash
        embedding = np.array([int(text_hash[i:i+2], 16) / 255.0 for i in range(0, 32, 2)])

        # Pad to 512 dimensions (CLIP standard)
        while len(embedding) < 512:
            embedding = np.concatenate([embedding, embedding])

        return embedding[:512]

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
        Search for images semantically similar to the query.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of image results with metadata
        """
        if not self.index or not self.metadata:
            return []

        try:
            # Generate query embedding (MVP simplified)
            query_embedding = self._generate_query_embedding(query)

            # Search index
            distances, indices = self.index.search(query_embedding.reshape(1, -1), top_k)

            results = []
            for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                if idx == -1 or idx >= len(self.metadata):
                    continue

                item = self.metadata[idx].copy()
                item['similarity_score'] = float(distance)
                item['rank'] = i + 1

                # Generate breadcrumb
                item['breadcrumb'] = self._generate_breadcrumb(item['file_path'])

                results.append(item)

            logger.info(f"Found {len(results)} image results for query: {query}")
            return results

        except Exception as e:
            logger.error(f"Error searching images: {e}")
            return []

    def _generate_query_embedding(self, query: str) -> np.ndarray:
        """
        Generate embedding for search query (MVP simplified).

        Args:
            query: Search query

        Returns:
            Embedding vector
        """
        # Use the same method as image embedding for consistency
        text_to_embed = query.lower()
        text_hash = hashlib.md5(text_to_embed.encode()).hexdigest()

        # Create deterministic "embedding" from text hash
        embedding = np.array([int(text_hash[i:i+2], 16) / 255.0 for i in range(0, 32, 2)])

        # Pad to 512 dimensions
        while len(embedding) < 512:
            embedding = np.concatenate([embedding, embedding])

        return embedding[:512]

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
        """Save the index and metadata to disk"""
        try:
            # Save metadata
            with open(self.metadata_path, 'wb') as f:
                pickle.dump(self.metadata, f)

            logger.info(f"Saved image index with {len(self.metadata)} images")
        except Exception as e:
            logger.error(f"Error saving image index: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        return {
            'total_images': len(self.metadata),
            'index_path': str(self.index_path),
            'metadata_path': str(self.metadata_path),
            'supported_types': list(self.supported_types),
            'folders': self.folders
        }


class MockFAISSIndex:
    """Mock FAISS index for MVP"""

    def __init__(self, dimension: int, metadata: List[Dict[str, Any]]):
        self.dimension = dimension
        self.metadata = metadata
        self.embeddings = []

    def add_embedding(self, embedding: np.ndarray, metadata_item: Dict[str, Any]):
        """Add embedding to index"""
        self.embeddings.append((embedding, metadata_item))

    def search(self, query_embedding: np.ndarray, k: int) -> Tuple[np.ndarray, np.ndarray]:
        """Search for similar embeddings"""
        if not self.embeddings:
            return np.array([[]]), np.array([[]])

        # Calculate similarities (cosine similarity)
        similarities = []
        for embedding, _ in self.embeddings:
            # Simple dot product similarity (normalized)
            similarity = np.dot(query_embedding.flatten(), embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(embedding)
            )
            similarities.append(similarity)

        # Get top-k results
        top_indices = np.argsort(similarities)[::-1][:k]
        top_similarities = np.array([similarities[i] for i in top_indices])

        return top_similarities.reshape(1, -1), top_indices.reshape(1, -1)
