"""
Execution Strategy Router - Decides how to execute resolved music playback intents.

This module implements an execution router that determines the best approach to actually
perform Spotify operations, with intelligent escalation from simple AppleScript to
advanced browser automation and vision-based approaches.

Based on ReAct pattern with feedback loops for handling complex UI interactions.
"""

import base64
import json
import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime
from pathlib import Path
from openai import OpenAI

logger = logging.getLogger(__name__)


class ExecutionStrategy(Enum):
    """Execution strategy for Spotify operations."""
    SIMPLE = "simple"           # Basic AppleScript (current approach)
    ADVANCED = "advanced"       # Browser automation with UI analysis
    VISION = "vision"          # Vision-based screenshot analysis and decisions


EXECUTION_SYSTEM_PROMPT = """You are an execution strategy router for Spotify operations. Your job is to decide HOW to execute a resolved music playback intent.

You have THREE execution strategies:

1. **SIMPLE** - Basic AppleScript automation
   - Standard Spotify operations (play, pause, search)
   - When: Straightforward operations that AppleScript can handle reliably
   - Fast, low-overhead, no UI complexity

2. **ADVANCED** - Browser automation with element detection
   - Complex UI interactions requiring element identification
   - When: Need to interact with specific UI elements, handle popups, or navigate complex flows
   - Uses screenshot + element detection for precise interactions

3. **VISION** - Vision-based analysis and reasoning
   - Screenshot analysis with LLM vision for complex scenarios
   - When: UI is unpredictable, need semantic understanding of what's on screen
   - Most sophisticated but slower approach

EXECUTION GUIDELINES:

**SIMPLE EXECUTION (Default)**
- Playing resolved songs: "SIMPLE" (AppleScript search and play)
- Basic controls (play/pause/status): "SIMPLE" (AppleScript commands)
- When: No UI complexity, standard Spotify behavior expected

**ADVANCED EXECUTION**
- After AppleScript failures: Escalate to ADVANCED for retry
- Complex search scenarios: Use browser automation to navigate Spotify UI
- When: Need to handle login prompts, ads, or non-standard UI states

**VISION EXECUTION**
- When Advanced fails: Use vision to understand what's actually on screen
- Complex error scenarios: Analyze screenshots to diagnose issues
- When: Need semantic understanding of UI state, not just element detection

ESCALATION LOGIC:
- Start with SIMPLE (fastest)
- If SIMPLE fails → Try ADVANCED (more robust)
- If ADVANCED fails → Use VISION (most intelligent)
- Each level can access results from previous attempts

CONFIDENCE SCORING:
- 0.9-1.0: Very confident in execution strategy
- 0.7-0.9: Good confidence, but monitor for escalation
- 0.5-0.7: Moderate confidence
- Below 0.5: Low confidence, suggest escalation

Always respond with valid JSON only."""

EXECUTION_PROMPT = """Choose the best execution strategy for this Spotify operation:

Operation: {operation_type}
Song: "{song_name}"
Artist: "{artist}"
Context: {context_info}

Previous Attempts: {previous_attempts}

Strategy Decision Factors:
1. Is this a standard playback operation? → SIMPLE
2. Did previous attempts fail with AppleScript? → ADVANCED
3. Is the UI state unpredictable or complex? → VISION
4. What's your confidence in the chosen strategy?

Respond with ONLY a JSON object:
{{
  "strategy": "simple" | "advanced" | "vision",
  "confidence": 0.0-1.0,
  "reasoning": "detailed explanation of strategy choice",
  "escalation_trigger": "condition that would trigger moving to next level",
  "fallback_strategy": "simple" | "advanced" | "vision"
}}

EXAMPLES:

Operation: play_song, Song: "Viva la Vida", Artist: "Coldplay", Context: first_attempt
Response:
{{
  "strategy": "simple",
  "confidence": 0.95,
  "reasoning": "Standard song playback - AppleScript can handle search and play reliably",
  "escalation_trigger": "AppleScript returns error",
  "fallback_strategy": "advanced"
}}

Operation: play_song, Song: "Complex Name", Artist: "Unknown", Context: after_applescript_failure
Response:
{{
  "strategy": "advanced",
  "confidence": 0.85,
  "reasoning": "AppleScript failed, escalating to browser automation for better UI handling",
  "escalation_trigger": "Element not found or interaction fails",
  "fallback_strategy": "vision"
}}

Operation: play_song, Song: "Vague Song", Artist: None, Context: multiple_failures_complex_ui
Response:
{{
  "strategy": "vision",
  "confidence": 0.75,
  "reasoning": "Complex scenario with UI unpredictability - need vision analysis",
  "escalation_trigger": "Cannot interpret screen content",
  "fallback_strategy": "advanced"
}}

Now choose strategy for: {operation_type}"""

VISION_ANALYSIS_PROMPT = """Analyze this Spotify screenshot and determine the best action to play the requested song.

Requested Song: "{song_name}"
Requested Artist: "{artist}"
Previous Attempts: {previous_attempts}

Look at the screenshot and identify:
1. Is Spotify visible and active?
2. What's currently playing (if anything)?
3. Is there a search bar visible?
4. Are there any error messages or popups?
5. What's the current UI state?

Based on your analysis, recommend the specific action to take.

Respond with JSON:
{{
  "ui_state": "description of what you see",
  "action_recommended": "specific action to take",
  "confidence": 0.0-1.0,
  "reasoning": "why this action will work",
  "coordinates": [x, y] // if clicking needed
}}

Be specific about UI elements and their locations."""


class ExecutionRouter:
    """
    Routes execution strategies for Spotify operations with intelligent escalation.

    Uses LLM-based decision making to choose between:
    1. Simple AppleScript (fast, reliable for standard operations)
    2. Advanced browser automation (handles complex UI scenarios)
    3. Vision-based analysis (most sophisticated for unpredictable UI)

    Includes feedback loops where failures automatically escalate to more robust approaches.
    """

    def __init__(self, config: Dict[str, Any], reasoning_trace: Optional[Any] = None):
        """
        Initialize the execution router.

        Args:
            config: Configuration with OpenAI settings
            reasoning_trace: Optional ReasoningTrace for logging
        """
        self.config = config
        self.reasoning_trace = reasoning_trace

        openai_cfg = config.get("openai", {})
        self.client = OpenAI(api_key=openai_cfg.get("api_key"))
        self.model = openai_cfg.get("model", "gpt-4o")
        self.vision_model = openai_cfg.get("vision_model", "gpt-4o")  # Can be different model for vision

        # Lower temperature for consistent execution decisions
        self.temperature = 0.1
        self.max_tokens = 500

        logger.info(f"[EXECUTION ROUTER] Initialized with models: {self.model}, vision: {self.vision_model}")

    def route_execution(self, operation: str, song_name: str, artist: Optional[str] = None,
                       context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Route to the best execution strategy for a Spotify operation.

        Args:
            operation: Operation type (e.g., "play_song", "pause_music")
            song_name: Song name (for playback operations)
            artist: Optional artist name
            context: Previous attempts, failures, UI state, etc.

        Returns:
            Dictionary with execution strategy and metadata
        """
        logger.info(f"[EXECUTION ROUTER] Routing execution for: {operation} '{song_name}'")

        context = context or {}
        previous_attempts = context.get("previous_attempts", [])

        # Check if we should skip routing and go directly to vision for certain operations
        if self._should_use_vision_first(operation, context):
            logger.info(f"[EXECUTION ROUTER] Skipping routing, using VISION for {operation}")
            return {
                "strategy": ExecutionStrategy.VISION,
                "confidence": 0.9,
                "reasoning": f"Direct vision routing for {operation} based on context analysis",
                "escalation_trigger": "vision automation fails",
                "fallback_strategy": ExecutionStrategy.SIMPLE,
                "metadata": {
                    "operation": operation,
                    "song_name": song_name,
                    "artist": artist,
                    "direct_vision": True
                }
            }

        # Build context string
        context_info = self._build_context_string(context)
        previous_attempts_str = self._format_previous_attempts(previous_attempts)

        try:
            # Determine API parameters
            api_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": EXECUTION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": EXECUTION_PROMPT.format(
                            operation_type=operation,
                            song_name=song_name,
                            artist=artist or "None",
                            context_info=context_info,
                            previous_attempts=previous_attempts_str
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
            strategy_str = result.get("strategy", "simple").lower()
            try:
                strategy = ExecutionStrategy(strategy_str)
            except ValueError:
                logger.warning(f"[EXECUTION ROUTER] Invalid strategy '{strategy_str}', defaulting to SIMPLE")
                strategy = ExecutionStrategy.SIMPLE

            confidence = float(result.get("confidence", 0.8))
            confidence = max(0.0, min(1.0, confidence))

            reasoning = result.get("reasoning", "No reasoning provided")
            escalation_trigger = result.get("escalation_trigger", "operation fails")

            fallback_str = result.get("fallback_strategy", "advanced").lower()
            try:
                fallback_strategy = ExecutionStrategy(fallback_str)
            except ValueError:
                fallback_strategy = ExecutionStrategy.ADVANCED

            decision = {
                "strategy": strategy,
                "confidence": confidence,
                "reasoning": reasoning,
                "escalation_trigger": escalation_trigger,
                "fallback_strategy": fallback_strategy,
                "metadata": {
                    "operation": operation,
                    "song_name": song_name,
                    "artist": artist,
                    "previous_attempts_count": len(previous_attempts),
                    "model": self.model
                }
            }

            logger.info(
                f"[EXECUTION ROUTER] Strategy: {strategy.value.upper()} "
                f"(confidence: {confidence:.2f}) - {reasoning[:100]}"
            )

            # Log to reasoning trace
            if self.reasoning_trace:
                try:
                    from ..memory.reasoning_trace import ReasoningStage, OutcomeStatus
                    self.reasoning_trace.add_entry(
                        stage=ReasoningStage.EXECUTION,
                        thought=f"Routing execution strategy for {operation}: '{song_name}'",
                        action="route_execution_strategy",
                        parameters={
                            "operation": operation,
                            "song_name": song_name,
                            "artist": artist,
                            "strategy": strategy.value
                        },
                        evidence=[
                            f"Strategy: {strategy.value} (confidence: {confidence:.2f})",
                            f"Previous attempts: {len(previous_attempts)}",
                            reasoning[:200]
                        ],
                        outcome=OutcomeStatus.SUCCESS,
                        metadata=decision["metadata"]
                    )
                except Exception as e:
                    logger.debug(f"[EXECUTION ROUTER] Failed to log to reasoning trace: {e}")

            return decision

        except Exception as e:
            logger.error(f"[EXECUTION ROUTER] Routing error: {e}")
            # Fallback to SIMPLE strategy
            return {
                "strategy": ExecutionStrategy.SIMPLE,
                "confidence": 0.5,
                "reasoning": f"Routing failed ({str(e)}), defaulting to simple execution",
                "escalation_trigger": "any failure",
                "fallback_strategy": ExecutionStrategy.ADVANCED,
                "metadata": {
                    "operation": operation,
                    "song_name": song_name,
                    "error": str(e),
                    "fallback": True
                }
            }

    def analyze_screenshot(self, screenshot_path: str, operation: str,
                          song_name: str, artist: Optional[str] = None,
                          previous_attempts: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Analyze a screenshot using vision capabilities to determine next action.

        Args:
            screenshot_path: Path to screenshot file
            operation: Operation being attempted
            song_name: Song name
            artist: Optional artist
            previous_attempts: List of previous failed attempts

        Returns:
            Dictionary with vision analysis and recommended action
        """
        logger.info(f"[EXECUTION ROUTER] Analyzing screenshot for {operation}: '{song_name}'")

        try:
            screenshot_file = Path(screenshot_path).expanduser()
            if not screenshot_file.exists():
                raise FileNotFoundError(f"Screenshot not found: {screenshot_path}")

            image_data = screenshot_file.read_bytes()
            if not image_data:
                raise ValueError("Screenshot file is empty")

            encoded_image = base64.b64encode(image_data).decode("utf-8")
            suffix = screenshot_file.suffix.lower()
            mime_type = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".heic": "image/heic",
            }.get(suffix, "image/png")

            # Build context from previous attempts
            attempts_str = self._format_previous_attempts(previous_attempts or [])

            # Create vision analysis prompt
            prompt = VISION_ANALYSIS_PROMPT.format(
                song_name=song_name,
                artist=artist or "Unknown",
                previous_attempts=attempts_str
            )

            # Call vision model
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {
                            "url": f"data:{mime_type};base64,{encoded_image}"
                        }}
                    ]}
                ],
                max_tokens=500,
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            # Add metadata
            result["metadata"] = {
                "operation": operation,
                "song_name": song_name,
                "artist": artist,
                "screenshot_path": screenshot_path,
                "vision_model": self.vision_model
            }

            logger.info(f"[EXECUTION ROUTER] Vision analysis: {result.get('action_recommended', 'unknown')}")

            return result

        except Exception as e:
            logger.error(f"[EXECUTION ROUTER] Vision analysis failed: {e}")
            return {
                "ui_state": "analysis_failed",
                "action_recommended": "retry_simple",
                "confidence": 0.0,
                "reasoning": f"Vision analysis failed: {str(e)}",
                "error": str(e)
            }

    def should_escalate(self, current_strategy: ExecutionStrategy,
                        result: Dict[str, Any], escalation_trigger: str) -> bool:
        """
        Determine if execution should escalate to a more sophisticated strategy.

        Args:
            current_strategy: Current execution strategy
            result: Execution result
            escalation_trigger: Trigger condition from routing decision

        Returns:
            True if should escalate
        """
        if result.get("success"):
            return False  # Success, no escalation needed

        # Check escalation trigger
        if "error" in escalation_trigger.lower() and result.get("error"):
            return True

        if "fails" in escalation_trigger.lower() and not result.get("success"):
            return True

        # Strategy-specific escalation logic
        if current_strategy == ExecutionStrategy.SIMPLE:
            # Escalate if AppleScript fails
            return result.get("error_type") in ["AppleScriptError", "SpotifyNotRunning", "TimeoutError"]

        elif current_strategy == ExecutionStrategy.ADVANCED:
            # Escalate if browser automation fails
            return result.get("error_type") in ["ElementNotFound", "InteractionFailed"]

        # VISION is the final level, don't escalate further
        return False

    def _build_context_string(self, context: Dict[str, Any]) -> str:
        """Build context string from execution context."""
        context_parts = []

        if context.get("ui_complexity"):
            context_parts.append(f"UI Complexity: {context['ui_complexity']}")

        if context.get("spotify_running") is False:
            context_parts.append("Spotify Status: Not Running")

        if context.get("previous_failures"):
            context_parts.append(f"Previous Failures: {len(context['previous_failures'])}")

        return ", ".join(context_parts) if context_parts else "standard_operation"

    def _should_use_vision_first(self, operation: str, context: Dict[str, Any]) -> bool:
        """
        Determine if we should skip normal routing and go directly to vision.

        Only used for operations that absolutely require vision-based automation.
        Vision should be a last resort, not the default.
        """
        # Check for explicit vision request in context
        if context.get("force_vision"):
            logger.info("[EXECUTION ROUTER] Explicit vision request in context")
            return True

        # Check for complex UI indicators that require vision
        ui_complexity = context.get("ui_complexity", "")
        if any(keyword in ui_complexity.lower() for keyword in [
            "complex", "unpredictable", "dynamic", "interactive", "popup", "ad"
        ]):
            logger.info("[EXECUTION ROUTER] Complex UI detected, using vision")
            return True

        # Check previous failures - only escalate to vision if all other strategies failed
        previous_attempts = context.get("previous_attempts", [])
        simple_failures = sum(1 for attempt in previous_attempts
                             if attempt.get("strategy") == "simple" and
                             attempt.get("success") == False)
        advanced_failures = sum(1 for attempt in previous_attempts
                               if attempt.get("strategy") == "advanced" and
                               attempt.get("success") == False)

        # Only use vision if both simple and advanced strategies have failed
        if simple_failures >= 1 and advanced_failures >= 1:
            logger.info(f"[EXECUTION ROUTER] Both simple ({simple_failures}) and advanced ({advanced_failures}) strategies failed, escalating to vision")
            return True

        return False

    def execute_with_feedback_loop(self, operation: str, song_name: str,
                                  artist: Optional[str] = None,
                                  context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute operation with intelligent feedback loop and strategy escalation.

        1. Route to initial strategy (SIMPLE → ADVANCED → VISION)
        2. Execute with chosen strategy
        3. If fails, escalate and retry
        4. Continue until success or max attempts reached

        This implements the vision feedback loop you requested.
        """
        logger.info(f"[EXECUTION ROUTER] Starting feedback loop execution: {operation}")

        context = context or {}
        all_attempts = context.get("previous_attempts", []).copy()
        max_feedback_attempts = 3

        for attempt in range(max_feedback_attempts):
            try:
                # Get current execution strategy
                strategy_decision = self.route_execution(
                    operation, song_name, artist,
                    {**context, "previous_attempts": all_attempts, "feedback_attempt": attempt}
                )

                strategy = strategy_decision["strategy"]
                logger.info(f"[EXECUTION ROUTER] Attempt {attempt + 1}: Using {strategy.value.upper()} strategy")

                # Execute with chosen strategy
                result = self._execute_with_strategy(strategy, operation, song_name, artist, context)

                # Record this attempt
                attempt_record = {
                    "attempt": attempt + 1,
                    "strategy": strategy.value,
                    "success": result.get("success", False),
                    "error_type": result.get("error_type", "None"),
                    "timestamp": datetime.now().isoformat()
                }
                all_attempts.append(attempt_record)

                # Check if successful
                if result.get("success"):
                    logger.info(f"[EXECUTION ROUTER] Success with {strategy.value.upper()} strategy")
                    result["execution_attempts"] = len(all_attempts)
                    result["final_strategy"] = strategy.value
                    return result

                # Check if we should escalate
                if self.should_escalate(strategy, result, strategy_decision.get("escalation_trigger", "")):
                    logger.info(f"[EXECUTION ROUTER] Escalating from {strategy.value.upper()} due to failure")
                    # Continue to next attempt with escalated strategy
                    continue
                else:
                    # Don't escalate, return current result
                    logger.info(f"[EXECUTION ROUTER] Not escalating, returning result")
                    break

            except Exception as e:
                logger.error(f"[EXECUTION ROUTER] Feedback loop error: {e}")
                all_attempts.append({
                    "attempt": attempt + 1,
                    "strategy": "error",
                    "success": False,
                    "error_type": "ExecutionError",
                    "error": str(e)
                })

        # All attempts failed
        return {
            "success": False,
            "error": True,
            "error_type": "AllStrategiesFailed",
            "error_message": f"All execution strategies failed after {len(all_attempts)} attempts",
            "execution_attempts": len(all_attempts),
            "attempt_history": all_attempts,
            "final_strategy": all_attempts[-1]["strategy"] if all_attempts else "unknown"
        }

    def _execute_with_strategy(self, strategy: ExecutionStrategy, operation: str,
                              song_name: str, artist: Optional[str],
                              context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute operation using the specified strategy.
        """
        if strategy == ExecutionStrategy.SIMPLE:
            return self._execute_simple(operation, song_name, artist, context)

        elif strategy == ExecutionStrategy.ADVANCED:
            return self._execute_advanced(operation, song_name, artist, context)

        elif strategy == ExecutionStrategy.VISION:
            return self._execute_vision(operation, song_name, artist, context)

        else:
            return {
                "success": False,
                "error": True,
                "error_type": "UnknownStrategy",
                "error_message": f"Unknown execution strategy: {strategy}"
            }

    def _execute_simple(self, operation: str, song_name: str,
                       artist: Optional[str], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute using unified playback service (prefers API, falls back to automation)."""
        logger.info("[EXECUTION ROUTER] Executing with SIMPLE strategy")

        # Use unified Spotify playback service
        from ..integrations.spotify_playback_service import SpotifyPlaybackService
        service = SpotifyPlaybackService(self.config)

        if operation == "play_song":
            result = service.play_track(song_name, artist)
            return result.to_dict()
        elif operation == "pause_music":
            result = service.pause()
            return result.to_dict()
        elif operation == "get_status":
            result = service.get_status()
            return result.to_dict()
        else:
            return {
                "success": False,
                "error": True,
                "error_type": "UnsupportedOperation",
                "error_message": f"Simple strategy doesn't support operation: {operation}"
            }

    def _execute_advanced(self, operation: str, song_name: str,
                         artist: Optional[str], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute using advanced browser automation."""
        logger.info("[EXECUTION ROUTER] Executing with ADVANCED strategy")

        # TODO: Implement browser automation version
        # This would use the available browser tools for more sophisticated interaction
        # For now, fall back to simple
        logger.warning("[EXECUTION ROUTER] ADVANCED strategy not fully implemented, falling back to SIMPLE")
        return self._execute_simple(operation, song_name, artist, context)

    def _execute_vision(self, operation: str, song_name: str,
                       artist: Optional[str], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute using vision-based automation."""
        logger.info("[EXECUTION ROUTER] Executing with VISION strategy")

        # Use vision-based Spotify automation
        from ..automation.vision_spotify_automation import VisionSpotifyAutomation
        vision_automation = VisionSpotifyAutomation(self.config)

        if operation == "play_song":
            return vision_automation.play_song_with_vision(song_name, artist)
        else:
            return {
                "success": False,
                "error": True,
                "error_type": "UnsupportedOperation",
                "error_message": f"Vision strategy doesn't support operation: {operation}"
            }

    def _format_previous_attempts(self, attempts: List[Dict[str, Any]]) -> str:
        """Format previous attempts for prompt inclusion."""
        if not attempts:
            return "None"

        formatted = []
        for i, attempt in enumerate(attempts[-3:], 1):  # Last 3 attempts
            strategy = attempt.get("strategy", "unknown")
            error = attempt.get("error_type", "unknown")
            formatted.append(f"{i}. {strategy} → {error}")

        return "; ".join(formatted)
