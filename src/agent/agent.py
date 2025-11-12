"""
LangGraph agent with task decomposition and state management.
"""

from typing import TypedDict, Annotated, List, Dict, Any, Optional
from threading import Event
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import json
import logging
from pathlib import Path

from . import ALL_AGENT_TOOLS
from .feasibility_checker import FeasibilityChecker
from .verifier import OutputVerifier
from ..memory import SessionManager
from ..utils.message_personality import get_generic_success_message

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State for the automation agent."""
    # Input
    user_request: str
    original_user_request: Optional[str]  # Preserved original request for delivery intent detection

    # Planning
    goal: str
    steps: List[Dict[str, Any]]
    current_step: int
    planning_context: Optional[Dict[str, Any]]  # Context for planning (e.g., intent_hints from slash commands)

    # Execution
    step_results: Dict[int, Any]  # step_id -> result
    verification_results: Dict[int, Any]  # step_id -> verification result
    messages: Annotated[List[Any], add_messages]  # Conversation history with add_messages reducer

    # Session context (NEW)
    session_id: Optional[str]
    session_context: Optional[Dict[str, Any]]
    tool_attempts: Dict[str, int]
    vision_usage: Dict[str, Any]
    recent_errors: Dict[str, List[str]]

    # Output
    final_result: Optional[Dict[str, Any]]
    status: str  # "planning" | "executing" | "completed" | "error"
    cancel_event: Optional[Event]
    cancelled: bool
    cancellation_reason: Optional[str]
    on_plan_created: Optional[callable]  # Callback for plan events (per-request, avoids cross-talk)
    
    # Reasoning trace instrumentation
    memory: Optional[Any]  # SessionMemory instance for trace instrumentation
    interaction_id: Optional[str]  # Current interaction ID for trace


class AutomationAgent:
    """
    LangGraph agent for task decomposition and execution.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        session_manager: Optional[SessionManager] = None,
        on_plan_created: Optional[callable] = None
    ):
        self.config = config
        # Note: on_plan_created is deprecated - pass through run() method instead to avoid cross-talk
        self.on_plan_created = on_plan_created  # Callback for sending plan to UI (deprecated)
        
        # Initialize config accessor for safe, validated access
        from ..config_validator import ConfigAccessor
        self.config_accessor = ConfigAccessor(config)

        # Vision / feasibility configuration
        self.vision_config = self.config_accessor.get_vision_config()
        self.feasibility_checker = FeasibilityChecker(self.vision_config)
        
        # Get OpenAI config through accessor (validates API key exists)
        openai_config = self.config_accessor.get_openai_config()
        # Handle both dict and OpenAISettings dataclass
        if hasattr(openai_config, 'model'):
            # It's an OpenAISettings dataclass
            model = openai_config.model
            api_key = openai_config.api_key
            temperature = openai_config.temperature if hasattr(openai_config, 'temperature') else 0.7
        else:
            # It's a dict (backward compatibility)
            model = openai_config["model"]
            api_key = openai_config["api_key"]
            temperature = openai_config.get("temperature", 0.7)

        # o-series models (o1, o3, o4) only support temperature=1
        if model and model.startswith(("o1", "o3", "o4")):
            temperature = 1
            logger.info(f"[AUTOMATION AGENT] Using temperature=1 for o-series model: {model}")

        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=api_key
        )

        # Session management
        self.session_manager = session_manager
        if self.session_manager:
            logger.info("[AUTOMATION AGENT] Session management enabled")

        # Initialize verifier
        self.verifier = OutputVerifier(config)

        # Load prompts
        self.prompts = self._load_prompts()

        # Build graph
        self.graph = self._build_graph()

    def _load_prompts(self) -> Dict[str, str]:
        """
        Load prompt templates from markdown files.

        Core prompts (system, task_decomposition) are loaded directly.
        Few-shot examples are loaded via PromptRepository for modular, agent-scoped loading.
        """
        prompts_dir = Path(__file__).parent.parent.parent / "prompts"

        prompts = {}
        # Load core prompts directly
        for prompt_file in ["system.md", "task_decomposition.md", "delivery_intent.md"]:
            path = prompts_dir / prompt_file
            if path.exists():
                prompts[prompt_file.replace(".md", "")] = path.read_text()
            else:
                # delivery_intent.md is optional (has fallback), others are critical
                if prompt_file != "delivery_intent.md":
                    logger.warning(f"Prompt file not found: {path}")

        # Load few-shot examples via PromptRepository (modular, agent-scoped)
        # For the automation agent (main planner), load "automation" agent examples
        try:
            from src.prompt_repository import PromptRepository
            repo = PromptRepository()
            few_shot_content = repo.to_prompt_block("automation")
            prompts["few_shot_examples"] = few_shot_content
            logger.info(f"[PROMPT LOADING] Loaded agent-scoped examples for 'automation' agent via PromptRepository")
        except Exception as exc:
            logger.warning(f"Failed to load few-shot examples via PromptRepository: {exc}")
            # Fallback to monolithic file if PromptRepository fails
            fallback_path = prompts_dir / "few_shot_examples.md"
            if fallback_path.exists():
                prompts["few_shot_examples"] = fallback_path.read_text()
                logger.info("[PROMPT LOADING] Fell back to monolithic few_shot_examples.md")

        return prompts

    def _load_atomic_examples_for_request(self, user_request: str) -> str:
        """
        Load atomic few-shot examples based on the user request characteristics.

        This replaces the monolithic few_shot_examples loading with task-specific
        examples to reduce context window usage and improve reasoning quality.
        """
        atomic_config = self.config.get("atomic_prompts", {})
        if not atomic_config.get("enabled", True):
            return self.prompts.get("few_shot_examples", "")

        try:
            from src.prompt_repository import PromptRepository
            repo = PromptRepository()

            # Extract task characteristics from the user request
            task_characteristics = self._extract_task_characteristics(user_request)

            # Load atomic examples with token budget
            max_tokens = atomic_config.get("max_tokens", 2000)
            atomic_examples = repo.load_atomic_examples(
                task_characteristics,
                max_tokens=max_tokens
            )

            if atomic_examples:
                token_count = repo._estimate_tokens(atomic_examples)
                if atomic_config.get("log_usage", True):
                    logger.info(
                        f"[ATOMIC PROMPTS] Loaded {token_count}/{max_tokens} tokens "
                        f"for task: {task_characteristics}"
                    )
                return atomic_examples

        except Exception as exc:
            logger.warning(f"Failed to load atomic examples: {exc}")

        # Fallback behavior
        if atomic_config.get("fallback_to_full", True):
            logger.info("[ATOMIC PROMPTS] Falling back to pre-loaded examples")
            return self.prompts.get("few_shot_examples", "")
        else:
            logger.info("[ATOMIC PROMPTS] Returning empty examples (no fallback)")
            return ""

    def _extract_task_characteristics(self, user_request: str) -> Dict[str, str]:
        """
        Extract task characteristics from a user request for atomic prompt loading.

        Returns a dictionary with keys like 'task_type', 'domain', 'complexity'.
        """
        request_lower = user_request.lower()

        characteristics = {}

        # Determine task type based on keywords and patterns
        if any(word in request_lower for word in ['email', 'mail', 'send', 'compose']):
            characteristics['domain'] = 'email'
            if 'summarize' in request_lower or 'summary' in request_lower:
                characteristics['task_type'] = 'email_summarization'
            elif 'read' in request_lower or 'latest' in request_lower:
                characteristics['task_type'] = 'email_reading'
            else:
                characteristics['task_type'] = 'email_composition'

        elif any(word in request_lower for word in ['stock', 'price', 'market', 'ticker']):
            characteristics['domain'] = 'stocks'
            characteristics['task_type'] = 'stock_analysis'

        elif any(word in request_lower for word in ['file', 'document', 'pdf', 'zip', 'folder']):
            characteristics['domain'] = 'file'
            if 'zip' in request_lower or 'archive' in request_lower:
                characteristics['task_type'] = 'file_archiving'
            elif 'search' in request_lower or 'find' in request_lower:
                characteristics['task_type'] = 'file_search'

        elif any(word in request_lower for word in ['map', 'directions', 'route', 'trip']):
            characteristics['domain'] = 'maps'
            characteristics['task_type'] = 'trip_planning'

        elif any(word in request_lower for word in ['presentation', 'slide', 'keynote', 'deck']):
            characteristics['domain'] = 'writing'
            characteristics['task_type'] = 'presentation_creation'

        elif any(word in request_lower for word in ['screenshot', 'screen', 'capture']):
            characteristics['domain'] = 'screen'
            characteristics['task_type'] = 'screen_capture'

        elif any(word in request_lower for word in ['weather', 'temperature', 'forecast']):
            characteristics['domain'] = 'weather'
            characteristics['task_type'] = 'weather_query'

        elif any(word in request_lower for word in ['search', 'find', 'lookup', 'research']):
            characteristics['domain'] = 'web'
            characteristics['task_type'] = 'web_search'

        elif any(word in request_lower for word in ['download', 'extract', 'scrape', 'crawl']):
            characteristics['domain'] = 'web'
            characteristics['task_type'] = 'web_scraping'

        elif any(word in request_lower for word in ['error', 'fail', 'problem', 'issue']):
            characteristics['domain'] = 'safety'
            characteristics['task_type'] = 'error_handling'

        # Estimate complexity (this could be enhanced with more sophisticated analysis)
        if len(user_request.split()) > 20 or any(word in request_lower for word in ['complex', 'multiple', 'advanced']):
            characteristics['complexity'] = 'complex'
        else:
            characteristics['complexity'] = 'simple'

        return characteristics

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("plan", self.plan_task)
        workflow.add_node("execute_step", self.execute_step)
        workflow.add_node("finalize", self.finalize)

        # Add edges
        workflow.set_entry_point("plan")

        # Conditional edge after planning: check if plan failed
        workflow.add_conditional_edges(
            "plan",
            lambda state: "finalize" if state.get("status") in {"error", "cancelled"} else "execute",
            {
                "execute": "execute_step",
                "finalize": "finalize"
            }
        )

        # Conditional edge: continue executing or finalize
        workflow.add_conditional_edges(
            "execute_step",
            self._should_continue,
            {
                "continue": "execute_step",
                "finalize": "finalize"
            }
        )

        workflow.add_edge("finalize", END)

        return workflow.compile()

    def plan_task(self, state: AgentState) -> AgentState:
        """
        Planning node: Decompose user request into steps.
        """
        if self._handle_cancellation(state, "planning"):
            return state
        
        # Safety check: reject /clear commands (should be handled by WebSocket handler)
        user_request_lowercase_only = state.get('user_request', '').strip().lower()
        if user_request_lowercase_only == '/clear' or user_request_lowercase_only == 'clear':
            logger.warning("Received /clear command in agent - this should be handled by WebSocket handler")
            state["status"] = "error"
            state["final_result"] = {
                "error": True,
                "message": "/clear command should be handled by the WebSocket handler, not the agent. Please use /clear directly.",
                "missing_capabilities": None
            }
            return state
        
        logger.info("=== PLANNING PHASE ===")
        full_user_request = state.get("user_request", "")
        logger.info(f"User request: {full_user_request}")
        state["original_user_request"] = full_user_request

        # Build planning prompt
        system_prompt = self.prompts.get("system", "")
        task_decomp_prompt = self.prompts.get("task_decomposition", "")

        # Load atomic few-shot examples based on user request
        few_shot_examples = self._load_atomic_examples_for_request(full_user_request)
        user_request_lower = full_user_request.lower()

        # Delivery intent detection - load from config instead of hardcoding
        # EXCLUDE slash command prefixes and noun usage (e.g., "/email summarize" or "my emails" should not trigger delivery intent)
        delivery_config = self.config.get("delivery", {})
        delivery_verbs = delivery_config.get("intent_verbs", ["email", "send", "mail", "attach"])
        
        # Check if this is a slash command (starts with /)
        is_slash_command = user_request_lower.strip().startswith('/')
        
        # For slash commands, check if delivery verb appears AFTER the command prefix
        # e.g., "/email summarize" -> no delivery intent
        # e.g., "/email send summary" -> delivery intent
        if is_slash_command:
            # Extract the part after the slash command prefix
            parts = user_request_lower.strip().split(None, 1)
            if len(parts) > 1:
                # Check delivery verbs in the task part, not the command part
                task_part = parts[1]
                # Check for verb usage patterns (email it, email the, email me, send it, etc.)
                # NOT noun usage (emails, my emails, summarize emails, etc.)
                needs_email_delivery = False
                for verb in delivery_verbs:
                    # Look for verb patterns: "verb it", "verb the", "verb me", "verb to", "verb this", "verb that"
                    verb_patterns = [
                        f"{verb} it", f"{verb} the", f"{verb} me", f"{verb} to", 
                        f"{verb} this", f"{verb} that", f"{verb} them", f"{verb} us"
                    ]
                    if any(pattern in task_part for pattern in verb_patterns):
                        needs_email_delivery = True
                        break
            else:
                # Just "/email" or similar - no delivery intent
                needs_email_delivery = False
        else:
            # Regular request - check for verb usage patterns, not noun usage
            # Look for patterns like "email it", "send it", "mail the", etc.
            # NOT "my emails", "summarize emails", "last emails", etc.
            needs_email_delivery = False
            for verb in delivery_verbs:
                # Verb patterns that indicate delivery intent
                verb_patterns = [
                    f"{verb} it", f"{verb} the", f"{verb} me", f"{verb} to", 
                    f"{verb} this", f"{verb} that", f"{verb} them", f"{verb} us",
                    f"{verb} results", f"{verb} summary", f"{verb} report"
                ]
                if any(pattern in user_request_lower for pattern in verb_patterns):
                    needs_email_delivery = True
                    break

        # Load delivery guidance from prompt file instead of hardcoded string
        delivery_guidance = ""
        if needs_email_delivery:
            delivery_guidance = self.prompts.get("delivery_intent", "")
            if delivery_guidance:
                # Wrap in header to make it stand out
                delivery_guidance = f"\n{'='*60}\nDELIVERY INTENT DETECTED\n{'='*60}\n{delivery_guidance}\n{'='*60}\n"
            else:
                # Fallback if prompt file not loaded (backwards compatibility)
                logger.warning("[PLANNING] delivery_intent.md not found, using fallback guidance")
                delivery_guidance = """
DELIVERY REQUIREMENT (AUTO-DETECTED):
- The user explicitly asked to email or send the results.
- Your plan MUST include a `compose_email` step (before the final `reply_to_user` step).
- Reference outputs from earlier steps (e.g., `$stepN.summary`, `$stepN.file_path`, `$stepN.zip_path`) in the email body/attachments.
- Set `"send": true` and rely on the default recipient when the user does not specify one.
- The final `reply_to_user` step must confirm that the email was sent and summarize what was delivered.
"""
        
        # Inject user context from config (constrains LLM to only use configured data)
        user_context = self.config_accessor.get_user_context_for_llm()

        # CRITICAL: Dynamically generate tool list from actual registered tools
        # This prevents hallucination by ensuring LLM only knows about real tools
        # Generate rich tool descriptions with parameters for better planning
        tool_descriptions = []
        for i, tool in enumerate(ALL_AGENT_TOOLS):
            # Get tool schema to extract parameters
            schema = tool.args_schema.schema() if hasattr(tool, 'args_schema') and tool.args_schema else {}
            properties = schema.get('properties', {})
            required_params = schema.get('required', [])

            # Build parameter info
            param_info = []
            for param_name, param_spec in properties.items():
                is_required = param_name in required_params
                param_type = param_spec.get('type', 'any')
                param_desc = param_spec.get('description', '')
                param_marker = "REQUIRED" if is_required else "optional"
                param_info.append(f"    - {param_name} ({param_marker}, {param_type}): {param_desc}")

            # Format tool entry
            tool_entry = f"{i+1}. **{tool.name}**\n   Description: {tool.description}"
            if param_info:
                tool_entry += "\n   Parameters:\n" + "\n".join(param_info)

            tool_descriptions.append(tool_entry)

        available_tools_list = "\n\n".join(tool_descriptions)
        logger.info(f"Planning with {len(ALL_AGENT_TOOLS)} available tools")

        planning_prompt = f"""
{system_prompt}

{task_decomp_prompt}

{user_context}

{delivery_guidance}

AVAILABLE TOOLS (COMPLETE LIST - DO NOT HALLUCINATE OTHER TOOLS):
{available_tools_list}

{few_shot_examples}

{self._get_trace_summary_for_prompt(state.get("session_id"))}

User Request: "{full_user_request}"

CRITICAL REQUIREMENTS:
1. **Tool Validation**: You may ONLY use tools from the list above. Any tool not listed does NOT exist.
2. **Capability Assessment**: Before creating a plan, verify you have the necessary tools to complete the request.
3. **Parameter Accuracy**: Use the exact parameter names and types specified in the tool definitions.
4. **No Hallucination**: Do not invent tools, parameters, or capabilities that don't exist.

PLANNING GUIDELINES:
- If the request involves taking screenshots AND creating a presentation, you MUST use "create_keynote_with_images" (NOT "create_keynote")
- "create_keynote_with_images" accepts "image_paths" parameter (list of screenshot paths)
- "create_keynote" is ONLY for text-based presentations
- IMPORTANT: If a step uses "$stepX.field" in parameters, you MUST list X in the "dependencies" array
- If a step depends on another step's output, list that step ID in "dependencies"
- After all work steps are complete, add a FINAL step that calls "reply_to_user" to deliver a polished summary referencing prior outputs

If you CANNOT complete the request with available tools, respond with:
{{
  "goal": "Unable to complete request",
  "steps": [],
  "complexity": "impossible",
  "reason": "Explanation of missing capabilities"
}}

Otherwise, decompose this request into executable steps using ONLY the available tools.
Respond with ONLY a JSON object in this format:

{{
  "goal": "high-level objective",
  "steps": [
    {{
      "id": 1,
      "action": "tool_name",
      "parameters": {{}},
      "dependencies": [],
      "reasoning": "why this step",
      "expected_output": "what this produces"
    }}
  ],
  "complexity": "simple | medium | complex"
}}

DEPENDENCIES EXAMPLE:
If step 3 uses "$step1.file_path" in parameters, then step 3's dependencies MUST include [1].
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=planning_prompt)
        ]

        response = self.llm.invoke(messages)
        response_text = response.content

        # Parse JSON response with robust retry logic
        try:
            from ..utils.json_parser import parse_json_with_retry, validate_json_structure
            
            # Use robust JSON parser with retry logic
            plan_dict, parse_error = parse_json_with_retry(
                response_text,
                max_retries=3,
                log_errors=True
            )
            
            if plan_dict is None:
                # JSON parsing failed after all retries
                logger.error(f"Failed to parse plan JSON: {parse_error}")
                logger.error(f"Response text (first 1000 chars): {response_text[:1000]}")
                state["status"] = "error"
                state["final_result"] = {
                    "error": True,
                    "message": f"Failed to create execution plan: {parse_error}"
                }
                return state
            
            # Validate JSON structure
            is_valid, validation_error = validate_json_structure(plan_dict, required_keys=["steps"])
            if not is_valid:
                logger.error(f"Plan structure validation failed: {validation_error}")
                logger.error(f"Parsed plan: {plan_dict}")
                state["status"] = "error"
                state["final_result"] = {
                    "error": True,
                    "message": f"Plan validation failed: {validation_error}"
                }
                return state
            
            plan = plan_dict

            plan_goal = plan.get("goal") or f"Handle user request: {full_user_request}"
            plan["goal"] = plan_goal

            plan_steps = plan.get("steps")
            if not isinstance(plan_steps, list):
                logger.error("[PLAN VALIDATION] Plan missing 'steps' array or has invalid format.")
                logger.error(f"[PLAN VALIDATION] Response text (first 500 chars): {response_text[:500]}")
                logger.error(f"[PLAN VALIDATION] Parsed plan: {plan}")
                state["status"] = "error"
                state["final_result"] = {
                    "error": True,
                    "message": "Plan validation failed: planner did not return a steps list."
                }
                return state

            logger.info(f"Plan created: {plan_goal}")
            logger.info(f"Steps: {len(plan_steps)}")

            # Check if LLM determined task is impossible
            if plan.get('complexity') == 'impossible':
                reason = plan.get('reason', 'Unknown reason')
                logger.warning(f"Task deemed impossible: {reason}")

                # GUARD: Check if this is a false negative for known supported workflows
                available_tools = {tool.name for tool in ALL_AGENT_TOOLS}

                # Check for common false negatives
                false_negative = False

                # 1. Duplicate detection + email (both tools exist)
                if ('duplicate' in user_request_lower and 'email' in user_request_lower):
                    if 'folder_find_duplicates' in available_tools and 'compose_email' in available_tools:
                        logger.warning(
                            "[GUARD] LLM incorrectly marked duplicate-email workflow as impossible. "
                            "Both folder_find_duplicates and compose_email are available!"
                        )
                        false_negative = True

                # 2. Duplicate detection + send (both tools exist)
                if ('duplicate' in user_request_lower and 'send' in user_request_lower):
                    if 'folder_find_duplicates' in available_tools and 'compose_email' in available_tools:
                        logger.warning(
                            "[GUARD] LLM incorrectly marked duplicate-send workflow as impossible. "
                            "Both folder_find_duplicates and compose_email are available!"
                        )
                        false_negative = True

                if false_negative:
                    # Don't return error, let the LLM try again with stronger prompt
                    logger.error(
                        "[GUARD] Forcing re-plan: LLM incorrectly determined supported workflow is impossible. "
                        "This is a prompt alignment issue that needs fixing."
                    )
                    # Fall through to the next validation - don't mark as error

                else:
                    # Legitimate impossible case
                    state["status"] = "error"
                    state["final_result"] = {
                        "error": True,
                        "message": f"Cannot complete request: {reason}",
                        "missing_capabilities": reason
                    }
                    return state

            # CRITICAL VALIDATION: Reject hallucinated tools
            valid_tool_names = {tool.name for tool in ALL_AGENT_TOOLS}
            invalid_tools = []
            for step in plan['steps']:
                tool_name = step.get('action')
                if tool_name not in valid_tool_names:
                    invalid_tools.append(tool_name)
                    logger.error(f"HALLUCINATED TOOL DETECTED: '{tool_name}' does not exist!")

            if invalid_tools:
                logger.error(f"Plan contains hallucinated tools: {invalid_tools}")
                logger.error(f"Valid tools are: {sorted(valid_tool_names)}")
                state["status"] = "error"
                state["final_result"] = {
                    "error": True,
                    "message": f"Plan validation failed: hallucinated tools {invalid_tools}. Valid tools: {sorted(valid_tool_names)}"
                }
                return state

            if needs_email_delivery:
                has_compose_email_step = any(
                    step.get("action") == "compose_email" for step in plan.get("steps", [])
                )
                if not has_compose_email_step:
                    logger.error(
                        "[DELIVERY GUARD] Plan missing required 'compose_email' step despite email/send intent. "
                        "Rejecting plan so planner can align with delivery requirement."
                    )
                    state["status"] = "error"
                    state["final_result"] = {
                        "error": True,
                        "message": (
                            "Plan validation failed: the request asked to email the results, but the generated plan omitted "
                            "the compose_email step. Re-run the request so the planner can include the delivery step."
                        )
                    }
                    return state

            # PLAN VALIDATION & AUTO-CORRECTION: Fix known bad patterns before execution
            plan = self._validate_and_fix_plan(plan, full_user_request)

            state["goal"] = plan["goal"]
            state["steps"] = plan["steps"]
            state["current_step"] = 0
            state["step_results"] = {}
            state["status"] = "executing"
            # Don't update messages directly - let add_messages reducer handle it
            # state["messages"] = messages + [response]

            # Add reasoning trace entry for planning phase
            memory = state.get("memory")
            if memory and memory.is_reasoning_trace_enabled():
                try:
                    from ..memory.reasoning_trace import detect_commitments_from_user_request
                    commitments = detect_commitments_from_user_request(full_user_request, self.config)
                    memory.add_reasoning_entry(
                        stage="planning",
                        thought=f"Created plan: {plan['goal']}",
                        evidence=[f"Steps: {len(plan.get('steps', []))}"],
                        commitments=commitments,
                        outcome="success"
                    )
                except Exception as e:
                    logger.debug(f"[REASONING TRACE] Failed to add planning entry: {e}")

            # Send plan to UI for disambiguation display (fire-and-forget)
            # Use callback from state (passed through run() method) if provided, otherwise fall back to instance callback (deprecated)
            callback = state.get("on_plan_created") or self.on_plan_created
            if callback and plan.get("steps"):
                try:
                    # Create a copy of plan data to avoid any threading issues
                    import copy
                    plan_copy = {
                        "goal": str(plan["goal"]),
                        "steps": copy.deepcopy(plan["steps"])
                    }
                    callback(plan_copy)
                except Exception as e:
                    logger.error(f"Failed to send plan to UI: {e}", exc_info=True)

        except Exception as e:
            # Catch any unexpected errors during parsing or validation
            logger.error(f"Unexpected error during plan parsing: {e}", exc_info=True)
            logger.error(f"Response text (first 1000 chars): {response_text[:1000]}")
            state["status"] = "error"
            state["final_result"] = {
                "error": True,
                "message": f"Failed to create execution plan: {str(e)}"
            }

        return state

    def execute_step(self, state: AgentState) -> AgentState:
        """
        Execution node: Execute current step.
        """
        if self._handle_cancellation(state, "execution"):
            return state
        current_idx = state["current_step"]
        steps = state.get("steps")

        # Handle case where plan has no steps (impossible task)
        if not steps or current_idx >= len(steps):
            state["status"] = "completed"
            return state

        step = steps[current_idx]
        logger.info(f"=== EXECUTING STEP {step['id']}: {step['action']} ===")
        logger.info(f"Reasoning: {step['reasoning']}")

        # Check if dependencies succeeded, with recovery attempt
        dependencies = step.get("dependencies", [])
        if dependencies:
            failed_deps = []
            recoverable_deps = []
            
            for dep_id in dependencies:
                if dep_id in state["step_results"]:
                    dep_result = state["step_results"][dep_id]
                    if dep_result.get("error", False):
                        failed_deps.append(dep_id)
                        
                        # Check if the dependency error is recoverable
                        # Look for error_analysis or retry_possible flag
                        error_analysis = dep_result.get("error_analysis")
                        retry_possible = dep_result.get("retry_possible", False)
                        
                        # If error analysis suggests recovery is possible, mark as recoverable
                        if error_analysis and error_analysis.get("is_recoverable", False):
                            recoverable_deps.append(dep_id)
                        elif retry_possible and not dep_result.get("skipped", False):
                            # If retry is possible and step wasn't skipped, might be recoverable
                            recoverable_deps.append(dep_id)
                else:
                    failed_deps.append(dep_id)

            if failed_deps:
                # If we have recoverable dependencies, attempt recovery
                if recoverable_deps:
                    logger.info(f"[DEPENDENCY RECOVERY] Step {step['id']} has recoverable dependencies: {recoverable_deps}")
                    
                    # Try to recover by using error analysis suggestions
                    recovery_attempted = False
                    for dep_id in recoverable_deps:
                        dep_result = state["step_results"][dep_id]
                        error_analysis = dep_result.get("error_analysis")
                        
                        if error_analysis:
                            alternative_approach = error_analysis.get("alternative_approach", "")
                            extracted_alternatives = error_analysis.get("extracted_alternatives", [])
                            
                            # If there are extracted alternatives (e.g., for Spotify), we might be able to proceed
                            # For now, log the recovery possibility but still skip if dependencies failed
                            # The actual recovery happens at the tool level (e.g., play_song tries alternatives)
                            logger.info(
                                f"[DEPENDENCY RECOVERY] Dependency {dep_id} has alternatives: {extracted_alternatives}. "
                                f"Alternative approach: {alternative_approach}"
                            )
                            
                            # If the current step can work with alternatives (e.g., reply_to_user can still inform user),
                            # we might proceed, but for now we'll be conservative and skip
                            # Future enhancement: check if step can proceed with partial/alternative results
                    
                    # For now, if dependencies failed, we skip (even if recoverable)
                    # The recovery happens at the tool level before the dependency check
                    logger.warning(f"Step {step['id']} skipped due to failed dependencies: {failed_deps}")
                    state["step_results"][step["id"]] = {
                        "error": True,
                        "skipped": True,
                        "message": f"Skipped due to failed dependencies: {failed_deps}",
                        "recoverable_dependencies": recoverable_deps,
                        "recovery_info": {
                            "alternatives_available": any(
                                state["step_results"].get(dep_id, {}).get("error_analysis", {}).get("extracted_alternatives", [])
                                for dep_id in recoverable_deps
                            )
                        }
                    }
                else:
                    # No recovery possible, skip normally
                    logger.warning(f"Step {step['id']} skipped due to failed dependencies: {failed_deps}")
                    state["step_results"][step["id"]] = {
                        "error": True,
                        "skipped": True,
                        "message": f"Skipped due to failed dependencies: {failed_deps}"
                    }
                
                state["current_step"] = current_idx + 1
                return state

        # Resolve parameters (handle context variables like $step1.doc_path)
        action = step.get("action", "")
        resolved_params = self._resolve_parameters(step["parameters"], state["step_results"], action)
        logger.info(f"Resolved parameters: {resolved_params}")

        # Get tool
        tool_name = step["action"]
        tool_attempts = state.setdefault("tool_attempts", {})
        attempt = tool_attempts.get(tool_name, 0) + 1
        tool_attempts[tool_name] = attempt

        recent_error_history = state.get("recent_errors", {}).get(tool_name, [])
        vision_usage = state.setdefault("vision_usage", {"count": 0, "session_count": 0})

        if self.feasibility_checker and self.feasibility_checker.enabled:
            decision = self.feasibility_checker.should_use_vision(
                tool_name=tool_name,
                attempt_count=attempt,
                recent_errors=recent_error_history,
                vision_usage=vision_usage
            )
            if decision.use_vision:
                vision_result = self._run_vision_pipeline(
                    state=state,
                    step=step,
                    decision=decision,
                    attempt=attempt
                )
                vision_result.setdefault("tool", tool_name)
                state["step_results"][step["id"]] = vision_result
                vision_usage["count"] = vision_usage.get("count", 0) + 1
                vision_usage["session_count"] = vision_usage.get("session_count", 0) + 1

                if vision_result.get("error"):
                    self._record_tool_error(
                        state,
                        tool_name,
                        vision_result.get("error_message", "Vision analysis failed")
                    )
                else:
                    self._clear_tool_errors(state, tool_name)

                state["current_step"] = current_idx + 1
                return state

        tool = self._get_tool_by_name(tool_name)

        # Add reasoning trace entry before tool execution
        execution_entry_id = None
        memory = state.get("memory")
        tool_commitments: List[str] = []
        if self.config:
            delivery_commitments = self.config.get("delivery", {}).get("tool_commitments", {})
            playback_commitments = self.config.get("playback", {}).get("tool_commitments", {})
            for mapping in (delivery_commitments, playback_commitments):
                if mapping and tool_name in mapping:
                    tool_commitments.extend(mapping.get(tool_name, []))

        if tool_commitments:
            tool_commitments = sorted(set(tool_commitments))

        if memory and memory.is_reasoning_trace_enabled():
            try:
                execution_entry_id = memory.add_reasoning_entry(
                    stage="execution",
                    thought=f"Executing {tool_name}",
                    action=tool_name,
                    parameters=resolved_params,
                    outcome="pending",
                    commitments=tool_commitments
                )
            except Exception as e:
                logger.debug(f"[REASONING TRACE] Failed to add execution entry: {e}")

        if not tool:
            logger.error(f"Tool not found: {tool_name}")
            state["step_results"][step["id"]] = {
                "error": True,
                "message": f"Tool '{tool_name}' not found",
                "tool": tool_name
            }
            self._record_tool_error(state, tool_name, "Tool not found in registry")
        else:
            # Execute tool with error recovery
            try:
                result = tool.invoke(resolved_params)
                logger.info(f"Step {step['id']} result: {result}")
                result.setdefault("tool", tool_name)
                
                # Update reasoning trace entry after tool execution
                if execution_entry_id and memory and memory.is_reasoning_trace_enabled():
                    try:
                        from ..memory.reasoning_trace import extract_attachments_from_step_result
                        attachments = extract_attachments_from_step_result(result)
                        outcome = "success" if not result.get("error") else "failed"
                        evidence = []
                        if result.get("message"):
                            evidence.append(result.get("message", "")[:200])
                        memory.update_reasoning_entry(
                            execution_entry_id,
                            outcome=outcome,
                            evidence=evidence,
                            attachments=attachments,
                            error=result.get("error_message") if result.get("error") else None
                        )
                    except Exception as e:
                        logger.debug(f"[REASONING TRACE] Failed to update execution entry: {e}")
                
                # Check if error occurred and attempt recovery
                if result.get("error"):
                    error_type = result.get("error_type", "UnknownError")
                    error_message = result.get("error_message", "Unknown error")
                    
                    # Use ErrorAnalyzer to analyze the error and suggest recovery
                    try:
                        from .error_analyzer import ErrorAnalyzer
                        error_analyzer = ErrorAnalyzer(self.config)
                        
                        # Build context for error analysis
                        context = {
                            "user_request": state.get("user_request", ""),
                            "step_id": step["id"],
                            "step_reasoning": step.get("reasoning", ""),
                            "previous_errors": recent_error_history
                        }
                        
                        analysis = error_analyzer.analyze_error(
                            tool_name=tool_name,
                            parameters=resolved_params,
                            error_type=error_type,
                            error_message=error_message,
                            attempt_number=attempt,
                            context=context
                        )
                        
                        logger.info(f"[ERROR RECOVERY] Analysis for step {step['id']}: {analysis.get('reasoning', '')}")
                        
                        # If retry is recommended and we haven't exceeded max attempts, retry with modified parameters
                        max_retries = 2  # Allow one retry with modified parameters
                        if analysis.get("retry_recommended") and attempt < max_retries:
                            suggested_params = analysis.get("suggested_parameters", {})
                            if suggested_params:
                                logger.info(f"[ERROR RECOVERY] Retrying step {step['id']} with modified parameters: {suggested_params}")
                                # Merge suggested parameters with original parameters
                                modified_params = {**resolved_params, **suggested_params}
                                
                                # Retry with modified parameters
                                retry_result = tool.invoke(modified_params)
                                retry_result.setdefault("tool", tool_name)
                                
                                if not retry_result.get("error"):
                                    logger.info(f"[ERROR RECOVERY] Retry succeeded for step {step['id']}")
                                    result = retry_result
                                    # Clear error since retry succeeded
                                    self._clear_tool_errors(state, tool_name)
                                else:
                                    logger.warning(f"[ERROR RECOVERY] Retry failed for step {step['id']}")
                                    # Store analysis in result for potential use by dependent steps
                                    result["error_analysis"] = analysis
                                    self._record_tool_error(state, tool_name, error_message)
                            else:
                                # No parameter modifications suggested, store analysis
                                result["error_analysis"] = analysis
                                self._record_tool_error(state, tool_name, error_message)
                        else:
                            # Don't retry or retry not recommended, store analysis
                            result["error_analysis"] = analysis
                            self._record_tool_error(state, tool_name, error_message)
                    except Exception as analyzer_error:
                        logger.error(f"[ERROR RECOVERY] Error analyzer failed: {analyzer_error}")
                        # Fallback: just record the error
                        self._record_tool_error(state, tool_name, error_message)
                else:
                    self._clear_tool_errors(state, tool_name)

                state["step_results"][step["id"]] = result

                # Verify output for critical steps (screenshots, attachments, etc.)
                if self._should_verify_step(step):
                    verification = self.verifier.verify_step_output(
                        user_request=state["user_request"],
                        step=step,
                        step_result=result,
                        context={"previous_steps": state["step_results"]}
                    )

                    if "verification_results" not in state:
                        state["verification_results"] = {}
                    state["verification_results"][step["id"]] = verification

                    # Log verification issues
                    if not verification.get("valid"):
                        logger.warning(f"Step {step['id']} verification failed!")
                        logger.warning(f"Issues: {verification.get('issues')}")
                        logger.warning(f"Suggestions: {verification.get('suggestions')}")
                        
                        # Add correction entry for verification failures
                        if memory and memory.is_reasoning_trace_enabled():
                            try:
                                memory.add_reasoning_entry(
                                    stage="correction",
                                    thought="Verification found issues",
                                    evidence=verification.get("issues", []),
                                    corrections=verification.get("suggestions", []),
                                    outcome="success"
                                )
                            except Exception as e:
                                logger.debug(f"[REASONING TRACE] Failed to add correction entry: {e}")

            except Exception as e:
                logger.error(f"Error executing step {step['id']}: {e}")
                state["step_results"][step["id"]] = {
                    "error": True,
                    "message": str(e),
                    "tool": tool_name
                }
                self._record_tool_error(state, tool_name, str(e))

                # Log retry attempt if retry logging is enabled
                memory = state.get("memory")
                if memory and memory.is_retry_logging_enabled():
                    try:
                        from ..memory.retry_logger import RetryReason, RecoveryPriority
                        interaction_id = state.get("interaction_id", str(uuid.uuid4()))

                        memory.log_retry_attempt(
                            interaction_id=interaction_id,
                            attempt_number=attempt,
                            reason=RetryReason.EXECUTION_ERROR,
                            priority=RecoveryPriority.HIGH,
                            failed_action=tool_name,
                            error_message=str(e),
                            error_type=type(e).__name__,
                            user_request=state.get("user_request", ""),
                            execution_context={
                                'current_plan': state.get("steps", []),
                                'execution_state': {
                                    'current_step': current_idx,
                                    'step_results': state.get("step_results", {})
                                },
                                'tool_parameters': resolved_params
                            },
                            reasoning_trace=self._get_reasoning_trace_for_retry(memory, interaction_id),
                            critic_feedback=[],  # Could be populated from error analysis
                            agent_name=self.__class__.__name__,
                            tool_name=tool_name,
                            execution_duration_ms=0,  # Not tracked here
                            retry_possible=attempt < 3,  # Allow up to 3 attempts
                            max_retries_reached=attempt >= 3
                        )
                    except Exception as retry_log_error:
                        logger.debug(f"[RETRY LOGGING] Failed to log retry attempt: {retry_log_error}")

        # Move to next step
        state["current_step"] = current_idx + 1

        return state

    def _get_reasoning_trace_for_retry(self, memory, interaction_id: str) -> List[Dict[str, Any]]:
        """Get reasoning trace entries for retry logging."""
        try:
            if hasattr(memory, '_reasoning_traces') and interaction_id in memory._reasoning_traces:
                trace_obj = memory._reasoning_traces[interaction_id]
                if hasattr(trace_obj, 'entries'):
                    return [entry.__dict__ if hasattr(entry, '__dict__') else entry for entry in trace_obj.entries]
        except Exception as e:
            logger.debug(f"[RETRY LOGGING] Failed to get reasoning trace: {e}")
        return []

    def finalize(self, state: AgentState) -> AgentState:
        """
        Finalization node: Summarize results.
        """
        logger.info("=== FINALIZING ===")

        # Handle case where plan has no steps (impossible task already set error)
        steps = state.get("steps") or []

        # Don't override statuses already set (error/cancelled)
        if state.get("status") == "error":
            logger.info("Final status: error (preserved from earlier stage)")
            return state

        if state.get("status") == "cancelled" or state.get("cancelled"):
            summary = {
                "goal": state.get("goal", ""),
                "steps_executed": min(state.get("current_step", 0), len(steps)),
                "results": state.get("step_results", {}),
                "status": "cancelled",
                "message": state.get("cancellation_reason") or "Execution cancelled."
            }
            state["final_result"] = summary
            logger.info("Final status: cancelled")
            return state

        # Gather all results
        summary = {
            "goal": state.get("goal", ""),
            "steps_executed": len(steps),
            "results": state.get("step_results", {}),
            "status": "success" if all(
                not r.get("error", False) for r in state.get("step_results", {}).values()
            ) else "partial_success"
        }

        # Prefer dedicated reply payload for user-facing communication
        step_results = state.get("step_results", {})
        reply_payload = None
        for step_id, step_result in step_results.items():
            if isinstance(step_result, dict) and step_result.get("type") == "reply":
                reply_payload = step_result
                summary["reply_step_id"] = step_id
                break

        if reply_payload:
            summary["status"] = reply_payload.get("status", summary["status"])
            summary["message"] = reply_payload.get("message", "")
            if reply_payload.get("details"):
                summary["details"] = reply_payload["details"]
            if reply_payload.get("artifacts"):
                summary["artifacts"] = reply_payload["artifacts"]

        # Always check step_results for richer message if current message is generic/short
        # This handles cases where reply agent gives generic message but search has detailed summary
        current_message = summary.get("message", "")
        if step_results and len(current_message) < 100:
            # Look through all step results for message/summary/content
            for step_id in sorted(step_results.keys()):
                step_result = step_results[step_id]
                if isinstance(step_result, dict) and step_result.get("type") != "reply":
                    # Skip reply payloads, look for actual tool results
                    # Extract message using same logic as slash commands
                    extracted_message = (
                        step_result.get("summary") or  # Try summary first (search results)
                        step_result.get("message") or
                        step_result.get("content") or
                        step_result.get("response") or
                        None
                    )
                    # Use this if it's longer/more detailed than current message
                    if extracted_message and len(extracted_message) > len(current_message):
                        summary["message"] = extracted_message
                        logger.info(f"[FINALIZE] Using richer message from step {step_id} ({len(extracted_message)} chars)")
                        break  # Use first substantive message found

        delivery_verbs = ["email", "send", "mail", "attach"]
        request_lower = (state.get("original_user_request") or state.get("user_request") or "").lower()

        email_result = None
        for step_id, step_result in step_results.items():
            if isinstance(step_result, dict) and step_result.get("tool") == "compose_email":
                email_result = step_result
                summary["compose_email_step_id"] = step_id
                break

        if email_result:
            # Log email result structure for debugging
            logger.info(f"[AGENT] Email result structure: {email_result}")
            
            base_message = summary.get("message", "")
            email_message = email_result.get("message") or ""
            
            # Check for error dict first
            if email_result.get("error"):
                error_type = email_result.get("error_type", "UnknownError")
                error_message = email_result.get("error_message", "Unknown error occurred")
                retry_possible = email_result.get("retry_possible", False)
                
                logger.warning(f"[AGENT] Email composition failed: {error_type} - {error_message}")
                
                if any(verb in request_lower for verb in delivery_verbs):
                    summary["status"] = "partial_success"
                    failure_note = f"Email composition failed: {error_message}"
                    if retry_possible:
                        failure_note += " (retry possible)"
                    
                    if base_message:
                        summary["message"] = f"{base_message.rstrip('. ')}. {failure_note}"
                    else:
                        summary["message"] = failure_note
            else:
                # Normal status handling
                email_status_value = (email_result.get("status") or "").lower()

                if email_status_value == "sent":
                    if base_message:
                        if "email" not in base_message.lower() and "sent" not in base_message.lower():
                            summary["message"] = f"{base_message.rstrip('. ')}. Email sent as requested."
                    else:
                        summary["message"] = email_message or "Email sent with the requested information."
                elif email_status_value in {"draft", "drafted"}:
                    summary["status"] = "partial_success"
                    draft_note = email_message or "Email drafted for your review. Please confirm and send it manually."
                    if base_message:
                        summary["message"] = f"{base_message.rstrip('. ')}. {draft_note}"
                    else:
                        summary["message"] = draft_note
                else:
                    # Status is missing or unexpected value
                    logger.warning(f"[AGENT] Email status is missing or unexpected: {email_status_value}, full result: {email_result}")
                    if any(verb in request_lower for verb in delivery_verbs):
                        summary["status"] = "partial_success"
                        failure_note = email_message or "Attempted to prepare the email, but delivery status is unclear."
                        if base_message:
                            summary["message"] = f"{base_message.rstrip('. ')}. {failure_note}"
                        else:
                            summary["message"] = failure_note
        else:
            if any(verb in request_lower for verb in delivery_verbs):
                base_message = summary.get("message", "")
                summary["status"] = "partial_success"
                note = "Email step was not executed. Please retry the request."
                if base_message:
                    summary["message"] = f"{base_message.rstrip('. ')}. {note}"
                else:
                    summary["message"] = note

        playback_config = self.config.get("playback", {}) if self.config else {}
        playback_verbs = playback_config.get("intent_verbs", ["play", "queue", "listen", "start"])
        playback_required_tool = playback_config.get("required_tool", "play_song")
        playback_verification_tool = playback_config.get("verification_tool")
        playback_failure_message = playback_config.get(
            "failure_message",
            "Unable to confirm Spotify playback. Please ensure Spotify is running and try again."
        )
        playback_success_message = playback_config.get(
            "success_message",
            "Started playback in Spotify."
        )

        def _append_summary_message(note: str):
            if not note:
                return
            base_message = summary.get("message", "")
            if base_message:
                summary["message"] = f"{base_message.rstrip('. ')}. {note}"
            else:
                summary["message"] = note

        playback_intent = any(verb in request_lower for verb in playback_verbs)
        if playback_intent:
            playback_success = False
            failure_details = None

            play_step = next(
                (s for s in steps if s.get("action") == playback_required_tool),
                None
            )
            play_step_result = step_results.get(play_step.get("id")) if play_step and play_step.get("id") in step_results else None

            if play_step_result:
                if play_step_result.get("error"):
                    failure_details = play_step_result.get("error_message") or play_step_result.get("message")
                else:
                    status_value = (play_step_result.get("status") or "").lower()
                    playback_success = bool(
                        play_step_result.get("success", False) or status_value == "playing"
                    )
            else:
                failure_details = "Playback tool did not execute."

            if playback_success and playback_verification_tool:
                verification_step = next(
                    (s for s in steps if s.get("action") == playback_verification_tool),
                    None
                )
                verification_result = step_results.get(verification_step.get("id")) if verification_step and verification_step.get("id") in step_results else None

                if not verification_result or verification_result.get("error"):
                    playback_success = False
                    failure_details = (
                        verification_result.get("error_message")
                        if verification_result and verification_result.get("error_message")
                        else "Could not verify Spotify playback status."
                    )
                else:
                    verification_status = (verification_result.get("status") or "").lower()
                    if verification_status != "playing":
                        playback_success = False
                        failure_details = verification_result.get("message") or "Spotify is not reporting playback."

            if playback_success and playback_success_message:
                _append_summary_message(playback_success_message)

            if not playback_success:
                if summary["status"] == "success":
                    summary["status"] = "partial_success"
                note_parts = [playback_failure_message]
                if failure_details and failure_details not in playback_failure_message:
                    note_parts.append(failure_details)
                _append_summary_message(" ".join(note_parts))

        # Check pending commitments from reasoning trace
        memory = state.get("memory")
        if memory and memory.is_reasoning_trace_enabled():
            try:
                pending = memory.get_pending_commitments()
                if pending:
                    # Block reply_to_user if commitments outstanding
                    has_reply_step = any(
                        step.get("action") == "reply_to_user"
                        for step in steps
                    )
                    critical_commitments = {"send_email", "attach_documents", "play_music"}
                    if has_reply_step and critical_commitments.intersection(set(pending)):
                        if summary["status"] == "success":
                            summary["status"] = "partial_success"
                        warning_msg = f" Warning: Some commitments not fulfilled: {', '.join(pending)}"
                        summary["message"] = f"{summary.get('message', '')}{warning_msg}".strip()
                        logger.warning(f"[FINALIZATION] Pending commitments detected: {pending}")
            except Exception as e:
                logger.debug(f"[REASONING TRACE] Failed to check pending commitments: {e}")

        state["final_result"] = summary
        state["status"] = "completed"

        logger.info(f"Final status: {summary['status']}")

        # CRITICAL: Check for unresolved template placeholders (regression detection)
        message = summary.get("message", "")
        details = summary.get("details", "")
        combined = f"{message} {details}"

        # Detect orphaned braces (sign of partial template resolution)
        import re
        if re.search(r'\{[\d.]+\}', combined):
            logger.error(
                "[FINALIZE] ❌ REGRESSION: Message contains orphaned braces (partial template resolution)! "
                f"Message: {message[:100]}"
            )

        # Detect unresolved template placeholders
        if "{$step" in combined or re.search(r'\$step\d+\.', combined):
            logger.error(
                "[FINALIZE] ❌ REGRESSION: Message contains unresolved template placeholders! "
                f"Message: {message[:100]}"
            )

        # Detect invalid placeholder patterns like {file1.name} or {fileX.field}
        # These are NOT part of the template language and indicate the planner
        # is copying the wrong example from the prompt
        invalid_placeholders = re.findall(r'\{(file\d+\.[a-z_]+|[a-z]+\d+\.[a-z_]+)\}', combined, re.IGNORECASE)
        if invalid_placeholders:
            logger.error(
                "[FINALIZE] ❌ REGRESSION: Message contains invalid placeholder patterns! "
                f"Found: {invalid_placeholders}. These are not valid template syntax. "
                f"Message: {message[:100]}"
            )

        return state

    def _should_continue(self, state: AgentState) -> str:
        """Decide whether to continue executing steps or finalize."""
        if state.get("status") == "cancelled" or state.get("cancelled"):
            return "finalize"
        steps = state.get("steps")
        if not steps or state["current_step"] >= len(steps):
            return "finalize"
        return "continue"

    def _cancellation_requested(self, state: AgentState) -> bool:
        """Check if a cancellation has been requested for this run."""
        cancel_event = state.get("cancel_event")
        return bool(cancel_event and cancel_event.is_set())

    def _handle_cancellation(self, state: AgentState, stage: str) -> bool:
        """Mark the run as cancelled if requested."""
        if self._cancellation_requested(state):
            reason = state.get("cancellation_reason") or "Execution cancelled by user request."
            state["cancellation_reason"] = reason
            state["cancelled"] = True
            state["status"] = "cancelled"
            logger.info(f"[AGENT] Cancellation requested during {stage}. Aborting remaining work.")
            return True
        return False

    def _validate_and_fix_plan(self, plan: Dict[str, Any], user_request: str) -> Dict[str, Any]:
        """
        Validate and auto-correct known bad patterns in plans before execution.

        This prevents regressions where the planner uses invalid placeholder syntax
        that was fixed in prompts but occasionally reappears.

        Args:
            plan: The parsed plan from the LLM
            user_request: Original user request for context

        Returns:
            Corrected plan with invalid patterns fixed
        """
        import re

        fixed_steps = []
        corrections_made = []
        warnings = []

        # Track what tools are used in the plan
        has_keynote_creation = False
        has_email = False
        keynote_step_id = None
        has_writing_tool = False
        has_playback_step = False
        has_playback_verification = False
        playback_config = self.config.get("playback", {}) if self.config else {}
        playback_required_tool = playback_config.get("required_tool", "play_song")
        playback_verification_tool = playback_config.get("verification_tool")
        playback_require_status_check = playback_config.get("require_status_check", True)
        candidate_body_steps: List[int] = []

        steps = plan.get("steps", [])

        # First pass: Identify tool usage patterns
        for step in steps:
            action = step.get("action", "")
            if action in ["create_keynote", "create_keynote_with_images"]:
                has_keynote_creation = True
                keynote_step_id = step.get("id")
            if action == "compose_email":
                has_email = True
            if action in ["synthesize_content", "create_detailed_report", "format_writing"]:
                has_writing_tool = True
            if action == playback_required_tool:
                has_playback_step = True
            if action == playback_verification_tool:
                has_playback_verification = True
            step_id = step.get("id")
            if step_id is not None and action not in ["compose_email", "reply_to_user"]:
                candidate_body_steps.append(step_id)

        existing_ids = [
            step.get("id") for step in steps
            if isinstance(step.get("id"), int)
        ]
        next_step_id = max(existing_ids) + 1 if existing_ids else len(steps) + 1
        verification_inserted = False

        # Second pass: Validate and fix each step
        for step in steps:
            step_fixed = False
            action = step.get("action", "")
            params = step.get("parameters", {})
            step_id = step.get("id")

            # VALIDATION 0: improve search_documents queries for file summaries
            if action == "search_documents":
                query_value = params.get("query")
                if isinstance(query_value, str):
                    cleaned_query = re.sub(r'\b(files?|documents?|docs)\b', '', query_value, flags=re.IGNORECASE)
                    cleaned_query = re.sub(r'\s+', ' ', cleaned_query).strip()
                    if cleaned_query and cleaned_query != query_value:
                        params["query"] = cleaned_query
                        step_fixed = True
                        corrections_made.append(
                            f"Step {step_id}: Cleaned search_documents query from '{query_value}' to '{cleaned_query}'"
                        )
                        logger.info(
                            f"[PLAN VALIDATION] ✅ Auto-corrected search_documents query -> '{cleaned_query}'"
                        )

            # VALIDATION 1: reply_to_user with invalid placeholders
            if action == "reply_to_user":
                # Check details field for invalid placeholder patterns
                details = params.get("details", "")
                if isinstance(details, str):
                    # Detect invalid patterns like {file1.name}, {file2.name}, etc.
                    invalid_pattern = re.search(r'\{(file\d+\.[a-z_]+|[a-z]+\d+\.[a-z_]+)\}', details, re.IGNORECASE)

                    if invalid_pattern:
                        logger.warning(
                            f"[PLAN VALIDATION] ❌ Step {step.get('id')} has invalid placeholder pattern: {invalid_pattern.group(0)}"
                        )

                        # Auto-fix: Replace with correct pattern based on context
                        if "duplicate" in user_request.lower():
                            # For duplicate queries, use $step1.duplicates
                            dup_step_id = None
                            for s in steps:
                                if s.get("action") == "folder_find_duplicates":
                                    dup_step_id = s.get("id")
                                    break

                            if dup_step_id:
                                params["details"] = f"$step{dup_step_id}.duplicates"
                                step_fixed = True
                                corrections_made.append(
                                    f"Step {step.get('id')}: Changed invalid placeholder details to '$step{dup_step_id}.duplicates'"
                                )
                                logger.info(
                                    f"[PLAN VALIDATION] ✅ Auto-corrected: details=\"$step{dup_step_id}.duplicates\""
                                )

            # VALIDATION 2: compose_email after keynote creation should reference the artifact
            if action == "compose_email" and has_keynote_creation and keynote_step_id:
                attachments = params.get("attachments", [])
                # Check if attachments reference the keynote step
                has_keynote_ref = any(
                    isinstance(att, str) and f"$step{keynote_step_id}" in att
                    for att in attachments
                )

                if not has_keynote_ref and not attachments:
                    # Auto-fix: Add keynote artifact as attachment
                    params["attachments"] = [f"$step{keynote_step_id}.file_path"]
                    step_fixed = True
                    corrections_made.append(
                        f"Step {step.get('id')}: Added missing keynote attachment from step {keynote_step_id}"
                    )
                    logger.info(
                        f"[PLAN VALIDATION] ✅ Auto-corrected: Added attachments=['$step{keynote_step_id}.file_path']"
                    )
                elif not has_keynote_ref and attachments:
                    warnings.append(
                        f"Step {step.get('id')}: Email has attachments but doesn't reference keynote from step {keynote_step_id}"
                    )

            # VALIDATION 2b: compose_email must send immediately when user requested delivery
            if action == "compose_email":
                send_flag = params.get("send")
                if send_flag is None or send_flag is False:
                    params["send"] = True
                    step_fixed = True
                    corrections_made.append(
                        f"Step {step_id}: Enforced send=true for compose_email to satisfy delivery request"
                    )
                    logger.info(
                        f"[PLAN VALIDATION] ✅ Auto-corrected: Step {step_id} now sets send=true for compose_email"
                    )

                body_value = params.get("body")
                if not isinstance(body_value, str) or not body_value.strip():
                    body_set = False
                    for candidate_step_id in reversed(candidate_body_steps):
                        for field in ["summary", "message", "content", "response"]:
                            params["body"] = f"$step{candidate_step_id}.{field}"
                            body_set = True
                            step_fixed = True
                            corrections_made.append(
                                f"Step {step_id}: Added email body reference '$step{candidate_step_id}.{field}'"
                            )
                            logger.info(
                                f"[PLAN VALIDATION] ✅ Auto-corrected: compose_email body now references $step{candidate_step_id}.{field}"
                            )
                            break
                        if body_set:
                            break
                    if not body_set:
                        params["body"] = "Summary of requested results."
                        step_fixed = True
                        corrections_made.append(
                            f"Step {step_id}: Set fallback email body text because no suitable step references were available"
                        )
                        logger.info(
                            f"[PLAN VALIDATION] ✅ Auto-corrected: compose_email body set to fallback summary text"
                        )

            fixed_steps.append(step)

            if (
                playback_require_status_check
                and has_playback_step
                and not has_playback_verification
                and not verification_inserted
                and playback_verification_tool
                and action == playback_required_tool
            ):
                verification_step = {
                    "id": next_step_id,
                    "action": playback_verification_tool,
                    "parameters": {},
                    "dependencies": [step.get("id")] if step.get("id") is not None else [],
                    "reasoning": "Verify Spotify playback status before responding to the user."
                }
                next_step_id += 1
                verification_inserted = True
                has_playback_verification = True
                fixed_steps.append(verification_step)
                corrections_made.append(
                    f"Inserted {playback_verification_tool} step after {playback_required_tool} to confirm playback."
                )
                logger.info(
                    f"[PLAN VALIDATION] ✅ Auto-corrected: Added {playback_verification_tool} step to verify Spotify playback"
                )

        # VALIDATION 3: Report/summary requests should use writing tools
        report_keywords = ["report", "summary", "summarize", "digest", "analysis", "analyze"]
        is_report_request = any(keyword in user_request.lower() for keyword in report_keywords)

        # Check if we have social media fetching
        has_social_fetch = any(
            step.get("action", "").startswith(("fetch_twitter", "fetch_bluesky", "fetch_social"))
            for step in steps
        )

        # Check if plan has reply_to_user
        has_reply = any(s.get("action") == "reply_to_user" for s in steps)

        if is_report_request and (has_email or has_reply) and not has_writing_tool:
            if has_social_fetch:
                warnings.append(
                    "⚠️  CRITICAL: Social media digest/summary detected but plan skips Writing Agent! "
                    "Required workflow: fetch_posts → synthesize_content → reply_to_user/compose_email. "
                    "Raw post data lacks analysis and formatting."
                )
            else:
                warnings.append(
                    "Request appears to need a report/summary but plan skips writing tools. "
                    "Consider using synthesize_content or create_detailed_report before email/reply."
                )

        # VALIDATION 4: Delivery intent detection - email/send/mail/attach verbs
        delivery_verbs = ["email", "send", "mail", "attach"]
        has_delivery_intent = any(verb in user_request.lower() for verb in delivery_verbs)

        if has_delivery_intent and not has_email:
            warnings.append(
                "⚠️  CRITICAL: Request includes delivery intent ('email', 'send', 'mail', 'attach') "
                "but plan is missing compose_email step! "
                "Required pattern: [work_step] → compose_email → reply_to_user"
            )

        if corrections_made:
            logger.warning(
                f"[PLAN VALIDATION] Made {len(corrections_made)} corrections to plan:\n" +
                "\n".join(f"  - {c}" for c in corrections_made)
            )

        if warnings:
            logger.warning(
                f"[PLAN VALIDATION] Potential issues detected:\n" +
                "\n".join(f"  ⚠️  {w}" for w in warnings)
            )

        plan["steps"] = fixed_steps
        return plan

    def _resolve_parameters(
        self,
        params: Dict[str, Any],
        step_results: Dict[int, Any],
        action: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resolve context variables in parameters.

        Uses shared template resolver for consistency across all executors.

        Handles both standalone variables and inline interpolation:
        - "$step1.doc_path" -> "/path/to/doc.pdf"
        - "Price is $step1.current_price" -> "Price is 225.50"
        - "Found {$step1.count} items" -> "Found 5 items"
        """
        from ..utils.template_resolver import resolve_parameters as resolve_params

        return resolve_params(params, step_results, action)

    def _resolve_single_value(self, value: Any, step_results: Dict[int, Any]) -> Any:
        """
        Resolve a single value that might be a context variable.

        Handles both standalone variables and inline interpolation.
        """
        if isinstance(value, str):
            # Check if entire value is a single context variable
            if value.startswith("$step") and "." in value:
                parts = value[1:].split(".")
                if len(parts) == 2:
                    step_ref, field = parts
                    try:
                        step_id = int(step_ref.replace("step", ""))
                        if step_id in step_results:
                            return step_results[step_id].get(field, value)
                    except (ValueError, KeyError):
                        pass

            # Handle inline variable interpolation
            import re
            def replace_var(match):
                var_name = match.group(0)
                parts = var_name[1:].split(".")
                if len(parts) == 2:
                    step_ref, field = parts
                    try:
                        step_id = int(step_ref.replace("step", ""))
                        if step_id in step_results:
                            result = step_results[step_id]
                            field_value = result.get(field, var_name)
                            return str(field_value) if field_value is not None else var_name
                    except (ValueError, KeyError):
                        pass
                return var_name

            return re.sub(r'\$step\d+\.\w+', replace_var, value)

        return value

    def _get_tool_by_name(self, tool_name: str):
        return next((t for t in ALL_AGENT_TOOLS if t.name == tool_name), None)

    def _record_tool_error(self, state: AgentState, tool_name: str, message: str):
        if not message:
            return
        errors = state.setdefault("recent_errors", {})
        history = errors.setdefault(tool_name, [])
        history.append(message)
        if len(history) > 5:
            history.pop(0)

    def _clear_tool_errors(self, state: AgentState, tool_name: str):
        errors = state.get("recent_errors")
        if errors and tool_name in errors:
            errors.pop(tool_name, None)

    def _run_vision_pipeline(
        self,
        state: AgentState,
        step: Dict[str, Any],
        decision,
        attempt: int
    ) -> Dict[str, Any]:
        tool_name = step.get("action")
        logger.info(
            "[VISION PIPELINE] Escalating step %s (%s) with decision=%s",
            step.get("id"),
            tool_name,
            decision.reason
        )

        screenshot_tool = self._get_tool_by_name("capture_screenshot")
        if not screenshot_tool:
            return {
                "error": True,
                "error_type": "VisionPipelineError",
                "error_message": "capture_screenshot tool unavailable",
                "escalated_to_vision": True,
            }

        target_app = step.get("parameters", {}).get("app_name")
        screenshot_params = {
            "output_name": f"vision_{tool_name}_{attempt}"
        }
        if target_app:
            screenshot_params["app_name"] = target_app

        screenshot_result = screenshot_tool.invoke(screenshot_params)
        if screenshot_result.get("error"):
            return {
                **screenshot_result,
                "escalated_to_vision": True
            }

        screenshot_path = screenshot_result.get("screenshot_path")

        vision_tool = self._get_tool_by_name("analyze_ui_screenshot")
        if not vision_tool:
            return {
                "error": True,
                "error_type": "VisionPipelineError",
                "error_message": "analyze_ui_screenshot tool unavailable",
                "screenshot_path": screenshot_path,
                "escalated_to_vision": True,
            }

        vision_payload = {
            "screenshot_path": screenshot_path,
            "goal": state.get("goal") or state.get("user_request"),
            "tool_name": tool_name,
            "recent_errors": state.get("recent_errors", {}).get(tool_name, []),
            "attempt": attempt
        }

        analysis = vision_tool.invoke(vision_payload)
        analysis.setdefault("status", "action_required")
        analysis["screenshot_path"] = screenshot_path
        analysis["escalated_to_vision"] = True
        analysis["vision_decision"] = {
            "confidence": decision.confidence,
            "reason": decision.reason
        }
        return analysis

    def _should_verify_step(self, step: Dict[str, Any]) -> bool:
        """
        Determine if a step's output should be verified.

        Verify steps that:
        - Take screenshots (quantitative output)
        - Extract sections (selection output)
        - Create files/presentations (content that will be attached)
        """
        action = step.get("action", "")
        verify_actions = [
            "take_screenshot",
            "extract_section",
            "create_keynote_with_images",
            "create_keynote",
            "create_pages_doc"
        ]
        return action in verify_actions

    def _get_trace_summary_for_prompt(self, session_id: Optional[str] = None) -> str:
        """
        Get reasoning trace summary for prompt injection.

        Returns empty string if trace is disabled or unavailable.
        Truncates to 500 chars to keep prompts manageable.

        Args:
            session_id: Session ID to get trace from

        Returns:
            Formatted trace summary (empty string if disabled)
        """
        if not self.session_manager or not session_id:
            return ""

        try:
            memory = self.session_manager.get_or_create_session(session_id)
            if not memory or not memory.is_reasoning_trace_enabled():
                return ""

            trace_summary = memory.get_reasoning_summary(max_entries=5)
            if not trace_summary:
                return ""

            # Truncate to 500 chars to keep prompts manageable
            if len(trace_summary) > 500:
                trace_summary = trace_summary[:497] + "..."

            return f"\n{trace_summary}\n"
        except Exception as e:
            logger.debug(f"[REASONING TRACE] Failed to get trace summary for prompt: {e}")
            return ""

    def run(
        self,
        user_request: str,
        session_id: Optional[str] = None,
        cancel_event: Optional[Event] = None,
        context: Optional[Dict[str, Any]] = None,
        on_plan_created: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Execute the agent workflow.

        Args:
            user_request: Natural language request
            session_id: Optional session ID for context tracking
            cancel_event: Optional threading.Event used to signal cancellation
            context: Optional context dictionary (e.g., intent_hints from slash commands)

        Returns:
            Final result dictionary
        """
        if context:
            logger.info(f"[EMAIL WORKFLOW] Starting agent with context: {context}")
        logger.info(f"Starting agent for request: {user_request}")

        # Check if this is a slash command and handle it directly
        if user_request.strip().startswith('/'):
            from ..ui.slash_commands import SlashCommandHandler
            from ..agent.agent_registry import AgentRegistry

            registry = AgentRegistry(self.config, session_manager=self.session_manager)
            handler = SlashCommandHandler(registry, session_manager=self.session_manager, config=self.config)
            is_command, result = handler.handle(user_request, session_id=session_id)
            
            if is_command:
                # Check if this is a retry_with_orchestrator result
                if isinstance(result, dict) and result.get("type") == "retry_with_orchestrator":
                    # Return the retry result as-is so api_server can handle it
                    return {
                        "type": "retry_with_orchestrator",
                        "original_message": result.get("original_message", user_request),
                        "content": result.get("content", "Retrying via main assistant..."),
                        "error": result.get("error")
                    }
                
                # Format result to match agent.run() return format
                if isinstance(result, dict):
                    if result.get("type") == "result":
                        tool_result = result.get("result", {})
                        # Extract message from various possible fields (message, summary, content, etc.)
                        message = (
                            tool_result.get("message") or
                            tool_result.get("summary") or
                            tool_result.get("content") or
                            tool_result.get("response") or
                            get_generic_success_message()
                        )
                        # Determine status: only mark as error if there's an explicit error field
                        # Otherwise, default to success if we have a message/summary/content
                        is_error = tool_result.get("error") is True
                        # Check if we have actual content (not just a fallback generic message)
                        # We check if message exists and has reasonable length (generic messages are typically short)
                        has_content = bool(
                            message and 
                            len(message.strip()) > 0 and
                            # If message came from tool_result, it's real content
                            (tool_result.get("message") or tool_result.get("summary") or tool_result.get("content") or tool_result.get("response"))
                        )
                        status = "error" if is_error else ("success" if has_content else "completed")

                        return {
                            "status": status,
                            "message": message,
                            "final_result": tool_result,
                            "results": {1: tool_result}
                        }
                    elif result.get("type") == "error":
                        return {
                            "status": "error",
                            "message": result.get("content", "Command failed"),
                            "final_result": {"error": True, "error_message": result.get("content")}
                        }
                    else:
                        # Help or other types - return as is
                        return {
                            "status": "success",
                            "message": result.get("content", str(result)),
                            "final_result": result
                        }
                return {
                    "status": "success",
                    "message": str(result),
                    "final_result": result
                }

        # Get session context if available
        session_context = None
        memory = None
        interaction_id = None
        if self.session_manager and session_id:
            memory = self.session_manager.get_or_create_session(session_id)
            session_context = self.session_manager.get_langgraph_context(session_id)
            logger.info(f"[SESSION] Loaded context for session: {session_id}")
            
            # Start reasoning trace if enabled
            if memory and memory.is_reasoning_trace_enabled():
                interaction_id = memory.add_interaction(user_request=user_request)
                memory.start_reasoning_trace(interaction_id)
                logger.debug(f"[REASONING TRACE] Started trace for interaction {interaction_id}")
        
        shared_context = (session_context or {}).get("shared_context", {})
        session_vision_count = shared_context.get("vision_session_count", 0)

        # Initialize state
        initial_state = {
            "user_request": user_request,
            "goal": "",
            "steps": [],
            "current_step": 0,
            "step_results": {},
            "verification_results": {},
            "messages": [],
            "session_id": session_id,
            "session_context": session_context,
            "final_result": None,
            "status": "planning",
            "cancel_event": cancel_event,
            "cancelled": False,
            "cancellation_reason": None,
            "tool_attempts": {},
            "vision_usage": {
                "count": 0,
                "session_count": session_vision_count
            },
            "recent_errors": {},
            "planning_context": context or {},  # Add planning context (e.g., intent_hints from slash commands)
            "on_plan_created": on_plan_created,  # Store callback in state for plan_task to access
            "memory": memory,  # Store memory reference for trace instrumentation
            "interaction_id": interaction_id  # Store interaction_id for trace instrumentation
        }

        # Run graph
        try:
            final_state = self.graph.invoke(initial_state)
            result = final_state["final_result"]

            # Record interaction in session memory
            if self.session_manager and session_id:
                memory = self.session_manager.get_or_create_session(session_id)
                vision_usage = final_state.get("vision_usage", {})
                if vision_usage:
                    memory.shared_context["vision_session_count"] = vision_usage.get("session_count", 0)
                memory.add_interaction(
                    user_request=user_request,
                    agent_response=result,
                    plan=final_state.get("steps", []),
                    step_results=final_state.get("step_results", {}),
                    metadata={
                        "goal": final_state.get("goal", ""),
                        "status": final_state.get("status", "unknown")
                    }
                )
                # Save session to disk
                self.session_manager.save_session(session_id)
                logger.info(f"[SESSION] Recorded interaction for session: {session_id}")

            return result

        except Exception as e:
            logger.error(f"Agent execution error: {e}")
            return {
                "error": True,
                "message": f"Agent failed: {str(e)}"
            }
