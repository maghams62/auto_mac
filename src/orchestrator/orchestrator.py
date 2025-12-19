"""
Main LangGraph orchestrator with Plan-Execute-Evaluate-Replan loop.
"""

import logging
import json
from typing import Dict, Any, Optional
from pathlib import Path
from langgraph.graph import StateGraph, END

from .state import OrchestratorState, create_initial_state, Budget
from .nodes import PlannerNode, EvaluatorNode, ExecutorNode, SynthesisNode
from .llamaindex_worker import create_llamaindex_worker
from .tools_catalog import generate_tool_catalog, get_tool_specs_as_dicts
from ..documents import DocumentIndexer

logger = logging.getLogger(__name__)


class LangGraphOrchestrator:
    """
    Main orchestrator using LangGraph for control flow.

    Implements Plan → Validate → Execute → Evaluate → Replan loop.
    """

    def __init__(self, config: Dict[str, Any], document_indexer: DocumentIndexer):
        """
        Initialize the orchestrator.

        Args:
            config: Configuration dictionary
            document_indexer: Document indexer for RAG
        """
        self.config = config
        self.document_indexer = document_indexer

        # Generate tool catalog
        self.tool_catalog = generate_tool_catalog(config=config)
        self.tool_specs = get_tool_specs_as_dicts(self.tool_catalog)

        # Initialize components
        self.llamaindex_worker = create_llamaindex_worker(config, document_indexer)
        self.planner = PlannerNode(config)
        self.evaluator = EvaluatorNode(config)
        self.executor = ExecutorNode(config, self.llamaindex_worker, self.evaluator)
        self.synthesizer = SynthesisNode(config)

        # Build graph
        self.graph = self._build_graph()

        logger.info("LangGraph orchestrator initialized")

    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow.

        Control flow:
        UserInput → Plan → Validate → [Execute → Evaluate]* → Synthesize → END
                      ↑                    ↓
                      └─── Replan ←────────┘
        """
        workflow = StateGraph(OrchestratorState)

        # Add nodes
        workflow.add_node("plan", self.planner)
        workflow.add_node("validate", self._validate_node)
        workflow.add_node("execute", self.executor)
        workflow.add_node("synthesize", self.synthesizer)

        # Entry point
        workflow.set_entry_point("plan")

        # Plan → Validate
        workflow.add_edge("plan", "validate")

        # Validate → Execute or Replan
        workflow.add_conditional_edges(
            "validate",
            self._after_validation,
            {
                "execute": "execute",
                "replan": "plan"
            }
        )

        # Execute → Continue Execute, Replan, or Synthesize
        workflow.add_conditional_edges(
            "execute",
            self._after_execution,
            {
                "continue": "execute",
                "replan": "plan",
                "synthesize": "synthesize"
            }
        )

        # Synthesize → END
        workflow.add_edge("synthesize", END)

        return workflow.compile()

    def _validate_node(self, state: OrchestratorState) -> OrchestratorState:
        """Validation node wrapper."""
        return self.evaluator.validate_plan(state)

    def _after_validation(self, state: OrchestratorState) -> str:
        """Decide next step after validation."""
        if state["need_replan"]:
            return "replan"
        return "execute"

    def _after_execution(self, state: OrchestratorState) -> str:
        """Decide next step after execution."""
        if state["need_replan"]:
            return "replan"
        elif state["status"] == "synthesizing":
            return "synthesize"
        else:
            return "continue"

    def execute(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        budget: Optional[Budget] = None
    ) -> Dict[str, Any]:
        """
        Execute a workflow for a goal.

        Args:
            goal: High-level objective
            context: Additional context and constraints
            budget: Budget constraints

        Returns:
            Final result dictionary
        """
        logger.info(f"Starting orchestrator for goal: {goal}")

        # Create initial state
        initial_state = create_initial_state(
            goal=goal,
            context=context or {},
            tool_specs=self.tool_catalog,
            budget=budget
        )

        try:
            # Run the graph
            final_state = self.graph.invoke(initial_state)

            # Extract result
            result = final_state.get("final_result", {
                "success": False,
                "summary": "No result generated"
            })

            # Add execution metadata
            result["metadata"] = {
                "run_id": final_state["metadata"]["run_id"],
                "steps_executed": len(final_state["completed_steps"]),
                "steps_failed": len(final_state["failed_steps"]),
                "budget_used": {
                    "tokens": final_state["budget"]["tokens_used"],
                    "time_s": final_state["budget"]["time_used"],
                    "steps": final_state["budget"]["steps_used"]
                },
                "status": final_state["status"]
            }

            logger.info(f"Orchestration completed: {result.get('summary', 'N/A')}")
            return result

        except Exception as e:
            logger.error(f"Orchestration error: {e}", exc_info=True)
            return {
                "success": False,
                "summary": f"Orchestration failed: {str(e)}",
                "key_outputs": {},
                "next_actions": [],
                "error": str(e)
            }

    def resume(self, state_path: str) -> Dict[str, Any]:
        """
        Resume execution from a saved state.

        Args:
            state_path: Path to saved state JSON

        Returns:
            Final result dictionary
        """
        logger.info(f"Resuming from state: {state_path}")

        try:
            # Load state
            with open(state_path, 'r') as f:
                saved_state = json.load(f)

            # Run from current point
            final_state = self.graph.invoke(saved_state)

            return final_state.get("final_result", {
                "success": False,
                "summary": "Resume failed"
            })

        except Exception as e:
            logger.error(f"Resume error: {e}")
            return {
                "success": False,
                "summary": f"Resume failed: {str(e)}",
                "error": str(e)
            }

    def save_state(self, state: OrchestratorState, output_path: str):
        """
        Save current state to disk for resumability.

        Args:
            state: Current orchestrator state
            output_path: Path to save state JSON
        """
        try:
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w') as f:
                json.dump(state, f, indent=2, default=str)

            logger.info(f"State saved to {output_path}")

        except Exception as e:
            logger.error(f"Failed to save state: {e}")


def create_orchestrator(config: Dict[str, Any], document_indexer: DocumentIndexer) -> LangGraphOrchestrator:
    """
    Factory function to create an orchestrator.

    Args:
        config: Configuration dictionary
        document_indexer: Document indexer instance

    Returns:
        LangGraphOrchestrator instance
    """
    return LangGraphOrchestrator(config, document_indexer)
