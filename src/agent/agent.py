"""
LangGraph agent with task decomposition and state management.
"""

from typing import TypedDict, Annotated, List, Dict, Any, Optional
from threading import Event, Lock
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import json
import logging
import uuid
import time
from pathlib import Path
from datetime import datetime

try:
    from opentelemetry import trace  # type: ignore
    from opentelemetry.trace import Status, StatusCode  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    trace = None  # type: ignore
    Status = None  # type: ignore
    StatusCode = None  # type: ignore

from . import ALL_AGENT_TOOLS
from .feasibility_checker import FeasibilityChecker
from .verifier import OutputVerifier
from .telemetry import get_telemetry
from ..memory import SessionManager
from ..utils.message_personality import get_generic_success_message
from ..utils.performance_monitor import get_performance_monitor

logger = logging.getLogger(__name__)


def _safe_set_span_status(span, code, description: str) -> None:
    """Set span status safely when OpenTelemetry is available."""
    if not span or not Status or not StatusCode:
        return
    try:
        if code == StatusCode.ERROR and description:
            span.set_status(Status(code, description))
        else:
            span.set_status(Status(code))
    except Exception:
        pass


class ResultCapture:
    """
    Thread-safe result capture mechanism for LangGraph execution.
    
    Allows agent.run() to return as soon as finalize() sets the result,
    even if graph.invoke() continues running in the background.
    """
    
    def __init__(self):
        self._result = None
        self._lock = Lock()
        self._captured = False
        self._capture_time = None
    
    def set(self, result: Dict[str, Any]) -> None:
        """Set the final result (called by finalize())."""
        with self._lock:
            if not self._captured:
                self._result = result
                self._captured = True
                self._capture_time = time.time()
                logger.info(f"[RESULT_CAPTURE] Result captured at {self._capture_time}")
    
    def wait(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Wait for result to be captured.
        
        Args:
            timeout: Maximum time to wait in seconds. None means wait indefinitely.
            
        Returns:
            The captured result dict, or None if timeout occurred.
        """
        start_time = time.time()
        while True:
            with self._lock:
                if self._captured:
                    elapsed = time.time() - start_time
                    logger.info(f"[RESULT_CAPTURE] Result retrieved after {elapsed:.2f}s wait")
                    return self._result
            
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    logger.warning(f"[RESULT_CAPTURE] Wait timed out after {timeout}s")
                    return None
            
            # Small sleep to avoid busy-waiting
            time.sleep(0.1)
    
    def get(self) -> Optional[Dict[str, Any]]:
        """Get the result if it's been captured, without waiting."""
        with self._lock:
            return self._result if self._captured else None
    
    def is_captured(self) -> bool:
        """Check if result has been captured."""
        with self._lock:
            return self._captured


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

    # Plan streaming state (for live progress tracking)
    sequence_number: int  # Monotonically increasing counter for plan update events
    on_step_started: Optional[callable]  # Callback when step begins execution
    on_step_succeeded: Optional[callable]  # Callback when step completes successfully
    on_step_failed: Optional[callable]  # Callback when step fails
    
    # Reasoning trace instrumentation
    memory: Optional[Any]  # SessionMemory instance for trace instrumentation
    interaction_id: Optional[str]  # Current interaction ID for trace
    
    # Result capture for non-blocking execution
    result_capture: Optional[ResultCapture]  # Thread-safe result capture mechanism
    
    # Telemetry
    correlation_id: Optional[str]  # Correlation ID for telemetry tracking


class AutomationAgent:
    """
    LangGraph agent for task decomposition and execution.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        session_manager: Optional[SessionManager] = None,
        on_plan_created: Optional[callable] = None,
        on_step_started: Optional[callable] = None,
        on_step_succeeded: Optional[callable] = None,
        on_step_failed: Optional[callable] = None
    ):
        self.config = config
        # Note: on_plan_created is deprecated - pass through run() method instead to avoid cross-talk
        self.on_plan_created = on_plan_created  # Callback for sending plan to UI (deprecated)
        self.on_step_started = on_step_started
        self.on_step_succeeded = on_step_succeeded
        self.on_step_failed = on_step_failed
        
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
            repo = PromptRepository(config=self.config)
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
            repo = PromptRepository(config=self.config)

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
        # Telemetry: Start planning phase span
        correlation_id = state.get("correlation_id")
        span = None
        if correlation_id:
            from telemetry.tool_helpers import create_tool_span, record_event
            span = create_tool_span("plan_task", correlation_id)
            span.set_attribute("phase", "planning")
            span.set_attribute("user_request", state.get("user_request", ""))
            record_event(span, "planning_started", {"correlation_id": correlation_id})

        if self._handle_cancellation(state, "planning"):
            if span:
                if StatusCode:
                    _safe_set_span_status(span, StatusCode.OK, "cancelled")
                record_event(span, "planning_cancelled")
                span.end()
            return state
        
        # Safety check: reject /clear commands (should be handled by WebSocket handler)
        user_request_lowercase_only = state.get('user_request', '').strip().lower()
        if user_request_lowercase_only == '/clear' or user_request_lowercase_only == 'clear':
            logger.warning("Received /clear command in agent - this should be handled by WebSocket handler")
            state["status"] = "error"
            error_result = {
                "error": True,
                "message": "/clear command should be handled by the WebSocket handler, not the agent. Please use /clear directly.",
                "missing_capabilities": None
            }
            state["final_result"] = error_result
            # Capture error result for non-blocking return
            result_capture = state.get("result_capture")
            if result_capture:
                result_capture.set(error_result)
            return state
        
        logger.info("=== PLANNING PHASE ===")
        full_user_request = state.get("user_request", "")
        logger.info(f"User request: {full_user_request}")
        state["original_user_request"] = full_user_request

        # Fast-fail known unsupported stock queries (private companies)
        private_companies = {
            "openai": "OpenAI is a private company and does not have a publicly traded stock price.",
            "spacex": "SpaceX is privately held and its stock price is not available to the public.",
        }
        user_lower = full_user_request.lower()
        stock_keywords = ("stock", "stocks", "price", "prices", "share", "shares", "ticker")
        has_stock_intent = any(keyword in user_lower for keyword in stock_keywords)
        for company, message in private_companies.items():
            if company in user_lower and has_stock_intent:
                logger.info(f"[PLANNING] Detected request for private company '{company}'. Failing fast.")
                state["status"] = "error"
                error_result = {
                    "status": "error",
                    "error": True,
                    "error_type": "PrivateCompany",
                    "message": f"{message} Please provide a publicly traded company (e.g., AAPL, MSFT).",
                    "details": message,
                    "suggestion": "Provide a company with an exchange-listed ticker symbol.",
                }
                state["final_result"] = error_result
                result_capture = state.get("result_capture")
                if result_capture:
                    result_capture.set(error_result)
                if span:
                    if StatusCode:
                        _safe_set_span_status(span, StatusCode.OK, "unsupported_request")
                    record_event(span, "planning_not_supported", {
                        "reason": "private_company",
                        "company": company
                    })
                    span.end()
                return state

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

        # Get recent failure avoidance tips
        failure_tips = ""
        try:
            from telemetry.catalog_manager import get_planner_failure_tips
            failure_tips = get_planner_failure_tips()
        except Exception as e:
            logger.debug(f"Could not load failure tips: {e}")

        planning_prompt = f"""
{system_prompt}

{task_decomp_prompt}

{user_context}

{delivery_guidance}

AVAILABLE TOOLS (COMPLETE LIST - DO NOT HALLUCINATE OTHER TOOLS):
{available_tools_list}

{few_shot_examples}

{failure_tips}

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

            # Telemetry: Record planning phase failure
            if correlation_id:
                from telemetry.tool_helpers import set_span_error
                if span:
                    set_span_error(span, Exception(str(e)), {"parsing_error": True, "status": "error"})
                    span.end()

        # Telemetry: Record planning phase success
        if correlation_id and state.get("status") != "error":
            plan_steps = len(state.get("steps", []))
            if span:
                span.set_attribute("steps_created", plan_steps)
                span.set_attribute("goal", state.get("goal", ""))
                record_event(span, "planning_completed", {
                    "steps_created": plan_steps,
                    "goal": state.get("goal", "")
                })
                span.end()

        return state

    def execute_step(self, state: AgentState) -> AgentState:
        """
        Execution node: Execute current step.
        """
        # Telemetry: Start step execution span
        correlation_id = state.get("correlation_id")
        current_step = state.get("current_step", 0)
        total_steps = len(state.get("steps", []))
        step_span = None

        if correlation_id:
            from telemetry.tool_helpers import create_tool_span, record_event, log_tool_step
            step_span = create_tool_span(f"step_{current_step}", correlation_id)
            step_span.set_attribute("step_index", current_step)
            step_span.set_attribute("total_steps", total_steps)
            record_event(step_span, "step_execution_started", {
                "step_index": current_step,
                "total_steps": total_steps
            })
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

        # Call step started callback for live progress tracking
        step_started_callback = state.get("on_step_started")
        if step_started_callback:
            try:
                state["sequence_number"] += 1
                step_started_callback({
                    "step_id": step["id"],
                    "sequence_number": state["sequence_number"],
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                logger.debug(f"Failed to call step started callback: {e}")

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

        # CRITICAL: Verify compose_email content before execution
        if action == "compose_email":
            verification_result = self._verify_email_content(
                state=state,
                step=step,
                resolved_params=resolved_params
            )
            
            if not verification_result.get("verified", True):
                logger.warning(f"[EMAIL VERIFICATION] Email content incomplete: {verification_result.get('missing_items', [])}")
                
                # Apply suggested corrections
                suggestions = verification_result.get("suggestions", {})
                if suggestions:
                    logger.info(f"[EMAIL VERIFICATION] Applying corrections to email parameters")
                    if "body" in suggestions:
                        resolved_params["body"] = suggestions["body"]
                        logger.info(f"[EMAIL VERIFICATION] Updated email body with missing content")
                    if "attachments" in suggestions:
                        resolved_params["attachments"] = suggestions["attachments"]
                        logger.info(f"[EMAIL VERIFICATION] Updated attachments list")

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
                # Add memory context to parameters for tools that can use it
                tool_params = resolved_params.copy()
                if memory and memory.is_reasoning_trace_enabled():
                    try:
                        # Add reasoning context for tools that can benefit from memory
                        reasoning_context = {
                            "trace_enabled": True,
                            "commitments": memory.get_pending_commitments(),
                            "past_attempts": len(memory.interactions),
                            "interaction_id": getattr(memory, '_current_interaction_id', None)
                        }

                        # Enhance reasoning context for music tools with recent playback history
                        if tool_name in ["play_song", "get_spotify_status"]:
                            # Get recent interactions from active context window
                            active_interactions = memory.get_active_context_interactions()
                            recent_music_attempts = []

                            # Extract recent music-related interactions
                            for interaction in reversed(active_interactions[-3:]):  # Last 3 interactions
                                if interaction.step_results:
                                    for step_result in interaction.step_results.values():
                                        if step_result.get("tool") in ["play_song", "pause_music", "get_spotify_status"]:
                                            music_attempt = {
                                                "timestamp": interaction.timestamp,
                                                "action": step_result.get("tool"),
                                                "song_name": step_result.get("song_name"),
                                                "artist": step_result.get("artist"),
                                                "success": not step_result.get("error", False),
                                                "disambiguation": step_result.get("disambiguation", {}),
                                                "error_type": step_result.get("error_type") if step_result.get("error") else None
                                            }
                                            recent_music_attempts.append(music_attempt)

                            reasoning_context.update({
                                "recent_music_attempts": recent_music_attempts,
                                "spotify_last_resolution": memory.get_context("spotify.last_resolution"),
                                "spotify_clarifications": memory.get_context("spotify.clarifications", [])
                            })

                        # Only add reasoning context to tools that can use it
                        memory_enabled_tools = [
                            "play_song", "clarify_song_selection", "process_clarification_response",
                            "get_stock_history", "search_stock_symbol",
                            "plan_trip_with_stops", "google_search", "compose_email",
                            "create_keynote", "synthesize_content", "create_slide_deck_content"
                        ]

                        if tool_name in memory_enabled_tools:
                            tool_params["reasoning_context"] = reasoning_context
                            logger.debug(f"[MEMORY INTEGRATION] Added reasoning context to {tool_name}")

                    except Exception as e:
                        logger.debug(f"[MEMORY INTEGRATION] Could not add reasoning context: {e}")

                # Telemetry: Record tool call start
                tool_start_time = time.time()
                if correlation_id:
                    log_tool_step(tool_name, "start", {
                        "inputs": tool_params,
                        "step_index": current_step,
                        "_span": step_span
                    }, correlation_id)

                try:
                    result = tool.invoke(tool_params)
                    execution_time_ms = (time.time() - tool_start_time) * 1000

                    # Telemetry: Record tool call success
                    if correlation_id:
                        log_tool_step(tool_name, "success", {
                            "inputs": tool_params,
                            "outputs": result,
                            "execution_time_ms": execution_time_ms,
                            "step_index": current_step,
                            "_span": step_span
                        }, correlation_id)

                except Exception as tool_error:
                    execution_time_ms = (time.time() - tool_start_time) * 1000

                    # Telemetry: Record tool call error
                    if correlation_id:
                        log_tool_step(tool_name, "error", {
                            "inputs": tool_params,
                            "error_message": str(tool_error),
                            "execution_time_ms": execution_time_ms,
                            "step_index": current_step,
                            "_span": step_span
                        }, correlation_id)
                    raise

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

                        # Capture additional metadata for music tasks
                        update_kwargs = {
                            "outcome": outcome,
                            "evidence": evidence,
                            "attachments": attachments,
                            "error": result.get("error_message") if result.get("error") else None
                        }

                        # Add disambiguation metadata for play_song tool
                        if tool_name == "play_song" and result.get("_disambiguation_metadata"):
                            disambiguation_data = result["_disambiguation_metadata"]
                            update_kwargs["disambiguation"] = disambiguation_data
                            # Add additional context about ambiguity decisions
                            if disambiguation_data.get("needs_clarification"):
                                update_kwargs["clarification_needed"] = True
                                update_kwargs["confidence_too_low"] = disambiguation_data.get("confidence", 0) < 0.7
                            if disambiguation_data.get("clarification_requested"):
                                update_kwargs["clarification_requested"] = True
                                update_kwargs["ambiguity_decision_reasoning"] = disambiguation_data.get("decision_reasoning", "")
                                update_kwargs["risk_factors"] = disambiguation_data.get("risk_factors", [])

                        # Store clarification data in session context for future learning
                        if tool_name == "process_clarification_response" and result.get("clarification_data"):
                            clarification_data = result["clarification_data"]
                            try:
                                # Store the successful clarification resolution
                                memory.set_context("spotify.last_resolution", {
                                    "original_query": clarification_data["original_query"],
                                    "resolved_song": clarification_data["resolved_song"],
                                    "resolved_artist": clarification_data["resolved_artist"],
                                    "clarification_timestamp": clarification_data["clarification_timestamp"],
                                    "confidence": 1.0  # User-confirmed resolutions get max confidence
                                })

                                # Add to clarifications list for pattern learning
                                existing_clarifications = memory.get_context("spotify.clarifications", [])
                                existing_clarifications.append(clarification_data)
                                # Keep only last 10 clarifications to avoid unbounded growth
                                if len(existing_clarifications) > 10:
                                    existing_clarifications = existing_clarifications[-10:]
                                memory.set_context("spotify.clarifications", existing_clarifications)

                                logger.debug(f"[CONTEXT LEARNING] Stored clarification: {clarification_data['original_query']} → {clarification_data['resolved_song']}")

                            except Exception as e:
                                logger.debug(f"[CONTEXT LEARNING] Failed to store clarification: {e}")

                        memory.update_reasoning_entry(execution_entry_id, **update_kwargs)
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

                # CRITICAL: Log result structure before storing in step_results
                step_id = step["id"]
                logger.info(f"[AGENT] Storing result in step_results[{step_id}] for tool '{tool_name}'")
                logger.info(f"[AGENT] Result type: {type(result)}, is_dict: {isinstance(result, dict)}")
                if isinstance(result, dict):
                    logger.info(f"[AGENT] Result keys: {list(result.keys())}")
                    result_type = result.get("type", "unknown")
                    logger.info(f"[AGENT] Result type field: '{result_type}'")
                    if result_type == "file_list":
                        files_count = len(result.get("files", []))
                        logger.info(f"[AGENT] ✅ FILE_LIST detected! files count: {files_count}")
                        if files_count > 0:
                            logger.info(f"[AGENT] First file keys: {list(result['files'][0].keys()) if result['files'] else 'empty'}")
                
                state["step_results"][step_id] = result
                logger.info(f"[AGENT] ✅ Result stored in step_results[{step_id}]")

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

        # Call step completion callback for live progress tracking
        step_result = state["step_results"].get(step["id"], {})
        has_error = step_result.get("error", False)

        if has_error:
            # Call step failed callback
            step_failed_callback = state.get("on_step_failed")
            if step_failed_callback:
                try:
                    state["sequence_number"] += 1
                    error_message = step_result.get("message", "Unknown error")
                    step_failed_callback({
                        "step_id": step["id"],
                        "sequence_number": state["sequence_number"],
                        "timestamp": datetime.now().isoformat(),
                        "error": error_message[:500] + "..." if len(error_message) > 500 else error_message,
                        "can_retry": step_result.get("retry_possible", False)
                    })
                except Exception as e:
                    logger.debug(f"Failed to call step failed callback: {e}")
        else:
            # Call step succeeded callback
            step_succeeded_callback = state.get("on_step_succeeded")
            if step_succeeded_callback:
                try:
                    state["sequence_number"] += 1
                    # Get output preview from step result
                    output_preview = None
                    if "message" in step_result and isinstance(step_result["message"], str):
                        output_preview = step_result["message"][:200] + "..." if len(step_result["message"]) > 200 else step_result["message"]
                    elif "result" in step_result:
                        result_str = str(step_result["result"])
                        output_preview = result_str[:200] + "..." if len(result_str) > 200 else result_str

                    step_succeeded_callback({
                        "step_id": step["id"],
                        "sequence_number": state["sequence_number"],
                        "timestamp": datetime.now().isoformat(),
                        "output_preview": output_preview
                    })
                except Exception as e:
                    logger.debug(f"Failed to call step succeeded callback: {e}")

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
    
    def _verify_commitments_fulfilled(self, state: AgentState, memory) -> None:
        """
        Verify that all commitments (like send_email, attach_documents) were fulfilled.
        
        Uses reasoning trace to check if what we promised to do actually got done.
        Logs warnings if commitments are unfulfilled.
        
        Args:
            state: Current agent state
            memory: Session memory with reasoning trace
        """
        try:
            reasoning_summary = memory.get_reasoning_summary()
            
            # Defensive check: reasoning_summary might be a string instead of dict
            if not isinstance(reasoning_summary, dict):
                logger.debug(f"[FINALIZE] reasoning_summary is not a dict (type: {type(reasoning_summary)}), skipping commitment verification")
                return
            
            commitments = reasoning_summary.get("commitments", [])
            
            if not commitments:
                logger.debug("[FINALIZE] No commitments to verify")
                return
            
            logger.info(f"[FINALIZE] Verifying commitments: {commitments}")
            
            step_results = state.get("step_results", {})
            user_request = state.get("original_user_request") or state.get("user_request", "")
            
            # Check each commitment
            unfulfilled = []
            for commitment in commitments:
                if commitment == "send_email":
                    # Check if compose_email was executed successfully
                    email_executed = any(
                        isinstance(result, dict) and result.get("tool") == "compose_email" and not result.get("error")
                        for result in step_results.values()
                    )
                    if not email_executed:
                        unfulfilled.append("send_email")
                        logger.warning("[FINALIZE] ⚠️  COMMITMENT UNFULFILLED: User asked to send email but compose_email not executed successfully")
                
                elif commitment == "attach_documents":
                    # Check if email had attachments
                    email_with_attachments = any(
                        isinstance(result, dict) and
                        result.get("tool") == "compose_email" and 
                        isinstance(result.get("parameters", {}).get("attachments"), list) and
                        len(result.get("parameters", {}).get("attachments", [])) > 0
                        for result in step_results.values()
                    )
                    if not email_with_attachments:
                        unfulfilled.append("attach_documents")
                        logger.warning("[FINALIZE] ⚠️  COMMITMENT UNFULFILLED: User asked to attach documents but email had no attachments")
                
                elif commitment == "play_music":
                    # Check if play_song was executed successfully
                    music_played = any(
                        isinstance(result, dict) and result.get("tool") == "play_song" and not result.get("error")
                        for result in step_results.values()
                    )
                    if not music_played:
                        unfulfilled.append("play_music")
                        logger.warning("[FINALIZE] ⚠️  COMMITMENT UNFULFILLED: User asked to play music but play_song not executed successfully")
            
            # Record verification in reasoning trace
            if unfulfilled:
                memory.add_reasoning_entry(
                    stage="finalization",
                    thought="Final commitment verification - some commitments unfulfilled",
                    outcome="partial",
                    evidence=[
                        f"User request: {user_request[:100]}",
                        f"Commitments made: {commitments}",
                        f"Unfulfilled: {unfulfilled}"
                    ],
                    commitments=unfulfilled,  # Track what's still pending
                    corrections=[f"In future, ensure {c} is actually executed" for c in unfulfilled]
                )
                logger.warning(f"[FINALIZE] ⚠️  {len(unfulfilled)} commitment(s) unfulfilled: {unfulfilled}")
                logger.warning(f"[FINALIZE] This may indicate the response is incomplete!")
            else:
                memory.add_reasoning_entry(
                    stage="finalization",
                    thought="Final commitment verification - all commitments fulfilled",
                    outcome="success",
                    evidence=[
                        f"User request: {user_request[:100]}",
                        f"Commitments made: {commitments}",
                        "All commitments verified"
                    ]
                )
                logger.info(f"[FINALIZE] ✅ All {len(commitments)} commitment(s) verified as fulfilled")
        
        except Exception as e:
            logger.error(f"[FINALIZE] Error during commitment verification: {e}")
            import traceback
            traceback.print_exc()

    def _enforce_reply_to_user_final_step(self, state: AgentState) -> None:
        """
        CRITICAL: Ensure every workflow ends with reply_to_user for UI consistency.

        If the final step is NOT reply_to_user, automatically execute one with a summary
        of what was accomplished. This guarantees users always get feedback.

        This method ALWAYS succeeds in adding a reply, even if the tool is not found or fails.
        It will create a manual reply payload as a last resort.

        Args:
            state: Current agent state
        """
        steps = state.get("steps", [])
        step_results = state.get("step_results", {})
        
        # Check if we already have a reply in step_results
        has_reply = False
        for step_result in step_results.values():
            if isinstance(step_result, dict) and step_result.get("type") == "reply":
                has_reply = True
                logger.debug("[REPLY ENFORCEMENT] ✅ Reply already exists in step_results - no enforcement needed")
                break
        
        if has_reply:
            return
        
        # If no steps, create a minimal reply
        if not steps:
            logger.warning("[REPLY ENFORCEMENT] No steps in plan - creating minimal reply")
            goal = state.get("goal", "Task")
            synthetic_step_id = "auto_reply_0"
            state["step_results"][synthetic_step_id] = {
                "type": "reply",
                "message": f"✅ {goal} completed.",
                "details": "",
                "artifacts": [],
                "status": "success",
                "error": False
            }
            logger.info(f"[REPLY ENFORCEMENT] ✅ Created minimal reply (step {synthetic_step_id})")
            return

        # Check if final step is reply_to_user
        final_step = steps[-1]
        if final_step.get("action") == "reply_to_user":
            logger.debug("[REPLY ENFORCEMENT] ✅ Final step is reply_to_user - no enforcement needed")
            return

        logger.warning("[REPLY ENFORCEMENT] ❌ Final step is NOT reply_to_user - enforcing automatic reply")

        # Build summary from all step results
        successful_steps = []
        failed_steps = []
        key_artifacts = []

        for step_id, result in step_results.items():
            if isinstance(result, dict):
                step_info = f"Step {step_id}"
                if result.get("error"):
                    failed_steps.append(step_info)
                else:
                    successful_steps.append(step_info)

                    # Collect key artifacts (files, emails, etc.)
                    if "file_path" in result:
                        key_artifacts.append(result["file_path"])
                    elif "reminder_id" in result:
                        key_artifacts.append(f"Reminder ID: {result['reminder_id']}")

        # Create automatic reply message
        goal = state.get("goal", "task")

        if failed_steps and not successful_steps:
            # Complete failure
            message = f"❌ {goal} failed to complete"
            details = f"Failed steps: {', '.join(failed_steps)}"
            status = "error"
        elif failed_steps:
            # Partial success
            message = f"⚠️ {goal} completed with some issues"
            details = f"Completed: {', '.join(successful_steps)}\nFailed: {', '.join(failed_steps)}"
            status = "partial_success"
        else:
            # Full success
            message = f"✅ {goal} completed successfully"
            details = f"Steps completed: {', '.join(successful_steps)}" if successful_steps else "Task completed."
            status = "success"

        # Try to execute reply_to_user tool first
        reply_result = None
        try:
            reply_tool = self._get_tool_by_name("reply_to_user")
            if reply_tool:
                reply_params = {
                    "message": message,
                    "details": details,
                    "artifacts": key_artifacts[:5],  # Limit artifacts to prevent overload
                    "status": status
                }

                logger.info(f"[REPLY ENFORCEMENT] Executing automatic reply_to_user: {reply_params}")

                reply_result = reply_tool.invoke(reply_params)
                if reply_result.get("error"):
                    logger.error(f"[REPLY ENFORCEMENT] Automatic reply_to_user returned error: {reply_result}")
                    reply_result = None  # Fall through to manual creation
                else:
                    logger.info(f"[REPLY ENFORCEMENT] ✅ Automatic reply_to_user executed successfully")
            else:
                logger.warning("[REPLY ENFORCEMENT] reply_to_user tool not found in registry - creating manual reply")
        except Exception as e:
            logger.error(f"[REPLY ENFORCEMENT] Exception executing reply_to_user tool: {e}", exc_info=True)
            # Fall through to manual creation

        # CRITICAL: If tool execution failed or tool not found, create reply manually
        # This ensures we ALWAYS have a reply, preventing stuck "processing" state
        if not reply_result:
            logger.warning("[REPLY ENFORCEMENT] Creating manual reply payload as fallback")
            reply_result = {
                "type": "reply",
                "message": message,
                "details": details,
                "artifacts": key_artifacts[:5],
                "status": status,
                "error": False
            }
            logger.info(f"[REPLY ENFORCEMENT] ✅ Created manual reply payload")

        # Add the reply result to step_results with a synthetic step ID
        synthetic_step_id = f"auto_reply_{len(steps)}"
        state["step_results"][synthetic_step_id] = reply_result
        logger.info(f"[REPLY ENFORCEMENT] ✅ Reply added to step_results (step {synthetic_step_id})")

    def _build_failure_summary(
        self,
        steps: List[Dict[str, Any]],
        step_results: Dict[Any, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Build a concise failure summary from step results.

        Returns:
            Optional dict with headline, details_lines, details_text, status, and failure_count.
        """
        if not step_results:
            return None

        step_index: Dict[Any, Dict[str, Any]] = {}
        for step in steps or []:
            step_id = step.get("id")
            if step_id is None:
                continue
            step_index[step_id] = step
            step_index[str(step_id)] = step

        failures: List[Dict[str, str]] = []
        success_count = 0

        for step_id, result in step_results.items():
            if not isinstance(result, dict):
                continue
            if result.get("type") == "reply":
                continue

            status_value = str(result.get("status", "")).lower()
            is_error = bool(result.get("error")) or status_value in {"error", "failed", "timeout"}

            if is_error:
                step_meta = step_index.get(step_id) or step_index.get(str(step_id))
                action_name = ""
                if step_meta:
                    action_name = step_meta.get("action") or step_meta.get("description") or ""
                if not action_name:
                    action_name = str(step_id)

                tool_name = result.get("tool")
                label_parts = [action_name]
                if tool_name and tool_name != action_name:
                    label_parts.append(tool_name)
                label = " → ".join(part for part in label_parts if part)

                reason = (
                    result.get("error_message")
                    or result.get("message")
                    or result.get("details")
                    or status_value
                    or "Unknown error"
                )
                if isinstance(reason, str):
                    reason_clean = " ".join(reason.split())
                else:
                    reason_clean = str(reason)

                if len(reason_clean) > 120:
                    reason_clean = reason_clean[:117] + "..."

                failures.append({"label": label, "reason": reason_clean})
            else:
                success_count += 1

        if not failures:
            return None

        failure_strings = [f"{entry['label']}: {entry['reason']}" for entry in failures]
        headline_core = "; ".join(failure_strings[:3])
        headline = f"Here's what failed: {headline_core}"
        details_lines = [f"- {entry['label']}: {entry['reason']}" for entry in failures]
        details_text = "\n".join(details_lines)
        status = "partial_success" if success_count > 0 else "error"

        return {
            "headline": headline,
            "details_lines": details_lines,
            "details_text": details_text,
            "status": status,
            "failure_count": len(failures),
        }

    def finalize(self, state: AgentState) -> AgentState:
        """
        Finalization node: Summarize results and verify commitments were fulfilled.
        """
        logger.info("=== FINALIZING ===")

        # Telemetry: Start finalize phase span
        correlation_id = state.get("correlation_id")
        finalize_span = None
        if correlation_id:
            from telemetry.tool_helpers import create_tool_span, record_event, record_reply_status
            finalize_span = create_tool_span("finalize", correlation_id)
            finalize_span.set_attribute("phase", "finalization")
            record_event(finalize_span, "finalization_started", {"correlation_id": correlation_id})

        # Handle case where plan has no steps (impossible task already set error)
        steps = state.get("steps") or []

        # Don't override statuses already set (error/cancelled)
        if state.get("status") == "error":
            logger.info("Final status: error (preserved from earlier stage)")
            if finalize_span and StatusCode:
                _safe_set_span_status(finalize_span, StatusCode.OK, "error_status_preserved")
                record_event(finalize_span, "finalization_completed", {"status": "error_preserved"})
                finalize_span.end()
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
            # Capture cancellation result for non-blocking return
            result_capture = state.get("result_capture")
            if result_capture:
                result_capture.set(summary)
                logger.info("[FINALIZE] Cancellation result captured in ResultCapture")

            # Telemetry: Record cancelled reply status
            if correlation_id:
                record_reply_status("reply_cancelled", correlation_id, {"reason": summary["message"]})

            logger.info("Final status: cancelled")
            if finalize_span and StatusCode:
                _safe_set_span_status(finalize_span, StatusCode.OK, "cancelled")
                record_event(finalize_span, "finalization_completed", {"status": "cancelled"})
                finalize_span.end()
            return state

        existing_step_results = state.get("step_results") or {}
        had_reply_before_enforcement = any(
            isinstance(res, dict) and res.get("type") == "reply"
            for res in existing_step_results.values()
        )
        failure_summary_applied = False
        
        # CRITICAL: Final commitment verification using reasoning trace
        memory = state.get("memory")
        interaction_id = state.get("interaction_id")
        if memory and memory.is_reasoning_trace_enabled():
            try:
                self._verify_commitments_fulfilled(state, memory)
            except Exception as e:
                logger.error(f"[FINALIZE] Error during commitment verification: {e}")

        # CRITICAL: Enforce reply_to_user as final step
        logger.info("[FINALIZE] Enforcing reply_to_user as final step")
        self._enforce_reply_to_user_final_step(state)
        
        # Log reply enforcement result
        step_results_after = state.get("step_results", {})
        has_reply_after = any(
            isinstance(r, dict) and r.get("type") == "reply"
            for r in step_results_after.values()
        )
        if has_reply_after:
            logger.info("[FINALIZE] ✅ Reply confirmed in step_results after enforcement")
            # Telemetry: Record successful reply status
            if correlation_id:
                record_reply_status("reply_sent", correlation_id, {"enforced": not had_reply_before_enforcement})
        else:
            logger.error("[FINALIZE] ❌ CRITICAL: No reply found in step_results after enforcement!")
            # Telemetry: Record missing reply status
            if correlation_id:
                record_reply_status("reply_missing", correlation_id, {
                    "had_reply_before": had_reply_before_enforcement,
                    "step_result_keys": list(step_results_after.keys())
                })

            try:
                get_performance_monitor().record_alert(
                    "missing_reply_payload",
                    "Finalize completed without reply payload",
                    {
                        "goal": state.get("goal", ""),
                        "status": state.get("status"),
                        "step_result_keys": list(step_results_after.keys()),
                    },
                )
            except Exception as alert_exc:
                logger.error(f"[FINALIZE] Failed to record telemetry alert: {alert_exc}")

        # Gather all results
        step_results_dict = state.get("step_results", {})
        logger.info(f"[FINALIZE] Gathering results: {len(step_results_dict)} step results")
        summary = {
            "goal": state.get("goal", ""),
            "steps_executed": len(steps),
            "results": step_results_dict,        # Legacy key
            "step_results": step_results_dict,   # API server expects this
            "status": "success" if all(
                not (isinstance(r, dict) and r.get("error", False))
                for r in step_results_dict.values()
            ) else "partial_success"
        }

        # Prefer dedicated reply payload for user-facing communication
        step_results = state.get("step_results", {})
        reply_payload = None
        reply_step_id = None
        for step_id, step_result in step_results.items():
            if isinstance(step_result, dict) and step_result.get("type") == "reply":
                reply_payload = step_result
                reply_step_id = step_id
                summary["reply_step_id"] = step_id
                logger.info(f"[FINALIZE] Found reply_payload in step {step_id}: {reply_payload.get('message', '')[:50]}...")
                break
        
        if not reply_payload:
            logger.warning("[FINALIZE] ⚠️ No reply_payload found in step_results - summary will use fallback message")

        if reply_payload:
            summary["status"] = reply_payload.get("status", summary["status"])
            summary["message"] = reply_payload.get("message", "")
            if reply_payload.get("details"):
                summary["details"] = reply_payload["details"]
            if reply_payload.get("artifacts"):
                summary["artifacts"] = reply_payload["artifacts"]

        auto_reply_enforced = not had_reply_before_enforcement
        failure_summary_info = self._build_failure_summary(steps, step_results)
        if failure_summary_info and (auto_reply_enforced or not reply_payload):
            failure_summary_applied = True
            summary["status"] = failure_summary_info["status"]
            summary["message"] = failure_summary_info["headline"]
            summary["details"] = failure_summary_info["details_text"]
            summary["failure_details"] = failure_summary_info["details_lines"]
            if reply_payload:
                reply_payload["status"] = summary["status"]
                reply_payload["message"] = summary["message"]
                reply_payload["details"] = failure_summary_info["details_text"]
                if reply_step_id is not None:
                    step_results[reply_step_id] = reply_payload
            logger.info("[FINALIZE] Applied synthesized failure summary for missing reply_to_user execution")

        # GUARANTEED REPLY FALLBACK: Ensure we ALWAYS have a user-facing message
        # This is the final safety net when all other reply mechanisms fail
        current_message = summary.get("message", "").strip()
        if not current_message or len(current_message) < 10:
            logger.warning("[FINALIZE] ❌ CRITICAL: No meaningful message found, applying guaranteed fallback")

            # Analyze what went wrong for telemetry
            failed_tools = []
            successful_tools = []
            for step_id, step_result in step_results.items():
                if isinstance(step_result, dict):
                    tool_name = step_result.get("tool", "unknown")
                    if step_result.get("error"):
                        failed_tools.append(tool_name)
                    elif step_result.get("success") or not step_result.get("error", True):
                        successful_tools.append(tool_name)

            # Telemetry: Record fallback usage with root cause analysis
            if correlation_id:
                from telemetry.tool_helpers import record_reply_status
                record_reply_status("fallback_used", correlation_id, {
                    "reason": "no_meaningful_message",
                    "failed_tools": failed_tools,
                    "successful_tools": successful_tools,
                    "had_reply_payload": reply_payload is not None,
                    "failure_summary_applied": failure_summary_applied
                })

            # Generate guaranteed fallback message
            user_request = state.get("user_request", "your request")
            if failed_tools:
                fallback_message = f"I encountered issues completing your request for '{user_request[:50]}...'. Some tools failed ({', '.join(failed_tools[:3])}). Please try rephrasing or contact support if the issue persists."
            else:
                fallback_message = f"I processed your request for '{user_request[:50]}...' but couldn't generate a proper response. Please try again or provide more details."

            summary["message"] = fallback_message
            summary["status"] = "error"
            summary["fallback_applied"] = True
            summary["root_cause_tools"] = failed_tools

            logger.info(f"[FINALIZE] ✅ Applied guaranteed fallback reply: {fallback_message[:100]}...")

        # Always check step_results for richer message if current message is generic/short
        # This handles cases where reply agent gives generic message but search has detailed summary
        current_message = summary.get("message", "")
        if step_results and len(current_message) < 100 and not failure_summary_applied and not summary.get("fallback_applied"):
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

                if email_result.get("duplicate_prevented"):
                    duplicate_note = email_message or "Email was already sent recently; skipped duplicate send."
                    summary["status"] = "success"
                    if base_message:
                        summary["message"] = f"{base_message.rstrip('. ')}. {duplicate_note}"
                    else:
                        summary["message"] = duplicate_note
                elif email_status_value == "sent":
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

                if verification_result and verification_result.get("error"):
                    playback_success = False
                    failure_details = (
                        verification_result.get("error_message")
                        if verification_result and verification_result.get("error_message")
                        else "Could not verify Spotify playback status."
                    )
                else:
                    verification_status = (verification_result.get("status") or "").lower()
                    # Accept "playing" status, or if there's track info (even paused), consider it success
                    # since we successfully initiated playback
                    has_track_info = bool(verification_result.get("track") or verification_result.get("track_artist"))

                    if verification_status == "playing":
                        # Perfect - actively playing
                        pass
                    elif has_track_info and verification_status in ["paused", "stopped", ""]:
                        # Track is loaded but not actively playing (common with Web Player)
                        # Still consider this success since playback was initiated
                        logger.info(f"[AGENT] Playback verification: track loaded but {verification_status}, accepting as success")
                    elif has_track_info:
                        # Some other status but track info exists
                        logger.info(f"[AGENT] Playback verification: track loaded with status '{verification_status}', accepting as success")
                    else:
                        # No track info and not playing - this is a failure
                        playback_success = False
                        failure_details = verification_result.get("message") or "Spotify is not reporting playback."

            if playback_success and playback_success_message:
                # Use track info from play_step_result if available (most accurate)
                # Only use verification_result for status check, not for track identification
                if play_step_result:
                    track = play_step_result.get("track") or play_step_result.get("song_name")
                    artist = play_step_result.get("track_artist") or play_step_result.get("artist")
                    if track and artist:
                        # Override the generic success message with specific track info
                        playback_success_message = f"Now playing: {track} by {artist}. Started playback in Spotify."
                _append_summary_message(playback_success_message)

            if not playback_success:
                if summary["status"] == "success":
                    summary["status"] = "partial_success"

                # Provide more informative messages - prefer play_step_result track info over verification_result
                track = None
                artist = None
                status = None
                
                # First, try to get track info from play_step_result (most accurate)
                if play_step_result:
                    track = play_step_result.get("track") or play_step_result.get("song_name")
                    artist = play_step_result.get("track_artist") or play_step_result.get("artist")
                
                # Fall back to verification_result only if play_step_result doesn't have track info
                if not track and verification_result and not verification_result.get("error"):
                    track = verification_result.get("track")
                    artist = verification_result.get("track_artist") or verification_result.get("artist")
                    status = verification_result.get("status", "").lower()

                if track and artist:
                    if status == "paused":
                        note = f"Track loaded and ready: {track} by {artist} (currently paused)"
                    elif status == "stopped":
                        note = f"Track loaded: {track} by {artist} (playback stopped)"
                    elif status:
                        note = f"Track loaded: {track} by {artist} (status: {status})"
                    else:
                        note = f"Track loaded: {track} by {artist}"
                elif verification_result and not verification_result.get("error"):
                    note = verification_result.get("message") or playback_failure_message
                else:
                    note = failure_details or playback_failure_message

                _append_summary_message(note)

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

        # Persist interaction outcome to session memory
        if memory and interaction_id:
            interaction_metadata = {
                "goal": summary.get("goal", ""),
                "status": summary.get("status", "unknown"),
                "correlation_id": correlation_id,
                "steps_executed": summary.get("steps_executed"),
                "completed_at": datetime.now().isoformat()
            }

            updated = memory.update_interaction(
                interaction_id,
                agent_response=summary,
                plan=steps,
                step_results=step_results_dict,
                metadata=interaction_metadata
            )

            if not updated:
                logger.warning(f"[FINALIZE] Failed to update interaction {interaction_id} in session memory")

        # CRITICAL: Capture result immediately so agent.run() can return even if graph.invoke() hangs
        result_capture = state.get("result_capture")
        if result_capture:
            result_capture.set(summary)
            logger.info("[FINALIZE] Result captured in ResultCapture for non-blocking return")

        logger.info(f"[FINALIZE] ✅ Final result set with status: {summary.get('status')}, message: {summary.get('message', '')[:50]}...")
        logger.info(f"[FINALIZE] Final result keys: {list(summary.keys())}")
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

        # Telemetry: Record finalize completion
        if finalize_span:
            finalize_span.set_attribute("final_status", summary.get("status"))
            finalize_span.set_attribute("has_reply", has_reply_after)
            finalize_span.set_attribute("fallback_used", failure_summary_applied)
            record_event(finalize_span, "finalization_completed", {
                "status": summary.get("status"),
                "has_reply": has_reply_after,
                "message_length": len(summary.get("message", "")),
                "steps_executed": len(steps)
            })
            finalize_span.end()

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

    def _verify_email_content(self, state: AgentState, step: Dict[str, Any], resolved_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify that compose_email parameters contain what the user requested.
        
        Uses LLM to check if email body/attachments include the requested content
        (links, files, reports, etc.) and suggests corrections if needed.
        
        Also uses reasoning trace to check past attempts and commitments.
        
        Args:
            state: Current agent state with user request and step results
            step: Current compose_email step
            resolved_params: Resolved parameters for compose_email
            
        Returns:
            Verification result with verified flag and suggestions
        """
        try:
            from .email_content_verifier import verify_compose_email_content
            
            user_request = state.get("original_user_request") or state.get("user_request", "")
            step_results = state.get("step_results", {})
            step_id = step.get("id", "unknown")
            memory = state.get("memory")
            
            logger.info(f"[EMAIL VERIFICATION] Verifying content for compose_email step {step_id}")
            
            # Get reasoning context if available
            reasoning_context = None
            if memory and memory.is_reasoning_trace_enabled():
                try:
                    reasoning_summary = memory.get_reasoning_summary()
                    reasoning_context = {
                        "commitments": reasoning_summary.get("commitments", []),
                        "past_attempts": memory.get_interaction_count(),
                        "trace_available": True
                    }
                    logger.debug(f"[EMAIL VERIFICATION] Using reasoning trace context: {reasoning_context}")
                except Exception as e:
                    logger.warning(f"[EMAIL VERIFICATION] Could not get reasoning context: {e}")
            
            verification_result = verify_compose_email_content(
                user_request=user_request,
                compose_email_params=resolved_params,
                step_results=step_results,
                current_step_id=step_id,
                reasoning_context=reasoning_context
            )
            
            # Record verification in reasoning trace
            if memory and memory.is_reasoning_trace_enabled():
                try:
                    memory.add_reasoning_entry(
                        stage="verification",
                        thought=f"Verifying compose_email content before execution",
                        action="email_content_verification",
                        outcome="success" if verification_result.get("verified") else "partial",
                        evidence=[
                            f"Verified: {verification_result.get('verified')}",
                            f"Missing: {verification_result.get('missing_items', [])}",
                            verification_result.get('reasoning', '')[:200]
                        ],
                        commitments=["send_email"] if not verification_result.get('verified') else []
                    )
                except Exception as e:
                    logger.debug(f"[REASONING TRACE] Failed to add verification entry: {e}")
            
            return verification_result
            
        except Exception as e:
            logger.error(f"[EMAIL VERIFICATION] Error during verification: {e}")
            # On error, allow email to proceed (fail open)
            return {
                "verified": True,
                "missing_items": [],
                "suggestions": {},
                "reasoning": f"Verification skipped due to error: {e}"
            }

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
            "create_keynote"
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
        on_plan_created: Optional[callable] = None,
        on_step_started: Optional[callable] = None,
        on_step_succeeded: Optional[callable] = None,
        on_step_failed: Optional[callable] = None
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
            
            if not is_command:
                # Unsupported slash command - strip leading slash and fall through to orchestrator
                # This allows commands like /maps to be treated as natural language
                logger.debug(f"[SLASH COMMANDS] Ignoring unsupported command: {user_request[:50]}")
                # Remove leading slash and command word, keep the rest as natural language
                parts = user_request.strip().split(None, 1)
                if len(parts) > 1:
                    user_request = parts[1]  # Keep task part only
                else:
                    user_request = user_request.lstrip('/').strip()  # Remove slash if no task
                # Continue to orchestrator with cleaned message
            
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

        # Check for natural language explain commands
        user_request_lower = user_request.lower().strip()

        # Simple delivery intent check to avoid conflicts
        delivery_verbs = ["email", "send", "mail", "attach"]
        has_delivery_intent = any(
            f"{verb} it" in user_request_lower or
            f"{verb} the" in user_request_lower or
            f"{verb} me" in user_request_lower or
            f"{verb} to" in user_request_lower
            for verb in delivery_verbs
        )

        explain_exclusion_keywords = [
            "bluesky",
            "bsky",
            "sky feed",
            "bluesky feed",
            "twitter",
            "tweet",
            "tweets",
            "post on bluesky",
            "bluesky post",
            "x post",
            "timeline",
        ]

        if ((user_request_lower.startswith('explain ') or
             user_request_lower.startswith('summarize ') or
             user_request_lower.startswith('summarise ') or
             user_request_lower.startswith('describe ') or
             user_request_lower.startswith('what is ') or
             user_request_lower.startswith('tell me about ')) and
                not has_delivery_intent and
                not any(keyword in user_request_lower for keyword in explain_exclusion_keywords)):
            # This is a standalone explain request - use the ExplainPipeline service
            try:
                from ..services.explain_pipeline import ExplainPipeline
                from ..agent.agent_registry import AgentRegistry

                registry = AgentRegistry(self.config, session_manager=self.session_manager)
                explain_pipeline = ExplainPipeline(registry)
                result = explain_pipeline.execute(user_request, session_id)

                # Format result to match agent.run() return format
                if result.get("success"):
                    return {
                        "status": "success",
                        "message": result.get("summary", "Explanation completed"),
                        "final_result": result,
                        "results": {1: result}
                    }
                else:
                    return {
                        "status": "error",
                        "message": result.get("error_message", "Explanation failed"),
                        "final_result": result,
                        "results": {1: result}
                    }
            except Exception as e:
                logger.error(f"[AGENT] Explain pipeline error: {e}")
                # Fall through to normal agent processing

        # Initialize telemetry tracking
        telemetry = get_telemetry()
        correlation_id = telemetry.start_request(user_request, session_id or "no_session", context)

        # Get session context if available
        session_context = None
        memory = None
        interaction_id = None
        user_id = context.get("user_id", "default_user") if context else "default_user"

        if self.session_manager and session_id:
            memory = self.session_manager.get_or_create_session(session_id, user_id)
            session_context = self.session_manager.get_langgraph_context(session_id)
            logger.info(f"[SESSION] Loaded context for session: {user_id}/{session_id}")

            if memory:
                # Pre-register interaction so we can update it once execution finishes.
                interaction_metadata = {
                    "status": "in_progress",
                    "correlation_id": correlation_id
                }
                interaction_id = memory.add_interaction(
                    user_request=user_request,
                    agent_response=None,
                    plan=[],
                    step_results={},
                    metadata=interaction_metadata
                )

                # Start reasoning trace if enabled
                if memory.is_reasoning_trace_enabled():
                    memory.start_reasoning_trace(interaction_id)
                    logger.debug(f"[REASONING TRACE] Started trace for interaction {interaction_id}")

        # Record initial reasoning step
        telemetry.record_reasoning_step(correlation_id, "request_received",
                                       f"User request: {user_request[:200]}...",
                                       {"session_id": session_id, "user_id": user_id})
        
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
            "correlation_id": correlation_id,  # Add correlation ID for telemetry
            "vision_usage": {
                "count": 0,
                "session_count": session_vision_count
            },
            "recent_errors": {},
            "planning_context": context or {},  # Add planning context (e.g., intent_hints from slash commands)
            "on_plan_created": on_plan_created,  # Store callback in state for plan_task to access
            "sequence_number": 0,  # Initialize sequence counter for plan streaming
            "on_step_started": on_step_started,  # Store step callbacks for live progress tracking
            "on_step_succeeded": on_step_succeeded,
            "on_step_failed": on_step_failed,
            "memory": memory,  # Store memory reference for trace instrumentation
            "interaction_id": interaction_id  # Store interaction_id for trace instrumentation
        }

        # Query persistent memory for relevant context
        persistent_memory = []
        if memory and memory.user_memory_store:
            try:
                # Query memories relevant to the current request
                relevant_memories = memory.user_memory_store.query_memories(
                    text=user_request,
                    top_k=5,
                    min_score=0.7
                )

                # Format for planning context
                persistent_memory = [
                    {
                        "content": mem.content,
                        "category": mem.category,
                        "tags": mem.tags,
                        "salience_score": score,
                        "source": "persistent_memory"
                    }
                    for mem, score in relevant_memories
                ]

                if persistent_memory:
                    logger.debug(f"[PERSISTENT MEMORY] Retrieved {len(persistent_memory)} relevant memories for planning")

            except Exception as e:
                logger.error(f"[PERSISTENT MEMORY] Failed to query memories: {e}")

        # Add persistent memory to planning context
        initial_state["planning_context"]["persistent_memory"] = persistent_memory

        # Create result capture for non-blocking execution
        result_capture = ResultCapture()
        initial_state["result_capture"] = result_capture

        # Run graph with non-blocking result capture
        # This allows us to return as soon as finalize() sets the result,
        # even if graph.invoke() continues running in the background
        try:
            import concurrent.futures
            import threading
            
            graph_start_time = time.time()
            logger.info(f"[AGENT] Starting graph.invoke() at {graph_start_time}")
            
            def run_graph():
                """Run graph.invoke in a separate thread."""
                try:
                    invoke_start = time.time()
                    final_state = self.graph.invoke(initial_state)
                    invoke_duration = time.time() - invoke_start
                    logger.info(f"[AGENT] graph.invoke() completed in {invoke_duration:.2f}s")
                    return final_state
                except Exception as e:
                    logger.error(f"[AGENT] graph.invoke() error: {e}")
                    raise
            
            # Create executor outside context manager to avoid blocking on shutdown
            # This allows us to return immediately after result capture
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            graph_future = executor.submit(run_graph)
            
            # Define callback to handle final_state logging when graph completes
            def handle_graph_completion(future):
                """Callback to log session data when graph execution completes."""
                captured_result = None
                try:
                    final_state = future.result()
                    if self.session_manager and session_id:
                        memory = self.session_manager.get_or_create_session(session_id)
                        vision_usage = final_state.get("vision_usage", {})
                        if vision_usage:
                            memory.shared_context["vision_session_count"] = vision_usage.get("session_count", 0)

                        # Get the result that was already captured
                        captured_result = result_capture.get()
                        if captured_result:
                            if interaction_id:
                                updated = memory.update_interaction(
                                    interaction_id,
                                    agent_response=captured_result,
                                    plan=final_state.get("steps", []),
                                    step_results=final_state.get("step_results", {}),
                                    metadata={
                                        "goal": final_state.get("goal", ""),
                                        "status": final_state.get("status", "unknown"),
                                        "correlation_id": correlation_id
                                    }
                                )
                                if not updated:
                                    logger.warning(f"[SESSION] Failed to update interaction {interaction_id} during completion callback")
                            else:
                                logger.warning("[SESSION] interaction_id missing; creating fallback interaction entry")
                                memory.add_interaction(
                                    user_request=user_request,
                                    agent_response=captured_result,
                                    plan=final_state.get("steps", []),
                                    step_results=final_state.get("step_results", {}),
                                    metadata={
                                        "goal": final_state.get("goal", ""),
                                        "status": final_state.get("status", "unknown"),
                                        "correlation_id": correlation_id
                                    }
                                )

                            self.session_manager.save_session(session_id)
                            logger.info(f"[SESSION] Recorded full interaction for session: {session_id} (after graph completion)")

                    # Record final telemetry completion
                    telemetry.end_request(correlation_id, captured_result)

                except Exception as e:
                    logger.warning(f"[AGENT] Error in graph completion callback: {e}")
                    # Record error in telemetry
                    telemetry.record_phase_end(correlation_id, "complete", success=False,
                                             error_message=str(e), metadata={"callback_error": True})
                finally:
                    # Shutdown executor without waiting (non-blocking)
                    executor.shutdown(wait=False)
            
            # Register callback to run when graph completes
            graph_future.add_done_callback(handle_graph_completion)
            
            # Wait for result capture (finalize() will set it)
            # No timeout - agents should run until completion
            logger.info(f"[AGENT] Waiting for result capture (no timeout - agents run until completion)...")
            
            captured_result = result_capture.wait(timeout=None)
            
            if captured_result:
                capture_wait_duration = time.time() - graph_start_time
                logger.info(f"[AGENT] Result captured after {capture_wait_duration:.2f}s, returning immediately")
                logger.info(f"[AGENT] graph.invoke() may still be running in background for cleanup")
                
                # Try to get final_state quickly for immediate logging (non-blocking)
                final_state = None
                if self.session_manager and session_id:
                    memory = self.session_manager.get_or_create_session(session_id)
                    try:
                        final_state = graph_future.result(timeout=1.0)
                    except (concurrent.futures.TimeoutError, concurrent.futures.CancelledError):
                        # Graph still running - that's fine, callback will handle it
                        final_state = None
                    
                    if final_state:
                        # Graph completed quickly, log immediately
                        vision_usage = final_state.get("vision_usage", {})
                        if vision_usage:
                            memory.shared_context["vision_session_count"] = vision_usage.get("session_count", 0)
                        if interaction_id:
                            updated = memory.update_interaction(
                                interaction_id,
                                agent_response=captured_result,
                                plan=final_state.get("steps", []),
                                step_results=final_state.get("step_results", {}),
                                metadata={
                                    "goal": final_state.get("goal", ""),
                                    "status": final_state.get("status", "unknown"),
                                    "correlation_id": correlation_id
                                }
                            )
                            if not updated:
                                logger.warning(f"[SESSION] Failed to update interaction {interaction_id} after quick completion")
                        else:
                            logger.warning("[SESSION] interaction_id missing; recording fallback interaction entry")
                            memory.add_interaction(
                                user_request=user_request,
                                agent_response=captured_result,
                                plan=final_state.get("steps", []),
                                step_results=final_state.get("step_results", {}),
                                metadata={
                                    "goal": final_state.get("goal", ""),
                                    "status": final_state.get("status", "unknown"),
                                    "correlation_id": correlation_id
                                }
                            )
                        self.session_manager.save_session(session_id)
                        logger.info(f"[SESSION] Recorded interaction for session: {session_id}")
                    else:
                        # Graph still running, record with available result
                        # Callback will update with full state later
                        logger.debug(f"[SESSION] Recording interaction while graph may still be running")
                        if interaction_id:
                            updated = memory.update_interaction(
                                interaction_id,
                                agent_response=captured_result,
                                plan=[],
                                step_results={},
                                metadata={
                                    "goal": "",
                                    "status": captured_result.get("status", "unknown"),
                                    "correlation_id": correlation_id
                                }
                            )
                            if not updated:
                                logger.warning(f"[SESSION] Failed to update interaction {interaction_id} while graph still running")
                        else:
                            logger.warning("[SESSION] interaction_id missing during interim update; creating fallback entry")
                            memory.add_interaction(
                                user_request=user_request,
                                agent_response=captured_result,
                                plan=[],
                                step_results={},
                                metadata={
                                    "goal": "",
                                    "status": captured_result.get("status", "unknown"),
                                    "correlation_id": correlation_id
                                }
                            )
                        self.session_manager.save_session(session_id)
                
                # Return immediately - executor and callback handle cleanup
                result = captured_result
            else:
                # Result capture never fired - fall back to waiting for graph.invoke()
                # No timeout - wait indefinitely for graph completion
                logger.warning(f"[AGENT] Result capture not set, waiting for graph.invoke() (no timeout)...")
                try:
                    final_state = graph_future.result(timeout=None)  # Wait indefinitely
                    result = final_state.get("final_result") or {
                        "error": True,
                        "message": "Graph completed but no result captured"
                    }
                    logger.info(f"[AGENT] Retrieved result from graph.invoke() after capture timeout")
                    
                    # Log session data
                    if self.session_manager and session_id:
                        memory = self.session_manager.get_or_create_session(session_id)
                        vision_usage = final_state.get("vision_usage", {})
                        if vision_usage:
                            memory.shared_context["vision_session_count"] = vision_usage.get("session_count", 0)
                        if interaction_id:
                            updated = memory.update_interaction(
                                interaction_id,
                                agent_response=result,
                                plan=final_state.get("steps", []),
                                step_results=final_state.get("step_results", {}),
                                metadata={
                                    "goal": final_state.get("goal", ""),
                                    "status": final_state.get("status", "unknown"),
                                    "correlation_id": correlation_id
                                }
                            )
                            if not updated:
                                logger.warning(f"[SESSION] Failed to update interaction {interaction_id} after graph completion fallback")
                        else:
                            logger.warning("[SESSION] interaction_id missing; recording fallback interaction entry after graph completion")
                            memory.add_interaction(
                                user_request=user_request,
                                agent_response=result,
                                plan=final_state.get("steps", []),
                                step_results=final_state.get("step_results", {}),
                                metadata={
                                    "goal": final_state.get("goal", ""),
                                    "status": final_state.get("status", "unknown"),
                                    "correlation_id": correlation_id
                                }
                            )
                        self.session_manager.save_session(session_id)
                except concurrent.futures.TimeoutError:
                    logger.error(f"[AGENT] graph.invoke() also timed out - agent may be stuck")
                    result = {
                        "error": True,
                        "message": "Agent execution timed out - finalize() may not have completed"
                    }
                finally:
                    # Shutdown executor
                    executor.shutdown(wait=False)

            total_duration = time.time() - graph_start_time
            logger.info(f"[AGENT] Total agent.run() duration: {total_duration:.2f}s")
            return result

        except Exception as e:
            logger.error(f"Agent execution error: {e}", exc_info=True)
            return {
                "error": True,
                "message": f"Agent failed: {str(e)}"
            }
