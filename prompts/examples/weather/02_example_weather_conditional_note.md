# Example: Weather-Conditional Note Creation

**User Query:**
"If it's sunny tomorrow, create a note reminding me to bring sunglasses"

**Context:**
- User location: Los Angeles, CA
- Current time: Evening (7 PM)
- User wants conditional note creation based on tomorrow's weather

**Expected Workflow:**
1. Get weather forecast for tomorrow
2. Use LLM to interpret conditions
3. Create note if LLM determines it will be sunny
4. Confirm action to user

---

## Task Planner Output

```json
{
  "reasoning": {
    "task_type": "conditional_workflow",
    "complexity": "simple",
    "required_tools": ["get_weather_forecast", "synthesize_content", "create_note", "reply_to_user"],
    "capability_check": {
      "all_tools_available": true,
      "weather_agent": "available",
      "writing_agent": "available",
      "notes_agent": "available"
    },
    "plan_rationale": "User wants conditional note based on weather. Pattern: (1) get_weather_forecast for tomorrow, (2) synthesize_content for LLM to interpret if 'sunny', (3) create_note only if LLM says sunny, (4) reply_to_user. LLM decides what 'sunny' means - not hardcoded conditions check."
  },
  "plan": [
    {
      "step": 0,
      "action": "get_weather_forecast",
      "parameters": {
        "location": "Los Angeles, CA",
        "timeframe": "tomorrow"
      }
    },
    {
      "step": 1,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": [
          "$step0.current_conditions",
          "$step0.precipitation_chance",
          "$step0.high_temp"
        ],
        "topic": "Will tomorrow be sunny enough to warrant bringing sunglasses?",
        "synthesis_style": "brief"
      },
      "reasoning": "LLM interprets what 'sunny' means. Considers: current_conditions, precipitation_chance, cloud cover, etc. Not just 'if conditions == Sunny'."
    },
    {
      "step": 2,
      "action": "create_note",
      "parameters": {
        "title": "Tomorrow's Weather - Sunglasses Reminder",
        "body": "Tomorrow will be $step0.current_conditions with a high of $step0.high_temp°F. Remember to bring sunglasses!",
        "folder": "Personal"
      },
      "reasoning": "Only execute if $step1 indicates sunny weather. Note persists beyond chat session."
    },
    {
      "step": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Tomorrow will be sunny in LA! I've created a note to remind you to bring sunglasses."
      }
    }
  ]
}
```

---

## Simulated Execution

**Step 0: get_weather_forecast**
```json
{
  "success": true,
  "location": "Los Angeles, CA",
  "timeframe": "tomorrow",
  "current_temp": 72,
  "current_conditions": "Sunny",
  "high_temp": 78,
  "low_temp": 62,
  "precipitation_chance": 5,
  "precipitation_type": "none",
  "humidity": 45,
  "wind_speed": 8
}
```

**Step 1: synthesize_content**

*LLM Input:*
- current_conditions: "Sunny"
- precipitation_chance: 5
- high_temp: 78
- Topic: "Will tomorrow be sunny enough to warrant bringing sunglasses?"

*LLM Output:*
```json
{
  "synthesized_content": "Yes, tomorrow will be sunny with clear skies (only 5% chance of precipitation) and a high of 78°F. Perfect sunglasses weather.",
  "reasoning": "'Sunny' conditions with very low precipitation chance (5%) confirms bright weather. User should bring sunglasses."
}
```

**Step 2: create_note**
```json
{
  "success": true,
  "note_title": "Tomorrow's Weather - Sunglasses Reminder",
  "note_id": "x-coredata://NOTE789",
  "folder": "Personal",
  "created_at": "2024-12-20T19:00:00",
  "message": "Created note 'Tomorrow's Weather - Sunglasses Reminder' in folder 'Personal'"
}
```

*Note Content:*
```
Tomorrow will be Sunny with a high of 78°F. Remember to bring sunglasses!
```

**Step 3: reply_to_user**
```json
{
  "message": "Tomorrow will be sunny in LA! I've created a note to remind you to bring sunglasses."
}
```

---

## Key Differences: Reminder vs. Note

### Why Note Instead of Reminder?

1. **Persistent Reference**: Note persists beyond tomorrow, can be reviewed later
2. **No Specific Time**: User didn't specify WHEN to be reminded ("tomorrow" is vague)
3. **Informational**: More of a "keep in mind" than a time-sensitive alert
4. **User Choice**: User explicitly said "create a note"

### When to Choose Note vs. Reminder:

**Use create_reminder when:**
- User specifies a time ("at 7am", "before leaving")
- Time-sensitive action required
- Needs notification/alert
- User says "remind me"

**Use create_note when:**
- User wants persistent storage
- No specific time mentioned
- Informational/reference
- User says "note", "write down", "save"

---

## Alternative Scenario: Cloudy Weather

**Step 0: get_weather_forecast**
```json
{
  "current_conditions": "Mostly Cloudy",
  "precipitation_chance": 40,
  "high_temp": 68
}
```

**Step 1: synthesize_content**

*LLM Output:*
```json
{
  "synthesized_content": "Tomorrow will be mostly cloudy with a 40% chance of rain. Not sunny enough for sunglasses to be essential.",
  "reasoning": "'Mostly Cloudy' suggests limited sunshine. 40% precipitation chance means potential rain. Not ideal sunglasses weather."
}
```

**Step 2: create_note**
*SKIPPED* - LLM decided not sunny

**Step 3: reply_to_user**
```json
{
  "message": "Tomorrow looks mostly cloudy in LA with a 40% chance of rain. I didn't create a note for sunglasses since it won't be very sunny."
}
```

---

## Integration with Writing Agent

**Optional Enhancement**: Store generated content in note

```json
{
  "plan": [
    {"action": "get_weather_forecast", "parameters": {...}},
    {"action": "create_detailed_report", "parameters": {
      "content": "$step0",
      "title": "Tomorrow's Weather Forecast",
      "report_style": "brief"
    }},
    {"action": "create_note", "parameters": {
      "title": "Weather Report - Tomorrow",
      "body": "$step1.report_content",
      "folder": "Personal"
    }},
    {"action": "reply_to_user", "parameters": {...}}
  ]
}
```

This pattern stores a formatted weather report in Notes for future reference.

---

## Notes

- **Note:** The LLM determines "sunny enough" based on context, not hardcoded rules
- Notes persist in Apple Notes app, accessible beyond the chat session
- Folder "Personal" can be customized or will use default Notes folder if it doesn't exist
