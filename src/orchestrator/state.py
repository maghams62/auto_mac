"""
Shared state schema and data structures for orchestration.
"""

from typing import TypedDict, List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class Budget:
    """Budget constraints for task execution."""
    tokens: int = 100000
    time_s: int = 600
    steps: int = 50

    # Current usage
    tokens_used: int = 0
    time_used: float = 0.0
    steps_used: int = 0

    def is_exceeded(self) -> bool:
        """Check if any budget limit is exceeded."""
        return (
            self.tokens_used >= self.tokens or
            self.time_used >= self.time_s or
            self.steps_used >= self.steps
        )

    def remaining_percentage(self) -> float:
        """Get the minimum remaining percentage across all limits."""
        token_pct = 1.0 - (self.tokens_used / self.tokens)
        time_pct = 1.0 - (self.time_used / self.time_s)
        step_pct = 1.0 - (self.steps_used / self.steps)
        return min(token_pct, time_pct, step_pct)


@dataclass
class ToolSpec:
    """Tool specification for the catalog."""
    name: str
    kind: str  # "tool" or "worker"
    io: Dict[str, List[str]]  # {"in": [...], "out": [...]}
    strengths: List[str]
    limits: List[str]
    description: str = ""
    parameters: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "kind": self.kind,
            "io": self.io,
            "strengths": self.strengths,
            "limits": self.limits,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass
class Step:
    """Execution step in the plan."""
    id: str
    title: str
    type: str  # "atomic" | "tool" | "subplan"
    tool: Optional[str] = None
    inputs: Dict[str, Any] = field(default_factory=dict)
    deps: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    max_retries: int = 3
    timeout_s: int = 60

    # Execution metadata
    status: str = "pending"  # "pending" | "running" | "completed" | "failed" | "skipped"
    retries_left: int = 3
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error: Optional[str] = None
    patched_by: Optional[str] = None

    def __post_init__(self):
        """Initialize retries_left from max_retries."""
        if self.retries_left == 3 and self.max_retries != 3:
            self.retries_left = self.max_retries

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "tool": self.tool,
            "inputs": self.inputs,
            "deps": self.deps,
            "success_criteria": self.success_criteria,
            "max_retries": self.max_retries,
            "timeout_s": self.timeout_s,
            "status": self.status,
            "retries_left": self.retries_left,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "error": self.error,
            "patched_by": self.patched_by
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Step':
        """Create Step from dictionary."""
        return cls(**data)


class OrchestratorState(TypedDict):
    """Complete state for the orchestrator workflow."""

    # Core identifiers and goals
    goal: str
    context: Dict[str, Any]
    tool_specs: List[Dict[str, Any]]

    # Plan and execution
    plan: List[Dict[str, Any]]
    cursor: int  # Current step index or -1
    notes: List[Any]  # Critiques and repair hints
    artifacts: Dict[str, Any]  # step_id -> result

    # Budget and constraints
    budget: Dict[str, Any]

    # Metadata
    metadata: Dict[str, Any]

    # Control flags
    need_replan: bool
    validation_passed: bool

    # Execution tracking
    completed_steps: List[str]
    failed_steps: List[str]

    # Final output
    final_result: Optional[Dict[str, Any]]
    status: str  # "planning" | "validating" | "executing" | "replanning" | "completed" | "failed"


def create_initial_state(
    goal: str,
    context: Optional[Dict[str, Any]] = None,
    tool_specs: Optional[List[ToolSpec]] = None,
    budget: Optional[Budget] = None
) -> OrchestratorState:
    """
    Create an initial orchestrator state.

    Args:
        goal: The high-level objective
        context: Additional context and constraints
        tool_specs: Available tools
        budget: Budget constraints

    Returns:
        Initial OrchestratorState
    """
    if context is None:
        context = {}

    if tool_specs is None:
        tool_specs = []

    if budget is None:
        budget = Budget()

    run_id = str(uuid.uuid4())

    return {
        "goal": goal,
        "context": context,
        "tool_specs": [spec.to_dict() if isinstance(spec, ToolSpec) else spec for spec in tool_specs],
        "plan": [],
        "cursor": -1,
        "notes": [],
        "artifacts": {},
        "budget": {
            "tokens": budget.tokens,
            "time_s": budget.time_s,
            "steps": budget.steps,
            "tokens_used": budget.tokens_used,
            "time_used": budget.time_used,
            "steps_used": budget.steps_used
        },
        "metadata": {
            "run_id": run_id,
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        },
        "need_replan": False,
        "validation_passed": False,
        "completed_steps": [],
        "failed_steps": [],
        "final_result": None,
        "status": "planning"
    }
