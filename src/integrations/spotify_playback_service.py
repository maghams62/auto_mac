"""
Spotify Playback Service - Unified interface for Spotify playback operations.

This service provides a consistent API for music playback that can delegate to either:
1. Spotify Web API (preferred, new implementation)
2. AppleScript automation (fallback, legacy implementation)

The service automatically chooses the best available backend based on configuration
and authentication status, providing seamless migration from automation to API.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from enum import Enum

logger = logging.getLogger(__name__)


class PlaybackBackend(Enum):
    """Available playback backends."""
    API = "api"           # Spotify Web API
    AUTOMATION = "automation"  # AppleScript automation (legacy)


class PlaybackResult:
    """Standardized result from playback operations."""

    def __init__(self, success: bool, action: str, message: str = "",
                 track: Optional[str] = None, artist: Optional[str] = None,
                 backend: PlaybackBackend = None, error_type: Optional[str] = None,
                 error_message: Optional[str] = None, retry_possible: bool = True):
        self.success = success
        self.action = action
        self.message = message
        self.track = track
        self.artist = artist
        self.backend = backend
        self.error_type = error_type
        self.error_message = error_message
        self.retry_possible = retry_possible

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for agent responses."""
        result = {
            "success": self.success,
            "action": self.action,
            "message": self.message,
            "backend": self.backend.value if self.backend else None,
        }

        if self.track:
            result["track"] = self.track
        if self.artist:
            result["track_artist"] = self.artist

        if not self.success:
            result.update({
                "error": True,
                "error_type": self.error_type,
                "error_message": self.error_message,
                "retry_possible": self.retry_possible
            })

        return result


class SpotifyPlaybackBackend(ABC):
    """Abstract base class for Spotify playback backends."""

    @abstractmethod
    def play(self) -> PlaybackResult:
        """Start or resume playback."""
        pass

    @abstractmethod
    def pause(self) -> PlaybackResult:
        """Pause current playback."""
        pass

    @abstractmethod
    def get_status(self) -> PlaybackResult:
        """Get current playback status."""
        pass

    @abstractmethod
    def play_track(self, track_identifier: str, artist: Optional[str] = None) -> PlaybackResult:
        """Play a specific track by URI or search query."""
        pass

    @abstractmethod
    def play_album(self, album_identifier: str, artist: Optional[str] = None) -> PlaybackResult:
        """Play a specific album by URI or search query."""
        pass

    @abstractmethod
    def play_artist(self, artist_identifier: str) -> PlaybackResult:
        """Play an artist's top tracks by URI or search query."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available and authenticated."""
        pass

    @property
    @abstractmethod
    def backend_type(self) -> PlaybackBackend:
        """Get the backend type."""
        pass


class SpotifyAPIBackend(SpotifyPlaybackBackend):
    """Spotify Web API backend implementation."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._api_client = None
        self._web_player_device_id: Optional[str] = None

    def set_web_player_device_id(self, device_id: str):
        """Set the web player device ID to target for playback."""
        self._web_player_device_id = device_id
        logger.info(f"[SPOTIFY API BACKEND] Set web player device ID: {device_id}")

    def _is_spotify_uri(self, uri_string: str) -> bool:
        """Check if a string is a valid Spotify URI."""
        return uri_string.startswith("spotify:") and any(
            uri_string.startswith(f"spotify:{entity}:")
            for entity in ["track", "album", "artist", "playlist"]
        )

    def _resolve_track_to_uri(self, track_query: str, artist_hint: Optional[str] = None) -> Optional[str]:
        """Search for a track and return its URI."""
        try:
            client = self._get_api_client()
            if not client:
                return None

            # Build search query
            query = track_query
            if artist_hint:
                query = f"{track_query} {artist_hint}"

            search_result = client.search_tracks(query, limit=1)
            tracks = search_result.get("tracks", {}).get("items", [])

            if tracks:
                return tracks[0]["uri"]
            else:
                logger.warning(f"[SPOTIFY API BACKEND] No tracks found for query: {query}")
                return None

        except Exception as e:
            logger.error(f"[SPOTIFY API BACKEND] Error resolving track '{track_query}': {e}")
            return None

    def _resolve_album_to_uri(self, album_query: str, artist_hint: Optional[str] = None) -> Optional[str]:
        """Search for an album and return its URI."""
        try:
            client = self._get_api_client()
            if not client:
                return None

            # Build search query
            query = album_query
            if artist_hint:
                query = f"{album_query} {artist_hint}"

            search_result = client.search_albums(query, limit=1)
            albums = search_result.get("albums", {}).get("items", [])

            if albums:
                return albums[0]["uri"]
            else:
                logger.warning(f"[SPOTIFY API BACKEND] No albums found for query: {query}")
                return None

        except Exception as e:
            logger.error(f"[SPOTIFY API BACKEND] Error resolving album '{album_query}': {e}")
            return None

    def _resolve_artist_to_uri(self, artist_query: str) -> Optional[str]:
        """Search for an artist and return their URI."""
        try:
            client = self._get_api_client()
            if not client:
                return None

            search_result = client.search_artists(artist_query, limit=1)
            artists = search_result.get("artists", {}).get("items", [])

            if artists:
                return artists[0]["uri"]
            else:
                logger.warning(f"[SPOTIFY API BACKEND] No artists found for query: {artist_query}")
                return None

        except Exception as e:
            logger.error(f"[SPOTIFY API BACKEND] Error resolving artist '{artist_query}': {e}")
            return None

    @property
    def backend_type(self) -> PlaybackBackend:
        return PlaybackBackend.API

    def _get_api_client(self):
        """Get or create API client instance."""
        if self._api_client is None:
            try:
                from .spotify_api import SpotifyAPIClient
                from ..config_validator import get_config_accessor

                accessor = get_config_accessor(self.config)
                api_config = accessor.get_spotify_api_config()

                self._api_client = SpotifyAPIClient(
                    client_id=api_config.client_id,
                    client_secret=api_config.client_secret,
                    redirect_uri=api_config.redirect_uri,
                    token_storage_path=api_config.token_storage_path,
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Spotify API client: {e}")
                self._api_client = None

        return self._api_client

    def is_available(self) -> bool:
        """Check if API backend is available."""
        client = self._get_api_client()
        return client is not None and client.is_authenticated()

    def play(self) -> PlaybackResult:
        """Resume playback using API."""
        try:
            client = self._get_api_client()
            if not client:
                return PlaybackResult(
                    success=False, action="play", backend=self.backend_type,
                    error_type="APINotAvailable", error_message="Spotify API not available"
                )

            result = client.resume_playback()
            return PlaybackResult(
                success=True, action="play", message="Resumed playback",
                backend=self.backend_type
            )
        except Exception as e:
            logger.error(f"API play failed: {e}")
            return PlaybackResult(
                success=False, action="play", backend=self.backend_type,
                error_type="APIError", error_message=str(e)
            )

    def pause(self) -> PlaybackResult:
        """Pause playback using API."""
        try:
            client = self._get_api_client()
            if not client:
                return PlaybackResult(
                    success=False, action="pause", backend=self.backend_type,
                    error_type="APINotAvailable", error_message="Spotify API not available"
                )

            result = client.pause_playback()
            return PlaybackResult(
                success=True, action="pause", message="Paused playback",
                backend=self.backend_type
            )
        except Exception as e:
            logger.error(f"API pause failed: {e}")
            return PlaybackResult(
                success=False, action="pause", backend=self.backend_type,
                error_type="APIError", error_message=str(e)
            )

    def get_status(self) -> PlaybackResult:
        """Get playback status using API."""
        try:
            client = self._get_api_client()
            if not client:
                return PlaybackResult(
                    success=False, action="get_status", backend=self.backend_type,
                    error_type="APINotAvailable", error_message="Spotify API not available"
                )

            playback = client.get_current_playback()
            if playback:
                track = playback.get("item", {})
                track_name = track.get("name", "Unknown Track")
                artists = track.get("artists", [])
                artist_name = artists[0].get("name", "Unknown Artist") if artists else "Unknown Artist"

                is_playing = playback.get("is_playing", False)
                status = "playing" if is_playing else "paused"

                return PlaybackResult(
                    success=True, action="get_status",
                    message=f"Currently {status}: {track_name} by {artist_name}",
                    track=track_name, artist=artist_name, backend=self.backend_type
                )
            else:
                return PlaybackResult(
                    success=True, action="get_status",
                    message="No active playback", backend=self.backend_type
                )
        except Exception as e:
            logger.error(f"API get_status failed: {e}")
            return PlaybackResult(
                success=False, action="get_status", backend=self.backend_type,
                error_type="APIError", error_message=str(e)
            )

    def play_track(self, track_identifier: str, artist: Optional[str] = None) -> PlaybackResult:
        """Play a track by URI or search query using API."""
        try:
            client = self._get_api_client()
            if not client:
                return PlaybackResult(
                    success=False, action="play_track", backend=self.backend_type,
                    error_type="APINotAvailable", error_message="Spotify API not available"
                )

            # Check if it's already a URI
            if self._is_spotify_uri(track_identifier):
                track_uri = track_identifier
            else:
                # Resolve the query to a URI
                logger.info(f"[SPOTIFY API BACKEND] Resolving track query: '{track_identifier}'")
                track_uri = self._resolve_track_to_uri(track_identifier, artist)
                if not track_uri:
                    return PlaybackResult(
                        success=False, action="play_song", backend=self.backend_type,
                        error_type="SongNotFound",
                        error_message=f"Could not find track '{track_identifier}' on Spotify",
                        retry_possible=True
                    )

            result = client.play_track(track_uri, device_id=self._web_player_device_id)
            return PlaybackResult(
                success=True, action="play_song", message="Started track playback",
                backend=self.backend_type
            )
        except Exception as e:
            logger.error(f"API play_track failed: {e}")
            # Provide more specific error messages
            error_msg = str(e)
            if "not found" in error_msg.lower() or "no active device" in error_msg.lower():
                return PlaybackResult(
                    success=False, action="play_song", backend=self.backend_type,
                    error_type="SongNotFound",
                    error_message=f"Could not play track '{track_identifier}': {error_msg}",
                    retry_possible=True
                )
            else:
                return PlaybackResult(
                    success=False, action="play_song", backend=self.backend_type,
                    error_type="APIError", error_message=f"API playback failed: {error_msg}",
                    retry_possible=True
                )

    def play_album(self, album_identifier: str, artist: Optional[str] = None) -> PlaybackResult:
        """Play an album by URI or search query using API."""
        try:
            client = self._get_api_client()
            if not client:
                return PlaybackResult(
                    success=False, action="play_album", backend=self.backend_type,
                    error_type="APINotAvailable", error_message="Spotify API not available"
                )

            # Check if it's already a URI
            if self._is_spotify_uri(album_identifier):
                album_uri = album_identifier
            else:
                # Resolve the query to a URI
                logger.info(f"[SPOTIFY API BACKEND] Resolving album query: '{album_identifier}'")
                album_uri = self._resolve_album_to_uri(album_identifier, artist)
                if not album_uri:
                    return PlaybackResult(
                        success=False, action="play_album", backend=self.backend_type,
                        error_type="AlbumNotFound",
                        error_message=f"Could not find album '{album_identifier}' on Spotify",
                        retry_possible=True
                    )

            result = client.play_context(album_uri, device_id=self._web_player_device_id)
            return PlaybackResult(
                success=True, action="play_album", message="Started album playback",
                backend=self.backend_type
            )
        except Exception as e:
            logger.error(f"API play_album failed: {e}")
            # Provide more specific error messages
            error_msg = str(e)
            if "not found" in error_msg.lower() or "no active device" in error_msg.lower():
                return PlaybackResult(
                    success=False, action="play_album", backend=self.backend_type,
                    error_type="AlbumNotFound",
                    error_message=f"Could not play album '{album_identifier}': {error_msg}",
                    retry_possible=True
                )
            else:
                return PlaybackResult(
                    success=False, action="play_album", backend=self.backend_type,
                    error_type="APIError", error_message=f"API album playback failed: {error_msg}",
                    retry_possible=True
                )

    def play_artist(self, artist_identifier: str) -> PlaybackResult:
        """Play an artist by URI or search query using API."""
        try:
            client = self._get_api_client()
            if not client:
                return PlaybackResult(
                    success=False, action="play_artist", backend=self.backend_type,
                    error_type="APINotAvailable", error_message="Spotify API not available"
                )

            # Check if it's already a URI
            if self._is_spotify_uri(artist_identifier):
                artist_uri = artist_identifier
            else:
                # Resolve the query to a URI
                logger.info(f"[SPOTIFY API BACKEND] Resolving artist query: '{artist_identifier}'")
                artist_uri = self._resolve_artist_to_uri(artist_identifier)
                if not artist_uri:
                    return PlaybackResult(
                        success=False, action="play_artist", backend=self.backend_type,
                        error_type="ArtistNotFound",
                        error_message=f"Could not find artist '{artist_identifier}' on Spotify",
                        retry_possible=True
                    )

            result = client.play_context(artist_uri, device_id=self._web_player_device_id)
            return PlaybackResult(
                success=True, action="play_artist", message="Started artist playback",
                backend=self.backend_type
            )
        except Exception as e:
            logger.error(f"API play_artist failed: {e}")
            # Provide more specific error messages
            error_msg = str(e)
            if "not found" in error_msg.lower() or "no active device" in error_msg.lower():
                return PlaybackResult(
                    success=False, action="play_artist", backend=self.backend_type,
                    error_type="ArtistNotFound",
                    error_message=f"Could not play artist '{artist_identifier}': {error_msg}",
                    retry_possible=True
                )
            else:
                return PlaybackResult(
                    success=False, action="play_artist", backend=self.backend_type,
                    error_type="APIError", error_message=f"API artist playback failed: {error_msg}",
                    retry_possible=True
                )


class SpotifyAutomationBackend(SpotifyPlaybackBackend):
    """Legacy AppleScript automation backend."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._automation = None

    def _is_spotify_uri(self, uri_string: str) -> bool:
        """Check if a string is a valid Spotify URI."""
        return uri_string.startswith("spotify:") and any(
            uri_string.startswith(f"spotify:{entity}:")
            for entity in ["track", "album", "artist", "playlist"]
        )

    @property
    def backend_type(self) -> PlaybackBackend:
        return PlaybackBackend.AUTOMATION

    def _get_automation(self):
        """Get or create automation instance."""
        if self._automation is None:
            try:
                from ..automation import SpotifyAutomation
                self._automation = SpotifyAutomation(self.config)
            except Exception as e:
                logger.warning(f"Failed to initialize Spotify automation: {e}")
                self._automation = None

        return self._automation

    def is_available(self) -> bool:
        """Check if automation backend is available."""
        # Automation is always "available" but may fail at runtime
        return True

    def play(self) -> PlaybackResult:
        """Resume playback using automation."""
        try:
            automation = self._get_automation()
            if not automation:
                return PlaybackResult(
                    success=False, action="play", backend=self.backend_type,
                    error_type="AutomationNotAvailable", error_message="Spotify automation not available"
                )

            result = automation.play()
            return PlaybackResult(
                success=result.get("success", False),
                action="play",
                message=result.get("message", ""),
                backend=self.backend_type,
                error_type=result.get("error_type") if not result.get("success") else None,
                error_message=result.get("error_message") if not result.get("success") else None
            )
        except Exception as e:
            logger.error(f"Automation play failed: {e}")
            return PlaybackResult(
                success=False, action="play", backend=self.backend_type,
                error_type="AutomationError", error_message=str(e)
            )

    def pause(self) -> PlaybackResult:
        """Pause playback using automation."""
        try:
            automation = self._get_automation()
            if not automation:
                return PlaybackResult(
                    success=False, action="pause", backend=self.backend_type,
                    error_type="AutomationNotAvailable", error_message="Spotify automation not available"
                )

            result = automation.pause()
            return PlaybackResult(
                success=result.get("success", False),
                action="pause",
                message=result.get("message", ""),
                backend=self.backend_type,
                error_type=result.get("error_type") if not result.get("success") else None,
                error_message=result.get("error_message") if not result.get("success") else None
            )
        except Exception as e:
            logger.error(f"Automation pause failed: {e}")
            return PlaybackResult(
                success=False, action="pause", backend=self.backend_type,
                error_type="AutomationError", error_message=str(e)
            )

    def get_status(self) -> PlaybackResult:
        """Get playback status using automation."""
        try:
            automation = self._get_automation()
            if not automation:
                return PlaybackResult(
                    success=False, action="get_status", backend=self.backend_type,
                    error_type="AutomationNotAvailable", error_message="Spotify automation not available"
                )

            result = automation.get_status()
            return PlaybackResult(
                success=result.get("success", False),
                action="get_status",
                message=result.get("message", ""),
                track=result.get("track"),
                artist=result.get("artist"),
                backend=self.backend_type,
                error_type=result.get("error_type") if not result.get("success") else None,
                error_message=result.get("error_message") if not result.get("success") else None
            )
        except Exception as e:
            logger.error(f"Automation get_status failed: {e}")
            return PlaybackResult(
                success=False, action="get_status", backend=self.backend_type,
                error_type="AutomationError", error_message=str(e)
            )

    def play_track(self, track_identifier: str, artist: Optional[str] = None) -> PlaybackResult:
        """Play a track using automation (searches by name)."""
        try:
            automation = self._get_automation()
            if not automation:
                return PlaybackResult(
                    success=False, action="play_song", backend=self.backend_type,
                    error_type="AutomationNotAvailable", error_message="Spotify automation not available"
                )

            # Automation backend works with search queries, not URIs
            # If it's a URI, we can't handle it properly, so return an error
            if self._is_spotify_uri(track_identifier):
                return PlaybackResult(
                    success=False, action="play_song", backend=self.backend_type,
                    error_type="NotSupported",
                    error_message="URI playback not supported in automation backend",
                    retry_possible=False
                )

            # For search queries, use the automation search and play
            result = automation.search_and_play(track_identifier, artist)
            return PlaybackResult(
                success=result.get("success", False),
                action="play_song",
                message=result.get("message", ""),
                track=result.get("track"),
                artist=result.get("track_artist"),
                backend=self.backend_type,
                error_type=result.get("error_type") if not result.get("success") else None,
                error_message=result.get("error_message") if not result.get("success") else None
            )
        except Exception as e:
            logger.error(f"Automation play_track failed: {e}")
            return PlaybackResult(
                success=False, action="play_song", backend=self.backend_type,
                error_type="AutomationError", error_message=str(e)
            )

    def play_album(self, album_identifier: str, artist: Optional[str] = None) -> PlaybackResult:
        """Play an album using automation."""
        # Automation doesn't support album/artist URIs directly
        if self._is_spotify_uri(album_identifier):
            return PlaybackResult(
                success=False, action="play_album", backend=self.backend_type,
                error_type="NotSupported", error_message="URI album playback not supported in automation backend",
                retry_possible=False
            )
        else:
            return PlaybackResult(
                success=False, action="play_album", backend=self.backend_type,
                error_type="NotSupported", error_message="Album playback not supported in automation backend",
                retry_possible=False
            )

    def play_artist(self, artist_identifier: str) -> PlaybackResult:
        """Play an artist using automation."""
        # Automation doesn't support album/artist URIs directly
        if self._is_spotify_uri(artist_identifier):
            return PlaybackResult(
                success=False, action="play_artist", backend=self.backend_type,
                error_type="NotSupported", error_message="URI artist playback not supported in automation backend",
                retry_possible=False
            )
        else:
            return PlaybackResult(
                success=False, action="play_artist", backend=self.backend_type,
                error_type="NotSupported", error_message="Artist playback not supported in automation backend",
                retry_possible=False
            )


class SpotifyPlaybackService:
    """
    Unified Spotify playback service with automatic backend selection.

    Provides a single interface for all Spotify playback operations, automatically
    choosing between API and automation backends based on availability and configuration.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize playback service.

        Args:
            config: Configuration dictionary
        """
        self.config = config

        # Initialize backends
        self.api_backend = SpotifyAPIBackend(config)
        self.automation_backend = SpotifyAutomationBackend(config)

        # Backend preference from config (default to API)
        playback_config = config.get("playback", {})
        self.prefer_api = playback_config.get("use_api", True)
        self.disable_automation_fallback = playback_config.get("disable_automation_fallback", False)

        logger.info(f"Initialized SpotifyPlaybackService (prefer_api={self.prefer_api}, disable_automation_fallback={self.disable_automation_fallback})")

        # Try to get web player device ID from API server
        self._sync_web_player_device_id()

    def _sync_web_player_device_id(self):
        """Sync web player device ID from API server."""
        try:
            import requests
            response = requests.get("http://localhost:8000/api/spotify/device-id", timeout=2)
            if response.status_code == 200:
                data = response.json()
                device_id = data.get("device_id")
                if device_id:
                    self.api_backend.set_web_player_device_id(device_id)
                    logger.info(f"[PLAYBACK SERVICE] Synced web player device ID: {device_id}")
        except Exception as e:
            logger.debug(f"Could not sync web player device ID: {e}")

    def _select_backend(self, operation: str) -> SpotifyPlaybackBackend:
        """
        Select the best available backend for an operation.

        Priority:
        1. API backend if preferred and available
        2. Automation backend as fallback (if not disabled)
        3. Error if no backend available and automation fallback disabled
        """
        if self.prefer_api and self.api_backend.is_available():
            logger.debug(f"Selected API backend for {operation}")
            return self.api_backend
        elif not self.disable_automation_fallback:
            logger.debug(f"Selected automation backend for {operation}")
            return self.automation_backend
        else:
            # No backend available and automation fallback disabled
            raise ValueError(f"No playback backend available for {operation}. Web API requires authentication. Please connect Spotify first.")

    def play(self) -> PlaybackResult:
        """Start or resume playback."""
        try:
            backend = self._select_backend("play")
            result = backend.play()
            logger.info(f"Play result: {result.success} (backend: {result.backend.value})")
            return result
        except ValueError as e:
            logger.warning(f"No backend available for play: {e}")
            return PlaybackResult(
                success=False, action="play", backend=None,
                error_type="NoBackendAvailable", error_message=str(e)
            )

    def pause(self) -> PlaybackResult:
        """Pause current playback."""
        try:
            backend = self._select_backend("pause")
            result = backend.pause()
            logger.info(f"Pause result: {result.success} (backend: {result.backend.value})")
            return result
        except ValueError as e:
            logger.warning(f"No backend available for pause: {e}")
            return PlaybackResult(
                success=False, action="pause", backend=None,
                error_type="NoBackendAvailable", error_message=str(e)
            )

    def get_status(self) -> PlaybackResult:
        """Get current playback status."""
        try:
            backend = self._select_backend("get_status")
            result = backend.get_status()
            logger.debug(f"Status result: {result.success} (backend: {result.backend.value})")
            return result
        except ValueError as e:
            logger.warning(f"No backend available for status: {e}")
            return PlaybackResult(
                success=False, action="get_status", backend=None,
                error_type="NoBackendAvailable", error_message=str(e)
            )

    def play_track(self, track_identifier: str, artist: Optional[str] = None) -> PlaybackResult:
        """
        Play a specific track by URI or search query.

        Args:
            track_identifier: Either a Spotify URI (spotify:track:xxx) or a search query
            artist: Optional artist name (only used for search queries)
        """
        # Sync web player device ID before playing
        self._sync_web_player_device_id()

        # Check if it's a Spotify URI
        if track_identifier.startswith("spotify:track:") or track_identifier.startswith("spotify:album:") or track_identifier.startswith("spotify:artist:"):
            # Use API backend for URIs if available
            if self.api_backend.is_available():
                backend = self.api_backend
                logger.debug("Using API backend for URI playback")
            else:
                backend = self.automation_backend
                logger.debug("Using automation backend for URI playback (API not available)")
        else:
            # For search queries, use normal backend selection
            try:
                backend = self._select_backend("play_track")
            except ValueError as e:
                logger.warning(f"No backend available for play_track: {e}")
                return PlaybackResult(
                    success=False, action="play_track", backend=None,
                    error_type="NoBackendAvailable", error_message=str(e)
                )

        try:
            if track_identifier.startswith("spotify:track:"):
                result = backend.play_track(track_identifier, artist)
            elif track_identifier.startswith("spotify:album:"):
                result = backend.play_album(track_identifier, artist)
            elif track_identifier.startswith("spotify:artist:"):
                result = backend.play_artist(track_identifier)
            else:
                # Not a URI, treat as search query
                result = backend.play_track(track_identifier, artist)

            logger.info(f"Play track result: {result.success} (backend: {result.backend.value})")
            return result
        except Exception as e:
            logger.error(f"Error playing track {track_identifier}: {e}")
            return PlaybackResult(
                success=False, action="play_track", backend=backend.backend_type if hasattr(backend, 'backend_type') else None,
                error_type="PlaybackError", error_message=str(e)
            )

    def play_album(self, album_uri: str, artist: Optional[str] = None) -> PlaybackResult:
        """Play a specific album."""
        try:
            backend = self._select_backend("play_album")
            result = backend.play_album(album_uri, artist)
            logger.info(f"Play album result: {result.success} (backend: {result.backend.value})")
            return result
        except ValueError as e:
            logger.warning(f"No backend available for play_album: {e}")
            return PlaybackResult(
                success=False, action="play_album", backend=None,
                error_type="NoBackendAvailable", error_message=str(e)
            )

    def play_artist(self, artist_uri: str) -> PlaybackResult:
        """Play an artist's top tracks."""
        try:
            backend = self._select_backend("play_artist")
            result = backend.play_artist(artist_uri)
            logger.info(f"Play artist result: {result.success} (backend: {result.backend.value})")
            return result
        except ValueError as e:
            logger.warning(f"No backend available for play_artist: {e}")
            return PlaybackResult(
                success=False, action="play_artist", backend=None,
                error_type="NoBackendAvailable", error_message=str(e)
            )

    def get_available_backends(self) -> List[PlaybackBackend]:
        """Get list of currently available backends."""
        available = []
        if self.api_backend.is_available():
            available.append(PlaybackBackend.API)
        if self.automation_backend.is_available():
            available.append(PlaybackBackend.AUTOMATION)
        return available

    def force_backend(self, backend: PlaybackBackend) -> None:
        """
        Force the use of a specific backend for all operations.

        Args:
            backend: Backend to force
        """
        if backend == PlaybackBackend.API:
            self.prefer_api = True
        elif backend == PlaybackBackend.AUTOMATION:
            self.prefer_api = False

        logger.info(f"Forced backend selection: {backend.value}")
