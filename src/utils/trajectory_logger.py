"""
Trajectory logging for LLM orchestration decisions.

Logs all LLM orchestration trajectories in JSONL format for revisitable decision tracking.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from threading import Lock
import uuid

logger = logging.getLogger(__name__)


class TrajectoryLogger:
    """
    Logs LLM orchestration trajectories in JSONL format.
    
    Each trajectory entry captures a decision point in the orchestration:
    - Planning decisions (model selection, tool selection, plan creation)
    - Execution decisions (step execution, parameter resolution)
    - Routing decisions (strategy selection, route selection)
    - Error and retry decisions
    """
    
    def __init__(self, base_dir: str = "data/trajectories", config: Optional[Dict[str, Any]] = None):
        """
        Initialize trajectory logger.
        
        Args:
            base_dir: Base directory for trajectory logs
            config: Optional configuration dict
        """
        self.base_dir = Path(base_dir)
        self.config = config or {}
        self._lock = Lock()
        self._current_file: Optional[Path] = None
        self._current_session_id: Optional[str] = None
        self._file_handle = None
        
        # Create directories
        self.base_dir.mkdir(parents=True, exist_ok=True)
        (self.base_dir / "aggregated").mkdir(parents=True, exist_ok=True)
        
        # Index file for metadata
        self.index_file = self.base_dir / "index.json"
        self._load_index()
    
    def _load_index(self):
        """Load or create index file."""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    self._index = json.load(f)
            except Exception as e:
                logger.warning(f"[TRAJECTORY] Failed to load index: {e}")
                self._index = {"trajectories": []}
        else:
            self._index = {"trajectories": []}
    
    def _save_index(self):
        """Save index file."""
        try:
            with open(self.index_file, 'w') as f:
                json.dump(self._index, f, indent=2)
        except Exception as e:
            logger.warning(f"[TRAJECTORY] Failed to save index: {e}")
    
    def _get_trajectory_file(self, session_id: str) -> Path:
        """Get or create trajectory file for session."""
        if self._current_session_id != session_id or self._current_file is None:
            # Close previous file if different session
            if self._file_handle:
                self._file_handle.close()
                self._file_handle = None
            
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{session_id}_{timestamp}.jsonl"
            self._current_file = self.base_dir / filename
            self._current_session_id = session_id
            
            # Add to index
            entry = {
                "session_id": session_id,
                "filename": filename,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "path": str(self._current_file.relative_to(self.base_dir.parent))
            }
            self._index["trajectories"].append(entry)
            self._save_index()
        
        return self._current_file
    
    def _get_file_handle(self, session_id: str):
        """Get file handle for writing (creates if needed)."""
        if self._file_handle is None or self._current_session_id != session_id:
            file_path = self._get_trajectory_file(session_id)
            self._file_handle = open(file_path, 'a', encoding='utf-8')
        return self._file_handle
    
    def log_trajectory(
        self,
        session_id: str,
        interaction_id: Optional[str],
        phase: str,
        component: str,
        decision_type: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        reasoning: Optional[str] = None,
        confidence: Optional[float] = None,
        model_used: Optional[str] = None,
        tokens_used: Optional[Dict[str, int]] = None,
        latency_ms: Optional[float] = None,
        success: bool = True,
        error: Optional[Dict[str, Any]] = None,
        **extra_fields
    ):
        """
        Log a trajectory entry.
        
        Args:
            session_id: Session identifier
            interaction_id: Interaction identifier (optional)
            phase: Phase of orchestration (planning|execution|synthesis|error)
            component: Component making decision (planner|executor|agent|tool)
            decision_type: Type of decision (model_selection|tool_selection|route_selection|parameter_resolution)
            input_data: Input data for the decision
            output_data: Output data from the decision
            reasoning: Reasoning for the decision (optional)
            confidence: Confidence score 0.0-1.0 (optional)
            model_used: Model used (optional)
            tokens_used: Token usage dict with prompt/completion/total (optional)
            latency_ms: Latency in milliseconds (optional)
            success: Whether decision was successful
            error: Error details if failed (optional)
            **extra_fields: Additional fields to include
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": session_id,
            "interaction_id": interaction_id or str(uuid.uuid4()),
            "phase": phase,
            "component": component,
            "decision_type": decision_type,
            "input": self._sanitize_data(input_data),
            "output": self._sanitize_data(output_data),
            "success": success,
        }
        
        if reasoning:
            entry["reasoning"] = reasoning
        if confidence is not None:
            entry["confidence"] = confidence
        if model_used:
            entry["model_used"] = model_used
        if tokens_used:
            entry["tokens_used"] = tokens_used
        if latency_ms is not None:
            entry["latency_ms"] = latency_ms
        if error:
            entry["error"] = error
        
        # Add extra fields
        entry.update(extra_fields)
        
        # Write to file
        with self._lock:
            try:
                f = self._get_file_handle(session_id)
                f.write(json.dumps(entry, default=str) + "\n")
                f.flush()  # Ensure immediate write
            except Exception as e:
                logger.error(f"[TRAJECTORY] Failed to write trajectory entry: {e}", exc_info=True)
    
    def _sanitize_data(self, data: Any) -> Any:
        """Sanitize data for logging (remove sensitive info, truncate large values)."""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                # Redact sensitive fields
                if any(sensitive in key.lower() for sensitive in ["password", "token", "key", "secret", "api_key"]):
                    sanitized[key] = "[REDACTED]"
                else:
                    sanitized[key] = self._sanitize_data(value)
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_data(item) for item in data[:100]]  # Limit list size
        elif isinstance(data, str):
            # Truncate very long strings
            if len(data) > 10000:
                return data[:10000] + "... [TRUNCATED]"
            return data
        else:
            return data
    
    def close(self):
        """Close file handles."""
        with self._lock:
            if self._file_handle:
                self._file_handle.close()
                self._file_handle = None
            self._current_file = None
            self._current_session_id = None


# Global trajectory logger instance
_trajectory_logger: Optional[TrajectoryLogger] = None


def get_trajectory_logger(config: Optional[Dict[str, Any]] = None) -> TrajectoryLogger:
    """Get or create global trajectory logger instance."""
    global _trajectory_logger
    if _trajectory_logger is None:
        base_dir = "data/trajectories"
        if config and "trajectories" in config:
            base_dir = config["trajectories"].get("base_dir", base_dir)
        _trajectory_logger = TrajectoryLogger(base_dir=base_dir, config=config)
    return _trajectory_logger


def log_trajectory(*args, **kwargs):
    """Convenience function to log trajectory."""
    logger = get_trajectory_logger()
    logger.log_trajectory(*args, **kwargs)

