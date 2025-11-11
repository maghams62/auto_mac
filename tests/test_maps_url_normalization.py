"""
Unit tests for Maps URL normalization helpers.

These tests avoid hitting the LLM by exercising the pure utility logic that
rewrites legacy Apple Maps URLs (maps:// with `via` segments) into the modern
https://maps.apple.com/ format with explicit waypoints.
"""

import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

# Ensure src package is on path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agent.maps_agent import _normalize_maps_url, _generate_apple_maps_url


def test_normalize_maps_url_converts_maps_scheme_and_via_segments():
    origin = "San Francisco, CA"
    destination = "New York, NY"
    stops = [
        "gas station near Salt Lake City, UT, USA",
        "gas station near Des Moines, IA, USA",
    ]

    legacy_url = (
        "maps://?saddr=San%20Francisco%2C%20CA"
        "&daddr=New%20York%2C%20NY%20via%20Salt%20Lake%20City%2C%20UT%2C%20USA%2C%20Des%20Moines%2C%20IA%2C%20USA"
        "&dirflg=d"
    )

    normalized = _normalize_maps_url(legacy_url, origin, destination, stops)

    assert normalized.startswith("https://maps.apple.com/")
    assert "maps://" not in normalized
    assert "%20via%20" not in normalized

    parsed = urlparse(normalized)
    params = parse_qs(parsed.query)
    daddr_values = params.get("daddr", [])

    # Expect one entry per stop plus the final destination
    assert len(daddr_values) == len(stops) + 1
    assert unquote(daddr_values[-1]) == destination
    assert unquote(daddr_values[0]).startswith("gas station near")


def test_normalize_maps_url_is_noop_for_clean_url():
    origin = "San Francisco, CA"
    destination = "Los Angeles, CA"
    stops = ["gas station near Kettleman City, CA, USA"]

    clean_url = _generate_apple_maps_url(origin, destination, stops)
    normalized = _normalize_maps_url(clean_url, origin, destination, stops)

    assert normalized == clean_url
