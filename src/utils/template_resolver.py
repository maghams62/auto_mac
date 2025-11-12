"""
Shared template string resolver for all executors.

This module provides consistent template resolution across:
- PlanExecutor (orchestrator/executor.py)
- AutomationAgent (agent/agent.py)
- Any future executors

Supports both:
- Direct references: "$step1.field" -> value
- Template strings: "Found {$step1.field} items" -> "Found value items"
"""

import re
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def resolve_template_string(template: str, step_results: Dict[int, Any]) -> str:
    """
    Resolve a template string with embedded step references.

    Handles both syntaxes:
    - {$step1.field} - Template syntax (braces included)
    - $step1.field - Direct reference (no braces)

    Args:
        template: String with potential step references
        step_results: Dictionary of step results keyed by step ID

    Returns:
        String with all references resolved

    Examples:
        >>> step_results = {1: {"count": 5, "total": 10}}
        >>> resolve_template_string("Found {$step1.count} items", step_results)
        "Found 5 items"
        >>> resolve_template_string("Price is $step1.total", step_results)
        "Price is 10"
    """
    # Pattern 1: Template syntax with braces {$stepN.field.subfield}
    # Matches: {$step1.field}, {$step1.data.count}, {$step1.files.0.name}, {$step1.results[0].link}
    template_pattern = r'\{\$step(\d+)\.([^}]+)\}'

    # Pattern 2: Direct reference without braces $stepN.field.subfield
    # Matches: $step1.field, $step1.data.count, $step1.files.0.name, $step1.results[0].link
    # Support both dot notation and bracket notation for arrays
    direct_pattern = r'\$step(\d+)\.([\w.\[\]]+)'

    def replace_template(match):
        """Replace {$step1.field} with value."""
        step_id = int(match.group(1))
        field_path = match.group(2)
        return _resolve_field_path(step_id, field_path, step_results, match.group(0))

    def replace_direct(match):
        """Replace $step1.field with value."""
        step_id = int(match.group(1))
        field_path = match.group(2)
        return _resolve_field_path(step_id, field_path, step_results, match.group(0))

    # First, resolve template syntax (with braces)
    resolved = re.sub(template_pattern, replace_template, template)

    # Then, resolve direct references (without braces)
    resolved = re.sub(direct_pattern, replace_direct, resolved)

    # Warn if any unresolved placeholders remain
    _check_unresolved(resolved)

    return resolved


def resolve_direct_reference(reference: str, step_results: Dict[int, Any]) -> Any:
    """
    Resolve a direct step reference like $step1.field.subfield.

    Args:
        reference: Reference string starting with $step
        step_results: Dictionary of step results keyed by step ID

    Returns:
        Resolved value or None if reference is invalid

    Examples:
        >>> step_results = {1: {"data": {"count": 5}}}
        >>> resolve_direct_reference("$step1.data.count", step_results)
        5
    """
    if not reference.startswith("$step"):
        logger.warning(f"Invalid reference (doesn't start with $step): {reference}")
        return None

    # Parse reference: $step1.field.subfield or $step1.results[0].link
    # First, normalize bracket notation to dot notation: results[0] -> results.0
    normalized_ref = re.sub(r'\[(\d+)\]', r'.\1', reference)

    parts = normalized_ref[1:].split(".")  # Remove $ and split
    step_ref = parts[0]  # "step1"
    field_path = parts[1:]  # ["field", "subfield"] or ["results", "0", "link"]

    # Extract step ID
    try:
        step_id = int(step_ref.replace("step", ""))
    except ValueError:
        logger.warning(f"Invalid step ID in reference: {reference}")
        return None

    # Get step result
    step_result = step_results.get(step_id)
    if step_result is None:
        logger.warning(f"Reference {reference} points to non-existent step {step_id}")
        return None

    # Navigate field path
    current_value = step_result
    for field in field_path:
        if isinstance(current_value, dict):
            current_value = current_value.get(field)
        elif isinstance(current_value, list):
            try:
                index = int(field)
                current_value = current_value[index]
            except (ValueError, IndexError):
                logger.warning(
                    f"Invalid list index '{field}' in reference {reference}"
                )
                return None
        else:
            logger.warning(
                f"Cannot drill into field '{field}' (reference {reference}) "
                f"because current value is type {type(current_value).__name__}"
            )
            return None

    if current_value is None:
        logger.warning(f"Reference {reference} resolved to None")

    return current_value


def _resolve_field_path(
    step_id: int,
    field_path: str,
    step_results: Dict[int, Any],
    original: str
) -> str:
    """
    Resolve a field path from a step result.

    Args:
        step_id: Step ID to look up
        field_path: Field path (e.g., "count" or "data.count")
        step_results: Dictionary of step results
        original: Original placeholder text (for fallback)

    Returns:
        String representation of resolved value, or original if resolution fails
    """
    # Build full reference
    reference = f"$step{step_id}.{field_path}"

    # Resolve the reference
    resolved_value = resolve_direct_reference(reference, step_results)

    # Convert to string for template substitution
    if resolved_value is None:
        logger.warning(f"Template placeholder {original} resolved to None")
        return original  # Keep original placeholder if resolution fails
    else:
        return str(resolved_value)


def _check_unresolved(text: str) -> None:
    """
    Check for unresolved placeholders and log warnings.

    Args:
        text: Resolved text to check
    """
    # Check for template syntax
    template_remaining = re.findall(r'\{\$step\d+\.[^}]+\}', text)
    if template_remaining:
        logger.warning(
            f"Template has unresolved template placeholders: {template_remaining}"
        )

    # Check for direct references
    direct_remaining = re.findall(r'\$step\d+\.\w+', text)
    if direct_remaining:
        logger.warning(
            f"Template has unresolved direct references: {direct_remaining}"
        )

    # Check for orphaned braces (sign of partial resolution)
    if "{" in text or "}" in text:
        # Only warn if it looks like unresolved template syntax
        if re.search(r'\{\d+\}', text):  # Pattern like {2}
            logger.warning(
                f"Message contains orphaned braces (possible partial resolution): {text[:100]}"
            )


def resolve_parameters(
    parameters: Dict[str, Any],
    step_results: Dict[int, Any],
    action: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resolve all parameters that may contain step references.

    Args:
        parameters: Dictionary of parameters with potential references
        step_results: Dictionary of step results keyed by step ID
        action: Optional action name (used for special handling, e.g., synthesize_content)

    Returns:
        Dictionary with all references resolved

    Examples:
        >>> params = {"message": "Found {$step1.count} items", "data": "$step1.results"}
        >>> step_results = {1: {"count": 5, "results": [1, 2, 3]}}
        >>> resolve_parameters(params, step_results)
        {"message": "Found 5 items", "data": [1, 2, 3]}
    """
    resolved = {}

    for key, value in parameters.items():
        if isinstance(value, str):
            # Check for direct reference: "$step1.field"
            if value.startswith("$step"):
                resolved_value = resolve_direct_reference(value, step_results)
                resolved[key] = resolved_value if resolved_value is not None else value
            # Check for template string: "Found {$step1.count} items"
            elif "{$step" in value or "$step" in value:
                resolved[key] = resolve_template_string(value, step_results)
            else:
                resolved[key] = value
        elif isinstance(value, list):
            # Special handling for synthesize_content.source_contents
            # Convert structured data (lists, dicts) to JSON strings
            if action == "synthesize_content" and key == "source_contents":
                resolved_list = []
                for item in value:
                    if isinstance(item, str):
                        # Check if it's a reference
                        if item.startswith("$step"):
                            resolved_item = resolve_direct_reference(item, step_results)
                            if resolved_item is not None:
                                # Convert to string if it's not already a string
                                if isinstance(resolved_item, (list, dict)):
                                    if resolved_item:  # Non-empty
                                        resolved_list.append(json.dumps(resolved_item))
                                    else:  # Empty list/dict
                                        resolved_list.append("No items found")
                                else:
                                    resolved_list.append(str(resolved_item))
                            else:
                                resolved_list.append(item)
                        elif "{$step" in item or "$step" in item:
                            resolved_list.append(resolve_template_string(item, step_results))
                        else:
                            resolved_list.append(item)
                    elif isinstance(item, (list, dict)):
                        # Convert structured data to JSON string
                        if item:  # Non-empty
                            resolved_list.append(json.dumps(item))
                        else:  # Empty list/dict
                            resolved_list.append("No items found")
                    else:
                        resolved_list.append(str(item))
                resolved[key] = resolved_list
            else:
                # Recursively resolve list items for other cases
                resolved[key] = [
                    resolve_parameters({"item": item}, step_results, action).get("item", item)
                    if isinstance(item, (str, dict))
                    else item
                    for item in value
                ]
        elif isinstance(value, dict):
            # Recursively resolve nested dictionaries
            resolved[key] = resolve_parameters(value, step_results, action)
        else:
            resolved[key] = value

    return resolved
