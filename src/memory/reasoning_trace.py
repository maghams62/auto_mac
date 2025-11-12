"""
ReasoningTrace - Persistent reasoning memory for multi-step execution.

This module implements a reasoning ledger that tracks decisions, evidence,
commitments, and corrections across agent executions. It enables:

1. Context-aware planning (use actual history vs. hypothetical examples)
2. Self-correction through Critic feedback loops
3. Delivery validation (track commitments like attachments, sends)
4. Reduced prompt engineering (trace replaces scenario-specific examples)

Design Philosophy:
- HYBRID: Complements existing prompts, doesn't replace them
- ADDITIVE: Extends SessionMemory without breaking existing code
- OPT-IN: Feature flag controlled, disabled by default
- LIGHTWEIGHT: Minimal overhead, simple data structures
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum


logger = logging.getLogger(__name__)


class ReasoningStage(Enum):
    """Execution stage for reasoning entry."""
    PLANNING = "planning"           # Planner creating plan
    EXECUTION = "execution"         # Executor running tool
    VERIFICATION = "verification"   # Verifier checking output
    CORRECTION = "correction"       # Critic analyzing failure
    FINALIZATION = "finalization"   # Final delivery checks


class OutcomeStatus(Enum):
    """Outcome of a reasoning step."""
    PENDING = "pending"           # Not yet completed
    SUCCESS = "success"           # Completed successfully
    PARTIAL = "partial"           # Partially successful
    FAILED = "failed"             # Failed with error
    SKIPPED = "skipped"           # Skipped due to dependencies


@dataclass
class ReasoningEntry:
    """
    Single entry in the reasoning trace.

    Captures what we decided, why we decided it, what happened,
    and what we learned from the outcome.
    """
    # Identity
    entry_id: str
    interaction_id: str  # Links to parent Interaction
    timestamp: str
    stage: str  # ReasoningStage value

    # Decision & Intent
    thought: str  # High-level reasoning (e.g., "Need to search for Tesla docs")
    action: Optional[str] = None  # Tool/agent invoked (e.g., "search_documents")
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Evidence & Observations
    evidence: List[str] = field(default_factory=list)
    # Example: ["Found 3 PDFs in /path/docs", "Email compose succeeded"]

    outcome: str = "pending"  # OutcomeStatus value
    error: Optional[str] = None

    # Commitments & Artifacts
    # Tracks what we promised to do (send email, attach file, etc.)
    commitments: List[str] = field(default_factory=list)
    # Example: ["send_email", "attach_document:tesla.pdf"]

    # Artifacts discovered/created during this step
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    # Example: [{"type": "file", "path": "/path/tesla.pdf", "status": "found"}]

    # Corrective Guidance (from Critic)
    corrections: List[str] = field(default_factory=list)
    # Example: ["Retry with broader search query", "Skip step 3"]

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReasoningEntry':
        """Deserialize from dictionary."""
        return cls(**data)

    def is_complete(self) -> bool:
        """Check if this entry represents a completed action."""
        return self.outcome in [
            OutcomeStatus.SUCCESS.value,
            OutcomeStatus.PARTIAL.value,
            OutcomeStatus.FAILED.value,
            OutcomeStatus.SKIPPED.value
        ]

    def has_pending_commitments(self) -> bool:
        """Check if this entry has unfulfilled commitments."""
        return bool(self.commitments) and not self.is_complete()


class ReasoningTrace:
    """
    Reasoning trace manager for a single interaction.

    Collects reasoning entries during planning → execution → verification.
    Provides summaries for LLM context and validation checks.
    """

    def __init__(self, interaction_id: str):
        """
        Initialize reasoning trace for an interaction.

        Args:
            interaction_id: Parent interaction ID from SessionMemory
        """
        self.interaction_id = interaction_id
        self.entries: List[ReasoningEntry] = []
        self._entry_index: Dict[str, ReasoningEntry] = {}  # Fast lookup

        logger.debug(f"[REASONING TRACE] Initialized for interaction {interaction_id}")

    def add_entry(
        self,
        stage: ReasoningStage,
        thought: str,
        action: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        evidence: Optional[List[str]] = None,
        outcome: OutcomeStatus = OutcomeStatus.PENDING,
        error: Optional[str] = None,
        commitments: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        corrections: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a reasoning entry to the trace.

        Args:
            stage: Execution stage (planning/execution/etc.)
            thought: High-level reasoning for this step
            action: Tool/agent being invoked (optional)
            parameters: Tool parameters (optional)
            evidence: Observations and facts (optional)
            outcome: Result status (default: PENDING)
            error: Error message if failed (optional)
            commitments: Promises to fulfill (optional)
            attachments: Files/artifacts found/created (optional)
            corrections: Corrective guidance from Critic (optional)
            metadata: Additional context (optional)

        Returns:
            Entry ID for later updates
        """
        entry_id = f"trace_{len(self.entries) + 1}_{uuid.uuid4().hex[:8]}"

        entry = ReasoningEntry(
            entry_id=entry_id,
            interaction_id=self.interaction_id,
            timestamp=datetime.now().isoformat(),
            stage=stage.value,
            thought=thought,
            action=action,
            parameters=parameters or {},
            evidence=evidence or [],
            outcome=outcome.value,
            error=error,
            commitments=commitments or [],
            attachments=attachments or [],
            corrections=corrections or [],
            metadata=metadata or {}
        )

        self.entries.append(entry)
        self._entry_index[entry_id] = entry

        logger.debug(
            f"[REASONING TRACE] Added {stage.value} entry: {thought[:50]}... "
            f"(outcome={outcome.value})"
        )

        return entry_id

    def update_entry(
        self,
        entry_id: str,
        outcome: Optional[OutcomeStatus] = None,
        evidence: Optional[List[str]] = None,
        error: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        corrections: Optional[List[str]] = None,
        **kwargs
    ) -> bool:
        """
        Update an existing reasoning entry.

        Typically called after a step completes to record the outcome.

        Args:
            entry_id: ID of entry to update
            outcome: New outcome status (optional)
            evidence: Additional observations (appends) (optional)
            error: Error message (optional)
            attachments: Artifacts discovered (appends) (optional)
            corrections: Corrective guidance (appends) (optional)
            **kwargs: Additional fields to update

        Returns:
            True if entry was found and updated, False otherwise
        """
        entry = self._entry_index.get(entry_id)
        if not entry:
            logger.warning(f"[REASONING TRACE] Entry {entry_id} not found for update")
            return False

        if outcome is not None:
            entry.outcome = outcome.value

        if evidence:
            entry.evidence.extend(evidence)

        if error is not None:
            entry.error = error

        if attachments:
            entry.attachments.extend(attachments)

        if corrections:
            entry.corrections.extend(corrections)

        # Update any additional fields
        for key, value in kwargs.items():
            if hasattr(entry, key):
                setattr(entry, key, value)

        logger.debug(f"[REASONING TRACE] Updated entry {entry_id}")
        return True

    def get_summary(
        self,
        max_entries: Optional[int] = None,
        stages: Optional[List[ReasoningStage]] = None,
        include_corrections_only: bool = False
    ) -> str:
        """
        Generate a text summary of the reasoning trace for LLM context.

        This is the key method that replaces scenario-specific prompt examples
        with actual execution history.

        Args:
            max_entries: Limit number of entries (most recent)
            stages: Filter by specific stages
            include_corrections_only: Only show entries with corrections

        Returns:
            Formatted string summary for prompt injection
        """
        if not self.entries:
            return ""

        # Filter entries
        filtered = self.entries
        if stages:
            stage_values = [s.value for s in stages]
            filtered = [e for e in filtered if e.stage in stage_values]

        if include_corrections_only:
            filtered = [e for e in filtered if e.corrections]

        if max_entries:
            filtered = filtered[-max_entries:]

        if not filtered:
            return ""

        # Format summary
        lines = ["## Reasoning Trace"]
        lines.append(f"(Recent {len(filtered)} steps from this interaction)")
        lines.append("")

        for entry in filtered:
            stage_label = entry.stage.upper()
            lines.append(f"[{stage_label}] {entry.thought}")

            if entry.action:
                params_str = ", ".join(f"{k}={v}" for k, v in entry.parameters.items())
                lines.append(f"  → Action: {entry.action}({params_str})")

            if entry.evidence:
                for ev in entry.evidence:
                    lines.append(f"  • Evidence: {ev}")

            if entry.attachments:
                for att in entry.attachments:
                    att_type = att.get("type", "unknown")
                    att_info = att.get("path") or att.get("id") or att.get("name")
                    lines.append(f"  📎 Attachment: {att_type} = {att_info}")

            if entry.commitments:
                lines.append(f"  ⚠️ Commitments: {', '.join(entry.commitments)}")

            if entry.corrections:
                for corr in entry.corrections:
                    lines.append(f"  🔧 Correction: {corr}")

            lines.append(f"  ✓ Outcome: {entry.outcome}")

            if entry.error:
                lines.append(f"  ❌ Error: {entry.error}")

            lines.append("")  # Blank line between entries

        return "\n".join(lines)

    def get_pending_commitments(self) -> List[str]:
        """
        Get all unfulfilled commitments from the trace.

        Used during finalization to check if we fulfilled all promises
        (e.g., "send_email", "attach_document").

        Returns:
            List of commitment strings
        """
        pending = []
        for entry in self.entries:
            if entry.has_pending_commitments():
                pending.extend(entry.commitments)
        return pending

    def get_attachments(self) -> List[Dict[str, Any]]:
        """
        Get all attachments discovered/created during execution.

        Returns:
            List of attachment dictionaries
        """
        attachments = []
        for entry in self.entries:
            attachments.extend(entry.attachments)
        return attachments

    def get_corrections(self) -> List[str]:
        """
        Get all corrective guidance from Critic agent.

        Returns:
            List of correction strings
        """
        corrections = []
        for entry in self.entries:
            corrections.extend(entry.corrections)
        return corrections

    def has_errors(self) -> bool:
        """Check if any steps failed with errors."""
        return any(
            e.outcome == OutcomeStatus.FAILED.value and e.error
            for e in self.entries
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize trace to dictionary."""
        return {
            "interaction_id": self.interaction_id,
            "entries": [e.to_dict() for e in self.entries]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReasoningTrace':
        """Deserialize trace from dictionary."""
        trace = cls(interaction_id=data["interaction_id"])
        trace.entries = [
            ReasoningEntry.from_dict(e) for e in data.get("entries", [])
        ]
        trace._entry_index = {e.entry_id: e for e in trace.entries}
        return trace


# Utility functions for common patterns

def extract_attachments_from_step_result(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract attachment metadata from a step result.

    Looks for common patterns:
    - result["files"] or result["file_paths"]
    - result["documents"]
    - result["output_path"]

    Args:
        result: Step execution result dictionary

    Returns:
        List of attachment dictionaries
    """
    attachments = []

    # Pattern 1: files/file_paths list
    files = result.get("files") or result.get("file_paths")
    if files:
        if isinstance(files, list):
            for f in files:
                if isinstance(f, str):
                    attachments.append({"type": "file", "path": f, "status": "found"})
                elif isinstance(f, dict):
                    attachments.append({
                        "type": "file",
                        "path": f.get("path") or f.get("file_path"),
                        "name": f.get("name"),
                        "status": "found"
                    })

    # Pattern 2: documents list
    documents = result.get("documents")
    if documents and isinstance(documents, list):
        for doc in documents:
            if isinstance(doc, dict):
                attachments.append({
                    "type": "document",
                    "path": doc.get("file_path") or doc.get("path"),
                    "name": doc.get("filename") or doc.get("name"),
                    "status": "found"
                })

    # Pattern 3: single output_path
    output_path = result.get("output_path") or result.get("file_path")
    if output_path and isinstance(output_path, str):
        attachments.append({
            "type": "file",
            "path": output_path,
            "status": "created"
        })

    return attachments


def detect_commitments_from_user_request(request: str, config: Dict[str, Any]) -> List[str]:
    """
    Detect delivery commitments from user request.

    Uses config.yaml delivery.intent_verbs to identify when user
    expects email sending, attachments, etc.

    Args:
        request: User's input string
        config: Configuration dictionary

    Returns:
        List of commitment strings (e.g., ["send_email", "attach_documents"])
    """
    commitments = []
    request_lower = request.lower()

    # Get delivery intent verbs from config (with fallback)
    intent_verbs = config.get("delivery", {}).get("intent_verbs", [])
    if not intent_verbs:
        intent_verbs = ["email", "send", "mail", "attach"]

    # Check for delivery intent
    if any(verb in request_lower for verb in intent_verbs):
        # Check for attachment intent (before adding send_email)
        attachment_keywords = ["attach", "include", "with", "files", "documents", "them", "it"]
        if any(kw in request_lower for kw in attachment_keywords):
            commitments.append("attach_documents")

        # Always add send_email if delivery verbs present
        commitments.append("send_email")

    return commitments
