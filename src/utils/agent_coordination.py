"""
Agent Coordination Utilities

Provides lock management and coordination mechanisms for multiple agents
working on the same codebase simultaneously.

Usage:
    from src.utils.agent_coordination import acquire_lock, release_lock, check_conflicts
    
    # Before modifying files
    if acquire_lock("src/agent/enriched_stock_agent.py", agent_id="agent_1"):
        try:
            # Do work
            pass
        finally:
            release_lock("src/agent/enriched_stock_agent.py", agent_id="agent_1")
"""

import json
import os
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
LOCKS_DIR = BASE_DIR / "data" / ".agent_locks"
STATUS_BOARD_PATH = LOCKS_DIR / "status_board.json"
MESSAGES_DIR = LOCKS_DIR / "messages"

# Ensure directories exist
LOCKS_DIR.mkdir(parents=True, exist_ok=True)
MESSAGES_DIR.mkdir(parents=True, exist_ok=True)

# Lock timeout (seconds) - if lock is older than this, consider it stale
LOCK_TIMEOUT = 3600  # 1 hour


def _get_agent_id() -> str:
    """Get current agent ID from environment or generate one."""
    import os
    agent_id = os.environ.get("AGENT_ID", "unknown_agent")
    return agent_id


def _load_status_board() -> Dict[str, Any]:
    """Load the status board from disk."""
    if not STATUS_BOARD_PATH.exists():
        return {
            "version": "1.0",
            "last_updated": None,
            "active_locks": [],
            "agent_assignments": {},
            "file_modification_history": [],
            "conflicts": [],
            "messages": []
        }
    
    try:
        with open(STATUS_BOARD_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading status board: {e}")
        return {
            "version": "1.0",
            "last_updated": None,
            "active_locks": [],
            "agent_assignments": {},
            "file_modification_history": [],
            "conflicts": [],
            "messages": []
        }


def _save_status_board(board: Dict[str, Any]) -> None:
    """Save the status board to disk."""
    board["last_updated"] = datetime.now().isoformat()
    try:
        with open(STATUS_BOARD_PATH, 'w') as f:
            json.dump(board, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving status board: {e}")


def _is_lock_stale(lock_timestamp: float) -> bool:
    """Check if a lock is stale (older than timeout)."""
    age = time.time() - lock_timestamp
    return age > LOCK_TIMEOUT


def acquire_lock(file_path: str, agent_id: Optional[str] = None, timeout: int = 300) -> bool:
    """
    Acquire a lock for a file.
    
    Args:
        file_path: Path to the file to lock (relative to workspace root)
        agent_id: Agent identifier (defaults to AGENT_ID env var or "unknown_agent")
        timeout: Maximum time to wait for lock (seconds)
    
    Returns:
        True if lock acquired, False otherwise
    """
    if agent_id is None:
        agent_id = _get_agent_id()
    
    # Normalize file path
    file_path = str(Path(file_path).as_posix())
    
    # Check for conflicts
    conflicts = check_conflicts([file_path], agent_id)
    if conflicts:
        logger.warning(f"Conflicts detected for {file_path}: {conflicts}")
        return False
    
    # Create lock file
    lock_filename = f"{agent_id}_{int(time.time())}_{file_path.replace('/', '_')}.lock"
    lock_file_path = LOCKS_DIR / lock_filename
    
    try:
        lock_data = {
            "agent_id": agent_id,
            "file_path": file_path,
            "timestamp": time.time(),
            "status": "in_progress",
            "estimated_completion": time.time() + timeout
        }
        
        with open(lock_file_path, 'w') as f:
            json.dump(lock_data, f, indent=2)
        
        # Update status board
        board = _load_status_board()
        board["active_locks"].append({
            "agent_id": agent_id,
            "file_path": file_path,
            "lock_file": lock_filename,
            "timestamp": lock_data["timestamp"],
            "status": "in_progress"
        })
        board["agent_assignments"][file_path] = agent_id
        _save_status_board(board)
        
        logger.info(f"Lock acquired: {file_path} by {agent_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error acquiring lock for {file_path}: {e}")
        return False


def release_lock(file_path: str, agent_id: Optional[str] = None) -> bool:
    """
    Release a lock for a file.
    
    Args:
        file_path: Path to the file to unlock
        agent_id: Agent identifier
    
    Returns:
        True if lock released, False otherwise
    """
    if agent_id is None:
        agent_id = _get_agent_id()
    
    # Normalize file path
    file_path = str(Path(file_path).as_posix())
    
    # Find and remove lock files
    lock_files = list(LOCKS_DIR.glob(f"*_{file_path.replace('/', '_')}.lock"))
    removed = False
    
    for lock_file in lock_files:
        try:
            with open(lock_file, 'r') as f:
                lock_data = json.load(f)
            
            if lock_data.get("agent_id") == agent_id:
                lock_file.unlink()
                removed = True
                logger.info(f"Lock released: {file_path} by {agent_id}")
        except Exception as e:
            logger.error(f"Error reading lock file {lock_file}: {e}")
    
    # Update status board
    board = _load_status_board()
    board["active_locks"] = [
        lock for lock in board["active_locks"]
        if not (lock["file_path"] == file_path and lock["agent_id"] == agent_id)
    ]
    if file_path in board["agent_assignments"]:
        if board["agent_assignments"][file_path] == agent_id:
            del board["agent_assignments"][file_path]
    _save_status_board(board)
    
    return removed


def check_conflicts(file_paths: List[str], agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Check for conflicts with other agents working on the same files.
    
    Args:
        file_paths: List of file paths to check
        agent_id: Current agent ID (to exclude from conflict check)
    
    Returns:
        List of conflicts found (empty if no conflicts)
    """
    if agent_id is None:
        agent_id = _get_agent_id()
    
    conflicts = []
    board = _load_status_board()
    
    # Normalize file paths
    normalized_paths = [str(Path(p).as_posix()) for p in file_paths]
    
    # Check active locks
    for lock in board["active_locks"]:
        if lock["agent_id"] == agent_id:
            continue
        
        lock_path = lock["file_path"]
        
        # Check if any of our files match locked files
        if lock_path in normalized_paths:
            # Check if lock is stale
            lock_timestamp = lock.get("timestamp", 0)
            if _is_lock_stale(lock_timestamp):
                logger.warning(f"Stale lock detected for {lock_path}, ignoring")
                continue
            
            conflicts.append({
                "file_path": lock_path,
                "locked_by": lock["agent_id"],
                "lock_timestamp": lock.get("timestamp"),
                "status": lock.get("status", "unknown")
            })
    
    return conflicts


def update_status_board(agent_id: Optional[str] = None, status: str = "in_progress", 
                       files: Optional[List[str]] = None) -> None:
    """
    Update the status board with current agent status.
    
    Args:
        agent_id: Agent identifier
        status: Current status
        files: List of files being worked on
    """
    if agent_id is None:
        agent_id = _get_agent_id()
    
    board = _load_status_board()
    
    if files:
        for file_path in files:
            file_path = str(Path(file_path).as_posix())
            # Update lock status
            for lock in board["active_locks"]:
                if lock["file_path"] == file_path and lock["agent_id"] == agent_id:
                    lock["status"] = status
                    lock["last_update"] = time.time()
    
    _save_status_board(board)


def send_message(target_agent_id: str, message: str, agent_id: Optional[str] = None) -> bool:
    """
    Send a message to another agent.
    
    Args:
        target_agent_id: ID of agent to message
        message: Message content
        agent_id: Sender agent ID
    
    Returns:
        True if message sent successfully
    """
    if agent_id is None:
        agent_id = _get_agent_id()
    
    try:
        message_file = MESSAGES_DIR / f"{target_agent_id}_{int(time.time())}.msg"
        message_data = {
            "from": agent_id,
            "to": target_agent_id,
            "message": message,
            "timestamp": time.time()
        }
        
        with open(message_file, 'w') as f:
            json.dump(message_data, f, indent=2)
        
        # Update status board
        board = _load_status_board()
        board["messages"].append({
            "from": agent_id,
            "to": target_agent_id,
            "timestamp": message_data["timestamp"]
        })
        _save_status_board(board)
        
        logger.info(f"Message sent from {agent_id} to {target_agent_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False


def read_messages(agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Read messages for the current agent.
    
    Args:
        agent_id: Agent identifier
    
    Returns:
        List of messages
    """
    if agent_id is None:
        agent_id = _get_agent_id()
    
    messages = []
    
    try:
        for message_file in MESSAGES_DIR.glob(f"{agent_id}_*.msg"):
            try:
                with open(message_file, 'r') as f:
                    message_data = json.load(f)
                    messages.append(message_data)
            except Exception as e:
                logger.error(f"Error reading message file {message_file}: {e}")
    except Exception as e:
        logger.error(f"Error reading messages: {e}")
    
    # Sort by timestamp
    messages.sort(key=lambda x: x.get("timestamp", 0))
    
    return messages


def cleanup_stale_locks() -> int:
    """
    Clean up stale locks (older than timeout).
    
    Returns:
        Number of locks cleaned up
    """
    cleaned = 0
    board = _load_status_board()
    
    current_time = time.time()
    active_locks = []
    
    for lock in board["active_locks"]:
        lock_timestamp = lock.get("timestamp", 0)
        if _is_lock_stale(lock_timestamp):
            # Remove lock file
            lock_file = LOCKS_DIR / lock.get("lock_file", "")
            if lock_file.exists():
                try:
                    lock_file.unlink()
                    cleaned += 1
                except Exception as e:
                    logger.error(f"Error removing stale lock file {lock_file}: {e}")
        else:
            active_locks.append(lock)
    
    board["active_locks"] = active_locks
    _save_status_board(board)
    
    if cleaned > 0:
        logger.info(f"Cleaned up {cleaned} stale locks")
    
    return cleaned

