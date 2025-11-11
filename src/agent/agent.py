"""
LangGraph agent with task decomposition and state management.
"""

from typing import TypedDict, Annotated, List, Dict, Any, Optional
from threading import Event
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import json
import logging
from pathlib import Path

from . import ALL_AGENT_TOOLS
from .feasibility_checker import FeasibilityChecker
from .verifier import OutputVerifier
from ..memory import SessionManager

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State for the automation agent."""
    # Input
    user_request: str

    # Planning
    goal: str
    steps: List[Dict[str, Any]]
    current_step: int

    # Execution
    step_results: Dict[int, Any]  # step_id -> result
    verification_results: Dict[int, Any]  # step_id -> verification result
    messages: List[Any]  # Conversation history

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


class AutomationAgent:
    """
    LangGraph agent for task decomposition and execution.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        session_manager: Optional[SessionManager] = None
    ):
        self.config = config
        
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
        for prompt_file in ["system.md", "task_decomposition.md"]:
            path = prompts_dir / prompt_file
            if path.exists():
                prompts[prompt_file.replace(".md", "")] = path.read_text()
            else:
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
        few_shot_examples = self.prompts.get("few_shot_examples", "")
        user_request_lower = full_user_request.lower()

        delivery_keywords = [" email", "email ", " send", "send ", " mail", "mail ", " attach", "attach "]
        needs_email_delivery = any(keyword in user_request_lower for keyword in delivery_keywords)

        delivery_guidance = ""
        if needs_email_delivery:
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

        # Parse JSON response
        try:
            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            json_str = response_text[json_start:json_end]
            plan = json.loads(json_str)

            logger.info(f"Plan created: {plan['goal']}")
            logger.info(f"Steps: {len(plan['steps'])}")

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
            state["messages"] = messages + [response]

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse plan JSON: {e}")
            logger.error(f"Response: {response_text}")
            state["status"] = "error"
            state["final_result"] = {
                "error": True,
                "message": "Failed to create execution plan"
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

        # Check if dependencies succeeded
        dependencies = step.get("dependencies", [])
        if dependencies:
            failed_deps = []
            for dep_id in dependencies:
                if dep_id in state["step_results"]:
                    if state["step_results"][dep_id].get("error", False):
                        failed_deps.append(dep_id)
                else:
                    failed_deps.append(dep_id)

            if failed_deps:
                logger.warning(f"Step {step['id']} skipped due to failed dependencies: {failed_deps}")
                state["step_results"][step["id"]] = {
                    "error": True,
                    "skipped": True,
                    "message": f"Skipped due to failed dependencies: {failed_deps}"
                }
                state["current_step"] = current_idx + 1
                return state

        # Resolve parameters (handle context variables like $step1.doc_path)
        resolved_params = self._resolve_parameters(step["parameters"], state["step_results"])
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

        if not tool:
            logger.error(f"Tool not found: {tool_name}")
            state["step_results"][step["id"]] = {
                "error": True,
                "message": f"Tool '{tool_name}' not found",
                "tool": tool_name
            }
            self._record_tool_error(state, tool_name, "Tool not found in registry")
        else:
            # Execute tool
            try:
                result = tool.invoke(resolved_params)
                logger.info(f"Step {step['id']} result: {result}")
                result.setdefault("tool", tool_name)
                state["step_results"][step["id"]] = result

                if result.get("error"):
                    self._record_tool_error(state, tool_name, result.get("error_message", "Unknown error"))
                else:
                    self._clear_tool_errors(state, tool_name)

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

            except Exception as e:
                logger.error(f"Error executing step {step['id']}: {e}")
                state["step_results"][step["id"]] = {
                    "error": True,
                    "message": str(e),
                    "tool": tool_name
                }
                self._record_tool_error(state, tool_name, str(e))

        # Move to next step
        state["current_step"] = current_idx + 1

        return state

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
            email_status_value = (email_result.get("status") or "").lower()
            email_message = email_result.get("message") or ""
            base_message = summary.get("message", "")

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
            step_id = step.get("id")
            if step_id is not None and action not in ["compose_email", "reply_to_user"]:
                candidate_body_steps.append(step_id)

        # Second pass: Validate and fix each step
        for step in steps:
            step_fixed = False
            action = step.get("action", "")
            params = step.get("parameters", {})
            step_id = step.get("id")

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
        step_results: Dict[int, Any]
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

        return resolve_params(params, step_results)

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

    def run(
        self,
        user_request: str,
        session_id: Optional[str] = None,
        cancel_event: Optional[Event] = None
    ) -> Dict[str, Any]:
        """
        Execute the agent workflow.

        Args:
            user_request: Natural language request
            session_id: Optional session ID for context tracking
            cancel_event: Optional threading.Event used to signal cancellation

        Returns:
            Final result dictionary
        """
        logger.info(f"Starting agent for request: {user_request}")

        # Check if this is a slash command and handle it directly
        if user_request.strip().startswith('/'):
            from ..ui.slash_commands import SlashCommandHandler
            from ..agent.agent_registry import AgentRegistry
            
            registry = AgentRegistry(self.config, session_manager=self.session_manager)
            handler = SlashCommandHandler(registry, self.config)
            is_command, result = handler.handle(user_request, session_id=session_id)
            
            if is_command:
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
                            "Command executed"
                        )
                        # Determine status: only mark as error if there's an explicit error field
                        # Otherwise, default to success if we have a message/summary/content
                        is_error = tool_result.get("error") is True
                        has_content = bool(message and message != "Command executed")
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
        if self.session_manager and session_id:
            session_context = self.session_manager.get_langgraph_context(session_id)
            logger.info(f"[SESSION] Loaded context for session: {session_id}")
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
            "recent_errors": {}
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
