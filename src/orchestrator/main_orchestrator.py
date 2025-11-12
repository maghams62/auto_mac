"""
Main Orchestrator - coordinates Planner and Executor.

Architecture:
┌──────────────┐
│     User     │
│   Request    │
└──────┬───────┘
       │
       v
┌──────────────────────────────────┐
│   MainOrchestrator               │
│   - Manages overall workflow     │
│   - Coordinates Planner/Executor │
│   - Handles replanning loop      │
└──────┬───────────────────────────┘
       │
       ├──> Planner (creates plans)
       │
       └──> Executor (executes plans)
"""

import logging
from typing import Dict, Any, Optional

from ..memory import SessionManager
from ..memory.session_memory import SessionContext
from .planner import Planner
from .executor import PlanExecutor, ExecutionStatus
from .tools_catalog import generate_tool_catalog, get_tool_specs_as_dicts


logger = logging.getLogger(__name__)


class MainOrchestrator:
    """
    Main orchestrator that coordinates planning and execution.

    Responsibilities:
    - Receive user requests
    - Coordinate Planner and Executor
    - Handle plan-execute-replan loop
    - Manage retry logic
    - Return final results

    Components:
    - Planner: Creates execution plans
    - Executor: Executes plans
    """

    def __init__(
        self,
        config: Dict[str, Any],
        max_replans: int = 2,
        session_manager: Optional[SessionManager] = None
    ):
        """
        Initialize the orchestrator.

        Args:
            config: Configuration dictionary
            max_replans: Maximum number of replanning attempts
            session_manager: Optional session manager for context tracking
        """
        self.config = config
        self.max_replans = max_replans

        # Session management
        self.session_manager = session_manager
        if self.session_manager:
            logger.info("[MAIN ORCHESTRATOR] Session management enabled")

        # Initialize tool catalog
        self.tool_catalog = generate_tool_catalog()
        self.tool_specs = get_tool_specs_as_dicts(self.tool_catalog)

        # Initialize components
        self.planner = Planner(config)
        self.executor = PlanExecutor(config, enable_verification=True)

        logger.info(f"MainOrchestrator initialized with {len(self.tool_specs)} tools")

    def execute(
        self,
        user_request: str,
        context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a user request.

        Args:
            user_request: User's request/goal
            context: Optional context
            session_id: Optional session ID for context tracking

        Returns:
            Execution result dictionary
        """
        logger.info("=" * 80)
        logger.info(f"Processing request: {user_request}")
        logger.info("=" * 80)

        # Build SessionContext for structured memory access
        session_context_obj = None
        if self.session_manager and session_id:
            session_memory = self.session_manager.get_or_create_session(session_id)

            # Determine profile based on model capabilities
            model_name = self.config.get("openai", {}).get("model", "gpt-4o")
            if "o1" in model_name.lower() or "reasoning" in model_name.lower():
                profile = "reasoning"
            else:
                profile = "compact"

            session_context_obj = session_memory.build_context(
                profile=profile,
                purpose="planner",
                max_tokens=self.config.get("openai", {}).get("max_tokens")
            )

            # Also get legacy langgraph context for backward compatibility
            session_context = self.session_manager.get_langgraph_context(session_id)
            if context is None:
                context = session_context
            else:
                # Merge contexts
                context = {**session_context, **context}
            logger.info(f"[SESSION] Loaded context for session: {session_id} (profile: {profile})")

        # Initialize state
        attempt = 0
        previous_plan = None
        feedback = None

        while attempt <= self.max_replans:
            logger.info(f"\n{'='*80}")
            logger.info(f"ATTEMPT {attempt + 1} / {self.max_replans + 1}")
            logger.info(f"{'='*80}\n")

            # Step 1: Create plan
            logger.info(">>> PLANNING PHASE")

            # Ensure we have a SessionContext (create minimal one if needed)
            if session_context_obj is None:
                # Fallback for cases without session management
                from ..memory.session_memory import SessionMemory
                temp_memory = SessionMemory()
                temp_memory.add_interaction(user_request)
                session_context_obj = temp_memory.build_context(profile="compact", purpose="planner")

            plan_result = self.planner.create_plan(
                goal=user_request,
                available_tools=self.tool_catalog,  # Pass ToolSpec objects, not dicts
                session_context=session_context_obj,
                context=context,
                previous_plan=previous_plan,
                feedback=feedback
            )

            if not plan_result["success"]:
                logger.error(f"Planning failed: {plan_result['error']}")
                return {
                    "status": "failed",
                    "error": f"Planning failed: {plan_result['error']}",
                    "step_results": {}
                }

            plan = plan_result["plan"]
            logger.info(f"Plan created: {len(plan)} steps")
            for step in plan:
                logger.info(f"  Step {step.get('id')}: {step.get('action')} - {step.get('reasoning', '')}")

            # Step 2: Validate plan
            logger.info("\n>>> VALIDATION PHASE")
            validation = self.planner.validate_plan(plan, self.tool_specs)

            if not validation["valid"]:
                logger.error(f"Plan validation failed: {validation['issues']}")
                feedback = f"Plan validation failed: {', '.join(validation['issues'])}"
                previous_plan = plan
                attempt += 1
                continue

            if validation["warnings"]:
                logger.warning(f"Plan warnings: {validation['warnings']}")

            # Step 3: Execute plan
            logger.info("\n>>> EXECUTION PHASE")
            exec_result = self.executor.execute_plan(
                plan=plan,
                goal=user_request,
                context=context
            )

            # Check execution status
            if exec_result["status"] == ExecutionStatus.SUCCESS:
                logger.info("\n✅ Execution successful!")
                
                # Extract Maps URLs from step results and include at top level for easy access
                maps_url = None
                maps_result = None
                for step_result in exec_result["step_results"].values():
                    if isinstance(step_result, dict) and "maps_url" in step_result:
                        maps_url = step_result.get("maps_url")
                        maps_result = step_result
                        break
                
                # Ensure Maps URL uses https:// format (not maps://) for browser/UI compatibility
                if maps_url and maps_url.startswith("maps://"):
                    maps_url = maps_url.replace("maps://", "https://maps.apple.com/", 1)
                    logger.info(f"[ORCHESTRATOR] Converted maps:// URL to https:// format: {maps_url[:80]}...")
                    # Update the step result as well
                    if maps_result:
                        maps_result["maps_url"] = maps_url
                
                result = {
                    "status": "success",
                    "step_results": exec_result["step_results"],
                    "verification_results": exec_result.get("verification_results", {}),
                    "final_output": exec_result["final_output"],
                    "attempts": attempt + 1
                }
                
                # Include Maps URL at top level if found
                if maps_url:
                    result["maps_url"] = maps_url
                    result["maps_service"] = maps_result.get("maps_service", "Apple Maps")
                    result["origin"] = maps_result.get("origin")
                    result["destination"] = maps_result.get("destination")
                    result["stops"] = maps_result.get("stops", [])
                    
                    # Create simple, clean response message
                    if maps_result.get("maps_opened"):
                        result["message"] = f"Here's your trip, enjoy! {result['maps_service']} opened with your route: {maps_url}"
                    else:
                        result["message"] = f"Here's your trip, enjoy: {maps_url}"
                    
                    logger.info(f"[MAPS] Extracted Maps URL to top level: {maps_url[:80]}...")
                
                return result

            elif exec_result["status"] == ExecutionStatus.NEEDS_REPLAN:
                logger.warning(f"\n⚠ Execution needs replanning: {exec_result['replan_reason']}")
                feedback = exec_result["replan_reason"]
                previous_plan = plan
                attempt += 1
                continue

            else:
                # Failed without possibility of replanning
                logger.error(f"\n❌ Execution failed: {exec_result['error']}")
                return {
                    "status": "failed",
                    "error": exec_result["error"],
                    "step_results": exec_result["step_results"],
                    "attempts": attempt + 1
                }

        # Max replans exceeded
        logger.error(f"\n❌ Max replans ({self.max_replans}) exceeded")
        return {
            "status": "failed",
            "error": f"Max replanning attempts ({self.max_replans}) exceeded",
            "step_results": {},
            "attempts": attempt
        }

    def execute_with_streaming(
        self,
        user_request: str,
        context: Optional[Dict[str, Any]] = None,
        callback = None
    ) -> Dict[str, Any]:
        """
        Execute with streaming updates via callback.

        Args:
            user_request: User's request
            context: Optional context
            callback: Callback function(event_type, data) for streaming updates

        Returns:
            Final execution result
        """
        def emit(event_type: str, data: Any):
            if callback:
                callback(event_type, data)

        emit("start", {"request": user_request})

        # Run execution with callbacks
        # (This could be enhanced to emit events during planning/execution)
        result = self.execute(user_request, context)

        emit("complete", result)
        return result


if __name__ == "__main__":
    # Simple test
    import yaml

    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Create orchestrator
    orchestrator = MainOrchestrator(config)

    # Test with file organization
    result = orchestrator.execute("Organize all my music notes to a single folder called music stuff")

    print("\n" + "=" * 80)
    print("FINAL RESULT")
    print("=" * 80)
    print(f"Status: {result['status']}")
    print(f"Attempts: {result.get('attempts', 1)}")

    if result.get('step_results'):
        print("\nStep Results:")
        for step_id, step_result in result['step_results'].items():
            print(f"\nStep {step_id}:")
            for key, value in step_result.items():
                if key == 'reasoning' and isinstance(value, dict):
                    print(f"  {key}: {len(value)} file decisions")
                else:
                    print(f"  {key}: {value}")
