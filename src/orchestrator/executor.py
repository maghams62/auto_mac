"""
Standalone Executor/Orchestrator - responsible ONLY for executing plans.

Separation of Concerns:
- Planner: Creates plans (planner.py)
- Executor/Orchestrator: Executes plans, manages state, handles errors
"""

import logging
from typing import Dict, Any, List, Optional
from enum import Enum

from ..agent import ALL_AGENT_TOOLS
from ..agent.verifier import OutputVerifier


logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Status of plan execution."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    NEEDS_REPLAN = "needs_replan"


class PlanExecutor:
    """
    Pure executor - executes plans created by the Planner.

    Responsibilities:
    - Execute plan steps in order
    - Manage execution state
    - Handle step failures
    - Resolve parameter references ($stepN.field)
    - Verify outputs (optional)
    - Track dependencies

    NOT responsible for:
    - Creating plans
    - Deciding which tools to use
    - Replanning (delegates to orchestrator)
    """

    def __init__(self, config: Dict[str, Any], enable_verification: bool = True):
        """
        Initialize the executor.

        Args:
            config: Configuration dictionary
            enable_verification: Whether to verify step outputs
        """
        self.config = config
        self.enable_verification = enable_verification

        # Initialize tools (all agent tools)
        self.tools = {tool.name: tool for tool in ALL_AGENT_TOOLS}
        logger.info(f"Executor initialized with {len(self.tools)} tools from all agents")

        # Initialize verifier if enabled
        self.verifier = None
        if enable_verification:
            from ..agent.verifier import OutputVerifier
            self.verifier = OutputVerifier(config)
            logger.info("Output verification enabled")

    def execute_plan(
        self,
        plan: List[Dict[str, Any]],
        goal: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a plan.

        Args:
            plan: List of plan steps to execute
            goal: Original user goal (for verification)
            context: Additional execution context

        Returns:
            Execution result:
            {
                "status": ExecutionStatus,
                "steps_completed": int,
                "steps_total": int,
                "step_results": Dict[int, Any],  # Results keyed by step ID
                "verification_results": Dict[int, Any],  # Verification keyed by step ID
                "final_output": Any,  # Output of last step
                "error": Optional[str],
                "needs_replan": bool,
                "replan_reason": Optional[str]
            }
        """
        logger.info(f"Executing plan with {len(plan)} steps")

        # Initialize execution state
        state = {
            "goal": goal,
            "plan": plan,
            "context": context or {},
            "step_results": {},
            "verification_results": {},
            "current_step": 0,
            "status": ExecutionStatus.IN_PROGRESS
        }

        # Execute steps
        for i, step in enumerate(plan):
            step_id = step.get("id", i)
            logger.info(f"Executing step {step_id}: {step.get('action')}")

            # Check dependencies
            if not self._check_dependencies(step, state):
                logger.warning(f"Step {step_id}: Dependencies not met, skipping")
                state["step_results"][step_id] = {
                    "error": True,
                    "skipped": True,
                    "error_message": "Dependencies not met"
                }
                continue

            # Execute the step
            step_result = self._execute_step(step, state)
            state["step_results"][step_id] = step_result

            # Check if step failed
            if step_result.get("error"):
                logger.error(f"Step {step_id} failed: {step_result.get('error_message')}")

                # Use Critic Agent to reflect on failure and suggest fixes
                reflection = self._reflect_on_failure(step, step_result, state)
                if reflection:
                    logger.info(f"[CRITIC] Root cause: {reflection.get('root_cause')}")
                    logger.info(f"[CRITIC] Corrective actions: {reflection.get('corrective_actions')}")

                # Check if we should replan
                should_retry = step_result.get("retry_possible") or (reflection and reflection.get("retry_recommended"))

                if should_retry:
                    replan_reason = f"Step {step_id} failed: {step_result.get('error_message')}"
                    if reflection:
                        replan_reason += f"\nRoot cause: {reflection.get('root_cause')}"
                        if reflection.get('corrective_actions'):
                            replan_reason += f"\nSuggested fixes: {', '.join(reflection.get('corrective_actions', []))}"

                    return {
                        "status": ExecutionStatus.NEEDS_REPLAN,
                        "steps_completed": i,
                        "steps_total": len(plan),
                        "step_results": state["step_results"],
                        "verification_results": state["verification_results"],
                        "final_output": None,
                        "error": step_result.get("error_message"),
                        "needs_replan": True,
                        "replan_reason": replan_reason,
                        "reflection": reflection
                    }
                else:
                    # Non-retryable error
                    return {
                        "status": ExecutionStatus.FAILED,
                        "steps_completed": i,
                        "steps_total": len(plan),
                        "step_results": state["step_results"],
                        "verification_results": state["verification_results"],
                        "final_output": None,
                        "error": step_result.get("error_message"),
                        "needs_replan": False,
                        "replan_reason": None,
                        "reflection": reflection
                    }

            # Verify step output if enabled
            if self.verifier and self._should_verify_step(step):
                verification = self.verifier.verify_step_output(
                    user_request=goal,
                    step=step,
                    step_result=step_result,
                    context={"previous_steps": state["step_results"]}
                )
                state["verification_results"][step_id] = verification

                # Check if verification failed significantly
                if not verification.get("valid") and verification.get("confidence", 0) > 0.8:
                    logger.warning(f"Step {step_id} verification failed: {verification.get('issues')}")
                    return {
                        "status": ExecutionStatus.NEEDS_REPLAN,
                        "steps_completed": i + 1,
                        "steps_total": len(plan),
                        "step_results": state["step_results"],
                        "verification_results": state["verification_results"],
                        "final_output": None,
                        "error": "Verification failed",
                        "needs_replan": True,
                        "replan_reason": f"Step {step_id} output doesn't match user intent: {verification.get('issues')}"
                    }

            logger.info(f"Step {step_id} completed successfully")

        # All steps completed
        final_output = state["step_results"].get(plan[-1].get("id", len(plan) - 1)) if plan else None

        return {
            "status": ExecutionStatus.SUCCESS,
            "steps_completed": len(plan),
            "steps_total": len(plan),
            "step_results": state["step_results"],
            "verification_results": state["verification_results"],
            "final_output": final_output,
            "error": None,
            "needs_replan": False,
            "replan_reason": None
        }

    def _execute_step(
        self,
        step: Dict[str, Any],
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a single step.

        Args:
            step: Step to execute
            state: Current execution state

        Returns:
            Step result dictionary
        """
        action = step.get("action")
        parameters = step.get("parameters", {})

        # Resolve parameter references
        resolved_params = self._resolve_parameters(parameters, state)

        # Get the tool
        tool = self.tools.get(action)
        if not tool:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Tool '{action}' not found",
                "retry_possible": False
            }

        # Execute the tool
        try:
            logger.info(f"Calling tool {action} with params: {resolved_params}")
            result = tool.invoke(resolved_params)
            logger.info(f"Tool {action} returned: {type(result)}")
            return result if isinstance(result, dict) else {"output": result}

        except Exception as e:
            logger.error(f"Tool {action} raised exception: {e}", exc_info=True)
            return {
                "error": True,
                "error_type": "ToolExecutionError",
                "error_message": str(e),
                "retry_possible": True
            }

    def _resolve_parameters(
        self,
        parameters: Dict[str, Any],
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Resolve parameter references like $step1.output.

        Args:
            parameters: Parameters with potential references
            state: Current execution state

        Returns:
            Parameters with references resolved
        """
        resolved = {}

        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith("$step"):
                # Parse reference: $step1.field.subfield
                parts = value[1:].split(".")  # Remove $ and split
                step_ref = parts[0]  # "step1"
                field_path = parts[1:]  # ["field", "subfield"]

                # Extract step ID
                step_id = int(step_ref.replace("step", ""))

                # Get step result
                step_result = state["step_results"].get(step_id)
                if step_result:
                    # Navigate field path
                    current_value = step_result
                    for field in field_path:
                        if isinstance(current_value, dict):
                            current_value = current_value.get(field)
                        else:
                            current_value = None
                            break

                    resolved[key] = current_value
                else:
                    logger.warning(f"Reference {value} points to non-existent step {step_id}")
                    resolved[key] = None
            else:
                resolved[key] = value

        return resolved

    def _check_dependencies(
        self,
        step: Dict[str, Any],
        state: Dict[str, Any]
    ) -> bool:
        """
        Check if step dependencies are satisfied.

        Args:
            step: Step to check
            state: Current execution state

        Returns:
            True if dependencies are met
        """
        dependencies = step.get("dependencies", [])

        for dep_id in dependencies:
            # Check if dependency step completed successfully
            dep_result = state["step_results"].get(dep_id)
            if not dep_result or dep_result.get("error"):
                return False

        return True

    def _should_verify_step(self, step: Dict[str, Any]) -> bool:
        """
        Determine if a step's output should be verified.

        Args:
            step: Step to check

        Returns:
            True if step should be verified
        """
        # Verify ALL critical steps that produce important outputs
        critical_actions = [
            # File Agent - verify content extraction and organization
            "extract_section",           # Verify correct section extracted
            "take_screenshot",           # Verify correct pages captured
            "organize_files",            # Verify correct files moved

            # Browser Agent - verify web content extraction
            "google_search",             # Verify search results relevant
            "extract_page_content",      # Verify content extracted correctly
            "take_web_screenshot",       # Verify screenshot captured

            # Presentation Agent - verify creation
            "create_keynote",            # Verify presentation created
            "create_keynote_with_images",# Verify images included
            "create_pages_doc",          # Verify document created

            # Email Agent - verify email sent
            "compose_email",             # Verify email sent/drafted
        ]

        return step.get("action") in critical_actions

    def _reflect_on_failure(
        self,
        step: Dict[str, Any],
        step_result: Dict[str, Any],
        state: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Use Critic Agent to reflect on step failure and suggest corrections.

        Args:
            step: The failed step
            step_result: The error result
            state: Current execution state

        Returns:
            Reflection with root cause and corrective actions, or None if reflection fails
        """
        try:
            from ..agent.critic_agent import CriticAgent

            critic = CriticAgent(self.config)

            # Build context for reflection
            context = {
                "step_description": f"Tool: {step.get('action')} with inputs: {step.get('inputs', {})}",
                "previous_steps": [
                    {
                        "id": k,
                        "result": v
                    }
                    for k, v in state["step_results"].items()
                ],
                "dependencies": step.get("deps", [])
            }

            # Use Critic Agent to reflect on failure
            reflection = critic.execute("reflect_on_failure", {
                "step_description": context["step_description"],
                "error_message": step_result.get("error_message", "Unknown error"),
                "context": context
            })

            if not reflection.get("error"):
                return reflection
            else:
                logger.warning(f"[CRITIC] Reflection failed: {reflection.get('error_message')}")
                return None

        except Exception as e:
            logger.error(f"[CRITIC] Error during reflection: {e}")
            return None
