"""
Typed configuration models for individual feature domains.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict


@dataclass(frozen=True)
class DocumentsSettings:
    primary_directory: str
    folders: List[str]
    supported_types: List[str]


@dataclass(frozen=True)
class EmailSettings:
    account_email: Optional[str]
    default_recipient: str
    signature: str
    default_subject_prefix: str


@dataclass(frozen=True)
class IMessageSettings:
    default_phone_number: str


@dataclass(frozen=True)
class WhatsAppSettings:
    screenshot_dir: str


@dataclass(frozen=True)
class DiscordCredentials:
    email: Optional[str]
    password: Optional[str]
    mfa_code: Optional[str]


@dataclass(frozen=True)
class DiscordSettings:
    default_server: Optional[str]
    default_channel: str
    screenshot_dir: str
    switcher_delay_seconds: float
    credentials: DiscordCredentials


@dataclass(frozen=True)
class BrowserSettings:
    allowed_domains: List[str]
    headless: bool
    timeout: int
    unique_session_search: bool


@dataclass(frozen=True)
class MapsSettings:
    max_stops: int
    default_maps_service: str
    stop_suggestion_max_tokens: int
    google_maps_api_key: Optional[str]


@dataclass(frozen=True)
class TwitterSettings:
    default_list: Optional[str]
    default_lookback_hours: int
    max_summary_items: int
    lists: Dict[str, str]


@dataclass(frozen=True)
class BlueskySettings:
    default_lookback_hours: int
    max_summary_items: int
    default_search_limit: int
    default_query: Optional[str]


@dataclass(frozen=True)
class VoiceSettings:
    default_voice: str
    default_speed: float
    tts_model: str
    stt_model: str
    audio_output_dir: str


@dataclass(frozen=True)
class VisionSettings:
    enabled: bool
    min_confidence: float
    max_calls_per_session: int
    max_calls_per_task: int
    retry_threshold: int
    eligible_tools: List[str]


@dataclass(frozen=True)
class ScreenshotSettings:
    base_dir: str


@dataclass(frozen=True)
class SpotifyAPISettings:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: List[str]
    token_storage_path: Optional[str] = "data/spotify_tokens.json"


@dataclass(frozen=True)
class OpenAISettings:
    api_key: str
    model: str
    embedding_model: str
    temperature: float
    max_tokens: int
