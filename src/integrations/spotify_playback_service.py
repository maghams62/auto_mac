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
    def next_track(self) -> PlaybackResult:
        """Skip to the next track in the current queue."""
        pass

    @abstractmethod
    def previous_track(self) -> PlaybackResult:
        """Return to the previous track in the current queue."""
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
        track_info = self._resolve_track_with_info(track_query, artist_hint)
        return track_info["uri"] if track_info else None

    def _resolve_track_with_info(self, track_query: str, artist_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Search for a track and return its URI along with track info (name, artist)."""
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
                track = tracks[0]
                artists = track.get("artists", [])
                artist_name = artists[0].get("name", "Unknown Artist") if artists else "Unknown Artist"
                return {
                    "uri": track["uri"],
                    "name": track.get("name", track_query),
                    "artist": artist_name
                }
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

    def has_available_devices(self) -> bool:
        """Check if there are available devices for playback."""
        client = self._get_api_client()
        return client is not None and client.is_authenticated() and client.has_available_devices()

    def play(self) -> PlaybackResult:
        """Resume playback using API."""
        try:
            client = self._get_api_client()
            if not client:
                return PlaybackResult(
                    success=False, action="play", backend=self.backend_type,
                    error_type="APINotAvailable", error_message="Spotify API not available"
                )

            # Check for available devices
            if not client.has_available_devices():
                return PlaybackResult(
                    success=False, action="play", backend=self.backend_type,
                    error_type="NoDevicesAvailable",
                    error_message="No Spotify devices available for playback control.",
                    retry_possible=True
                )

            # Try to resume on the web player device first, fallback to any available device
            device_id = self._web_player_device_id
            if device_id:
                logger.info(f"[SPOTIFY API BACKEND] Attempting resume with device ID: {device_id}")
                try:
                    result = client.resume_playback(device_id=device_id)
                    return PlaybackResult(
                        success=True, action="play", message="Resumed playback",
                        backend=self.backend_type
                    )
                except Exception as device_e:
                    logger.warning(f"[SPOTIFY API BACKEND] Failed to resume on web player device: {device_e}")

            # Fallback: try to resume without specifying device (uses active device)
            result = client.resume_playback()
            return PlaybackResult(
                success=True, action="play", message="Resumed playback",
                backend=self.backend_type
            )
        except Exception as e:
            logger.error(f"API play failed: {e}")
            # Provide more specific error messages
            error_msg = str(e)
            if "restriction violated" in error_msg.lower():
                return PlaybackResult(
                    success=False, action="play", backend=self.backend_type,
                    error_type="DeviceRestriction",
                    error_message="Cannot control this Spotify device due to restrictions. Try playing music on a different device first.",
                    retry_possible=True
                )
            else:
                return PlaybackResult(
                    success=False, action="play", backend=self.backend_type,
                    error_type="APIError", error_message=f"API resume failed: {error_msg}",
                    retry_possible=True
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

            # Check for available devices
            if not client.has_available_devices():
                return PlaybackResult(
                    success=False, action="pause", backend=self.backend_type,
                    error_type="NoDevicesAvailable",
                    error_message="No Spotify devices available for playback control.",
                    retry_possible=True
                )

            # Try to pause on the web player device first, fallback to any available device
            device_id = self._web_player_device_id
            if device_id:
                logger.info(f"[SPOTIFY API BACKEND] Attempting pause with device ID: {device_id}")
                try:
                    result = client.pause_playback(device_id=device_id)
                    return PlaybackResult(
                        success=True, action="pause", message="Paused playback",
                        backend=self.backend_type
                    )
                except Exception as device_e:
                    logger.warning(f"[SPOTIFY API BACKEND] Failed to pause on web player device: {device_e}")

            # Fallback: try to pause without specifying device (uses active device)
            result = client.pause_playback()
            return PlaybackResult(
                success=True, action="pause", message="Paused playback",
                backend=self.backend_type
            )
        except Exception as e:
            logger.error(f"API pause failed: {e}")
            # Provide more specific error messages
            error_msg = str(e)
            if "restriction violated" in error_msg.lower():
                return PlaybackResult(
                    success=False, action="pause", backend=self.backend_type,
                    error_type="DeviceRestriction",
                    error_message="Cannot control this Spotify device due to restrictions. Try playing music on a different device first.",
                    retry_possible=True
                )
            else:
                return PlaybackResult(
                    success=False, action="pause", backend=self.backend_type,
                    error_type="APIError", error_message=f"API pause failed: {error_msg}",
                    retry_possible=True
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

    def _activate_device(self, client, preferred_device_id: Optional[str] = None) -> Optional[str]:
        """Activate a Spotify device for playback.

        Returns the device ID that was activated, or None if activation failed.
        """
        try:
            devices = client.get_devices()
            if not devices:
                logger.warning("[SPOTIFY API BACKEND] No devices available for activation")
                return None

            # Priority order: preferred device, then Cerebro Web Player, then MacBook Air, then any device
            device_priority = []

            # Add preferred device first if specified
            if preferred_device_id:
                device_priority.append(preferred_device_id)

            # Add Cerebro Web Player
            cerebro_devices = [d for d in devices if 'Cerebro' in d.get('name', '')]
            if cerebro_devices:
                device_priority.append(cerebro_devices[0]['id'])

            # Add MacBook Air
            mac_devices = [d for d in devices if 'MacBook Air' in d.get('name', '')]
            if mac_devices:
                device_priority.append(mac_devices[0]['id'])

            # Add any remaining devices
            for device in devices:
                device_id = device['id']
                if device_id not in device_priority:
                    device_priority.append(device_id)

            # Try to activate devices in priority order
            for device_id in device_priority:
                try:
                    logger.info(f"[SPOTIFY API BACKEND] Attempting to activate device: {device_id}")
                    # Transfer playback to the device and start playing (play=True)
                    client.transfer_playback(device_id, play=True)

                    # Wait a moment for activation to take effect
                    import time
                    time.sleep(1)

                    # Verify the device is now active
                    updated_devices = client.get_devices()
                    activated_device = next((d for d in updated_devices if d['id'] == device_id), None)
                    if activated_device and activated_device.get('is_active', False):
                        logger.info(f"[SPOTIFY API BACKEND] Successfully activated device: {device_id}")
                        return device_id
                    else:
                        logger.warning(f"[SPOTIFY API BACKEND] Device {device_id} not active after transfer")

                except Exception as e:
                    logger.warning(f"[SPOTIFY API BACKEND] Failed to activate device {device_id}: {e}")
                    continue

            logger.error("[SPOTIFY API BACKEND] Failed to activate any device")
            return None

        except Exception as e:
            logger.error(f"[SPOTIFY API BACKEND] Error during device activation: {e}")
            return None

    def play_track(self, track_identifier: str, artist: Optional[str] = None) -> PlaybackResult:
        """Play a track by URI or search query using API."""
        try:
            client = self._get_api_client()
            if not client:
                return PlaybackResult(
                    success=False, action="play_track", backend=self.backend_type,
                    error_type="APINotAvailable", error_message="Spotify API not available"
                )

            # Check for available devices first
            if not client.has_available_devices():
                return PlaybackResult(
                    success=False, action="play_track", backend=self.backend_type,
                    error_type="NoDevicesAvailable",
                    error_message="No Spotify devices available for playback. Please make sure Spotify is running on at least one device.",
                    retry_possible=True
                )

            # Resolve track info (URI, name, artist)
            track_info = None
            if self._is_spotify_uri(track_identifier):
                track_uri = track_identifier
                # For URIs, we don't have track info yet - will try to get it after playback
            else:
                # Resolve the query to get URI and track info
                logger.info(f"[SPOTIFY API BACKEND] Resolving track query: '{track_identifier}'")
                track_info = self._resolve_track_with_info(track_identifier, artist)
                if not track_info:
                    return PlaybackResult(
                        success=False, action="play_song", backend=self.backend_type,
                        error_type="SongNotFound",
                        error_message=f"Could not find track '{track_identifier}' on Spotify",
                        retry_possible=True
                    )
                track_uri = track_info["uri"]

            # Try to play with device activation logic
            device_id_to_use = self._web_player_device_id

            # First attempt: try to play directly (Spotify will use active device if available)
            try:
                logger.info(f"[SPOTIFY API BACKEND] Attempting direct playback")
                result = client.play_track(track_uri, device_id=device_id_to_use)
                # Build message with track info if available
                if track_info:
                    message = f"Now playing: {track_info['name']} by {track_info['artist']}"
                else:
                    message = "Started track playback"
                return PlaybackResult(
                    success=True, action="play_song", message=message,
                    track=track_info["name"] if track_info else None,
                    artist=track_info["artist"] if track_info else None,
                    backend=self.backend_type
                )
            except Exception as e:
                error_msg = str(e).lower()
                if "no active device" not in error_msg:
                    # Re-raise if it's not a "no active device" error
                    raise e

                # No active device - try to activate one
                logger.info("[SPOTIFY API BACKEND] No active device found, attempting device activation")
                activated_device_id = self._activate_device(client, device_id_to_use)

                if activated_device_id:
                    # Try to play again with the activated device
                    try:
                        logger.info(f"[SPOTIFY API BACKEND] Retrying playback with activated device: {activated_device_id}")
                        result = client.play_track(track_uri, device_id=activated_device_id)
                        # Build message with track info if available
                        if track_info:
                            message = f"Now playing: {track_info['name']} by {track_info['artist']}"
                        else:
                            message = "Started track playback"
                        return PlaybackResult(
                            success=True, action="play_song", message=message,
                            track=track_info["name"] if track_info else None,
                            artist=track_info["artist"] if track_info else None,
                            backend=self.backend_type
                        )
                    except Exception as retry_error:
                        logger.error(f"[SPOTIFY API BACKEND] Playback failed even after device activation: {retry_error}")
                        raise retry_error
                else:
                    # Could not activate any device
                    return PlaybackResult(
                        success=False, action="play_song", backend=self.backend_type,
                        error_type="DeviceActivationFailed",
                        error_message="Could not activate any Spotify device for playback. Please ensure Spotify is running and accessible.",
                        retry_possible=True
                    )

        except Exception as e:
            logger.error(f"API play_track failed: {e}")
            # Provide more specific error messages
            error_msg = str(e)
            if "not found" in error_msg.lower():
                return PlaybackResult(
                    success=False, action="play_song", backend=self.backend_type,
                    error_type="SongNotFound",
                    error_message=f"Could not find track '{track_identifier}' on Spotify",
                    retry_possible=True
                )
            elif "no active device" in error_msg.lower():
                return PlaybackResult(
                    success=False, action="play_song", backend=self.backend_type,
                    error_type="NoActiveDevice",
                    error_message="No active Spotify device found. Please start Spotify on a device and try again.",
                    retry_possible=True
                )
            elif "device not found" in error_msg.lower():
                return PlaybackResult(
                    success=False, action="play_song", backend=self.backend_type,
                    error_type="DeviceNotFound",
                    error_message="The specified Spotify device is not available. Please check your device connections.",
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

            # Check for available devices first
            if not client.has_available_devices():
                return PlaybackResult(
                    success=False, action="play_album", backend=self.backend_type,
                    error_type="NoDevicesAvailable",
                    error_message="No Spotify devices available for playback. Please make sure Spotify is running on at least one device.",
                    retry_possible=True
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

            # Try to play with device activation logic
            device_id_to_use = self._web_player_device_id

            # First attempt: try to play directly
            try:
                logger.info(f"[SPOTIFY API BACKEND] Attempting direct album playback")
                result = client.play_context(album_uri, device_id=device_id_to_use)
                return PlaybackResult(
                    success=True, action="play_album", message="Started album playback",
                    backend=self.backend_type
                )
            except Exception as e:
                error_msg = str(e).lower()
                if "no active device" not in error_msg:
                    raise e

                # No active device - try to activate one
                logger.info("[SPOTIFY API BACKEND] No active device found for album playback, attempting device activation")
                activated_device_id = self._activate_device(client, device_id_to_use)

                if activated_device_id:
                    # Try to play again with the activated device
                    try:
                        logger.info(f"[SPOTIFY API BACKEND] Retrying album playback with activated device: {activated_device_id}")
                        result = client.play_context(album_uri, device_id=activated_device_id)
                        return PlaybackResult(
                            success=True, action="play_album", message="Started album playback",
                            backend=self.backend_type
                        )
                    except Exception as retry_error:
                        logger.error(f"[SPOTIFY API BACKEND] Album playback failed even after device activation: {retry_error}")
                        raise retry_error
                else:
                    # Could not activate any device
                    return PlaybackResult(
                        success=False, action="play_album", backend=self.backend_type,
                        error_type="DeviceActivationFailed",
                        error_message="Could not activate any Spotify device for playback. Please ensure Spotify is running and accessible.",
                        retry_possible=True
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

            # Check for available devices first
            if not client.has_available_devices():
                return PlaybackResult(
                    success=False, action="play_artist", backend=self.backend_type,
                    error_type="NoDevicesAvailable",
                    error_message="No Spotify devices available for playback. Please make sure Spotify is running on at least one device.",
                    retry_possible=True
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

            # Try to play with device activation logic
            device_id_to_use = self._web_player_device_id

            # First attempt: try to play directly
            try:
                logger.info(f"[SPOTIFY API BACKEND] Attempting direct artist playback")
                result = client.play_context(artist_uri, device_id=device_id_to_use)
                return PlaybackResult(
                    success=True, action="play_artist", message="Started artist playback",
                    backend=self.backend_type
                )
            except Exception as e:
                error_msg = str(e).lower()
                if "no active device" not in error_msg:
                    raise e

                # No active device - try to activate one
                logger.info("[SPOTIFY API BACKEND] No active device found for artist playback, attempting device activation")
                activated_device_id = self._activate_device(client, device_id_to_use)

                if activated_device_id:
                    # Try to play again with the activated device
                    try:
                        logger.info(f"[SPOTIFY API BACKEND] Retrying artist playback with activated device: {activated_device_id}")
                        result = client.play_context(artist_uri, device_id=activated_device_id)
                        return PlaybackResult(
                            success=True, action="play_artist", message="Started artist playback",
                            backend=self.backend_type
                        )
                    except Exception as retry_error:
                        logger.error(f"[SPOTIFY API BACKEND] Artist playback failed even after device activation: {retry_error}")
                        raise retry_error
                else:
                    # Could not activate any device
                    return PlaybackResult(
                        success=False, action="play_artist", backend=self.backend_type,
                        error_type="DeviceActivationFailed",
                        error_message="Could not activate any Spotify device for playback. Please ensure Spotify is running and accessible.",
                        retry_possible=True
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

    def next_track(self) -> PlaybackResult:
        """Skip to the next track in the queue using the API backend."""
        try:
            client = self._get_api_client()
            if not client:
                return PlaybackResult(
                    success=False, action="next_track", backend=self.backend_type,
                    error_type="APINotAvailable", error_message="Spotify API not available"
                )

            if not client.has_available_devices():
                return PlaybackResult(
                    success=False, action="next_track", backend=self.backend_type,
                    error_type="NoDevicesAvailable",
                    error_message="No Spotify devices available for playback control.",
                    retry_possible=True
                )

            device_id = self._web_player_device_id
            if device_id:
                try:
                    client.skip_to_next(device_id=device_id)
                except Exception as device_error:
                    logger.warning(f"[SPOTIFY API BACKEND] Failed to skip to next track on device {device_id}: {device_error}. Retrying without device.")
                    client.skip_to_next()
            else:
                client.skip_to_next()

            return PlaybackResult(
                success=True, action="next_track", message="Skipped to the next track",
                backend=self.backend_type
            )
        except Exception as e:
            logger.error(f"[SPOTIFY API BACKEND] Error skipping to next track: {e}")
            return PlaybackResult(
                success=False, action="next_track", backend=self.backend_type,
                error_type="APIError", error_message=str(e),
                retry_possible=True
            )

    def previous_track(self) -> PlaybackResult:
        """Skip to the previous track in the queue using the API backend."""
        try:
            client = self._get_api_client()
            if not client:
                return PlaybackResult(
                    success=False, action="previous_track", backend=self.backend_type,
                    error_type="APINotAvailable", error_message="Spotify API not available"
                )

            if not client.has_available_devices():
                return PlaybackResult(
                    success=False, action="previous_track", backend=self.backend_type,
                    error_type="NoDevicesAvailable",
                    error_message="No Spotify devices available for playback control.",
                    retry_possible=True
                )

            device_id = self._web_player_device_id
            if device_id:
                try:
                    client.skip_to_previous(device_id=device_id)
                except Exception as device_error:
                    logger.warning(f"[SPOTIFY API BACKEND] Failed to skip to previous track on device {device_id}: {device_error}. Retrying without device.")
                    client.skip_to_previous()
            else:
                client.skip_to_previous()

            return PlaybackResult(
                success=True, action="previous_track", message="Returned to the previous track",
                backend=self.backend_type
            )
        except Exception as e:
            logger.error(f"[SPOTIFY API BACKEND] Error skipping to previous track: {e}")
            return PlaybackResult(
                success=False, action="previous_track", backend=self.backend_type,
                error_type="APIError", error_message=str(e),
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

    def next_track(self) -> PlaybackResult:
        """Skip to the next track using automation."""
        try:
            automation = self._get_automation()
            if not automation:
                return PlaybackResult(
                    success=False, action="next_track", backend=self.backend_type,
                    error_type="AutomationNotAvailable", error_message="Spotify automation not available"
                )

            result = automation.next_track()
            return PlaybackResult(
                success=result.get("success", False),
                action="next_track",
                message=result.get("message", ""),
                backend=self.backend_type,
                error_type=result.get("error_type") if not result.get("success") else None,
                error_message=result.get("error_message") if not result.get("success") else None
            )
        except Exception as e:
            logger.error(f"Automation next_track failed: {e}")
            return PlaybackResult(
                success=False, action="next_track", backend=self.backend_type,
                error_type="AutomationError", error_message=str(e)
            )

    def previous_track(self) -> PlaybackResult:
        """Return to the previous track using automation."""
        try:
            automation = self._get_automation()
            if not automation:
                return PlaybackResult(
                    success=False, action="previous_track", backend=self.backend_type,
                    error_type="AutomationNotAvailable", error_message="Spotify automation not available"
                )

            result = automation.previous_track()
            return PlaybackResult(
                success=result.get("success", False),
                action="previous_track",
                message=result.get("message", ""),
                backend=self.backend_type,
                error_type=result.get("error_type") if not result.get("success") else None,
                error_message=result.get("error_message") if not result.get("success") else None
            )
        except Exception as e:
            logger.error(f"Automation previous_track failed: {e}")
            return PlaybackResult(
                success=False, action="previous_track", backend=self.backend_type,
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
                    return device_id
                else:
                    logger.warning("[PLAYBACK SERVICE] Device ID endpoint returned empty device_id")
            else:
                logger.warning(f"[PLAYBACK SERVICE] Device ID endpoint returned status {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"[PLAYBACK SERVICE] Could not connect to API server for device ID: {e}")
        except Exception as e:
            logger.error(f"[PLAYBACK SERVICE] Error syncing web player device ID: {e}")
        return None

    def _transfer_playback_to_available_device(self, track_identifier: str, artist: Optional[str] = None) -> PlaybackResult:
        """
        Transfer playback to an available device and play the track.

        Args:
            track_identifier: Track URI or search query
            artist: Optional artist name

        Returns:
            PlaybackResult indicating success or failure
        """
        try:
            client = self.api_backend._get_api_client()
            if not client:
                return PlaybackResult(
                    success=False, action="transfer_playback",
                    error_type="APINotAvailable", error_message="Spotify API not available"
                )

            # Get available devices
            devices = client.get_devices()
            if not devices:
                return PlaybackResult(
                    success=False, action="transfer_playback",
                    error_type="NoDevices", error_message="No Spotify devices found"
                )

            # Find the first active device (preferably not restricted)
            target_device = None
            for device in devices:
                if device.get("is_active", False):
                    target_device = device
                    break
                elif not device.get("is_restricted", True):
                    target_device = device
                    break

            if not target_device:
                # If no active device, use the first available device
                target_device = devices[0]

            device_id = target_device["id"]
            device_name = target_device.get("name", "Unknown Device")
            logger.info(f"[PLAYBACK SERVICE] Transferring playback to device: {device_name} ({device_id})")

            # First, try to transfer playback to the target device
            try:
                transfer_result = client.transfer_playback(device_id, play=False)
                logger.info(f"[PLAYBACK SERVICE] Playback transferred to {device_name}")
            except Exception as transfer_e:
                logger.warning(f"[PLAYBACK SERVICE] Could not transfer playback to {device_name}: {transfer_e}")
                # Continue anyway - we might still be able to play directly on the device

            # Check if it's already a URI
            if self.api_backend._is_spotify_uri(track_identifier):
                track_uri = track_identifier
            else:
                # Resolve the query to a URI
                track_uri = self.api_backend._resolve_track_to_uri(track_identifier, artist)
                if not track_uri:
                    return PlaybackResult(
                        success=False, action="transfer_playback",
                        error_type="SongNotFound", error_message=f"Could not find track '{track_identifier}'"
                    )

            # Play the track on the target device
            result = client.play_track(track_uri, device_id=device_id)

            return PlaybackResult(
                success=True, action="transfer_playback",
                message=f"Transferred playback to {device_name} and started track",
                backend=self.api_backend.backend_type
            )

        except Exception as e:
            logger.error(f"[PLAYBACK SERVICE] Failed to transfer playback: {e}")
            return PlaybackResult(
                success=False, action="transfer_playback",
                error_type="TransferFailed", error_message=f"Could not transfer playback: {str(e)}"
            )

    def _select_backend(self, operation: str) -> SpotifyPlaybackBackend:
        """
        Select the best available backend for an operation.

        Priority:
        1. API backend if preferred and available
        2. Automation backend as fallback (if not disabled)
        3. Error if no backend available and automation fallback disabled
        """
        if self.prefer_api and self.api_backend.is_available():
            logger.info(f"[BACKEND SELECTION] Selected API backend for {operation} (prefer_api={self.prefer_api}, api_available={self.api_backend.is_available()})")
            return self.api_backend
        elif not self.disable_automation_fallback:
            logger.warning(f"[BACKEND SELECTION] Selected automation backend for {operation} (automation fallback enabled)")
            return self.automation_backend
        else:
            # No backend available and automation fallback disabled
            logger.error(f"[BACKEND SELECTION] No backend available for {operation}: prefer_api={self.prefer_api}, api_available={self.api_backend.is_available()}, disable_automation_fallback={self.disable_automation_fallback}")
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

    def next_track(self) -> PlaybackResult:
        """Skip to the next track."""
        try:
            backend = self._select_backend("next_track")
            result = backend.next_track()
            logger.info(f"Next track result: {result.success} (backend: {result.backend.value if result.backend else 'unknown'})")
            return result
        except ValueError as e:
            logger.warning(f"No backend available for next_track: {e}")
            return PlaybackResult(
                success=False, action="next_track", backend=None,
                error_type="NoBackendAvailable", error_message=str(e)
            )

    def previous_track(self) -> PlaybackResult:
        """Return to the previous track."""
        try:
            backend = self._select_backend("previous_track")
            result = backend.previous_track()
            logger.info(f"Previous track result: {result.success} (backend: {result.backend.value if result.backend else 'unknown'})")
            return result
        except ValueError as e:
            logger.warning(f"No backend available for previous_track: {e}")
            return PlaybackResult(
                success=False, action="previous_track", backend=None,
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
        device_id = self._sync_web_player_device_id()
        logger.info(f"[PLAYBACK SERVICE] Attempting to play track with device_id: {device_id}")

        # Always use backend selection logic - this respects disable_automation_fallback setting
        # URIs and search queries both should use the same backend selection
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

            # If we get a "no active device" error and we have API backend available,
            # try to transfer playback to an available device
            if "no active device" in str(e).lower() and self.api_backend.is_available():
                logger.info("[PLAYBACK SERVICE] No active device found, attempting to transfer playback")
                try:
                    transfer_result = self._transfer_playback_to_available_device(track_identifier, artist)
                    if transfer_result.success:
                        logger.info("[PLAYBACK SERVICE] Successfully transferred playback to available device")
                        return transfer_result
                except Exception as transfer_e:
                    logger.error(f"[PLAYBACK SERVICE] Failed to transfer playback: {transfer_e}")

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
