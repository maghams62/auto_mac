"""
Critic/Evaluator Agent - Handles verification, reflection, and quality assurance.

This agent is responsible for:
- Output verification (checking if results match user intent)
- Reflection (analyzing failures and generating corrections)
- Quality assurance (validating outputs meet constraints)

Acts as a mini-orchestrator for critic/evaluation operations.
"""

from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import logging
import json

logger = logging.getLogger(__name__)


@tool
def verify_output(
    step_description: str,
    user_intent: str,
    actual_output: Dict[str, Any],
    constraints: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Verify that a step's output matches user intent and constraints.

    CRITIC AGENT - LEVEL 1: Output Verification
    Use this to validate that outputs meet requirements.

    Args:
        step_description: Description of what the step was supposed to do
        user_intent: Original user request/intent
        actual_output: The actual output produced
        constraints: Optional constraints to check (e.g., {"page_count": 1})

    Returns:
        Dictionary with valid (bool), confidence (float), issues (list), suggestions (list)
    """
    logger.info(f"[CRITIC AGENT] Tool: verify_output(step='{step_description}')")

    try:
        from ..agent.verifier import OutputVerifier
        from ..utils import load_config

        config = load_config()
        verifier = OutputVerifier(config)

        # Use the verifier to check output
        verification = verifier.verify_step_output(
            step_description=step_description,
            user_intent=user_intent,
            actual_output=actual_output,
            expected_constraints=constraints or {}
        )

        return {
            "valid": verification.get("valid", False),
            "confidence": verification.get("confidence", 0.0),
            "issues": verification.get("issues", []),
            "suggestions": verification.get("suggestions", []),
            "reasoning": verification.get("reasoning", "")
        }

    except Exception as e:
        logger.error(f"[CRITIC AGENT] Error in verify_output: {e}")
        return {
            "error": True,
            "error_type": "VerificationError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def reflect_on_failure(
    step_description: str,
    error_message: str,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyze why a step failed and generate corrective actions.

    CRITIC AGENT - LEVEL 2: Failure Reflection
    Use this when a step fails to understand root cause and fixes.

    Args:
        step_description: Description of what the step was trying to do
        error_message: The error that occurred
        context: Context about the execution (previous steps, inputs, etc.)

    Returns:
        Dictionary with root_cause, corrective_actions, retry_recommended
    """
    logger.info(f"[CRITIC AGENT] Tool: reflect_on_failure(step='{step_description}')")

    try:
        from ..agent.verifier import ReflectionEngine
        from ..utils import load_config

        config = load_config()
        reflection_engine = ReflectionEngine(config)

        # Use reflection engine to analyze failure
        reflection = reflection_engine.reflect_on_failure(
            step_description=step_description,
            error_message=error_message,
            context=context
        )

        return {
            "root_cause": reflection.get("root_cause", ""),
            "corrective_actions": reflection.get("corrective_actions", []),
            "retry_recommended": reflection.get("retry_recommended", False),
            "alternative_approach": reflection.get("alternative_approach", ""),
            "reasoning": reflection.get("reasoning", "")
        }

    except Exception as e:
        logger.error(f"[CRITIC AGENT] Error in reflect_on_failure: {e}")
        return {
            "error": True,
            "error_type": "ReflectionError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def validate_plan(
    plan: List[Dict[str, Any]],
    goal: str,
    available_tools: List[str]
) -> Dict[str, Any]:
    """
    Validate a plan before execution.

    CRITIC AGENT - LEVEL 3: Plan Validation
    Use this to check if a plan is sound before executing.

    Args:
        plan: List of plan steps to validate
        goal: The goal the plan is trying to achieve
        available_tools: List of available tool names

    Returns:
        Dictionary with valid (bool), errors (list), warnings (list)
    """
    logger.info(f"[CRITIC AGENT] Tool: validate_plan(steps={len(plan)})")

    try:
        from ..orchestrator.validator import PlanValidator
        from ..orchestrator.tools_catalog import generate_tool_catalog, get_tool_specs_as_dicts

        # Generate tool catalog
        catalog = generate_tool_catalog()
        tool_specs = get_tool_specs_as_dicts(catalog)

        # Create validator
        validator = PlanValidator(tool_specs)

        # Validate plan
        is_valid, errors = validator.validate_plan(plan)

        # Separate errors and warnings
        critical_errors = [e for e in errors if e.get("severity") == "error"]
        warnings = [e for e in errors if e.get("severity") == "warning"]

        return {
            "valid": is_valid,
            "errors": critical_errors,
            "warnings": warnings,
            "total_issues": len(errors),
            "message": "Plan is valid" if is_valid else f"Plan has {len(critical_errors)} errors"
        }

    except Exception as e:
        logger.error(f"[CRITIC AGENT] Error in validate_plan: {e}")
        return {
            "error": True,
            "error_type": "ValidationError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def check_quality(
    output: Dict[str, Any],
    quality_criteria: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Check if output meets quality criteria.

    CRITIC AGENT - LEVEL 4: Quality Assurance
    Use this to validate outputs meet specific quality standards.

    Args:
        output: The output to check
        quality_criteria: Dictionary of quality criteria to validate
                         e.g., {"min_word_count": 100, "has_attachment": True}

    Returns:
        Dictionary with passed (bool), failed_criteria (list), score (float)
    """
    logger.info(f"[CRITIC AGENT] Tool: check_quality(criteria={list(quality_criteria.keys())})")

    try:
        from ..utils import load_config

        config = load_config()
        openai_config = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=0.0,
            api_key=openai_config.get("api_key")
        )

        # Use LLM to evaluate quality
        prompt = f"""Evaluate if the following output meets the quality criteria.

OUTPUT:
{json.dumps(output, indent=2)}

QUALITY CRITERIA:
{json.dumps(quality_criteria, indent=2)}

Provide a JSON response with:
{{
    "passed": true/false,
    "failed_criteria": ["criterion1", "criterion2", ...],
    "score": 0.0-1.0,
    "reasoning": "explanation"
}}"""

        messages = [
            SystemMessage(content="You are a quality assurance expert. Evaluate outputs objectively."),
            HumanMessage(content=prompt)
        ]

        response = llm.invoke(messages)

        # Parse LLM response
        try:
            result = json.loads(response.content)
            return {
                "passed": result.get("passed", False),
                "failed_criteria": result.get("failed_criteria", []),
                "score": result.get("score", 0.0),
                "reasoning": result.get("reasoning", "")
            }
        except json.JSONDecodeError:
            logger.error(f"[CRITIC AGENT] Failed to parse LLM response: {response.content}")
            return {
                "error": True,
                "error_type": "QualityCheckError",
                "error_message": "Failed to parse quality check response",
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"[CRITIC AGENT] Error in check_quality: {e}")
        return {
            "error": True,
            "error_type": "QualityCheckError",
            "error_message": str(e),
            "retry_possible": False
        }


# Critic Agent Tool Registry
CRITIC_AGENT_TOOLS = [
    verify_output,
    reflect_on_failure,
    validate_plan,
    check_quality,
]


# Critic Agent Hierarchy
CRITIC_AGENT_HIERARCHY = """
Critic/Evaluator Agent Hierarchy:
=================================

LEVEL 1: Output Verification
└─ verify_output → Verify outputs match user intent and constraints

LEVEL 2: Failure Reflection
└─ reflect_on_failure → Analyze failures and generate corrective actions

LEVEL 3: Plan Validation
└─ validate_plan → Validate plans before execution (anti-hallucination)

LEVEL 4: Quality Assurance
└─ check_quality → Check outputs meet quality criteria

Typical Workflow:
1. validate_plan(plan) → Check plan is valid before execution
2. [Execute steps]
3. verify_output(step_output) → Verify each critical step
4. [If failure] reflect_on_failure(error) → Understand and fix
5. check_quality(final_output) → Final quality check
"""


class CriticAgent:
    """
    Critic/Evaluator Agent - Mini-orchestrator for verification and quality assurance.

    Responsibilities:
    - Output verification (semantic validation)
    - Failure reflection (root cause analysis)
    - Plan validation (anti-hallucination)
    - Quality assurance (criteria checking)

    This agent acts as a sub-orchestrator that handles all critic/evaluation tasks.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in CRITIC_AGENT_TOOLS}
        logger.info(f"[CRITIC AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        """Get all critic agent tools."""
        return CRITIC_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get critic agent hierarchy documentation."""
        return CRITIC_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a critic agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Critic agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[CRITIC AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[CRITIC AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }
