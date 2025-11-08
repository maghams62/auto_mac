"""
LangGraph agent with task decomposition and state management.
"""

from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import json
import logging
from pathlib import Path

from . import ALL_AGENT_TOOLS
from .verifier import OutputVerifier

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

    # Output
    final_result: Optional[Dict[str, Any]]
    status: str  # "planning" | "executing" | "completed" | "error"


class AutomationAgent:
    """
    LangGraph agent for task decomposition and execution.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.llm = ChatOpenAI(
            model=config.get("openai", {}).get("model", "gpt-4o"),
            temperature=0.0
        )

        # Initialize verifier
        self.verifier = OutputVerifier(config)

        # Load prompts
        self.prompts = self._load_prompts()

        # Build graph
        self.graph = self._build_graph()

    def _load_prompts(self) -> Dict[str, str]:
        """Load prompt templates from markdown files."""
        prompts_dir = Path(__file__).parent.parent.parent / "prompts"

        prompts = {}
        for prompt_file in ["system.md", "task_decomposition.md", "few_shot_examples.md"]:
            path = prompts_dir / prompt_file
            if path.exists():
                prompts[prompt_file.replace(".md", "")] = path.read_text()
            else:
                logger.warning(f"Prompt file not found: {path}")

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
            lambda state: "finalize" if state.get("status") == "error" else "execute",
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
        logger.info("=== PLANNING PHASE ===")
        logger.info(f"User request: {state['user_request']}")

        # Build planning prompt
        system_prompt = self.prompts.get("system", "")
        task_decomp_prompt = self.prompts.get("task_decomposition", "")
        few_shot_examples = self.prompts.get("few_shot_examples", "")

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

AVAILABLE TOOLS (COMPLETE LIST - DO NOT HALLUCINATE OTHER TOOLS):
{available_tools_list}

{few_shot_examples}

User Request: "{state['user_request']}"

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
        tool = next((t for t in ALL_AGENT_TOOLS if t.name == tool_name), None)

        if not tool:
            logger.error(f"Tool not found: {tool_name}")
            state["step_results"][step["id"]] = {
                "error": True,
                "message": f"Tool '{tool_name}' not found"
            }
        else:
            # Execute tool
            try:
                result = tool.invoke(resolved_params)
                logger.info(f"Step {step['id']} result: {result}")
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

            except Exception as e:
                logger.error(f"Error executing step {step['id']}: {e}")
                state["step_results"][step["id"]] = {
                    "error": True,
                    "message": str(e)
                }

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

        # Don't override error status if already set (e.g., from impossible task detection)
        if state.get("status") == "error":
            logger.info(f"Final status: error (preserved from planning)")
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

        state["final_result"] = summary
        state["status"] = "completed"

        logger.info(f"Final status: {summary['status']}")

        return state

    def _should_continue(self, state: AgentState) -> str:
        """Decide whether to continue executing steps or finalize."""
        steps = state.get("steps")
        if not steps or state["current_step"] >= len(steps):
            return "finalize"
        return "continue"

    def _resolve_parameters(
        self,
        params: Dict[str, Any],
        step_results: Dict[int, Any]
    ) -> Dict[str, Any]:
        """
        Resolve context variables in parameters.

        Handles both standalone variables and inline interpolation:
        - "$step1.doc_path" -> "/path/to/doc.pdf"
        - "Price is $step1.current_price" -> "Price is 225.50"
        """
        resolved = {}

        for key, value in params.items():
            if isinstance(value, str):
                # Check if entire value is a single context variable
                if value.startswith("$step") and "." in value:
                    parts = value[1:].split(".")
                    if len(parts) == 2:
                        step_ref, field = parts
                        try:
                            step_id = int(step_ref.replace("step", ""))
                            if step_id in step_results:
                                result = step_results[step_id]
                                resolved[key] = result.get(field, value)
                            else:
                                logger.warning(f"Step {step_id} result not found for {value}")
                                resolved[key] = value
                        except ValueError:
                            resolved[key] = value
                    else:
                        resolved[key] = value
                else:
                    # Handle inline variable interpolation using regex
                    import re
                    def replace_var(match):
                        var_name = match.group(0)  # e.g., "$step1.current_price"
                        parts = var_name[1:].split(".")  # ["step1", "current_price"]
                        if len(parts) == 2:
                            step_ref, field = parts
                            try:
                                step_id = int(step_ref.replace("step", ""))
                                if step_id in step_results:
                                    result = step_results[step_id]
                                    field_value = result.get(field, var_name)
                                    # Convert to string representation
                                    return str(field_value) if field_value is not None else var_name
                            except (ValueError, KeyError):
                                pass
                        return var_name

                    # Replace all $stepN.field patterns
                    resolved[key] = re.sub(r'\$step\d+\.\w+', replace_var, value)
            elif isinstance(value, list):
                # Handle lists (e.g., attachments)
                resolved[key] = [
                    self._resolve_single_value(v, step_results) for v in value
                ]
            else:
                resolved[key] = value

        return resolved

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

    def run(self, user_request: str) -> Dict[str, Any]:
        """
        Execute the agent workflow.

        Args:
            user_request: Natural language request

        Returns:
            Final result dictionary
        """
        logger.info(f"Starting agent for request: {user_request}")

        # Initialize state
        initial_state = {
            "user_request": user_request,
            "goal": "",
            "steps": [],
            "current_step": 0,
            "step_results": {},
            "verification_results": {},
            "messages": [],
            "final_result": None,
            "status": "planning"
        }

        # Run graph
        try:
            final_state = self.graph.invoke(initial_state)
            return final_state["final_result"]

        except Exception as e:
            logger.error(f"Agent execution error: {e}")
            return {
                "error": True,
                "message": f"Agent failed: {str(e)}"
            }
