# Music Clarification Workflow Example

## Pattern: Ambiguous Song Request → Clarification → Resolution

When a song request is ambiguous (low confidence, multiple matches, recent failures), the agent should:
1. Present clarification options to the user
2. Wait for user response
3. Process the clarification and play the selected song
4. Store the resolution for future reference

### Example 1: Low Confidence Song Request

**User Query:** "play the hello song"

**Agent Planning:**
```json
{
  "goal": "Play the song requested by the user, seeking clarification if needed",
  "steps": [
    {
      "id": 1,
      "action": "play_song",
      "parameters": {"song_name": "the hello song"},
      "dependencies": [],
      "reasoning": "Attempt to play the requested song using semantic disambiguation",
      "expected_output": "Song starts playing or clarification request",
      "post_check": "Check if clarification_needed flag is set",
      "deliveries": []
    },
    {
      "id": 2,
      "action": "clarify_song_selection",
      "parameters": {
        "clarification_options": "$step1.disambiguation.clarification_options",
        "original_query": "the hello song"
      },
      "dependencies": [1],
      "reasoning": "Present clarification options when disambiguation confidence is low",
      "expected_output": "User sees clarification options with multiple song choices",
      "post_check": "Ensure clarification message is presented",
      "deliveries": [],
      "conditional": "step1.clarification_needed"
    }
  ],
  "complexity": "medium"
}
```

**Step 1 Result (Ambiguous):**
```json
{
  "error": true,
  "error_type": "AmbiguousSongRequest",
  "clarification_needed": true,
  "clarification_options": [
    {"song_name": "Hello", "artist": "Adele", "confidence": 0.8, "primary": true},
    {"song_name": "Hello", "artist": "Lionel Richie", "confidence": 0.6, "primary": false}
  ],
  "disambiguation": {
    "confidence": 0.65,
    "decision_reasoning": "Multiple popular 'Hello' songs exist - Adele and Lionel Richie versions are most common"
  }
}
```

**Step 2 Execution:** Agent presents clarification UI to user.

### Example 2: Processing User Clarification Response

**User Response:** "1" (or "Adele" or "the Adele one")

**Follow-up Planning:**
```json
{
  "goal": "Process user clarification and play the selected song",
  "steps": [
    {
      "id": 1,
      "action": "process_clarification_response",
      "parameters": {
        "user_response": "1",
        "clarification_options": [
          {"song_name": "Hello", "artist": "Adele", "confidence": 0.8, "primary": true},
          {"song_name": "Hello", "artist": "Lionel Richie", "confidence": 0.6, "primary": false}
        ],
        "original_query": "the hello song"
      },
      "dependencies": [],
      "reasoning": "Interpret user's clarification response and resolve to specific song choice",
      "expected_output": "Clear resolution of which song to play",
      "post_check": "Verify resolved_choice contains song_name and artist",
      "deliveries": []
    },
    {
      "id": 2,
      "action": "play_song",
      "parameters": {
        "song_name": "$step1.resolved_choice.song_name + ' by ' + $step1.resolved_choice.artist"
      },
      "dependencies": [1],
      "reasoning": "Play the song that was clarified by the user",
      "expected_output": "Song starts playing successfully",
      "post_check": "Check for successful playback status",
      "deliveries": ["play_music"]
    }
  ],
  "complexity": "simple"
}
```

**Step 1 Result:**
```json
{
  "success": true,
  "resolved_choice": {"song_name": "Hello", "artist": "Adele"},
  "ready_for_playback": true
}
```

**Step 2 Execution:** Plays "Hello" by Adele.

## Key Patterns

1. **Always check for clarification_needed flag** after play_song attempts
2. **Present options clearly** with numbers, song names, artists, and confidence indicators
3. **Accept multiple response formats** (numbers, song names, artist names)
4. **Store clarification learning** in session context for future disambiguation improvement
5. **Chain clarification → resolution → playback** as a seamless workflow

## Error Handling

- If user provides invalid clarification response, re-present options
- If playback fails after clarification, don't ask for more clarification (avoid loops)
- Always preserve original query context through the clarification chain
