"""
Verification and reflection system for agent outputs.

This module provides critic/verifier capabilities to ensure agent outputs
match user intent and instructions are followed precisely.
"""

import logging
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.utils import get_temperature_for_model
from src.utils.openai_client import PooledOpenAIClient


logger = logging.getLogger(__name__)


class OutputVerifier:
    """
    Verifies that agent step outputs match the intended goal and user request.
    Uses LLM-based reflection to check for discrepancies.
    """

    def __init__(self, config: dict):
        """
        Initialize the output verifier.

        Args:
            config: Configuration dictionary containing API keys and model settings
        """
        self.config = config
        openai_config = config.get("openai", {})
        
        # Use pooled client for better performance
        pooled_client = PooledOpenAIClient.get_client(config)
        
        self.llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.0),  # Use deterministic output for verification
            api_key=openai_config.get("api_key"),
            http_client=pooled_client._http_client if hasattr(pooled_client, '_http_client') else None
        )
        logger.info("[VERIFIER] Using pooled OpenAI client")

    def verify_step_output(
        self,
        user_request: str,
        step: Dict[str, Any],
        step_result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Verify that a step's output matches the user's intent.

        Args:
            user_request: Original user request
            step: Step definition (action, parameters, reasoning, etc.)
            step_result: Actual output from the step execution
            context: Additional context (previous steps, etc.)

        Returns:
            Dictionary with verification result:
            {
                "valid": bool,
                "issues": List[str],
                "suggestions": List[str],
                "confidence": float (0-1)
            }
        """
        logger.info(f"Verifying step {step.get('id')}: {step.get('action')}")

        # Skip verification if step errored
        if step_result.get("error"):
            return {
                "valid": False,
                "issues": ["Step execution failed"],
                "suggestions": [],
                "confidence": 1.0
            }

        # Build verification prompt
        prompt = self._build_verification_prompt(
            user_request=user_request,
            step=step,
            step_result=step_result,
            context=context
        )

        try:
            # Call LLM for verification
            messages = [
                SystemMessage(content="""You are a precise output verifier. Your job is to check if an agent's step output matches the user's original request.

Pay special attention to:
1. Quantitative requirements (e.g., "last page" means exactly ONE page, not multiple)
2. Specific selections (e.g., "only X" means exclude everything else)
3. Precise constraints (e.g., "first 3 pages" means pages 1, 2, 3 only)

CRITICAL: You MUST respond with ONLY a valid JSON object, no other text before or after.
Format:
{
  "valid": true,
  "issues": [],
  "suggestions": [],
  "confidence": 1.0
}"""),
                HumanMessage(content=prompt)
            ]

            response = self.llm.invoke(messages)

            # Parse response
            import json
            import re

            # Extract JSON from response
            content = response.content.strip()

            # Try to find JSON in the response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                content = json_match.group()

            result = json.loads(content)

            logger.info(f"Verification result: valid={result.get('valid')}, issues={len(result.get('issues', []))}")
            return result

        except Exception as e:
            logger.error(f"Error during verification: {e}")
            return {
                "valid": True,  # Default to valid on error to avoid blocking
                "issues": [],
                "suggestions": [],
                "confidence": 0.0
            }

    def _build_verification_prompt(
        self,
        user_request: str,
        step: Dict[str, Any],
        step_result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build prompt for LLM verification."""

        prompt_parts = [
            "USER REQUEST:",
            f'"{user_request}"',
            "",
            "STEP DEFINITION:",
            f"Action: {step.get('action')}",
            f"Reasoning: {step.get('reasoning')}",
            f"Parameters: {step.get('parameters')}",
            "",
            "STEP OUTPUT:",
        ]

        # Format step result for readability
        for key, value in step_result.items():
            if isinstance(value, list):
                prompt_parts.append(f"{key}: {len(value)} items")
                if key == "screenshot_paths" or key == "page_numbers":
                    for item in value:
                        prompt_parts.append(f"  - {item}")
            else:
                prompt_parts.append(f"{key}: {value}")

        prompt_parts.extend([
            "",
            "VERIFICATION QUESTIONS:",
            "1. Does the output quantity match the user's request?",
            "2. If the user asked for 'last page', 'first page', or specific count, is that exact count present?",
            "3. Are there any extra items that shouldn't be included?",
            "4. Does the step reasoning align with what was actually done?",
            "",
            "Provide your verification result as JSON."
        ])

        return "\n".join(prompt_parts)

    def verify_attachment_creation(
        self,
        user_request: str,
        attachment_path: str,
        intended_content: str,
        step_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Special verification for files being attached to emails.

        Args:
            user_request: Original user request
            attachment_path: Path to the file being attached
            intended_content: Description of what should be in the file
            step_history: History of all steps taken

        Returns:
            Verification result dictionary
        """
        logger.info(f"Verifying attachment: {attachment_path}")

        prompt = f"""USER REQUEST: "{user_request}"

ATTACHMENT PATH: {attachment_path}

INTENDED CONTENT: {intended_content}

STEP HISTORY:
"""
        for step in step_history:
            prompt += f"\nStep {step.get('id')}: {step.get('action')}"
            if step.get('result'):
                result = step['result']
                if 'screenshot_paths' in result:
                    prompt += f"\n  Screenshots: {len(result['screenshot_paths'])} files"
                if 'page_numbers' in result:
                    prompt += f"\n  Pages: {result['page_numbers']}"

        prompt += """

VERIFY:
1. Does the attachment contain what the user asked for?
2. Is the quantity/selection correct (e.g., if user said "last page", is it only 1 page)?
3. Does the attachment path suggest the right content was created?

Respond with JSON."""

        try:
            messages = [
                SystemMessage(content="""You verify attachments match user intent.
Focus on whether the quantity and selection are correct.
Respond with JSON: {"valid": bool, "issues": [], "suggestions": [], "confidence": float}"""),
                HumanMessage(content=prompt)
            ]

            response = self.llm.invoke(messages)
            import json
            result = json.loads(response.content)

            logger.info(f"Attachment verification: valid={result.get('valid')}")
            return result

        except Exception as e:
            logger.error(f"Error verifying attachment: {e}")
            return {
                "valid": True,
                "issues": [],
                "suggestions": [],
                "confidence": 0.0
            }


class ReflectionEngine:
    """
    Provides reflection and re-thinking capabilities using LlamaIndex.
    Helps the agent reconsider its plan when verification fails.
    """

    def __init__(self, config: dict):
        """Initialize reflection engine."""
        self.config = config
        openai_config = config.get("openai", {})
        self.llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.3),
            api_key=openai_config.get("api_key")
        )

    def reflect_and_replan(
        self,
        user_request: str,
        original_plan: Dict[str, Any],
        verification_results: List[Dict[str, Any]],
        execution_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Reflect on failed verification and create a new plan.

        Args:
            user_request: Original user request
            original_plan: The original plan that had issues
            verification_results: List of verification failures
            execution_history: What actually happened

        Returns:
            New plan dictionary or None if can't improve
        """
        logger.info("Reflecting on verification failures and replanning")

        prompt = self._build_reflection_prompt(
            user_request=user_request,
            original_plan=original_plan,
            verification_results=verification_results,
            execution_history=execution_history
        )

        try:
            messages = [
                SystemMessage(content="""You are a reflective planner. When a plan fails verification,
you analyze what went wrong and create a corrected plan.

Pay attention to:
- Exact quantities requested ("last page" = 1 page, not multiple)
- Filtering unwanted results
- Using parameters correctly to achieve the exact desired output

Respond with a corrected plan in JSON format."""),
                HumanMessage(content=prompt)
            ]

            response = self.llm.invoke(messages)

            import json
            new_plan = json.loads(response.content)

            logger.info("Generated new plan after reflection")
            return new_plan

        except Exception as e:
            logger.error(f"Error during reflection: {e}")
            return None

    def _build_reflection_prompt(
        self,
        user_request: str,
        original_plan: Dict[str, Any],
        verification_results: List[Dict[str, Any]],
        execution_history: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for reflection."""

        prompt_parts = [
            "REFLECTION AND REPLANNING",
            "=" * 80,
            "",
            f'USER REQUEST: "{user_request}"',
            "",
            "ORIGINAL PLAN:",
            f"Goal: {original_plan.get('goal')}",
            f"Steps: {len(original_plan.get('steps', []))}",
            ""
        ]

        for step in original_plan.get('steps', []):
            prompt_parts.append(f"Step {step['id']}: {step['action']}")
            prompt_parts.append(f"  Reasoning: {step['reasoning']}")
            prompt_parts.append(f"  Parameters: {step['parameters']}")

        prompt_parts.extend([
            "",
            "VERIFICATION FAILURES:",
            ""
        ])

        for i, verification in enumerate(verification_results, 1):
            if not verification.get('valid'):
                prompt_parts.append(f"Failure {i}:")
                for issue in verification.get('issues', []):
                    prompt_parts.append(f"  - {issue}")
                for suggestion in verification.get('suggestions', []):
                    prompt_parts.append(f"  Suggestion: {suggestion}")
                prompt_parts.append("")

        prompt_parts.extend([
            "WHAT WENT WRONG:",
            "Analyze the failures and identify the root cause.",
            "",
            "CORRECTED PLAN:",
            "Create a new plan that addresses these issues.",
            "Focus on using the right parameters and filtering to get EXACTLY what the user asked for.",
            "",
            "Respond with a complete plan JSON."
        ])

        return "\n".join(prompt_parts)
