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

from .tools import ALL_TOOLS

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
        workflow.add_edge("plan", "execute_step")

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

        planning_prompt = f"""
{system_prompt}

{task_decomp_prompt}

{few_shot_examples}

User Request: "{state['user_request']}"

Decompose this request into executable steps using the available tools.
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
        steps = state["steps"]

        if current_idx >= len(steps):
            state["status"] = "completed"
            return state

        step = steps[current_idx]
        logger.info(f"=== EXECUTING STEP {step['id']}: {step['action']} ===")
        logger.info(f"Reasoning: {step['reasoning']}")

        # Resolve parameters (handle context variables like $step1.doc_path)
        resolved_params = self._resolve_parameters(step["parameters"], state["step_results"])
        logger.info(f"Resolved parameters: {resolved_params}")

        # Get tool
        tool_name = step["action"]
        tool = next((t for t in ALL_TOOLS if t.name == tool_name), None)

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

        # Gather all results
        summary = {
            "goal": state["goal"],
            "steps_executed": len(state["steps"]),
            "results": state["step_results"],
            "status": "success" if all(
                not r.get("error", False) for r in state["step_results"].values()
            ) else "partial_success"
        }

        state["final_result"] = summary
        state["status"] = "completed"

        logger.info(f"Final status: {summary['status']}")

        return state

    def _should_continue(self, state: AgentState) -> str:
        """Decide whether to continue executing steps or finalize."""
        if state["current_step"] >= len(state["steps"]):
            return "finalize"
        return "continue"

    def _resolve_parameters(
        self,
        params: Dict[str, Any],
        step_results: Dict[int, Any]
    ) -> Dict[str, Any]:
        """
        Resolve context variables in parameters.

        Example: "$step1.doc_path" -> "/path/to/doc.pdf"
        """
        resolved = {}

        for key, value in params.items():
            if isinstance(value, str) and value.startswith("$step"):
                # Parse context variable: $step1.doc_path
                parts = value[1:].split(".")
                if len(parts) == 2:
                    step_ref, field = parts
                    step_id = int(step_ref.replace("step", ""))

                    if step_id in step_results:
                        result = step_results[step_id]
                        resolved[key] = result.get(field, value)
                    else:
                        logger.warning(f"Step {step_id} result not found for {value}")
                        resolved[key] = value
                else:
                    resolved[key] = value
            elif isinstance(value, list):
                # Handle lists (e.g., attachments)
                resolved[key] = [
                    self._resolve_single_value(v, step_results) for v in value
                ]
            else:
                resolved[key] = value

        return resolved

    def _resolve_single_value(self, value: Any, step_results: Dict[int, Any]) -> Any:
        """Resolve a single value that might be a context variable."""
        if isinstance(value, str) and value.startswith("$step"):
            parts = value[1:].split(".")
            if len(parts) == 2:
                step_ref, field = parts
                step_id = int(step_ref.replace("step", ""))
                if step_id in step_results:
                    return step_results[step_id].get(field, value)
        return value

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
