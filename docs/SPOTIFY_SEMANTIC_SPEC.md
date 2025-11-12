# Spotify Semantic Song Search - Technical Specification

## Overview
This document specifies the implementation details for LLM-powered semantic song name disambiguation and playback in Spotify.

## 1. AppleScript Search Flow

### Exact Script Implementation

```applescript
tell application "Spotify"
    activate
    try
        open location "spotify:search:{search_query}"
        delay 1.5
        play
    on error errMsg
        return "ERROR: " & errMsg
    end try
end tell
```

### Flow Steps
1. **Activate Spotify**: Opens Spotify if closed (no error if already open)
2. **Search URI**: Uses `spotify:search:{query}` to open search results
3. **Wait**: 1.5 second delay for search results to load
4. **Play**: Plays first result from search
5. **Error Handling**: Catches AppleScript errors and returns error message

### Fallbacks
- **Spotify not installed**: AppleScript error → Returns `SpotifyNotRunning` error
- **Spotify not running**: `activate` may fail → Returns `SpotifyNotRunning` error  
- **Zero search results**: Play command may fail → Returns `SongNotFound` error
- **Network issues**: Search may timeout → Returns `SearchError` with timeout message

### Search Query Formatting
- Combine song_name + artist if artist provided: `"{song_name} {artist}"`
- Remove non-ASCII characters that might break URI encoding
- No URL encoding needed (AppleScript handles it)

## 2. Disambiguator Contract

### Input Requirements
- **Type**: `str`
- **Non-empty**: Must contain at least one non-whitespace character
- **Encoding**: UTF-8 (preserves non-ASCII characters)

### Output Contract

```python
{
    "song_name": str,        # Required, non-empty after cleaning
    "artist": str | None,    # None if unknown/unresolved
    "confidence": float,     # 0.0-1.0, clamped to valid range
    "reasoning": str,        # Non-empty explanation string
    "alternatives": List[Dict[str, str]]  # Empty list if no alternatives
}
```

### Validation Rules
1. **song_name**: Must be non-empty string after disambiguation
   - If LLM returns empty: Falls back to cleaned input
   - If cleaned input is empty: Returns error
2. **confidence**: Must be float in range [0.0, 1.0]
   - Values outside range are clamped
   - < 0.5: Low confidence, caller should consider fallback
   - >= 0.5: Acceptable confidence
   - >= 0.8: High confidence
3. **artist**: 
   - Can be `None` if unknown
   - If provided, must be non-empty string
4. **reasoning**: Always present (default: "No specific reasoning provided")

### Fallback Behavior
- **LLM API failure**: Returns cleaned input with confidence 0.3
- **Invalid JSON response**: Returns cleaned input with confidence 0.3
- **Empty song_name**: Uses cleaned input as fallback
- **Exception during disambiguation**: Returns cleaned input with error field

### Non-ASCII Handling
- Input preserved as-is (no encoding conversion)
- Output may contain non-ASCII characters
- Caller (`search_and_play`) removes non-ASCII before Spotify search URI

## 3. Slash Command Routing

### Routing Priority (in order)

1. **Pause/Stop** → `pause_music`
   - Pattern: `^(pause|stop)$` (exact match, case-insensitive)
   - Examples: `/spotify pause`, `/spotify stop`

2. **Status** → `get_spotify_status`
   - Keywords: "status", "what", "current", "playing"
   - Examples: `/spotify status`, `/spotify what's playing`

3. **Song Play** → `play_song`
   - Pattern: Contains "play"/"start"/"resume" + content after keyword
   - Song name extraction:
     - Find play keyword position
     - Extract text after keyword
     - Remove natural language prefixes: "that song called", "the song", "song", "track"
     - If remaining text length > 2: Route to `play_song`
   - Examples:
     - `/spotify play Viva la Vida` → `{"song_name": "Viva la Vida"}`
     - `/spotify play Viva la something` → `{"song_name": "Viva la something"}`
     - `/spotify play that song called Viva la something` → `{"song_name": "Viva la something"}`

4. **Simple Play** → `play_music`
   - Pattern: Contains "play"/"start"/"resume" but no song name
   - Examples: `/spotify play`, `/spotify start`

5. **Default** → `play_music`
   - Fallback for unrecognized commands

### Regex Patterns

```python
# Pause/Stop (exact match)
pause_pattern = re.match(r'^(pause|stop)$', task_lower)

# Status (contains keyword)
status_keywords = ["status", "what", "current", "playing"]

# Play keyword detection
play_match = re.search(r'\b(play|start|resume)\b', task_lower)

# Natural language prefix removal
natural_lang_patterns = [
    r"^that\s+song\s+called\s+",
    r"^the\s+song\s+",
    r"^song\s+",
    r"^track\s+",
]
```

## 4. Error Messages

### Required Error Strings

1. **Spotify Not Running**
   ```
   "Spotify is not running. Please open Spotify and try again."
   ```
   - Error type: `SpotifyNotRunning`
   - Retry possible: `True`

2. **Song Not Found**
   ```
   "Could not find '{song_name}' in Spotify. Please check the spelling or try a different search."
   ```
   - Error type: `SongNotFound`
   - Retry possible: `True`
   - Includes song name in message

3. **Ambiguous Results** (Low Confidence)
   ```
   "Found '{resolved_name}' but confidence is low. Alternative matches: {alternatives}"
   ```
   - Shown in success message, not error
   - Includes alternatives if available

4. **Validation Error**
   ```
   "Song name cannot be empty"
   ```
   - Error type: `ValidationError`
   - Retry possible: `False`

5. **Search Error** (Generic)
   ```
   "Could not play '{song_name}'. Error: {error_msg}. Please make sure Spotify is running and the song exists."
   ```
   - Error type: `SearchError`
   - Retry possible: `True`

### Error Propagation
- Errors flow: `SpotifyAutomation` → `play_song` tool → `SlashCommandHandler` → UI
- All errors include `error_type` and `error_message` fields
- UI should display `error_message` to user

## 5. Return Payload Structure

### `search_and_play()` Return Shape

```python
{
    # Success case
    "success": True,
    "action": "play_song",
    "song_name": str,           # Original requested name
    "artist": str | None,       # Artist if provided
    "status": "playing",
    "message": str,             # User-friendly message
    "track": str,               # Actual track name playing
    "track_artist": str,        # Actual artist playing
    
    # Error case
    "success": False,
    "error": True,
    "error_type": str,          # "SpotifyNotRunning" | "SongNotFound" | "SearchError" | "ValidationError"
    "error_message": str,       # User-friendly error message
    "retry_possible": bool
}
```

### `play_song()` Tool Return Shape

```python
{
    # Success case
    "success": True,
    "action": "play_song",
    "song_name": str,           # Resolved song name
    "artist": str | None,       # Resolved artist
    "status": "playing",
    "message": str,             # Includes disambiguation info if low confidence
    "track": str,               # Actual track playing
    "track_artist": str,        # Actual artist playing
    "disambiguation": {
        "original": str,        # Original fuzzy input
        "resolved": str,        # Resolved canonical name
        "confidence": float,    # 0.0-1.0
        "reasoning": str,       # LLM reasoning
        "alternatives": List[Dict]  # Alternative matches
    },
    
    # Error case
    "error": True,
    "error_type": str,
    "error_message": str,       # Enhanced with disambiguation context
    "retry_possible": bool,
    "disambiguation": {         # Included even on error
        "original": str,
        "resolved": str,
        "confidence": float,
        "reasoning": str
    }
}
```

## 6. Rate Limiting & Caching

### Caching Strategy
- **No caching implemented** (LLM responses may vary)
- **Future consideration**: Cache disambiguation results per session
  - Key: `(fuzzy_name, session_id)`
  - TTL: Session duration
  - Invalidate on session clear

### Rate Limiting
- **No rate limiting** (relies on OpenAI API rate limits)
- **Future consideration**: 
  - Max 10 disambiguation calls per minute per user
  - Exponential backoff on 429 errors

### Retry Policy
- **No automatic retries** for disambiguation failures
- **Fallback**: Returns cleaned input with low confidence
- **User can retry**: Error messages include `retry_possible: True`

## 7. Integration Touchpoints

### Tool Registration
- Tool: `play_song` in `src/agent/spotify_agent.py`
- Decorator: `@tool` from `langchain_core.tools`
- Export: Added to `SPOTIFY_AGENT_TOOLS` list
- Registry: Automatically included in `ALL_AGENT_TOOLS` via import

### Agent Execution
- Tool executed via `SpotifyAgent.execute(tool_name, parameters)`
- Called from `SlashCommandHandler._execute_agent_task()`
- Routing: `_route_spotify_command()` determines tool and params

### LLM Integration
- `SongDisambiguator` uses OpenAI API (same config as other LLM calls)
- Model: From `config.yaml` → `openai.model` (default: "gpt-4o")
- Temperature: 0.3 for older models, default (1) for o-series models
- Max tokens: From config (default: 2000, clamped to 500 for disambiguation)

## 8. Testing Strategy

### Unit Tests (Mocked)
- **SongDisambiguator**: Mock OpenAI API responses
  - Test exact matches, fuzzy matches, misspellings
  - Test validation and fallback behavior
  - Test confidence thresholds

- **Slash Command Routing**: Test regex patterns
  - Test all routing priorities
  - Test song name extraction
  - Test natural language parsing

- **SpotifyAutomation**: Mock AppleScript execution
  - Test success cases
  - Test error cases (not running, not found, timeout)
  - Test search query formatting

### Integration Tests (Partial Mock)
- **End-to-End Flow**: Mock LLM, real routing
  - Test command → routing → tool selection
  - Verify parameters passed correctly
  - Test error propagation

### Manual Tests (Real Spotify)
- **Requires Spotify running**
- Test actual song playback
- Test disambiguation accuracy
- Test error handling with real failures

### Test File Structure
- `tests/test_spotify_semantic.py`: Comprehensive test suite
  - Test Suite 1: Song Disambiguator (LLM semantic understanding)
  - Test Suite 2: Slash Command Routing
  - Test Suite 3: End-to-End (documented, requires Spotify)

## 9. Future Enhancements

### Potential Improvements
1. **Caching**: Cache disambiguation results per session
2. **User Confirmation**: Prompt user when confidence < 0.5
3. **Alternative Selection**: Show alternatives when ambiguous
4. **Playlist Support**: Search within user's playlists
5. **Recent History**: Remember recently played songs
6. **Voice Integration**: Handle voice input for song names

