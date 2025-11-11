"""
Spotify Agent - Controls Spotify playback on macOS.

This agent is responsible for:
- Playing music in Spotify
- Pausing music in Spotify
- Getting playback status

Uses AppleScript to control the Spotify desktop app.
"""

from typing import Dict, Any
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)


@tool
def play_music() -> Dict[str, Any]:
    """
    Play music in Spotify.

    Use this tool when you need to:
    - Start playing music
    - Resume playback
    - Play music after pausing

    This is useful for:
    - Starting music playback ("play music", "start music")
    - Resuming paused music ("resume", "continue playing")
    - Quick music control ("play")

    Returns:
        Dictionary with success status and message

    Examples:
        # Play music
        play_music()

        # User says "play music" or "start music"
        → play_music()
    """
    logger.info("[SPOTIFY AGENT] Tool: play_music()")

    try:
        from ..automation import SpotifyAutomation
        from ..utils import load_config

        config = load_config()
        spotify = SpotifyAutomation(config)

        result = spotify.play()

        if result.get("success"):
            return {
                "success": True,
                "action": "play",
                "status": "playing",
                "message": result.get("message", "Music is now playing")
            }
        else:
            return result

    except Exception as e:
        logger.error(f"[SPOTIFY AGENT] Error in play_music: {e}")
        return {
            "error": True,
            "error_type": "SpotifyError",
            "error_message": f"Failed to play music: {str(e)}",
            "retry_possible": True
        }


@tool
def pause_music() -> Dict[str, Any]:
    """
    Pause music in Spotify.

    Use this tool when you need to:
    - Stop/pause music playback
    - Pause currently playing music
    - Temporarily stop playback

    This is useful for:
    - Pausing music ("pause", "pause music", "stop music")
    - Quick pause control ("pause playback")
    - Stopping music temporarily

    Returns:
        Dictionary with success status and message

    Examples:
        # Pause music
        pause_music()

        # User says "pause" or "pause music"
        → pause_music()
    """
    logger.info("[SPOTIFY AGENT] Tool: pause_music()")

    try:
        from ..automation import SpotifyAutomation
        from ..utils import load_config

        config = load_config()
        spotify = SpotifyAutomation(config)

        result = spotify.pause()

        if result.get("success"):
            return {
                "success": True,
                "action": "pause",
                "status": "paused",
                "message": result.get("message", "Music is now paused")
            }
        else:
            return result

    except Exception as e:
        logger.error(f"[SPOTIFY AGENT] Error in pause_music: {e}")
        return {
            "error": True,
            "error_type": "SpotifyError",
            "error_message": f"Failed to pause music: {str(e)}",
            "retry_possible": True
        }


@tool
def get_spotify_status() -> Dict[str, Any]:
    """
    Get current playback status from Spotify.

    Use this tool when you need to:
    - Check if music is playing or paused
    - Get current track information
    - Check Spotify playback state

    This is useful for:
    - Status checks ("what's playing?", "is music playing?")
    - Getting track info ("what song is this?")
    - Checking playback state

    Returns:
        Dictionary with current status, track, and artist info

    Examples:
        # Get status
        get_spotify_status()

        # User says "what's playing?" or "is music playing?"
        → get_spotify_status()
    """
    logger.info("[SPOTIFY AGENT] Tool: get_spotify_status()")

    try:
        from ..automation import SpotifyAutomation
        from ..utils import load_config

        config = load_config()
        spotify = SpotifyAutomation(config)

        result = spotify.get_status()

        return result

    except Exception as e:
        logger.error(f"[SPOTIFY AGENT] Error in get_spotify_status: {e}")
        return {
            "error": True,
            "error_type": "SpotifyError",
            "error_message": f"Failed to get Spotify status: {str(e)}",
            "retry_possible": True
        }


# Tool exports
SPOTIFY_AGENT_TOOLS = [play_music, pause_music, get_spotify_status]

# Agent hierarchy documentation
SPOTIFY_AGENT_HIERARCHY = """
SPOTIFY AGENT (3 tools)
Domain: Music playback control
└─ Tools:
   ├─ play_music - Start/resume music playback
   ├─ pause_music - Pause music playback
   └─ get_spotify_status - Get current playback status and track info
"""


class SpotifyAgent:
    """
    Spotify Agent - Controls Spotify playback.

    This agent handles music playback control through Spotify desktop app.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = SPOTIFY_AGENT_TOOLS
        logger.info("[SPOTIFY AGENT] Initialized")

    def get_tools(self):
        """Get all Spotify agent tools."""
        return SPOTIFY_AGENT_TOOLS

    def execute(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a Spotify tool.

        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters

        Returns:
            Tool execution result
        """
        logger.info(f"[SPOTIFY AGENT] Executing tool: {tool_name}")

        tool_map = {
            "play_music": play_music,
            "pause_music": pause_music,
            "get_spotify_status": get_spotify_status,
        }

        tool = tool_map.get(tool_name)
        if not tool:
            return {
                "error": True,
                "error_type": "UnknownTool",
                "error_message": f"Unknown tool: {tool_name}",
                "available_tools": list(tool_map.keys())
            }

        try:
            result = tool.invoke(parameters)
            return result
        except Exception as e:
            logger.error(f"[SPOTIFY AGENT] Tool execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e)
            }

