"""
Global ConfigManager singleton for hot-reload support.

This module provides a global ConfigManager instance that can be accessed
from anywhere in the application. Tools should use get_global_config_manager()
or get_config() to access the latest config values.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path

# Import utils functions inside methods to avoid circular imports
logger = logging.getLogger(__name__)

# Global singleton instance
_global_config_manager: Optional['ConfigManager'] = None


class ConfigManager:
    """Manages configuration with hot-reload support."""
    
    def __init__(self, config_path: str = "config.yaml"):
        # Import here to avoid circular import
        from .utils import load_config as _load_config
        self.config_path = Path(config_path)
        # Use use_global_manager=False to avoid circular dependency during init
        self.config = _load_config(str(self.config_path), use_global_manager=False)
        self._verify_api_key()
        logger.info("[CONFIG MANAGER] ConfigManager initialized")
    
    def _verify_api_key(self):
        """Verify OpenAI API key is loaded."""
        api_key = self.config.get("openai", {}).get("api_key", "")
        if not api_key or api_key.startswith("${"):
            logger.error("⚠️  WARNING: OpenAI API key not loaded from .env file!")
            logger.error("   Please ensure .env file exists and contains OPENAI_API_KEY")
            # Try to get from environment as fallback
            import os
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                logger.warning("   Using API key from environment variable instead")
                self.config["openai"]["api_key"] = api_key
            else:
                logger.error("   ❌ No API key found in config or environment!")
        else:
            logger.info(f"✅ OpenAI API key loaded successfully (ends with: ...{api_key[-10:]})")
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return self.config.copy()
    
    def update_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update configuration with new values.
        
        Args:
            updates: Dictionary with config updates (nested structure supported)
            
        Returns:
            Updated configuration
        """
        # Deep merge updates into config, skipping redacted values
        def deep_merge(base: Dict, updates: Dict) -> Dict:
            result = base.copy()
            for key, value in updates.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    # Special handling for credentials to preserve redacted values
                    if key == "credentials" or (isinstance(value, dict) and "password" in value or "mfa_code" in value):
                        merged = result[key].copy()
                        for sub_key, sub_value in value.items():
                            # Don't overwrite with redacted values
                            if sub_value != "***REDACTED***":
                                merged[sub_key] = sub_value
                            elif sub_key not in merged:
                                # If field doesn't exist and is redacted, skip it
                                continue
                        result[key] = merged
                    else:
                        result[key] = deep_merge(result[key], value)
                else:
                    # Don't overwrite with redacted values
                    if value != "***REDACTED***":
                        result[key] = value
            return result
        
        self.config = deep_merge(self.config, updates)
        
        # Save to file
        from .utils import save_config as _save_config, load_config as _load_config
        _save_config(self.config, str(self.config_path))
        logger.info(f"[CONFIG MANAGER] Config updated and saved to {self.config_path}")
        
        # Reload to ensure environment variables are expanded
        # Use use_global_manager=False to reload from file directly
        self.config = _load_config(str(self.config_path), use_global_manager=False)
        
        return self.config
    
    def reload_config(self) -> Dict[str, Any]:
        """Reload configuration from file."""
        from .utils import load_config as _load_config
        # Use use_global_manager=False to reload from file directly
        self.config = _load_config(str(self.config_path), use_global_manager=False)
        self._verify_api_key()
        logger.info("[CONFIG MANAGER] Config reloaded from file")
        return self.config
    
    def update_components(self, agent_registry_ref=None, agent_ref=None, orchestrator_ref=None):
        """
        Update component configs after config change.
        
        Args:
            agent_registry_ref: Reference to AgentRegistry instance
            agent_ref: Reference to AutomationAgent instance
            orchestrator_ref: Reference to WorkflowOrchestrator instance
        """
        # Update config references in components
        if agent_registry_ref:
            agent_registry_ref.config = self.config
            # Update config in all already-instantiated agents within registry
            # New agents will use updated config when lazily created
            for agent_instance in agent_registry_ref.agents.values():
                if hasattr(agent_instance, 'config'):
                    agent_instance.config = self.config
                    # If agent has config_accessor, recreate it
                    if hasattr(agent_instance, 'config_accessor'):
                        from .config_validator import ConfigAccessor
                        agent_instance.config_accessor = ConfigAccessor(self.config)
        
        if agent_ref:
            agent_ref.config = self.config
            # Recreate ConfigAccessor with new config
            from .config_validator import ConfigAccessor
            agent_ref.config_accessor = ConfigAccessor(self.config)
            logger.info("[CONFIG MANAGER] Recreated ConfigAccessor in AutomationAgent")
        
        if orchestrator_ref:
            orchestrator_ref.config = self.config
            # Update config in orchestrator components
            if hasattr(orchestrator_ref, 'indexer') and hasattr(orchestrator_ref.indexer, 'config'):
                orchestrator_ref.indexer.config = self.config
            if hasattr(orchestrator_ref, 'parser') and hasattr(orchestrator_ref.parser, 'config'):
                orchestrator_ref.parser.config = self.config
            if hasattr(orchestrator_ref, 'search') and hasattr(orchestrator_ref.search, 'config'):
                orchestrator_ref.search.config = self.config
            if hasattr(orchestrator_ref, 'mail_composer') and hasattr(orchestrator_ref.mail_composer, 'config'):
                orchestrator_ref.mail_composer.config = self.config
        
        logger.info("[CONFIG MANAGER] Component configs updated")


def get_global_config_manager(config_path: str = "config.yaml") -> ConfigManager:
    """
    Get or create the global ConfigManager singleton.
    
    Args:
        config_path: Path to config file (only used on first call)
        
    Returns:
        Global ConfigManager instance
    """
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = ConfigManager(config_path)
    return _global_config_manager


def set_global_config_manager(manager: ConfigManager):
    """
    Set the global ConfigManager instance (for testing or explicit initialization).
    
    Args:
        manager: ConfigManager instance to use globally
    """
    global _global_config_manager
    _global_config_manager = manager


def get_config() -> Dict[str, Any]:
    """
    Get the latest config from global ConfigManager.
    
    Falls back to load_config() if ConfigManager not initialized.
    
    Returns:
        Configuration dictionary
    """
    global _global_config_manager
    if _global_config_manager is not None:
        return _global_config_manager.get_config()
    else:
        # Fallback to file-based loading
        from .utils import load_config as _load_config
        return _load_config(use_global_manager=False)

