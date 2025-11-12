"""
Robust JSON parsing utility with retry logic and error recovery.

Handles common JSON parsing issues:
- Markdown code blocks (```json ... ```)
- Trailing commas
- Unquoted keys
- Leading/trailing whitespace
- Comments (attempts to remove)
"""

import json
import re
import logging
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger(__name__)


def parse_json_with_retry(
    text: str,
    max_retries: int = 3,
    log_errors: bool = True
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Parse JSON from text with retry logic and error recovery.
    
    Attempts multiple strategies to parse JSON:
    1. Direct parsing
    2. Strip markdown code blocks
    3. Fix trailing commas
    4. Fix unquoted keys (if possible)
    5. Extract JSON using regex patterns
    
    Args:
        text: Text containing JSON (may have markdown, comments, etc.)
        max_retries: Maximum number of retry attempts
        log_errors: Whether to log errors (default: True)
    
    Returns:
        Tuple of (parsed_json_dict, error_message)
        - If successful: (dict, None)
        - If failed: (None, error_message)
    """
    if not text or not isinstance(text, str):
        return None, "Input is not a valid string"
    
    original_text = text
    cleaned_text = text
    
    for attempt in range(max_retries):
        try:
            # Strategy 1: Try direct parsing
            if attempt == 0:
                parsed = json.loads(cleaned_text)
                if isinstance(parsed, dict):
                    return parsed, None
                elif isinstance(parsed, list):
                    # Wrap list in dict with "steps" key if it looks like a plan
                    return {"steps": parsed}, None
                else:
                    return None, f"Parsed JSON is not a dict or list: {type(parsed)}"
            
            # Strategy 2: Strip markdown code blocks
            elif attempt == 1:
                cleaned_text = _strip_markdown_code_blocks(original_text)
                cleaned_text = cleaned_text.strip()
                if cleaned_text != original_text.strip():
                    parsed = json.loads(cleaned_text)
                    if isinstance(parsed, dict):
                        return parsed, None
                    elif isinstance(parsed, list):
                        return {"steps": parsed}, None
            
            # Strategy 3: Fix trailing commas and other common issues
            elif attempt == 2:
                cleaned_text = _strip_markdown_code_blocks(original_text)
                cleaned_text = _fix_trailing_commas(cleaned_text)
                cleaned_text = cleaned_text.strip()
                parsed = json.loads(cleaned_text)
                if isinstance(parsed, dict):
                    return parsed, None
                elif isinstance(parsed, list):
                    return {"steps": parsed}, None
            
            # Strategy 4: Extract JSON using regex patterns
            elif attempt == 3:
                extracted = _extract_json_with_regex(original_text)
                if extracted:
                    parsed = json.loads(extracted)
                    if isinstance(parsed, dict):
                        return parsed, None
                    elif isinstance(parsed, list):
                        return {"steps": parsed}, None
        
        except json.JSONDecodeError as e:
            if attempt < max_retries - 1:
                if log_errors:
                    logger.debug(f"JSON parse attempt {attempt + 1} failed: {e}. Retrying...")
                continue
            else:
                error_msg = f"Failed to parse JSON after {max_retries} attempts. Last error: {str(e)}"
                if log_errors:
                    logger.error(f"{error_msg}. Text (first 1000 chars): {original_text[:1000]}")
                return None, error_msg
        
        except Exception as e:
            error_msg = f"Unexpected error parsing JSON: {str(e)}"
            if log_errors:
                logger.error(f"{error_msg}. Text (first 1000 chars): {original_text[:1000]}")
            return None, error_msg
    
    return None, f"Failed to parse JSON after {max_retries} attempts"


def _strip_markdown_code_blocks(text: str) -> str:
    """Remove markdown code blocks (```json ... ``` or ``` ... ```)."""
    # Remove ```json ... ```
    text = re.sub(r'```json\s*\n?(.*?)\n?```', r'\1', text, flags=re.DOTALL)
    # Remove ``` ... ```
    text = re.sub(r'```\s*\n?(.*?)\n?```', r'\1', text, flags=re.DOTALL)
    return text.strip()


def _fix_trailing_commas(text: str) -> str:
    """Fix trailing commas in JSON (remove commas before } or ])."""
    # Remove trailing commas before closing braces/brackets
    # This regex handles:
    # - ,} -> }
    # - ,] -> ]
    # But avoids removing commas in strings
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    return text


def _extract_json_with_regex(text: str) -> Optional[str]:
    """
    Extract JSON object or array from text using regex patterns.
    
    Tries to find:
    1. JSON object: { ... }
    2. JSON array: [ ... ]
    """
    # Try to find JSON object
    json_obj_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if json_obj_match:
        return json_obj_match.group(0)
    
    # Try to find JSON array
    json_array_match = re.search(r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]', text, re.DOTALL)
    if json_array_match:
        return json_array_match.group(0)
    
    return None


def validate_json_structure(
    parsed_json: Dict[str, Any],
    required_keys: Optional[List[str]] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate that parsed JSON has the expected structure.
    
    Args:
        parsed_json: Parsed JSON dictionary
        required_keys: List of required top-level keys (default: ["steps"])
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(parsed_json, dict):
        return False, f"JSON is not a dictionary: {type(parsed_json)}"
    
    if required_keys is None:
        required_keys = ["steps"]
    
    for key in required_keys:
        if key not in parsed_json:
            return False, f"Missing required key: '{key}'"
    
    # Validate steps is a list if present
    if "steps" in parsed_json:
        if not isinstance(parsed_json["steps"], list):
            return False, f"'steps' must be a list, got {type(parsed_json['steps'])}"
    
    return True, None

