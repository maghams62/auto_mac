"""
Configuration validation and propagation utilities.

Ensures all performance-critical components receive and validate
performance config with proper defaults.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PerformanceConfigDefaults:
    """Default values for performance configuration."""
    connection_pooling_enabled: bool = True
    connection_pooling_max_connections: int = 100
    connection_pooling_max_keepalive: int = 50
    connection_pooling_keepalive_expiry: float = 30.0
    
    rate_limiting_enabled: bool = True
    rate_limiting_rpm_limit: int = 10000
    rate_limiting_tpm_limit: int = 2_000_000
    rate_limiting_burst_size: int = 100
    rate_limiting_safety_margin: float = 0.9
    
    parallel_execution_enabled: bool = True
    parallel_execution_max_parallel_steps: int = 5
    parallel_execution_max_parallel_llm_calls: int = 3
    parallel_execution_dependency_analysis: bool = True
    
    batch_embeddings_enabled: bool = True
    batch_embeddings_batch_size: int = 100
    batch_embeddings_max_concurrent_batches: int = 2
    
    caching_tool_catalog: bool = True
    caching_prompt_templates: bool = True
    caching_embeddings: bool = True
    
    background_tasks_verification: bool = True
    background_tasks_memory_updates: bool = True
    background_tasks_logging: bool = True
    
    session_serialization_use_msgpack: bool = False
    session_serialization_write_behind: bool = True
    session_serialization_write_behind_interval: int = 30
    session_serialization_compression_threshold: int = 100_000


class ConfigValidator:
    """
    Validates and normalizes performance configuration.
    
    Ensures all performance-critical components have valid config
    with proper defaults when values are missing.
    """
    
    def __init__(self, defaults: Optional[PerformanceConfigDefaults] = None):
        """
        Initialize config validator.
        
        Args:
            defaults: Optional custom defaults (uses PerformanceConfigDefaults if None)
        """
        self.defaults = defaults or PerformanceConfigDefaults()
    
    def validate_performance_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize performance configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Validated performance config with defaults applied
        """
        perf_config = config.get("performance", {})
        
        # Validate and set defaults for each section
        validated = {
            "connection_pooling": self._validate_connection_pooling(
                perf_config.get("connection_pooling", {})
            ),
            "rate_limiting": self._validate_rate_limiting(
                perf_config.get("rate_limiting", {})
            ),
            "parallel_execution": self._validate_parallel_execution(
                perf_config.get("parallel_execution", {})
            ),
            "batch_embeddings": self._validate_batch_embeddings(
                perf_config.get("batch_embeddings", {})
            ),
            "caching": self._validate_caching(
                perf_config.get("caching", {})
            ),
            "background_tasks": self._validate_background_tasks(
                perf_config.get("background_tasks", {})
            ),
            "session_serialization": self._validate_session_serialization(
                perf_config.get("session_serialization", {})
            )
        }
        
        # Log warnings for disabled optimizations
        self._log_disabled_optimizations(validated)
        
        return validated
    
    def _validate_connection_pooling(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate connection pooling config."""
        return {
            "enabled": config.get("enabled", self.defaults.connection_pooling_enabled),
            "max_connections": config.get("max_connections", self.defaults.connection_pooling_max_connections),
            "max_keepalive": config.get("max_keepalive", self.defaults.connection_pooling_max_keepalive),
            "keepalive_expiry": config.get("keepalive_expiry", self.defaults.connection_pooling_keepalive_expiry)
        }
    
    def _validate_rate_limiting(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate rate limiting config."""
        return {
            "enabled": config.get("enabled", self.defaults.rate_limiting_enabled),
            "rpm_limit": config.get("rpm_limit", self.defaults.rate_limiting_rpm_limit),
            "tpm_limit": config.get("tpm_limit", self.defaults.rate_limiting_tpm_limit),
            "burst_size": config.get("burst_size", self.defaults.rate_limiting_burst_size),
            "safety_margin": config.get("safety_margin", self.defaults.rate_limiting_safety_margin)
        }
    
    def _validate_parallel_execution(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate parallel execution config."""
        return {
            "enabled": config.get("enabled", self.defaults.parallel_execution_enabled),
            "max_parallel_steps": config.get("max_parallel_steps", self.defaults.parallel_execution_max_parallel_steps),
            "max_parallel_llm_calls": config.get("max_parallel_llm_calls", self.defaults.parallel_execution_max_parallel_llm_calls),
            "dependency_analysis": config.get("dependency_analysis", self.defaults.parallel_execution_dependency_analysis)
        }
    
    def _validate_batch_embeddings(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate batch embeddings config."""
        return {
            "enabled": config.get("enabled", self.defaults.batch_embeddings_enabled),
            "batch_size": config.get("batch_size", self.defaults.batch_embeddings_batch_size),
            "max_concurrent_batches": config.get("max_concurrent_batches", self.defaults.batch_embeddings_max_concurrent_batches)
        }
    
    def _validate_caching(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate caching config."""
        return {
            "tool_catalog": config.get("tool_catalog", self.defaults.caching_tool_catalog),
            "prompt_templates": config.get("prompt_templates", self.defaults.caching_prompt_templates),
            "embeddings": config.get("embeddings", self.defaults.caching_embeddings)
        }
    
    def _validate_background_tasks(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate background tasks config."""
        return {
            "verification": config.get("verification", self.defaults.background_tasks_verification),
            "memory_updates": config.get("memory_updates", self.defaults.background_tasks_memory_updates),
            "logging": config.get("logging", self.defaults.background_tasks_logging)
        }
    
    def _validate_session_serialization(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate session serialization config."""
        return {
            "use_msgpack": config.get("use_msgpack", self.defaults.session_serialization_use_msgpack),
            "write_behind": config.get("write_behind", self.defaults.session_serialization_write_behind),
            "write_behind_interval": config.get("write_behind_interval", self.defaults.session_serialization_write_behind_interval),
            "compression_threshold": config.get("compression_threshold", self.defaults.session_serialization_compression_threshold)
        }
    
    def _log_disabled_optimizations(self, validated: Dict[str, Any]):
        """Log warnings for disabled optimizations."""
        warnings = []
        
        if not validated["connection_pooling"]["enabled"]:
            warnings.append("Connection pooling is disabled")
        if not validated["rate_limiting"]["enabled"]:
            warnings.append("Rate limiting is disabled")
        if not validated["parallel_execution"]["enabled"]:
            warnings.append("Parallel execution is disabled")
        if not validated["batch_embeddings"]["enabled"]:
            warnings.append("Batch embeddings is disabled")
        if not validated["caching"]["tool_catalog"]:
            warnings.append("Tool catalog caching is disabled")
        if not validated["caching"]["prompt_templates"]:
            warnings.append("Prompt template caching is disabled")
        if not validated["background_tasks"]["memory_updates"]:
            warnings.append("Background memory updates are disabled")
        
        if warnings:
            logger.warning(f"[CONFIG VALIDATOR] Performance optimizations disabled: {', '.join(warnings)}")
    
    def ensure_performance_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure performance config exists in config dictionary with defaults.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Config with validated performance section
        """
        if "performance" not in config:
            config["performance"] = {}
        
        validated = self.validate_performance_config(config)
        config["performance"] = validated
        
        return config
    
    def get_performance_config(self, config: Dict[str, Any], section: str, key: str, default: Any = None) -> Any:
        """
        Get a performance config value with validation.
        
        Args:
            config: Configuration dictionary
            section: Performance section name (e.g., "connection_pooling")
            key: Config key name
            default: Default value if not found
            
        Returns:
            Config value or default
        """
        validated = self.validate_performance_config(config)
        section_config = validated.get(section, {})
        return section_config.get(key, default)


# Global validator instance
_validator = ConfigValidator()


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize entire config with performance defaults.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Validated config
    """
    return _validator.ensure_performance_config(config)


def get_performance_config_value(config: Dict[str, Any], section: str, key: str, default: Any = None) -> Any:
    """
    Get a performance config value with validation.
    
    Args:
        config: Configuration dictionary
        section: Performance section name
        key: Config key name
        default: Default value if not found
        
    Returns:
        Config value or default
    """
    return _validator.get_performance_config(config, section, key, default)

