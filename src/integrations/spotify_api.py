"""
Spotify API Client - OAuth2 authentication and API endpoints for Spotify Web API.

This module provides a complete Spotify Web API client with:
- OAuth2 authorization flow
- Automatic token refresh
- Core playback endpoints (play, pause, resume, status)
- Search functionality (tracks, albums, artists)
- Error handling and retry logic

Based on Spotify Web API documentation: https://developer.spotify.com/documentation/web-api/
"""

import base64
import json
import logging
import time
import urllib.parse
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class SpotifyToken:
    """Spotify OAuth token data."""
    access_token: str
    token_type: str
    scope: str
    expires_in: int
    refresh_token: Optional[str] = None
    expires_at: Optional[float] = None

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """Check if token is expired (with buffer)."""
        if not self.expires_at:
            return True
        return time.time() >= (self.expires_at - buffer_seconds)

    def get_authorization_header(self) -> str:
        """Get Authorization header value."""
        return f"{self.token_type} {self.access_token}"


@dataclass
class SpotifyTrack:
    """Spotify track data."""
    id: str
    name: str
    uri: str
    artists: List[Dict[str, Any]]
    album: Dict[str, Any]
    duration_ms: int
    popularity: int

    @property
    def primary_artist(self) -> str:
        """Get primary artist name."""
        return self.artists[0]["name"] if self.artists else "Unknown Artist"


@dataclass
class SpotifyAlbum:
    """Spotify album data."""
    id: str
    name: str
    uri: str
    artists: List[Dict[str, Any]]
    tracks: List[SpotifyTrack]
    total_tracks: int

    @property
    def primary_artist(self) -> str:
        """Get primary artist name."""
        return self.artists[0]["name"] if self.artists else "Unknown Artist"


@dataclass
class SpotifyArtist:
    """Spotify artist data."""
    id: str
    name: str
    uri: str
    genres: List[str]
    popularity: int
    followers: int


class SpotifyAPIError(Exception):
    """Spotify API error."""
    def __init__(self, message: str, status_code: Optional[int] = None, error_code: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class SpotifyAPIAuthError(SpotifyAPIError):
    """Spotify authentication error."""
    pass


class SpotifyAPIClient:
    """
    Spotify Web API client with OAuth2 authentication.

    Handles:
    - OAuth2 authorization code flow
    - Token refresh
    - API requests with retry logic
    - Core playback operations
    - Search functionality
    """

    BASE_URL = "https://api.spotify.com/v1"
    AUTH_URL = "https://accounts.spotify.com"
    TOKEN_URL = f"{AUTH_URL}/api/token"
    AUTHORIZE_URL = f"{AUTH_URL}/authorize"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str,
                 token_storage_path: Optional[str] = None):
        """
        Initialize Spotify API client.

        Args:
            client_id: Spotify application client ID
            client_secret: Spotify application client secret
            redirect_uri: OAuth redirect URI
            token_storage_path: Path to store/restore tokens (optional)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token_storage_path = Path(token_storage_path) if token_storage_path else None

        # Current token
        self.token: Optional[SpotifyToken] = None

        # HTTP session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Load existing token if available
        self._load_token()

    def _get_basic_auth_header(self) -> str:
        """Get basic auth header for client credentials."""
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """
        Make authenticated request to Spotify API.

        Args:
            method: HTTP method
            url: API endpoint URL
            **kwargs: Additional request parameters

        Returns:
            JSON response data

        Raises:
            SpotifyAPIError: On API errors
            SpotifyAPIAuthError: On authentication errors
        """
        if not self.token or self.token.is_expired():
            self._refresh_token()

        if not self.token:
            raise SpotifyAPIAuthError("No valid token available. Please authenticate first.")

        headers = kwargs.get('headers', {})
        headers['Authorization'] = self.token.get_authorization_header()
        kwargs['headers'] = headers

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()

            # Handle empty responses (204 No Content) from Spotify API
            # Play/pause/skip endpoints return 204 with no body
            if response.status_code == 204:
                return {"success": True, "status_code": response.status_code}

            # Handle responses with no content
            if not response.content:
                return {"success": True, "status_code": response.status_code}

            # Try to parse as JSON, but handle cases where Spotify returns non-JSON content
            try:
                return response.json()
            except ValueError:
                # If it's not valid JSON, return success with the raw content
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "content": response.content.decode('utf-8', errors='ignore')
                }
        except requests.HTTPError as e:
            error_data = response.json() if response.content else {}
            error_msg = error_data.get('error', {}).get('message', str(e))

            if response.status_code == 401:
                # Token expired, try refresh once
                if self.token and self.token.refresh_token:
                    logger.info("Token expired, attempting refresh")
                    self._refresh_token()
                    # Retry the request
                    headers['Authorization'] = self.token.get_authorization_header()
                    response = self.session.request(method, url, **kwargs)
                    response.raise_for_status()

                    # Handle empty responses on retry too
                    if response.status_code == 204:
                        return {"success": True, "status_code": response.status_code}

                    # Handle responses with no content
                    if not response.content:
                        return {"success": True, "status_code": response.status_code}

                    # Try to parse as JSON, but handle cases where Spotify returns non-JSON content
                    try:
                        return response.json()
                    except ValueError:
                        # If it's not valid JSON, return success with the raw content
                        return {
                            "success": True,
                            "status_code": response.status_code,
                            "content": response.content.decode('utf-8', errors='ignore')
                        }
                else:
                    raise SpotifyAPIAuthError(f"Authentication failed: {error_msg}")

            raise SpotifyAPIError(error_msg, response.status_code, error_data.get('error', {}).get('status'))

    def get_authorization_url(self, scopes: List[str]) -> str:
        """
        Generate Spotify authorization URL for OAuth flow.

        Args:
            scopes: List of OAuth scopes

        Returns:
            Authorization URL to redirect user to
        """
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'scope': ' '.join(scopes),
            'state': 'spotify_oauth',  # Simple state for CSRF protection
        }

        query_string = urllib.parse.urlencode(params)
        return f"{self.AUTHORIZE_URL}?{query_string}"

    def exchange_code_for_token(self, authorization_code: str) -> SpotifyToken:
        """
        Exchange authorization code for access token.

        Args:
            authorization_code: Code from OAuth redirect

        Returns:
            SpotifyToken with access and refresh tokens
        """
        data = {
            'grant_type': 'authorization_code',
            'code': authorization_code,
            'redirect_uri': self.redirect_uri,
        }

        headers = {
            'Authorization': self._get_basic_auth_header(),
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        try:
            response = self.session.post(self.TOKEN_URL, data=data, headers=headers)
            response.raise_for_status()
            token_data = response.json()

            token = SpotifyToken(
                access_token=token_data['access_token'],
                token_type=token_data['token_type'],
                scope=token_data.get('scope', ''),
                expires_in=token_data['expires_in'],
                refresh_token=token_data.get('refresh_token'),
                expires_at=time.time() + token_data['expires_in']
            )

            self.token = token
            self._save_token()
            logger.info("Successfully exchanged authorization code for token")
            return token

        except requests.HTTPError as e:
            error_data = response.json() if response.content else {}
            raise SpotifyAPIError(f"Token exchange failed: {error_data}", response.status_code)

    def _refresh_token(self) -> None:
        """Refresh access token using refresh token."""
        if not self.token or not self.token.refresh_token:
            raise SpotifyAPIAuthError("No refresh token available")

        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.token.refresh_token,
        }

        headers = {
            'Authorization': self._get_basic_auth_header(),
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        try:
            response = self.session.post(self.TOKEN_URL, data=data, headers=headers)
            response.raise_for_status()
            token_data = response.json()

            # Update token with new data
            self.token.access_token = token_data['access_token']
            self.token.token_type = token_data['token_type']
            self.token.scope = token_data.get('scope', self.token.scope)
            self.token.expires_in = token_data['expires_in']
            self.token.expires_at = time.time() + token_data['expires_in']

            # Refresh token might be updated
            if 'refresh_token' in token_data:
                self.token.refresh_token = token_data['refresh_token']

            self._save_token()
            logger.info("Successfully refreshed access token")

        except requests.HTTPError as e:
            error_data = response.json() if response.content else {}
            self.token = None  # Clear invalid token
            raise SpotifyAPIError(f"Token refresh failed: {error_data}", response.status_code)

    def _save_token(self) -> None:
        """Save token to storage file."""
        if not self.token_storage_path:
            return

        try:
            self.token_storage_path.parent.mkdir(parents=True, exist_ok=True)

            token_data = {
                'access_token': self.token.access_token,
                'token_type': self.token.token_type,
                'scope': self.token.scope,
                'expires_in': self.token.expires_in,
                'refresh_token': self.token.refresh_token,
                'expires_at': self.token.expires_at,
            }

            with open(self.token_storage_path, 'w') as f:
                json.dump(token_data, f, indent=2)

        except Exception as e:
            logger.warning(f"Failed to save token: {e}")

    def _load_token(self) -> None:
        """Load token from storage file."""
        if not self.token_storage_path or not self.token_storage_path.exists():
            return

        try:
            with open(self.token_storage_path, 'r') as f:
                token_data = json.load(f)

            self.token = SpotifyToken(
                access_token=token_data['access_token'],
                token_type=token_data['token_type'],
                scope=token_data['scope'],
                expires_in=token_data['expires_in'],
                refresh_token=token_data.get('refresh_token'),
                expires_at=token_data.get('expires_at'),
            )

            # Check if loaded token is still valid
            if self.token.is_expired():
                logger.info("Loaded token is expired, will refresh on next request")

        except Exception as e:
            logger.warning(f"Failed to load token: {e}")

    # Core Playback API Methods

    def get_current_playback(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the user's current playback.

        Returns:
            Current playback state or None if nothing playing
        """
        try:
            response = self._make_request('GET', f"{self.BASE_URL}/me/player")
            # If we got a 204 response (handled by _make_request), it returns {"success": True}
            # This means no active playback
            if response.get("success") and response.get("status_code") == 204:
                return None
            return response
        except SpotifyAPIError as e:
            if e.status_code == 204:  # No active device
                return None
            raise

    def play_track(self, track_uri: str, device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Start playback of a track.

        Args:
            track_uri: Spotify URI of track to play
            device_id: Optional device ID to play on

        Returns:
            Success response
        """
        data = {"uris": [track_uri]}
        if device_id:
            data["device_id"] = device_id

        return self._make_request('PUT', f"{self.BASE_URL}/me/player/play", json=data)

    def play_context(self, context_uri: str, offset: Optional[Dict[str, Any]] = None,
                    device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Start playback of a context (album, playlist, artist).

        Args:
            context_uri: Spotify URI of context (album/artist/playlist)
            offset: Optional offset into context (track position)
            device_id: Optional device ID to play on

        Returns:
            Success response
        """
        data = {"context_uri": context_uri}
        if offset:
            data["offset"] = offset
        if device_id:
            data["device_id"] = device_id

        return self._make_request('PUT', f"{self.BASE_URL}/me/player/play", json=data)

    def pause_playback(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Pause current playback.

        Args:
            device_id: Optional device ID to control

        Returns:
            Success response
        """
        params = {}
        if device_id:
            params['device_id'] = device_id
        return self._make_request('PUT', f"{self.BASE_URL}/me/player/pause", params=params)

    def resume_playback(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Resume current playback.

        Args:
            device_id: Optional device ID to control

        Returns:
            Success response
        """
        params = {}
        if device_id:
            params['device_id'] = device_id
        return self._make_request('PUT', f"{self.BASE_URL}/me/player/play", params=params)

    def skip_to_next(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Skip to next track in queue.

        Args:
            device_id: Optional device ID to control

        Returns:
            Success response
        """
        params = {}
        if device_id:
            params['device_id'] = device_id
        return self._make_request('POST', f"{self.BASE_URL}/me/player/next", params=params)

    def skip_to_previous(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Skip to previous track.

        Args:
            device_id: Optional device ID to control

        Returns:
            Success response
        """
        params = {}
        if device_id:
            params['device_id'] = device_id
        return self._make_request('POST', f"{self.BASE_URL}/me/player/previous", params=params)

    def get_devices(self) -> List[Dict[str, Any]]:
        """
        Get information about available devices.

        Returns:
            List of available devices
        """
        response = self._make_request('GET', f"{self.BASE_URL}/me/player/devices")
        return response.get('devices', [])

    def transfer_playback(self, device_id: str, play: bool = False) -> Dict[str, Any]:
        """
        Transfer playback to another device.

        Args:
            device_id: ID of the device to transfer playback to
            play: If true, ensure playback happens on the new device

        Returns:
            Success response
        """
        data = {"device_ids": [device_id], "play": play}
        return self._make_request('PUT', f"{self.BASE_URL}/me/player", json=data)

    def has_available_devices(self) -> bool:
        """
        Check if there are any available devices for playback.

        Returns:
            True if at least one device is available
        """
        try:
            devices = self.get_devices()
            return len(devices) > 0
        except Exception:
            return False

    # Search API Methods

    def search_tracks(self, query: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """
        Search for tracks.

        Args:
            query: Search query
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            Search results
        """
        params = {
            'q': query,
            'type': 'track',
            'limit': limit,
            'offset': offset
        }
        return self._make_request('GET', f"{self.BASE_URL}/search", params=params)

    def search_albums(self, query: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """
        Search for albums.

        Args:
            query: Search query
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            Search results
        """
        params = {
            'q': query,
            'type': 'album',
            'limit': limit,
            'offset': offset
        }
        return self._make_request('GET', f"{self.BASE_URL}/search", params=params)

    def search_artists(self, query: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """
        Search for artists.

        Args:
            query: Search query
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            Search results
        """
        params = {
            'q': query,
            'type': 'artist',
            'limit': limit,
            'offset': offset
        }
        return self._make_request('GET', f"{self.BASE_URL}/search", params=params)

    def search(self, query: str, types: List[str] = None, limit: int = 20) -> Dict[str, Any]:
        """
        General search across multiple types.

        Args:
            query: Search query
            types: List of types to search (track, album, artist)
            limit: Maximum results per type

        Returns:
            Search results by type
        """
        if types is None:
            types = ['track', 'album', 'artist']

        params = {
            'q': query,
            'type': ','.join(types),
            'limit': limit
        }
        return self._make_request('GET', f"{self.BASE_URL}/search", params=params)

    # Convenience methods for common operations

    def play_first_track(self, query: str) -> Dict[str, Any]:
        """
        Search for a track and play the first result.

        Args:
            query: Search query for track

        Returns:
            Play result
        """
        search_result = self.search_tracks(query, limit=1)
        tracks = search_result.get('tracks', {}).get('items', [])

        if not tracks:
            raise SpotifyAPIError(f"No tracks found for query: {query}")

        track_uri = tracks[0]['uri']
        return self.play_track(track_uri)

    def play_first_album(self, query: str) -> Dict[str, Any]:
        """
        Search for an album and play it.

        Args:
            query: Search query for album

        Returns:
            Play result
        """
        search_result = self.search_albums(query, limit=1)
        albums = search_result.get('albums', {}).get('items', [])

        if not albums:
            raise SpotifyAPIError(f"No albums found for query: {query}")

        album_uri = albums[0]['uri']
        return self.play_context(album_uri)

    def play_first_artist(self, query: str) -> Dict[str, Any]:
        """
        Search for an artist and play their top tracks.

        Args:
            query: Search query for artist

        Returns:
            Play result
        """
        search_result = self.search_artists(query, limit=1)
        artists = search_result.get('artists', {}).get('items', [])

        if not artists:
            raise SpotifyAPIError(f"No artists found for query: {query}")

        artist_uri = artists[0]['uri']
        return self.play_context(artist_uri)

    def is_authenticated(self) -> bool:
        """
        Check if client has valid authentication.
        Auto-refreshes expired tokens if refresh token is available.

        Returns:
            True if authenticated and token is valid (or successfully refreshed)
        """
        if not self.token:
            return False
        
        # If token is expired but we have a refresh token, try to refresh
        if self.token.is_expired() and self.token.refresh_token:
            try:
                logger.info("Token expired, auto-refreshing in is_authenticated check")
                self._refresh_token()
                return self.token is not None and not self.token.is_expired()
            except Exception as e:
                logger.warning(f"Failed to refresh token in is_authenticated: {e}")
                return False
        
        return not self.token.is_expired()
