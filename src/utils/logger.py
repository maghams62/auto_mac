"""
Comprehensive logging utility with structured logging, context tracking, and file rotation.
"""
import logging
import json
import sys
import traceback
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from logging.handlers import RotatingFileHandler
import uuid


class StructuredLogger:
    """
    Structured logger that adds context (session_id, request_id, etc.) to all log entries.
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize structured logger.
        
        Args:
            name: Logger name (typically __name__)
            config: Optional config dict for log settings
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self.config = config or {}
        self._context: Dict[str, Any] = {}
        
    def set_context(self, **kwargs):
        """Set context that will be included in all log messages."""
        self._context.update(kwargs)
        
    def clear_context(self):
        """Clear all context."""
        self._context.clear()
        
    def update_context(self, **kwargs):
        """Update context (alias for set_context)."""
        self.set_context(**kwargs)
        
    def _format_message(self, level: str, message: str, extra: Optional[Dict[str, Any]] = None) -> str:
        """Format log message with context."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "logger": self.name,
            "message": message,
            **self._context
        }
        
        if extra:
            log_entry.update(extra)
            
        return json.dumps(log_entry, default=str)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        formatted = self._format_message("DEBUG", message, kwargs)
        self.logger.debug(formatted)
        
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        formatted = self._format_message("INFO", message, kwargs)
        self.logger.info(formatted)
        
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        formatted = self._format_message("WARNING", message, kwargs)
        self.logger.warning(formatted)
        
    def error(self, message: str, exc_info: bool = False, **kwargs):
        """Log error message with context."""
        if exc_info:
            kwargs['exception'] = traceback.format_exc()
        formatted = self._format_message("ERROR", message, kwargs)
        self.logger.error(formatted, exc_info=exc_info)
        
    def exception(self, message: str, **kwargs):
        """Log exception with traceback."""
        self.error(message, exc_info=True, **kwargs)
        
    def critical(self, message: str, **kwargs):
        """Log critical message with context."""
        formatted = self._format_message("CRITICAL", message, kwargs)
        self.logger.critical(formatted)


def setup_structured_logging(config: Dict[str, Any]) -> None:
    """
    Setup structured logging with file rotation and JSON formatting.
    
    Args:
        config: Configuration dictionary
    """
    log_config = config.get('logging', {})
    log_level = log_config.get('level', 'INFO')
    log_file = log_config.get('file', 'data/app.log')
    max_bytes = log_config.get('max_bytes', 10 * 1024 * 1024)  # 10MB default
    backup_count = log_config.get('backup_count', 5)
    json_format = log_config.get('json_format', True)
    
    # Check if async logging is enabled (for future async handler implementation)
    perf_config = config.get('performance', {})
    background_config = perf_config.get('background_tasks', {})
    async_logging_enabled = background_config.get('logging', True)
    
    # Note: Currently using synchronous handlers. When async logging is implemented,
    # use async_logging_enabled flag to choose between async and sync handlers.
    
    # Create log directory
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    
    if json_format:
        # JSON format for structured logging
        file_handler.setFormatter(logging.Formatter('%(message)s'))
    else:
        # Human-readable format
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
    
    # Console handler (always human-readable)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Reduce noise from some libraries
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    
    # Log initialization
    logger = logging.getLogger(__name__)
    logger.info(f"Structured logging initialized: level={log_level}, file={log_file}")


def get_logger(name: str, config: Optional[Dict[str, Any]] = None) -> StructuredLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        config: Optional config dict
        
    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name, config)


# Context manager for request logging
class RequestContext:
    """Context manager for request-scoped logging."""
    
    def __init__(self, logger: StructuredLogger, request_id: Optional[str] = None, **context):
        self.logger = logger
        self.request_id = request_id or str(uuid.uuid4())
        self.context = context
        self.original_context = {}
        
    def __enter__(self):
        self.original_context = self.logger._context.copy()
        self.logger.set_context(
            request_id=self.request_id,
            **self.context
        )
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger._context = self.original_context

