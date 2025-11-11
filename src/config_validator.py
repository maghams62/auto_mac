"""
Config Validator and Access Layer

Ensures config.yaml is the single source of truth for all user-specific data.
Provides safe accessors that validate fields exist before use and prevent
LLM from hallucinating or accessing undefined user data.
"""

import logging
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when config validation fails."""
    pass


class ConfigAccessor:
    """
    Safe config accessor that validates fields exist before use.
    
    This class ensures:
    1. All user-specific data comes from config
    2. Fields are validated before access
    3. No undefined fields can be accessed
    4. LLM decisions are constrained by available config
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize config accessor.
        
        Args:
            config: Configuration dictionary from load_config()
        """
        self.config = config
        self._validate_structure()

    def _validate_structure(self):
        """Validate that required top-level sections exist."""
        required_sections = [
            "openai",
            "documents",
            "search"
        ]
        
        missing = [section for section in required_sections if section not in self.config]
        if missing:
            raise ConfigValidationError(
                f"Missing required config sections: {', '.join(missing)}"
            )

    def get(self, path: str, default: Any = None, required: bool = False) -> Any:
        """
        Safely get a config value by dot-separated path.
        
        Args:
            path: Dot-separated path (e.g., "documents.folders")
            default: Default value if path doesn't exist
            required: If True, raise error if path doesn't exist
            
        Returns:
            Config value or default
            
        Raises:
            ConfigValidationError: If required=True and path doesn't exist
        """
        parts = path.split(".")
        value = self.config
        
        for part in parts:
            if not isinstance(value, dict) or part not in value:
                if required:
                    raise ConfigValidationError(
                        f"Required config path not found: {path}"
                    )
                return default
            value = value[part]
        
        return value

    # User-specific data accessors with validation

    def get_user_folders(self) -> List[str]:
        """
        Get list of folders user has access to.
        
        Returns:
            List of folder paths
            
        Raises:
            ConfigValidationError: If folders not configured
        """
        folders = self.get("documents.folders", [])
        if not folders:
            raise ConfigValidationError(
                "No document folders configured. User has no folder access."
            )
        
        # Validate folders exist
        valid_folders = []
        for folder in folders:
            folder_path = Path(folder).expanduser()
            if folder_path.exists():
                valid_folders.append(str(folder_path.absolute()))
            else:
                logger.warning(f"Configured folder does not exist: {folder}")
        
        if not valid_folders:
            raise ConfigValidationError(
                "No valid document folders found. Please configure accessible folders in config.yaml"
            )
        
        return valid_folders

    def get_supported_file_types(self) -> List[str]:
        """Get list of supported file types."""
        return self.get("documents.supported_types", [".pdf", ".docx", ".txt"])

    def get_email_config(self) -> Dict[str, Any]:
        """
        Get email configuration.
        
        Returns:
            Email config dict with signature, default_subject_prefix, etc.
        """
        email_config = self.get("email", {})
        return {
            "signature": email_config.get("signature", ""),
            "default_subject_prefix": email_config.get("default_subject_prefix", "[Auto-generated]"),
        }

    def get_imessage_config(self) -> Dict[str, Any]:
        """
        Get iMessage configuration.
        
        Returns:
            iMessage config dict
        """
        imessage_config = self.get("imessage", {})
        default_phone = imessage_config.get("default_phone_number")
        
        if not default_phone:
            logger.warning("No default phone number configured for iMessage")
        
        return {
            "default_phone_number": default_phone,
        }

    def get_discord_config(self) -> Dict[str, Any]:
        """
        Get Discord configuration.
        
        Returns:
            Discord config dict with credentials, defaults, etc.
        """
        discord_config = self.get("discord", {})
        credentials = discord_config.get("credentials", {})
        
        return {
            "default_server": discord_config.get("default_server"),
            "default_channel": discord_config.get("default_channel", "general"),
            "screenshot_dir": discord_config.get("screenshot_dir", "data/screenshots"),
            "switcher_delay_seconds": discord_config.get("switcher_delay_seconds", 0.6),
            "credentials": {
                "email": credentials.get("email"),
                "password": credentials.get("password"),
                "mfa_code": credentials.get("mfa_code"),
            }
        }

    def get_twitter_config(self) -> Dict[str, Any]:
        """
        Get Twitter configuration.
        
        Returns:
            Twitter config dict
        """
        twitter_config = self.get("twitter", {})
        return {
            "default_list": twitter_config.get("default_list"),
            "default_lookback_hours": twitter_config.get("default_lookback_hours", 24),
            "max_summary_items": twitter_config.get("max_summary_items", 5),
            "lists": twitter_config.get("lists", {}),
        }

    def get_bluesky_config(self) -> Dict[str, Any]:
        """
        Get Bluesky configuration.

        Returns:
            Bluesky config dict
        """
        bluesky_config = self.get("bluesky", {})
        return {
            "default_lookback_hours": bluesky_config.get("default_lookback_hours", 24),
            "max_summary_items": bluesky_config.get("max_summary_items", 5),
            "default_search_limit": bluesky_config.get("default_search_limit", 10),
            "default_query": bluesky_config.get("default_query"),
        }

    def get_vision_config(self) -> Dict[str, Any]:
        """
        Get configuration for vision-assisted UI navigation.

        Returns:
            Vision config dict
        """
        vision_config = self.get("vision", {})
        return {
            "enabled": vision_config.get("enabled", False),
            "min_confidence": vision_config.get("min_confidence", 0.6),
            "max_calls_per_session": vision_config.get("max_calls_per_session", 5),
            "max_calls_per_task": vision_config.get("max_calls_per_task", 2),
            "retry_threshold": vision_config.get("retry_threshold", 2),
            "eligible_tools": vision_config.get("eligible_tools", []),
        }

    def get_browser_config(self) -> Dict[str, Any]:
        """
        Get browser configuration.
        
        Returns:
            Browser config dict with allowed domains, headless mode, etc.
        """
        browser_config = self.get("browser", {})
        return {
            "allowed_domains": browser_config.get("allowed_domains", []),
            "headless": browser_config.get("headless", True),
            "timeout": browser_config.get("timeout", 30000),
            "unique_session_search": browser_config.get("unique_session_search", True),
        }

    def get_maps_config(self) -> Dict[str, Any]:
        """Get Maps configuration."""
        maps_config = self.get("maps", {})
        return {
            "max_stops": maps_config.get("max_stops", 20),
            "default_maps_service": maps_config.get("default_maps_service", "apple"),
            "stop_suggestion_max_tokens": maps_config.get("stop_suggestion_max_tokens", 1000),
        }

    def get_openai_config(self) -> Dict[str, Any]:
        """
        Get OpenAI configuration.
        
        Returns:
            OpenAI config dict
        """
        openai_config = self.get("openai", {})
        api_key = openai_config.get("api_key")
        
        if not api_key or api_key.startswith("${"):
            raise ConfigValidationError(
                "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
            )
        
        return {
            "api_key": api_key,
            "model": openai_config.get("model", "gpt-4o"),
            "embedding_model": openai_config.get("embedding_model", "text-embedding-3-small"),
            "temperature": openai_config.get("temperature", 0.7),
            "max_tokens": openai_config.get("max_tokens", 2000),
        }

    def get_search_config(self) -> Dict[str, Any]:
        """Get search configuration."""
        search_config = self.get("search", {})
        return {
            "top_k": search_config.get("top_k", 5),
            "similarity_threshold": search_config.get("similarity_threshold", 0.7),
        }

    def get_user_context_for_llm(self) -> str:
        """
        Generate a user context string for LLM prompts.
        
        This constrains LLM decisions to only use configured user data.
        
        Returns:
            Formatted string describing user's configured access and constraints
        """
        lines = ["=== USER CONFIGURATION (Source of Truth) ==="]
        lines.append("")
        
        # Document folders (user's accessible folders)
        try:
            folders = self.get_user_folders()
            lines.append(f"Document Folders (user has access to): {', '.join(folders)}")
        except ConfigValidationError as e:
            lines.append(f"Document Folders: ERROR - {str(e)}")
        
        lines.append(f"Supported File Types: {', '.join(self.get_supported_file_types())}")
        lines.append("")
        
        # Email config
        email_config = self.get_email_config()
        if email_config.get("signature"):
            lines.append(f"Email Signature: {email_config['signature'][:50]}...")
        lines.append("")
        
        # iMessage config
        imessage_config = self.get_imessage_config()
        if imessage_config.get("default_phone_number"):
            lines.append(f"iMessage Default Recipient: {imessage_config['default_phone_number']}")
        lines.append("")
        
        # Browser allowed domains
        browser_config = self.get_browser_config()
        if browser_config.get("allowed_domains"):
            lines.append(f"Browser Allowed Domains: {', '.join(browser_config['allowed_domains'])}")
        lines.append("")
        
        # Twitter config
        twitter_config = self.get_twitter_config()
        if twitter_config.get("default_list"):
            lines.append(f"Twitter Default List: {twitter_config['default_list']}")
        lines.append("")

        # Bluesky config
        bluesky_config = self.get_bluesky_config()
        default_query = bluesky_config.get("default_query") or "N/A"
        lines.append(f"Bluesky Default Summary Limit: {bluesky_config.get('max_summary_items', 5)}")
        lines.append(f"Bluesky Default Query (optional): {default_query}")
        lines.append("")

        # Vision config
        vision_config = self.get_vision_config()
        vision_status = "enabled" if vision_config.get("enabled") else "disabled"
        lines.append(f"Vision Path: {vision_status} (min_confidence={vision_config.get('min_confidence')})")
        eligible = vision_config.get("eligible_tools") or []
        if eligible:
            lines.append(f"Vision Eligible Tools: {', '.join(eligible)}")
        lines.append("")
        
        lines.append("=== IMPORTANT ===")
        lines.append("- ONLY use folders listed above for file operations")
        lines.append("- ONLY use configured email/iMessage recipients")
        lines.append("- ONLY access browser domains listed above")
        lines.append("- DO NOT invent or assume user data not in this config")
        lines.append("- If a required field is missing, inform the user to configure it")
        lines.append("")
        
        return "\n".join(lines)

    def validate_folder_access(self, folder_path: str) -> bool:
        """
        Validate that a folder path is within user's allowed folders.
        
        Args:
            folder_path: Path to validate
            
        Returns:
            True if folder is accessible, False otherwise
        """
        try:
            allowed_folders = self.get_user_folders()
            folder_abs = str(Path(folder_path).expanduser().absolute())
            
            for allowed in allowed_folders:
                allowed_abs = str(Path(allowed).absolute())
                # Check if folder_path is within allowed folder
                if folder_abs.startswith(allowed_abs):
                    return True
            
            return False
        except ConfigValidationError:
            return False

    def validate_browser_domain(self, domain: str) -> bool:
        """
        Validate that a domain is in the allowed list.
        
        Args:
            domain: Domain to validate (e.g., "example.com")
            
        Returns:
            True if domain is allowed, False otherwise
        """
        browser_config = self.get_browser_config()
        allowed_domains = browser_config.get("allowed_domains", [])
        
        if not allowed_domains:
            # If no restrictions, allow all (but log warning)
            logger.warning("No browser domain restrictions configured")
            return True
        
        # Normalize domain (remove protocol, www, etc.)
        domain_clean = domain.lower().replace("http://", "").replace("https://", "").replace("www.", "").split("/")[0]
        
        for allowed in allowed_domains:
            allowed_clean = allowed.lower().replace("http://", "").replace("https://", "").replace("www.", "").split("/")[0]
            if domain_clean == allowed_clean or domain_clean.endswith("." + allowed_clean):
                return True
        
        return False


def get_config_accessor(config: Optional[Dict[str, Any]] = None) -> ConfigAccessor:
    """
    Get a config accessor instance.
    
    Args:
        config: Optional config dict. If None, loads from file.
        
    Returns:
        ConfigAccessor instance
    """
    if config is None:
        from .utils import load_config
        config = load_config()
    
    return ConfigAccessor(config)
