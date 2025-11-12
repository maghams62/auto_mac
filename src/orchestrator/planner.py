"""
Standalone Planner - responsible ONLY for creating execution plans.

Separation of Concerns:
- Planner: Creates plans based on user intent and available tools
- Orchestrator: Executes plans, manages state, handles retries and verification
"""

import json
import logging
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .tools_catalog import format_tool_catalog_for_prompt, build_tool_parameter_index
from ..agent.agent_registry import AgentRegistry
from .agent_capabilities import build_agent_capabilities
from .intent_planner import IntentPlanner
from .agent_router import AgentRouter
from ..utils import get_temperature_for_model


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
        self.llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.2),  # Lower temperature for structured planning
            api_key=openai_config.get("api_key")
        )
        self.agent_registry = AgentRegistry(config)
        self.intent_planner = IntentPlanner(config)
        self.agent_router = AgentRouter()
        self.agent_capabilities = build_agent_capabilities(self.agent_registry)
        self.tool_parameters = build_tool_parameter_index()

    def create_plan(
        self,
        goal: str,
        available_tools: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        previous_plan: Optional[List[Dict[str, Any]]] = None,
        feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an execution plan for the given goal.

        Args:
            goal: User's goal/request
            available_tools: List of available tool specifications
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

        try:
            router_metadata = self._prepare_hierarchy_metadata(goal, available_tools)
            filtered_tools = router_metadata.get("tool_catalog", available_tools)

            # Build the planning prompt
            prompt = self._build_planning_prompt(
                goal=goal,
                available_tools=filtered_tools,
                context=context,
                previous_plan=previous_plan,
                feedback=feedback,
                intent_metadata=router_metadata.get("intent")
            )

            # Get plan from LLM
            messages = [
                SystemMessage(content=self._get_system_prompt()),
                HumanMessage(content=prompt)
            ]

            response = self.llm.invoke(messages)
            response_text = response.content

            # Parse the plan
            plan_data = self._parse_plan_response(response_text)

            if plan_data:
                logger.info(f"Plan created with {len(plan_data['steps'])} steps")
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
                return {
                    "success": False,
                    "plan": [],
                    "reasoning": "",
                    "error": "Failed to parse plan from LLM response"
                }

        except Exception as e:
            logger.error(f"Error creating plan: {e}", exc_info=True)
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
- Example: organize_files creates folders AND moves files - don't add separate "create_folder" steps
- Example: create_keynote_with_images handles images - don't manually process images first
- Read the "strengths" and "limits" of each tool carefully
- When in doubt, prefer fewer steps with more capable tools

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
            "- For reminders summarization: use list_reminders → synthesize_content → reply_to_user workflow. Convert reminders data to JSON string before passing to synthesize_content. Extract time windows (e.g., 'next 3 days') using LLM reasoning - do NOT hardcode defaults.",
            "- For calendar summarization: use list_calendar_events → synthesize_content → reply_to_user workflow. Extract days_ahead from query (e.g., 'next week' → 7 days, 'this month' → 30 days) using LLM reasoning. Convert events data to JSON string before passing to synthesize_content.",
            "- For news summarization: use google_search (DuckDuckGo) → synthesize_content → reply_to_user workflow. For 'recent news' queries, use LLM reasoning to determine appropriate search query (e.g., 'recent tech news today') - do NOT hardcode generic queries like 'news' or 'trending'.",
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
            "- For stock price slideshow workflows (e.g., 'get NVIDIA stock price and create slideshow'):",
            "  * CRITICAL: Stock price data from get_stock_price is minimal (just price, change, ticker)",
            "  * ALWAYS include synthesize_content step between get_stock_price and create_slide_deck_content",
            "  * synthesize_content enriches stock data with context, trends, and market information",
            "  * This ensures slideshow has substantial content (3-5 slides) rather than just raw price data",
            "  * Workflow: get_stock_price → synthesize_content → create_slide_deck_content → create_keynote → compose_email",
            "- CRITICAL: When passing data to reply_to_user or compose_email, always use string fields:",
            "  * Use '\$stepN.synthesized_content' (string) NOT '\$stepN' (dict)",
            "  * Use '\$stepN.message' (string) NOT '\$stepN' (dict)",
            "  * If step result is dict/list, convert to JSON string or extract string field",
            "  * reply_to_user.message and reply_to_user.details must be strings",
            "  * compose_email.body must be a string",
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

    def _prepare_hierarchy_metadata(
        self,
        goal: str,
        available_tools: List[Any]
    ) -> Dict[str, Any]:
        """Run Level 1 and Level 2 stages and provide routing metadata."""

        try:
            intent = self.intent_planner.analyze(goal, self.agent_capabilities)
            logger.debug(f"[PLANNER] Intent planner result: {intent}")

            # OPTIMIZATION: Only initialize agents that are actually needed
            # This prevents loading all 16 agents for every request
            involved_agents = intent.get("involved_agents", [])
            if involved_agents:
                logger.info(f"[PLANNER] Initializing only required agents: {involved_agents}")
                self.agent_registry.initialize_agents(involved_agents)
            else:
                logger.warning(f"[PLANNER] No specific agents identified by intent planner. Intent: {intent}")

            routing = self.agent_router.route(intent, available_tools, self.agent_registry)
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

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }
