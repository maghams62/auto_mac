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
    ContextResolutionSettings,
    DiscordCredentials,
    DiscordSettings,
    DocumentsSettings,
    EmailSettings,
    ImpactEvidenceSettings,
    ImpactPipelineSettings,
    ImpactNotificationSettings,
    ImpactSettings,
    IMessageSettings,
    MapsSettings,
    OpenAISettings,
    ScreenshotSettings,
    SpotifyAPISettings,
    TraceabilitySettings,
    TwitterSettings,
    VisionSettings,
    VoiceSettings,
    WhatsAppSettings,
)
from .utils.screenshot import DEFAULT_SCREENSHOT_DIR

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when config validation fails."""
    pass


def _parse_impact_level(
    value: Optional[Union[str, int]],
    *,
    default: str,
) -> str:
    """
    Normalize user-provided impact level strings.
    """
    allowed = {"low", "medium", "high"}
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized not in allowed:
        raise ConfigValidationError(
            f"Invalid impact.notifications.min_impact_level '{value}'. "
            "Expected one of: low, medium, high."
        )
    return normalized


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
        self._validate_metadata_cache_settings()

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

    def _validate_metadata_cache_settings(self) -> None:
        metadata_cache = self.config.get("metadata_cache", {})
        slack_cfg = metadata_cache.get("slack", {})
        git_cfg = metadata_cache.get("git", {})

        def _validate_positive_int(value: Any, path: str, *, allow_zero: bool = False) -> None:
            if value is None:
                return
            try:
                int_value = int(value)
            except (TypeError, ValueError):
                raise ConfigValidationError(f"{path} must be an integer.")
            if allow_zero:
                if int_value < 0:
                    raise ConfigValidationError(f"{path} must be zero or greater.")
            else:
                if int_value <= 0:
                    raise ConfigValidationError(f"{path} must be greater than zero.")

        def _validate_bool(value: Any, path: str) -> None:
            if value is None:
                return
            if not isinstance(value, bool):
                raise ConfigValidationError(f"{path} must be true or false.")

        _validate_positive_int(slack_cfg.get("ttl_seconds"), "metadata_cache.slack.ttl_seconds")
        _validate_positive_int(slack_cfg.get("max_items"), "metadata_cache.slack.max_items")
        _validate_bool(slack_cfg.get("log_metrics"), "metadata_cache.slack.log_metrics")

        _validate_positive_int(git_cfg.get("repo_ttl_seconds"), "metadata_cache.git.repo_ttl_seconds")
        _validate_positive_int(git_cfg.get("branch_ttl_seconds"), "metadata_cache.git.branch_ttl_seconds")
        _validate_positive_int(
            git_cfg.get("max_branches_per_repo"),
            "metadata_cache.git.max_branches_per_repo",
        )
        _validate_bool(git_cfg.get("log_metrics"), "metadata_cache.git.log_metrics")

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

    def get_screenshot_config(self) -> ScreenshotSettings:
        """
        Get global screenshot configuration.

        Returns:
            ScreenshotSettings dataclass with the base directory.
        """
        screenshots_config = self.get("screenshots", {})
        base_dir = screenshots_config.get("base_dir", DEFAULT_SCREENSHOT_DIR)
        path = Path(base_dir).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return ScreenshotSettings(base_dir=str(path))

    def get_traceability_settings(self) -> TraceabilitySettings:
        """
        Get traceability configuration (investigation storage + graph hooks).
        """
        traceability_cfg = self.get("traceability", {})
        investigations_path = traceability_cfg.get("investigations_path", "data/live/investigations.jsonl")
        max_entries = int(traceability_cfg.get("max_entries", 500))
        neo4j_cfg = traceability_cfg.get("neo4j", {}) or {}
        neo4j_enabled = bool(neo4j_cfg.get("enabled", False))
        retention_days = int(traceability_cfg.get("retention_days", 30))
        max_file_bytes = int(traceability_cfg.get("max_file_bytes", 5 * 1024 * 1024))
        missing_evidence_threshold = int(traceability_cfg.get("missing_evidence_threshold", 5))
        missing_evidence_window_seconds = int(traceability_cfg.get("missing_evidence_window_seconds", 3600))
        enabled = bool(traceability_cfg.get("enabled", True))

        return TraceabilitySettings(
            investigations_path=str(investigations_path),
            max_entries=max_entries,
            retention_days=retention_days,
            max_file_bytes=max_file_bytes,
            missing_evidence_threshold=missing_evidence_threshold,
            missing_evidence_window_seconds=missing_evidence_window_seconds,
            enabled=enabled,
            neo4j_enabled=neo4j_enabled,
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

    def get_context_resolution_settings(self) -> ContextResolutionSettings:
        """
        Return normalized context resolution configuration used by impact analysis.
        """
        cr_cfg = self.get("context_resolution", {})
        dependency_files = [
            str(path) for path in cr_cfg.get("dependency_files", []) or []
        ]
        repo_mode = str(cr_cfg.get("repo_mode", "polyrepo"))
        activity_window = int(cr_cfg.get("activity_window_hours", 168))

        impact_cfg = cr_cfg.get("impact", {}) or {}
        evidence_cfg = impact_cfg.get("evidence", {}) or {}
        pipeline_cfg = impact_cfg.get("pipeline", {}) or {}

        evidence = ImpactEvidenceSettings(
            llm_enabled=bool(evidence_cfg.get("llm_enabled", False)),
            llm_model=evidence_cfg.get("llm_model"),
            max_bullets=int(evidence_cfg.get("max_bullets", 5)),
        )
        pipeline = ImpactPipelineSettings(
            slack_lookup_hours=int(pipeline_cfg.get("slack_lookup_hours", 72)),
            git_lookup_hours=int(pipeline_cfg.get("git_lookup_hours", 168)),
            notify_slack=bool(pipeline_cfg.get("notify_slack", False)),
        )
        notifications_cfg = impact_cfg.get("notifications", {}) or {}
        min_impact_level = _parse_impact_level(
            notifications_cfg.get("min_impact_level"),
            default="high",
        )
        notifications = ImpactNotificationSettings(
            enabled=bool(notifications_cfg.get("enabled", False)),
            slack_channel=notifications_cfg.get("slack_channel"),
            github_app_id=notifications_cfg.get("github_app_id"),
            min_impact_level=min_impact_level,
        )
        impact = ImpactSettings(
            default_max_depth=int(impact_cfg.get("default_max_depth", 2)),
            include_docs=bool(impact_cfg.get("include_docs", True)),
            include_services=bool(impact_cfg.get("include_services", True)),
            include_components=bool(impact_cfg.get("include_components", True)),
            include_slack_threads=bool(impact_cfg.get("include_slack_threads", True)),
            max_recommendations=int(impact_cfg.get("max_recommendations", 5)),
            evidence=evidence,
            pipeline=pipeline,
            notifications=notifications,
        )
        return ContextResolutionSettings(
            dependency_files=dependency_files,
            repo_mode=repo_mode,
            activity_window_hours=activity_window,
            impact=impact,
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

    def get_spotify_api_config(self) -> SpotifyAPISettings:
        """
        Get Spotify API configuration.

        Returns:
            SpotifyAPISettings dataclass with client credentials and OAuth settings.
        """
        spotify_config = self.get("spotify_api", {})
        client_id = spotify_config.get("client_id")
        client_secret = spotify_config.get("client_secret")
        redirect_uri = spotify_config.get("redirect_uri")

        # Validate required fields
        missing = []
        if not client_id or client_id.startswith("${"):
            missing.append("client_id")
        if not client_secret or client_secret.startswith("${"):
            missing.append("client_secret")
        if not redirect_uri or redirect_uri.startswith("${"):
            missing.append("redirect_uri")

        if missing:
            raise ConfigValidationError(
                f"Spotify API credentials not configured. Missing: {', '.join(missing)}. "
                "Set SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, and SPOTIFY_REDIRECT_URI environment variables."
            )

        scopes = spotify_config.get("scopes", [
            "user-read-playback-state",
            "user-modify-playback-state",
            "user-read-currently-playing",
            "streaming"
        ])

        token_storage_path = spotify_config.get("token_storage_path", "data/spotify_tokens.json")

        return SpotifyAPISettings(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scopes=scopes,
            token_storage_path=token_storage_path,
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
