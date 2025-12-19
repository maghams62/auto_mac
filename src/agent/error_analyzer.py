"""
LLM-powered error analysis and recovery strategy service.

Uses OpenAI to analyze errors and suggest recovery strategies including
parameter modifications, alternative approaches, and retry decisions.
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List
from openai import OpenAI

logger = logging.getLogger(__name__)

ERROR_ANALYSIS_SYSTEM_PROMPT = """You are an expert error analyzer specializing in understanding failures and suggesting recovery strategies.

Your job is to analyze error messages and execution context to:
1. Determine the root cause of the error
2. Suggest corrective actions (parameter modifications, alternative approaches)
3. Decide if the error is recoverable or should be reported to the user
4. Recommend whether to retry with modifications or try a different approach

Guidelines:
- Be specific about what went wrong and why
- Suggest concrete parameter modifications when applicable
- For Spotify errors: extract alternative matches from error messages
- Consider context: tool name, parameters, error type, error message
- Recommend retry only if the error seems recoverable
- Be conservative: don't retry if the error suggests a fundamental issue

Always respond with valid JSON only."""

ERROR_ANALYSIS_PROMPT = """Analyze this error and suggest recovery strategies:

Tool: {tool_name}
Parameters: {parameters}
Error Type: {error_type}
Error Message: {error_message}
Attempt Number: {attempt_number}
Context: {context}

Respond with a JSON object:
{{
  "root_cause": "brief explanation of what went wrong",
  "is_recoverable": true/false,
  "should_retry": true/false,
  "retry_recommended": true/false,
  "suggested_parameters": {{"param_name": "modified_value"}},
  "alternative_approach": "description of alternative if retry won't work",
  "reasoning": "explanation of the analysis and recommendations",
  "extracted_alternatives": ["alternative1", "alternative2"]  // For Spotify: extract alternative matches from error
}}

Examples:

Tool: play_song
Parameters: {{"song_name": "Space Song"}}
Error Type: SearchError
Error Message: "Could not play 'Space Song'. Error: syntax error. Alternative matches: Space Oddity by David Bowie, Intergalactic by Beastie Boys"
Attempt Number: 1
Context: {{"user_request": "Play Space Song on Spotify"}}

Response:
{{
  "root_cause": "AppleScript syntax error when searching for 'Space Song', possibly due to special characters or reserved words",
  "is_recoverable": true,
  "should_retry": true,
  "retry_recommended": true,
  "suggested_parameters": {{"song_name": "Space Song by Beach House"}},
  "alternative_approach": "Try alternative matches: Space Oddity by David Bowie or Intergalactic by Beastie Boys, or ask user to clarify",
  "reasoning": "The error mentions alternative matches, suggesting the search partially worked. Adding artist name might help, or we could try the alternatives.",
  "extracted_alternatives": ["Space Oddity by David Bowie", "Intergalactic by Beastie Boys"]
}}

Tool: play_song
Parameters: {{"song_name": "NonexistentSong12345"}}
Error Type: SongNotFound
Error Message: "Could not find 'NonexistentSong12345' in Spotify"
Attempt Number: 2
Context: {{"user_request": "Play NonexistentSong12345"}}

Response:
{{
  "root_cause": "Song does not exist in Spotify",
  "is_recoverable": false,
  "should_retry": false,
  "retry_recommended": false,
  "suggested_parameters": {{}},
  "alternative_approach": "Inform user that the song was not found and suggest checking spelling or trying a different search",
  "reasoning": "Song not found after multiple attempts. This is not recoverable - the song simply doesn't exist.",
  "extracted_alternatives": []
}}

Now analyze this error:
Tool: {tool_name}
Parameters: {parameters}
Error Type: {error_type}
Error Message: {error_message}
Attempt Number: {attempt_number}
Context: {context}

Respond with ONLY the JSON object, no additional text."""


class ErrorAnalyzer:
    """Use LLM to analyze errors and suggest recovery strategies."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the error analyzer.

        Args:
            config: Configuration dictionary with OpenAI settings
        """
        self.config = config
        openai_cfg = config.get("openai", {})
        self.client = OpenAI(api_key=openai_cfg.get("api_key"))
        self.model = openai_cfg.get("model", "gpt-4o")
        # Use moderate temperature for error analysis (need some creativity but also consistency)
        self.temperature = 0.5
        self.max_tokens = openai_cfg.get("max_tokens", 1000)

    def analyze_error(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        error_type: str,
        error_message: str,
        attempt_number: int = 1,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze an error and suggest recovery strategies.

        Args:
            tool_name: Name of the tool that failed
            parameters: Parameters that were used when the error occurred
            error_type: Type of error (e.g., "SearchError", "ValidationError")
            error_message: Full error message
            attempt_number: Current attempt number (1-based)
            context: Additional context (e.g., user_request, previous errors)

        Returns:
            Dictionary with shape:
            {
                "root_cause": str,
                "is_recoverable": bool,
                "should_retry": bool,
                "retry_recommended": bool,
                "suggested_parameters": Dict[str, Any],
                "alternative_approach": str,
                "reasoning": str,
                "extracted_alternatives": List[str]  # For Spotify: alternative matches
            }
        """
        logger.info(f"[ERROR ANALYZER] Analyzing error for {tool_name}: {error_type}")

        context_str = json.dumps(context or {}, indent=2)
        parameters_str = json.dumps(parameters, indent=2)

        try:
            # Determine which parameters to use based on model
            api_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": ERROR_ANALYSIS_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": ERROR_ANALYSIS_PROMPT.format(
                            tool_name=tool_name,
                            parameters=parameters_str,
                            error_type=error_type,
                            error_message=error_message,
                            attempt_number=attempt_number,
                            context=context_str
                        ),
                    },
                ],
                "response_format": {"type": "json_object"},
            }
            
            # Check if model requires max_completion_tokens (newer models)
            if self.model.startswith("o1") or self.model.startswith("o3") or self.model.startswith("o4"):
                api_params["max_completion_tokens"] = self.max_tokens
                # o-series models don't support custom temperature, use default (1)
            else:
                api_params["max_tokens"] = self.max_tokens
                api_params["temperature"] = self.temperature
            
            response = self.client.chat.completions.create(**api_params)

            result = json.loads(response.choices[0].message.content)
            
            # Validate result structure
            if not isinstance(result, dict):
                raise ValueError("LLM response is not a dictionary")
            
            # Ensure required fields with defaults
            analysis = {
                "root_cause": result.get("root_cause", "Unknown error"),
                "is_recoverable": bool(result.get("is_recoverable", False)),
                "should_retry": bool(result.get("should_retry", False)),
                "retry_recommended": bool(result.get("retry_recommended", False)),
                "suggested_parameters": result.get("suggested_parameters", {}),
                "alternative_approach": result.get("alternative_approach", ""),
                "reasoning": result.get("reasoning", "No specific reasoning provided"),
                "extracted_alternatives": result.get("extracted_alternatives", [])
            }
            
            logger.info(
                f"[ERROR ANALYZER] Analysis complete: recoverable={analysis['is_recoverable']}, "
                f"retry={analysis['should_retry']}, root_cause={analysis['root_cause'][:50]}..."
            )
            
            return analysis

        except Exception as e:
            logger.error(f"[ERROR ANALYZER] Error analyzing error: {e}")
            # Fallback: conservative analysis
            return {
                "root_cause": f"Error analysis failed: {str(e)}",
                "is_recoverable": False,
                "should_retry": False,
                "retry_recommended": False,
                "suggested_parameters": {},
                "alternative_approach": "Unable to analyze error - report to user",
                "reasoning": f"Error analyzer failed: {str(e)}",
                "extracted_alternatives": []
            }

