"""
Helper functions for instrumenting tools with OpenTelemetry.
Provides one-line instrumentation for new tools and future integrations.
"""

from typing import Dict, Any, Optional, Callable
from opentelemetry import trace
from .config import get_tracer, sanitize_value, record_event, set_span_error, log_structured

_tracer = get_tracer("auto_mac.tools")

def log_tool_step(tool_name: str, status: str, metadata: Optional[Dict[str, Any]] = None,
                 correlation_id: Optional[str] = None):
    """
    One-line tool instrumentation for telemetry.

    Args:
        tool_name: Name of the tool being executed
        status: 'start', 'success', 'error', or 'cancelled'
        metadata: Additional context (inputs, outputs, duration, etc.)
        correlation_id: Correlation ID for tracing
    """
    metadata = metadata or {}

    if status == "start":
        span = _tracer.start_span(f"tool.{tool_name}")
        if correlation_id:
            span.set_attribute("correlation_id", correlation_id)
        span.set_attribute("tool_name", tool_name)
        span.set_attribute("operation", "start")

        # Record tool start event
        record_event(span, "tool_execution_start", {
            "tool_name": tool_name,
            "correlation_id": correlation_id,
            **metadata
        })

        # Store span in metadata for later completion
        metadata["_span"] = span

        log_structured("info", f"Tool {tool_name} started",
                      tool_name=tool_name, correlation_id=correlation_id, **metadata)

    elif status in ["success", "error", "cancelled"]:
        span = metadata.get("_span")
        if span:
            span.set_attribute("operation", "complete")
            span.set_attribute("final_status", status)

            if status == "success":
                span.set_status(trace.Status(trace.StatusCode.OK))
                record_event(span, "tool_execution_success", {
                    "tool_name": tool_name,
                    "correlation_id": correlation_id,
                    **metadata
                })
            elif status == "error":
                error_msg = metadata.get("error_message", "Unknown error")
                set_span_error(span, Exception(error_msg), {
                    "tool_name": tool_name,
                    "correlation_id": correlation_id,
                    **metadata
                })
            elif status == "cancelled":
                span.set_status(trace.Status(trace.StatusCode.OK, "cancelled"))
                record_event(span, "tool_execution_cancelled", {
                    "tool_name": tool_name,
                    "correlation_id": correlation_id,
                    **metadata
                })

            span.end()

            log_structured("info" if status == "success" else "error",
                          f"Tool {tool_name} {status}",
                          tool_name=tool_name, correlation_id=correlation_id, **metadata)

def instrument_tool_execution(tool_name: str, correlation_id: Optional[str] = None):
    """
    Decorator to automatically instrument tool execution.

    Usage:
        @instrument_tool_execution("search_documents")
        def search_documents(inputs):
            # tool logic here
            return result
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            # Start tool execution
            start_metadata = {
                "inputs": sanitize_value(kwargs if kwargs else args),
            }
            log_tool_step(tool_name, "start", start_metadata, correlation_id)

            try:
                # Execute the tool
                result = func(*args, **kwargs)

                # Record success
                success_metadata = {
                    "inputs": sanitize_value(kwargs if kwargs else args),
                    "outputs": sanitize_value(result),
                    "execution_time_ms": 0,  # Could be enhanced with timing
                }
                log_tool_step(tool_name, "success", success_metadata, correlation_id)

                return result

            except Exception as e:
                # Record error
                error_metadata = {
                    "inputs": sanitize_value(kwargs if kwargs else args),
                    "error_message": str(e),
                    "error_type": type(e).__name__,
                }
                log_tool_step(tool_name, "error", error_metadata, correlation_id)
                raise

        return wrapper
    return decorator

def create_tool_span(tool_name: str, correlation_id: Optional[str] = None) -> trace.Span:
    """
    Create a span for tool execution. Useful for manual span management.

    Returns:
        OpenTelemetry span that should be ended by the caller
    """
    span = _tracer.start_span(f"tool.{tool_name}")
    if correlation_id:
        span.set_attribute("correlation_id", correlation_id)
    span.set_attribute("tool_name", tool_name)
    return span

def record_tool_chain_step(chain_name: str, step_name: str, step_index: int,
                          total_steps: int, correlation_id: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None):
    """
    Record a step in a tool chain execution.

    Args:
        chain_name: Name of the tool chain (e.g., "search_extract_reply")
        step_name: Name of the current step tool
        step_index: Current step number (0-based)
        total_steps: Total steps in chain
        correlation_id: Correlation ID
        metadata: Additional context
    """
    metadata = metadata or {}
    span_name = f"chain.{chain_name}.step_{step_index}"

    span = _tracer.start_span(span_name)
    if correlation_id:
        span.set_attribute("correlation_id", correlation_id)
    span.set_attribute("chain_name", chain_name)
    span.set_attribute("step_name", step_name)
    span.set_attribute("step_index", step_index)
    span.set_attribute("total_steps", total_steps)

    record_event(span, "chain_step_start", {
        "chain_name": chain_name,
        "step_name": step_name,
        "step_index": step_index,
        "total_steps": total_steps,
        "correlation_id": correlation_id,
        **metadata
    })

    log_structured("info", f"Chain {chain_name} step {step_index+1}/{total_steps}: {step_name}",
                  chain_name=chain_name, step_name=step_name, step_index=step_index,
                  total_steps=total_steps, correlation_id=correlation_id, **metadata)

    return span

def record_reply_status(status: str, correlation_id: Optional[str] = None,
                       metadata: Optional[Dict[str, Any]] = None):
    """
    Record reply delivery status.

    Args:
        status: 'reply_sent', 'reply_missing', 'fallback_used'
        correlation_id: Correlation ID
        metadata: Additional context (error details, fallback reason, etc.)
    """
    metadata = metadata or {}

    span = _tracer.start_span(f"reply.{status}")
    if correlation_id:
        span.set_attribute("correlation_id", correlation_id)
    span.set_attribute("reply_status", status)

    if status == "reply_missing":
        span.set_status(trace.Status(trace.StatusCode.ERROR, "Reply not found"))
    elif status == "fallback_used":
        span.set_status(trace.Status(trace.StatusCode.OK, "Fallback reply used"))

    record_event(span, f"reply_{status}", {
        "status": status,
        "correlation_id": correlation_id,
        **metadata
    })

    span.end()

    log_level = "error" if status == "reply_missing" else "warning" if status == "fallback_used" else "info"
    log_structured(log_level, f"Reply status: {status}",
                  reply_status=status, correlation_id=correlation_id, **metadata)
