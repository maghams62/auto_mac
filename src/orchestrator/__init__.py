"""
Orchestrator with separated Planner and Executor responsibilities.

New Architecture:
- Planner: Creates execution plans
- Executor: Executes plans
- MainOrchestrator: Coordinates planning and execution

Legacy:
- LangGraphOrchestrator: Old combined implementation (deprecated)
"""

from .state import OrchestratorState, Step, Budget, ToolSpec

# Import orchestrator (for backwards compatibility)
try:
    from .orchestrator import LangGraphOrchestrator
except ImportError as e:
    LangGraphOrchestrator = None

# New separated architecture (recommended)
try:
    from .planner import Planner
    from .executor import PlanExecutor
    # Don't import MainOrchestrator here to avoid circular imports
except ImportError as e:
    # Graceful degradation if dependencies missing
    Planner = None
    PlanExecutor = None

__all__ = [
    'OrchestratorState',
    'Step',
    'Budget',
    'ToolSpec',
    'LangGraphOrchestrator',
    'Planner',
    'PlanExecutor',
]
