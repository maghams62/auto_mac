"""
Integration tests for Spotify API client and playback service.

These tests verify the Spotify API integration works correctly,
including OAuth flow simulation and playback operations.
"""

import pytest
import json
import tempfile
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Test the Spotify API client
class TestSpotifyAPIClient:
    """Test Spotify API client functionality."""

    def test_client_initialization(self):
        """Test client initializes with correct parameters."""
        from src.integrations.spotify_api import SpotifyAPIClient

        with patch('src.integrations.spotify_api.SpotifyAPIClient._load_token'):
            client = SpotifyAPIClient(
                client_id="test_client_id",
                client_secret="test_client_secret",
                redirect_uri="http://localhost:3000/redirect"
            )

            assert client.client_id == "test_client_id"
            assert client.client_secret == "test_client_secret"
            assert client.redirect_uri == "http://localhost:3000/redirect"

    def test_authorization_url_generation(self):
        """Test OAuth authorization URL generation."""
        from src.integrations.spotify_api import SpotifyAPIClient

        with patch('src.integrations.spotify_api.SpotifyAPIClient._load_token'):
            client = SpotifyAPIClient(
                client_id="test_client_id",
                client_secret="test_client_secret",
                redirect_uri="http://localhost:3000/redirect"
            )

            url = client.get_authorization_url(["user-read-playback-state", "user-modify-playback-state"])

            assert "https://accounts.spotify.com/authorize" in url
            assert "client_id=test_client_id" in url
            assert "redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Fredirect" in url  # Correct URL encoding
            assert "scope=user-read-playback-state+user-modify-playback-state" in url

    @patch('src.integrations.spotify_api.requests.Session')
    def test_token_exchange(self, mock_session_class):
        """Test authorization code exchange for tokens."""
        from src.integrations.spotify_api import SpotifyAPIClient, SpotifyToken

        # Mock the session and its post method
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'access_token': 'test_access_token',
            'token_type': 'Bearer',
            'scope': 'user-read-playback-state',
            'expires_in': 3600,
            'refresh_token': 'test_refresh_token'
        }
        mock_session.post.return_value = mock_response

        with patch('src.integrations.spotify_api.SpotifyAPIClient._load_token'), \
             patch('src.integrations.spotify_api.SpotifyAPIClient._save_token'):

            client = SpotifyAPIClient(
                client_id="test_client_id",
                client_secret="test_client_secret",
                redirect_uri="http://localhost:3000/redirect"
            )

            token = client.exchange_code_for_token("test_auth_code")

            assert isinstance(token, SpotifyToken)
            assert token.access_token == 'test_access_token'
            assert token.refresh_token == 'test_refresh_token'
            assert token.token_type == 'Bearer'

    def test_token_expiration(self):
        """Test token expiration detection."""
        from src.integrations.spotify_api import SpotifyToken
        import time

        # Test expired token
        past_time = time.time() - 100
        expired_token = SpotifyToken(
            access_token="test",
            token_type="Bearer",
            scope="test",
            expires_in=3600,
            expires_at=past_time
        )
        assert expired_token.is_expired()

        # Test valid token
        future_time = time.time() + 100
        valid_token = SpotifyToken(
            access_token="test",
            token_type="Bearer",
            scope="test",
            expires_in=3600,
            expires_at=future_time
        )
        assert not valid_token.is_expired()


class TestSpotifyPlaybackService:
    """Test Spotify playback service integration."""

    def test_service_initialization(self):
        """Test playback service initializes correctly."""
        from src.integrations.spotify_playback_service import SpotifyPlaybackService

        config = {
            "playback": {"use_api": True}
        }

        service = SpotifyPlaybackService(config)
        assert service.prefer_api is True

        # Test with API disabled
        config["playback"]["use_api"] = False
        service = SpotifyPlaybackService(config)
        assert service.prefer_api is False

    @patch('src.integrations.spotify_playback_service.SpotifyAPIBackend')
    @patch('src.integrations.spotify_playback_service.SpotifyAutomationBackend')
    def test_backend_selection(self, mock_automation, mock_api):
        """Test backend selection logic."""
        from src.integrations.spotify_playback_service import SpotifyPlaybackService, PlaybackBackend

        # Mock API backend as available
        mock_api_instance = Mock()
        mock_api_instance.is_available.return_value = True
        mock_api.return_value = mock_api_instance

        # Mock automation backend
        mock_automation_instance = Mock()
        mock_automation.return_value = mock_automation_instance

        config = {"playback": {"use_api": True}}
        service = SpotifyPlaybackService(config)

        # Should select API backend for URI
        backend = service._select_backend("play_track")
        assert backend == mock_api_instance

    def test_uri_detection(self):
        """Test URI detection in play_track method."""
        from src.integrations.spotify_playback_service import SpotifyPlaybackService, PlaybackResult

        config = {"playback": {"use_api": True}}  # Enable API for URI testing
        service = SpotifyPlaybackService(config)

        # Mock API backend as available and working
        mock_result = PlaybackResult(
            success=True,
            action="play_track",
            message="Track started via API",
            backend=service.api_backend.backend_type
        )

        with patch.object(service.api_backend, 'is_available', return_value=True), \
             patch.object(service.api_backend, 'play_track', return_value=mock_result), \
             patch.object(service.api_backend, 'play_album', return_value=mock_result), \
             patch.object(service.api_backend, 'play_artist', return_value=mock_result):

            # Test track URI - should use API backend
            result = service.play_track("spotify:track:4uLU6hMCjMI75M1A2tKUQC")
            assert result.success is True
            assert result.action == "play_track"

            # Test album URI - should use API backend
            result = service.play_track("spotify:album:4uLU6hMCjMI75M1A2tKUQC")
            assert result.success is True

            # Test artist URI - should use API backend
            result = service.play_track("spotify:artist:4uLU6hMCjMI75M1A2tKUQC")
            assert result.success is True


class TestSpotifyAgentIntegration:
    """Test Spotify agent integration with new tools."""

    def test_new_tools_available(self):
        """Test that new album/artist tools are available."""
        from src.agent.spotify_agent import SPOTIFY_AGENT_TOOLS

        tool_names = [tool.name for tool in SPOTIFY_AGENT_TOOLS]

        assert "play_music" in tool_names
        assert "pause_music" in tool_names
        assert "get_spotify_status" in tool_names
        assert "play_song" in tool_names
        assert "play_album" in tool_names  # New tool
        assert "play_artist" in tool_names  # New tool

        assert len(SPOTIFY_AGENT_TOOLS) == 6  # Should have 6 tools now

    @patch('src.integrations.spotify_playback_service.SpotifyPlaybackService')
    def test_album_tool_execution(self, mock_service):
        """Test play_album tool execution."""
        from src.agent.spotify_agent import play_album

        # Mock service and result
        mock_service_instance = Mock()
        mock_result = Mock()
        mock_result.to_dict.return_value = {
            "success": True,
            "action": "play_album",
            "message": "Album started"
        }
        mock_service_instance.play_album.return_value = mock_result
        mock_service.return_value = mock_service_instance

        with patch('src.utils.load_config', return_value={"test": "config"}):
            result = play_album("Abbey Road")

            assert result["success"] is True
            assert result["action"] == "play_album"
            mock_service_instance.play_album.assert_called_once_with("Abbey Road")

    @patch('src.integrations.spotify_playback_service.SpotifyPlaybackService')
    def test_artist_tool_execution(self, mock_service):
        """Test play_artist tool execution."""
        from src.agent.spotify_agent import play_artist

        # Mock service and result
        mock_service_instance = Mock()
        mock_result = Mock()
        mock_result.to_dict.return_value = {
            "success": True,
            "action": "play_artist",
            "message": "Artist started"
        }
        mock_service_instance.play_artist.return_value = mock_result
        mock_service.return_value = mock_service_instance

        with patch('src.utils.load_config', return_value={"test": "config"}):
            result = play_artist("The Beatles")

            assert result["success"] is True
            assert result["action"] == "play_artist"
            mock_service_instance.play_artist.assert_called_once_with("The Beatles")


class TestSlashCommandRouting:
    """Test slash command routing for new album/artist commands."""

    def test_album_command_routing(self):
        """Test routing of album commands."""
        from src.ui.slash_commands import SlashCommandHandler

        handler = SlashCommandHandler({})

        # Test album command
        tool_name, params, status_msg = handler._route_spotify_command("play album Abbey Road")

        assert tool_name == "play_album"
        assert params == {"album_name": "Abbey Road"}
        assert status_msg is None

    def test_artist_command_routing(self):
        """Test routing of artist commands."""
        from src.ui.slash_commands import SlashCommandHandler

        handler = SlashCommandHandler({})

        # Test artist command
        tool_name, params, status_msg = handler._route_spotify_command("play artist The Beatles")

        assert tool_name == "play_artist"
        assert params == {"artist_name": "The Beatles"}
        assert status_msg is None

    def test_song_command_routing_still_works(self):
        """Test that song command routing still works."""
        from src.ui.slash_commands import SlashCommandHandler

        handler = SlashCommandHandler({})

        # Test song command
        tool_name, params, status_msg = handler._route_spotify_command("play Viva la Vida")

        assert tool_name == "play_song"
        assert params == {"song_name": "Viva la Vida"}
        assert status_msg is None


if __name__ == "__main__":
    pytest.main([__file__])
