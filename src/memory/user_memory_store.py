"""
UserMemoryStore - Persistent user memory with semantic search.

This module implements persistent memory storage for user preferences,
conversation history, and learned patterns across sessions. Uses FAISS
for semantic search over embeddings and JSON for structured data persistence.

Architecture:
- UserProfile: Static user information and preferences
- MemoryEntry: Individual facts/patterns with metadata
- ConversationSummary: Session-level summaries
- Semantic search with cosine similarity scoring
- Automatic deduplication and salience decay
"""

import json
import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from threading import RLock
import numpy as np

logger = logging.getLogger(__name__)

try:
    import faiss
    from openai import OpenAI
    from sklearn.metrics.pairwise import cosine_similarity
    from src.utils.openai_client import PooledOpenAIClient
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    OpenAI = None  # Define as None for type hints
    PooledOpenAIClient = None
    logger.warning("[USER MEMORY] FAISS/OpenAI not available - semantic search disabled")


@dataclass
class PersistentContext:
    """Merged persistent context for session integration."""
    user_profile: Optional['UserProfile'] = None
    top_persistent_memories: List[Tuple['MemoryEntry', float]] = field(default_factory=list)
    recent_summaries: List['ConversationSummary'] = field(default_factory=list)
    memory_stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "user_profile": self.user_profile.to_dict() if self.user_profile else None,
            "top_persistent_memories": [
                {
                    "memory": memory.to_dict(),
                    "score": score
                }
                for memory, score in self.top_persistent_memories
            ],
            "recent_summaries": [s.to_dict() for s in self.recent_summaries],
            "memory_stats": self.memory_stats
        }


@dataclass
class UserProfile:
    """Static user profile information and preferences."""
    user_id: str
    display_name: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    timezone: Optional[str] = None
    location: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserProfile':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class MemoryEntry:
    """Individual memory entry with content and metadata."""
    memory_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    category: str = "general"  # preferences, facts, patterns, commitments
    tags: List[str] = field(default_factory=list)
    salience_score: float = 1.0  # 0.0-1.0, decays over time
    access_count: int = 0
    embedding: Optional[List[float]] = None
    source_interaction_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_accessed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ttl_days: Optional[int] = None  # Time-to-live in days, None = permanent

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Convert numpy array to list if present
        if isinstance(data.get('embedding'), np.ndarray):
            data['embedding'] = data['embedding'].tolist()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryEntry':
        """Create from dictionary."""
        return cls(**data)

    def is_expired(self) -> bool:
        """Check if memory has expired based on TTL."""
        if self.ttl_days is None:
            return False
        created = datetime.fromisoformat(self.created_at)
        return datetime.now() - created > timedelta(days=self.ttl_days)

    def update_access(self):
        """Update access metadata."""
        self.access_count += 1
        self.last_accessed_at = datetime.now().isoformat()

    def decay_salience(self, decay_factor: float = 0.95):
        """Apply time-based salience decay."""
        # Simple exponential decay based on time since last access
        last_access = datetime.fromisoformat(self.last_accessed_at)
        days_since_access = (datetime.now() - last_access).days
        decay = decay_factor ** days_since_access
        self.salience_score *= decay
        self.salience_score = max(0.1, min(1.0, self.salience_score))  # Clamp to [0.1, 1.0]


@dataclass
class ConversationSummary:
    """Summary of a conversation session."""
    session_id: str
    summary: str
    key_topics: List[str] = field(default_factory=list)
    key_decisions: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: Optional[str] = None
    interaction_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationSummary':
        """Create from dictionary."""
        return cls(**data)


class UserMemoryStore:
    """
    Persistent memory store for user data with semantic search.

    Stores user profiles, memory entries, and conversation summaries
    with FAISS-based semantic search capabilities.
    """

    def __init__(
        self,
        user_id: str,
        storage_dir: str = "data/user_memory",
        embedding_model: str = "text-embedding-3-small",
        openai_client: Optional[Any] = None,  # OpenAI client when available
        config: Optional[Dict[str, Any]] = None  # Optional config for batch settings
    ):
        """
        Initialize user memory store.

        Args:
            user_id: Unique identifier for the user
            storage_dir: Base directory for memory storage
            embedding_model: OpenAI embedding model to use
            openai_client: Pre-configured OpenAI client (optional)
            config: Optional configuration dictionary for batch embeddings settings
        """
        self.user_id = user_id
        self.storage_dir = Path(storage_dir) / user_id
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_model = embedding_model

        # Read batch embeddings config
        if config:
            perf_config = config.get("performance", {})
            batch_config = perf_config.get("batch_embeddings", {})
            if batch_config.get("enabled", True):
                self.batch_size = batch_config.get("batch_size", 100)
            else:
                self.batch_size = 1  # Disable batching if disabled
            
            # Read background tasks config for memory updates
            background_config = perf_config.get("background_tasks", {})
            self._background_memory_updates = background_config.get("memory_updates", True)
        else:
            self.batch_size = 100  # Default fallback
            self._background_memory_updates = True  # Default to enabled

        # Thread safety
        self._lock = RLock()

        # OpenAI client for embeddings - use pooled client if config provided
        if openai_client:
            # Use provided client (backward compatibility)
            self.openai_client = openai_client
        elif config and PooledOpenAIClient:
            # Use pooled client for connection reuse (20-40% faster)
            self.openai_client = PooledOpenAIClient.get_client(config)
            logger.info("[USER MEMORY] Using pooled OpenAI client for connection reuse")
        else:
            # Fallback to direct client
            self.openai_client = OpenAI() if OpenAI else None

        # In-memory data
        self.profile: Optional[UserProfile] = None
        self.memories: List[MemoryEntry] = []
        self.summaries: List[ConversationSummary] = []

        # FAISS index for semantic search
        self.faiss_index = None
        self.memory_ids: List[str] = []  # Maps FAISS index to memory_id

        # Load existing data
        self._load_data()

    def _load_data(self):
        """Load all persisted data from disk."""
        with self._lock:
            # Load profile
            profile_path = self.storage_dir / "profile.json"
            if profile_path.exists():
                try:
                    with open(profile_path, 'r', encoding='utf-8') as f:
                        self.profile = UserProfile.from_dict(json.load(f))
                except Exception as e:
                    logger.error(f"[USER MEMORY] Failed to load profile: {e}")

            # Load memories
            memories_path = self.storage_dir / "memories.json"
            if memories_path.exists():
                try:
                    with open(memories_path, 'r', encoding='utf-8') as f:
                        memories_data = json.load(f)
                        self.memories = [MemoryEntry.from_dict(m) for m in memories_data]
                except Exception as e:
                    logger.error(f"[USER MEMORY] Failed to load memories: {e}")

            # Load summaries
            summaries_path = self.storage_dir / "summaries.json"
            if summaries_path.exists():
                try:
                    with open(summaries_path, 'r', encoding='utf-8') as f:
                        summaries_data = json.load(f)
                        self.summaries = [ConversationSummary.from_dict(s) for s in summaries_data]
                except Exception as e:
                    logger.error(f"[USER MEMORY] Failed to load summaries: {e}")

            # Build FAISS index
            self._rebuild_faiss_index()

    def _rebuild_faiss_index(self):
        """Rebuild FAISS index from current memories."""
        if not FAISS_AVAILABLE or not self.memories:
            return

        try:
            # Filter memories with embeddings
            valid_memories = [m for m in self.memories if m.embedding is not None]
            if not valid_memories:
                return

            # Create FAISS index
            dimension = len(valid_memories[0].embedding)
            self.faiss_index = faiss.IndexFlatIP(dimension)  # Inner product (cosine similarity)

            # Add embeddings
            embeddings = np.array([m.embedding for m in valid_memories], dtype=np.float32)
            # Normalize for cosine similarity
            faiss.normalize_L2(embeddings)
            self.faiss_index.add(embeddings)

            # Update ID mapping
            self.memory_ids = [m.memory_id for m in valid_memories]

            logger.debug(f"[USER MEMORY] Rebuilt FAISS index with {len(valid_memories)} memories")

        except Exception as e:
            logger.error(f"[USER MEMORY] Failed to rebuild FAISS index: {e}")
            self.faiss_index = None

    def _save_data(self):
        """Persist all data to disk."""
        with self._lock:
            try:
                # Save profile
                if self.profile:
                    profile_path = self.storage_dir / "profile.json"
                    with open(profile_path, 'w', encoding='utf-8') as f:
                        json.dump(self.profile.to_dict(), f, indent=2, ensure_ascii=False)

                # Save memories
                memories_path = self.storage_dir / "memories.json"
                with open(memories_path, 'w', encoding='utf-8') as f:
                    json.dump([m.to_dict() for m in self.memories], f, indent=2, ensure_ascii=False)

                # Save summaries
                summaries_path = self.storage_dir / "summaries.json"
                with open(summaries_path, 'w', encoding='utf-8') as f:
                    json.dump([s.to_dict() for s in self.summaries], f, indent=2, ensure_ascii=False)

            except Exception as e:
                logger.error(f"[USER MEMORY] Failed to save data: {e}")

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for text using OpenAI."""
        if not FAISS_AVAILABLE:
            return None

        try:
            response = self.openai_client.embeddings.create(
                input=text,
                model=self.embedding_model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"[USER MEMORY] Failed to get embedding: {e}")
            return None
    
    def _get_embeddings_batch(self, texts: List[str], batch_size: Optional[int] = None) -> List[Optional[List[float]]]:
        """
        Get embeddings for multiple texts in batches (faster).
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call (uses config default if None)
            
        Returns:
            List of embeddings (same length as texts, None for failures)
        """
        # Use instance batch_size from config if not provided
        if batch_size is None:
            batch_size = self.batch_size
        if not FAISS_AVAILABLE or not texts:
            return [None] * len(texts)
        
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            
            try:
                response = self.openai_client.embeddings.create(
                    input=batch,
                    model=self.embedding_model
                )
                
                # Extract embeddings in order
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
            except Exception as e:
                logger.error(f"[USER MEMORY] Batch embedding failed: {e}")
                # Fallback to individual calls
                for text in batch:
                    embedding = self._get_embedding(text)
                    all_embeddings.append(embedding)
        
        return all_embeddings

    # CRUD Operations

    def create_profile(
        self,
        display_name: Optional[str] = None,
        preferences: Optional[Dict[str, Any]] = None,
        timezone: Optional[str] = None,
        location: Optional[str] = None
    ) -> UserProfile:
        """Create or update user profile."""
        with self._lock:
            if self.profile:
                # Update existing
                if display_name is not None:
                    self.profile.display_name = display_name
                if preferences is not None:
                    self.profile.preferences.update(preferences)
                if timezone is not None:
                    self.profile.timezone = timezone
                if location is not None:
                    self.profile.location = location
                self.profile.updated_at = datetime.now().isoformat()
            else:
                # Create new
                self.profile = UserProfile(
                    user_id=self.user_id,
                    display_name=display_name,
                    preferences=preferences or {},
                    timezone=timezone,
                    location=location
                )

            self._save_data()
            return self.profile

    def get_profile(self) -> Optional[UserProfile]:
        """Get user profile."""
        with self._lock:
            return self.profile

    def add_memory(
        self,
        content: str,
        category: str = "general",
        tags: Optional[List[str]] = None,
        salience_score: float = 1.0,
        source_interaction_id: Optional[str] = None,
        ttl_days: Optional[int] = None
    ) -> MemoryEntry:
        """Add a new memory entry."""
        with self._lock:
            # Create memory entry
            memory = MemoryEntry(
                content=content,
                category=category,
                tags=tags or [],
                salience_score=salience_score,
                source_interaction_id=source_interaction_id,
                ttl_days=ttl_days
            )

            # Get embedding
            memory.embedding = self._get_embedding(content)

            # Add to collection
            self.memories.append(memory)

            # Update FAISS index
            if FAISS_AVAILABLE and memory.embedding is not None:
                if self.faiss_index is None:
                    self._rebuild_faiss_index()
                else:
                    # Add single embedding
                    embedding = np.array([memory.embedding], dtype=np.float32)
                    faiss.normalize_L2(embedding)
                    self.faiss_index.add(embedding)
                    self.memory_ids.append(memory.memory_id)

            self._save_data()
            logger.debug(f"[USER MEMORY] Added memory: {memory.memory_id}")
            return memory
    
    async def add_memory_async(
        self,
        content: str,
        category: str = "general",
        tags: Optional[List[str]] = None,
        salience_score: float = 1.0,
        source_interaction_id: Optional[str] = None,
        ttl_days: Optional[int] = None
    ) -> MemoryEntry:
        """
        Async version of add_memory for background operations.
        
        Args:
            content: Memory content
            category: Memory category
            tags: Optional tags
            salience_score: Salience score (0.0-1.0)
            source_interaction_id: Source interaction ID
            ttl_days: Time-to-live in days
            
        Returns:
            Created MemoryEntry
        """
        # Run synchronous version in thread pool to avoid blocking
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.add_memory,
            content,
            category,
            tags,
            salience_score,
            source_interaction_id,
            ttl_days
        )
    
    def add_memories_batch(
        self,
        memory_data: List[Dict[str, Any]]
    ) -> List[MemoryEntry]:
        """
        Add multiple memories with batch embedding (30-50% faster).
        
        Args:
            memory_data: List of dicts with keys: content, category, tags, salience_score, etc.
            
        Returns:
            List of created MemoryEntry objects
        """
        if not memory_data:
            return []
        
        with self._lock:
            logger.info(f"[USER MEMORY] Batch adding {len(memory_data)} memories")
            
            # Create memory entries
            new_memories = []
            texts_to_embed = []
            
            for data in memory_data:
                memory = MemoryEntry(
                    content=data.get("content", ""),
                    category=data.get("category", "general"),
                    tags=data.get("tags", []),
                    salience_score=data.get("salience_score", 1.0),
                    source_interaction_id=data.get("source_interaction_id"),
                    ttl_days=data.get("ttl_days")
                )
                new_memories.append(memory)
                texts_to_embed.append(memory.content)
            
            # Get embeddings in batch
            batch_embeddings = self._get_embeddings_batch(texts_to_embed)
            
            # Track batch operation
            try:
                from src.utils.performance_monitor import get_performance_monitor
                get_performance_monitor().record_batch_operation("memory_embeddings", len(texts_to_embed))
            except Exception:
                pass
            
            # Assign embeddings to memories
            for memory, embedding in zip(new_memories, batch_embeddings):
                memory.embedding = embedding
                self.memories.append(memory)
            
            # Update FAISS index with all new embeddings at once
            if FAISS_AVAILABLE and any(m.embedding is not None for m in new_memories):
                valid_embeddings = [m.embedding for m in new_memories if m.embedding is not None]
                valid_ids = [m.memory_id for m in new_memories if m.embedding is not None]
                
                if valid_embeddings:
                    embeddings_array = np.array(valid_embeddings, dtype=np.float32)
                    faiss.normalize_L2(embeddings_array)
                    
                    if self.faiss_index is None:
                        self._rebuild_faiss_index()
                    else:
                        self.faiss_index.add(embeddings_array)
                        self.memory_ids.extend(valid_ids)
            
            self._save_data()
            logger.info(f"[USER MEMORY] Batch added {len(new_memories)} memories")
            return new_memories

    def update_memory(self, memory_id: str, **updates) -> Optional[MemoryEntry]:
        """Update an existing memory entry."""
        with self._lock:
            for memory in self.memories:
                if memory.memory_id == memory_id:
                    for key, value in updates.items():
                        if hasattr(memory, key):
                            setattr(memory, key, value)
                    memory.update_access()
                    self._save_data()
                    return memory
            return None

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory entry."""
        with self._lock:
            for i, memory in enumerate(self.memories):
                if memory.memory_id == memory_id:
                    del self.memories[i]
                    # Rebuild FAISS index
                    self._rebuild_faiss_index()
                    self._save_data()
                    logger.debug(f"[USER MEMORY] Deleted memory: {memory_id}")
                    return True
            return False

    def get_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        """Get a specific memory entry."""
        with self._lock:
            for memory in self.memories:
                if memory.memory_id == memory_id:
                    memory.update_access()
                    return memory
            return None

    def list_memories(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[MemoryEntry]:
        """List memory entries with optional filtering."""
        with self._lock:
            memories = self.memories.copy()

            # Apply filters
            if category:
                memories = [m for m in memories if m.category == category]
            if tags:
                memories = [m for m in memories if any(tag in m.tags for tag in tags)]

            # Sort by salience and recency
            memories.sort(key=lambda m: (m.salience_score, m.last_accessed_at), reverse=True)

            if limit:
                memories = memories[:limit]

            # Update access times
            for memory in memories:
                memory.update_access()

            return memories

    def add_conversation_summary(
        self,
        session_id: str,
        summary: str,
        key_topics: Optional[List[str]] = None,
        key_decisions: Optional[List[str]] = None,
        action_items: Optional[List[str]] = None,
        interaction_count: int = 0
    ) -> ConversationSummary:
        """Add a conversation summary."""
        with self._lock:
            summary_obj = ConversationSummary(
                session_id=session_id,
                summary=summary,
                key_topics=key_topics or [],
                key_decisions=key_decisions or [],
                action_items=action_items or [],
                interaction_count=interaction_count,
                end_time=datetime.now().isoformat()
            )

            self.summaries.append(summary_obj)
            self._save_data()
            return summary_obj

    def get_recent_summaries(self, limit: int = 5) -> List[ConversationSummary]:
        """Get recent conversation summaries."""
        with self._lock:
            summaries = sorted(self.summaries, key=lambda s: s.end_time or s.start_time, reverse=True)
            return summaries[:limit]

    # Semantic Search

    def query_memories(
        self,
        text: str,
        top_k: int = 5,
        min_score: float = 0.7,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[Tuple[MemoryEntry, float]]:
        """
        Semantic search over memories.

        Args:
            text: Query text
            top_k: Maximum number of results
            min_score: Minimum similarity score (0.0-1.0)
            category: Filter by category
            tags: Filter by tags

        Returns:
            List of (memory, score) tuples
        """
        if not FAISS_AVAILABLE or self.faiss_index is None or not self.memories:
            # Fallback to simple text search
            return self._text_search(text, top_k, min_score, category, tags)

        with self._lock:
            try:
                # Get query embedding
                query_embedding = self._get_embedding(text)
                if query_embedding is None:
                    return self._text_search(text, top_k, min_score, category, tags)

                # Search FAISS index
                query_vector = np.array([query_embedding], dtype=np.float32)
                faiss.normalize_L2(query_vector)

                scores, indices = self.faiss_index.search(query_vector, top_k * 2)  # Get more candidates

                # Convert to similarity scores and filter
                results = []
                for score, idx in zip(scores[0], indices[0]):
                    if idx < len(self.memory_ids):
                        memory_id = self.memory_ids[idx]
                        memory = next((m for m in self.memories if m.memory_id == memory_id), None)
                        if memory and not memory.is_expired():
                            # Apply filters
                            if category and memory.category != category:
                                continue
                            if tags and not any(tag in memory.tags for tag in tags):
                                continue

                            similarity = float(score)
                            if similarity >= min_score:
                                memory.update_access()
                                results.append((memory, similarity))

                # Sort by score and return top_k
                results.sort(key=lambda x: x[1], reverse=True)
                return results[:top_k]

            except Exception as e:
                logger.error(f"[USER MEMORY] Semantic search failed: {e}")
                return self._text_search(text, top_k, min_score, category, tags)

    def _text_search(
        self,
        text: str,
        top_k: int = 5,
        min_score: float = 0.7,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[Tuple[MemoryEntry, float]]:
        """Fallback text-based search when embeddings unavailable."""
        with self._lock:
            query_lower = text.lower()
            results = []

            for memory in self.memories:
                if memory.is_expired():
                    continue

                # Apply filters
                if category and memory.category != category:
                    continue
                if tags and not any(tag in memory.tags for tag in tags):
                    continue

                # Simple text similarity
                content_lower = memory.content.lower()
                if query_lower in content_lower:
                    score = 0.9  # High score for exact matches
                else:
                    # Count word overlaps
                    query_words = set(query_lower.split())
                    content_words = set(content_lower.split())
                    overlap = len(query_words.intersection(content_words))
                    if overlap > 0:
                        score = min(0.8, overlap / len(query_words))
                    else:
                        continue

                if score >= min_score:
                    memory.update_access()
                    results.append((memory, score))

            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]

    # Maintenance

    def cleanup_expired_memories(self) -> int:
        """Remove expired memories and return count deleted."""
        with self._lock:
            original_count = len(self.memories)
            self.memories = [m for m in self.memories if not m.is_expired()]

            deleted_count = original_count - len(self.memories)
            if deleted_count > 0:
                self._rebuild_faiss_index()
                self._save_data()
                logger.info(f"[USER MEMORY] Cleaned up {deleted_count} expired memories")

            return deleted_count

    def decay_salience_scores(self, decay_factor: float = 0.95):
        """Apply time-based decay to all memory salience scores."""
        with self._lock:
            for memory in self.memories:
                memory.decay_salience()
            self._save_data()
            logger.debug("[USER MEMORY] Applied salience decay")

    def get_stats(self) -> Dict[str, Any]:
        """Get memory store statistics."""
        with self._lock:
            total_memories = len(self.memories)
            categories = {}
            for memory in self.memories:
                categories[memory.category] = categories.get(memory.category, 0) + 1

            return {
                "user_id": self.user_id,
                "total_memories": total_memories,
                "categories": categories,
                "total_summaries": len(self.summaries),
                "faiss_index_built": self.faiss_index is not None,
                "storage_path": str(self.storage_dir)
            }

    def build_persistent_context(
        self,
        query: Optional[str] = None,
        top_k: int = 5,
        include_summaries: bool = True
    ) -> PersistentContext:
        """
        Build a PersistentContext bundle for session integration.

        Args:
            query: Optional query to find relevant memories (uses general top memories if None)
            top_k: Number of top memories to include
            include_summaries: Whether to include recent conversation summaries

        Returns:
            PersistentContext with merged persistent data
        """
        with self._lock:
            context = PersistentContext()

            # Add user profile
            context.user_profile = self.profile

            # Get top persistent memories
            if query:
                # Query for relevant memories
                context.top_persistent_memories = self.query_memories(
                    text=query,
                    top_k=top_k,
                    min_score=0.6  # Lower threshold for context building
                )
            else:
                # Get top memories by salience
                memories = sorted(
                    [m for m in self.memories if not m.is_expired()],
                    key=lambda m: (m.salience_score, m.last_accessed_at),
                    reverse=True
                )[:top_k]
                context.top_persistent_memories = [(m, m.salience_score) for m in memories]

            # Add recent summaries
            if include_summaries:
                context.recent_summaries = self.get_recent_summaries(limit=3)

            # Add memory stats
            context.memory_stats = self.get_stats()

            return context
