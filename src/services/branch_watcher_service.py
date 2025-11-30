"""
Branch Watcher Service - Background monitoring for GitHub branch changes.

Implements the Oqoqo pattern for self-evolving API documentation:
- Polls GitHub API for branch updates
- Detects when monitored files (api_server.py) change
- Sends WebSocket notifications to connected clients
- Tracks pending drift reports for user approval
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field

from .github_pr_service import GitHubPRService, GitHubAPIError, get_github_pr_service

logger = logging.getLogger(__name__)


@dataclass
class PendingDriftReport:
    """A drift report waiting for user approval."""
    branch: str
    has_drift: bool
    change_count: int
    breaking_changes: int
    summary: str
    proposed_spec: Optional[str]
    detected_at: str
    session_id: Optional[str] = None  # Track which session received the notification


@dataclass 
class BranchState:
    """Tracks the state of a branch for change detection."""
    branch_name: str
    last_commit_sha: Optional[str] = None
    last_checked: Optional[str] = None
    has_monitored_file_changes: bool = False
    notified: bool = False


class BranchWatcherService:
    """
    Background service that polls GitHub for branch changes and notifies
    connected WebSocket clients when API documentation drift is detected.
    """

    def __init__(self, connection_manager, config: Dict[str, Any]):
        self.connection_manager = connection_manager
        self.config = config
        self.github_config = config.get("github", {})
        
        # Service state
        self.running = False
        self.poll_interval = self.github_config.get("poll_interval_seconds", 60)
        self.max_retries = 3
        self.backoff_factor = 2.0
        
        # Branch tracking
        self.watched_branches: Dict[str, BranchState] = {}
        self.pending_drift_reports: Dict[str, PendingDriftReport] = {}  # branch -> report
        
        # Branches to exclude from watching
        self.excluded_branches = {"main", "master", "develop", "HEAD"}
        
        # Persistence file for state recovery
        self.state_file = os.path.join("data", "branch_watcher_state.json")
        
        # GitHub service (created lazily)
        self._github_service: Optional[GitHubPRService] = None
        
        # Background task
        self.poll_task: Optional[asyncio.Task] = None

        # Telemetry for health/debug
        self.last_poll_started_at: Optional[str] = None
        self.last_poll_completed_at: Optional[str] = None
        self.last_poll_error: Optional[str] = None
        
        logger.info(f"[BRANCH WATCHER] Initialized with {self.poll_interval}s poll interval")
    
    @property
    def github_service(self) -> GitHubPRService:
        """Lazy-load GitHub service."""
        if self._github_service is None:
            self._github_service = get_github_pr_service()
        return self._github_service
    
    def _load_persistent_state(self) -> None:
        """Load watcher state from persistent storage."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                
                # Load watched branches
                for branch_data in state.get("watched_branches", []):
                    branch = BranchState(**branch_data)
                    self.watched_branches[branch.branch_name] = branch
                
                # Load pending drift reports
                for report_data in state.get("pending_drift_reports", []):
                    report = PendingDriftReport(**report_data)
                    self.pending_drift_reports[report.branch] = report
                
                logger.info(f"[BRANCH WATCHER] Loaded state: {len(self.watched_branches)} branches, "
                           f"{len(self.pending_drift_reports)} pending reports")
        except Exception as e:
            logger.warning(f"[BRANCH WATCHER] Failed to load persistent state: {e}")
    
    def _save_persistent_state(self) -> None:
        """Save watcher state to persistent storage."""
        try:
            state = {
                "watched_branches": [
                    {
                        "branch_name": b.branch_name,
                        "last_commit_sha": b.last_commit_sha,
                        "last_checked": b.last_checked,
                        "has_monitored_file_changes": b.has_monitored_file_changes,
                        "notified": b.notified,
                    }
                    for b in self.watched_branches.values()
                ],
                "pending_drift_reports": [
                    {
                        "branch": r.branch,
                        "has_drift": r.has_drift,
                        "change_count": r.change_count,
                        "breaking_changes": r.breaking_changes,
                        "summary": r.summary,
                        "proposed_spec": r.proposed_spec,
                        "detected_at": r.detected_at,
                        "session_id": r.session_id,
                    }
                    for r in self.pending_drift_reports.values()
                ],
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.warning(f"[BRANCH WATCHER] Failed to save persistent state: {e}")
    
    async def _fetch_branches(self) -> List[str]:
        """Fetch list of branches from GitHub."""
        try:
            branches = await asyncio.to_thread(self.github_service.list_branches)
            # Filter out excluded branches
            return [b for b in branches if b not in self.excluded_branches]
        except GitHubAPIError as e:
            logger.error(f"[BRANCH WATCHER] Failed to fetch branches: {e}")
            return []
    
    async def _check_branch_for_changes(self, branch_name: str) -> Optional[Dict[str, Any]]:
        """Check if a branch has changes to the monitored file."""
        try:
            result = await asyncio.to_thread(self.github_service.check_branch_for_api_changes, branch_name)
            return result
        except GitHubAPIError as e:
            logger.error(f"[BRANCH WATCHER] Failed to check branch {branch_name}: {e}")
            return None
    
    async def _run_drift_check(self, branch_name: str, branch_code: str) -> Optional[Dict[str, Any]]:
        """Run semantic diff to detect API drift."""
        try:
            # Import here to avoid circular imports
            from src.agent.apidocs_agent import read_api_spec
            from src.services.api_diff_service import get_api_diff_service
            from src.utils import load_config
            
            # Get current spec
            spec_result = read_api_spec.invoke({})
            if not spec_result.get("exists"):
                logger.warning("[BRANCH WATCHER] API spec not found, skipping drift check")
                return None
            
            # Run semantic diff
            config = load_config()
            diff_service = get_api_diff_service(config)
            drift_report = diff_service.check_drift(
                code_content=branch_code,
                spec_content=spec_result["content"]
            )
            
            return {
                "has_drift": drift_report.has_drift,
                "changes": drift_report.changes,
                "summary": drift_report.summary,
                "proposed_spec": drift_report.proposed_spec,
                "change_count": len(drift_report.changes),
                "breaking_changes": sum(1 for c in drift_report.changes 
                                       if hasattr(c, 'severity') and c.severity.value == "breaking"),
            }
            
        except Exception as e:
            logger.error(f"[BRANCH WATCHER] Failed to run drift check for {branch_name}: {e}")
            return None
    
    async def _broadcast_drift_notification(self, branch: str, drift_result: Dict[str, Any]) -> None:
        """Send drift notification to all connected WebSocket clients."""
        try:
            message = {
                "type": "apidocs_drift",
                "message": f"🔔 Branch `{branch}` has API changes that need documentation updates.\n\n"
                          f"{drift_result.get('summary', '')}\n\n"
                          f"Would you like to sync the API docs? Reply 'yes' or '/apidocs sync' to update.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "apidocs_drift": {
                    "has_drift": drift_result.get("has_drift", True),
                    "branch": branch,
                    "changes": [c.to_dict() if hasattr(c, 'to_dict') else c 
                               for c in drift_result.get("changes", [])],
                    "summary": drift_result.get("summary", ""),
                    "proposed_spec": drift_result.get("proposed_spec"),
                    "change_count": drift_result.get("change_count", 0),
                    "breaking_changes": drift_result.get("breaking_changes", 0),
                    "awaiting_approval": True,
                }
            }
            
            # Broadcast to all connected clients
            await self.connection_manager.broadcast(message)
            logger.info(f"[BRANCH WATCHER] Broadcasted drift notification for branch {branch}")
            
        except Exception as e:
            logger.error(f"[BRANCH WATCHER] Failed to broadcast notification: {e}")
    
    async def _poll_branches(self) -> None:
        """Poll GitHub for branch changes and check for drift."""
        logger.debug("[BRANCH WATCHER] Starting poll cycle...")
        
        # Fetch current branches
        branches = await self._fetch_branches()
        if not branches:
            logger.debug("[BRANCH WATCHER] No branches to check")
            return
        
        logger.debug(f"[BRANCH WATCHER] Checking {len(branches)} branches")
        
        for branch_name in branches:
            # Skip if already notified and pending approval
            if branch_name in self.pending_drift_reports:
                logger.debug(f"[BRANCH WATCHER] Skipping {branch_name} - pending approval")
                continue
            
            # Check for changes to monitored file
            result = await self._check_branch_for_changes(branch_name)
            if not result:
                continue
            
            if not result.get("has_changes"):
                # No changes to monitored file
                if branch_name in self.watched_branches:
                    self.watched_branches[branch_name].has_monitored_file_changes = False
                continue
            
            # Branch has changes to monitored file
            logger.info(f"[BRANCH WATCHER] Detected changes in branch {branch_name}")
            
            # Update branch state
            branch_state = self.watched_branches.get(branch_name, BranchState(branch_name=branch_name))
            branch_state.has_monitored_file_changes = True
            branch_state.last_checked = datetime.now(timezone.utc).isoformat()
            self.watched_branches[branch_name] = branch_state
            
            # Skip if already notified for this branch
            if branch_state.notified:
                logger.debug(f"[BRANCH WATCHER] Already notified for {branch_name}")
                continue
            
            # Run drift check
            branch_code = result.get("branch_file_content")
            if not branch_code:
                logger.warning(f"[BRANCH WATCHER] No file content for {branch_name}")
                continue
            
            drift_result = await self._run_drift_check(branch_name, branch_code)
            if not drift_result:
                continue
            
            if drift_result.get("has_drift"):
                # Store pending report
                pending_report = PendingDriftReport(
                    branch=branch_name,
                    has_drift=True,
                    change_count=drift_result.get("change_count", 0),
                    breaking_changes=drift_result.get("breaking_changes", 0),
                    summary=drift_result.get("summary", ""),
                    proposed_spec=drift_result.get("proposed_spec"),
                    detected_at=datetime.now(timezone.utc).isoformat(),
                )
                self.pending_drift_reports[branch_name] = pending_report
                
                # Mark as notified
                branch_state.notified = True
                
                # Broadcast notification
                await self._broadcast_drift_notification(branch_name, drift_result)
                
                # Save state
                self._save_persistent_state()
            else:
                logger.info(f"[BRANCH WATCHER] No drift detected for {branch_name}")
    
    async def _poll_loop(self) -> None:
        """Main polling loop."""
        retry_count = 0
        
        while self.running:
            try:
                self.last_poll_started_at = datetime.now(timezone.utc).isoformat()
                await self._poll_branches()
                self.last_poll_completed_at = datetime.now(timezone.utc).isoformat()
                self.last_poll_error = None
                retry_count = 0  # Reset on success
                
            except Exception as e:
                retry_count += 1
                self.last_poll_error = str(e)
                logger.error(f"[BRANCH WATCHER] Poll error (attempt {retry_count}): {e}")
                
                if retry_count >= self.max_retries:
                    logger.error("[BRANCH WATCHER] Max retries exceeded, backing off")
                    await asyncio.sleep(self.poll_interval * self.backoff_factor)
                    retry_count = 0
            
            # Wait for next poll
            await asyncio.sleep(self.poll_interval)
    
    async def start(self) -> None:
        """Start the background polling service."""
        if self.running:
            logger.warning("[BRANCH WATCHER] Already running")
            return
        
        logger.info("[BRANCH WATCHER] Starting background service...")
        self.running = True
        self.last_poll_started_at = None
        self.last_poll_completed_at = None
        self.last_poll_error = None
        
        # Load persistent state
        self._load_persistent_state()
        
        # Start polling task
        self.poll_task = asyncio.create_task(self._poll_loop())
        logger.info("[BRANCH WATCHER] Background service started")
    
    async def stop(self) -> None:
        """Stop the background polling service."""
        if not self.running:
            return
        
        logger.info("[BRANCH WATCHER] Stopping background service...")
        self.running = False
        
        if self.poll_task:
            self.poll_task.cancel()
            try:
                await self.poll_task
            except asyncio.CancelledError:
                pass
        
        # Save state before stopping
        self._save_persistent_state()
        logger.info("[BRANCH WATCHER] Background service stopped")
    
    def get_pending_report(self, branch: Optional[str] = None) -> Optional[PendingDriftReport]:
        """Get a pending drift report, optionally for a specific branch."""
        if branch:
            return self.pending_drift_reports.get(branch)
        
        # Return the most recent pending report
        if self.pending_drift_reports:
            return list(self.pending_drift_reports.values())[-1]
        return None
    
    def clear_pending_report(self, branch: str) -> bool:
        """Clear a pending drift report after approval/rejection."""
        if branch in self.pending_drift_reports:
            del self.pending_drift_reports[branch]
            
            # Reset notified flag so we can detect future changes
            if branch in self.watched_branches:
                self.watched_branches[branch].notified = False
            
            self._save_persistent_state()
            return True
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current service status."""
        return {
            "running": self.running,
            "poll_interval": self.poll_interval,
            "watched_branches": len(self.watched_branches),
            "pending_reports": len(self.pending_drift_reports),
            "pending_branches": list(self.pending_drift_reports.keys()),
            "last_poll_started_at": self.last_poll_started_at,
            "last_poll_completed_at": self.last_poll_completed_at,
            "last_poll_error": self.last_poll_error,
        }


# Singleton instance
_branch_watcher_instance: Optional[BranchWatcherService] = None


def get_branch_watcher_service(connection_manager=None, config: Dict[str, Any] = None) -> Optional[BranchWatcherService]:
    """Get or create the singleton BranchWatcherService instance."""
    global _branch_watcher_instance
    
    if _branch_watcher_instance is None:
        if connection_manager is None or config is None:
            return None
        _branch_watcher_instance = BranchWatcherService(connection_manager, config)
    
    return _branch_watcher_instance

