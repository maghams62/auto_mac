"""
Utility functions for configuration and logging.
"""

import os
import logging
import yaml
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv, find_dotenv


def load_config(config_path: str = "config.yaml", use_global_manager: bool = True) -> Dict[str, Any]:
    """
    Load configuration from YAML file or global ConfigManager.

    If global ConfigManager is available, uses it for hot-reload support.
    Otherwise, falls back to reading from file.

    Args:
        config_path: Path to config file (used if global manager not available)
        use_global_manager: If True, try to use global ConfigManager first

    Returns:
        Configuration dictionary
    """
    # Try to use global ConfigManager if available (for hot-reload)
    if use_global_manager:
        try:
            from ..config_manager import get_global_config_manager
            manager = get_global_config_manager(config_path)
            return manager.get_config()
        except (ImportError, AttributeError):
            # ConfigManager not initialized yet, fall back to file
            pass

    # Fallback to file-based loading
    # Ensure environment variables are available (loads .env once if present)
    # Always prioritize the project-local .env so the value the developer edits wins.
    project_root = Path(__file__).resolve().parent.parent.parent
    explicit_env = project_root / ".env"
    dotenv_loaded = False

    if explicit_env.exists():
        load_dotenv(explicit_env, override=True)
        dotenv_loaded = True

    if not dotenv_loaded:
        env_path = find_dotenv(usecwd=True)
        if env_path:
            load_dotenv(env_path, override=True)
            dotenv_loaded = True

    if not dotenv_loaded:
        # Fallback: attempt default loading without overriding existing values
        load_dotenv(override=False)

    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Expand environment variables
    config = _expand_env_vars(config)

    return config


def _expand_env_vars(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively expand environment variables in config.

    Args:
        config: Configuration dictionary

    Returns:
        Config with expanded environment variables
    """
    if isinstance(config, dict):
        return {k: _expand_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [_expand_env_vars(item) for item in config]
    elif isinstance(config, str):
        # Replace ${VAR} or $VAR with environment variable
        if config.startswith('${') and config.endswith('}'):
            var_name = config[2:-1]
            return os.getenv(var_name, config)
        return config
    else:
        return config


def save_config(config: Dict[str, Any], config_path: str = "config.yaml") -> None:
    """
    Save configuration to YAML file.
    
    Uses ruamel.yaml if available to preserve comments and structure,
    otherwise falls back to standard yaml library.
    
    Args:
        config: Configuration dictionary to save
        config_path: Path to config file
    """
    config_path = Path(config_path)
    
    try:
        # Try to use ruamel.yaml for better YAML preservation
        from ruamel.yaml import YAML
        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.width = 4096  # Prevent line wrapping
        
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
    except ImportError:
        # Fallback to standard yaml library
        import yaml
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def setup_logging(config: Dict[str, Any]):
    """
    Setup logging configuration.

    Args:
        config: Configuration dictionary
    """
    log_level = config.get('logging', {}).get('level', 'INFO')
    log_file = config.get('logging', {}).get('file', 'data/app.log')

    # Create log directory
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ]
    )

    # Reduce noise from some libraries
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)


def get_temperature_for_model(config: Dict[str, Any], default_temperature: float = 0.7) -> float:
    """
    Get appropriate temperature for the configured model.

    o-series models (o1, o3, o4) only support temperature=1.
    Other models use the config temperature or the provided default.

    Args:
        config: Configuration dictionary
        default_temperature: Default temperature to use if not in config (only for non-o-series)

    Returns:
        Temperature value appropriate for the model
    """
    openai_config = config.get("openai", {})
    model = openai_config.get("model", "gpt-4o")

    # o-series models only support temperature=1
    if model and model.startswith(("o1", "o3", "o4")):
        return 1.0

    # For other models, use config value or default
    return openai_config.get("temperature", default_temperature)


def get_llm_params(config: Dict[str, Any], default_temperature: float = 0.7, max_tokens: int = 2000) -> Dict[str, Any]:
    """
    Get LLM parameters compatible with the configured model.

    o-series models (o1, o3, o4) have special requirements:
    - Only support temperature=1
    - Use max_completion_tokens instead of max_tokens

    Args:
        config: Configuration dictionary
        default_temperature: Default temperature for non-o-series models
        max_tokens: Maximum tokens (will be converted to max_completion_tokens for o-series)

    Returns:
        Dictionary of parameters to pass to ChatOpenAI()
    """
    openai_config = config.get("openai", {})
    model = openai_config.get("model", "gpt-4o")

    params = {
        "model": model,
        "api_key": openai_config.get("api_key"),
    }

    # o-series models have special requirements
    if model and model.startswith(("o1", "o3", "o4")):
        params["temperature"] = 1.0
        params["max_completion_tokens"] = max_tokens
    else:
        params["temperature"] = openai_config.get("temperature", default_temperature)
        params["max_tokens"] = max_tokens

    return params


def ensure_directories():
    """Create necessary directories if they don't exist."""
    directories = [
        'data',
        'data/embeddings',
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


# Export structured logger
from .logger import StructuredLogger, setup_structured_logging, get_logger, RequestContext

# Export writing UI formatter
from .writing_ui_formatter import (
    format_report_for_ui,
    format_slides_for_ui,
    format_synthesis_for_ui,
    format_quick_summary_for_ui,
    format_email_for_ui,
    format_writing_output,
)

# Export JSON parser
from .json_parser import (
    parse_json_with_retry,
    validate_json_structure,
)

__all__ = [
    'load_config',
    'save_config',
    'setup_logging',
    'get_temperature_for_model',
    'get_llm_params',
    'ensure_directories',
    'StructuredLogger',
    'setup_structured_logging',
    'get_logger',
    'RequestContext',
    'format_report_for_ui',
    'format_slides_for_ui',
    'format_synthesis_for_ui',
    'format_quick_summary_for_ui',
    'format_email_for_ui',
    'format_writing_output',
    'parse_json_with_retry',
    'validate_json_structure',
]

