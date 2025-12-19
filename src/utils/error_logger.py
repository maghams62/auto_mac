"""
Enhanced error logging with full context.

Provides comprehensive error logging with stack traces, input parameters,
execution state, and error categorization.
"""

import logging
import traceback
from typing import Dict, Any, Optional, List
from enum import Enum

from .trajectory_logger import get_trajectory_logger
from telemetry.config import get_tracer, set_span_error, sanitize_value

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories of errors for better analysis."""
    NETWORK = "network"
    VALIDATION = "validation"
    EXECUTION = "execution"
    PARSING = "parsing"
    TIMEOUT = "timeout"
    PERMISSION = "permission"
    RESOURCE = "resource"
    UNKNOWN = "unknown"


def categorize_error(error: Exception) -> ErrorCategory:
    """
    Categorize an error based on its type and message.
    
    Args:
        error: Exception to categorize
        
    Returns:
        ErrorCategory enum value
    """
    error_type = type(error).__name__
    error_message = str(error).lower()
    
    # Network errors
    if any(keyword in error_type.lower() or keyword in error_message for keyword in 
           ["connection", "timeout", "network", "http", "ssl", "dns"]):
        return ErrorCategory.NETWORK
    
    # Validation errors
    if any(keyword in error_type.lower() or keyword in error_message for keyword in
           ["validation", "invalid", "missing", "required", "parameter"]):
        return ErrorCategory.VALIDATION
    
    # Parsing errors
    if any(keyword in error_type.lower() or keyword in error_message for keyword in
           ["json", "parse", "decode", "syntax", "format"]):
        return ErrorCategory.PARSING
    
    # Timeout errors
    if "timeout" in error_type.lower() or "timeout" in error_message:
        return ErrorCategory.TIMEOUT
    
    # Permission errors
    if any(keyword in error_type.lower() or keyword in error_message for keyword in
           ["permission", "access", "forbidden", "unauthorized"]):
        return ErrorCategory.PERMISSION
    
    # Resource errors
    if any(keyword in error_type.lower() or keyword in error_message for keyword in
           ["resource", "not found", "missing", "unavailable"]):
        return ErrorCategory.RESOURCE
    
    # Execution errors (default for most exceptions)
    if any(keyword in error_type.lower() for keyword in
           ["error", "exception", "failure"]):
        return ErrorCategory.EXECUTION
    
    return ErrorCategory.UNKNOWN


def is_retryable_error(error: Exception, error_category: ErrorCategory) -> bool:
    """
    Determine if an error is retryable.
    
    Args:
        error: Exception
        error_category: Categorized error category
        
    Returns:
        True if error is retryable
    """
    # Network errors are usually retryable
    if error_category == ErrorCategory.NETWORK:
        return True
    
    # Timeout errors are retryable
    if error_category == ErrorCategory.TIMEOUT:
        return True
    
    # Resource errors might be retryable (temporary unavailability)
    if error_category == ErrorCategory.RESOURCE:
        error_message = str(error).lower()
        if any(keyword in error_message for keyword in ["temporary", "unavailable", "busy", "rate limit"]):
            return True
    
    # Validation and parsing errors are usually not retryable
    if error_category in [ErrorCategory.VALIDATION, ErrorCategory.PARSING]:
        return False
    
    # Permission errors are not retryable
    if error_category == ErrorCategory.PERMISSION:
        return False
    
    # Default: execution errors might be retryable
    return True


def log_error_with_context(
    error: Exception,
    component: str,
    input_data: Optional[Dict[str, Any]] = None,
    execution_state: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    interaction_id: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    span=None
) -> Dict[str, Any]:
    """
    Log error with full context.
    
    Args:
        error: Exception that occurred
        component: Component where error occurred
        input_data: Input data that caused the error
        execution_state: Execution state at time of error
        session_id: Session identifier
        interaction_id: Interaction identifier
        config: Configuration dict
        span: OpenTelemetry span (optional)
        
    Returns:
        Dictionary with error details
    """
    error_category = categorize_error(error)
    is_retryable = is_retryable_error(error, error_category)
    
    # Get full stack trace
    stack_trace = traceback.format_exc()
    
    # Build error details
    error_details = {
        "type": type(error).__name__,
        "message": str(error),
        "category": error_category.value,
        "retryable": is_retryable,
        "stack_trace": stack_trace,
        "input_data": input_data,
        "execution_state": execution_state
    }
    
    # Log to trajectory logger
    trajectory_logger = get_trajectory_logger(config)
    trajectory_logger.log_trajectory(
        session_id=session_id or "unknown",
        interaction_id=interaction_id,
        phase="error",
        component=component,
        decision_type="error_occurred",
        input_data=input_data or {},
        output_data={},
        reasoning=f"Error in {component}: {str(error)}",
        success=False,
        error=error_details
    )
    
    # Log to standard logger with full context
    logger.error(
        f"[ERROR] {component}: {type(error).__name__}: {str(error)}",
        extra={
            "error_type": type(error).__name__,
            "error_message": str(error),
            "error_category": error_category.value,
            "retryable": is_retryable,
            "component": component,
            "input_data": input_data,
            "execution_state": execution_state,
            "stack_trace": stack_trace
        },
        exc_info=True
    )
    
    # Add to OpenTelemetry span if provided
    if span:
        span.set_attribute("error.type", type(error).__name__)
        span.set_attribute("error.message", sanitize_value(str(error), "error.message"))
        span.set_attribute("error.category", error_category.value)
        span.set_attribute("error.retryable", is_retryable)
        if input_data:
            span.set_attribute("error.input_data", sanitize_value(str(input_data), "error.input_data"))
        set_span_error(span, error)
    
    return error_details

