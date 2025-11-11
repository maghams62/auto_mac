"""
API Parameter Validator - Defensive programming for external APIs.

This module provides validation utilities to ensure we only send parameters
that are actually supported by external APIs, preventing errors from
unsupported parameters.

Key Principle: Never assume all endpoints support the same parameters.
Always validate against the API's actual capabilities.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class APIEndpoint:
    """
    Represents an API endpoint with its supported parameters.

    Attributes:
        name: Human-readable endpoint name
        url_pattern: URL pattern for this endpoint
        supported_params: Set of parameter names this endpoint accepts
        required_params: Set of parameters that are required
        description: Brief description of what this endpoint does
    """
    name: str
    url_pattern: str
    supported_params: Set[str]
    required_params: Set[str] = None
    description: str = ""

    def __post_init__(self):
        if self.required_params is None:
            self.required_params = set()


class APIValidator:
    """
    Validates parameters against API endpoint capabilities.

    Prevents sending unsupported parameters that would cause 400 errors.
    """

    def __init__(self, api_name: str):
        """
        Initialize validator for a specific API.

        Args:
            api_name: Name of the API (e.g., "Twitter", "Google Maps")
        """
        self.api_name = api_name
        self.endpoints: Dict[str, APIEndpoint] = {}

    def register_endpoint(self, endpoint: APIEndpoint) -> None:
        """Register an API endpoint with its supported parameters."""
        self.endpoints[endpoint.name] = endpoint
        logger.debug(f"[{self.api_name}] Registered endpoint: {endpoint.name}")

    def validate_params(
        self,
        endpoint_name: str,
        params: Dict[str, Any],
        strict: bool = False
    ) -> Dict[str, Any]:
        """
        Validate and filter parameters for an endpoint.

        Args:
            endpoint_name: Name of the endpoint to validate against
            params: Parameters to validate
            strict: If True, raise exception on invalid params. If False, log warning and filter.

        Returns:
            Filtered dictionary containing only supported parameters

        Raises:
            ValueError: If strict=True and unsupported parameters are found
        """
        if endpoint_name not in self.endpoints:
            logger.warning(
                f"[{self.api_name}] Unknown endpoint: {endpoint_name}. "
                f"Returning params unvalidated."
            )
            return params

        endpoint = self.endpoints[endpoint_name]
        validated = {}
        unsupported = []
        missing_required = []

        # Check for unsupported parameters
        for key, value in params.items():
            if key in endpoint.supported_params:
                validated[key] = value
            else:
                unsupported.append(key)
                logger.warning(
                    f"[{self.api_name}] Endpoint '{endpoint_name}' does not support "
                    f"parameter '{key}'. Filtering it out. "
                    f"Supported params: {sorted(endpoint.supported_params)}"
                )

        # Check for missing required parameters
        for required_param in endpoint.required_params:
            if required_param not in params:
                missing_required.append(required_param)

        if missing_required:
            error_msg = (
                f"[{self.api_name}] Endpoint '{endpoint_name}' missing required "
                f"parameters: {missing_required}"
            )
            logger.error(error_msg)
            if strict:
                raise ValueError(error_msg)

        if unsupported and strict:
            raise ValueError(
                f"[{self.api_name}] Endpoint '{endpoint_name}' does not support "
                f"parameters: {unsupported}"
            )

        if unsupported:
            logger.info(
                f"[{self.api_name}] Filtered out {len(unsupported)} unsupported "
                f"parameter(s) for '{endpoint_name}': {unsupported}"
            )

        return validated

    def get_endpoint_info(self, endpoint_name: str) -> Optional[APIEndpoint]:
        """Get information about an endpoint's capabilities."""
        return self.endpoints.get(endpoint_name)

    def list_endpoints(self) -> List[str]:
        """List all registered endpoint names."""
        return list(self.endpoints.keys())

    def get_supported_params(self, endpoint_name: str) -> Optional[Set[str]]:
        """Get the set of supported parameters for an endpoint."""
        endpoint = self.endpoints.get(endpoint_name)
        return endpoint.supported_params if endpoint else None


# Pre-configured validators for common APIs

def create_twitter_validator() -> APIValidator:
    """
    Create validator for Twitter API v2.

    Reference: https://developer.twitter.com/en/docs/twitter-api/tweets/lookup/api-reference
    """
    validator = APIValidator("Twitter API v2")

    # Lists endpoint - does NOT support start_time
    validator.register_endpoint(APIEndpoint(
        name="lists_tweets",
        url_pattern="/2/lists/:id/tweets",
        supported_params={
            "max_results",
            "pagination_token",
            "expansions",
            "tweet.fields",
            "media.fields",
            "poll.fields",
            "place.fields",
            "user.fields"
        },
        description="Get tweets from a Twitter List (does NOT support time filtering)"
    ))

    # Search endpoint - DOES support start_time
    validator.register_endpoint(APIEndpoint(
        name="search_recent",
        url_pattern="/2/tweets/search/recent",
        supported_params={
            "query",
            "start_time",
            "end_time",
            "max_results",
            "pagination_token",
            "expansions",
            "tweet.fields",
            "media.fields",
            "poll.fields",
            "place.fields",
            "user.fields",
            "sort_order"
        },
        required_params={"query"},
        description="Search recent tweets (supports time filtering)"
    ))

    return validator


def create_google_maps_validator() -> APIValidator:
    """
    Create validator for Google Maps APIs.

    Different Maps endpoints support different parameters.
    """
    validator = APIValidator("Google Maps API")

    # Directions API
    validator.register_endpoint(APIEndpoint(
        name="directions",
        url_pattern="/maps/api/directions/json",
        supported_params={
            "origin",
            "destination",
            "mode",
            "waypoints",
            "alternatives",
            "avoid",
            "language",
            "units",
            "region",
            "arrival_time",
            "departure_time",
            "traffic_model",
            "transit_mode",
            "transit_routing_preference",
            "key"
        },
        required_params={"origin", "destination"},
        description="Get directions between locations"
    ))

    # Places API
    validator.register_endpoint(APIEndpoint(
        name="places_search",
        url_pattern="/maps/api/place/nearbysearch/json",
        supported_params={
            "location",
            "radius",
            "keyword",
            "type",
            "name",
            "language",
            "minprice",
            "maxprice",
            "opennow",
            "rankby",
            "pagetoken",
            "key"
        },
        required_params={"location"},
        description="Search for places near a location"
    ))

    return validator


def create_playwright_validator() -> APIValidator:
    """
    Create validator for Playwright browser automation.

    Different browser methods support different parameters.
    """
    validator = APIValidator("Playwright")

    # page.goto()
    validator.register_endpoint(APIEndpoint(
        name="page_goto",
        url_pattern="page.goto(url, options)",
        supported_params={
            "timeout",
            "wait_until",
            "referer"
        },
        description="Navigate to URL"
    ))

    # page.screenshot()
    validator.register_endpoint(APIEndpoint(
        name="page_screenshot",
        url_pattern="page.screenshot(options)",
        supported_params={
            "path",
            "type",
            "quality",
            "full_page",
            "clip",
            "omit_background",
            "timeout"
        },
        description="Take screenshot of page"
    ))

    return validator


# Example usage patterns
USAGE_EXAMPLES = """
# Example 1: Twitter API validation

validator = create_twitter_validator()

# This will filter out 'start_time' for lists endpoint
params = {
    "max_results": 100,
    "start_time": "2025-01-01T00:00:00Z",  # NOT supported by lists endpoint
    "tweet.fields": "created_at,author_id"
}

validated = validator.validate_params("lists_tweets", params)
# Result: {'max_results': 100, 'tweet.fields': 'created_at,author_id'}
# 'start_time' filtered out with warning

# Example 2: Check what's supported

supported = validator.get_supported_params("lists_tweets")
print(f"Lists endpoint supports: {supported}")

# Example 3: Strict mode (raise error on invalid params)

try:
    validated = validator.validate_params("lists_tweets", params, strict=True)
except ValueError as e:
    print(f"Validation error: {e}")
"""
