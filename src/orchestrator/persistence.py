"""
State persistence and resumability utilities.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from .state import OrchestratorState

logger = logging.getLogger(__name__)


class StatePersistence:
    """
    Handles state persistence and recovery.
    """

    def __init__(self, storage_dir: str = "data/orchestrator_states"):
        """
        Initialize state persistence.

        Args:
            storage_dir: Directory to store state files
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, state: OrchestratorState, checkpoint_name: Optional[str] = None) -> str:
        """
        Save orchestrator state to disk.

        Args:
            state: Current orchestrator state
            checkpoint_name: Optional checkpoint name (default: auto-generated)

        Returns:
            Path to saved state file
        """
        try:
            # Generate filename
            if checkpoint_name:
                filename = f"{checkpoint_name}.json"
            else:
                run_id = state["metadata"]["run_id"]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{run_id}_{timestamp}.json"

            filepath = self.storage_dir / filename

            # Save state
            with open(filepath, 'w') as f:
                json.dump(state, f, indent=2, default=str)

            logger.info(f"State saved to {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            raise

    def load(self, filepath: str) -> OrchestratorState:
        """
        Load orchestrator state from disk.

        Args:
            filepath: Path to state file

        Returns:
            Loaded orchestrator state
        """
        try:
            with open(filepath, 'r') as f:
                state = json.load(f)

            logger.info(f"State loaded from {filepath}")
            return state

        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            raise

    def list_states(self, run_id: Optional[str] = None) -> list:
        """
        List all saved states.

        Args:
            run_id: Optional filter by run ID

        Returns:
            List of state file paths
        """
        try:
            if run_id:
                pattern = f"{run_id}_*.json"
            else:
                pattern = "*.json"

            states = sorted(self.storage_dir.glob(pattern))
            return [str(s) for s in states]

        except Exception as e:
            logger.error(f"Failed to list states: {e}")
            return []

    def get_latest_state(self, run_id: Optional[str] = None) -> Optional[str]:
        """
        Get the most recent state file.

        Args:
            run_id: Optional filter by run ID

        Returns:
            Path to latest state file or None
        """
        states = self.list_states(run_id)
        return states[-1] if states else None

    def cleanup_old_states(self, keep_last_n: int = 10):
        """
        Remove old state files, keeping only the most recent N.

        Args:
            keep_last_n: Number of recent states to keep
        """
        try:
            states = sorted(self.storage_dir.glob("*.json"))

            if len(states) > keep_last_n:
                to_remove = states[:-keep_last_n]
                for state_file in to_remove:
                    state_file.unlink()
                    logger.debug(f"Removed old state: {state_file}")

                logger.info(f"Cleaned up {len(to_remove)} old state files")

        except Exception as e:
            logger.error(f"Failed to cleanup states: {e}")


class CheckpointManager:
    """
    Manages checkpoints during workflow execution.
    """

    def __init__(self, persistence: StatePersistence):
        """
        Initialize checkpoint manager.

        Args:
            persistence: State persistence instance
        """
        self.persistence = persistence
        self.checkpoints = {}

    def create_checkpoint(
        self,
        state: OrchestratorState,
        name: str,
        description: str = ""
    ) -> str:
        """
        Create a named checkpoint.

        Args:
            state: Current state
            name: Checkpoint name
            description: Optional description

        Returns:
            Path to checkpoint file
        """
        # Add checkpoint metadata
        checkpoint_state = state.copy()
        checkpoint_state["metadata"]["checkpoint"] = {
            "name": name,
            "description": description,
            "created_at": datetime.now().isoformat()
        }

        # Save checkpoint
        filepath = self.persistence.save(checkpoint_state, checkpoint_name=f"checkpoint_{name}")

        # Track checkpoint
        self.checkpoints[name] = filepath

        logger.info(f"Checkpoint '{name}' created: {filepath}")
        return filepath

    def restore_checkpoint(self, name: str) -> OrchestratorState:
        """
        Restore from a named checkpoint.

        Args:
            name: Checkpoint name

        Returns:
            Restored state
        """
        if name not in self.checkpoints:
            raise ValueError(f"Checkpoint '{name}' not found")

        filepath = self.checkpoints[name]
        state = self.persistence.load(filepath)

        logger.info(f"Restored from checkpoint '{name}'")
        return state

    def list_checkpoints(self) -> Dict[str, str]:
        """
        List all checkpoints.

        Returns:
            Dictionary mapping checkpoint names to file paths
        """
        return self.checkpoints.copy()


def create_persistence(config: Dict[str, Any]) -> StatePersistence:
    """
    Factory function to create state persistence.

    Args:
        config: Configuration dictionary

    Returns:
        StatePersistence instance
    """
    storage_dir = config.get("orchestrator", {}).get("state_storage_dir", "data/orchestrator_states")
    return StatePersistence(storage_dir)
