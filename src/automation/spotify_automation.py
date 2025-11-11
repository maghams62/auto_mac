"""
Spotify Automation - Control Spotify playback on macOS using AppleScript.
"""

import subprocess
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SpotifyAutomation:
    """Automate Spotify app on macOS for playback control."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def play(self) -> Dict[str, Any]:
        """
        Play music in Spotify.

        Returns:
            Dictionary with success status and message
        """
        logger.info("[SPOTIFY AUTOMATION] Playing music")

        try:
            applescript = '''
            tell application "Spotify"
                activate
                play
            end tell
            '''

            result = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "action": "play",
                    "message": "Music is now playing",
                    "status": "playing"
                }
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                logger.error(f"[SPOTIFY AUTOMATION] Play failed: {error_msg}")
                return {
                    "success": False,
                    "error": True,
                    "error_type": "PlaybackError",
                    "error_message": f"Failed to play music: {error_msg}",
                    "retry_possible": True
                }

        except subprocess.TimeoutExpired:
            logger.error("[SPOTIFY AUTOMATION] Play command timed out")
            return {
                "success": False,
                "error": True,
                "error_type": "TimeoutError",
                "error_message": "Play command timed out - Spotify may not be responding",
                "retry_possible": True
            }
        except Exception as e:
            logger.error(f"[SPOTIFY AUTOMATION] Error playing music: {e}")
            return {
                "success": False,
                "error": True,
                "error_type": "SpotifyError",
                "error_message": f"Error controlling Spotify: {str(e)}",
                "retry_possible": True
            }

    def pause(self) -> Dict[str, Any]:
        """
        Pause music in Spotify.

        Returns:
            Dictionary with success status and message
        """
        logger.info("[SPOTIFY AUTOMATION] Pausing music")

        try:
            applescript = '''
            tell application "Spotify"
                activate
                pause
            end tell
            '''

            result = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "action": "pause",
                    "message": "Music is now paused",
                    "status": "paused"
                }
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                logger.error(f"[SPOTIFY AUTOMATION] Pause failed: {error_msg}")
                return {
                    "success": False,
                    "error": True,
                    "error_type": "PlaybackError",
                    "error_message": f"Failed to pause music: {error_msg}",
                    "retry_possible": True
                }

        except subprocess.TimeoutExpired:
            logger.error("[SPOTIFY AUTOMATION] Pause command timed out")
            return {
                "success": False,
                "error": True,
                "error_type": "TimeoutError",
                "error_message": "Pause command timed out - Spotify may not be responding",
                "retry_possible": True
            }
        except Exception as e:
            logger.error(f"[SPOTIFY AUTOMATION] Error pausing music: {e}")
            return {
                "success": False,
                "error": True,
                "error_type": "SpotifyError",
                "error_message": f"Error controlling Spotify: {str(e)}",
                "retry_possible": True
            }

    def get_status(self) -> Dict[str, Any]:
        """
        Get current playback status from Spotify.

        Returns:
            Dictionary with current status (playing/paused) and track info
        """
        logger.info("[SPOTIFY AUTOMATION] Getting playback status")

        try:
            applescript = '''
            tell application "Spotify"
                set playerState to player state as string
                set trackName to name of current track
                set artistName to artist of current track
                return playerState & "|" & trackName & "|" & artistName
            end tell
            '''

            result = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                parts = output.split("|")
                if len(parts) >= 3:
                    state = parts[0].strip()
                    track = parts[1].strip()
                    artist = parts[2].strip()
                    
                    return {
                        "success": True,
                        "status": state.lower(),
                        "track": track,
                        "artist": artist,
                        "message": f"Currently {state.lower()}: {track} by {artist}" if track and artist else f"Status: {state.lower()}"
                    }
                else:
                    return {
                        "success": True,
                        "status": output.lower() if output else "unknown",
                        "track": None,
                        "artist": None,
                        "message": f"Status: {output}" if output else "Status unknown"
                    }
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                logger.error(f"[SPOTIFY AUTOMATION] Get status failed: {error_msg}")
                return {
                    "success": False,
                    "error": True,
                    "error_type": "StatusError",
                    "error_message": f"Failed to get status: {error_msg}",
                    "retry_possible": True
                }

        except subprocess.TimeoutExpired:
            logger.error("[SPOTIFY AUTOMATION] Get status command timed out")
            return {
                "success": False,
                "error": True,
                "error_type": "TimeoutError",
                "error_message": "Status command timed out",
                "retry_possible": True
            }
        except Exception as e:
            logger.error(f"[SPOTIFY AUTOMATION] Error getting status: {e}")
            return {
                "success": False,
                "error": True,
                "error_type": "SpotifyError",
                "error_message": f"Error getting Spotify status: {str(e)}",
                "retry_possible": True
            }

