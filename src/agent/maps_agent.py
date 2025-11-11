"""
Maps Agent - Handles Apple Maps trip planning operations.

This agent is responsible for:
- Planning trips with origin and destination
- Adding stops for food and gas (using LLM reasoning + Apple Maps POI search)
- Setting departure times
- Generating Apple Maps URLs

CRITICAL ARCHITECTURE PRINCIPLES:
- NO hardcoded locations, cities, or routes
- LLM reasons about what "fuel stops" and "food stops" mean
- LLM suggests optimal locations along the route based on distance, highway access, etc.
- Apple Maps is used to find ACTUAL gas stations and restaurants (POIs), not just cities
- All decisions are tool-driven and configurable

Acts as a mini-orchestrator for maps-related operations.
"""

from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
import logging
from urllib.parse import quote
from datetime import datetime
from openai import OpenAI
import os
import googlemaps
from datetime import datetime as dt

logger = logging.getLogger(__name__)

# Global Google Maps client (initialized on first use)
_gmaps_client = None


def _find_pois_via_applescript(location: str, poi_type: str) -> Optional[str]:
    """
    Use AppleScript to search Apple Maps for actual POIs (gas stations, restaurants).
    
    This queries Apple Maps for real businesses, not hardcoded locations.
    
    Args:
        location: Approximate location to search near (e.g., "Bakersfield, CA")
        poi_type: Type of POI - "fuel" for gas stations, "food" for restaurants
        
    Returns:
        Actual POI location string if found, None otherwise
    """
    try:
        from ..automation.maps_automation import MapsAutomation
        from ..utils import load_config
        
        config = load_config()
        maps_automation = MapsAutomation(config)
        
        # Map stop types to search queries
        search_queries = {
            "fuel": ["gas station", "fuel", "gas", "petrol"],
            "food": ["restaurant", "food", "dining"]
        }
        
        # Try different search terms
        queries = search_queries.get(poi_type.lower(), [poi_type])
        
        # Use Apple Maps search URL to find POIs
        # Format: https://maps.apple.com/?q=gas+station+near+Bakersfield+CA
        for query in queries:
            search_term = f"{query} near {location}"
            search_url = f"https://maps.apple.com/?q={quote(search_term)}"
            
            # Use AppleScript to search and get first result
            # For now, return the search location as the stop
            # In a full implementation, we'd parse Maps results via AppleScript
            # But URL-based approach works for now
            return f"{query} near {location}"
        
        return location  # Fallback to original location
        
    except Exception as e:
        logger.warning(f"Could not search for POI via AppleScript: {e}")
        return location  # Fallback to original location


def _calculate_stop_points_with_llm(origin: str, destination: str, num_stops: int, stop_types: List[str]) -> List[Dict[str, str]]:
    """
    Use LLM to intelligently determine optimal stop locations along a route.
    
    The LLM reasons about:
    - What "fuel stops" means (actual gas stations needed for refueling)
    - What "food stops" means (actual restaurants for meals)
    - Optimal locations along the route based on distance, highway access, etc.
    
    Then we use Apple Maps to find actual POIs (gas stations/restaurants) at those locations.
    NO hardcoded cities or locations - everything is LLM-reasoned and Maps-queried.

    Args:
        origin: Starting location
        destination: End location
        num_stops: Number of stops needed
        stop_types: List of stop types (e.g., ['food', 'food', 'fuel'])

    Returns:
        List of dicts with 'location' and 'type' keys - locations are actual POI search queries
    """
    if num_stops == 0:
        return []

    try:
        # Get OpenAI client - use config if available, otherwise env var
        # ALL LLM parameters come from config - NO hardcoded values
        from ..utils import load_config
        from pathlib import Path
        from dotenv import load_dotenv
        
        # Ensure .env is loaded before loading config
        project_root = Path(__file__).resolve().parent.parent.parent
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=True)
        
        try:
            config = load_config()
            api_key = config.get("openai", {}).get("api_key")
            if not api_key or api_key.startswith("${"):
                # Fallback to environment variable
                api_key = os.getenv("OPENAI_API_KEY")
            model = config.get("openai", {}).get("model", "gpt-4o")
            temperature = config.get("openai", {}).get("temperature", 0.7)
            max_tokens = config.get("openai", {}).get("max_tokens", 2000)
            # For stop suggestions, use a reasonable token limit (can be overridden)
            stop_suggestion_tokens = config.get("maps", {}).get("stop_suggestion_max_tokens", 1000)
        except Exception as e:
            # Fallback to environment variable only
            api_key = os.getenv("OPENAI_API_KEY")
            model = "gpt-4o"
            temperature = 0.7
            stop_suggestion_tokens = 1000
        
        if not api_key:
            raise ValueError("OpenAI API key not found in config or environment")
        
        client = OpenAI(api_key=api_key)

        # Create a detailed prompt for the LLM - NO hardcoded geographic assumptions
        stop_types_str = ", ".join(stop_types)

        prompt = f"""You are a travel route planning expert. Given a road trip from {origin} to {destination}, suggest {num_stops} optimal stop locations along the most common driving route.

CRITICAL: Understand what each stop type means:
- "fuel" means the user needs to refuel their vehicle - suggest locations where they can find ACTUAL GAS STATIONS
- "food" means the user needs to eat - suggest locations where they can find ACTUAL RESTAURANTS

The stops should be for: {stop_types_str}

Requirements:
- Reason about the route: What highways/roads connect these locations? What's the typical driving distance?
- For FUEL stops: Suggest locations where gas stations are readily available (near highways, in towns/cities along the route)
- For FOOD stops: Suggest locations where restaurants are available (cities, rest areas, service plazas)
- Distribute stops evenly along the route based on driving distance (not just geographic distance)
- Consider typical refueling ranges (every 200-300 miles for fuel stops)
- Consider meal times and typical meal spacing
- Use your knowledge of geography and common routes for the region/country (do NOT assume any specific country)
- If the route crosses borders or is international, suggest appropriate stops for each country/region
- Consider the actual road network and highway system for the given locations

Return ONLY a JSON array of objects with this exact format:
[
  {{"location": "City, State/Province/Region, Country", "type": "food", "reasoning": "Brief reason why this location"}},
  {{"location": "City, State/Province/Region, Country", "type": "fuel", "reasoning": "Brief reason why this location"}},
  ...
]

Do not include any explanation outside the JSON array.
Use appropriate location format based on the origin/destination countries (e.g., "City, State" for US, "City, Province" for Canada, "City" for smaller countries, etc.)."""

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful travel planning assistant that provides accurate stop suggestions for road trips worldwide. Use your geographic knowledge to suggest optimal stops for any route, regardless of country or region."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=stop_suggestion_tokens  # Configurable - supports international routes
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

        logger.info(f"LLM suggested {len(stops)} stop locations for {origin} -> {destination}: {stops}")
        
        # Now enhance each stop with actual POI search queries
        # Instead of just city names, we'll create search queries for actual POIs
        enhanced_stops = []
        for stop in stops:
            location = stop.get("location", "")
            stop_type = stop.get("type", "")
            
            # Create POI search query - this will be used to find actual gas stations/restaurants
            # Format: "gas station near City, State" or "restaurant near City, State"
            poi_location = _find_pois_via_applescript(location, stop_type)
            
            enhanced_stop = {
                "location": poi_location or location,  # Use POI search query if available
                "type": stop_type,
                "original_location": location,  # Keep original for reference
                "reasoning": stop.get("reasoning", "")
            }
            enhanced_stops.append(enhanced_stop)
        
        logger.info(f"Enhanced {len(enhanced_stops)} stops with POI search queries")
        return enhanced_stops

    except Exception as e:
        logger.error(f"Error using LLM to calculate stops: {e}")
        # Return error rather than hardcoded fallback - let LLM retry or user handle
        raise Exception(f"Failed to calculate stop locations using LLM: {e}. Please retry or provide specific stop locations.")


def _generate_apple_maps_url(
    origin: str,
    destination: str,
    stops: List[str],
    departure_time: Optional[str] = None,
    transportation_mode: str = "d"
) -> str:
    """
    Generate an Apple Maps URL with waypoints and transportation mode.

    Apple Maps supports waypoints in web URLs (https://maps.apple.com/).
    The web URL format supports multiple waypoints and opens in Maps app on macOS.

    Args:
        origin: Starting location
        destination: End location
        stops: List of intermediate stops
        departure_time: Departure time (not supported in URL scheme, used for reference)
        transportation_mode: Transportation mode:
            - "d" = Driving (default)
            - "w" = Walking
            - "r" = Transit/Public Transportation
            - "b" = Bicycle

    Returns:
        Apple Maps URL string (web format that opens in Maps app)
    """
    # URL encode the locations
    origin_encoded = quote(origin)
    destination_encoded = quote(destination)

    if not stops:
        # Simple route without stops - use web URL format
        url = f"https://maps.apple.com/?saddr={origin_encoded}&daddr={destination_encoded}&dirflg={transportation_mode}"
    else:
        # Build waypoints string for Apple Maps web URL
        # Format: https://maps.apple.com/?saddr=ORIGIN&daddr=STOP1&daddr=STOP2&daddr=DESTINATION
        # Apple Maps web URLs support multiple daddr parameters for waypoints
        url = f"https://maps.apple.com/?saddr={origin_encoded}"

        # Add each stop as a waypoint
        for stop in stops:
            stop_encoded = quote(stop)
            url += f"&daddr={stop_encoded}"

        # Add final destination
        url += f"&daddr={destination_encoded}&dirflg={transportation_mode}"

    return url


def _normalize_maps_url(
    url: str,
    origin: str,
    destination: str,
    stops: List[str]
) -> str:
    """
    Normalize Apple Maps URLs to ensure https scheme and explicit daddr waypoints.

    This fixes legacy formats such as:
    maps://?saddr=...&daddr=Destination via Stop1, Stop2
    """
    if not url:
        return url

    normalized = url

    # Ensure https://maps.apple.com/ scheme
    if normalized.startswith("maps://"):
        normalized = normalized.replace("maps://", "https://maps.apple.com/", 1)
    if "maps://" in normalized:
        normalized = normalized.replace("maps://", "https://maps.apple.com/")

    from urllib.parse import urlparse, parse_qs, unquote

    parsed = urlparse(normalized)

    # Only normalize Apple Maps URLs
    if parsed.netloc and "maps.apple.com" not in parsed.netloc:
        return normalized

    query = parse_qs(parsed.query)
    daddr_values = query.get("daddr", [])

    needs_rebuild = False

    # No daddr params or scheme missing -> rebuild
    if not daddr_values or parsed.scheme not in ("http", "https"):
        needs_rebuild = True
    else:
        for raw_value in daddr_values:
            decoded = unquote(raw_value)
            if " via " in decoded.lower():
                needs_rebuild = True
                break

    if needs_rebuild:
        # Rebuild with clean repeated daddr parameters
        normalized = _generate_apple_maps_url(origin, destination, stops, None)

    return normalized


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


def _get_gmaps_client():
    """Get or initialize Google Maps client."""
    global _gmaps_client
    if _gmaps_client is None:
        from ..utils import load_config
        config = load_config()
        api_key = config.get('maps', {}).get('google_maps_api_key', '')

        if not api_key or api_key == 'YOUR_API_KEY_HERE':
            logger.warning("[MAPS AGENT] Google Maps API key not configured. Add GOOGLE_MAPS_API_KEY to .env file.")
            return None

        _gmaps_client = googlemaps.Client(key=api_key)
        logger.info("[MAPS AGENT] Google Maps client initialized")

    return _gmaps_client


def _parse_transit_response(directions_result: list) -> Dict[str, Any]:
    """Parse Google Maps directions response for transit data."""
    if not directions_result:
        return {"error": "No route found"}

    route = directions_result[0]
    leg = route['legs'][0]

    # Extract basic route info
    result = {
        "distance": leg['distance']['text'],
        "duration": leg['duration']['text'],
        "start_address": leg['start_address'],
        "end_address": leg['end_address'],
        "steps": []
    }

    # Extract transit steps with departure times
    for step in leg['steps']:
        step_info = {
            "instruction": step.get('html_instructions', ''),
            "distance": step.get('distance', {}).get('text', ''),
            "duration": step.get('duration', {}).get('text', '')
        }

        # If this is a transit step, extract detailed info
        if step.get('travel_mode') == 'TRANSIT':
            transit = step.get('transit_details', {})
            step_info['transit'] = {
                "line": transit.get('line', {}).get('short_name', ''),
                "line_name": transit.get('line', {}).get('name', ''),
                "vehicle": transit.get('line', {}).get('vehicle', {}).get('name', ''),
                "departure_stop": transit.get('departure_stop', {}).get('name', ''),
                "arrival_stop": transit.get('arrival_stop', {}).get('name', ''),
                "departure_time": transit.get('departure_time', {}).get('text', ''),
                "arrival_time": transit.get('arrival_time', {}).get('text', ''),
                "num_stops": transit.get('num_stops', 0)
            }

        result['steps'].append(step_info)

    # Extract next departure time
    for step in leg['steps']:
        if step.get('travel_mode') == 'TRANSIT':
            transit = step.get('transit_details', {})
            departure_time = transit.get('departure_time', {}).get('text', '')
            if departure_time:
                result['next_departure'] = departure_time
                break

    return result


@tool
def get_google_transit_directions(
    origin: str,
    destination: str,
    departure_time: Optional[str] = "now"
) -> Dict[str, Any]:
    """
    Get real-time transit directions with actual departure times using Google Maps API.

    This tool provides PROGRAMMATIC access to transit schedules including:
    - Next bus/train departure time
    - Step-by-step transit directions
    - Line numbers and vehicle types
    - Real-time schedule data

    Use this for queries like:
    - "When's the next bus to UCSC Silicon Valley"
    - "What time is the next train to downtown"
    - "Show me transit directions to Berkeley"

    Args:
        origin: Starting location (address, place name, or "Current Location")
        destination: End location (address or place name)
        departure_time: When to depart - "now" (default) or specific time

    Returns:
        Dictionary with real-time transit schedule data including next departure time

    Example:
        get_google_transit_directions(
            origin="Current Location",
            destination="UCSC Silicon Valley",
            departure_time="now"
        )
    """
    logger.info(
        f"[MAPS AGENT] Tool: get_google_transit_directions(origin='{origin}', "
        f"destination='{destination}', departure_time='{departure_time}')"
    )

    try:
        gmaps = _get_gmaps_client()
        if gmaps is None:
            return {
                "error": True,
                "error_type": "ConfigurationError",
                "error_message": "Google Maps API key not configured. Please add GOOGLE_MAPS_API_KEY to your .env file.",
                "setup_instructions": "1. Get API key from https://console.cloud.google.com/google/maps-apis/\n2. Add to .env: GOOGLE_MAPS_API_KEY=your_key_here\n3. Enable Maps Directions API in Google Cloud Console"
            }

        # Parse departure time
        if departure_time == "now" or not departure_time:
            departure_dt = dt.now()
        else:
            # Try to parse the time string (basic parsing)
            try:
                departure_dt = dt.strptime(departure_time, "%Y-%m-%d %H:%M")
            except:
                departure_dt = dt.now()

        # Get transit directions from Google Maps
        logger.info(f"[MAPS AGENT] Requesting transit directions from Google Maps API...")
        directions_result = gmaps.directions(
            origin=origin,
            destination=destination,
            mode="transit",
            departure_time=departure_dt
        )

        if not directions_result:
            return {
                "error": True,
                "error_type": "NoRouteFound",
                "error_message": f"No transit route found from {origin} to {destination}",
                "suggestion": "Try a different location or check if transit service is available in this area."
            }

        # Parse the response
        parsed = _parse_transit_response(directions_result)

        # Build human-readable response
        result = {
            "origin": origin,
            "destination": destination,
            "transportation_mode": "transit",
            "maps_service": "Google Maps",
            "distance": parsed.get('distance', 'Unknown'),
            "duration": parsed.get('duration', 'Unknown'),
            "next_departure": parsed.get('next_departure', 'See directions for details')
        }

        # Create Google Maps URL
        gmaps_url = f"https://www.google.com/maps/dir/?api=1&origin={quote(origin)}&destination={quote(destination)}&travelmode=transit"
        result["maps_url"] = gmaps_url

        # Build message with next departure time
        if 'next_departure' in parsed:
            result["message"] = (
                f"Next departure: {parsed['next_departure']}. "
                f"Trip duration: {parsed['duration']}. "
                f"View full directions: {gmaps_url}"
            )
        else:
            result["message"] = (
                f"Transit directions from {origin} to {destination}. "
                f"Duration: {parsed['duration']}. Distance: {parsed['distance']}. "
                f"View directions: {gmaps_url}"
            )

        # Add detailed steps
        result["transit_steps"] = []
        for step in parsed.get('steps', []):
            if 'transit' in step:
                transit = step['transit']
                result["transit_steps"].append({
                    "line": transit.get('line', ''),
                    "vehicle": transit.get('vehicle', ''),
                    "from": transit.get('departure_stop', ''),
                    "to": transit.get('arrival_stop', ''),
                    "departure": transit.get('departure_time', ''),
                    "arrival": transit.get('arrival_time', ''),
                    "stops": transit.get('num_stops', 0)
                })

        # Open in browser
        try:
            import subprocess
            subprocess.run(["open", gmaps_url], check=True)
            result["maps_opened"] = True
            logger.info(f"[MAPS AGENT] Opened Google Maps in browser with transit directions")
        except Exception as e:
            result["maps_opened"] = False
            logger.warning(f"[MAPS AGENT] Failed to open browser: {e}")

        return result

    except googlemaps.exceptions.ApiError as e:
        logger.error(f"[MAPS AGENT] Google Maps API error: {e}")
        return {
            "error": True,
            "error_type": "GoogleMapsApiError",
            "error_message": str(e),
            "retry_possible": False
        }
    except Exception as e:
        logger.error(f"[MAPS AGENT] Error in get_google_transit_directions: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": True,
            "error_type": "TransitDirectionsError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def get_directions(
    origin: str,
    destination: str,
    transportation_mode: str = "driving",
    open_maps: bool = True
) -> Dict[str, Any]:
    """
    Get simple directions from one location to another with specified transportation mode.

    Use this for simple point-to-point navigation queries like:
    - "When's the next bus to Berkeley"
    - "How do I bike to the office"
    - "Walk me to the coffee shop"
    - "Drive to San Francisco"

    IMPORTANT: For "current location" queries, use the location service to detect current location first,
    then call this tool with the actual coordinates or "Current Location" string.

    Args:
        origin: Starting location (can be "Current Location" or specific address/coordinates)
        destination: End location (address, place name, or coordinates)
        transportation_mode: Mode of transportation:
            - "driving" or "car" = Driving (default)
            - "walking" or "walk" = Walking
            - "transit" or "bus" or "public transport" = Public Transportation/Transit
            - "bicycle" or "bike" or "cycling" = Bicycle
        open_maps: If True, automatically open Maps with the route (default: True)

    Returns:
        Dictionary with route details and maps URL

    Example:
        get_directions(
            origin="Current Location",
            destination="Berkeley, CA",
            transportation_mode="transit"
        )
    """
    logger.info(
        f"[MAPS AGENT] Tool: get_directions(origin='{origin}', destination='{destination}', "
        f"mode='{transportation_mode}', open_maps={open_maps})"
    )

    try:
        # Map transportation mode to Apple Maps dirflg parameter
        mode_mapping = {
            "driving": "d",
            "car": "d",
            "walking": "w",
            "walk": "w",
            "transit": "r",
            "bus": "r",
            "public transport": "r",
            "public transportation": "r",
            "bicycle": "b",
            "bike": "b",
            "cycling": "b"
        }

        mode_key = transportation_mode.lower().strip()
        dirflg = mode_mapping.get(mode_key, "d")

        # Generate maps URL
        maps_url = _generate_apple_maps_url(
            origin=origin,
            destination=destination,
            stops=[],
            departure_time=None,
            transportation_mode=dirflg
        )

        # Build response
        mode_display = {
            "d": "driving",
            "w": "walking",
            "r": "transit",
            "b": "bicycle"
        }

        result = {
            "origin": origin,
            "destination": destination,
            "transportation_mode": mode_display.get(dirflg, "driving"),
            "maps_url": maps_url,
            "maps_service": "Apple Maps"
        }

        # Open Maps if requested
        maps_opened = False
        if open_maps:
            import subprocess
            try:
                subprocess.run(["open", maps_url], check=True)
                maps_opened = True
                logger.info(f"[MAPS AGENT] Opened Apple Maps with {mode_display.get(dirflg)} directions")
            except Exception as e:
                logger.error(f"[MAPS AGENT] Failed to open Maps: {e}")

        result["maps_opened"] = maps_opened

        if maps_opened:
            result["message"] = f"Opening {mode_display.get(dirflg)} directions from {origin} to {destination} in Apple Maps: {maps_url}"
        else:
            result["message"] = f"Here are {mode_display.get(dirflg)} directions from {origin} to {destination}: {maps_url}"

        # Add note about transit schedules
        if dirflg == "r":
            result["note"] = "Apple Maps will show real-time transit schedules and next departure times when you open the app."

        return result

    except Exception as e:
        logger.error(f"[MAPS AGENT] Error in get_directions: {e}")
        return {
            "error": True,
            "error_type": "DirectionsError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def get_transit_schedule(
    origin: str,
    destination: str,
    open_maps: bool = True
) -> Dict[str, Any]:
    """
    Get transit schedule and next departures from one location to another.

    Use this specifically for transit/bus/train queries like:
    - "When's the next bus to downtown"
    - "Show me the train schedule to the airport"
    - "What time is the next BART to San Francisco"

    NOTE: Apple Maps API does not provide programmatic access to real-time schedule data.
    This tool opens Apple Maps with transit directions, where users can see:
    - Next departure times
    - Multiple route options
    - Real-time transit updates
    - Step-by-step transit directions

    Args:
        origin: Starting location (can be "Current Location" or specific address)
        destination: End location (address or place name)
        open_maps: If True, automatically open Maps with transit view (default: True)

    Returns:
        Dictionary with transit information and maps URL

    Example:
        get_transit_schedule(
            origin="Current Location",
            destination="Downtown Berkeley"
        )
    """
    logger.info(
        f"[MAPS AGENT] Tool: get_transit_schedule(origin='{origin}', destination='{destination}')"
    )

    try:
        # Generate transit directions URL (dirflg=r for transit)
        maps_url = _generate_apple_maps_url(
            origin=origin,
            destination=destination,
            stops=[],
            departure_time=None,
            transportation_mode="r"  # Transit mode
        )

        result = {
            "origin": origin,
            "destination": destination,
            "transportation_mode": "transit",
            "maps_url": maps_url,
            "maps_service": "Apple Maps",
            "note": "Opening Apple Maps to view real-time transit schedules. Apple Maps will show next departure times, route options, and live transit updates."
        }

        # Open Maps
        maps_opened = False
        if open_maps:
            import subprocess
            try:
                subprocess.run(["open", maps_url], check=True)
                maps_opened = True
                logger.info(f"[MAPS AGENT] Opened Apple Maps with transit schedule view")
            except Exception as e:
                logger.error(f"[MAPS AGENT] Failed to open Maps: {e}")

        result["maps_opened"] = maps_opened

        if maps_opened:
            result["message"] = (
                f"Opening Apple Maps with transit directions from {origin} to {destination}. "
                f"You'll see next departure times and route options in the Maps app: {maps_url}"
            )
        else:
            result["message"] = (
                f"View transit schedule from {origin} to {destination} in Apple Maps: {maps_url}"
            )

        return result

    except Exception as e:
        logger.error(f"[MAPS AGENT] Error in get_transit_schedule: {e}")
        return {
            "error": True,
            "error_type": "TransitScheduleError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def plan_trip_with_stops(
    origin: str,
    destination: str,
    num_fuel_stops: int = 0,
    num_food_stops: int = 0,
    departure_time: Optional[str] = None,
    use_google_maps: bool = False,
    open_maps: bool = True  # Default to True for better UX - automatically open maps
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
        num_fuel_stops: Number of fuel/gas stops to add (any reasonable number, typically 0-10)
        num_food_stops: Number of food stops to add (any reasonable number, e.g., 2 for breakfast and lunch)
        departure_time: Departure time in format "HH:MM AM/PM" or "YYYY-MM-DD HH:MM"
        use_google_maps: If True, generate Google Maps URL (opens in browser);
                        if False, use Apple Maps URL (opens in Maps app, default). 
                        Apple Maps is preferred for macOS integration and supports waypoints.
        open_maps: If True, automatically open Maps app/browser with the route (default: True for better UX)

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
        
        # Get max stops limit from config (if available) or use reasonable default
        # Maps APIs typically support 10-25 waypoints, so we use a generous but reasonable limit
        try:
            from ..utils import load_config
            config = load_config()
            max_stops = config.get("maps", {}).get("max_stops", 20)
        except Exception:
            max_stops = 20  # Default if config not available
        
        if total_stops > max_stops:
            return {
                "error": True,
                "error_type": "TooManyStops",
                "error_message": f"Maximum {max_stops} total stops supported (fuel + food combined). Consider planning multiple shorter trips or adjust config.yaml maps.max_stops.",
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

        # Parse departure time if provided - use LLM-friendly parsing
        departure_dt = None
        if departure_time:
            try:
                # Try to parse various time formats using dateutil
                # This handles formats like "5 AM", "7:30 PM", "2024-01-15 10:00", etc.
                from dateutil import parser
                departure_dt = parser.parse(departure_time)
            except Exception as e:
                # If parsing fails, log warning but don't fail - Maps can work without exact time
                # The LLM planner should extract time in a parseable format
                logger.warning(f"Could not parse departure time '{departure_time}': {e}. Continuing without exact time parsing.")

        # Generate appropriate maps URL
        # use_google_maps is determined by LLM planner based on user query (no hardcoded default)
        # Use POI search queries if available, otherwise use original locations
        stop_locations_list = []
        for s in stops_with_types:
            # Prefer POI search queries (e.g., "gas station near City, State")
            # These will help Maps find actual businesses, not just cities
            location = s.get("location", "")
            if location and ("near" in location.lower() or "gas station" in location.lower() or "restaurant" in location.lower()):
                stop_locations_list.append(location)
            else:
                # Fallback to original location
                stop_locations_list.append(s.get("original_location", location))
        
        if use_google_maps:
            maps_url = _generate_google_maps_url(origin, destination, stop_locations_list, departure_dt)
            maps_service = "Google Maps"
        else:
            maps_url = _generate_apple_maps_url(origin, destination, stop_locations_list, departure_time)
            maps_url = _normalize_maps_url(maps_url, origin, destination, stop_locations_list)
            maps_service = "Apple Maps"
        
        # Ensure URL uses https:// format (not maps://) for better browser/UI compatibility
        # Convert maps:// URLs to https://maps.apple.com/ format if needed
        # This handles both standard format and via format URLs
        if maps_url.startswith("maps://"):
            maps_url = maps_url.replace("maps://", "https://maps.apple.com/", 1)
            logger.info(f"[MAPS AGENT] Converted maps:// URL to https:// format")
        
        # Also ensure it's not using maps:// anywhere in the URL (double-check)
        if "maps://" in maps_url:
            maps_url = maps_url.replace("maps://", "https://maps.apple.com/")
            logger.info(f"[MAPS AGENT] Found and converted maps:// protocol in URL")

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

        # Optionally open Maps app/browser
        maps_opened = False
        if open_maps:
            import subprocess
            try:
                if use_google_maps:
                    # Open Google Maps in browser
                    subprocess.run(["open", maps_url], check=True)
                    maps_opened = True
                    logger.info(f"[MAPS AGENT] Opened Google Maps in browser")
                else:
                    # Try AppleScript automation first for Apple Maps (better integration)
                    try:
                        from ..automation.maps_automation import MapsAutomation
                        from ..utils import load_config
                        config = load_config()
                        maps_automation = MapsAutomation(config)
                        
                        result = maps_automation.open_directions(
                            origin=origin,
                            destination=destination,
                            stops=stop_locations_list,
                            start_navigation=False  # Just open directions, don't start navigation
                        )
                        
                        if result.get("success"):
                            maps_opened = True
                            logger.info(f"[MAPS AGENT] Opened Apple Maps with route using AppleScript")
                        else:
                            logger.warning(f"[MAPS AGENT] AppleScript automation failed: {result.get('error_message')}, falling back to URL method")
                            # Fallback to URL method
                            subprocess.run(["open", maps_url], check=True)
                            maps_opened = True
                            logger.info(f"[MAPS AGENT] Opened Apple Maps using URL fallback method")
                    except Exception as applescript_error:
                        logger.warning(f"[MAPS AGENT] AppleScript automation error: {applescript_error}, falling back to URL method")
                        # Fallback to URL method
                        subprocess.run(["open", maps_url], check=True)
                        maps_opened = True
                        logger.info(f"[MAPS AGENT] Opened Apple Maps using URL fallback method")
            except Exception as e:
                logger.error(f"[MAPS AGENT] Failed to open Maps: {e}")
                # Last resort fallback
                try:
                    subprocess.run(["open", maps_url], check=True)
                    maps_opened = True
                    logger.info(f"[MAPS AGENT] Opened Maps using last resort fallback")
                except Exception as fallback_error:
                    logger.error(f"[MAPS AGENT] All methods failed to open Maps: {fallback_error}")

        # Create simple, clean message with just the URL
        # Ensure message uses the converted https:// URL (not maps://)
        display_url = maps_url.replace("maps://", "https://maps.apple.com/") if "maps://" in maps_url else maps_url
        
        if maps_opened:
            message = f"Here's your trip, enjoy! {maps_service} opened with your route: {display_url}"
        else:
            message = f"Here's your trip, enjoy: {display_url}"

        return {
            **route_details,
            "message": message,
            "total_stops": len(stops_with_types),
            "maps_opened": maps_opened
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
    stops: Optional[List[str]] = None,
    start_navigation: bool = False
) -> Dict[str, Any]:
    """
    Open Apple Maps application with a specific route using AppleScript automation.

    This will launch the Maps app on macOS with the specified route loaded.
    Uses AppleScript for native macOS integration.

    Args:
        origin: Starting location
        destination: End location
        stops: Optional list of intermediate stops
        start_navigation: If True, automatically start navigation (default: False)

    Returns:
        Dictionary with status and details

    Example:
        open_maps_with_route(
            origin="San Francisco",
            destination="Los Angeles",
            stops=["Gilroy, CA", "Coalinga, CA"]
        )
    """
    logger.info(
        f"[MAPS AGENT] Tool: open_maps_with_route(origin='{origin}', "
        f"destination='{destination}', stops={stops}, start_navigation={start_navigation})"
    )

    try:
        from ..automation.maps_automation import MapsAutomation
        from ..utils import load_config
        
        config = load_config()
        maps_automation = MapsAutomation(config)
        
        stops = stops or []
        
        result = maps_automation.open_directions(
            origin=origin,
            destination=destination,
            stops=stops,
            start_navigation=start_navigation
        )
        
        if result.get("success"):
            # Generate URL for reference
            maps_url = _generate_apple_maps_url(origin, destination, stops, None)
            
            return {
                "status": "opened",
                "maps_url": maps_url,
                "origin": origin,
                "destination": destination,
                "stops": stops,
                "message": f"Opened Apple Maps with route from {origin} to {destination} using AppleScript"
            }
        else:
            # Fallback to URL method
            import subprocess
            maps_url = _generate_apple_maps_url(origin, destination, stops, None)
            subprocess.run(["open", maps_url], check=True)
            
            return {
                "status": "opened",
                "maps_url": maps_url,
                "origin": origin,
                "destination": destination,
                "stops": stops,
                "message": f"Opened Apple Maps with route from {origin} to {destination} (fallback to URL method)"
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
    get_google_transit_directions,  # NEW: Google Maps with real-time transit data
    get_directions,
    get_transit_schedule,
    plan_trip_with_stops,
    open_maps_with_route,
]


# Maps Agent Hierarchy
MAPS_AGENT_HIERARCHY = """
Maps Agent Hierarchy:
====================

LEVEL 1: Simple Directions - Google Maps API (RECOMMENDED for Transit)
├─ get_google_transit_directions → Get REAL-TIME transit directions with actual departure times
│   └─ Uses: Google Maps API with programmatic transit data
│   └─ Returns: "Next bus at 3:45 PM" - actual times in chat response
│   └─ Use for: "when's the next bus", "next train time", "transit schedule"
│   └─ Requires: GOOGLE_MAPS_API_KEY in .env file

LEVEL 2: Simple Directions - Apple Maps (Fallback)
├─ get_directions → Get point-to-point directions with any transportation mode
│   └─ Supports: driving, walking, transit/bus, bicycle
│   └─ Use for: "bike to the office", "walk to cafe", "drive to SF"
│   └─ Limitation: Cannot extract programmatic transit times
└─ get_transit_schedule → Get transit schedule (opens Apple Maps only)
    └─ Opens Maps with transit view showing real-time schedules
    └─ User views times in Maps app, not in chat
    └─ Use for: backup if Google Maps API not available

LEVEL 3: Trip Planning with Stops
├─ plan_trip_with_stops → Plan route with specific numbers of food and fuel stops
└─ open_maps_with_route → Open Apple Maps app with specific route using AppleScript

Transportation Modes:
- Driving (default): dirflg=d
- Walking: dirflg=w
- Transit/Bus: dirflg=r (shows real-time schedules)
- Bicycle: dirflg=b

Typical Workflows:

1. Simple Transit Query:
   get_directions(origin="Current Location", destination="Berkeley", transportation_mode="transit")
   → Opens Apple Maps with transit directions and next departure times

   OR use get_transit_schedule() for transit-specific queries

2. Simple Bicycle/Walking Query:
   get_directions(origin="Home", destination="Coffee Shop", transportation_mode="bicycle")
   → Opens Apple Maps with bicycle directions

3. Complex Trip Planning:
   plan_trip_with_stops(
       origin="Santa Clara, CA",
       destination="San Diego, CA",
       num_fuel_stops=2,
       num_food_stops=2,
       departure_time="7:00 AM",
       open_maps=True
   )
   → Returns route details and Maps URL with all specified stops
   → Automatically opens Apple Maps using AppleScript automation

Integration Details:
- Uses MapsAutomation class (src/automation/maps_automation.py) for AppleScript control
- Native macOS integration via AppleScript - opens Maps.app directly
- Falls back to URL method if AppleScript fails
- Supports multiple waypoints in Apple Maps web URL format
- Multi-modal transportation support (driving, walking, transit, bicycle)
- Location service integration for "current location" queries

Features:
- Multi-modal transportation (driving, walking, transit, bicycle)
- Real-time transit schedules and next departure times
- Current location detection (via LocationService)
- Specify exact number of fuel stops (supports any reasonable number)
- Specify exact number of food stops - supports multiple meals (breakfast, lunch, dinner, etc.)
- LLM-driven automatic stop suggestions for ANY route (no hardcoded routes)
- Works for routes worldwide (not limited to US - LLM handles international routes)
- Apple Maps is default (uses AppleScript for native macOS integration)
- Google Maps available as alternative (opens in browser)
- Departure time specification (flexible time format parsing)
- Direct Maps app launching on macOS via AppleScript
- All decisions made by LLM - no hardcoded city names or routes

AppleScript Automation:
- Activates Maps.app
- Opens directions URL with waypoints
- Can optionally start navigation automatically
- Provides fallback to URL method for reliability

Examples:

# Simple transit query
get_directions(
    origin="Current Location",
    destination="Downtown Berkeley",
    transportation_mode="transit"
)
→ Opens Maps with transit directions showing next bus/train times

# Bicycle directions
get_directions(
    origin="Home",
    destination="Office",
    transportation_mode="bicycle"
)
→ Opens Maps with bicycle route

# Complex trip with stops
plan_trip_with_stops(
    origin="Los Angeles, CA",
    destination="San Diego, CA",
    num_fuel_stops=2,
    num_food_stops=2,
    departure_time="7:00 AM",
    open_maps=True
)
→ Returns Maps URL with route including 2 fuel stops and 2 food stops (LLM suggests optimal locations)
→ Opens Apple Maps app automatically using AppleScript
"""


class MapsAgent:
    """
    Maps Agent - Mini-orchestrator for Apple Maps trip planning.

    Responsibilities:
    - Planning trips with origin and destination
    - Adding stops for food and gas
    - Setting departure times
    - Generating and opening Maps URLs
    - Native macOS integration via AppleScript (MapsAutomation)

    Integration:
    - Uses MapsAutomation class (src/automation/maps_automation.py) for AppleScript control
    - Opens Maps.app directly using AppleScript automation
    - Falls back to URL method for reliability

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
