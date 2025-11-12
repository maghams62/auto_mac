"""
Weather Agent - Handles weather forecast queries and conditional logic.

This agent is responsible for:
- Retrieving weather forecasts for specified locations
- Providing current conditions and multi-day forecasts
- Returning structured data for LLM-based decision making

INTEGRATION PATTERN:
- Agent returns structured weather data (precipitation_chance, temperature, etc.)
- LLM (via Writing Agent synthesis) interprets data and makes decisions
- Conditional actions (reminders, notes) triggered based on LLM reasoning
- NO hardcoded thresholds - LLM decides what "likely to rain" means

Acts as a data provider for weather-aware workflows.
"""

from typing import Dict, Any, Optional
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)


@tool
def get_weather_forecast(
    location: Optional[str] = None,
    timeframe: str = "today"
) -> Dict[str, Any]:
    """
    Get weather forecast for a location and timeframe.

    This tool retrieves weather data from macOS Weather app and returns
    structured information that can be used for decision-making.

    WEATHER AGENT - LEVEL 1: Data Retrieval
    Use this to get weather information before making conditional decisions.

    Args:
        location: Location name (e.g., "San Francisco, CA")
                 If None, uses default location from config
        timeframe: Forecast timeframe:
            - "now" or "current": Current conditions only
            - "today": Today's forecast (default)
            - "tomorrow": Tomorrow's forecast
            - "week" or "7day": 7-day forecast
            - "3day": 3-day forecast

    Returns:
        Dictionary with weather forecast data:
        {
            "success": True,
            "location": str,
            "timeframe": str,
            "current_temp": int,  # Fahrenheit
            "current_conditions": str,
            "high_temp": int,
            "low_temp": int,
            "precipitation_chance": int,  # 0-100%
            "precipitation_type": str,  # "rain", "snow", "none"
            "humidity": int,  # 0-100%
            "wind_speed": int,  # mph
            "forecast_days": [  # Only for multi-day forecasts
                {
                    "day": str,
                    "date": str,
                    "high": int,
                    "low": int,
                    "conditions": str,
                    "precipitation_chance": int
                }
            ]
        }

    Example Workflow (LLM-driven decision):
        Step 0: get_weather_forecast(location="Los Angeles", timeframe="today")
        Step 1: synthesize_content(
            source_contents=["$step0.precipitation_chance", "$step0.precipitation_type"],
            topic="Should user bring umbrella?",
            synthesis_style="brief"
        )
        Step 2: IF $step1 says "yes" -> create_reminder(
            title="Bring umbrella",
            due_time="today at 8am"
        )

    CRITICAL: Use Writing Agent (synthesize_content) to interpret weather data.
    The LLM decides what precipitation_chance threshold means "likely to rain".
    """
    logger.info(f"[WEATHER AGENT] get_weather_forecast(location={location}, timeframe={timeframe})")

    try:
        from ..automation.weather_automation import WeatherAutomation
        from ..utils import load_config

        config = load_config()

        # Use default location if not provided
        if not location:
            location = config.get("weather", {}).get("default_location", "San Francisco, CA")
            logger.info(f"[WEATHER AGENT] Using default location: {location}")

        # Initialize weather automation
        weather_automation = WeatherAutomation(config)

        # Get forecast
        result = weather_automation.get_weather_forecast(location, timeframe)

        if result.get("success"):
            logger.info(f"[WEATHER AGENT] ✅ Retrieved weather for {location}: "
                       f"{result.get('current_temp')}°F, {result.get('current_conditions')}, "
                       f"{result.get('precipitation_chance')}% precip chance")
        else:
            logger.error(f"[WEATHER AGENT] ❌ Failed to get weather: {result.get('error_message')}")

        return result

    except Exception as e:
        logger.error(f"[WEATHER AGENT] Error in get_weather_forecast: {e}")
        return {
            "success": False,
            "error": True,
            "error_type": "WeatherRetrievalError",
            "error_message": str(e),
            "retry_possible": False
        }


# Weather Agent Tool Registry
WEATHER_AGENT_TOOLS = [
    get_weather_forecast,
]


# Tool hierarchy documentation
WEATHER_AGENT_HIERARCHY = """
WEATHER AGENT TOOL HIERARCHY
============================

LEVEL 1: Weather Data Retrieval
└─ get_weather_forecast → Retrieve weather forecast for location and timeframe
   ├─ Returns structured data (temp, precipitation_chance, conditions, etc.)
   ├─ Supports: current, today, tomorrow, week, 3day timeframes
   └─ Data can be fed to Writing Agent for interpretation

INTEGRATION PATTERN:
Weather Agent provides RAW DATA → Writing Agent INTERPRETS → Conditional Agent ACTS

Example Flow:
1. get_weather_forecast(location="NYC", timeframe="today")
   → Returns: {precipitation_chance: 75%, precipitation_type: "rain"}

2. synthesize_content(
       source_contents=["$step1.precipitation_chance", "$step1.precipitation_type"],
       topic="Will it rain heavily enough to need umbrella?",
       synthesis_style="brief"
   )
   → Returns: "Yes, 75% chance of rain indicates you should bring an umbrella"

3. create_reminder(
       title="Bring umbrella",
       due_time="today at 7am"
   )
   → Creates reminder based on LLM reasoning

CRITICAL PRINCIPLES:
- Weather Agent is READ-ONLY (no actions, just data retrieval)
- LLM interprets weather data via Writing Agent
- NO hardcoded thresholds (e.g., "rain if > 50%")
- Conditional logic lives in LLM reasoning, not agent code
"""


def execute_weather_agent_tools(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a weather agent tool by name.

    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments as dictionary

    Returns:
        Tool execution result
    """
    logger.info(f"[WEATHER AGENT] Executing tool: {tool_name}")

    tool_map = {
        "get_weather_forecast": get_weather_forecast,
    }

    if tool_name not in tool_map:
        return {
            "error": True,
            "error_type": "UnknownTool",
            "error_message": f"Unknown weather agent tool: {tool_name}",
            "retry_possible": False
        }

    try:
        tool = tool_map[tool_name]
        result = tool.invoke(arguments)
        return result
    except Exception as e:
        logger.error(f"[WEATHER AGENT] Execution error: {e}")
        return {
            "error": True,
            "error_type": "ExecutionError",
            "error_message": str(e),
            "retry_possible": False
        }
