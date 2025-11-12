# Example: Multi-Conditional Branching (Weather → Reminder OR Note)

**User Query:**
"Check the weather. If there's more than 60% chance of rain, remind me to bring an umbrella. Otherwise, create a note to bring sunglasses."

**Context:**
- User location: San Francisco, CA
- Current time: Morning (6 AM)
- User wants EITHER reminder OR note based on weather condition
- Complex conditional with explicit threshold mentioned

**Expected Workflow:**
1. Get weather forecast
2. Use LLM to interpret if rain > 60%
3. EITHER create reminder (if yes) OR create note (if no)
4. Confirm action to user

---

## Task Planner Output

```json
{
  "reasoning": {
    "task_type": "multi_conditional_workflow",
    "complexity": "moderate",
    "required_tools": ["get_weather_forecast", "synthesize_content", "create_reminder", "create_note", "reply_to_user"],
    "capability_check": {
      "all_tools_available": true,
      "conditional_branching": "LLM interprets threshold via synthesize_content"
    },
    "plan_rationale": "User specifies explicit branching logic: rain > 60% → reminder, else → note. CRITICAL: Planner does NOT hardcode 'if precipitation_chance > 60'. Instead, LLM interprets via synthesize_content. Pattern: (1) get_weather_forecast, (2) synthesize_content asks 'Is rain > 60%?', (3) Based on LLM response, execute EITHER create_reminder OR create_note, (4) reply_to_user."
  },
  "plan": [
    {
      "step": 0,
      "action": "get_weather_forecast",
      "parameters": {
        "location": "San Francisco, CA",
        "timeframe": "today"
      }
    },
    {
      "step": 1,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": [
          "$step0.precipitation_chance",
          "$step0.precipitation_type",
          "$step0.current_conditions"
        ],
        "topic": "Is the rain probability above 60%? Answer 'yes' or 'no' with brief reasoning.",
        "synthesis_style": "brief"
      },
      "reasoning": "LLM interprets the '> 60%' threshold. User said '60%' but LLM considers context: is it exactly 60%? What if it's 59%? What if it's 61% but 'light drizzle'? LLM makes nuanced decision."
    },
    {
      "step": 2,
      "action": "conditional_branch",
      "reasoning": "Based on $step1.synthesized_content, execute EITHER step2a (reminder) OR step2b (note).",
      "branch_logic": "If $step1 contains 'yes', execute step2a. If $step1 contains 'no', execute step2b."
    },
    {
      "step": "2a",
      "action": "create_reminder",
      "parameters": {
        "title": "Bring umbrella",
        "due_time": "today at 7am",
        "notes": "Rain probability: $step0.precipitation_chance%"
      },
      "condition": "Execute only if $step1 indicates rain > 60%"
    },
    {
      "step": "2b",
      "action": "create_note",
      "parameters": {
        "title": "Weather Note - Sunglasses",
        "body": "Weather looks good today ($step0.current_conditions, $step0.precipitation_chance% rain chance). Bring sunglasses!",
        "folder": "Personal"
      },
      "condition": "Execute only if $step1 indicates rain <= 60%"
    },
    {
      "step": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Based on today's weather ($step0.precipitation_chance% chance of $step0.precipitation_type), [I've set a reminder for umbrella / I've created a note for sunglasses]."
      }
    }
  ]
}
```

---

## Scenario A: High Rain Probability (>60%)

**Step 0: get_weather_forecast**
```json
{
  "success": true,
  "location": "San Francisco, CA",
  "timeframe": "today",
  "current_temp": 58,
  "current_conditions": "Overcast",
  "precipitation_chance": 75,
  "precipitation_type": "rain",
  "humidity": 85,
  "wind_speed": 15
}
```

**Step 1: synthesize_content**

*LLM Input:*
- precipitation_chance: 75
- precipitation_type: "rain"
- current_conditions: "Overcast"
- Topic: "Is the rain probability above 60%?"

*LLM Output:*
```json
{
  "synthesized_content": "Yes, the rain probability is 75%, which is above the 60% threshold. With overcast conditions and rain in the forecast, an umbrella is definitely needed.",
  "reasoning": "75% > 60%, and overcast conditions support the high rain probability."
}
```

**Step 2a: create_reminder** *(executed because LLM said "yes")*
```json
{
  "success": true,
  "reminder_title": "Bring umbrella",
  "reminder_id": "x-apple-reminder://REM123",
  "due_date": "2024-12-20T07:00:00",
  "message": "Created reminder 'Bring umbrella' due at 7am"
}
```

**Step 2b: create_note** *(SKIPPED - condition not met)*

**Step 3: reply_to_user**
```json
{
  "message": "Based on today's weather (75% chance of rain), I've set a reminder for 7am to bring your umbrella."
}
```

---

## Scenario B: Low Rain Probability (<=60%)

**Step 0: get_weather_forecast**
```json
{
  "success": true,
  "location": "San Francisco, CA",
  "timeframe": "today",
  "current_temp": 68,
  "current_conditions": "Partly Cloudy",
  "precipitation_chance": 20,
  "precipitation_type": "none",
  "humidity": 60,
  "wind_speed": 8
}
```

**Step 1: synthesize_content**

*LLM Input:*
- precipitation_chance: 20
- precipitation_type: "none"
- current_conditions: "Partly Cloudy"
- Topic: "Is the rain probability above 60%?"

*LLM Output:*
```json
{
  "synthesized_content": "No, the rain probability is only 20%, well below the 60% threshold. With partly cloudy conditions and no rain expected, sunglasses are more appropriate.",
  "reasoning": "20% << 60%, and partly cloudy suggests some sunshine. Good weather for sunglasses."
}
```

**Step 2a: create_reminder** *(SKIPPED - condition not met)*

**Step 2b: create_note** *(executed because LLM said "no")*
```json
{
  "success": true,
  "note_title": "Weather Note - Sunglasses",
  "note_id": "x-coredata://NOTE456",
  "folder": "Personal",
  "message": "Created note 'Weather Note - Sunglasses' in folder 'Personal'"
}
```

*Note Content:*
```
Weather looks good today (Partly Cloudy, 20% rain chance). Bring sunglasses!
```

**Step 3: reply_to_user**
```json
{
  "message": "Based on today's weather (20% chance of rain), I've created a note reminding you to bring sunglasses."
}
```

---

## Edge Case: Exactly 60% Rain

**Step 0: get_weather_forecast**
```json
{
  "precipitation_chance": 60,
  "precipitation_type": "rain",
  "current_conditions": "Cloudy"
}
```

**Step 1: synthesize_content**

*LLM Input:*
- precipitation_chance: 60
- Topic: "Is the rain probability above 60%?"

*LLM Output (Possible Interpretation 1):*
```json
{
  "synthesized_content": "The rain probability is exactly 60%, which equals but does not exceed the threshold. However, with cloudy conditions, I'd recommend erring on the side of caution and bringing an umbrella.",
  "reasoning": "60% = 60%, technically not 'above'. But cloudy conditions + 60% probability warrants umbrella."
}
```

*LLM Output (Possible Interpretation 2):*
```json
{
  "synthesized_content": "The rain probability is 60%, which is at the threshold but not above it. Given the user said 'more than 60%', this doesn't qualify. Sunglasses note is more appropriate.",
  "reasoning": "User said 'more than 60%', not '>= 60%'. 60% == 60%, not > 60%."
}
```

**Key Insight**: The LLM interprets edge cases contextually. It might:
- Consider "more than 60%" literally (so 60% doesn't qualify)
- Factor in other signals (cloudy conditions → lean toward umbrella)
- Make a judgment call based on user safety

This is WHY we use LLM interpretation instead of hardcoded logic!

---

## Implementation Notes

### How Conditional Branching Works

The planner creates a plan with BOTH branches (step2a and step2b). During execution:

1. **Executor** runs step0 (get_weather_forecast)
2. **Executor** runs step1 (synthesize_content)
3. **Executor** reads $step1 output, checks if it contains "yes" or "no"
4. **Executor** executes EITHER step2a OR step2b based on LLM response
5. **Executor** runs step3 (reply_to_user)

The **conditional logic lives in the LLM's synthesize_content output**, NOT in Python code.

### Alternative: Two-Stage Planning

Some architectures might handle this as two separate planning calls:

**Stage 1:**
```json
[
  {"action": "get_weather_forecast"},
  {"action": "synthesize_content"},
  {"action": "reply_to_user", "parameters": {"message": "Checking weather..."}}
]
```

**Stage 2 (after seeing Stage 1 results):**
```json
// If rain > 60%:
[
  {"action": "create_reminder"},
  {"action": "reply_to_user"}
]

// If rain <= 60%:
[
  {"action": "create_note"},
  {"action": "reply_to_user"}
]
```

Both approaches are valid. The key is that **LLM decides, not hardcoded logic**.

---

## Key Principles Demonstrated

1. **LLM Interprets Thresholds**: User says "60%" but LLM decides what that means (exactly 60%? More than? What about edge cases?)

2. **Contextual Decision Making**: LLM considers precipitation_chance AND current_conditions AND precipitation_type, not just one number

3. **Nuanced Logic**: "75% chance of light drizzle" vs "61% chance of heavy rain" might have different interpretations

4. **Safe Defaults**: When uncertain, LLM tends toward safer option (umbrella over sunglasses if close call)

5. **Explicit Branching**: Plan clearly shows BOTH possible paths, making logic transparent

---

## Notes

- **Note:** User explicitly mentions "60%" but LLM still interprets contextually
- This pattern extends to other multi-conditional workflows (temperature thresholds, wind speed, etc.)
- Always finish with reply_to_user to confirm which branch was taken
