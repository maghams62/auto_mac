"""
LLM-powered song name disambiguation service.

Uses OpenAI to resolve fuzzy/imprecise song names to canonical titles.
"""

import json
import logging
import re
from typing import Dict, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

SONG_DISAMBIGUATION_SYSTEM_PROMPT = """You are a music knowledge expert specializing in identifying songs from any type of query - full names, vague references, descriptive queries, or partial descriptions.

Your job is to resolve ANY song query to its canonical title and artist using your extensive knowledge of popular music across all genres and time periods.

QUERY TYPES YOU MUST HANDLE:

1. **Full Song Names**: Extract complete song names from natural language
   - "play a song called breaking the habit" → "Breaking the Habit" by Linkin Park
   - "song called space song" → "Space Song" by Beach House

2. **Vague References**: Identify songs from minimal context
   - "the space song" → "Space Song" by Beach House
   - "that hello song" → "Hello" by Adele (with alternatives)

3. **Descriptive Queries**: Identify songs from actions, characteristics, lyrics, or visual descriptions
   - "that song by Michael Jackson where he move like he moonwalks" → "Smooth Criminal"
   - "song where he dances backwards" → "Smooth Criminal" by Michael Jackson
   - "song with the guitar solo" (context-dependent)

4. **Partial Descriptions**: Identify songs from incomplete information with artist hints
   - "song that starts with space by Eminem" → "Space Bound" by Eminem
   - "that song that's something around it's it starts with space by Eminem" → "Space Bound"
   - "song with 'breaking' in the title by Linkin Park" → "Breaking the Habit"

GUIDELINES:
- Use your music knowledge to identify songs from ANY description
- For descriptive queries, think about famous songs, iconic moments, lyrics, or characteristics
- Extract full song names from phrases like "a song called X" or "song called X"
- Preserve artist hints when provided (e.g., "by Eminem", "by Michael Jackson")
- Return high confidence (0.9+) for well-known songs with clear matches
- Return moderate confidence (0.7-0.9) for descriptive queries that match iconic songs
- Return lower confidence (0.5-0.7) for ambiguous queries and provide alternatives
- Always provide reasoning explaining how you identified the song

Always respond with valid JSON only."""

SONG_DISAMBIGUATION_PROMPT = """Resolve this song query to its canonical title and artist:

Query: "{fuzzy_name}"

Respond with a JSON object:
{{
  "song_name": "canonical song title",
  "artist": "artist name",
  "confidence": 0.0-1.0,
  "reasoning": "detailed explanation of how you identified this song",
  "alternatives": [
    {{"song_name": "alternative 1", "artist": "artist 1"}},
    {{"song_name": "alternative 2", "artist": "artist 2"}}
  ]
}}

EXAMPLES BY QUERY TYPE:

1. FULL SONG NAME:
Input: "play a song called breaking the habit on Spotify"
Response:
{{
  "song_name": "Breaking the Habit",
  "artist": "Linkin Park",
  "confidence": 0.95,
  "reasoning": "Extracted full song name 'Breaking the Habit' from natural language phrase. This is a well-known Linkin Park song from their Meteora album.",
  "alternatives": []
}}

2. VAGUE REFERENCE:
Input: "the space song"
Response:
{{
  "song_name": "Space Song",
  "artist": "Beach House",
  "confidence": 0.85,
  "reasoning": "The phrase 'the space song' most commonly refers to 'Space Song' by Beach House, a popular indie track known for its dreamy, space-themed atmosphere.",
  "alternatives": [
    {{"song_name": "Space Oddity", "artist": "David Bowie"}},
    {{"song_name": "Space Bound", "artist": "Eminem"}}
  ]
}}

3. DESCRIPTIVE QUERY:
Input: "play that song by Michael Jackson where he move like he moonwalks"
Response:
{{
  "song_name": "Smooth Criminal",
  "artist": "Michael Jackson",
  "confidence": 0.90,
  "reasoning": "Michael Jackson's iconic moonwalk dance move is most famously associated with 'Smooth Criminal' from the Bad album. The song features his signature lean and moonwalk choreography.",
  "alternatives": [
    {{"song_name": "Billie Jean", "artist": "Michael Jackson"}}
  ]
}}

4. PARTIAL DESCRIPTION WITH ARTIST:
Input: "play that song that's something around it's it starts with space by Eminem"
Response:
{{
  "song_name": "Space Bound",
  "artist": "Eminem",
  "confidence": 0.85,
  "reasoning": "User describes a song by Eminem that starts with 'space'. 'Space Bound' is Eminem's song from the Recovery album that matches this description.",
  "alternatives": []
}}

5. AMBIGUOUS QUERY:
Input: "that hello song"
Response:
{{
  "song_name": "Hello",
  "artist": "Adele",
  "confidence": 0.80,
  "reasoning": "Most popular 'Hello' song in recent years is by Adele (2015), though there are other famous versions.",
  "alternatives": [
    {{"song_name": "Hello", "artist": "Lionel Richie"}},
    {{"song_name": "Hello", "artist": "Evanescence"}}
  ]
}}

6. PARTIAL WITH CORRECTION:
Input: "Viva la something"
Response:
{{
  "song_name": "Viva la Vida",
  "artist": "Coldplay",
  "confidence": 0.95,
  "reasoning": "User likely refers to the famous Coldplay song 'Viva la Vida' from their Viva la Vida or Death and All His Friends album.",
  "alternatives": []
}}

Now resolve this query: "{fuzzy_name}"

Think step by step:
1. What type of query is this? (full name, vague, descriptive, partial)
2. What clues are present? (artist hints, descriptive phrases, partial words)
3. What is the most likely song match?
4. What is your confidence level?
5. Are there alternatives that should be mentioned?

Respond with ONLY the JSON object, no additional text."""


class SongDisambiguator:
    """Use LLM to disambiguate fuzzy song names to canonical titles."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the song disambiguator.

        Args:
            config: Configuration dictionary with OpenAI settings
        """
        self.config = config
        openai_cfg = config.get("openai", {})
        self.client = OpenAI(api_key=openai_cfg.get("api_key"))
        self.model = openai_cfg.get("model", "gpt-4o")
        # Use lower temperature for more consistent disambiguation
        self.temperature = 0.3
        self.max_tokens = openai_cfg.get("max_tokens", 500)

    def disambiguate(self, fuzzy_name: str) -> Dict[str, Any]:
        """
        Resolve fuzzy song name to canonical name + artist using LLM.

        Contract:
        - Input: Non-empty string (will be cleaned of natural language phrases)
        - Output: Dictionary with required fields:
          * song_name: str (required, non-empty) - Canonical song title
          * artist: str | None - Artist name (None if unknown)
          * confidence: float (0.0-1.0) - Confidence score
          * reasoning: str - Explanation of the match
          * alternatives: List[Dict] - Alternative matches if ambiguous
        
        Validation:
        - song_name must be non-empty string after disambiguation
        - confidence must be between 0.0 and 1.0
        - If confidence < 0.5, caller should consider fallback
        
        Fallback Behavior:
        - If LLM call fails: Returns cleaned input with confidence 0.3
        - If LLM returns invalid JSON: Returns cleaned input with confidence 0.3
        - If song_name is empty after disambiguation: Uses cleaned input
        
        Non-ASCII Handling:
        - Input is cleaned but preserved (no encoding conversion)
        - Output song_name/artist may contain non-ASCII characters
        - Caller should handle encoding for Spotify search if needed

        Args:
            fuzzy_name: Fuzzy, partial, or imprecise song name
                       (e.g., "Viva la something", "that song called X")
                       Must be non-empty string

        Returns:
            Dictionary with shape:
            {
                "song_name": str,  # Required, non-empty
                "artist": str | None,
                "confidence": float,  # 0.0-1.0
                "reasoning": str,
                "alternatives": List[Dict[str, str]],  # [{"song_name": "...", "artist": "..."}]
                "error": str (optional, if fallback used)
            }
        """
        logger.info(f"[SONG DISAMBIGUATOR] Resolving fuzzy name: {fuzzy_name}")

        # Clean up the input - remove common phrases
        cleaned_name = self._clean_song_name(fuzzy_name)

        try:
            # Determine which parameters to use based on model
            # Newer models (o1, o3, o4-mini) use max_completion_tokens and don't support custom temperature
            # Older models (gpt-4o, gpt-4) use max_tokens and support temperature
            api_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SONG_DISAMBIGUATION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": SONG_DISAMBIGUATION_PROMPT.format(fuzzy_name=cleaned_name),
                    },
                ],
                "response_format": {"type": "json_object"},
            }
            
            # Check if model requires max_completion_tokens (newer models)
            if self.model.startswith("o1") or self.model.startswith("o3") or self.model.startswith("o4"):
                api_params["max_completion_tokens"] = self.max_tokens
                # o-series models don't support custom temperature, use default (1)
            else:
                api_params["max_tokens"] = self.max_tokens
                api_params["temperature"] = self.temperature
            
            response = self.client.chat.completions.create(**api_params)

            result = json.loads(response.choices[0].message.content)
            
            # Validate result structure
            if not isinstance(result, dict):
                raise ValueError("LLM response is not a dictionary")
            
            # Validate and ensure required fields
            song_name = result.get("song_name", "").strip()
            if not song_name:
                # Fallback: use cleaned input if LLM returned empty song_name
                song_name = cleaned_name
                logger.warning(f"[SONG DISAMBIGUATOR] LLM returned empty song_name, using cleaned input: {cleaned_name}")
            
            artist = result.get("artist")
            if artist:
                artist = str(artist).strip() or None
            
            confidence = float(result.get("confidence", 0.5))
            # Clamp confidence to valid range
            confidence = max(0.0, min(1.0, confidence))
            
            reasoning = str(result.get("reasoning", "No specific reasoning provided"))
            alternatives = result.get("alternatives", [])
            if not isinstance(alternatives, list):
                alternatives = []
            
            validated_result = {
                "song_name": song_name,
                "artist": artist,
                "confidence": confidence,
                "reasoning": reasoning,
                "alternatives": alternatives
            }
            
            logger.info(
                f"[SONG DISAMBIGUATOR] Resolved to: '{song_name}' by {artist or 'Unknown'} "
                f"(confidence: {confidence:.2f})"
            )
            
            # Log warning if confidence is low
            if confidence < 0.5:
                logger.warning(
                    f"[SONG DISAMBIGUATOR] Low confidence ({confidence:.2f}) for '{fuzzy_name}' → '{song_name}'. "
                    "Caller should consider fallback or user confirmation."
                )

            return validated_result

        except Exception as e:
            logger.error(f"[SONG DISAMBIGUATOR] Error disambiguating song name: {e}")
            # Fallback: return the cleaned name as-is
            return {
                "song_name": cleaned_name,
                "artist": None,
                "confidence": 0.3,
                "reasoning": f"Fallback due to disambiguation error: {str(e)}",
                "alternatives": [],
                "error": str(e),
            }

    def _clean_song_name(self, fuzzy_name: str) -> str:
        """
        Clean up song name by removing only command prefixes, preserving descriptive content.

        IMPORTANT: We preserve descriptive phrases, artist hints, and contextual clues
        because the LLM needs this information to identify songs from descriptions.

        Args:
            fuzzy_name: Raw song name input

        Returns:
            Cleaned song name with descriptive content preserved
        """
        # Only remove command/action prefixes, NOT descriptive content
        # Preserve "by Artist" hints, descriptive phrases, and contextual clues
        patterns = [
            r"^play\s+",
            r"^play\s+a\s+song\s+called\s+",
            r"^play\s+that\s+song\s+called\s+",
            r"^play\s+the\s+song\s+called\s+",
            r"^that\s+song\s+called\s+",
            r"^the\s+song\s+called\s+",
            r"^a\s+song\s+called\s+",
            r"^song\s+called\s+",
            r"^track\s+called\s+",
            # Don't remove "by Artist" - LLM needs this for identification
            # Don't remove descriptive phrases like "where he", "that starts with", etc.
        ]

        cleaned = fuzzy_name.strip()
        for pattern in patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

        # Remove trailing "on Spotify" if present (just a platform indicator)
        cleaned = re.sub(r"\s+on\s+spotify\s*$", "", cleaned, flags=re.IGNORECASE)

        return cleaned.strip()
