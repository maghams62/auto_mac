"""
Spotify Agent - Controls Spotify playback on macOS.

This agent is responsible for:
- Playing music in Spotify
- Pausing music in Spotify
- Getting playback status

Uses AppleScript to control the Spotify desktop app.
"""

from typing import Dict, Any, Optional, List
from langchain_core.tools import tool
import logging
from datetime import datetime
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
        from ..integrations.spotify_playback_service import SpotifyPlaybackService
        from ..utils import load_config

        config = load_config()
        service = SpotifyPlaybackService(config)

        result = service.play()
        return result.to_dict()

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
        from ..integrations.spotify_playback_service import SpotifyPlaybackService
        from ..utils import load_config

        config = load_config()
        service = SpotifyPlaybackService(config)

        result = service.pause()
        return result.to_dict()

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
        from ..integrations.spotify_playback_service import SpotifyPlaybackService
        from ..utils import load_config

        config = load_config()
        service = SpotifyPlaybackService(config)

        result = service.get_status()
        return result.to_dict()

    except Exception as e:
        logger.error(f"[SPOTIFY AGENT] Error in get_spotify_status: {e}")
        return {
            "error": True,
            "error_type": "SpotifyError",
            "error_message": f"Failed to get Spotify status: {str(e)}",
            "retry_possible": True
        }


@tool
def play_song(song_name: str, reasoning_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Play a specific song by name in Spotify using API-first playback.

    This tool uses LLM-powered semantic understanding to resolve song queries
    and plays them via Spotify Web API (no mac automation scripts).

    Handles diverse queries like:
    - "play that song where michael jackson does the moonwalk" → "Smooth Criminal"
    - "play breaking the" → "Breaking the Habit"
    - "play that new taylor swift song" → recent popular release

    Args:
        song_name: The song query (may be fuzzy, partial, descriptive, or imprecise)
        reasoning_context: Optional memory context for learning from past attempts

    Returns:
        Dictionary with success status, song info, and message
    """
    logger.info(f"[SPOTIFY AGENT] Tool: play_song('{song_name}')")

    # Check memory context for learning from past attempts
    if reasoning_context:
        past_attempts = reasoning_context.get("past_attempts", 0)
        commitments = reasoning_context.get("commitments", [])
        logger.debug(f"[SPOTIFY AGENT] Memory context: {past_attempts} past attempts, commitments: {commitments}")

        # If we've tried before and had failures, be more conservative
        if past_attempts > 0 and any("play_music" in str(c) for c in commitments):
            logger.info(f"[SPOTIFY AGENT] Learning from {past_attempts} past attempts")

    try:
        from ..llm import SongDisambiguator
        from ..integrations.spotify_playback_service import SpotifyPlaybackService
        from ..utils import load_config

        config = load_config()

        # Step 1: Disambiguate the song query using LLM
        logger.info(f"[SPOTIFY AGENT] Disambiguating song query: '{song_name}'")
        disambiguator = SongDisambiguator(config)
        disambiguation_result = disambiguator.disambiguate(song_name, reasoning_context)

        resolved_song_name = disambiguation_result.get("song_name", song_name)
        resolved_artist = disambiguation_result.get("artist")
        confidence = disambiguation_result.get("confidence", 0.5)
        alternatives = disambiguation_result.get("alternatives", [])
        reasoning_text = disambiguation_result.get("reasoning", "")

        logger.info(
            f"[SPOTIFY AGENT] Disambiguated '{song_name}' → '{resolved_song_name}' "
            f"by {resolved_artist or 'Unknown'} (confidence: {confidence:.2f})"
        )

        # Step 2: Check for ambiguity and decide whether to clarify with user
        logger.info(f"[SPOTIFY AGENT] Checking ambiguity for clarification decision")
        ambiguity_decision = disambiguator.check_ambiguity_and_decide(
            disambiguation_result, reasoning_context
        )

        should_clarify = ambiguity_decision.get("should_clarify", False)
        adjusted_confidence = ambiguity_decision.get("confidence", confidence)
        decision_reasoning = ambiguity_decision.get("reasoning", "")
        risk_factors = ambiguity_decision.get("risk_factors", [])

        logger.info(
            f"[SPOTIFY AGENT] Ambiguity decision: clarify={should_clarify}, "
            f"adjusted_confidence={adjusted_confidence:.2f}, risk_factors={len(risk_factors)}"
        )

        # If we need clarification, return a special result that triggers user clarification
        if should_clarify:
            clarification_options = []
            if alternatives:
                # Include the top suggestion plus alternatives
                clarification_options.append({
                    "song_name": resolved_song_name,
                    "artist": resolved_artist,
                    "confidence": adjusted_confidence,
                    "primary": True
                })
                for alt in alternatives[:3]:  # Limit to 3 alternatives
                    clarification_options.append({
                        "song_name": alt.get("song_name"),
                        "artist": alt.get("artist"),
                        "confidence": 0.5,  # Lower confidence for alternatives
                        "primary": False
                    })

            clarification_result = {
                "error": True,
                "error_type": "AmbiguousSongRequest",
                "error_message": f"I'm not confident about which song you mean. {decision_reasoning}",
                "clarification_needed": True,
                "clarification_options": clarification_options,
                "disambiguation": {
                    "original": song_name,
                    "resolved": resolved_song_name,
                    "confidence": adjusted_confidence,
                    "reasoning": reasoning_text,
                    "alternatives": alternatives,
                    "ambiguous": True,
                    "needed_clarification": True,
                    "decision_reasoning": decision_reasoning,
                    "risk_factors": risk_factors
                },
                "_disambiguation_metadata": {
                    "original_query": song_name,
                    "resolved_song": resolved_song_name,
                    "resolved_artist": resolved_artist,
                    "confidence": adjusted_confidence,
                    "reasoning": reasoning_text,
                    "candidates_count": len(alternatives),
                    "alternatives": alternatives[:3],
                    "ambiguous": True,
                    "needs_clarification": True,
                    "decision_reasoning": decision_reasoning,
                    "risk_factors": risk_factors,
                    "clarification_requested": True
                }
            }
            return clarification_result

        # Instrument reasoning data for disambiguation attempts
        if reasoning_context and "trace_enabled" in reasoning_context and reasoning_context["trace_enabled"]:
            # Add disambiguation details to reasoning trace
            disambiguation_metadata = {
                "original_query": song_name,
                "resolved_song": resolved_song_name,
                "resolved_artist": resolved_artist,
                "confidence": adjusted_confidence,
                "reasoning": reasoning_text,
                "candidates_count": len(alternatives),
                "alternatives": alternatives[:3],  # Limit to top 3
                "ambiguous": confidence < 0.8 or len(alternatives) > 1,
                "needs_clarification": False,  # We passed the ambiguity check
                "decision_reasoning": decision_reasoning,
                "risk_factors": risk_factors
            }

            # Note: The reasoning context update will happen in the agent.py execution loop
            # We prepare the metadata here for later use

        # Step 3: Use unified playback service (API-first)
        logger.info(f"[SPOTIFY AGENT] Playing via API-first playback service")
        service = SpotifyPlaybackService(config)
        result = service.play_track(resolved_song_name, resolved_artist)

        if result.success:
            # Success - return enriched result
            message = result.message or f"Now playing: {resolved_song_name}"
            if confidence < 0.8:
                message += f" (resolved from '{song_name}')"

            success_result = {
                "success": True,
                "action": "play_song",
                "song_name": resolved_song_name,
                "artist": resolved_artist or result.artist,
                "status": "playing",
                "message": message,
                "track": result.track or resolved_song_name,
                "track_artist": result.artist or resolved_artist,
                "backend": result.backend.value if result.backend else None,
                "disambiguation": {
                    "original": song_name,
                    "resolved": resolved_song_name,
                    "confidence": confidence,
                    "reasoning": disambiguation_result.get("reasoning", ""),
                    "alternatives": disambiguation_result.get("alternatives", []),
                    "ambiguous": confidence < 0.8 or len(disambiguation_result.get("alternatives", [])) > 1,
                    "needed_clarification": confidence < 0.7
                }
            }

            # Add disambiguation metadata to result for reasoning trace capture
            if reasoning_context and "trace_enabled" in reasoning_context and reasoning_context["trace_enabled"]:
                success_result["_disambiguation_metadata"] = disambiguation_metadata

            return success_result
        else:
            # Handle failure with specific error types
            error_msg = result.error_message

            # For "SongNotFound" errors, include disambiguation alternatives
            if result.error_type == "SongNotFound" and disambiguation_result.get("alternatives"):
                alternatives = disambiguation_result["alternatives"]
                alt_text = ", ".join([f"{alt.get('song_name')} by {alt.get('artist', 'Unknown')}"
                                    for alt in alternatives[:3]])
                error_msg += f" Alternative matches: {alt_text}"

            failure_result = {
                "error": True,
                "error_type": result.error_type,
                "error_message": error_msg,
                "retry_possible": result.retry_possible,
                "disambiguation": {
                    "original": song_name,
                    "resolved": resolved_song_name,
                    "confidence": confidence,
                    "reasoning": disambiguation_result.get("reasoning", ""),
                    "alternatives": disambiguation_result.get("alternatives", []),
                    "ambiguous": confidence < 0.8 or len(disambiguation_result.get("alternatives", [])) > 1,
                    "needed_clarification": confidence < 0.7
                }
            }

            # Add disambiguation metadata to result for reasoning trace capture
            if reasoning_context and "trace_enabled" in reasoning_context and reasoning_context["trace_enabled"]:
                failure_result["_disambiguation_metadata"] = disambiguation_metadata

            return failure_result

    except Exception as e:
        logger.error(f"[SPOTIFY AGENT] Error in play_song: {e}")
        return {
            "error": True,
            "error_type": "SpotifyError",
            "error_message": f"Failed to play song: {str(e)}",
            "retry_possible": True
        }


@tool
def clarify_song_selection(clarification_options: List[Dict[str, Any]], original_query: str) -> Dict[str, Any]:
    """
    Present song clarification options to the user and collect their choice.

    This tool is used when the agent is uncertain about which song the user wants
    and needs to present options for clarification.

    Args:
        clarification_options: List of song options with metadata
        original_query: The user's original ambiguous query

    Returns:
        Dictionary with clarification result
    """
    logger.info(f"[SPOTIFY AGENT] Clarifying song selection for: '{original_query}'")

    try:
        # Format options for user presentation
        options_text = []
        for i, option in enumerate(clarification_options, 1):
            song_name = option.get("song_name", "Unknown")
            artist = option.get("artist", "Unknown Artist")
            confidence = option.get("confidence", 0.5)
            primary = option.get("primary", False)

            marker = " (recommended)" if primary else ""
            confidence_indicator = f" ({confidence:.1%} confidence)" if confidence < 0.8 else ""
            options_text.append(f"{i}. '{song_name}' by {artist}{marker}{confidence_indicator}")

        options_list = "\n".join(options_text)

        clarification_message = f"""I'm not sure which song you mean by "{original_query}". Here are the options I found:

{options_list}

Which one would you like me to play? Please reply with just the number (1, 2, 3, etc.) or tell me the song name if you see a different option."""

        return {
            "success": True,
            "action": "clarify_song_selection",
            "message": clarification_message,
            "clarification_options": clarification_options,
            "original_query": original_query,
            "awaiting_user_choice": True,
            "status": "clarification_needed"
        }

    except Exception as e:
        logger.error(f"[SPOTIFY AGENT] Error in clarify_song_selection: {e}")
        return {
            "error": True,
            "error_type": "ClarificationError",
            "error_message": f"Failed to generate clarification options: {str(e)}",
            "retry_possible": True
        }


@tool
def process_clarification_response(user_response: str, clarification_options: List[Dict[str, Any]], original_query: str, reasoning_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Process user's clarification response and resolve to a specific song choice.

    This tool interprets the user's response to a clarification request and
    determines which song they selected.

    Args:
        user_response: The user's response to the clarification (number, song name, etc.)
        clarification_options: The original clarification options presented
        original_query: The original ambiguous query
        reasoning_context: Optional context for learning from clarification

    Returns:
        Dictionary with resolved song choice or error
    """
    logger.info(f"[SPOTIFY AGENT] Processing clarification response: '{user_response}'")

    try:
        # Clean up user response
        response = user_response.strip().lower()

        # Try to parse as a number first
        selected_option = None
        try:
            option_number = int(response) - 1  # Convert to 0-based index
            if 0 <= option_number < len(clarification_options):
                selected_option = clarification_options[option_number]
                logger.info(f"[SPOTIFY AGENT] User selected option {option_number + 1}: {selected_option}")
        except ValueError:
            pass  # Not a number, try other parsing

        # If not a number, try to match against song names or artists
        if not selected_option:
            for option in clarification_options:
                song_name = option.get("song_name", "").lower()
                artist = option.get("artist", "").lower()

                # Check if response contains the song name or artist
                if (song_name in response or
                    response in song_name or
                    artist in response or
                    response in artist):
                    selected_option = option
                    logger.info(f"[SPOTIFY AGENT] User selected by name match: {selected_option}")
                    break

        if not selected_option:
            return {
                "error": True,
                "error_type": "InvalidClarificationResponse",
                "error_message": f"I couldn't understand your selection '{user_response}'. Please reply with a number (1, 2, 3, etc.) or the song name.",
                "retry_possible": True,
                "clarification_options": clarification_options,
                "original_query": original_query
            }

        # Store the clarification in context for future learning
        clarification_data = {
            "original_query": original_query,
            "user_response": user_response,
            "resolved_song": selected_option.get("song_name"),
            "resolved_artist": selected_option.get("artist"),
            "clarification_timestamp": datetime.now().isoformat(),
            "options_presented": len(clarification_options)
        }

        # Also store in session context for cross-interaction learning
        try:
            from ..memory.session_manager import SessionManager
            from ..utils import load_config

            config = load_config()
            session_manager = SessionManager(config=config)

            # Get current session (this assumes we have session context available)
            # In practice, this would be passed through reasoning_context
            if reasoning_context and "interaction_id" in reasoning_context:
                # We can't easily get the session manager here, so we'll prepare the data
                # for the agent to store it in the reasoning trace update
                pass

        except Exception as e:
            logger.debug(f"[SPOTIFY AGENT] Could not store clarification in session context: {e}")

        return {
            "success": True,
            "action": "process_clarification_response",
            "message": f"Got it! Playing '{selected_option.get('song_name')}' by {selected_option.get('artist')}.",
            "resolved_choice": selected_option,
            "original_query": original_query,
            "user_response": user_response,
            "ready_for_playback": True,
            "clarification_data": clarification_data if 'clarification_data' in locals() else None
        }

    except Exception as e:
        logger.error(f"[SPOTIFY AGENT] Error in process_clarification_response: {e}")
        return {
            "error": True,
            "error_type": "ClarificationProcessingError",
            "error_message": f"Failed to process your response: {str(e)}",
            "retry_possible": True
        }


@tool
def play_album(album_name: str) -> Dict[str, Any]:
    """
    Play a specific album by name in Spotify using API-first playback.

    Args:
        album_name: The album name to search for and play (may be fuzzy or partial)

    Returns:
        Dictionary with success status and album info
    """
    logger.info(f"[SPOTIFY AGENT] Tool: play_album('{album_name}')")

    try:
        from ..integrations.spotify_playback_service import SpotifyPlaybackService
        from ..utils import load_config

        config = load_config()
        service = SpotifyPlaybackService(config)

        result = service.play_album(album_name)
        return result.to_dict()

    except Exception as e:
        logger.error(f"[SPOTIFY AGENT] Error in play_album: {e}")
        return {
            "error": True,
            "error_type": "SpotifyError",
            "error_message": f"Failed to play album: {str(e)}",
            "retry_possible": True
        }


@tool
def play_artist(artist_name: str) -> Dict[str, Any]:
    """
    Play an artist's top tracks in Spotify using API-first playback.

    Args:
        artist_name: The artist name to search for and play

    Returns:
        Dictionary with success status and artist info
    """
    logger.info(f"[SPOTIFY AGENT] Tool: play_artist('{artist_name}')")

    try:
        from ..integrations.spotify_playback_service import SpotifyPlaybackService
        from ..utils import load_config

        config = load_config()
        service = SpotifyPlaybackService(config)

        result = service.play_artist(artist_name)
        return result.to_dict()

    except Exception as e:
        logger.error(f"[SPOTIFY AGENT] Error in play_artist: {e}")
        return {
            "error": True,
            "error_type": "SpotifyError",
            "error_message": f"Failed to play artist: {str(e)}",
            "retry_possible": True
        }


# Tool exports
SPOTIFY_AGENT_TOOLS = [play_music, pause_music, get_spotify_status, play_song, play_album, play_artist]

# Agent hierarchy documentation
SPOTIFY_AGENT_HIERARCHY = """
SPOTIFY AGENT (6 tools)
Domain: Music playback control
└─ Tools:
   ├─ play_music - Start/resume music playback
   ├─ pause_music - Pause music playback
   ├─ get_spotify_status - Get current playback status and track info
   ├─ play_song - Play a specific song by name (with LLM-powered semantic understanding)
   ├─ play_album - Play a specific album by name
   └─ play_artist - Play an artist's top tracks
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
            "play_album": play_album,
            "play_artist": play_artist,
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

