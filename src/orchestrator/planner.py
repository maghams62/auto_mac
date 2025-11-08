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

from .tools_catalog import format_tool_catalog_for_prompt


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
        self.llm = ChatOpenAI(
            model=config.get("openai", {}).get("model", "gpt-4o"),
            temperature=0.2  # Lower temperature for structured planning
        )

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
            # Build the planning prompt
            prompt = self._build_planning_prompt(
                goal=goal,
                available_tools=available_tools,
                context=context,
                previous_plan=previous_plan,
                feedback=feedback
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
                return {
                    "success": True,
                    "plan": plan_data['steps'],
                    "reasoning": plan_data.get('reasoning', 'Plan created successfully'),
                    "error": None
                }
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
1. **LLM-Driven Decisions**: All parameters and choices must be determined by LLM reasoning, not hardcoded
2. **Tool Understanding**: Carefully read tool capabilities - some tools are COMPLETE and standalone
3. **Simplicity**: Prefer simple plans - if one tool can do everything, use just that tool
4. **Dependencies**: Clearly specify step dependencies
5. **Context Passing**: Use $stepN.field syntax to pass results between steps

CRITICAL RULES:
- If a tool description says "COMPLETE" or "STANDALONE", it handles everything - don't break it into sub-steps!
- Example: organize_files creates folders AND moves files - don't add separate "create_folder" steps
- Example: create_keynote_with_images handles images - don't manually process images first
- Read the "strengths" and "limits" of each tool carefully
- When in doubt, prefer fewer steps with more capable tools

OUTPUT FORMAT:
Respond with JSON containing:
{
  "reasoning": "Brief explanation of why this plan achieves the goal",
  "steps": [
    {
      "id": 1,
      "action": "tool_name",
      "parameters": {
        "param1": "value1",
        "param2": "$step0.output_field"  // Reference previous step outputs
      },
      "reasoning": "Why this step is needed",
      "dependencies": [0]  // Which steps must complete before this
    }
  ]
}"""

    def _build_planning_prompt(
        self,
        goal: str,
        available_tools: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        previous_plan: Optional[List[Dict[str, Any]]] = None,
        feedback: Optional[str] = None
    ) -> str:
        """Build the planning prompt."""

        # Format tool catalog
        tool_catalog_str = format_tool_catalog_for_prompt(available_tools)

        prompt_parts = [
            f"GOAL: {goal}",
            "",
            "AVAILABLE TOOLS:",
            tool_catalog_str,
            ""
        ]

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
            "Remember:",
            "- Use LLM reasoning for all decisions",
            "- Check if tools are COMPLETE/STANDALONE before breaking into sub-steps",
            "- Keep plans as simple as possible",
            "- Specify dependencies clearly",
            "",
            "Respond with the plan in JSON format."
        ])

        return "\n".join(prompt_parts)

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
            if "parameters" not in step:
                warnings.append(f"Step {step_id}: No parameters specified")

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
