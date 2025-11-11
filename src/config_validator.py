"""
Config Validator and Access Layer

Ensures config.yaml is the single source of truth for all user-specific data.
Provides safe accessors that validate fields exist before use and prevent
LLM from hallucinating or accessing undefined user data.
"""

import logging
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from .config.models import (
    BrowserSettings,
    BlueskySettings,
    DiscordCredentials,
    DiscordSettings,
    DocumentsSettings,
    EmailSettings,
    IMessageSettings,
    MapsSettings,
    OpenAISettings,
    TwitterSettings,
    VisionSettings,
    VoiceSettings,
    WhatsAppSettings,
)

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

    def get_primary_document_directory(self) -> str:
        """
        Get the primary document directory that automation should operate on.

        Resolution order:
        1. Explicit top-level `document_directory`
        2. First validated entry from `documents.folders`

        Returns:
            Absolute path to the primary document directory

        Raises:
            ConfigValidationError: If no directory is configured or it is inaccessible
        """
        explicit_dir = self.get("document_directory")
        if explicit_dir:
            path = Path(explicit_dir).expanduser()
            if not path.exists():
                raise ConfigValidationError(
                    f"Configured document_directory does not exist: {path}"
                )
            # Ensure the explicit directory is within the user's allowed folders
            if not self.validate_folder_access(str(path)):
                raise ConfigValidationError(
                    f"Configured document_directory is outside allowed folders: {path}"
                )
            return str(path.resolve())

        folders = self.get_user_folders()
        if not folders:
            raise ConfigValidationError(
                "No document folders configured. Cannot resolve primary document directory."
            )

        primary = Path(folders[0]).expanduser()
        if not primary.exists():
            raise ConfigValidationError(
                f"Primary document directory does not exist: {primary}"
            )

        return str(primary.resolve())

    def get_supported_file_types(self) -> List[str]:
        """Get list of supported file types."""
        return self.get("documents.supported_types", [".pdf", ".docx", ".txt"])

    def get_documents_settings(self) -> DocumentsSettings:
        """
        Get validated document settings bundle.

        Returns:
            DocumentsSettings dataclass with primary directory, folders, and supported types.
        """
        primary_directory = self.get_primary_document_directory()
        folders = self.get_user_folders()
        supported_types = self.get_supported_file_types()
        return DocumentsSettings(
            primary_directory=primary_directory,
            folders=folders,
            supported_types=supported_types,
        )

    def get_email_config(self) -> EmailSettings:
        """
        Get email configuration.

        Returns:
            EmailSettings dataclass with validated fields.
        """
        email_config = self.get("email", {})
        default_recipient = email_config.get("default_recipient")

        if not default_recipient:
            raise ConfigValidationError(
                "Default email recipient not configured. Set email.default_recipient in config.yaml."
            )

        account_email = email_config.get("account_email")
        if not account_email:
            logger.warning("No account_email configured - email reading may not be constrained")

        return EmailSettings(
            account_email=account_email,
            default_recipient=default_recipient,
            signature=email_config.get("signature", ""),
            default_subject_prefix=email_config.get("default_subject_prefix", "[Auto-generated]"),
        )

    def get_imessage_config(self) -> IMessageSettings:
        """
        Get iMessage configuration.
        
        Returns:
            IMessageSettings dataclass
        """
        imessage_config = self.get("imessage", {})
        default_phone = imessage_config.get("default_phone_number")
        
        if not default_phone:
            raise ConfigValidationError(
                "No default phone number configured for iMessage. Set imessage.default_phone_number."
            )
        
        return IMessageSettings(default_phone_number=str(default_phone))

    def get_whatsapp_config(self) -> WhatsAppSettings:
        """
        Get WhatsApp configuration.

        Returns:
            WhatsAppSettings dataclass
        """
        whatsapp_config = self.get("whatsapp", {})
        screenshot_dir = whatsapp_config.get("screenshot_dir")

        if not screenshot_dir:
            raise ConfigValidationError(
                "WhatsApp screenshot directory not configured. Set whatsapp.screenshot_dir."
            )

        return WhatsAppSettings(screenshot_dir=str(screenshot_dir))

    def get_discord_config(self) -> DiscordSettings:
        """
        Get Discord configuration.
        
        Returns:
            DiscordSettings dataclass with credentials, defaults, etc.
        """
        discord_config = self.get("discord", {})
        credentials = discord_config.get("credentials", {})
        
        return DiscordSettings(
            default_server=discord_config.get("default_server"),
            default_channel=discord_config.get("default_channel", "general"),
            screenshot_dir=discord_config.get("screenshot_dir", "data/screenshots"),
            switcher_delay_seconds=float(discord_config.get("switcher_delay_seconds", 0.6)),
            credentials=DiscordCredentials(
                email=credentials.get("email"),
                password=credentials.get("password"),
                mfa_code=credentials.get("mfa_code"),
            ),
        )

    def get_twitter_config(self) -> TwitterSettings:
        """
        Get Twitter configuration.
        
        Returns:
            TwitterSettings dataclass
        """
        twitter_config = self.get("twitter", {})
        return TwitterSettings(
            default_list=twitter_config.get("default_list"),
            default_lookback_hours=int(twitter_config.get("default_lookback_hours", 24)),
            max_summary_items=int(twitter_config.get("max_summary_items", 5)),
            lists=twitter_config.get("lists", {}),
        )

    def get_bluesky_config(self) -> BlueskySettings:
        """
        Get Bluesky configuration.

        Returns:
            BlueskySettings dataclass
        """
        bluesky_config = self.get("bluesky", {})
        return BlueskySettings(
            default_lookback_hours=int(bluesky_config.get("default_lookback_hours", 24)),
            max_summary_items=int(bluesky_config.get("max_summary_items", 5)),
            default_search_limit=int(bluesky_config.get("default_search_limit", 10)),
            default_query=bluesky_config.get("default_query"),
        )

    def get_voice_config(self) -> VoiceSettings:
        """
        Get OpenAI voice configuration.

        Returns:
            VoiceSettings dataclass
        """
        voice_config = self.get("voice", {})
        return VoiceSettings(
            default_voice=voice_config.get("default_voice", "alloy"),
            default_speed=float(voice_config.get("default_speed", 1.0)),
            tts_model=voice_config.get("tts_model", "tts-1"),
            stt_model=voice_config.get("stt_model", "whisper-1"),
            audio_output_dir=voice_config.get("audio_output_dir", "data/audio"),
        )

    def get_vision_config(self) -> VisionSettings:
        """
        Get configuration for vision-assisted UI navigation.

        Returns:
            VisionSettings dataclass
        """
        vision_config = self.get("vision", {})
        return VisionSettings(
            enabled=vision_config.get("enabled", False),
            min_confidence=float(vision_config.get("min_confidence", 0.6)),
            max_calls_per_session=int(vision_config.get("max_calls_per_session", 5)),
            max_calls_per_task=int(vision_config.get("max_calls_per_task", 2)),
            retry_threshold=int(vision_config.get("retry_threshold", 2)),
            eligible_tools=vision_config.get("eligible_tools", []),
        )

    def get_browser_config(self) -> BrowserSettings:
        """
        Get browser configuration.
        
        Returns:
            BrowserSettings dataclass with allowed domains, headless mode, etc.
        """
        browser_config = self.get("browser", {})
        return BrowserSettings(
            allowed_domains=browser_config.get("allowed_domains", []),
            headless=browser_config.get("headless", True),
            timeout=int(browser_config.get("timeout", 30000)),
            unique_session_search=browser_config.get("unique_session_search", True),
        )

    def get_maps_config(self) -> MapsSettings:
        """Get Maps configuration."""
        maps_config = self.get("maps", {})
        return MapsSettings(
            max_stops=int(maps_config.get("max_stops", 20)),
            default_maps_service=maps_config.get("default_maps_service", "apple"),
            stop_suggestion_max_tokens=int(maps_config.get("stop_suggestion_max_tokens", 1000)),
            google_maps_api_key=maps_config.get("google_maps_api_key"),
        )

    def get_openai_config(self) -> OpenAISettings:
        """
        Get OpenAI configuration.
        
        Returns:
            OpenAISettings dataclass
        """
        openai_config = self.get("openai", {})
        api_key = openai_config.get("api_key")
        
        if not api_key or api_key.startswith("${"):
            raise ConfigValidationError(
                "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
            )
        
        return OpenAISettings(
            api_key=api_key,
            model=openai_config.get("model", "gpt-4o"),
            embedding_model=openai_config.get("embedding_model", "text-embedding-3-small"),
            temperature=float(openai_config.get("temperature", 0.7)),
            max_tokens=int(openai_config.get("max_tokens", 2000)),
        )

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
        email_settings = self.get_email_config()
        if email_settings.signature:
            lines.append(f"Email Signature: {email_settings.signature[:50]}...")
        lines.append(f"Default Email Recipient: {email_settings.default_recipient}")
        lines.append("")
        
        # iMessage config
        try:
            imessage_settings = self.get_imessage_config()
            lines.append(f"iMessage Default Recipient: {imessage_settings.default_phone_number}")
        except ConfigValidationError as e:
            lines.append(f"iMessage: ERROR - {str(e)}")
        lines.append("")
        
        # Browser allowed domains
        browser_settings = self.get_browser_config()
        if browser_settings.allowed_domains:
            lines.append(f"Browser Allowed Domains: {', '.join(browser_settings.allowed_domains)}")
        else:
            lines.append("Browser Allowed Domains: None configured (all domains blocked)")
        lines.append("")
        
        # Twitter config
        twitter_settings = self.get_twitter_config()
        if twitter_settings.default_list:
            lines.append(f"Twitter Default List: {twitter_settings.default_list}")
        lines.append("")

        # Bluesky config
        bluesky_settings = self.get_bluesky_config()
        default_query = bluesky_settings.default_query or "N/A"
        lines.append(f"Bluesky Default Summary Limit: {bluesky_settings.max_summary_items}")
        lines.append(f"Bluesky Default Query (optional): {default_query}")
        lines.append("")

        # Vision config
        vision_settings = self.get_vision_config()
        vision_status = "enabled" if vision_settings.enabled else "disabled"
        lines.append(f"Vision Path: {vision_status} (min_confidence={vision_settings.min_confidence})")
        eligible = vision_settings.eligible_tools or []
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
        allowed_domains = browser_config.allowed_domains
        
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
