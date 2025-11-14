"""
Centralized LLM call wrapper for logging and telemetry.

Wraps all LLM calls to provide consistent logging, token tracking, latency measurement,
and OpenTelemetry instrumentation.
"""

import logging
import time
from typing import Dict, Any, Optional, Callable, TypeVar, Awaitable
from functools import wraps
import traceback

from .trajectory_logger import get_trajectory_logger
from telemetry.config import get_tracer, sanitize_value, record_event, set_span_error

logger = logging.getLogger(__name__)

T = TypeVar('T')


class LLMCallLogger:
    """Logs LLM calls with full context."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize LLM call logger.
        
        Args:
            config: Optional configuration dict
        """
        self.config = config or {}
        self.trajectory_logger = get_trajectory_logger(config)
        self.tracer = get_tracer("llm_wrapper")
    
    def log_call(
        self,
        model: str,
        prompt: Any,
        response: Any,
        tokens_used: Optional[Dict[str, int]] = None,
        latency_ms: float = 0.0,
        success: bool = True,
        error: Optional[Exception] = None,
        session_id: Optional[str] = None,
        interaction_id: Optional[str] = None,
        component: str = "unknown",
        decision_type: str = "llm_call",
        **extra_context
    ):
        """
        Log an LLM call.
        
        Args:
            model: Model name used
            prompt: Input prompt (will be sanitized/truncated)
            response: Response content (will be sanitized/truncated)
            tokens_used: Token usage dict with prompt/completion/total
            latency_ms: Latency in milliseconds
            success: Whether call was successful
            error: Exception if failed
            session_id: Session identifier
            interaction_id: Interaction identifier
            component: Component making the call
            decision_type: Type of decision/operation
            **extra_context: Additional context
        """
        # Prepare input/output data
        input_data = {
            "model": model,
            "prompt_length": len(str(prompt)) if prompt else 0,
            "prompt_preview": str(prompt)[:500] + "..." if prompt and len(str(prompt)) > 500 else str(prompt) if prompt else None
        }
        
        output_data = {
            "response_length": len(str(response)) if response else 0,
            "response_preview": str(response)[:500] + "..." if response and len(str(response)) > 500 else str(response) if response else None
        }
        
        if tokens_used:
            output_data["tokens_used"] = tokens_used
        
        # Log to trajectory logger
        if session_id:
            self.trajectory_logger.log_trajectory(
                session_id=session_id,
                interaction_id=interaction_id,
                phase="planning" if "plan" in decision_type.lower() else "execution",
                component=component,
                decision_type=decision_type,
                input_data=input_data,
                output_data=output_data,
                model_used=model,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
                success=success,
                error={
                    "type": type(error).__name__ if error else None,
                    "message": str(error) if error else None,
                    "traceback": traceback.format_exc() if error else None
                } if error else None,
                **extra_context
            )
        
        # Log to standard logger
        log_level = logging.ERROR if error else logging.INFO
        logger.log(
            log_level,
            f"[LLM CALL] model={model} component={component} latency={latency_ms:.2f}ms "
            f"tokens={tokens_used.get('total', 0) if tokens_used else 'N/A'} success={success}",
            extra={
                "model": model,
                "component": component,
                "latency_ms": latency_ms,
                "tokens_used": tokens_used,
                "success": success,
                "error": str(error) if error else None
            }
        )
    
    def create_span(self, model: str, component: str, operation: str = "llm_call"):
        """Create OpenTelemetry span for LLM call."""
        span = self.tracer.start_span(f"{operation}.{component}")
        span.set_attribute("llm.model", model)
        span.set_attribute("llm.component", component)
        return span


# Global LLM call logger instance
_llm_call_logger: Optional[LLMCallLogger] = None


def get_llm_call_logger(config: Optional[Dict[str, Any]] = None) -> LLMCallLogger:
    """Get or create global LLM call logger instance."""
    global _llm_call_logger
    if _llm_call_logger is None:
        _llm_call_logger = LLMCallLogger(config)
    return _llm_call_logger


def extract_token_usage(response: Any) -> Optional[Dict[str, int]]:
    """
    Extract token usage from LLM response.
    
    Works with LangChain responses and OpenAI API responses.
    """
    if hasattr(response, 'response_metadata'):
        # LangChain response
        metadata = response.response_metadata
        if 'token_usage' in metadata:
            usage = metadata['token_usage']
            return {
                "prompt": usage.get('prompt_tokens', 0),
                "completion": usage.get('completion_tokens', 0),
                "total": usage.get('total_tokens', 0)
            }
    
    if hasattr(response, 'usage'):
        # OpenAI API response
        usage = response.usage
        return {
            "prompt": usage.prompt_tokens if hasattr(usage, 'prompt_tokens') else 0,
            "completion": usage.completion_tokens if hasattr(usage, 'completion_tokens') else 0,
            "total": usage.total_tokens if hasattr(usage, 'total_tokens') else 0
        }
    
    return None


def log_llm_call(
    model: str,
    prompt: Any,
    response: Any,
    latency_ms: float,
    success: bool = True,
    error: Optional[Exception] = None,
    session_id: Optional[str] = None,
    interaction_id: Optional[str] = None,
    component: str = "unknown",
    decision_type: str = "llm_call",
    **extra_context
):
    """
    Convenience function to log an LLM call.
    
    Args:
        model: Model name
        prompt: Input prompt
        response: Response (can be None if error)
        latency_ms: Latency in milliseconds
        success: Whether call succeeded
        error: Exception if failed
        session_id: Session identifier
        interaction_id: Interaction identifier
        component: Component making call
        decision_type: Type of decision
        **extra_context: Additional context
    """
    logger = get_llm_call_logger()
    tokens_used = extract_token_usage(response) if response and success else None
    
    logger.log_call(
        model=model,
        prompt=prompt,
        response=response.content if hasattr(response, 'content') else response,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
        success=success,
        error=error,
        session_id=session_id,
        interaction_id=interaction_id,
        component=component,
        decision_type=decision_type,
        **extra_context
    )


def wrap_llm_call(
    component: str = "unknown",
    decision_type: str = "llm_call",
    session_id: Optional[str] = None,
    interaction_id: Optional[str] = None
):
    """
    Decorator to wrap LLM calls with logging and telemetry.
    
    Usage:
        @wrap_llm_call(component="planner", decision_type="plan_creation", session_id=session_id)
        async def create_plan(...):
            response = await self.llm.ainvoke(messages)
            return response
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            call_logger = get_llm_call_logger()
            start_time = time.time()
            error = None
            response = None
            model = "unknown"
            
            # Try to extract model from args/kwargs
            if 'model' in kwargs:
                model = kwargs['model']
            elif args and hasattr(args[0], 'model_name'):
                model = args[0].model_name
            elif args and hasattr(args[0], 'model'):
                model = args[0].model
            
            # Create OpenTelemetry span
            span = call_logger.create_span(model, component, decision_type)
            span.set_attribute("llm.operation", decision_type)
            
            try:
                response = await func(*args, **kwargs)
                latency_ms = (time.time() - start_time) * 1000
                
                # Extract token usage
                tokens_used = extract_token_usage(response)
                if tokens_used:
                    span.set_attribute("llm.tokens.prompt", tokens_used.get("prompt", 0))
                    span.set_attribute("llm.tokens.completion", tokens_used.get("completion", 0))
                    span.set_attribute("llm.tokens.total", tokens_used.get("total", 0))
                
                span.set_attribute("llm.latency_ms", latency_ms)
                span.set_attribute("llm.success", True)
                
                # Log the call
                log_llm_call(
                    model=model,
                    prompt=kwargs.get('messages') or kwargs.get('prompt') or args[1] if len(args) > 1 else None,
                    response=response,
                    latency_ms=latency_ms,
                    success=True,
                    session_id=session_id,
                    interaction_id=interaction_id,
                    component=component,
                    decision_type=decision_type
                )
                
                return response
            except Exception as e:
                error = e
                latency_ms = (time.time() - start_time) * 1000
                
                span.set_attribute("llm.latency_ms", latency_ms)
                span.set_attribute("llm.success", False)
                set_span_error(span, e)
                
                # Log the error
                log_llm_call(
                    model=model,
                    prompt=kwargs.get('messages') or kwargs.get('prompt') or args[1] if len(args) > 1 else None,
                    response=None,
                    latency_ms=latency_ms,
                    success=False,
                    error=e,
                    session_id=session_id,
                    interaction_id=interaction_id,
                    component=component,
                    decision_type=decision_type
                )
                
                raise
            finally:
                span.end()
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            call_logger = get_llm_call_logger()
            start_time = time.time()
            error = None
            response = None
            model = "unknown"
            
            # Try to extract model from args/kwargs
            if 'model' in kwargs:
                model = kwargs['model']
            elif args and hasattr(args[0], 'model_name'):
                model = args[0].model_name
            elif args and hasattr(args[0], 'model'):
                model = args[0].model
            
            # Create OpenTelemetry span
            span = call_logger.create_span(model, component, decision_type)
            span.set_attribute("llm.operation", decision_type)
            
            try:
                response = func(*args, **kwargs)
                latency_ms = (time.time() - start_time) * 1000
                
                # Extract token usage
                tokens_used = extract_token_usage(response)
                if tokens_used:
                    span.set_attribute("llm.tokens.prompt", tokens_used.get("prompt", 0))
                    span.set_attribute("llm.tokens.completion", tokens_used.get("completion", 0))
                    span.set_attribute("llm.tokens.total", tokens_used.get("total", 0))
                
                span.set_attribute("llm.latency_ms", latency_ms)
                span.set_attribute("llm.success", True)
                
                # Log the call
                log_llm_call(
                    model=model,
                    prompt=kwargs.get('messages') or kwargs.get('prompt') or args[1] if len(args) > 1 else None,
                    response=response,
                    latency_ms=latency_ms,
                    success=True,
                    session_id=session_id,
                    interaction_id=interaction_id,
                    component=component,
                    decision_type=decision_type
                )
                
                return response
            except Exception as e:
                error = e
                latency_ms = (time.time() - start_time) * 1000
                
                span.set_attribute("llm.latency_ms", latency_ms)
                span.set_attribute("llm.success", False)
                set_span_error(span, e)
                
                # Log the error
                log_llm_call(
                    model=model,
                    prompt=kwargs.get('messages') or kwargs.get('prompt') or args[1] if len(args) > 1 else None,
                    response=None,
                    latency_ms=latency_ms,
                    success=False,
                    error=e,
                    session_id=session_id,
                    interaction_id=interaction_id,
                    component=component,
                    decision_type=decision_type
                )
                
                raise
            finally:
                span.end()
        
        # Return appropriate wrapper based on whether function is async
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

