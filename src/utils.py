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
            from .config_manager import get_global_config_manager
            manager = get_global_config_manager(config_path)
            return manager.get_config()
        except (ImportError, AttributeError):
            # ConfigManager not initialized yet, fall back to file
            pass

    # Fallback to file-based loading
    # Ensure environment variables are available (loads .env once if present)
    # Always prioritize the project-local .env so the value the developer edits wins.
    project_root = Path(__file__).resolve().parent.parent
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


def ensure_directories():
    """Create necessary directories if they don't exist."""
    directories = [
        'data',
        'data/embeddings',
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
