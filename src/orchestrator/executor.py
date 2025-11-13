"""
Standalone Executor/Orchestrator - responsible ONLY for executing plans.

Separation of Concerns:
- Planner: Creates plans (planner.py)
- Executor/Orchestrator: Executes plans, manages state, handles errors
"""

import logging
import re
import asyncio
from typing import Dict, Any, List, Optional, Set, Tuple
from enum import Enum
from collections import defaultdict

from ..agent import ALL_AGENT_TOOLS
from ..agent.verifier import OutputVerifier
from .tools_catalog import build_tool_parameter_index


logger = logging.getLogger(__name__)
PLACEHOLDER_PATTERN = re.compile(r"\$step\d+[^\s]+")


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
        
        # Performance configuration
        perf_config = config.get("performance", {})
        parallel_config = perf_config.get("parallel_execution", {})
        self.parallel_enabled = parallel_config.get("enabled", True)
        self.max_parallel_steps = parallel_config.get("max_parallel_steps", 5)
        self.dependency_analysis = parallel_config.get("dependency_analysis", True)
        
        background_config = perf_config.get("background_tasks", {})
        self.background_verification = background_config.get("verification", True)
        
        logger.info(f"[EXECUTOR] Parallel execution: {self.parallel_enabled}, Max parallel: {self.max_parallel_steps}")
        logger.info(f"[EXECUTOR] Background verification: {self.background_verification}")

        # Initialize tools (all agent tools)
        self.tools = {tool.name: tool for tool in ALL_AGENT_TOOLS}
        self.tool_parameters = build_tool_parameter_index()
        logger.info(f"Executor initialized with {len(self.tools)} tools from all agents")

        # Initialize verifier if enabled
        self.verifier = None
        if enable_verification:
            from ..agent.verifier import OutputVerifier
            self.verifier = OutputVerifier(config)
            logger.info("Output verification enabled")
    
    def _analyze_dependencies(self, plan: List[Dict[str, Any]]) -> Dict[int, Set[int]]:
        """
        Analyze step dependencies to enable parallel execution.
        
        Args:
            plan: List of plan steps
            
        Returns:
            Dictionary mapping step_id to set of dependency step_ids
        """
        dependencies = {}
        
        for step in plan:
            step_id = step.get("id", -1)
            
            # Explicit dependencies from plan
            explicit_deps = set(step.get("dependencies", []))
            
            # Implicit dependencies from parameter references ($stepN.field)
            implicit_deps = set()
            parameters = step.get("parameters", {})
            
            def find_step_refs(obj):
                """Recursively find step references in parameters."""
                if isinstance(obj, str):
                    matches = PLACEHOLDER_PATTERN.findall(obj)
                    for match in matches:
                        # Extract step number from $step3.output or similar
                        step_num_str = match.split('.')[0].replace('$step', '')
                        try:
                            implicit_deps.add(int(step_num_str))
                        except ValueError:
                            pass
                elif isinstance(obj, dict):
                    for val in obj.values():
                        find_step_refs(val)
                elif isinstance(obj, list):
                    for item in obj:
                        find_step_refs(item)
            
            find_step_refs(parameters)
            
            # Combine explicit and implicit dependencies
            all_deps = explicit_deps | implicit_deps
            dependencies[step_id] = all_deps
            
            if all_deps:
                logger.debug(f"[EXECUTOR] Step {step_id} depends on: {all_deps}")
        
        return dependencies
    
    def _group_steps_by_level(
        self, 
        plan: List[Dict[str, Any]], 
        dependencies: Dict[int, Set[int]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Group steps into execution levels where each level can run in parallel.
        
        Args:
            plan: List of plan steps
            dependencies: Step dependencies from _analyze_dependencies
            
        Returns:
            List of step groups (levels), where steps in same level can run in parallel
        """
        # Map step IDs to steps
        step_map = {step.get("id"): step for step in plan}
        
        # Calculate execution level for each step
        step_levels = {}
        
        def get_level(step_id: int) -> int:
            """Get execution level for a step (recursive with memoization)."""
            if step_id in step_levels:
                return step_levels[step_id]
            
            deps = dependencies.get(step_id, set())
            if not deps:
                # No dependencies = level 0
                step_levels[step_id] = 0
                return 0
            
            # Level is 1 + max level of dependencies
            max_dep_level = max(get_level(dep_id) for dep_id in deps if dep_id in step_map)
            level = max_dep_level + 1
            step_levels[step_id] = level
            return level
        
        # Calculate levels for all steps
        for step in plan:
            get_level(step.get("id"))
        
        # Group steps by level
        levels = defaultdict(list)
        for step in plan:
            level = step_levels[step.get("id")]
            levels[level].append(step)
        
        # Convert to sorted list of levels
        sorted_levels = [levels[i] for i in sorted(levels.keys())]
        
        logger.info(f"[EXECUTOR] Grouped {len(plan)} steps into {len(sorted_levels)} execution levels")
        for i, level_steps in enumerate(sorted_levels):
            step_ids = [s.get("id") for s in level_steps]
            logger.info(f"[EXECUTOR] Level {i}: {len(level_steps)} steps (IDs: {step_ids})")
        
        return sorted_levels
    
    async def _execute_step_async(
        self,
        step: Dict[str, Any],
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a single step asynchronously.
        
        Args:
            step: Step to execute
            state: Current execution state
            
        Returns:
            Step result dictionary
        """
        # Use asyncio to run synchronous _execute_step in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._execute_step, step, state)
    
    async def _verify_step_async(
        self,
        goal: str,
        step: Dict[str, Any],
        step_result: Dict[str, Any],
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Verify step output asynchronously.
        
        Args:
            goal: Original user goal
            step: Step definition
            step_result: Step execution result
            state: Execution state
            
        Returns:
            Verification result dictionary
        """
        if not self.verifier:
            return {"valid": True, "issues": [], "suggestions": [], "confidence": 1.0}
        
        # Use asyncio to run synchronous verification in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.verifier.verify_step_output,
            goal,
            step,
            step_result,
            {"previous_steps": state["step_results"]}
        )

    async def execute_plan_async(
        self,
        plan: List[Dict[str, Any]],
        goal: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a plan with parallel execution where possible (async).
        
        Args:
            plan: List of plan steps to execute
            goal: Original user goal (for verification)
            context: Additional execution context
            
        Returns:
            Execution result dictionary
        """
        logger.info(f"[EXECUTOR] Executing plan with {len(plan)} steps (async/parallel)")
        
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
        
        # Analyze dependencies and group steps
        if self.dependency_analysis and len(plan) > 1:
            dependencies = self._analyze_dependencies(plan)
            step_levels = self._group_steps_by_level(plan, dependencies)
        else:
            # Fallback: treat as sequential
            step_levels = [[step] for step in plan]
        
        total_completed = 0
        verification_tasks = []
        
        # Execute steps level by level
        for level_idx, level_steps in enumerate(step_levels):
            logger.info(f"[EXECUTOR] Executing level {level_idx} with {len(level_steps)} steps")
            
            # Execute steps in this level in parallel
            tasks = []
            for step in level_steps:
                step_id = step.get("id")
                
                # Check dependencies
                if not self._check_dependencies(step, state):
                    logger.warning(f"Step {step_id}: Dependencies not met, skipping")
                    state["step_results"][step_id] = {
                        "error": True,
                        "skipped": True,
                        "error_message": "Dependencies not met"
                    }
                    continue
                
                # Create execution task
                task = self._execute_step_async(step, state)
                tasks.append((step_id, step, task))
            
            # Wait for all steps in this level to complete
            if tasks:
                results = await asyncio.gather(*[task for _, _, task in tasks], return_exceptions=True)
                
                # Process results
                for (step_id, step, _), result in zip(tasks, results):
                    if isinstance(result, Exception):
                        logger.error(f"Step {step_id} failed with exception: {result}")
                        state["step_results"][step_id] = {
                            "error": True,
                            "error_message": str(result),
                            "output": None
                        }
                    else:
                        state["step_results"][step_id] = result
                        total_completed += 1
                    
                    self._log_step_outcome(step_id, step, state["step_results"][step_id])
                    
                    # Check for critical failures
                    if state["step_results"][step_id].get("error"):
                        error_result = state["step_results"][step_id]
                        if error_result.get("retry_possible"):
                            return {
                                "status": ExecutionStatus.NEEDS_REPLAN,
                                "steps_completed": total_completed,
                                "steps_total": len(plan),
                                "step_results": state["step_results"],
                                "verification_results": state["verification_results"],
                                "final_output": None,
                                "error": error_result.get("error_message"),
                                "needs_replan": True,
                                "replan_reason": f"Step {step_id} failed: {error_result.get('error_message')}"
                            }
                    
                    # Start background verification if enabled
                    if self.verifier and self._should_verify_step(step) and not state["step_results"][step_id].get("error"):
                        if self.background_verification:
                            # Create verification task to run in background
                            verify_task = asyncio.create_task(
                                self._verify_step_async(goal, step, state["step_results"][step_id], state)
                            )
                            verification_tasks.append((step_id, verify_task))
                        else:
                            # Run verification synchronously
                            verification = await self._verify_step_async(
                                goal, step, state["step_results"][step_id], state
                            )
                            state["verification_results"][step_id] = verification
        
        # Wait for all background verification tasks to complete
        if verification_tasks:
            logger.info(f"[EXECUTOR] Waiting for {len(verification_tasks)} background verification tasks")
            verifications = await asyncio.gather(*[task for _, task in verification_tasks], return_exceptions=True)
            
            for (step_id, _), verification in zip(verification_tasks, verifications):
                if isinstance(verification, Exception):
                    logger.error(f"Verification for step {step_id} failed: {verification}")
                else:
                    state["verification_results"][step_id] = verification
        
        # All steps completed
        logger.info(f"[EXECUTOR] Plan execution complete: {total_completed}/{len(plan)} steps succeeded")
        
        final_output = state["step_results"].get(plan[-1].get("id")) if plan else None
        
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
    
    def execute_plan(
        self,
        plan: List[Dict[str, Any]],
        goal: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a plan (with optional parallel execution).

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
        # Use async execution if parallel is enabled
        if self.parallel_enabled and len(plan) > 1:
            logger.info(f"[EXECUTOR] Using parallel execution for {len(plan)} steps")
            # Run async version in sync context
            return asyncio.run(self.execute_plan_async(plan, goal, context))
        
        logger.info(f"Executing plan with {len(plan)} steps (sequential)")

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

        success_steps = 0
        failed_steps = 0
        skipped_steps = 0

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
                skipped_steps += 1
                continue

            # Execute the step
            step_result = self._execute_step(step, state)
            state["step_results"][step_id] = step_result
            step_success = self._log_step_outcome(step_id, step, step_result)

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

            if step_success:
                success_steps += 1
            else:
                failed_steps += 1

        # All steps completed
        logger.info(
            "[EXECUTOR] Plan execution summary: total=%d, succeeded=%d, failed=%d, skipped=%d",
            len(plan),
            success_steps,
            failed_steps,
            skipped_steps,
        )

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
        parameters = step.get("parameters") or {}
        if not isinstance(parameters, dict):
            return {
                "error": True,
                "error_type": "InvalidParameters",
                "error_message": f"Parameters for '{action}' must be an object/dict, got {type(parameters).__name__}",
                "retry_possible": False
            }

        # Resolve parameter references (pass action name for special handling)
        resolved_params = self._resolve_parameters(parameters, state, action)
        logger.info(f"[EXECUTOR] {action} parameters -> raw={parameters}, resolved={resolved_params}")

        # Get the tool
        tool = self.tools.get(action)
        if not tool:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Tool '{action}' not found",
                "retry_possible": False
            }

        # Validate required parameters before invocation
        validation_error = self._validate_parameters(action, resolved_params)
        if validation_error:
            logger.error(f"[EXECUTOR] Parameter validation failed for {action}: {validation_error['error_message']}")
            return validation_error

        # Execute the tool
        try:
            logger.info(f"Calling tool {action} with params: {resolved_params}")
            result = tool.invoke(resolved_params)
            logger.info(f"Tool {action} returned: {type(result)}")
            
            # Ensure result is always a dictionary (defensive programming)
            if not isinstance(result, dict):
                logger.warning(f"Tool {action} returned non-dict result: {type(result)}, wrapping")
                return {"output": result, "error": False}
            
            # Validate error structure if error is present
            if result.get("error") and not result.get("error_type"):
                logger.warning(f"Tool {action} returned error=True but missing error_type, adding default")
                result["error_type"] = "UnknownError"
            
            return result

        except Exception as e:
            logger.error(f"Tool {action} raised exception: {e}", exc_info=True)
            return {
                "error": True,
                "error_type": "ToolExecutionError",
                "error_message": str(e),
                "retry_possible": True
            }

    def _log_step_outcome(self, step_id: Any, step: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """
        Emit rich logging for step outcomes so CLI/UI discrepancies are easier to spot.

        Returns True when the step is considered successful.
        """
        action = step.get("action", "unknown")
        status = result.get("status") or ("error" if result.get("error") else "success")
        success = not result.get("error") and status not in {"error", "failed", "failure"}
        icon = "✅" if success else "❌"

        summary_parts: List[str] = []
        message = result.get("message")
        if message:
            summary_parts.append(f"message={self._compact_text(message)}")

        error_message = result.get("error_message")
        if error_message:
            summary_parts.append(f"error={self._compact_text(error_message)}")
        elif result.get("error"):
            summary_parts.append("error flag set (no error_message)")

        if result.get("skipped"):
            summary_parts.append("skipped=True")

        logger.info(
            "[EXECUTOR] %s Step %s [%s] status=%s%s",
            icon,
            step_id,
            action,
            status,
            f" | {' | '.join(summary_parts)}" if summary_parts else "",
        )

        if action == "reply_to_user":
            details = result.get("details", "") or ""
            if not (message or "").strip():
                logger.warning("[EXECUTOR] reply_to_user produced an empty message payload")

            combined_text = f"{message or ''} {details}"
            unresolved = PLACEHOLDER_PATTERN.findall(combined_text)
            if unresolved:
                logger.warning(
                    "[EXECUTOR] reply_to_user contains unresolved placeholders: %s",
                    sorted(set(unresolved)),
                )

            if details:
                logger.debug(
                    "[EXECUTOR] reply_to_user details preview: %s",
                    self._compact_text(details, limit=200),
                )

        return success

    @staticmethod
    def _compact_text(text: str, limit: int = 160) -> str:
        """Compact text for logging by stripping whitespace and truncating."""
        cleaned = " ".join(text.split())
        if len(cleaned) <= limit:
            return cleaned
        return f"{cleaned[:limit - 3]}..."

    def _resolve_parameters(
        self,
        parameters: Dict[str, Any],
        state: Dict[str, Any],
        action: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resolve parameter references like $step1.output and template strings like "Found {$step1.count} items".

        Uses shared template resolver for consistency across all executors.

        Args:
            parameters: Parameters with potential references
            state: Current execution state
            action: Optional action name (for special handling)

        Returns:
            Parameters with references resolved
        """
        from ..utils.template_resolver import resolve_parameters as resolve_params

        return resolve_params(parameters, state["step_results"], action)

    def _validate_parameters(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Ensure required parameters are populated before executing a tool.

        Args:
            tool_name: Tool being executed
            parameters: Resolved parameters for the tool

        Returns:
            None if validation passes, else structured error payload
        """
        param_meta = self.tool_parameters.get(tool_name, {})
        required_params: List[str] = param_meta.get("required") or []

        if not required_params:
            return None

        missing: List[str] = []
        for param in required_params:
            if param not in parameters:
                missing.append(param)
                continue

            value = parameters.get(param)
            if value is None:
                missing.append(param)
            elif isinstance(value, str) and not value.strip():
                missing.append(param)

        if missing:
            missing_sorted = sorted(set(missing))
            return {
                "error": True,
                "error_type": "MissingParameters",
                "error_message": (
                    f"Missing required parameters for '{tool_name}': "
                    f"{', '.join(missing_sorted)}"
                ),
                "retry_possible": False,
                "missing_parameters": missing_sorted,
            }

        # Special validation for compose_email attachments
        if tool_name == "compose_email" and "attachments" in parameters:
            attachments = parameters.get("attachments")
            if attachments:
                if not isinstance(attachments, list):
                    return {
                        "error": True,
                        "error_type": "InvalidAttachments",
                        "error_message": (
                            "compose_email 'attachments' parameter must be a list of file paths. "
                            f"Got {type(attachments).__name__} instead."
                        ),
                        "retry_possible": False,
                        "suggestion": "Use create_pages_doc to save report content to a file, then pass the file path in attachments."
                    }
                
                for att in attachments:
                    if not isinstance(att, str):
                        return {
                            "error": True,
                            "error_type": "InvalidAttachments",
                            "error_message": (
                                "All items in 'attachments' must be strings (file paths). "
                                f"Found {type(att).__name__} in the list."
                            ),
                            "retry_possible": False,
                            "suggestion": "Ensure all attachments are file paths, not content/data objects."
                        }
                    
                    # Check if string looks like TEXT CONTENT rather than a file path
                    # Heuristics: contains newlines, is very long, or doesn't look like a path
                    if len(att) > 500 or '\n' in att or '\r' in att:
                        return {
                            "error": True,
                            "error_type": "InvalidAttachments",
                            "error_message": (
                                "Attachment appears to be TEXT CONTENT rather than a file path. "
                                f"The attachment string is {len(att)} characters long and contains newlines. "
                                "compose_email 'attachments' parameter requires FILE PATHS, not content."
                            ),
                            "retry_possible": True,
                            "suggestion": (
                                "To email a report: "
                                "1. Use create_detailed_report to generate report content (returns report_content as TEXT) "
                                "2. Use create_pages_doc(content=$stepN.report_content) to save it to a file (returns pages_path) "
                                "3. Use compose_email(attachments=[$stepN.pages_path]) with the FILE PATH"
                            ),
                            "detected_content_preview": att[:200] + "..." if len(att) > 200 else att
                        }

        return None

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
