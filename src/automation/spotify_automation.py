"""
Spotify Automation - Control Spotify playback on macOS using AppleScript.
"""

import subprocess
import logging
from typing import Dict, Any
from urllib.parse import quote
from ..utils.message_personality import get_music_playing_message, get_music_paused_message

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
                    "message": get_music_playing_message(),
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
                    "message": get_music_paused_message(),
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

    def next_track(self) -> Dict[str, Any]:
        """
        Skip to the next track in Spotify.

        Returns:
            Dictionary with success status and message
        """
        logger.info("[SPOTIFY AUTOMATION] Skipping to next track")

        try:
            applescript = '''
            tell application "Spotify"
                activate
                next track
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
                    "action": "next_track",
                    "message": "Skipped to the next track.",
                    "status": "skipped_next"
                }
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                logger.error(f"[SPOTIFY AUTOMATION] Next track failed: {error_msg}")
                return {
                    "success": False,
                    "error": True,
                    "error_type": "PlaybackError",
                    "error_message": f"Failed to skip track: {error_msg}",
                    "retry_possible": True
                }

        except subprocess.TimeoutExpired:
            logger.error("[SPOTIFY AUTOMATION] Next track command timed out")
            return {
                "success": False,
                "error": True,
                "error_type": "TimeoutError",
                "error_message": "Next track command timed out - Spotify may not be responding",
                "retry_possible": True
            }
        except Exception as e:
            logger.error(f"[SPOTIFY AUTOMATION] Error skipping to next track: {e}")
            return {
                "success": False,
                "error": True,
                "error_type": "SpotifyError",
                "error_message": f"Error controlling Spotify: {str(e)}",
                "retry_possible": True
            }

    def previous_track(self) -> Dict[str, Any]:
        """
        Return to the previous track in Spotify.

        Returns:
            Dictionary with success status and message
        """
        logger.info("[SPOTIFY AUTOMATION] Returning to previous track")

        try:
            applescript = '''
            tell application "Spotify"
                activate
                previous track
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
                    "action": "previous_track",
                    "message": "Replaying the previous track.",
                    "status": "skipped_previous"
                }
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                logger.error(f"[SPOTIFY AUTOMATION] Previous track failed: {error_msg}")
                return {
                    "success": False,
                    "error": True,
                    "error_type": "PlaybackError",
                    "error_message": f"Failed to replay previous track: {error_msg}",
                    "retry_possible": True
                }

        except subprocess.TimeoutExpired:
            logger.error("[SPOTIFY AUTOMATION] Previous track command timed out")
            return {
                "success": False,
                "error": True,
                "error_type": "TimeoutError",
                "error_message": "Previous track command timed out - Spotify may not be responding",
                "retry_possible": True
            }
        except Exception as e:
            logger.error(f"[SPOTIFY AUTOMATION] Error returning to previous track: {e}")
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

    def _validate_search_input(self, song_name: str, artist: str = None) -> Dict[str, Any]:
        """
        Validate search input parameters.
        
        Args:
            song_name: Song name to validate
            artist: Optional artist name to validate
        
        Returns:
            Dictionary with "valid" (bool) and "error_message" (str if invalid)
        """
        if not song_name:
            return {
                "valid": False,
                "error_message": "Song name cannot be empty"
            }
        
        if not isinstance(song_name, str):
            return {
                "valid": False,
                "error_message": f"Song name must be a string, got {type(song_name)}"
            }
        
        if not song_name.strip():
            return {
                "valid": False,
                "error_message": "Song name cannot be empty or whitespace only"
            }
        
        if artist is not None:
            if not isinstance(artist, str):
                return {
                    "valid": False,
                    "error_message": f"Artist must be a string or None, got {type(artist)}"
                }
            
            if not artist.strip():
                return {
                    "valid": False,
                    "error_message": "Artist cannot be empty or whitespace only if provided"
                }
        
        return {"valid": True}

    def search_and_play(self, song_name: str, artist: str = None) -> Dict[str, Any]:
        """
        Search for a song by name and play it in Spotify.

        AppleScript Flow:
        1. Activate Spotify (opens if closed)
        2. Use Spotify search URI to search for the track
        3. Wait briefly for search results to load
        4. Play the first result
        5. Verify playback started by checking status
        
        Fallbacks:
        - If Spotify not running: Returns error with clear message
        - If song not found: Returns error suggesting user check spelling
        - If search fails: Returns error with retry suggestion

        Args:
            song_name: Name of the song to search for (required, non-empty string)
            artist: Optional artist name to improve search accuracy

        Returns:
            Dictionary with shape:
            {
                "success": bool,
                "action": "play_song",
                "song_name": str,  # Original requested song name
                "artist": str | None,  # Artist if provided
                "status": "playing" | "error",
                "message": str,  # User-friendly message
                "track": str,  # Actual track name playing
                "track_artist": str,  # Actual artist playing
                "error": bool (if success=False),
                "error_type": str (if error),
                "error_message": str (if error),
                "retry_possible": bool (if error)
            }
        """
        # Validate input before processing
        validation_result = self._validate_search_input(song_name, artist)
        if not validation_result["valid"]:
            return {
                "success": False,
                "error": True,
                "error_type": "ValidationError",
                "error_message": validation_result["error_message"],
                "retry_possible": False
            }
        
        logger.info(f"[SPOTIFY AUTOMATION] Searching and playing: {song_name}" + (f" by {artist}" if artist else ""))

        try:
            # Build search query - preserve Unicode, will be URL-encoded
            if artist:
                search_query = f"{song_name} {artist}"
            else:
                search_query = song_name
            
            # URL-encode the search query for Spotify URI (preserves Unicode)
            encoded_query = quote(search_query, safe="")
            
            # Use Spotify URI approach with keyboard simulation
            applescript = f'''tell application "Spotify"
    activate
    try
        -- Use Spotify search URI (more reliable than AppleScript search command)
        open location "spotify:search:{encoded_query}"

        -- Wait for search to load
        delay 3

        -- Try to play the first result by simulating keyboard input
        -- Press Enter to play the first search result
        tell application "System Events"
            key code 76 -- Press Enter key
        end tell

        -- Wait a moment for playback to start
        delay 2

        -- Return success with track info
        set trackName to name of current track
        set artistName to artist of current track
        return "SUCCESS: " & trackName & " by " & artistName
    on error errMsg
        return "ERROR: " & errMsg
    end try
end tell'''

            # Use stdin approach for more reliable string handling
            result = subprocess.run(
                ["osascript", "-"],
                input=applescript,
                capture_output=True,
                text=True,
                timeout=15,
                encoding='utf-8'
            )

            if result.returncode == 0:
                output = result.stdout.strip() if result.stdout else ""
                
                # Check if AppleScript returned success with track info
                if output.startswith("SUCCESS:"):
                    # Extract track name and artist from AppleScript output
                    # Format: "SUCCESS: TrackName by ArtistName"
                    success_parts = output.replace("SUCCESS:", "").strip()
                    if " by " in success_parts:
                        track_parts = success_parts.split(" by ", 1)
                        track = track_parts[0].strip()
                        artist_name = track_parts[1].strip() if len(track_parts) > 1 else "Unknown Artist"
                    else:
                        track = success_parts
                        artist_name = artist or "Unknown Artist"
                    
                    # Verify playback started
                    import time
                    time.sleep(0.5)  # Brief wait for playback to start
                    
                    status_result = self.get_status()
                    if status_result.get("success") and status_result.get("status") == "playing":
                        # Confirm we're playing the right track
                        actual_track = status_result.get("track", "")
                        if actual_track and track.lower() in actual_track.lower() or actual_track.lower() in track.lower():
                            return {
                                "success": True,
                                "action": "play_song",
                                "song_name": song_name,
                                "artist": artist,
                                "status": "playing",
                                "message": f"Now playing: {track} by {artist_name}",
                                "track": track,
                                "track_artist": artist_name
                            }
                    
                    # If status check failed but AppleScript succeeded, still return success
                    return {
                        "success": True,
                        "action": "play_song",
                        "song_name": song_name,
                        "artist": artist,
                        "status": "playing",
                        "message": f"Now playing: {track} by {artist_name}",
                        "track": track,
                        "track_artist": artist_name
                    }
                elif output.startswith("ERROR:"):
                    # AppleScript returned explicit error
                    error_msg = output.replace("ERROR:", "").strip()
                    logger.error(f"[SPOTIFY AUTOMATION] AppleScript error: {error_msg}")
                    
                    if "no results found" in error_msg.lower():
                        return {
                            "success": False,
                            "error": True,
                            "error_type": "SongNotFound",
                            "error_message": f"Could not find '{song_name}' in Spotify. Please check the spelling or try a different search.",
                            "retry_possible": True
                        }
                    else:
                        return {
                            "success": False,
                            "error": True,
                            "error_type": "SearchError",
                            "error_message": f"Could not play '{song_name}'. {error_msg}",
                            "retry_possible": True
                        }
                else:
                    # Unexpected output, try status check as fallback
                    import time
                    time.sleep(0.5)
                    status_result = self.get_status()
                    if status_result.get("success") and status_result.get("status") == "playing":
                        track = status_result.get("track", song_name)
                        artist_name = status_result.get("artist", artist or "Unknown Artist")
                        return {
                            "success": True,
                            "action": "play_song",
                            "song_name": song_name,
                            "artist": artist,
                            "status": "playing",
                            "message": f"Now playing: {track} by {artist_name}",
                            "track": track,
                            "track_artist": artist_name
                        }
                    else:
                        return {
                            "success": False,
                            "error": True,
                            "error_type": "SearchError",
                            "error_message": f"Could not play '{song_name}'. Please make sure Spotify is running and the song exists.",
                            "retry_possible": True
                        }
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                logger.error(f"[SPOTIFY AUTOMATION] Search and play failed for '{song_name}': {error_msg}")
                
                # Check error type and provide specific error messages
                error_lower = error_msg.lower()
                
                if "not running" in error_lower or "not found" in error_lower or "application" in error_lower:
                    return {
                        "success": False,
                        "error": True,
                        "error_type": "SpotifyNotRunning",
                        "error_message": f"Spotify is not running. Please open Spotify and try again. (Song: '{song_name}')",
                        "retry_possible": True
                    }
                elif "couldn't find" in error_lower or "no results" in error_lower:
                    return {
                        "success": False,
                        "error": True,
                        "error_type": "SongNotFound",
                        "error_message": f"Could not find '{song_name}' in Spotify. Please check the spelling or try a different search.",
                        "retry_possible": True
                    }
                elif "syntax error" in error_lower or "parse" in error_lower:
                    # AppleScript syntax error - this should be rare with character code construction
                    logger.error(f"[SPOTIFY AUTOMATION] AppleScript syntax error for '{song_name}': {error_msg}")
                    return {
                        "success": False,
                        "error": True,
                        "error_type": "AppleScriptError",
                        "error_message": f"AppleScript syntax error while searching for '{song_name}'. Error: {error_msg}",
                        "retry_possible": False  # Syntax errors are not retryable
                    }
                else:
                    return {
                        "success": False,
                        "error": True,
                        "error_type": "SearchError",
                        "error_message": f"Could not play '{song_name}'. Error: {error_msg}. Please make sure Spotify is running and the song exists.",
                        "retry_possible": True
                    }

        except subprocess.TimeoutExpired:
            logger.error("[SPOTIFY AUTOMATION] Search and play command timed out")
            return {
                "success": False,
                "error": True,
                "error_type": "TimeoutError",
                "error_message": "Search and play command timed out - Spotify may not be responding",
                "retry_possible": True
            }
        except Exception as e:
            logger.error(f"[SPOTIFY AUTOMATION] Error searching and playing song: {e}")
            return {
                "success": False,
                "error": True,
                "error_type": "SpotifyError",
                "error_message": f"Error searching and playing song: {str(e)}",
                "retry_possible": True
            }
