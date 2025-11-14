"""
SessionManager - Manages session lifecycle, persistence, and retrieval.

Coordinates multiple sessions, handles disk persistence, and provides
session management utilities for the application layer.
"""

import json
import logging
import zlib
import time
from typing import Dict, Optional, List, Any, Tuple
from pathlib import Path
from datetime import datetime
from threading import RLock  # Reentrant lock to allow nested lock acquisition

from .session_memory import SessionMemory, SessionStatus
from .user_memory_store import UserMemoryStore

# Optional msgpack support
try:
    import msgpack
    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False
    msgpack = None
    logger = logging.getLogger(__name__)
    logger.debug("[SESSION MANAGER] msgpack not available - using JSON")


logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages session lifecycle and persistence.

    Responsibilities:
    - Create and retrieve sessions
    - Persist sessions to disk
    - Load sessions from disk
    - Handle session cleanup and archival
    - Thread-safe session access
    """

    def __init__(self, storage_dir: str = "data/sessions", config: Optional[Dict[str, Any]] = None):
        """
        Initialize session manager.

        Args:
            storage_dir: Directory for session persistence
            config: Optional configuration dictionary (for reasoning_trace.enabled, active_context_window, persistent_memory)
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Store config for passing to UserMemoryStore
        self._config = config

        # Active sessions (in-memory cache) - now keyed by (user_id, session_id)
        self._sessions: Dict[Tuple[str, str], SessionMemory] = {}

        # User memory stores (lazy-loaded cache)
        self._user_memory_stores: Dict[str, UserMemoryStore] = {}

        # Thread safety for concurrent access
        # Use RLock (reentrant lock) to allow nested lock acquisition
        # e.g., clear_session() can call get_or_create_session() while holding the lock
        self._lock = RLock()

        # Default values for single-user mode
        self._default_session_id = "default"
        self._default_user_id = "default_user"

        # Extract reasoning_trace.enabled flag from config (default: False)
        self._enable_reasoning_trace = False
        if config:
            self._enable_reasoning_trace = config.get("reasoning_trace", {}).get("enabled", False)

        # Extract active_context_window from config (default: 5)
        self._active_context_window = 5
        if config:
            self._active_context_window = config.get("active_context_window", 5)

        # Extract enable_conversation_summary from config (default: False)
        self._enable_conversation_summary = False
        if config:
            self._enable_conversation_summary = config.get("enable_conversation_summary", False)

        # Extract persistent memory config
        self._persistent_memory_config = config.get("persistent_memory", {}) if config else {}
        self._enable_persistent_memory = self._persistent_memory_config.get("enabled", False)
        self._user_memory_dir = self._persistent_memory_config.get("directory", "data/user_memory")
        self._embedding_model = self._persistent_memory_config.get("embedding_model", "text-embedding-3-small")
        
        # Session serialization optimization config
        perf_config = config.get("performance", {}) if config else {}
        session_config = perf_config.get("session_serialization", {})
        self._use_msgpack = session_config.get("use_msgpack", False)
        self._write_behind_enabled = session_config.get("write_behind", True)
        self._write_behind_interval = session_config.get("write_behind_interval", 30)  # seconds
        self._compression_threshold = session_config.get("compression_threshold", 100_000)  # bytes
        self._dirty_sessions: set = set()  # Track sessions that need saving
        self._background_saver_task = None
        
        # Start background saver if write-behind is enabled
        if self._write_behind_enabled:
            import threading
            self._background_saver_thread = threading.Thread(target=self._background_saver_loop, daemon=True)
            self._background_saver_thread.start()
            logger.info(f"[SESSION MANAGER] Write-behind caching enabled (interval: {self._write_behind_interval}s)")

        logger.info(f"[SESSION MANAGER] Initialized with storage: {self.storage_dir}, reasoning_trace={self._enable_reasoning_trace}, active_window={self._active_context_window}, persistent_memory={self._enable_persistent_memory}, msgpack={self._use_msgpack}")

    def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> SessionMemory:
        """
        Get existing session or create a new one.

        Args:
            session_id: Session identifier (uses default if not provided)
            user_id: User identifier (uses default if not provided)

        Returns:
            SessionMemory instance
        """
        session_id = session_id or self._default_session_id
        user_id = user_id or self._default_user_id
        session_key = (user_id, session_id)

        with self._lock:
            # Check in-memory cache
            if session_key in self._sessions:
                memory = self._sessions[session_key]
                logger.debug(f"[SESSION MANAGER] Retrieved cached session: {user_id}/{session_id}")
                return memory

            # Try to load from disk
            memory = self._load_session_from_disk(session_id, user_id)

            if memory:
                # Reactivate if it was cleared
                if memory.status == SessionStatus.CLEARED:
                    memory.status = SessionStatus.ACTIVE
                    logger.info(f"[SESSION MANAGER] Reactivated cleared session: {user_id}/{session_id}")

                self._sessions[session_key] = memory
                return memory

            # Get or create user memory store
            user_memory_store = None
            if self._enable_persistent_memory:
                user_memory_store = self._get_or_create_user_memory_store(user_id)

            # Create new session
            memory = SessionMemory(
                session_id=session_id,
                user_id=user_id,
                enable_reasoning_trace=self._enable_reasoning_trace,
                active_context_window=self._active_context_window,
                enable_conversation_summary=self._enable_conversation_summary,
                user_memory_store=user_memory_store,
                config=self._config
            )
            self._sessions[session_key] = memory
            logger.info(f"[SESSION MANAGER] Created new session: {user_id}/{session_id} (active window: {self._active_context_window})")

            return memory

    def _get_or_create_user_memory_store(self, user_id: str) -> UserMemoryStore:
        """
        Get or create user memory store (lazy loading).

        Args:
            user_id: User identifier

        Returns:
            UserMemoryStore instance
        """
        if user_id in self._user_memory_stores:
            return self._user_memory_stores[user_id]

        # Create new user memory store
        # Pass config for batch embeddings settings
        user_memory_store = UserMemoryStore(
            user_id=user_id,
            storage_dir=self._user_memory_dir,
            embedding_model=self._embedding_model,
            config=self._config
        )
        self._user_memory_stores[user_id] = user_memory_store
        logger.debug(f"[SESSION MANAGER] Created user memory store for: {user_id}")

        return user_memory_store

    def get_session(self, session_id: str, user_id: Optional[str] = None) -> Optional[SessionMemory]:
        """
        Get existing session without creating.

        Args:
            session_id: Session identifier
            user_id: User identifier (uses default if not provided)

        Returns:
            SessionMemory instance or None if not found
        """
        user_id = user_id or self._default_user_id
        session_key = (user_id, session_id)

        with self._lock:
            # Check cache
            if session_key in self._sessions:
                return self._sessions[session_key]

            # Try disk
            return self._load_session_from_disk(session_id, user_id)

    def save_session(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        memory: Optional[SessionMemory] = None
    ) -> bool:
        """
        Persist session to disk.

        Args:
            session_id: Session to save (uses default if not provided)
            user_id: User identifier (uses default if not provided)
            memory: SessionMemory instance (looked up if not provided)

        Returns:
            True if saved successfully
        """
        session_id = session_id or self._default_session_id
        user_id = user_id or self._default_user_id

        with self._lock:
            # Get memory instance
            session_key = (user_id, session_id)
            if memory is None:
                memory = self._sessions.get(session_key)
                if not memory:
                    logger.warning(f"[SESSION MANAGER] Session not found: {user_id}/{session_id}")
                    return False

            # Mark as dirty for write-behind, or save immediately
            if self._write_behind_enabled:
                self._dirty_sessions.add(session_key)
                logger.debug(f"[SESSION MANAGER] Marked session as dirty: {user_id}/{session_id}")
                return True
            else:
                # Save immediately
                return self._save_session_to_disk(session_id, user_id, memory)

    def clear_session(self, session_id: Optional[str] = None, user_id: Optional[str] = None, clear_all: bool = False) -> SessionMemory:
        """
        Clear a session's memory.

        This is called when the user issues /clear command.

        Args:
            session_id: Session to clear (uses default if not provided)
            user_id: User identifier (uses default if not provided)
            clear_all: If True, also clear persistent user memory

        Returns:
            Cleared SessionMemory instance
        """
        session_id = session_id or self._default_session_id
        user_id = user_id or self._default_user_id

        with self._lock:
            memory = self.get_or_create_session(session_id, user_id)
            memory.clear()

            # Clear persistent memory if requested
            if clear_all and self._enable_persistent_memory and user_id in self._user_memory_stores:
                user_memory_store = self._user_memory_stores[user_id]
                # Clear all memories (set them as expired effectively)
                for memory_entry in user_memory_store.memories:
                    memory_entry.ttl_days = 0  # Mark for immediate expiration
                user_memory_store.cleanup_expired_memories()

            # Save cleared state to disk immediately (force save, bypass write-behind)
            self._save_session_to_disk(session_id, user_id, memory)
            if (user_id, session_id) in self._dirty_sessions:
                self._dirty_sessions.remove((user_id, session_id))

            logger.info(f"[SESSION MANAGER] Cleared session: {user_id}/{session_id}" + (" (including persistent memory)" if clear_all else ""))
            return memory

    def delete_session(self, session_id: str, user_id: Optional[str] = None) -> bool:
        """
        Delete a session entirely (from memory and disk).

        Args:
            session_id: Session to delete
            user_id: User identifier (uses default if not provided)

        Returns:
            True if deleted successfully
        """
        user_id = user_id or self._default_user_id
        session_key = (user_id, session_id)

        with self._lock:
            # Remove from memory
            if session_key in self._sessions:
                del self._sessions[session_key]

            # Remove from disk
            filepath = self._get_session_filepath(session_id, user_id)
            if filepath.exists():
                try:
                    filepath.unlink()
                    logger.info(f"[SESSION MANAGER] Deleted session: {user_id}/{session_id}")
                    return True
                except Exception as e:
                    logger.error(f"[SESSION MANAGER] Failed to delete session: {e}")
                    return False

            return True

    def list_sessions(self) -> List[Dict[str, any]]:
        """
        List all available sessions.

        Returns:
            List of session metadata
        """
        sessions = []

        # Check disk for all saved sessions (JSON, msgpack, compressed)
        for filepath in self.storage_dir.rglob("*"):
            # Skip compressed files and non-session files
            if filepath.suffix in ['.gz'] or filepath.name.startswith('.'):
                continue
            # Only process session files
            if filepath.suffix not in ['.json', '.msgpack']:
                continue
            
            try:
                # Try to load session (handles all formats)
                memory = self._load_session_from_disk(
                    filepath.stem.replace('.json', '').replace('.msgpack', ''),
                    filepath.parent.name if filepath.parent != self.storage_dir else None
                )
                if not memory:
                    continue
                
                data = memory.to_dict()

                sessions.append({
                    "session_id": data["session_id"],
                    "status": data["status"],
                    "created_at": data["created_at"],
                    "last_active_at": data["last_active_at"],
                    "interactions": len(data["interactions"]),
                    "total_requests": data["metadata"].get("total_requests", 0),
                })
            except Exception as e:
                logger.error(f"[SESSION MANAGER] Error reading session {filepath}: {e}")

        return sorted(sessions, key=lambda x: x["last_active_at"], reverse=True)

    def archive_old_sessions(self, days: int = 30) -> int:
        """
        Archive sessions older than N days.

        Args:
            days: Archive sessions inactive for this many days

        Returns:
            Number of sessions archived
        """
        archived = 0
        cutoff = datetime.now().timestamp() - (days * 86400)

        for session_id, memory in list(self._sessions.items()):
            try:
                last_active = datetime.fromisoformat(memory.last_active_at).timestamp()
                if last_active < cutoff:
                    memory.status = SessionStatus.ARCHIVED
                    self.save_session(session_id, memory)
                    del self._sessions[session_id]
                    archived += 1
                    logger.info(f"[SESSION MANAGER] Archived session: {session_id}")
            except Exception as e:
                logger.error(f"[SESSION MANAGER] Error archiving session: {e}")

        return archived

    def _save_session_to_disk(self, session_id: str, user_id: str, memory: SessionMemory) -> bool:
        """
        Save session to disk with optimized serialization.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            memory: SessionMemory instance
            
        Returns:
            True if saved successfully
        """
        try:
            data = memory.to_dict()
            
            # Determine file extension and serialization method
            use_msgpack = self._use_msgpack and MSGPACK_AVAILABLE
            filepath = self._get_session_filepath(session_id, user_id, use_msgpack=use_msgpack)
            
            # Serialize data
            if use_msgpack:
                # Use msgpack (5-10x faster, 30-50% smaller)
                serialized = msgpack.packb(data, use_bin_type=True)
            else:
                # Use JSON
                serialized = json.dumps(data, indent=2, ensure_ascii=False, default=str).encode('utf-8')
            
            # Compress if above threshold
            if len(serialized) > self._compression_threshold:
                serialized = zlib.compress(serialized, level=6)
                filepath = filepath.with_suffix(filepath.suffix + '.gz')
                logger.debug(f"[SESSION MANAGER] Compressed session ({len(serialized)} bytes): {filepath}")
            
            # Write to disk
            with open(filepath, 'wb') as f:
                f.write(serialized)
            
            logger.debug(f"[SESSION MANAGER] Saved session to: {filepath} ({len(serialized)} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"[SESSION MANAGER] Failed to save session: {e}", exc_info=True)
            return False
    
    def _background_saver_loop(self):
        """Background thread loop for write-behind caching."""
        while True:
            try:
                time.sleep(self._write_behind_interval)
                
                with self._lock:
                    dirty_sessions = list(self._dirty_sessions)
                    self._dirty_sessions.clear()
                
                if dirty_sessions:
                    logger.debug(f"[SESSION MANAGER] Background saver: saving {len(dirty_sessions)} sessions")
                    for user_id, session_id in dirty_sessions:
                        session_key = (user_id, session_id)
                        memory = self._sessions.get(session_key)
                        if memory:
                            self._save_session_to_disk(session_id, user_id, memory)
                            
            except Exception as e:
                logger.error(f"[SESSION MANAGER] Background saver error: {e}")

    def _load_session_from_disk(self, session_id: str, user_id: Optional[str] = None) -> Optional[SessionMemory]:
        """
        Load session from disk with optimized deserialization.

        Args:
            session_id: Session identifier
            user_id: User identifier (uses default if not provided)

        Returns:
            SessionMemory instance or None if not found
        """
        user_id = user_id or self._default_user_id
        
        # Try different file formats (msgpack, JSON, compressed)
        filepath = self._get_session_filepath(session_id, user_id, use_msgpack=False)
        compressed_path = filepath.with_suffix(filepath.suffix + '.gz')
        msgpack_path = self._get_session_filepath(session_id, user_id, use_msgpack=True)
        msgpack_compressed_path = msgpack_path.with_suffix(msgpack_path.suffix + '.gz')
        
        # Try to find existing file
        actual_path = None
        use_msgpack = False
        is_compressed = False
        
        for path, is_msgpack, is_comp in [
            (msgpack_compressed_path, True, True),
            (msgpack_path, True, False),
            (compressed_path, False, True),
            (filepath, False, False)
        ]:
            if path.exists():
                actual_path = path
                use_msgpack = is_msgpack
                is_compressed = is_comp
                break
        
        if not actual_path:
            return None

        try:
            # Read file
            with open(actual_path, 'rb') as f:
                serialized = f.read()
            
            # Decompress if needed
            if is_compressed:
                serialized = zlib.decompress(serialized)
                logger.debug(f"[SESSION MANAGER] Decompressed session: {actual_path}")
            
            # Deserialize
            if use_msgpack and MSGPACK_AVAILABLE:
                data = msgpack.unpackb(serialized, raw=False)
            else:
                data = json.loads(serialized.decode('utf-8'))

            memory = SessionMemory.from_dict(data)

            # Re-attach user memory store if persistent memory is enabled
            if self._enable_persistent_memory:
                user_memory_store = self._get_or_create_user_memory_store(user_id)
                memory.user_memory_store = user_memory_store

            logger.debug(f"[SESSION MANAGER] Loaded session from disk: {user_id}/{session_id}")
            return memory

        except Exception as e:
            logger.error(f"[SESSION MANAGER] Failed to load session: {e}", exc_info=True)
            return None

    def _get_session_filepath(self, session_id: str, user_id: Optional[str] = None, use_msgpack: bool = False) -> Path:
        """
        Get filepath for session storage.

        Args:
            session_id: Session identifier
            user_id: User identifier (uses default if not provided)
            use_msgpack: Whether to use msgpack extension

        Returns:
            Path to session file
        """
        user_id = user_id or self._default_user_id

        # Create user-specific subdirectory
        user_dir = self.storage_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize session ID for filesystem
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
        extension = ".msgpack" if use_msgpack else ".json"
        return user_dir / f"{safe_id}{extension}"

    def auto_save_enabled(self, enabled: bool = True, interval: int = 5):
        """
        Enable automatic session saving.

        Args:
            enabled: Whether to enable auto-save
            interval: Save interval in interactions
        """
        # This would be implemented with a background thread or hook
        # For now, we'll save manually after each interaction
        pass

    def get_context_for_llm(self, session_id: Optional[str] = None) -> str:
        """
        Get formatted context summary for LLM prompt injection.

        Args:
            session_id: Session identifier (uses default if not provided)

        Returns:
            Formatted context string
        """
        memory = self.get_or_create_session(session_id)
        return memory.get_context_summary()

    def get_langgraph_context(
        self,
        session_id: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Get context formatted for LangGraph state.

        Args:
            session_id: Session identifier (uses default if not provided)

        Returns:
            Dictionary for LangGraph state injection
        """
        memory = self.get_or_create_session(session_id)
        return memory.get_langgraph_context()

    def __repr__(self) -> str:
        return (
            f"SessionManager(storage={self.storage_dir}, "
            f"active_sessions={len(self._sessions)})"
        )
