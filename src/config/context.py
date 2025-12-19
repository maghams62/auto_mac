"""
Config context helpers.

Centralizes loading of raw configuration together with the validated
`ConfigAccessor` so that downstream modules can depend on a single source
of truth per invocation instead of re-parsing YAML or inventing defaults.
"""

from dataclasses import dataclass
from typing import Dict, Any

from ..utils import load_config
from ..config_validator import ConfigAccessor


@dataclass(frozen=True)
class ConfigContext:
    """Bundle of raw config data and a validated accessor."""

    data: Dict[str, Any]
    accessor: ConfigAccessor


def get_config_context() -> ConfigContext:
    """
    Load configuration and return a validated context bundle.

    Returns:
        ConfigContext with raw data and accessor ready for use.
    """
    config = load_config()
    accessor = ConfigAccessor(config)
    return ConfigContext(data=config, accessor=accessor)
