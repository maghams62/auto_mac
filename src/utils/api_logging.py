"""
API and WebSocket logging utilities.

Provides structured logging for API endpoints and WebSocket message flows.
"""

import logging
import time
import json
from typing import Dict, Any, Optional, Callable
from functools import wraps

from .trajectory_logger import get_trajectory_logger
from telemetry.config import get_tracer, sanitize_value, set_span_error

logger = logging.getLogger(__name__)


def sanitize_payload(payload: Any, max_length: int = 1000) -> Any:
    """
    Sanitize payload for logging (remove PII, truncate large values).
    
    Args:
        payload: Payload to sanitize
        max_length: Maximum length for string values
        
    Returns:
        Sanitized payload
    """
    if isinstance(payload, dict):
        sanitized = {}
        for key, value in payload.items():
            # Redact sensitive fields
            if any(sensitive in key.lower() for sensitive in 
                   ["password", "token", "key", "secret", "api_key", "auth"]):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = sanitize_payload(value, max_length)
        return sanitized
    elif isinstance(payload, list):
        return [sanitize_payload(item, max_length) for item in payload[:10]]  # Limit list size
    elif isinstance(payload, str):
        if len(payload) > max_length:
            return payload[:max_length] + "... [TRUNCATED]"
        return payload
    else:
        return payload


def log_api_request(
    method: str,
    path: str,
    status_code: int,
    latency_ms: float,
    request_payload: Optional[Dict[str, Any]] = None,
    response_payload: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    error: Optional[Exception] = None,
    config: Optional[Dict[str, Any]] = None
):
    """
    Log an API request/response.
    
    Args:
        method: HTTP method
        path: Request path
        status_code: Response status code
        latency_ms: Request latency in milliseconds
        request_payload: Request payload (sanitized)
        response_payload: Response payload (sanitized)
        session_id: Session identifier
        error: Exception if request failed
        config: Configuration dict
    """
    trajectory_logger = get_trajectory_logger(config)
    
    # Log to trajectory
    trajectory_logger.log_trajectory(
        session_id=session_id or "unknown",
        interaction_id=None,
        phase="api",
        component="api_server",
        decision_type="api_request",
        input_data={
            "method": method,
            "path": path,
            "request_payload": sanitize_payload(request_payload) if request_payload else None
        },
        output_data={
            "status_code": status_code,
            "response_payload": sanitize_payload(response_payload) if response_payload else None
        },
        reasoning=f"{method} {path} -> {status_code}",
        latency_ms=latency_ms,
        success=200 <= status_code < 400,
        error={
            "type": type(error).__name__,
            "message": str(error)
        } if error else None
    )
    
    # Log to standard logger
    log_level = logging.ERROR if error or status_code >= 400 else logging.INFO
    logger.log(
        log_level,
        f"[API] {method} {path} -> {status_code} ({latency_ms:.2f}ms)",
        extra={
            "method": method,
            "path": path,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "session_id": session_id,
            "error": str(error) if error else None
        }
    )


def log_websocket_event(
    event_type: str,
    session_id: str,
    message_type: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    error: Optional[Exception] = None,
    config: Optional[Dict[str, Any]] = None
):
    """
    Log a WebSocket event.
    
    Args:
        event_type: Event type (connect, disconnect, message, error)
        session_id: Session identifier
        message_type: Message type if event_type is "message"
        payload: Message payload (sanitized)
        error: Exception if event is error
        config: Configuration dict
    """
    trajectory_logger = get_trajectory_logger(config)
    
    # Log to trajectory
    trajectory_logger.log_trajectory(
        session_id=session_id,
        interaction_id=None,
        phase="api",
        component="websocket",
        decision_type=f"websocket_{event_type}",
        input_data={
            "event_type": event_type,
            "message_type": message_type,
            "payload": sanitize_payload(payload) if payload else None
        },
        output_data={},
        reasoning=f"WebSocket {event_type} for session {session_id}",
        success=event_type not in ["error", "disconnect"] or error is None,
        error={
            "type": type(error).__name__,
            "message": str(error)
        } if error else None
    )
    
    # Log to standard logger
    log_level = logging.ERROR if error else logging.INFO
    logger.log(
        log_level,
        f"[WEBSOCKET] {event_type} session={session_id} type={message_type}",
        extra={
            "event_type": event_type,
            "session_id": session_id,
            "message_type": message_type,
            "error": str(error) if error else None
        }
    )


def api_logging_middleware(func: Callable) -> Callable:
    """
    Decorator to add API request/response logging.
    
    Usage:
        @app.post("/api/endpoint")
        @api_logging_middleware
        async def endpoint(request: Request):
            ...
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        from fastapi import Request
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        
        if not request:
            # No request object, just call the function
            return await func(*args, **kwargs)
        
        start_time = time.time()
        method = request.method
        path = request.url.path
        session_id = None
        
        # Try to extract session_id from request
        try:
            if hasattr(request, 'json'):
                body = await request.json()
                session_id = body.get('session_id') if isinstance(body, dict) else None
        except Exception:
            pass
        
        error = None
        status_code = 200
        response_payload = None
        
        try:
            response = await func(*args, **kwargs)
            
            # Try to extract status code and payload from response
            if hasattr(response, 'status_code'):
                status_code = response.status_code
            if hasattr(response, 'body'):
                try:
                    response_payload = json.loads(response.body) if isinstance(response.body, bytes) else response.body
                except Exception:
                    pass
            
            return response
        except Exception as e:
            error = e
            status_code = 500
            raise
        finally:
            latency_ms = (time.time() - start_time) * 1000
            
            # Try to get request payload
            request_payload = None
            try:
                if hasattr(request, 'json'):
                    request_payload = await request.json()
            except Exception:
                pass
            
            log_api_request(
                method=method,
                path=path,
                status_code=status_code,
                latency_ms=latency_ms,
                request_payload=request_payload,
                response_payload=response_payload,
                session_id=session_id,
                error=error,
                config=None  # TODO: Get config from app state
            )
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        from fastapi import Request
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        
        if not request:
            return func(*args, **kwargs)
        
        start_time = time.time()
        method = request.method
        path = request.url.path
        session_id = None
        
        error = None
        status_code = 200
        
        try:
            response = func(*args, **kwargs)
            return response
        except Exception as e:
            error = e
            status_code = 500
            raise
        finally:
            latency_ms = (time.time() - start_time) * 1000
            log_api_request(
                method=method,
                path=path,
                status_code=status_code,
                latency_ms=latency_ms,
                session_id=session_id,
                error=error,
                config=None
            )
    
    import inspect
    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

