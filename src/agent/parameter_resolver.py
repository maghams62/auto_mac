"""
LLM-based parameter resolution for all tool decisions.

This module ensures NO hardcoded values - every parameter is determined by LLM reasoning.
"""

import logging
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import json
import re

from ..utils import get_temperature_for_model


logger = logging.getLogger(__name__)


class ParameterResolver:
    """
    Uses LLM to resolve tool parameters dynamically.

    Eliminates hardcoded values like:
    - top_k=3 → LLM decides how many results needed
    - timeout=30 → LLM decides appropriate timeout
    - threshold=0.5 → LLM decides relevance threshold
    """

    def __init__(self, config: dict):
        """Initialize parameter resolver."""
        self.config = config
        openai_config = config.get("openai", {})
        self.llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.0),
            api_key=openai_config.get("api_key")
        )

    def resolve_search_parameters(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Determine optimal search parameters using LLM.

        Args:
            query: Search query
            context: Context about the search (user request, previous results, etc.)

        Returns:
            Dictionary with resolved parameters:
            {
                "top_k": int,  # How many results to return
                "threshold": float,  # Minimum relevance score
                "strategy": str  # "semantic" | "keyword" | "hybrid"
            }
        """
        logger.info(f"Resolving search parameters for: '{query}'")

        prompt = f"""SEARCH QUERY: "{query}"

CONTEXT:
User Request: {context.get('user_request', 'unknown')}
Previous Steps: {len(context.get('previous_steps', []))}

TASK: Determine optimal search parameters.

CONSIDERATIONS:
- If user wants "the document" or "last page", they want exactly 1 result (top_k=1)
- If user wants "all pages" or "everything", set top_k high (5-10)
- If query is specific (names, dates), use lower threshold (0.3)
- If query is vague (concepts), use higher threshold (0.6)

Respond with JSON:
{{
  "top_k": 1,
  "threshold": 0.5,
  "strategy": "semantic",
  "reasoning": "User wants specific document, need exactly 1 result"
}}"""

        try:
            messages = [
                SystemMessage(content="""You determine search parameters.
Respond with ONLY valid JSON, no other text.
Format: {"top_k": int, "threshold": float, "strategy": str, "reasoning": str}"""),
                HumanMessage(content=prompt)
            ]

            response = self.llm.invoke(messages)
            content = response.content.strip()

            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                content = json_match.group()

            result = json.loads(content)
            logger.info(f"Search parameters: top_k={result.get('top_k')}, reasoning={result.get('reasoning')}")

            return result

        except Exception as e:
            logger.error(f"Error resolving search parameters: {e}")
            # Safe fallback
            return {
                "top_k": 1,
                "threshold": 0.5,
                "strategy": "semantic",
                "reasoning": f"Fallback due to error: {e}"
            }

    def resolve_page_selection_parameters(
        self,
        total_pages: int,
        user_intent: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Determine how many pages to return in semantic search.

        Args:
            total_pages: Total pages in document
            user_intent: What user wants (e.g., "chorus", "summary", "last page")
            context: Additional context

        Returns:
            {
                "max_pages": int,  # Maximum pages to return
                "require_exact": bool,  # Whether result must be exact match
                "reasoning": str
            }
        """
        logger.info(f"Resolving page selection for: '{user_intent}' (total: {total_pages})")

        prompt = f"""USER INTENT: "{user_intent}"

DOCUMENT INFO:
Total Pages: {total_pages}

TASK: Determine how many pages to return from semantic search.

RULES:
- If user says "last page" or "first page", return ONLY 1 page (max_pages=1, require_exact=true)
- If user says "first 3 pages", return exactly 3 (max_pages=3, require_exact=true)
- If user wants concept like "chorus", may span multiple pages (max_pages=3, require_exact=false)
- If user says "all", return many pages (max_pages={total_pages}, require_exact=false)

Respond with JSON:
{{
  "max_pages": 1,
  "require_exact": true,
  "reasoning": "User wants specific single page"
}}"""

        try:
            messages = [
                SystemMessage(content="""You determine page selection parameters.
Respond with ONLY valid JSON.
Format: {"max_pages": int, "require_exact": bool, "reasoning": str}"""),
                HumanMessage(content=prompt)
            ]

            response = self.llm.invoke(messages)
            content = response.content.strip()

            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                content = json_match.group()

            result = json.loads(content)
            logger.info(f"Page selection: max={result.get('max_pages')}, reasoning={result.get('reasoning')}")

            return result

        except Exception as e:
            logger.error(f"Error resolving page parameters: {e}")
            return {
                "max_pages": 1,
                "require_exact": True,
                "reasoning": f"Fallback: {e}"
            }

    def resolve_timeout(
        self,
        operation: str,
        context: Dict[str, Any]
    ) -> int:
        """
        Determine appropriate timeout for an operation.

        Args:
            operation: Type of operation (e.g., "pdf_render", "email_send", "search")
            context: Context about the operation

        Returns:
            Timeout in seconds
        """
        prompt = f"""OPERATION: {operation}

CONTEXT: {context}

TASK: Determine appropriate timeout in seconds.

GUIDELINES:
- Simple searches: 5-10 seconds
- PDF rendering: 30-60 seconds
- Email sending: 15-30 seconds
- Large file operations: 60-120 seconds

Respond with JSON:
{{
  "timeout_seconds": 30,
  "reasoning": "PDF rendering may take time"
}}"""

        try:
            messages = [
                SystemMessage(content="""You determine timeouts.
Respond with ONLY JSON: {"timeout_seconds": int, "reasoning": str}"""),
                HumanMessage(content=prompt)
            ]

            response = self.llm.invoke(messages)
            content = response.content.strip()

            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                content = json_match.group()

            result = json.loads(content)
            timeout = result.get('timeout_seconds', 30)

            logger.info(f"Timeout for {operation}: {timeout}s - {result.get('reasoning')}")
            return timeout

        except Exception as e:
            logger.error(f"Error resolving timeout: {e}")
            return 30  # Safe default

    def resolve_retry_strategy(
        self,
        error_type: str,
        attempt_number: int,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Determine if and how to retry a failed operation.

        Args:
            error_type: Type of error encountered
            attempt_number: Current attempt number
            context: Context about the failure

        Returns:
            {
                "should_retry": bool,
                "wait_seconds": int,
                "max_attempts": int,
                "reasoning": str
            }
        """
        prompt = f"""ERROR: {error_type}
ATTEMPT: {attempt_number}
CONTEXT: {context}

TASK: Decide retry strategy.

CONSIDERATIONS:
- Network errors: Retry with backoff
- Not found errors: Don't retry
- Rate limits: Wait longer
- Temporary failures: Retry quickly

Respond with JSON:
{{
  "should_retry": true,
  "wait_seconds": 5,
  "max_attempts": 3,
  "reasoning": "Network error, worth retrying"
}}"""

        try:
            messages = [
                SystemMessage(content="""You determine retry strategies.
Respond with ONLY JSON: {"should_retry": bool, "wait_seconds": int, "max_attempts": int, "reasoning": str}"""),
                HumanMessage(content=prompt)
            ]

            response = self.llm.invoke(messages)
            content = response.content.strip()

            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                content = json_match.group()

            result = json.loads(content)
            logger.info(f"Retry decision: {result.get('should_retry')} - {result.get('reasoning')}")

            return result

        except Exception as e:
            logger.error(f"Error resolving retry strategy: {e}")
            return {
                "should_retry": False,
                "wait_seconds": 0,
                "max_attempts": 1,
                "reasoning": f"Error in resolver: {e}"
            }
