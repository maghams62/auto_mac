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
from ..utils.message_personality import get_music_playing_message, get_music_paused_message

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
                "message": result.get("message", get_music_playing_message())
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
                "message": result.get("message", get_music_paused_message())
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


@tool
def play_song(song_name: str) -> Dict[str, Any]:
    """
    Play a specific song by name in Spotify.

    TWO USAGE SCENARIOS:
    
    1. DIRECT USE (When LLM can reason out the song):
       - Use this tool DIRECTLY for song queries you can identify from your music knowledge
       - NO google_search needed first!
       - This tool uses LLM-powered semantic understanding to resolve song queries internally
       - Handles descriptive queries, vague references, and partial names using internal LLM reasoning
    
    2. FALLBACK USE (When LLM cannot identify the song):
       - If you cannot confidently identify the song, use google_search FIRST to find the song name
       - Then pass the identified song name to this tool
       - Example: google_search("new Taylor Swift album songs") → extract song name → play_song("<song_name>")

    Use this tool DIRECTLY when:
    - You can identify well-known songs (e.g., "Viva la Vida", "Breaking the Habit")
    - You can reason about descriptive queries (e.g., "Michael Jackson moonwalk song" → "Smooth Criminal")
    - You can resolve vague references (e.g., "the space song" → "Space Song" by Beach House)
    - You can handle partial descriptions with artist hints (e.g., "space by Eminem" → "Space Bound")

    Use google_search FIRST, then this tool when:
    - Song is obscure/unknown (e.g., "that indie song I heard last week")
    - Description is unclear (e.g., "that song with the weird beat")
    - Recent releases you might not know (e.g., "new Taylor Swift album song")
    - Ambiguous queries with no clear match (e.g., "that song about love")

    This tool automatically:
    - Identifies songs from descriptive queries (e.g., "moonwalk" → "Smooth Criminal" by Michael Jackson)
    - Resolves vague references (e.g., "the space song" → "Space Song" by Beach House)
    - Extracts full song names from natural language (e.g., "song called X" → "X")
    - Handles partial descriptions with artist hints (e.g., "space by Eminem" → "Space Bound")
    - Returns high confidence matches for well-known songs

    This is useful for:
    - Playing specific songs ("play Viva la Vida", "play that song called Viva la something")
    - Descriptive queries ("play that Michael Jackson song where he does the moonwalk")
    - Vague references ("play the space song")
    - Handling partial song names ("play Viva la", "play Hello")
    - Correcting misspellings ("play Viba la Vida" → "Viva la Vida")
    - Playing songs identified from search results (after google_search)

    Args:
        song_name: The song query (may be fuzzy, partial, descriptive, or imprecise)
                   Can be:
                   - User's exact query (if LLM can identify it)
                   - Song name extracted from google_search results (if fallback was used)
                   - Pass the user's exact query - no preprocessing needed for direct use!

    Returns:
        Dictionary with success status, song info, and message

    Examples:
        # Scenario 1: Direct use (LLM can identify)
        # Play exact song name
        play_song("Viva la Vida")
        
        # Play descriptive query (NO google_search needed!)
        play_song("that Michael Jackson song where he does the moonwalk")
        # → Automatically identifies as "Smooth Criminal" by Michael Jackson
        
        # Play vague reference
        play_song("the space song")
        # → Automatically identifies as "Space Song" by Beach House
        
        # Play partial with artist hint
        play_song("song that starts with space by Eminem")
        # → Automatically identifies as "Space Bound" by Eminem
        
        # Scenario 2: Fallback use (after google_search)
        # Step 1: google_search("new Taylor Swift album songs 2024")
        # Step 2: Extract song name from results
        # Step 3: play_song("Anti-Hero")  # or whatever song was identified
"""
    logger.info(f"[SPOTIFY AGENT] Tool: play_song('{song_name}')")

    try:
        from ..automation import SpotifyAutomation
        from ..llm import SongDisambiguator
        from ..utils import load_config

        config = load_config()
        spotify = SpotifyAutomation(config)
        
        # Use LLM to disambiguate fuzzy song name
        disambiguator = SongDisambiguator(config)
        disambiguation_result = disambiguator.disambiguate(song_name)
        
        resolved_song_name = disambiguation_result.get("song_name", song_name)
        resolved_artist = disambiguation_result.get("artist")
        confidence = disambiguation_result.get("confidence", 0.5)
        
        # Validation: Ensure we have a valid song name
        if not resolved_song_name or not resolved_song_name.strip():
            return {
                "error": True,
                "error_type": "ValidationError",
                "error_message": f"Could not resolve song name from '{song_name}'. Please try a different search.",
                "retry_possible": True
            }
        
        logger.info(
            f"[SPOTIFY AGENT] Disambiguated '{song_name}' → '{resolved_song_name}' "
            f"by {resolved_artist or 'Unknown'} (confidence: {confidence:.2f})"
        )
        
        # Low confidence threshold: warn but proceed
        LOW_CONFIDENCE_THRESHOLD = 0.5
        if confidence < LOW_CONFIDENCE_THRESHOLD:
            logger.warning(
                f"[SPOTIFY AGENT] Low confidence disambiguation ({confidence:.2f}). "
                f"Proceeding with '{resolved_song_name}' but result may be incorrect."
            )
        
        # Search and play the resolved song
        result = spotify.search_and_play(resolved_song_name, resolved_artist)
        
        if result.get("success"):
            # Enhance message with disambiguation info if confidence was low
            message = result.get("message", f"Now playing: {resolved_song_name}")
            if confidence < 0.7:
                if disambiguation_result.get("reasoning"):
                    message += f" (resolved from '{song_name}')"
                else:
                    message += f" (searched for '{song_name}')"
            
            return {
                "success": True,
                "action": "play_song",
                "song_name": resolved_song_name,
                "artist": resolved_artist or result.get("track_artist"),
                "status": "playing",
                "message": message,
                "track": result.get("track", resolved_song_name),
                "track_artist": result.get("track_artist", resolved_artist),
                "disambiguation": {
                    "original": song_name,
                    "resolved": resolved_song_name,
                    "confidence": confidence,
                    "reasoning": disambiguation_result.get("reasoning", ""),
                    "alternatives": disambiguation_result.get("alternatives", [])
                }
            }
        else:
            # Try to extract and use alternative matches from error message
            error_result = result.copy()
            error_msg = error_result.get("error_message", "Unknown error")
            
            # Extract alternative matches from error message using ErrorAnalyzer
            alternatives_to_try = []
            try:
                from .error_analyzer import ErrorAnalyzer
                error_analyzer = ErrorAnalyzer(config)
                
                analysis = error_analyzer.analyze_error(
                    tool_name="play_song",
                    parameters={"song_name": resolved_song_name, "artist": resolved_artist},
                    error_type=error_result.get("error_type", "SearchError"),
                    error_message=error_msg,
                    attempt_number=1,
                    context={"original_request": song_name, "disambiguation": disambiguation_result}
                )
                
                extracted_alternatives = analysis.get("extracted_alternatives", [])
                if extracted_alternatives:
                    logger.info(f"[SPOTIFY AGENT] Extracted alternatives from error: {extracted_alternatives}")
                    alternatives_to_try = extracted_alternatives
            except Exception as e:
                logger.warning(f"[SPOTIFY AGENT] Failed to extract alternatives using ErrorAnalyzer: {e}")
            
            # Also check disambiguation alternatives
            disambiguation_alternatives = disambiguation_result.get("alternatives", [])
            if disambiguation_alternatives and not alternatives_to_try:
                alternatives_to_try = [
                    f"{alt.get('song_name')} by {alt.get('artist', 'Unknown')}"
                    for alt in disambiguation_alternatives[:2]
                ]
            
            # Try alternatives if available and error suggests it might help
            if alternatives_to_try and error_result.get("retry_possible", True):
                logger.info(f"[SPOTIFY AGENT] Attempting to play alternatives: {alternatives_to_try}")
                
                for alt_match in alternatives_to_try[:2]:  # Try up to 2 alternatives
                    try:
                        # Parse alternative match (format: "Song Name by Artist" or just "Song Name")
                        if " by " in alt_match:
                            alt_parts = alt_match.split(" by ", 1)
                            alt_song = alt_parts[0].strip()
                            alt_artist = alt_parts[1].strip() if len(alt_parts) > 1 else None
                        else:
                            alt_song = alt_match.strip()
                            alt_artist = None
                        
                        logger.info(f"[SPOTIFY AGENT] Trying alternative: '{alt_song}' by {alt_artist or 'Unknown'}")
                        alt_result = spotify.search_and_play(alt_song, alt_artist)
                        
                        if alt_result.get("success"):
                            logger.info(f"[SPOTIFY AGENT] Alternative match succeeded: {alt_song}")
                            return {
                                "success": True,
                                "action": "play_song",
                                "song_name": alt_song,
                                "artist": alt_artist or alt_result.get("track_artist"),
                                "status": "playing",
                                "message": f"Playing alternative match: {alt_result.get('message', f'{alt_song}')}",
                                "track": alt_result.get("track", alt_song),
                                "track_artist": alt_result.get("track_artist", alt_artist),
                                "disambiguation": {
                                    "original": song_name,
                                    "resolved": alt_song,
                                    "confidence": 0.7,  # Lower confidence since it's an alternative
                                    "reasoning": f"Original '{resolved_song_name}' failed, tried alternative match",
                                    "alternatives": []
                                },
                                "used_alternative": True
                            }
                    except Exception as alt_error:
                        logger.warning(f"[SPOTIFY AGENT] Alternative '{alt_match}' also failed: {alt_error}")
                        continue
            
            # All attempts failed, return error with enhanced message
            if confidence < LOW_CONFIDENCE_THRESHOLD:
                error_msg += f" (Note: '{song_name}' was resolved to '{resolved_song_name}' with low confidence)"
            
            if alternatives_to_try:
                alt_list = ", ".join(alternatives_to_try[:3])
                error_msg += f" Tried alternatives: {alt_list}"
            elif disambiguation_alternatives:
                alt_list = ", ".join([f"{alt.get('song_name')} by {alt.get('artist', 'Unknown')}" for alt in disambiguation_alternatives[:3]])
                error_msg += f" Alternative matches: {alt_list}"
            
            error_result["error_message"] = error_msg
            error_result["disambiguation"] = {
                "original": song_name,
                "resolved": resolved_song_name,
                "confidence": confidence,
                "reasoning": disambiguation_result.get("reasoning", ""),
                "alternatives_tried": alternatives_to_try
            }
            return error_result

    except Exception as e:
        logger.error(f"[SPOTIFY AGENT] Error in play_song: {e}")
        return {
            "error": True,
            "error_type": "SpotifyError",
            "error_message": f"Failed to play song: {str(e)}",
            "retry_possible": True
        }


# Tool exports
SPOTIFY_AGENT_TOOLS = [play_music, pause_music, get_spotify_status, play_song]

# Agent hierarchy documentation
SPOTIFY_AGENT_HIERARCHY = """
SPOTIFY AGENT (4 tools)
Domain: Music playback control
└─ Tools:
   ├─ play_music - Start/resume music playback
   ├─ pause_music - Pause music playback
   ├─ get_spotify_status - Get current playback status and track info
   └─ play_song - Play a specific song by name (with LLM-powered semantic understanding)
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
            "play_song": play_song,
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

