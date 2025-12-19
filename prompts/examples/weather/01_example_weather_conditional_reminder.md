# Example: Weather-Conditional Reminder

**User Query:**
"If it's going to rain today, remind me to bring an umbrella"

**Context:**
- User location: New York, NY (inferred from config or previous context)
- Current time: Morning (6:30 AM)
- User wants conditional action based on weather

**Expected Workflow:**
1. Get weather forecast for today
2. Use LLM to interpret precipitation data
3. Create reminder if LLM determines rain is likely
4. Confirm action to user

---

## Task Planner Output

```json
{
  "reasoning": {
    "task_type": "conditional_workflow",
    "complexity": "simple",
    "required_tools": ["get_weather_forecast", "synthesize_content", "create_reminder", "reply_to_user"],
    "capability_check": {
      "all_tools_available": true,
      "weather_agent": "available",
      "writing_agent": "available",
      "reminders_agent": "available"
    },
    "plan_rationale": "User wants conditional reminder based on weather. Pattern: (1) get_weather_forecast to retrieve precipitation data, (2) synthesize_content for LLM to interpret if 'likely to rain', (3) create_reminder only if LLM says yes, (4) reply_to_user to confirm action. NO hardcoded threshold - LLM decides what precipitation_chance means in context."
  },
  "plan": [
    {
      "step": 0,
      "action": "get_weather_forecast",
      "parameters": {
        "location": "New York, NY",
        "timeframe": "today"
      },
      "expected_output": {
        "precipitation_chance": "number (0-100)",
        "precipitation_type": "string (rain/snow/none)",
        "current_temp": "number",
        "current_conditions": "string"
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
        "topic": "Will it rain heavily enough that the user should bring an umbrella?",
        "synthesis_style": "brief"
      },
      "reasoning": "LLM interprets weather data contextually. No hardcoded threshold like 'if > 50%'. LLM considers: precipitation_chance, precipitation_type (drizzle vs downpour), current_conditions, user location, season, etc."
    },
    {
      "step": 2,
      "action": "create_reminder",
      "parameters": {
        "title": "Bring umbrella",
        "due_time": "today at 7am",
        "notes": "Rain expected: $step0.precipitation_chance% chance of $step0.precipitation_type"
      },
      "reasoning": "Only execute this step if $step1.synthesized_content indicates rain is likely. LLM-driven decision."
    },
    {
      "step": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "It's going to rain today ($step0.precipitation_chance% chance of $step0.precipitation_type). I've set a reminder for 7am to bring your umbrella."
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
  "location": "New York, NY",
  "timeframe": "today",
  "current_temp": 54,
  "current_conditions": "Cloudy",
  "high_temp": 62,
  "low_temp": 48,
  "precipitation_chance": 75,
  "precipitation_type": "rain",
  "humidity": 78,
  "wind_speed": 12
}
```

**Step 1: synthesize_content**

*LLM Input:*
- precipitation_chance: 75
- precipitation_type: "rain"
- current_conditions: "Cloudy"
- Topic: "Will it rain heavily enough that the user should bring an umbrella?"

*LLM Output:*
```json
{
  "synthesized_content": "Yes, with a 75% chance of rain and cloudy conditions, it's quite likely to rain today. The user should bring an umbrella.",
  "reasoning": "75% precipitation chance is high enough to warrant bringing an umbrella. The cloudy conditions support the forecast.",
  "word_count": 28
}
```

**Step 2: create_reminder**
```json
{
  "success": true,
  "reminder_title": "Bring umbrella",
  "reminder_id": "x-apple-reminder://ABC123",
  "list_name": "Reminders",
  "due_date": "2024-12-20T07:00:00",
  "created_at": "2024-12-20T06:30:00",
  "message": "Created reminder 'Bring umbrella' in list 'Reminders' due 2024-12-20 07:00"
}
```

**Step 3: reply_to_user**
```json
{
  "message": "It's going to rain today (75% chance of rain). I've set a reminder for 7am to bring your umbrella."
}
```

---

## Key Principles Demonstrated

1. **NO Hardcoded Thresholds**: The planner doesn't hardcode "if precipitation_chance > 50%". The LLM interprets the data contextually via synthesize_content.

2. **LLM-Driven Decision**: The synthesize_content step is critical. It lets the LLM reason about:
   - What does 75% precipitation chance mean?
   - Is "Cloudy" + "rain" likely enough for an umbrella?
   - Context: time of year, user location, severity of rain

3. **Conditional Execution**: The create_reminder step only executes if synthesize_content indicates rain is likely. This is driven by LLM reasoning, not code logic.

4. **User Confirmation**: Always finish with reply_to_user to confirm what action was taken.

5. **Parameter Referencing**: Uses `$step0.precipitation_chance` to pass data between steps, enabling dynamic workflows.

---

## Alternative Scenario: Low Rain Chance

**Step 0: get_weather_forecast**
```json
{
  "precipitation_chance": 15,
  "precipitation_type": "none",
  "current_conditions": "Partly Sunny"
}
```

**Step 1: synthesize_content**

*LLM Output:*
```json
{
  "synthesized_content": "No, with only a 15% chance of precipitation and partly sunny conditions, rain is unlikely. User doesn't need an umbrella.",
  "reasoning": "15% is low probability, and 'partly sunny' suggests clear weather."
}
```

**Step 2: create_reminder**
*SKIPPED* - LLM decided rain is unlikely

**Step 3: reply_to_user**
```json
{
  "message": "Good news! The weather looks clear today (only 15% chance of rain, partly sunny). No need for an umbrella."
}
```

---

## Notes

- **Note:** This example shows the INTENDED workflow. The actual LLM interpretation in synthesize_content may vary based on context.
- The planner creates the plan BEFORE execution. The conditional logic (whether to create_reminder) is determined during execution based on synthesize_content output.
- This pattern extends to other conditional workflows: weather → note, weather → multi-conditional branching, etc.
