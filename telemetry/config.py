"""
OpenTelemetry configuration for backend and frontend runtimes.
Provides shared correlation IDs (session_id + run_id) and redaction rules.
"""

import os
import json
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry, but make it optional
_OPENTELEMETRY_AVAILABLE = False
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.semconv.resource import ResourceAttributes
    _OPENTELEMETRY_AVAILABLE = True
except ImportError:
    # Create stub classes when opentelemetry is not available
    logger.warning("[TELEMETRY] OpenTelemetry not available. Telemetry features will be disabled.")
    
    # Stub classes for when opentelemetry is not available
    class Status:
        def __init__(self, code, description=""):
            self.code = code
            self.description = description
    
    class StatusCode:
        OK = "OK"
        ERROR = "ERROR"
    
    class Span:
        """Stub span class when opentelemetry is not available."""
        def set_attribute(self, key, value):
            pass
        def add_event(self, name, attributes=None):
            pass
        def set_status(self, status):
            pass
        def record_exception(self, exception):
            pass
        def end(self):
            pass
    
    class Tracer:
        """Stub tracer class when opentelemetry is not available."""
        def start_span(self, name):
            return Span()
    
    class TracerProvider:
        """Stub tracer provider when opentelemetry is not available."""
        def add_span_processor(self, processor):
            pass
        def shutdown(self):
            pass
    
    class Resource:
        """Stub resource class when opentelemetry is not available."""
        @staticmethod
        def create(attributes):
            return Resource()
    
    class ResourceAttributes:
        SERVICE_NAME = "service.name"
        SERVICE_VERSION = "service.version"
    
    # Stub module for trace
    class TraceModule:
        Span = Span  # Make Span accessible as trace.Span
        Status = Status  # Make Status accessible as trace.Status
        StatusCode = StatusCode  # Make StatusCode accessible as trace.StatusCode
        def get_tracer(self, name):
            return Tracer()
        def set_tracer_provider(self, provider):
            pass
        def get_tracer_provider(self):
            return None
    
    trace = TraceModule()
    TracerProvider = TracerProvider
    BatchSpanProcessor = None
    OTLPSpanExporter = None
    Status = Status
    StatusCode = StatusCode
    Resource = Resource
    ResourceAttributes = ResourceAttributes

# Telemetry configuration
TELEMETRY_CONFIG = {
    "service_name": "auto_mac_agent",
    "service_version": "1.0.0",
    "environment": os.getenv("ENVIRONMENT", "development"),
    "otlp_endpoint": os.getenv("OTLP_ENDPOINT", "http://localhost:4317"),
    "sample_rate": float(os.getenv("TELEMETRY_SAMPLE_RATE", "1.0")),  # 1.0 = 100% sampling
    "redact_sensitive_fields": [
        "password", "token", "key", "secret", "auth", "credential",
        "api_key", "access_token", "refresh_token", "bearer"
    ],
    "max_attribute_length": 2048,  # Limit attribute values to prevent huge spans
    "max_log_message_length": 4096,  # Limit log messages
}

def create_resource() -> Resource:
    """Create OpenTelemetry resource with service metadata."""
    if not _OPENTELEMETRY_AVAILABLE:
        return Resource()
    return Resource.create({
        ResourceAttributes.SERVICE_NAME: TELEMETRY_CONFIG["service_name"],
        ResourceAttributes.SERVICE_VERSION: TELEMETRY_CONFIG["service_version"],
        # Note: ENVIRONMENT attribute may not be available in all OpenTelemetry versions
        # "environment": TELEMETRY_CONFIG["environment"],
    })

def create_tracer_provider() -> TracerProvider:
    """
    Create and configure the OpenTelemetry tracer provider.
    
    NOTE: If no OTLP collector is running at the configured endpoint (default: localhost:4317),
    spans will still be created but export attempts will fail silently or log warnings.
    This is expected behavior for local development without a collector.
    To disable telemetry entirely, set TELEMETRY_DISABLED=true in environment.
    """
    if not _OPENTELEMETRY_AVAILABLE:
        logger.warning("[TELEMETRY] OpenTelemetry not available, returning stub tracer provider")
        return TracerProvider()
    
    # Check if telemetry is disabled via environment variable
    if os.getenv("TELEMETRY_DISABLED", "").lower() == "true":
        logger.info("[TELEMETRY] Telemetry disabled via TELEMETRY_DISABLED environment variable")
        return TracerProvider()
    
    resource = create_resource()
    tracer_provider = TracerProvider(resource=resource)

    # Configure OTLP exporter
    # Note: If no collector is running, export will fail but spans are still created
    # This allows local development without requiring a collector
    otlp_exporter = OTLPSpanExporter(
        endpoint=TELEMETRY_CONFIG["otlp_endpoint"],
        insecure=True,  # Use insecure for local development
    )

    # Add batch span processor
    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)

    # Set as global tracer provider
    trace.set_tracer_provider(tracer_provider)

    logger.info(f"[TELEMETRY] Initialized OpenTelemetry tracer provider with OTLP endpoint: {TELEMETRY_CONFIG['otlp_endpoint']}")
    logger.info("[TELEMETRY] Note: If no collector is running, export warnings are expected and can be ignored")
    return tracer_provider

def get_tracer(name: str = "auto_mac"):
    """Get a tracer instance for the given name."""
    if not _OPENTELEMETRY_AVAILABLE:
        return Tracer()
    return trace.get_tracer(name)

def sanitize_value(value: Any, field_name: str = "") -> Any:
    """
    Sanitize sensitive data for telemetry.
    
    IMPORTANT: OpenTelemetry attributes must be primitive types (str, int, float, bool)
    or sequences of primitives. Dicts and complex objects must be converted to JSON strings.
    This function ensures all values are telemetry-compatible.
    """
    if isinstance(value, dict):
        # Convert dicts to JSON strings for OpenTelemetry compatibility
        # This prevents "Invalid type dict for attribute" warnings
        try:
            return json.dumps(value, default=str)[:TELEMETRY_CONFIG["max_attribute_length"]]
        except (TypeError, ValueError):
            return str(value)[:TELEMETRY_CONFIG["max_attribute_length"]]
    elif isinstance(value, list):
        # Convert lists to JSON strings if they contain complex objects
        if value and not all(isinstance(item, (str, int, float, bool)) for item in value):
            try:
                return json.dumps(value, default=str)[:TELEMETRY_CONFIG["max_attribute_length"]]
            except (TypeError, ValueError):
                return str(value)[:TELEMETRY_CONFIG["max_attribute_length"]]
        # Simple lists of primitives can be kept as-is (if OpenTelemetry supports them)
        # But to be safe, convert to JSON string
        try:
            return json.dumps(value, default=str)[:TELEMETRY_CONFIG["max_attribute_length"]]
        except (TypeError, ValueError):
            return str(value)[:TELEMETRY_CONFIG["max_attribute_length"]]
    elif isinstance(value, str):
        # Check if this field contains sensitive data
        field_lower = field_name.lower()
        value_lower = value.lower()

        for sensitive in TELEMETRY_CONFIG["redact_sensitive_fields"]:
            if sensitive in field_lower or sensitive in value_lower:
                return "[REDACTED]"

        # Truncate long values
        if len(value) > TELEMETRY_CONFIG["max_attribute_length"]:
            return value[:TELEMETRY_CONFIG["max_attribute_length"]] + "..."

        return value
    else:
        return value

def create_correlation_id(session_id: str, run_id: Optional[str] = None) -> str:
    """Create a correlation ID combining session and run identifiers."""
    if run_id:
        return f"{session_id}:{run_id}"
    return f"{session_id}:default"

def extract_session_from_correlation(correlation_id: str) -> str:
    """Extract session_id from correlation_id."""
    return correlation_id.split(":")[0] if ":" in correlation_id else correlation_id

def extract_run_from_correlation(correlation_id: str) -> str:
    """Extract run_id from correlation_id."""
    parts = correlation_id.split(":")
    return parts[1] if len(parts) > 1 else "default"

def record_event(span, name: str, attributes: Optional[Dict[str, Any]] = None):
    """Record an event on a span with sanitized attributes."""
    if span is None:
        return
    if attributes:
        sanitized = {k: sanitize_value(v, k) for k, v in attributes.items()}
        span.add_event(name, attributes=sanitized)
    else:
        span.add_event(name)

def set_span_error(span, error: Exception, attributes: Optional[Dict[str, Any]] = None):
    """Set span status to error with exception details."""
    if span is None:
        return
    span.set_status(Status(StatusCode.ERROR, str(error)))
    span.record_exception(error)

    if attributes:
        sanitized = {k: sanitize_value(v, k) for k, v in attributes.items()}
        for key, value in sanitized.items():
            span.set_attribute(key, value)

def log_structured(level: str, message: str, **kwargs):
    """Log structured data for telemetry analysis."""
    # Sanitize kwargs
    sanitized_kwargs = {k: sanitize_value(v, k) for k, v in kwargs.items()}

    # Truncate message if too long
    if len(message) > TELEMETRY_CONFIG["max_log_message_length"]:
        message = message[:TELEMETRY_CONFIG["max_log_message_length"]] + "..."

    # Create structured log entry
    # Note: 'message' is a reserved attribute in LogRecord, so we use 'log_message' instead
    log_entry = {
        "level": level,
        "log_message": message,  # Renamed from 'message' to avoid LogRecord conflict
        **sanitized_kwargs
    }

    # Log using appropriate level
    if level == "error":
        logger.error(f"[TELEMETRY] {message}", extra=log_entry)
    elif level == "warning":
        logger.warning(f"[TELEMETRY] {message}", extra=log_entry)
    elif level == "info":
        logger.info(f"[TELEMETRY] {message}", extra=log_entry)
    else:
        logger.debug(f"[TELEMETRY] {message}", extra=log_entry)

# Initialize telemetry on import
_tracer_provider = None

def init_telemetry():
    """Initialize telemetry infrastructure."""
    global _tracer_provider
    if _tracer_provider is None:
        try:
            _tracer_provider = create_tracer_provider()
            logger.info("[TELEMETRY] Telemetry initialization complete")
        except Exception as e:
            logger.warning(f"[TELEMETRY] Failed to initialize telemetry: {e}")
            # Continue without telemetry rather than crashing

def shutdown_telemetry():
    """Shutdown telemetry infrastructure."""
    global _tracer_provider
    if _tracer_provider:
        _tracer_provider.shutdown()
        _tracer_provider = None
        logger.info("[TELEMETRY] Telemetry shutdown complete")

# Auto-initialize on import (only if opentelemetry is available)
# Don't auto-initialize if opentelemetry is missing to avoid errors
if _OPENTELEMETRY_AVAILABLE:
    init_telemetry()
else:
    logger.debug("[TELEMETRY] Skipping auto-initialization (OpenTelemetry not available)")
