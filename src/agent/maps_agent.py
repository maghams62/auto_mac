"""
Maps Agent - Handles Apple Maps trip planning operations.

This agent is responsible for:
- Planning trips with origin and destination
- Adding stops for food and gas
- Setting departure times
- Generating Apple Maps URLs

Acts as a mini-orchestrator for maps-related operations.
"""

from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
import logging
from urllib.parse import quote
from datetime import datetime
from openai import OpenAI
import os

logger = logging.getLogger(__name__)


def _calculate_stop_points_with_llm(origin: str, destination: str, num_stops: int, stop_types: List[str]) -> List[Dict[str, str]]:
    """
    Use LLM to intelligently determine optimal stop locations along a route.

    This uses the LLM's knowledge of geography and common routes to suggest
    actual cities/towns that make sense as stops.

    Args:
        origin: Starting location
        destination: End location
        num_stops: Number of stops needed
        stop_types: List of stop types (e.g., ['food', 'food', 'fuel'])

    Returns:
        List of dicts with 'location' and 'type' keys
    """
    if num_stops == 0:
        return []

    try:
        # Get OpenAI client
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Create a detailed prompt for the LLM
        stop_types_str = ", ".join(stop_types)

        prompt = f"""You are a travel route planning expert. Given a road trip from {origin} to {destination}, suggest {num_stops} optimal stop locations along the most common driving route.

The stops should be for: {stop_types_str}

Requirements:
- Suggest actual cities or towns that are directly along or very close to the main highway route
- Distribute stops relatively evenly along the route
- Consider typical rest stop locations (cities with gas stations, restaurants, etc.)
- Use your knowledge of US geography and common highway routes

Return ONLY a JSON array of objects with this exact format:
[
  {{"location": "City, State", "type": "food"}},
  {{"location": "City, State", "type": "fuel"}},
  ...
]

Do not include any explanation, just the JSON array."""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful travel planning assistant that provides accurate stop suggestions for road trips."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )

        # Parse the response
        import json
        result_text = response.choices[0].message.content.strip()

        # Remove markdown code blocks if present
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()

        stops = json.loads(result_text)

        logger.info(f"LLM suggested {len(stops)} stops for {origin} -> {destination}: {stops}")
        return stops

    except Exception as e:
        logger.error(f"Error using LLM to calculate stops: {e}")
        # Fallback to generic descriptions
        fallback_stops = []
        for i, stop_type in enumerate(stop_types):
            fallback_stops.append({
                "location": f"Stop {i+1} along route from {origin} to {destination}",
                "type": stop_type
            })
        return fallback_stops


def _generate_apple_maps_url(
    origin: str,
    destination: str,
    stops: List[str],
    departure_time: Optional[str] = None
) -> str:
    """
    Generate an Apple Maps URL with waypoints.

    Apple Maps URL scheme:
    - maps://?saddr=START&daddr=END
    - Multiple waypoints not directly supported in URL scheme
    - Alternative: Use search query format

    Args:
        origin: Starting location
        destination: End location
        stops: List of intermediate stops
        departure_time: Departure time (not supported in URL scheme, used for reference)

    Returns:
        Apple Maps URL string
    """
    # URL encode the locations
    origin_encoded = quote(origin)
    destination_encoded = quote(destination)

    if not stops:
        # Simple route without stops
        url = f"maps://?saddr={origin_encoded}&daddr={destination_encoded}&dirflg=d"
    else:
        # For routes with stops, we'll create a directions URL
        # Apple Maps doesn't support multiple waypoints in URL scheme directly,
        # so we'll use the destination with a note about stops
        stops_text = " via " + ", ".join(stops)
        destination_with_stops = f"{destination}{stops_text}"
        destination_encoded = quote(destination_with_stops)
        url = f"maps://?saddr={origin_encoded}&daddr={destination_encoded}&dirflg=d"

    return url


def _generate_google_maps_url(
    origin: str,
    destination: str,
    stops: List[str],
    departure_time: Optional[datetime] = None
) -> str:
    """
    Generate a Google Maps URL with waypoints (better support for multiple stops).

    Args:
        origin: Starting location
        destination: End location
        stops: List of intermediate stops
        departure_time: Departure time as datetime object

    Returns:
        Google Maps URL string
    """
    # Build the waypoints string
    waypoints = ""
    if stops:
        waypoints = "|".join([quote(stop) for stop in stops])

    # Base URL
    url = f"https://www.google.com/maps/dir/?api=1"
    url += f"&origin={quote(origin)}"
    url += f"&destination={quote(destination)}"

    if waypoints:
        url += f"&waypoints={waypoints}"

    # Add departure time if provided (Unix timestamp in seconds)
    if departure_time:
        timestamp = int(departure_time.timestamp())
        url += f"&departure_time={timestamp}"

    # Set travel mode to driving
    url += "&travelmode=driving"

    return url


@tool
def plan_trip_with_stops(
    origin: str,
    destination: str,
    num_fuel_stops: int = 0,
    num_food_stops: int = 0,
    departure_time: Optional[str] = None,
    use_google_maps: bool = False
) -> Dict[str, Any]:
    """
    Plan a trip from origin to destination with specific numbers of fuel and food stops.

    This is the PRIMARY trip planning tool. Use this when you need to:
    - Plan a route with multiple fuel stops
    - Plan a route with multiple food stops (breakfast, lunch, dinner, etc.)
    - Specify exact number of stops needed
    - Get a Maps URL with all waypoints

    Args:
        origin: Starting location (e.g., "San Francisco, CA", "Santa Clara, CA")
        destination: End location (e.g., "Los Angeles, CA", "San Diego, CA")
        num_fuel_stops: Number of fuel/gas stops to add (0-3)
        num_food_stops: Number of food stops to add (0-3, e.g., 2 for breakfast and lunch)
        departure_time: Departure time in format "HH:MM AM/PM" or "YYYY-MM-DD HH:MM"
        use_google_maps: If True, generate Google Maps URL (better waypoint support);
                        if False, use Apple Maps URL

    Returns:
        Dictionary with route details and maps URL

    Example:
        plan_trip_with_stops(
            origin="Santa Clara, CA",
            destination="San Diego, CA",
            num_fuel_stops=2,
            num_food_stops=2,
            departure_time="7:00 AM"
        )
    """
    logger.info(
        f"[MAPS AGENT] Tool: plan_trip_with_stops(origin='{origin}', destination='{destination}', "
        f"fuel_stops={num_fuel_stops}, food_stops={num_food_stops}, departure={departure_time})"
    )

    try:
        # Calculate total number of stops needed
        total_stops = num_fuel_stops + num_food_stops

        if total_stops > 6:
            return {
                "error": True,
                "error_type": "TooManyStops",
                "error_message": "Maximum 6 total stops supported (fuel + food combined)",
                "retry_possible": True
            }

        # Build list of stop types to request from LLM
        stop_types = []
        for _ in range(num_food_stops):
            stop_types.append("food")
        for _ in range(num_fuel_stops):
            stop_types.append("fuel")

        # Use LLM to determine optimal stop locations
        stops_with_types = _calculate_stop_points_with_llm(origin, destination, total_stops, stop_types)

        # Add order numbers to the stops
        for i, stop in enumerate(stops_with_types):
            stop['order'] = i + 1

        food_count = sum(1 for s in stops_with_types if s['type'] == 'food')
        fuel_count = sum(1 for s in stops_with_types if s['type'] == 'fuel')

        # Parse departure time if provided
        departure_dt = None
        if departure_time:
            try:
                # Try to parse various time formats
                from dateutil import parser
                departure_dt = parser.parse(departure_time)
            except Exception as e:
                logger.warning(f"Could not parse departure time '{departure_time}': {e}")

        # Generate appropriate maps URL
        stop_locations_list = [s["location"] for s in stops_with_types]
        if use_google_maps:
            maps_url = _generate_google_maps_url(origin, destination, stop_locations_list, departure_dt)
            maps_service = "Google Maps"
        else:
            maps_url = _generate_apple_maps_url(origin, destination, stop_locations_list, departure_time)
            maps_service = "Apple Maps"

        # Build response
        route_details = {
            "origin": origin,
            "destination": destination,
            "stops": stops_with_types,
            "departure_time": departure_time,
            "maps_url": maps_url,
            "maps_service": maps_service,
            "num_fuel_stops": fuel_count,
            "num_food_stops": food_count
        }

        # Create summary message
        stops_summary = ", ".join([f"{s['location']} ({s['type']})" for s in stops_with_types])
        message = f"Trip planned from {origin} to {destination}"
        if stops_with_types:
            message += f" with {num_food_stops} food stop(s) and {num_fuel_stops} fuel stop(s): {stops_summary}"
        if departure_time:
            message += f". Departure time: {departure_time}"

        return {
            **route_details,
            "message": message,
            "total_stops": len(stops_with_types)
        }

    except Exception as e:
        logger.error(f"[MAPS AGENT] Error in plan_trip_with_stops: {e}")
        return {
            "error": True,
            "error_type": "TripPlanningError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def open_maps_with_route(
    origin: str,
    destination: str,
    stops: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Open Apple Maps application with a specific route.

    This will launch the Maps app on macOS with the specified route loaded.

    Args:
        origin: Starting location
        destination: End location
        stops: Optional list of intermediate stops

    Returns:
        Dictionary with status and URL used

    Example:
        open_maps_with_route(
            origin="San Francisco",
            destination="Los Angeles",
            stops=["Gilroy, CA", "Coalinga, CA"]
        )
    """
    logger.info(
        f"[MAPS AGENT] Tool: open_maps_with_route(origin='{origin}', "
        f"destination='{destination}', stops={stops})"
    )

    try:
        import subprocess

        # Generate maps URL
        stops = stops or []
        maps_url = _generate_apple_maps_url(origin, destination, stops, None)

        # Open URL using macOS 'open' command
        subprocess.run(["open", maps_url], check=True)

        return {
            "status": "opened",
            "maps_url": maps_url,
            "message": f"Opened Apple Maps with route from {origin} to {destination}"
        }

    except Exception as e:
        logger.error(f"[MAPS AGENT] Error in open_maps_with_route: {e}")
        return {
            "error": True,
            "error_type": "MapsOpenError",
            "error_message": str(e),
            "retry_possible": False
        }


# Maps Agent Tool Registry
MAPS_AGENT_TOOLS = [
    plan_trip_with_stops,
    open_maps_with_route,
]


# Maps Agent Hierarchy
MAPS_AGENT_HIERARCHY = """
Maps Agent Hierarchy:
====================

LEVEL 1: Trip Planning
├─ plan_trip_with_stops → Plan route with specific numbers of food and fuel stops
└─ open_maps_with_route → Open Apple Maps app with specific route

Typical Workflow:
1. plan_trip_with_stops(origin, destination, num_fuel_stops=2, num_food_stops=2, departure_time="7:00 AM")
   → Returns route details and Maps URL with all specified stops
2. open_maps_with_route(origin, destination, stops)
   → Opens Maps app with the route

Features:
- Specify exact number of fuel stops (0-3)
- Specify exact number of food stops (0-3) - supports multiple meals (breakfast, lunch, etc.)
- Automatic stop suggestions for common routes (SF-LA, Santa Clara-San Diego, etc.)
- Support for both Apple Maps and Google Maps URLs
- Departure time specification
- Direct Maps app launching on macOS

Example:
plan_trip_with_stops(
    origin="Santa Clara, CA",
    destination="San Diego, CA",
    num_fuel_stops=2,
    num_food_stops=2,
    departure_time="7:00 AM"
)
→ Returns Maps URL with route including 2 fuel stops and 2 food stops (breakfast and lunch)
"""


class MapsAgent:
    """
    Maps Agent - Mini-orchestrator for Apple Maps trip planning.

    Responsibilities:
    - Planning trips with origin and destination
    - Adding stops for food and gas
    - Setting departure times
    - Generating and opening Maps URLs

    This agent acts as a sub-orchestrator that handles all maps-related tasks.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in MAPS_AGENT_TOOLS}
        logger.info(f"[MAPS AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        """Get all maps agent tools."""
        return MAPS_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get maps agent hierarchy documentation."""
        return MAPS_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a maps agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Maps agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[MAPS AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[MAPS AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }
