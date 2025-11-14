"""
Test Verification Helpers

Helper functions for verifying backend tool execution, WebSocket message format,
UI rendering, and completion events across all test layers.
"""

from typing import Dict, Any, List, Optional, Set
import json


def verify_backend_tool_execution(
    messages: List[Dict[str, Any]],
    tool_name: str,
    expected_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Verify that a backend tool was called correctly.
    
    Args:
        messages: List of WebSocket messages from the API
        tool_name: Name of the tool to verify
        expected_params: Expected parameters (partial match - checks if keys exist and values match)
    
    Returns:
        Dictionary with verification results:
        {
            "found": bool,
            "tool_calls": List[Dict],  # All matching tool calls
            "params_match": bool,  # If expected_params provided
            "details": Dict  # Detailed verification info
        }
    """
    tool_calls = [
        msg for msg in messages
        if msg.get("type") == "tool_call" and msg.get("tool_name") == tool_name
    ]
    
    result = {
        "found": len(tool_calls) > 0,
        "tool_calls": tool_calls,
        "params_match": True,
        "details": {}
    }
    
    if expected_params and tool_calls:
        # Check if any tool call matches expected parameters
        params_match = False
        for tool_call in tool_calls:
            params = tool_call.get("parameters", {})
            match = True
            for key, expected_value in expected_params.items():
                if key not in params:
                    match = False
                    break
                actual_value = params.get(key)
                # Allow partial matching (e.g., if expected is substring)
                if isinstance(expected_value, str) and isinstance(actual_value, str):
                    if expected_value.lower() not in str(actual_value).lower():
                        match = False
                        break
                elif actual_value != expected_value:
                    match = False
                    break
            
            if match:
                params_match = True
                result["details"]["matching_call"] = tool_call
                break
        
        result["params_match"] = params_match
        result["details"]["expected_params"] = expected_params
        result["details"]["actual_params"] = [tc.get("parameters", {}) for tc in tool_calls]
    
    return result


def verify_websocket_message_format(
    message: Dict[str, Any],
    expected_type: str,
    required_fields: List[str]
) -> Dict[str, Any]:
    """
    Verify that a WebSocket message has the correct format.
    
    Args:
        message: WebSocket message to verify
        expected_type: Expected message type
        required_fields: List of required field names
    
    Returns:
        Dictionary with verification results:
        {
            "type_match": bool,
            "has_all_fields": bool,
            "missing_fields": List[str],
            "details": Dict
        }
    """
    actual_type = message.get("type")
    type_match = actual_type == expected_type
    
    missing_fields = []
    for field in required_fields:
        if field not in message:
            missing_fields.append(field)
    
    has_all_fields = len(missing_fields) == 0
    
    return {
        "type_match": type_match,
        "has_all_fields": has_all_fields,
        "missing_fields": missing_fields,
        "details": {
            "expected_type": expected_type,
            "actual_type": actual_type,
            "required_fields": required_fields,
            "message_keys": list(message.keys())
        }
    }


def verify_completion_event(
    messages: List[Dict[str, Any]],
    expected_action: Optional[str] = None,
    expected_status: str = "success"
) -> Dict[str, Any]:
    """
    Verify that a completion event was sent with correct action and status.
    
    Args:
        messages: List of WebSocket messages
        expected_action: Expected action name (e.g., "email_sent", "bluesky_posted")
        expected_status: Expected status (default: "success")
    
    Returns:
        Dictionary with verification results:
        {
            "found": bool,
            "action_match": bool,  # If expected_action provided
            "status_match": bool,
            "completion_events": List[Dict],
            "details": Dict
        }
    """
    completion_events = [
        msg for msg in messages
        if msg.get("type") == "completion_event" or (
            msg.get("completion_event") is not None
        )
    ]
    
    # Also check for completion_event nested in messages
    nested_completions = []
    for msg in messages:
        if msg.get("completion_event"):
            nested_completions.append(msg.get("completion_event"))
    
    all_completions = completion_events + nested_completions
    
    result = {
        "found": len(all_completions) > 0,
        "action_match": True,
        "status_match": True,
        "completion_events": all_completions,
        "details": {}
    }
    
    if all_completions:
        # Check status
        status_match = False
        action_match = True  # Default to True if no expected_action
        
        for completion in all_completions:
            # Handle both direct completion_event and nested structure
            if isinstance(completion, dict):
                status = completion.get("status", completion.get("action_status", ""))
                action = completion.get("action", completion.get("action_type", ""))
            else:
                status = getattr(completion, "status", "")
                action = getattr(completion, "action", "")
            
            if status and expected_status.lower() in str(status).lower():
                status_match = True
            
            if expected_action:
                if action and expected_action.lower() not in str(action).lower():
                    action_match = False
                elif not action:
                    action_match = False
        
        result["status_match"] = status_match
        result["action_match"] = action_match if expected_action else True
        result["details"]["expected_action"] = expected_action
        result["details"]["expected_status"] = expected_status
        result["details"]["actual_completions"] = all_completions
    
    return result


def verify_ui_rendering(
    response: Dict[str, Any],
    expected_elements: List[str]
) -> Dict[str, Any]:
    """
    Verify that UI elements are present in the response.
    
    This checks the response message for keywords that indicate UI elements
    would be rendered (e.g., "email sent", "reminder created", etc.)
    
    Args:
        response: API response dictionary
        expected_elements: List of keywords/elements to look for
    
    Returns:
        Dictionary with verification results:
        {
            "elements_found": List[str],
            "elements_missing": List[str],
            "all_present": bool,
            "response_text": str
        }
    """
    response_text = response.get("message", "").lower()
    if not response_text:
        response_text = str(response).lower()
    
    elements_found = []
    elements_missing = []
    
    for element in expected_elements:
        if element.lower() in response_text:
            elements_found.append(element)
        else:
            elements_missing.append(element)
    
    return {
        "elements_found": elements_found,
        "elements_missing": elements_missing,
        "all_present": len(elements_missing) == 0,
        "response_text": response.get("message", "")
    }


def verify_tool_result_data(
    messages: List[Dict[str, Any]],
    tool_name: str,
    expected_data_keys: List[str]
) -> Dict[str, Any]:
    """
    Verify that a tool result contains expected data keys.
    
    Args:
        messages: List of WebSocket messages
        tool_name: Name of the tool
        expected_data_keys: List of keys that should be in the tool result
    
    Returns:
        Dictionary with verification results:
        {
            "tool_result_found": bool,
            "has_all_keys": bool,
            "missing_keys": List[str],
            "result_data": Dict
        }
    """
    tool_results = [
        msg for msg in messages
        if msg.get("type") == "tool_result" and msg.get("tool_name") == tool_name
    ]
    
    if not tool_results:
        return {
            "tool_result_found": False,
            "has_all_keys": False,
            "missing_keys": expected_data_keys,
            "result_data": {}
        }
    
    result_data = tool_results[0].get("result", {})
    if isinstance(result_data, str):
        try:
            result_data = json.loads(result_data)
        except:
            result_data = {}
    
    missing_keys = []
    for key in expected_data_keys:
        if key not in result_data:
            missing_keys.append(key)
    
    return {
        "tool_result_found": True,
        "has_all_keys": len(missing_keys) == 0,
        "missing_keys": missing_keys,
        "result_data": result_data
    }


def verify_multiple_tool_execution(
    messages: List[Dict[str, Any]],
    expected_tools: List[str],
    require_all: bool = True
) -> Dict[str, Any]:
    """
    Verify that multiple tools were executed.
    
    Args:
        messages: List of WebSocket messages
        expected_tools: List of tool names that should be called
        require_all: If True, all tools must be present; if False, at least one
    
    Returns:
        Dictionary with verification results:
        {
            "tools_found": List[str],
            "tools_missing": List[str],
            "all_present": bool,
            "details": Dict
        }
    """
    tool_calls = [
        msg.get("tool_name") for msg in messages
        if msg.get("type") == "tool_call" and msg.get("tool_name")
    ]
    
    tools_found = []
    tools_missing = []
    
    for tool in expected_tools:
        # Allow partial matching (e.g., "email" matches "compose_email")
        found = any(tool.lower() in called_tool.lower() for called_tool in tool_calls)
        if found:
            tools_found.append(tool)
        else:
            tools_missing.append(tool)
    
    all_present = len(tools_missing) == 0 if require_all else len(tools_found) > 0
    
    return {
        "tools_found": tools_found,
        "tools_missing": tools_missing,
        "all_present": all_present,
        "details": {
            "expected_tools": expected_tools,
            "actual_tool_calls": tool_calls,
            "require_all": require_all
        }
    }


def verify_data_source_access(
    messages: List[Dict[str, Any]],
    data_sources: List[str]
) -> Dict[str, Any]:
    """
    Verify that data sources (calendar, email, reminders) were accessed.
    
    Args:
        messages: List of WebSocket messages
        data_sources: List of data source names (e.g., ["calendar", "email", "reminders"])
    
    Returns:
        Dictionary with verification results showing which sources were accessed
    """
    tool_calls = [
        msg.get("tool_name", "").lower() for msg in messages
        if msg.get("type") == "tool_call"
    ]
    
    sources_accessed = {}
    for source in data_sources:
        source_lower = source.lower()
        accessed = any(
            source_lower in tool_name for tool_name in tool_calls
        )
        sources_accessed[source] = accessed
    
    all_accessed = all(sources_accessed.values())
    
    return {
        "sources_accessed": sources_accessed,
        "all_accessed": all_accessed,
        "details": {
            "expected_sources": data_sources,
            "tool_calls": tool_calls
        }
    }

