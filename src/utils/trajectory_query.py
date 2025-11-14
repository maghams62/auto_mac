"""
Query utilities for trajectory logs.

Provides functions to query and analyze trajectory logs.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class TrajectoryQuery:
    """Query interface for trajectory logs."""
    
    def __init__(self, base_dir: str = "data/trajectories"):
        """
        Initialize trajectory query.
        
        Args:
            base_dir: Base directory for trajectory logs
        """
        self.base_dir = Path(base_dir)
        self.index_file = self.base_dir / "index.json"
    
    def _load_index(self) -> Dict[str, Any]:
        """Load index file."""
        if not self.index_file.exists():
            return {"trajectories": []}
        try:
            with open(self.index_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[TRAJECTORY QUERY] Failed to load index: {e}")
            return {"trajectories": []}
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions with trajectory logs."""
        index = self._load_index()
        return index.get("trajectories", [])
    
    def query_by_session(
        self,
        session_id: str,
        decision_type: Optional[str] = None,
        phase: Optional[str] = None,
        component: Optional[str] = None,
        success: Optional[bool] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Query trajectories by session ID.
        
        Args:
            session_id: Session ID to query
            decision_type: Filter by decision type (optional)
            phase: Filter by phase (optional)
            component: Filter by component (optional)
            success: Filter by success status (optional)
            start_time: Filter by start time (optional)
            end_time: Filter by end time (optional)
            
        Returns:
            List of trajectory entries matching criteria
        """
        # Find trajectory files for this session
        index = self._load_index()
        session_files = [
            entry for entry in index.get("trajectories", [])
            if entry.get("session_id") == session_id
        ]
        
        if not session_files:
            return []
        
        results = []
        for entry in session_files:
            file_path = self.base_dir / entry["filename"]
            if not file_path.exists():
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        trajectory = json.loads(line)
                        
                        # Apply filters
                        if decision_type and trajectory.get("decision_type") != decision_type:
                            continue
                        if phase and trajectory.get("phase") != phase:
                            continue
                        if component and trajectory.get("component") != component:
                            continue
                        if success is not None and trajectory.get("success") != success:
                            continue
                        
                        # Time filter
                        if start_time or end_time:
                            traj_time = datetime.fromisoformat(
                                trajectory["timestamp"].replace("Z", "+00:00")
                            )
                            if start_time and traj_time < start_time:
                                continue
                            if end_time and traj_time > end_time:
                                continue
                        
                        results.append(trajectory)
            except Exception as e:
                logger.warning(f"[TRAJECTORY QUERY] Failed to read {file_path}: {e}")
        
        return results
    
    def query_by_decision_type(
        self,
        decision_type: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Query trajectories by decision type.
        
        Args:
            decision_type: Decision type to query
            start_time: Filter by start time (optional)
            end_time: Filter by end time (optional)
            
        Returns:
            List of trajectory entries matching criteria
        """
        index = self._load_index()
        results = []
        
        for entry in index.get("trajectories", []):
            file_path = self.base_dir / entry["filename"]
            if not file_path.exists():
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        trajectory = json.loads(line)
                        
                        if trajectory.get("decision_type") != decision_type:
                            continue
                        
                        # Time filter
                        if start_time or end_time:
                            traj_time = datetime.fromisoformat(
                                trajectory["timestamp"].replace("Z", "+00:00")
                            )
                            if start_time and traj_time < start_time:
                                continue
                            if end_time and traj_time > end_time:
                                continue
                        
                        results.append(trajectory)
            except Exception as e:
                logger.warning(f"[TRAJECTORY QUERY] Failed to read {file_path}: {e}")
        
        return results
    
    def query_by_model(
        self,
        model_used: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Query trajectories by model used.
        
        Args:
            model_used: Model name to query
            start_time: Filter by start time (optional)
            end_time: Filter by end time (optional)
            
        Returns:
            List of trajectory entries matching criteria
        """
        index = self._load_index()
        results = []
        
        for entry in index.get("trajectories", []):
            file_path = self.base_dir / entry["filename"]
            if not file_path.exists():
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        trajectory = json.loads(line)
                        
                        if trajectory.get("model_used") != model_used:
                            continue
                        
                        # Time filter
                        if start_time or end_time:
                            traj_time = datetime.fromisoformat(
                                trajectory["timestamp"].replace("Z", "+00:00")
                            )
                            if start_time and traj_time < start_time:
                                continue
                            if end_time and traj_time > end_time:
                                continue
                        
                        results.append(trajectory)
            except Exception as e:
                logger.warning(f"[TRAJECTORY QUERY] Failed to read {file_path}: {e}")
        
        return results
    
    def get_statistics(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about trajectories.
        
        Args:
            session_id: Optional session ID to filter by
            
        Returns:
            Statistics dictionary
        """
        if session_id:
            trajectories = self.query_by_session(session_id)
        else:
            # Load all trajectories
            index = self._load_index()
            trajectories = []
            for entry in index.get("trajectories", []):
                file_path = self.base_dir / entry["filename"]
                if not file_path.exists():
                    continue
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip():
                                trajectories.append(json.loads(line))
                except Exception as e:
                    logger.warning(f"[TRAJECTORY QUERY] Failed to read {file_path}: {e}")
        
        if not trajectories:
            return {
                "total": 0,
                "by_phase": {},
                "by_component": {},
                "by_decision_type": {},
                "by_model": {},
                "success_rate": 0.0,
                "avg_confidence": 0.0,
                "total_tokens": 0
            }
        
        # Calculate statistics
        total = len(trajectories)
        by_phase = {}
        by_component = {}
        by_decision_type = {}
        by_model = {}
        success_count = 0
        confidence_sum = 0.0
        confidence_count = 0
        total_tokens = 0
        
        for traj in trajectories:
            phase = traj.get("phase", "unknown")
            by_phase[phase] = by_phase.get(phase, 0) + 1
            
            component = traj.get("component", "unknown")
            by_component[component] = by_component.get(component, 0) + 1
            
            decision_type = traj.get("decision_type", "unknown")
            by_decision_type[decision_type] = by_decision_type.get(decision_type, 0) + 1
            
            model = traj.get("model_used", "unknown")
            by_model[model] = by_model.get(model, 0) + 1
            
            if traj.get("success", False):
                success_count += 1
            
            if "confidence" in traj:
                confidence_sum += traj["confidence"]
                confidence_count += 1
            
            if "tokens_used" in traj:
                tokens = traj["tokens_used"]
                if isinstance(tokens, dict):
                    total_tokens += tokens.get("total", 0)
        
        return {
            "total": total,
            "by_phase": by_phase,
            "by_component": by_component,
            "by_decision_type": by_decision_type,
            "by_model": by_model,
            "success_rate": success_count / total if total > 0 else 0.0,
            "avg_confidence": confidence_sum / confidence_count if confidence_count > 0 else 0.0,
            "total_tokens": total_tokens
        }


def query_trajectories(
    session_id: Optional[str] = None,
    decision_type: Optional[str] = None,
    model_used: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """
    Convenience function to query trajectories.
    
    Args:
        session_id: Session ID to query (optional)
        decision_type: Decision type to filter (optional)
        model_used: Model to filter (optional)
        start_time: Start time filter (optional)
        end_time: End time filter (optional)
        
    Returns:
        List of trajectory entries
    """
    query = TrajectoryQuery()
    
    if session_id:
        return query.query_by_session(
            session_id,
            decision_type=decision_type,
            start_time=start_time,
            end_time=end_time
        )
    elif decision_type:
        return query.query_by_decision_type(
            decision_type,
            start_time=start_time,
            end_time=end_time
        )
    elif model_used:
        return query.query_by_model(
            model_used,
            start_time=start_time,
            end_time=end_time
        )
    else:
        # Return all trajectories (limited)
        index = query._load_index()
        results = []
        for entry in index.get("trajectories", [])[:100]:  # Limit to 100 files
            file_path = query.base_dir / entry["filename"]
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip():
                                results.append(json.loads(line))
                except Exception:
                    pass
        return results

