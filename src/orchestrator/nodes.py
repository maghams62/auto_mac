"""
Orchestrator nodes: Planner, Executor, Evaluator, Synthesis.
"""

import json
import logging
import time
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .state import OrchestratorState, Step
from .prompts import (
    PLANNER_SYSTEM_PROMPT, PLANNER_TASK_PROMPT,
    EVALUATOR_SYSTEM_PROMPT, EVALUATOR_VALIDATION_PROMPT, EVALUATOR_STEP_CHECK_PROMPT,
    REPLAN_PROMPT, SYNTHESIS_PROMPT,
    format_notes_section, format_existing_plan_section
)
from .tools_catalog import format_tool_catalog_for_prompt
from .llamaindex_worker import LlamaIndexWorker
from .validator import PlanValidator
from ..agent import ALL_AGENT_TOOLS

logger = logging.getLogger(__name__)


class PlannerNode:
    """Planner node that creates execution plans."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.llm = ChatOpenAI(
            model=config.get("openai", {}).get("model", "gpt-4o"),
            temperature=0.2  # Lower temperature for structured planning
        )

    def __call__(self, state: OrchestratorState) -> OrchestratorState:
        """
        Plan task execution.

        Args:
            state: Current orchestrator state

        Returns:
            Updated state with plan
        """
        logger.info("=== PLANNER NODE ===")
        logger.info(f"Goal: {state['goal']}")

        # Format tool specs for prompt
        tool_catalog_str = format_tool_catalog_for_prompt(
            [{"name": t["name"], **t} for t in state["tool_specs"]]
        )

        # Format notes and existing plan if replanning
        notes_section = format_notes_section(state["notes"])
        existing_plan_section = format_existing_plan_section(
            state["plan"],
            state["completed_steps"]
        )

        # Build prompt
        task_prompt = PLANNER_TASK_PROMPT.format(
            goal=state["goal"],
            context=json.dumps(state["context"], indent=2),
            tool_specs=tool_catalog_str,
            notes_section=notes_section,
            existing_plan_section=existing_plan_section
        )

        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=task_prompt)
        ]

        try:
            response = self.llm.invoke(messages)
            response_text = response.content

            # Parse JSON response
            plan_steps = self._parse_plan(response_text)

            if plan_steps:
                logger.info(f"Plan created with {len(plan_steps)} steps")

                # ⚠️ CRITICAL: Programmatic validation BEFORE storing the plan
                # This prevents hallucinated tools from ever entering the system
                validator = PlanValidator(state["tool_specs"])
                is_valid, validation_errors = validator.validate_plan(plan_steps)

                if not is_valid:
                    logger.error("❌ PROGRAMMATIC VALIDATION FAILED - Plan contains invalid tools!")
                    for error in validation_errors:
                        if error["severity"] == "error":
                            logger.error(f"  {error['error_type']}: {error['message']}")
                            if "suggested_tools" in error:
                                logger.error(f"  Suggested alternatives: {error['suggested_tools']}")

                    # Force replanning with detailed feedback
                    error_messages = [e["message"] for e in validation_errors if e["severity"] == "error"]
                    state["notes"].append(f"VALIDATION FAILED: {'; '.join(error_messages)}")
                    state["need_replan"] = True
                    state["status"] = "validating"
                    return state

                logger.info("✅ Programmatic validation passed")

                # Validation passed - store the plan
                state["plan"] = plan_steps
                state["cursor"] = -1  # Reset cursor
                state["status"] = "validating"
                state["need_replan"] = False
            else:
                logger.error("Failed to create plan")
                state["status"] = "failed"
                state["final_result"] = {
                    "success": False,
                    "error": "Failed to create execution plan"
                }

        except Exception as e:
            logger.error(f"Planner error: {e}", exc_info=True)
            state["status"] = "failed"
            state["final_result"] = {
                "success": False,
                "error": f"Planner error: {str(e)}"
            }

        return state

    def _parse_plan(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Parse plan from LLM response.

        Args:
            response_text: Raw LLM response

        Returns:
            List of step dictionaries
        """
        try:
            # Try to extract JSON array
            # Handle both direct array and wrapped in object
            json_start = response_text.find("[")
            json_end = response_text.rfind("]") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                plan = json.loads(json_str)
                return plan if isinstance(plan, list) else []

            # Try object with "steps" key
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                obj = json.loads(json_str)
                if "steps" in obj:
                    return obj["steps"]

            logger.error("No valid JSON array found in response")
            return []

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse plan JSON: {e}")
            logger.error(f"Response: {response_text[:500]}")
            return []


class EvaluatorNode:
    """Evaluator node that validates plans and checks step results."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.llm = ChatOpenAI(
            model=config.get("openai", {}).get("model", "gpt-4o"),
            temperature=0.0  # Deterministic evaluation
        )

    def validate_plan(self, state: OrchestratorState) -> OrchestratorState:
        """
        Perform pre-execution validation on the plan.

        Args:
            state: Current orchestrator state

        Returns:
            Updated state with validation results
        """
        logger.info("=== EVALUATOR NODE (Validation) ===")

        # Build validation prompt
        prompt = EVALUATOR_VALIDATION_PROMPT.format(
            goal=state["goal"],
            plan=json.dumps(state["plan"], indent=2),
            tool_specs=json.dumps(state["tool_specs"], indent=2),
            budget=json.dumps(state["budget"], indent=2)
        )

        messages = [
            SystemMessage(content=EVALUATOR_SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]

        try:
            response = self.llm.invoke(messages)
            validation = self._parse_validation(response.content)

            if validation["valid"]:
                logger.info("Plan validation passed")
                state["validation_passed"] = True
                state["status"] = "executing"

                # Apply patches if any
                if validation.get("can_patch") and validation.get("patches"):
                    state = self._apply_patches(state, validation["patches"])

            else:
                logger.warning(f"Plan validation failed: {len(validation['issues'])} issues")
                state["validation_passed"] = False
                state["need_replan"] = True
                state["status"] = "replanning"

                # Add issues to notes
                for issue in validation["issues"]:
                    state["notes"].append(issue)

        except Exception as e:
            logger.error(f"Validation error: {e}", exc_info=True)
            # On validation error, proceed cautiously
            state["validation_passed"] = True
            state["status"] = "executing"
            state["notes"].append({
                "severity": "warning",
                "message": f"Validation error, proceeding: {str(e)}"
            })

        return state

    def check_step_result(
        self,
        step: Dict[str, Any],
        output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check if a step's output meets success criteria.

        Args:
            step: Step dictionary
            output: Step output

        Returns:
            Evaluation result
        """
        logger.debug(f"Checking step {step['id']} result")

        # Quick check for obvious errors
        if output.get("error"):
            return {
                "success": False,
                "criteria_met": [],
                "criteria_failed": step.get("success_criteria", []),
                "should_retry": step.get("retries_left", 0) > 0,
                "should_replan": False,
                "notes": "Step returned error"
            }

        # If no success criteria, assume success if no error
        success_criteria = step.get("success_criteria", [])
        if not success_criteria:
            return {
                "success": True,
                "criteria_met": [],
                "criteria_failed": [],
                "should_retry": False,
                "should_replan": False,
                "notes": "No success criteria defined, assuming success"
            }

        # Use LLM for detailed criteria check
        try:
            prompt = EVALUATOR_STEP_CHECK_PROMPT.format(
                step=json.dumps(step, indent=2),
                success_criteria=json.dumps(success_criteria, indent=2),
                output=json.dumps(output, indent=2)
            )

            messages = [
                SystemMessage(content=EVALUATOR_SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ]

            response = self.llm.invoke(messages)
            return self._parse_step_check(response.content)

        except Exception as e:
            logger.error(f"Step check error: {e}")
            # Default to success on evaluation error
            return {
                "success": True,
                "criteria_met": success_criteria,
                "criteria_failed": [],
                "should_retry": False,
                "should_replan": False,
                "notes": f"Evaluation error, assuming success: {str(e)}"
            }

    def _parse_validation(self, response_text: str) -> Dict[str, Any]:
        """Parse validation response."""
        try:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            json_str = response_text[json_start:json_end]
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Failed to parse validation: {e}")
            return {
                "valid": True,  # Default to valid on parse error
                "issues": [],
                "can_patch": False,
                "patches": []
            }

    def _parse_step_check(self, response_text: str) -> Dict[str, Any]:
        """Parse step check response."""
        try:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            json_str = response_text[json_start:json_end]
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Failed to parse step check: {e}")
            return {
                "success": True,
                "criteria_met": [],
                "criteria_failed": [],
                "should_retry": False,
                "should_replan": False,
                "notes": f"Parse error: {str(e)}"
            }

    def _apply_patches(self, state: OrchestratorState, patches: List[Dict[str, Any]]) -> OrchestratorState:
        """Apply patches to the plan."""
        logger.info(f"Applying {len(patches)} patches")

        for patch in patches:
            step_id = patch.get("step_id")
            field = patch.get("field")
            value = patch.get("value")

            # Find and update the step
            for step in state["plan"]:
                if step["id"] == step_id:
                    # Handle nested field paths (e.g., "inputs.param")
                    field_parts = field.split(".")
                    target = step
                    for part in field_parts[:-1]:
                        target = target.setdefault(part, {})
                    target[field_parts[-1]] = value

                    step["patched_by"] = "evaluator"
                    logger.info(f"Patched {step_id}.{field} = {value}")
                    break

        return state


class ExecutorNode:
    """Executor node that dispatches and runs steps."""

    def __init__(
        self,
        config: Dict[str, Any],
        llamaindex_worker: LlamaIndexWorker,
        evaluator: EvaluatorNode
    ):
        self.config = config
        self.llamaindex_worker = llamaindex_worker
        self.evaluator = evaluator

    def __call__(self, state: OrchestratorState) -> OrchestratorState:
        """
        Execute next ready step.

        Args:
            state: Current orchestrator state

        Returns:
            Updated state
        """
        # Check budget first
        if self._is_budget_exceeded(state):
            logger.warning("Budget exceeded, stopping execution")
            state["status"] = "completed"
            state["notes"].append("Stopped due to budget exhaustion")
            return state

        # Find next ready step
        next_step = self._get_next_ready_step(state)

        if next_step is None:
            # No more steps to execute
            logger.info("No more steps to execute")
            state["status"] = "synthesizing"
            return state

        logger.info(f"=== EXECUTOR NODE: {next_step['id']} ===")
        logger.info(f"Step: {next_step['title']}")

        # Execute the step
        start_time = time.time()
        result = self._execute_step(state, next_step)
        end_time = time.time()

        # Store result
        state["artifacts"][next_step["id"]] = result

        # Update budget
        elapsed = end_time - start_time
        state["budget"]["time_used"] += elapsed
        state["budget"]["steps_used"] += 1

        if "usage" in result:
            state["budget"]["tokens_used"] += result["usage"].get("tokens", 0)

        # Evaluate step result
        evaluation = self.evaluator.check_step_result(next_step, result)

        if evaluation["success"]:
            # Step succeeded
            state["completed_steps"].append(next_step["id"])
            next_step["status"] = "completed"
            logger.info(f"Step {next_step['id']} completed successfully")
        elif evaluation["should_retry"]:
            # Retry the step
            next_step["retries_left"] -= 1
            next_step["status"] = "pending"
            state["notes"].append({
                "severity": "info",
                "message": f"Retrying step {next_step['id']}: {evaluation['notes']}"
            })
            logger.info(f"Retrying step {next_step['id']} ({next_step['retries_left']} retries left)")
        elif evaluation["should_replan"]:
            # Fundamental issue, need replan
            next_step["status"] = "failed"
            state["failed_steps"].append(next_step["id"])
            state["need_replan"] = True
            state["status"] = "replanning"
            state["notes"].append({
                "severity": "error",
                "step_id": next_step["id"],
                "message": f"Step failed critically: {evaluation['notes']}"
            })
            logger.warning(f"Step {next_step['id']} failed, triggering replan")
        else:
            # Failed but no retry or replan
            next_step["status"] = "failed"
            state["failed_steps"].append(next_step["id"])
            logger.error(f"Step {next_step['id']} failed: {evaluation['notes']}")

        # Update cursor
        state["cursor"] = state["plan"].index(next_step)

        return state

    def _get_next_ready_step(self, state: OrchestratorState) -> Dict[str, Any]:
        """Find next step whose dependencies are all completed."""
        completed = set(state["completed_steps"])

        for step in state["plan"]:
            if step["status"] in ["completed", "running"]:
                continue

            # Check if all dependencies are met
            deps = step.get("deps", [])
            if all(dep in completed for dep in deps):
                return step

        return None

    def _execute_step(self, state: OrchestratorState, step: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single step.

        Args:
            state: Current state
            step: Step to execute

        Returns:
            Step result
        """
        step["status"] = "running"
        step["start_time"] = time.time()

        try:
            # Resolve parameters
            resolved_inputs = self._resolve_parameters(step["inputs"], state["artifacts"])

            # Route based on type and tool
            step_type = step.get("type", "tool")
            tool_name = step.get("tool")

            if step_type == "atomic" or tool_name == "llamaindex_worker":
                # Use LlamaIndex worker
                result = self.llamaindex_worker.execute(
                    task=step["title"],
                    context=state["context"],
                    artifacts=state["artifacts"]
                )
            elif step_type == "tool" and tool_name:
                # Use regular tool
                result = self._call_tool(tool_name, resolved_inputs)
            else:
                result = {
                    "error": True,
                    "error_type": "InvalidStep",
                    "error_message": f"Unknown step type: {step_type}"
                }

            step["end_time"] = time.time()
            return result

        except Exception as e:
            logger.error(f"Step execution error: {e}", exc_info=True)
            step["end_time"] = time.time()
            step["error"] = str(e)
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e)
            }

    def _call_tool(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Call a LangChain tool."""
        tool = next((t for t in ALL_AGENT_TOOLS if t.name == tool_name), None)

        if not tool:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Tool '{tool_name}' not found"
            }

        try:
            result = tool.invoke(inputs)
            return result if isinstance(result, dict) else {"result": result}
        except Exception as e:
            logger.error(f"Tool {tool_name} error: {e}")
            return {
                "error": True,
                "error_type": "ToolError",
                "error_message": str(e)
            }

    def _resolve_parameters(
        self,
        inputs: Dict[str, Any],
        artifacts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolve parameter references like $step1.field."""
        resolved = {}

        for key, value in inputs.items():
            if isinstance(value, str) and value.startswith("$"):
                # Parse reference
                parts = value[1:].split(".")
                if len(parts) >= 2:
                    step_id = parts[0]
                    field_path = parts[1:]

                    # Navigate nested structure
                    if step_id in artifacts:
                        artifact = artifacts[step_id]
                        for field in field_path:
                            if isinstance(artifact, dict) and field in artifact:
                                artifact = artifact[field]
                            else:
                                artifact = value  # Keep original if can't resolve
                                break
                        resolved[key] = artifact
                    else:
                        resolved[key] = value  # Keep original
                else:
                    resolved[key] = value
            elif isinstance(value, list):
                resolved[key] = [self._resolve_single_value(v, artifacts) for v in value]
            else:
                resolved[key] = value

        return resolved

    def _resolve_single_value(self, value: Any, artifacts: Dict[str, Any]) -> Any:
        """Resolve a single value."""
        if isinstance(value, str) and value.startswith("$"):
            parts = value[1:].split(".")
            if len(parts) >= 2:
                step_id = parts[0]
                field = parts[1]
                if step_id in artifacts and field in artifacts[step_id]:
                    return artifacts[step_id][field]
        return value

    def _is_budget_exceeded(self, state: OrchestratorState) -> bool:
        """Check if budget is exceeded."""
        budget = state["budget"]
        return (
            budget["tokens_used"] >= budget["tokens"] or
            budget["time_used"] >= budget["time_s"] or
            budget["steps_used"] >= budget["steps"]
        )


class SynthesisNode:
    """Synthesis node that creates final result."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.llm = ChatOpenAI(
            model=config.get("openai", {}).get("model", "gpt-4o"),
            temperature=0.3
        )

    def __call__(self, state: OrchestratorState) -> OrchestratorState:
        """
        Synthesize final result.

        Args:
            state: Current orchestrator state

        Returns:
            Updated state with final result
        """
        logger.info("=== SYNTHESIS NODE ===")

        prompt = SYNTHESIS_PROMPT.format(
            goal=state["goal"],
            steps=json.dumps(state["plan"], indent=2),
            artifacts=json.dumps(state["artifacts"], indent=2)
        )

        messages = [
            SystemMessage(content="You synthesize workflow results into final outputs."),
            HumanMessage(content=prompt)
        ]

        try:
            response = self.llm.invoke(messages)
            final_result = self._parse_result(response.content)

            state["final_result"] = final_result
            state["status"] = "completed"

            logger.info("Synthesis completed")

        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            state["final_result"] = {
                "success": False,
                "summary": f"Synthesis error: {str(e)}",
                "key_outputs": state["artifacts"],
                "next_actions": []
            }
            state["status"] = "completed"

        return state

    def _parse_result(self, response_text: str) -> Dict[str, Any]:
        """Parse synthesis result."""
        try:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            json_str = response_text[json_start:json_end]
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Failed to parse synthesis: {e}")
            return {
                "success": False,
                "summary": "Failed to synthesize result",
                "key_outputs": {},
                "next_actions": []
            }
