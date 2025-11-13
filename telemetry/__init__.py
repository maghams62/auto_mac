"""
Telemetry package for auto_mac agent.
Provides OpenTelemetry integration and observability tools.
"""

from .config import (
    init_telemetry,
    shutdown_telemetry,
    get_tracer,
    create_correlation_id,
    extract_session_from_correlation,
    extract_run_from_correlation,
    log_structured,
    TELEMETRY_CONFIG,
    _tracer_provider
)

from .tool_helpers import (
    log_tool_step,
    instrument_tool_execution,
    create_tool_span,
    record_tool_chain_step,
    record_reply_status
)

def get_telemetry():
    """Get the telemetry tracer for manual instrumentation."""
    return get_tracer()

__all__ = [
    # Config
    "init_telemetry",
    "shutdown_telemetry",
    "get_telemetry",
    "get_tracer",
    "create_correlation_id",
    "extract_session_from_correlation",
    "extract_run_from_correlation",
    "log_structured",
    "TELEMETRY_CONFIG",

    # Tool helpers
    "log_tool_step",
    "instrument_tool_execution",
    "create_tool_span",
    "record_tool_chain_step",
    "record_reply_status",
]
