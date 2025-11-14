"""
Standalone Planner - responsible ONLY for creating execution plans.

Separation of Concerns:
- Planner: Creates plans based on user intent and available tools
- Orchestrator: Executes plans, manages state, handles retries and verification
"""

import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .tools_catalog import format_tool_catalog_for_prompt, build_tool_parameter_index
from ..agent.agent_registry import AgentRegistry
from .agent_capabilities import build_agent_capabilities
from .intent_planner import IntentPlanner
from .agent_router import AgentRouter
from ..utils import get_temperature_for_model
from ..utils.openai_client import PooledOpenAIClient
from ..memory.session_memory import SessionContext
from ..utils.trajectory_logger import get_trajectory_logger
from ..utils.llm_wrapper import log_llm_call, extract_token_usage
import time


logger = logging.getLogger(__name__)


class Planner:
    """
    Pure planner - creates execution plans without execution logic.

    Responsibilities:
    - Analyze user request
    - Select appropriate tools
    - Create step-by-step execution plan
    - Consider tool capabilities and constraints

    NOT responsible for:
    - Executing steps
    - Managing state
    - Handling errors
    - Verification
    - Replanning (that's orchestrator's job)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the planner.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        openai_config = config.get("openai", {})
        
        # Initialize pooled OpenAI client for better performance (20-40% faster)
        pooled_client = PooledOpenAIClient.get_client(config)
        
        # Use global rate limiter singleton
        from src.utils.rate_limiter import get_rate_limiter
        self.rate_limiter = get_rate_limiter(config=config)
        logger.info("[PLANNER] Using global rate limiter")
        
        # Use pooled client with LangChain
        self.llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.2),  # Lower temperature for structured planning
            api_key=openai_config.get("api_key"),
            http_client=pooled_client._http_client if hasattr(pooled_client, '_http_client') else None
        )
        logger.info("[PLANNER] Using pooled OpenAI client for connection reuse")
        
        self.agent_registry = AgentRegistry(config)
        self.intent_planner = IntentPlanner(config)
        self.agent_router = AgentRouter(config)
        self.agent_capabilities = build_agent_capabilities(self.agent_registry)
        self.tool_parameters = build_tool_parameter_index()
        self.trajectory_logger = get_trajectory_logger(config)

    async def create_plan(
        self,
        goal: str,
        available_tools: List[Dict[str, Any]],
        session_context: SessionContext,
        context: Optional[Dict[str, Any]] = None,
        previous_plan: Optional[List[Dict[str, Any]]] = None,
        feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an execution plan for the given goal (async for performance).

        Args:
            goal: User's goal/request
            available_tools: List of available tool specifications
            session_context: SessionContext with original query and structured memory
            context: Additional context (previous results, user preferences, etc.)
            previous_plan: Previous plan if replanning
            feedback: Feedback on why previous plan failed (for replanning)

        Returns:
            Dictionary containing:
            {
                "success": bool,
                "plan": List[Dict],  # List of steps
                "reasoning": str,  # Why this plan was chosen
                "error": Optional[str]  # Error if planning failed
            }
        """
        logger.info(f"Creating plan for goal: '{goal}'")
        
        # Get session ID for trajectory logging
        session_id = getattr(session_context, 'session_id', None) or "unknown"
        interaction_id = getattr(session_context, 'interaction_id', None)

        try:
            # Acquire rate limit if enabled
            if self.rate_limiter:
                await self.rate_limiter.acquire(estimated_tokens=1000)
            
            router_metadata = await self._prepare_hierarchy_metadata(goal, available_tools)
            filtered_tools = router_metadata.get("tool_catalog", available_tools)
            
            # Log tool catalog filtering decision
            if router_metadata.get("intent"):
                self.trajectory_logger.log_trajectory(
                    session_id=session_id,
                    interaction_id=interaction_id,
                    phase="planning",
                    component="planner",
                    decision_type="tool_catalog_filtering",
                    input_data={
                        "goal": goal,
                        "total_tools": len(available_tools),
                        "intent": router_metadata.get("intent")
                    },
                    output_data={
                        "filtered_tools_count": len(filtered_tools),
                        "filtering_mode": router_metadata.get("mode", "full"),
                        "involved_agents": router_metadata.get("intent", {}).get("involved_agents", [])
                    },
                    reasoning=f"Filtered tool catalog based on intent: {router_metadata.get('intent', {}).get('intent', 'unknown')}",
                    success=True
                )

            # Build the planning prompt
            prompt = self._build_planning_prompt(
                goal=goal,
                available_tools=filtered_tools,
                session_context=session_context,
                context=context,
                previous_plan=previous_plan,
                feedback=feedback,
                intent_metadata=router_metadata.get("intent")
            )

            # Get plan from LLM (async)
            messages = [
                SystemMessage(content=self._get_system_prompt()),
                HumanMessage(content=prompt)
            ]
            
            # Log LLM call with timing
            llm_start_time = time.time()
            model_name = self.llm.model_name if hasattr(self.llm, 'model_name') else str(self.llm.model) if hasattr(self.llm, 'model') else "unknown"

            response = await self.llm.ainvoke(messages)
            response_text = response.content
            llm_latency_ms = (time.time() - llm_start_time) * 1000
            
            # Extract token usage
            tokens_used = extract_token_usage(response)
            
            # Record actual token usage
            if self.rate_limiter and tokens_used:
                total_tokens = tokens_used.get('total', 0)
                if total_tokens:
                    self.rate_limiter.record_usage(total_tokens)

            # Log LLM call
            log_llm_call(
                model=model_name,
                prompt=prompt[:2000] + "..." if len(prompt) > 2000 else prompt,  # Truncate for logging
                response=response_text[:2000] + "..." if len(response_text) > 2000 else response_text,
                latency_ms=llm_latency_ms,
                success=True,
                session_id=session_id,
                interaction_id=interaction_id,
                component="planner",
                decision_type="plan_creation"
            )

            # Parse the plan
            plan_data = self._parse_plan_response(response_text)

            if plan_data:
                logger.info(f"Plan created with {len(plan_data['steps'])} steps")
                
                # Log plan creation trajectory
                self.trajectory_logger.log_trajectory(
                    session_id=session_id,
                    interaction_id=interaction_id,
                    phase="planning",
                    component="planner",
                    decision_type="plan_creation",
                    input_data={
                        "goal": goal,
                        "available_tools_count": len(filtered_tools),
                        "previous_plan": previous_plan is not None,
                        "has_feedback": feedback is not None,
                        "prompt_length": len(prompt)
                    },
                    output_data={
                        "plan_steps_count": len(plan_data['steps']),
                        "plan_steps": [{"id": s.get("id"), "action": s.get("action")} for s in plan_data['steps']],
                        "reasoning": plan_data.get('reasoning', '')
                    },
                    reasoning=plan_data.get('reasoning', 'Plan created successfully'),
                    model_used=model_name,
                    tokens_used=tokens_used,
                    latency_ms=llm_latency_ms,
                    success=True
                )
                
                result_payload = {
                    "success": True,
                    "plan": plan_data['steps'],
                    "reasoning": plan_data.get('reasoning', 'Plan created successfully'),
                    "error": None
                }
                if router_metadata.get("intent"):
                    result_payload["intent_metadata"] = router_metadata["intent"]
                return result_payload
            else:
                logger.error("Failed to parse plan from LLM response")
                
                # Log parsing failure
                self.trajectory_logger.log_trajectory(
                    session_id=session_id,
                    interaction_id=interaction_id,
                    phase="planning",
                    component="planner",
                    decision_type="plan_parsing",
                    input_data={
                        "goal": goal,
                        "response_preview": response_text[:500] if response_text else None
                    },
                    output_data={},
                    reasoning="Failed to parse plan from LLM response",
                    model_used=model_name,
                    tokens_used=tokens_used,
                    latency_ms=llm_latency_ms,
                    success=False,
                    error={
                        "type": "ParseError",
                        "message": "Failed to parse plan from LLM response"
                    }
                )
                
                return {
                    "success": False,
                    "plan": [],
                    "reasoning": "",
                    "error": "Failed to parse plan from LLM response"
                }

        except Exception as e:
            logger.error(f"Error creating plan: {e}", exc_info=True)
            
            # Log error trajectory
            self.trajectory_logger.log_trajectory(
                session_id=session_id,
                interaction_id=interaction_id,
                phase="planning",
                component="planner",
                decision_type="plan_creation",
                input_data={
                    "goal": goal,
                    "available_tools_count": len(available_tools) if available_tools else 0
                },
                output_data={},
                reasoning=f"Error during plan creation: {str(e)}",
                success=False,
                error={
                    "type": type(e).__name__,
                    "message": str(e)
                }
            )
            
            return {
                "success": False,
                "plan": [],
                "reasoning": "",
                "error": str(e)
            }

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the planner."""
        return """You are an expert task planner. Your job is to create step-by-step execution plans.

CORE PRINCIPLES:
1. **LLM-Driven Decisions**: ALL parameters MUST be extracted from the user's natural language query using LLM reasoning
   - NO hardcoded values or assumptions
   - Parse city names, stop counts, times, etc. from the query text
   - Handle variations: "LA" = "Los Angeles, CA", "2 gas stops" = num_fuel_stops=2, "lunch and dinner" = num_food_stops=2
   - Use your knowledge to interpret abbreviations and common phrases
2. **Tool Understanding**: Carefully read tool capabilities - some tools are COMPLETE and standalone
3. **Simplicity**: Prefer simple plans - if one tool can do everything, use just that tool
4. **Dependencies**: Clearly specify step dependencies
5. **Context Passing**: Use $stepN.field syntax to pass results between steps
6. **Selective File Workflows**: If the user requests zipping or emailing only certain kinds of files (e.g., "non music files", "only PDFs"), FIRST create the filtered collection using LLM reasoning (`organize_files` or similar). Only after that call `create_zip_archive`, passing the appropriate `include_extensions` or `exclude_extensions`, and attach the resulting ZIP with `compose_email` when email is requested. Never zip the whole folder when the user asked for a filtered subset.

CRITICAL RULES:
- If a tool description says "COMPLETE" or "STANDALONE", it handles everything - don't break it into sub-steps!
- Example: organize_files creates folders AND moves files - don't add separate "create_folder" steps (create_folder doesn't exist - see invalid_tools_reference.md)
- Example: create_keynote_with_images handles images - don't manually process images first
- Read the "strengths" and "limits" of each tool carefully
- When in doubt, prefer fewer steps with more capable tools
- NEVER invent tools - see prompts/examples/core/08_invalid_tools_reference.md for tools that DO NOT EXIST

OUTPUT FORMAT:
Respond with ONLY valid JSON (no comments, no markdown code blocks) containing:
{
  "reasoning": "Brief explanation of why this plan achieves the goal",
  "steps": [
    {
      "id": 1,
      "action": "tool_name",
      "parameters": {
        "param1": "value1",
        "param2": "$step0.output_field"
      },
      "reasoning": "Why this step is needed",
      "dependencies": [0]
    }
  ]
}

CRITICAL: Return pure JSON only. Do NOT include comments like "// comment". Do NOT wrap in markdown code blocks."""

    def _build_planning_prompt(
        self,
        goal: str,
        available_tools: List[Any],
        session_context: SessionContext,
        context: Optional[Dict[str, Any]] = None,
        previous_plan: Optional[List[Dict[str, Any]]] = None,
        feedback: Optional[str] = None,
        intent_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build the planning prompt."""

        # Format tool catalog
        tool_catalog_str = format_tool_catalog_for_prompt(available_tools)

        # Add file system context from config
        file_context = {}
        if self.config.get('documents', {}).get('folders'):
            file_context['user_document_folders'] = self.config['documents']['folders']
            file_context['note'] = "When working with user files (zip, search, organize), use these document folders"

        prompt_parts = [
            f"ORIGINAL USER QUERY: {session_context.original_query}",
            "",
            f"DERIVED TOPIC: {session_context.headline()}",
            "",
            "CONTEXT OBJECTS:",
            json.dumps(session_context.context_objects, indent=2),
            "",
            f"REASONING BUDGET: {session_context.token_budget_metadata}",
            "",
            f"GOAL: {goal}",
            "",
            "AVAILABLE TOOLS:",
            tool_catalog_str,
            ""
        ]

        if file_context:
            prompt_parts.extend([
                "FILE SYSTEM CONTEXT:",
                json.dumps(file_context, indent=2),
                ""
            ])

        if intent_metadata:
            prompt_parts.extend([
                "INTENT SUMMARY:",
                json.dumps(intent_metadata, indent=2),
                ""
            ])

        # Add context if provided
        if context:
            prompt_parts.extend([
                "CONTEXT:",
                json.dumps(context, indent=2),
                ""
            ])

        # Add previous plan and feedback if replanning
        if previous_plan and feedback:
            prompt_parts.extend([
                "PREVIOUS PLAN (that failed):",
                json.dumps(previous_plan, indent=2),
                "",
                "FEEDBACK ON WHY IT FAILED:",
                feedback,
                "",
                "Create a CORRECTED plan that addresses the issues.",
                ""
            ])

        prompt_parts.extend([
            "TASK: Create a step-by-step execution plan to achieve the goal.",
            "",
            "CRITICAL: Parameter Extraction - Use LLM Reasoning:",
            "- Extract ALL parameters from the user's natural language query",
            "- For trip planning: parse origin, destination, number of stops, departure time from the query",
            "- Handle variations: 'LA' → 'Los Angeles, CA', 'SD' → 'San Diego, CA', '2 gas stops' → num_fuel_stops=2",
            "- Interpret meal requests: 'lunch and dinner' → num_food_stops=2, 'breakfast and lunch' → num_food_stops=2",
            "- Parse time formats: '5 AM' → '5:00 AM', '7:30 PM' → '7:30 PM'",
            "- For Bluesky/social media time windows: extract lookback_hours from phrases like 'past one hour' → lookback_hours=1, 'last 2 hours' → lookback_hours=2, 'over the past hour' → lookback_hours=1",
            "- For Bluesky queries: when user asks 'what happened' or 'summarize activity', use LLM reasoning to determine appropriate search query (e.g., 'trending', 'news', or broad terms) - do NOT hardcode",
            "- For email time windows: extract hours/minutes from phrases like 'past 5 hours' → hours=5, 'last 2 hours' → hours=2, 'past 30 minutes' → minutes=30, 'over the past hour' → hours=1",
            "- For email summarization: when user requests time-based email summary, use read_emails_by_time followed by summarize_emails - always pass full output from read_emails_by_time to summarize_emails via emails_data parameter",
            "- For email focus: extract optional focus keywords like 'action items', 'deadlines', 'important' from user query and pass to summarize_emails focus parameter",
            "- **Listing Reminders Workflow**: For queries requesting to see/list reminders (e.g., 'pull up my reminders', 'show my reminders', 'what are my reminders'):",
            "  * **REQUIRED 3-step pattern**: list_reminders → synthesize_content → reply_to_user",
            "  * **CRITICAL**: You MUST include synthesize_content step between list_reminders and reply_to_user",
            "  * **CRITICAL**: NEVER skip synthesize_content - raw reminder data must be formatted before display",
            "  * Convert reminders data to JSON string: source_contents=['$step0.reminders']",
            "  * Extract time windows (e.g., 'next 3 days', 'today', 'this week') using LLM reasoning for list_reminders parameters",
            "  * Example: 'pull up my reminders for today' → Step 0: list_reminders(include_completed=False), Step 1: synthesize_content(source_contents=['$step0.reminders'], topic='Summary of reminders for today', synthesis_style='concise'), Step 2: reply_to_user(message='$step1.synthesized_content')",
            "  * **VALIDATION**: If plan contains list_reminders, it MUST be followed by synthesize_content before reply_to_user",
            "- **Creating Reminders Workflow**: For queries requesting to create/set reminders (e.g., 'remind me to call John', 'set a reminder'):",
            "  * **Pattern**: create_reminder → [optional: compose_email if user wants confirmation] → reply_to_user",
            "  * **No synthesize_content needed** - create_reminder returns simple confirmation",
            "  * Extract reminder details (title, due_time) from user query using LLM reasoning",
            "  * Example: 'remind me to call John tomorrow' → Step 0: create_reminder(title='Call John', due_time='tomorrow'), Step 1: reply_to_user(message='Reminder set: Call John (tomorrow)')",
            "- For calendar summarization: use list_calendar_events → synthesize_content → reply_to_user workflow. Extract days_ahead from query (e.g., 'next week' → 7 days, 'this month' → 30 days) using LLM reasoning. Convert events data to JSON string before passing to synthesize_content.",
            "- For news summarization: use google_search (DuckDuckGo ONLY, no Google) → synthesize_content → reply_to_user workflow. For 'recent news' queries, use LLM reasoning to determine appropriate search query (e.g., 'recent tech news today') - do NOT hardcode generic queries like 'news' or 'trending'.",
            "- For selective ZIP requests: Use LLM reasoning to determine include_pattern from user query",
            "  * Example: 'Ed Sheeran files' → Reason: filenames contain 'Ed' and 'Sheeran' → include_pattern='*Ed*Sheeran*'",
            "  * Example: 'files starting with A' → Reason: filenames start with 'A' → include_pattern='A*'",
            "  * Example: 'only PDFs' → Reason: PDFs have .pdf extension → include_extensions=['pdf']",
            "  * NO hardcoded patterns - always reason about what the user means!",
            "- For file operations (zip, organize, search): ALWAYS specify source_path using the user_document_folders from FILE SYSTEM CONTEXT",
            "- Example: if user says 'zip files starting with A', set source_path to the first folder from user_document_folders",
            "- NO hardcoded values - extract everything from the user's query using reasoning",
            "",
            "CRITICAL: synthesize_content Parameter Handling:",
            "- synthesize_content.source_contents MUST be a List[str] (list of strings), NOT raw structured data",
            "- When passing data from previous steps to synthesize_content, convert structured data (lists/dicts) to JSON strings",
            "- Example: If step1 returns {events: [...]}, use json.dumps($step1.events) or convert to string representation",
            "- If a data retrieval step returns empty results (empty list/dict), use LLM reasoning to decide:",
            "  * Skip synthesis if truly empty and provide informative empty-state message directly",
            "  * OR convert empty result to descriptive string like 'No items found' for synthesis",
            "- For 'reminders' or 'todos' queries, use BOTH list_reminders AND list_calendar_events, then synthesize both results",
            "- For stock price slideshow/report workflows: Use `hybrid_stock_brief` as the default entry point (see task_decomposition.md section 'Stock Data/Analysis' for detailed decision tree). The hybrid tool internally uses stock tools and provides confidence-based fallback. Check `confidence_level` from output: high → proceed directly to synthesis, medium/low → add google_search with normalized period and date.",
            "- CRITICAL: When passing data to reply_to_user or compose_email, always use string fields:",
            "  * Use '\$stepN.synthesized_content' (string) NOT '\$stepN' (dict)",
            "  * Use '\$stepN.message' (string) NOT '\$stepN' (dict)",
            "  * If step result is dict/list, convert to JSON string or extract string field",
            "  * reply_to_user.message and reply_to_user.details must be strings",
            "  * compose_email.body must be a string",
            "- **CRITICAL - Day Overview Formatting**: For day overview queries (e.g., 'how's my day', 'what's on my schedule'):",
            "  * Use generate_day_overview(filters='today') to get comprehensive overview",
            "  * The overview returns a structured object with 'summary' field containing formatted text like 'Your today includes: X meetings, Y reminders, Z email actions'",
            "  * **DO NOT duplicate the summary**: Use reply_to_user(message='$step0.summary') - the summary field already contains the complete formatted message",
            "  * **DO NOT** put the summary in both message and details fields - this causes duplication",
            "  * If you need additional details, use the 'sections' field from the overview for structured data, but keep the summary in message only",
            "  * Example: reply_to_user(message='$step0.summary') - this is sufficient, do not add details with the same summary text",
            "- For rich UI feedback, use reply_to_user with completion_event parameters:",
            "  * After compose_email (send=true): use action_type='email_sent', include recipient in artifact_metadata",
            "  * After create_stock_report/create_local_document_report: use action_type='report_created', include report_path in artifacts",
            "  * After create_keynote/create_keynote_with_images: use action_type='presentation_created', include keynote_path in artifacts",
            "  * Use get_message_for_action(action_type) from message_personality for fun celebratory messages",
            "",
            "Remember:",
            "- Use LLM reasoning for all decisions and parameter extraction",
            "- For file operations, ALWAYS check FILE SYSTEM CONTEXT for the correct folder paths",
            "- Check if tools are COMPLETE/STANDALONE before breaking into sub-steps",
            "- Keep plans as simple as possible",
            "- Specify dependencies clearly",
            "- Handle empty results intelligently - don't pass empty lists directly to synthesize_content",
            "",
            "Respond with the plan in JSON format."
        ])

        return "\n".join(prompt_parts)

    async def _prepare_hierarchy_metadata(
        self,
        goal: str,
        available_tools: List[Any]
    ) -> Dict[str, Any]:
        """Run Level 1 and Level 2 stages and provide routing metadata (async)."""

        try:
            # Get session ID for intent planner
            session_id = getattr(session_context, 'session_id', None) if 'session_context' in locals() else None
            interaction_id = getattr(session_context, 'interaction_id', None) if 'session_context' in locals() else None
            
            intent = await self.intent_planner.analyze(goal, self.agent_capabilities, session_id=session_id, interaction_id=interaction_id)
            logger.debug(f"[PLANNER] Intent planner result: {intent}")

            # OPTIMIZATION: Only initialize agents that are actually needed
            # This prevents loading all 16 agents for every request
            involved_agents = intent.get("involved_agents", [])
            if involved_agents:
                logger.info(f"[PLANNER] Initializing only required agents: {involved_agents}")
                self.agent_registry.initialize_agents(involved_agents)
            else:
                logger.warning(f"[PLANNER] No specific agents identified by intent planner. Intent: {intent}")

            routing = self.agent_router.route(intent, available_tools, self.agent_registry, session_id=session_id, interaction_id=interaction_id)
            routing.setdefault("tool_catalog", available_tools)
            return routing
        except Exception as exc:
            logger.warning("[PLANNER] Intent planning failed, using fallback: %s", exc)
            return {
                "tool_catalog": available_tools,
                "intent": None
            }

    def _parse_plan_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse plan from LLM response.

        Args:
            response_text: Raw LLM response

        Returns:
            Dictionary with 'steps' and optionally 'reasoning', or None if parsing fails
        """
        try:
            # Try to find JSON object in response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                plan_data = json.loads(json_str)

                # Validate structure
                if "steps" in plan_data and isinstance(plan_data["steps"], list):
                    return plan_data

                # If no "steps" key, maybe it's a direct array
                if isinstance(plan_data, dict) and len(plan_data) > 0:
                    # Try to find steps as direct list
                    for key in plan_data:
                        if isinstance(plan_data[key], list):
                            return {"steps": plan_data[key], "reasoning": ""}

            # Try to find just an array
            array_start = response_text.find("[")
            array_end = response_text.rfind("]") + 1

            if array_start >= 0 and array_end > array_start:
                array_str = response_text[array_start:array_end]
                steps = json.loads(array_str)
                if isinstance(steps, list):
                    return {"steps": steps, "reasoning": ""}

            logger.error("Could not find valid plan structure in response")
            return None

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Response: {response_text[:500]}")
            return None

    def validate_plan(
        self,
        plan: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate a plan before execution.

        Args:
            plan: List of plan steps
            available_tools: List of available tool specifications

        Returns:
            Dictionary with validation results:
            {
                "valid": bool,
                "issues": List[str],
                "warnings": List[str]
            }
        """
        issues = []
        warnings = []

        # Get available tool names
        tool_names = {tool["name"] for tool in available_tools}

        # Check each step
        for i, step in enumerate(plan):
            step_id = step.get("id", i)
            action = step.get("action")

            # Check if action exists
            if not action:
                issues.append(f"Step {step_id}: Missing 'action' field")
                continue

            # Check if tool exists
            if action not in tool_names:
                issues.append(f"Step {step_id}: Tool '{action}' not available")

            # Check parameters
            parameters = step.get("parameters")
            if parameters is None:
                warnings.append(f"Step {step_id}: No parameters specified")
                parameters = {}
            elif not isinstance(parameters, dict):
                issues.append(f"Step {step_id}: Parameters must be an object/dict, got {type(parameters).__name__}")
                continue

            # Check required parameters against schema
            param_meta = self.tool_parameters.get(action, {})
            required_params = param_meta.get("required") or []
            optional_params = param_meta.get("optional") or []
            declared_params = set(parameters.keys())

            missing_required = [param for param in required_params if param not in declared_params]
            if missing_required:
                issues.append(
                    f"Step {step_id}: Missing required parameters for '{action}': {', '.join(sorted(missing_required))}"
                )

            # Warn about unknown parameters (may indicate typo)
            allowed_params = set(required_params) | set(optional_params)
            if allowed_params and declared_params - allowed_params:
                unknown = ", ".join(sorted(declared_params - allowed_params))
                warnings.append(
                    f"Step {step_id}: Unknown parameters for '{action}': {unknown}"
                )

            # Check dependencies
            dependencies = step.get("dependencies", [])
            for dep_id in dependencies:
                if dep_id >= step_id:
                    issues.append(f"Step {step_id}: Invalid dependency on step {dep_id} (must depend on earlier steps)")

        # CRITICAL: Validate reminders workflow pattern
        # If plan contains list_reminders, it MUST be followed by synthesize_content before reply_to_user
        list_reminders_indices = [i for i, step in enumerate(plan) if step.get("action") == "list_reminders"]
        if list_reminders_indices:
            for list_idx in list_reminders_indices:
                # Find the next step after list_reminders
                next_steps = [step for i, step in enumerate(plan) if i > list_idx]
                if not next_steps:
                    issues.append(
                        f"Step {plan[list_idx].get('id', list_idx)}: list_reminders must be followed by synthesize_content before reply_to_user"
                    )
                    continue
                
                # Check if synthesize_content appears before reply_to_user
                found_synthesize = False
                found_reply = False
                synthesize_idx = None
                
                for i, step in enumerate(next_steps, start=list_idx + 1):
                    action = step.get("action")
                    if action == "synthesize_content":
                        found_synthesize = True
                        synthesize_idx = i
                    elif action == "reply_to_user":
                        found_reply = True
                        if not found_synthesize:
                            issues.append(
                                f"Step {plan[list_idx].get('id', list_idx)}: list_reminders must be followed by synthesize_content before reply_to_user. "
                                f"Found reply_to_user at step {plan[i].get('id', i)} without synthesize_content in between."
                            )
                        break
                
                if found_synthesize and not found_reply:
                    warnings.append(
                        f"Step {plan[list_idx].get('id', list_idx)}: list_reminders followed by synthesize_content, but no reply_to_user found. "
                        f"Plan should end with reply_to_user to display results."
                    )

        # CRITICAL: Validate stock slideshow workflows
        # Check if plan contains stock-related actions (get_stock_history, get_stock_price, capture_stock_chart)
        # AND also contains slideshow actions (create_slide_deck_content, create_keynote)
        stock_tools = ["get_stock_history", "get_stock_price", "capture_stock_chart", "search_stock_symbol"]
        slideshow_tools = ["create_slide_deck_content", "create_keynote"]
        has_stock_tool = any(step.get("action") in stock_tools for step in plan)
        has_slideshow_tool = any(step.get("action") in slideshow_tools for step in plan)
        
        if has_stock_tool and has_slideshow_tool:
            # This is a stock slideshow workflow - must use DuckDuckGo, not stock tools
            issues.append(
                "Stock slideshow workflows must use google_search (DuckDuckGo) instead of stock tools "
                "(get_stock_history, get_stock_price, capture_stock_chart). "
                "Workflow: google_search → synthesize_content → create_slide_deck_content → create_keynote → compose_email → reply_to_user"
            )
        
        # CRITICAL: Validate that plans always end with reply_to_user
        if plan and plan[-1].get("action") != "reply_to_user":
            # Check if this is a workflow that should have a reply (has compose_email, create_keynote, etc.)
            final_actions = ["compose_email", "create_keynote", "create_pages_doc", "create_keynote_with_images"]
            has_final_action = any(step.get("action") in final_actions for step in plan)
            if has_final_action:
                issues.append(
                    f"Plan must end with reply_to_user as the final step. "
                    f"Current final step: {plan[-1].get('action')}"
                )
            else:
                warnings.append(
                    f"Plan should end with reply_to_user to confirm completion. "
                    f"Current final step: {plan[-1].get('action')}"
                )

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }
