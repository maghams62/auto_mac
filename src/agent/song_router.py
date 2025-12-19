"""
Song Intent Router - Decides how to resolve song queries.

This module implements a routing layer that decides whether to:
1. Use LLM-based semantic resolution for famous/iconic songs
2. Use direct Spotify catalog search for unknown songs
3. Ask user for clarification when ambiguous

Based on ReAct pattern (Yao et al., ICLR 2023) with Thought -> Action routing.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from openai import OpenAI

logger = logging.getLogger(__name__)


class RouteDecision(Enum):
    """Routing decision for song query resolution."""
    RESOLVE = "resolve"      # Use LLM semantic resolution (famous songs, iconic queries)
    SEARCH = "search"        # Use direct catalog search (unknown songs, exact matches)
    ASK_USER = "ask_user"    # Ask for clarification (ambiguous queries)


ROUTING_SYSTEM_PROMPT = """You are a music query router. Your job is to decide HOW to resolve a song query.

You have THREE routing options:

1. **RESOLVE** - Use semantic LLM resolution
   - Famous songs with iconic descriptions ("moonwalk song", "space song")
   - Well-known artists + partial info ("Eminem space song")
   - Descriptive queries that map to famous songs
   - When: High confidence that LLM can identify from context

2. **SEARCH** - Use direct Spotify catalog search
   - Exact song titles provided ("Breaking the Habit")
   - Unknown/obscure songs
   - Recent releases LLM might not know
   - When: Query is specific but not famous enough for semantic resolution

3. **ASK_USER** - Request clarification
   - Extremely vague queries ("that song")
   - Ambiguous with many possible matches
   - When: Cannot confidently route to RESOLVE or SEARCH

ROUTING GUIDELINES:

**Famous/Iconic Queries → RESOLVE**
- "moonwalk song" → RESOLVE (famous MJ reference)
- "space song" → RESOLVE (iconic Beach House track)
- "song by Eminem about space" → RESOLVE (can narrow to Space Bound)
- "that Linkin Park song about habits" → RESOLVE (Breaking the Habit)

**Exact/Unknown Queries → SEARCH**
- "Breaking the Habit" → SEARCH (exact title, use catalog)
- "new Taylor Swift song" → SEARCH (recent release, catalog better)
- "obscure indie track xyz" → SEARCH (unknown to LLM)

**Vague/Ambiguous Queries → ASK_USER**
- "that song" → ASK_USER (no context)
- "the sad song" → ASK_USER (too many matches)
- "song I heard yesterday" → ASK_USER (unknown reference)

CONFIDENCE SCORING:
- 0.9-1.0: Very confident in routing decision
- 0.7-0.9: Confident, but could use fallback
- 0.5-0.7: Moderate confidence
- Below 0.5: Low confidence, suggest ASK_USER

Always respond with valid JSON only."""


ROUTING_PROMPT = """Route this song query to the best resolution strategy:

Query: "{query}"

{history_context}

Think step-by-step:
1. Is this a famous/iconic query that semantic resolution can handle?
2. Is this an exact title that catalog search should handle?
3. Is this too vague and needs clarification?
4. What's your confidence level?

Respond with ONLY a JSON object:
{{
  "route": "resolve" | "search" | "ask_user",
  "confidence": 0.0-1.0,
  "reasoning": "detailed explanation of routing decision",
  "fallback_route": "resolve" | "search" (if confidence < 0.8)
}}

EXAMPLES:

Query: "play that Michael Jackson song where he does the moonwalk"
Response:
{{
  "route": "resolve",
  "confidence": 0.95,
  "reasoning": "Famous iconic query - 'moonwalk' + 'Michael Jackson' is a well-known reference that semantic resolution can identify as 'Smooth Criminal'. This is the type of descriptive query LLM excels at.",
  "fallback_route": "search"
}}

Query: "Breaking the Habit"
Response:
{{
  "route": "search",
  "confidence": 0.90,
  "reasoning": "Exact song title provided. Direct catalog search is more efficient than semantic resolution for exact matches.",
  "fallback_route": "resolve"
}}

Query: "the space song"
Response:
{{
  "route": "resolve",
  "confidence": 0.85,
  "reasoning": "Vague but famous reference - 'the space song' commonly refers to Beach House's 'Space Song'. Semantic resolution can identify this with alternatives.",
  "fallback_route": "search"
}}

Query: "new Taylor Swift song from her latest album"
Response:
{{
  "route": "search",
  "confidence": 0.80,
  "reasoning": "Recent release that LLM might not know. Catalog search is better for current music.",
  "fallback_route": "resolve"
}}

Query: "that song"
Response:
{{
  "route": "ask_user",
  "confidence": 0.95,
  "reasoning": "Extremely vague with no context. Cannot confidently route to either RESOLVE or SEARCH. User clarification required.",
  "fallback_route": "search"
}}

Now route this query: "{query}"
"""


class IntentRouter:
    """
    Routes song queries to appropriate resolution strategy.

    Uses LLM-based decision making following ReAct pattern to determine
    whether to use semantic resolution, catalog search, or ask for clarification.
    """

    def __init__(self, config: Dict[str, Any], reasoning_trace: Optional[Any] = None):
        """
        Initialize the intent router.

        Args:
            config: Configuration dictionary with OpenAI settings
            reasoning_trace: Optional ReasoningTrace instance for logging decisions
        """
        self.config = config
        self.reasoning_trace = reasoning_trace

        openai_cfg = config.get("openai", {})
        self.client = OpenAI(api_key=openai_cfg.get("api_key"))
        self.model = openai_cfg.get("model", "gpt-4o")
        # Use lower temperature for consistent routing decisions
        self.temperature = 0.2
        self.max_tokens = 300  # Routing decisions are short

        logger.info(f"[SONG ROUTER] Initialized with model: {self.model}")

    def route(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Route a song query to the appropriate resolution strategy.

        Args:
            query: User's song query (e.g., "moonwalk song", "Breaking the Habit")
            context: Optional context with:
                - past_failures: List of previous failed resolution attempts
                - session_history: Recent queries from this session
                - user_preferences: User's listening patterns

        Returns:
            Dictionary with routing decision:
            {
                "route": RouteDecision enum value,
                "confidence": float (0.0-1.0),
                "reasoning": str,
                "fallback_route": RouteDecision enum value,
                "metadata": Dict with additional context
            }
        """
        logger.info(f"[SONG ROUTER] Routing query: '{query}'")

        # Build history context from reasoning trace if available
        history_context = self._build_history_context(context)

        try:
            # Determine API parameters based on model
            api_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": ROUTING_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": ROUTING_PROMPT.format(
                            query=query,
                            history_context=history_context
                        ),
                    },
                ],
                "response_format": {"type": "json_object"},
            }

            # Model-specific parameters
            if self.model.startswith(("o1", "o3", "o4")):
                api_params["max_completion_tokens"] = self.max_tokens
            else:
                api_params["max_tokens"] = self.max_tokens
                api_params["temperature"] = self.temperature

            response = self.client.chat.completions.create(**api_params)
            result = json.loads(response.choices[0].message.content)

            # Validate and parse result
            route_str = result.get("route", "search").lower()
            try:
                route = RouteDecision(route_str)
            except ValueError:
                logger.warning(f"[SONG ROUTER] Invalid route '{route_str}', defaulting to SEARCH")
                route = RouteDecision.SEARCH

            confidence = float(result.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]

            reasoning = result.get("reasoning", "No reasoning provided")

            fallback_str = result.get("fallback_route", "search").lower()
            try:
                fallback_route = RouteDecision(fallback_str)
            except ValueError:
                fallback_route = RouteDecision.SEARCH

            decision = {
                "route": route,
                "confidence": confidence,
                "reasoning": reasoning,
                "fallback_route": fallback_route,
                "metadata": {
                    "query": query,
                    "model": self.model,
                    "context_used": bool(history_context)
                }
            }

            logger.info(
                f"[SONG ROUTER] Decision: {route.value.upper()} "
                f"(confidence: {confidence:.2f}) - {reasoning[:100]}"
            )

            # Log to reasoning trace if available
            if self.reasoning_trace:
                try:
                    self.reasoning_trace.add_entry(
                        stage=self.reasoning_trace.__class__.__module__.rsplit('.', 1)[0] + '.reasoning_trace.ReasoningStage.PLANNING',
                        thought=f"Routing song query: '{query}'",
                        action="route_song_query",
                        parameters={"query": query, "route": route.value},
                        evidence=[
                            f"Route: {route.value}",
                            f"Confidence: {confidence:.2f}",
                            reasoning[:200]
                        ],
                        outcome=self.reasoning_trace.__class__.__module__.rsplit('.', 1)[0] + '.reasoning_trace.OutcomeStatus.SUCCESS',
                        metadata=decision["metadata"]
                    )
                except Exception as e:
                    logger.debug(f"[SONG ROUTER] Failed to log to reasoning trace: {e}")

            return decision

        except Exception as e:
            logger.error(f"[SONG ROUTER] Routing error: {e}")
            # Fallback: default to SEARCH (safest option)
            fallback_decision = {
                "route": RouteDecision.SEARCH,
                "confidence": 0.3,
                "reasoning": f"Routing failed ({str(e)}), defaulting to catalog search",
                "fallback_route": RouteDecision.RESOLVE,
                "metadata": {
                    "query": query,
                    "error": str(e),
                    "fallback": True
                }
            }

            logger.warning(
                f"[SONG ROUTER] Fallback to SEARCH due to error: {e}"
            )

            return fallback_decision

    def _build_history_context(self, context: Optional[Dict[str, Any]]) -> str:
        """
        Build context string from past failures and session history.

        Args:
            context: Optional context dictionary

        Returns:
            Formatted context string for prompt injection
        """
        if not context:
            return ""

        context_lines = []

        # Past failures
        past_failures = context.get("past_failures", [])
        if past_failures:
            context_lines.append("PAST FAILURES (consider when routing):")
            for failure in past_failures[-3:]:  # Last 3 failures
                query_failed = failure.get("query", "unknown")
                route_used = failure.get("route", "unknown")
                reason = failure.get("reason", "unknown")
                context_lines.append(f"  - Query: '{query_failed}' | Route: {route_used} | Failed: {reason}")

        # Session history
        session_history = context.get("session_history", [])
        if session_history:
            context_lines.append("\nRECENT QUERIES THIS SESSION:")
            for entry in session_history[-3:]:  # Last 3 queries
                query_prev = entry.get("query", "unknown")
                success = entry.get("success", False)
                context_lines.append(f"  - '{query_prev}' → {'SUCCESS' if success else 'FAILED'}")

        if context_lines:
            return "\n".join(context_lines) + "\n"
        return ""

    def should_use_fallback(self, decision: Dict[str, Any]) -> bool:
        """
        Check if routing confidence is low and fallback should be used.

        Args:
            decision: Routing decision dictionary

        Returns:
            True if fallback route should be attempted
        """
        confidence = decision.get("confidence", 1.0)
        return confidence < 0.8
