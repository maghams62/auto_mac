import sys
from pathlib import Path
from unittest.mock import patch, mock_open
import json
import tempfile
import os

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.knowledge_providers.wiki import lookup_wikipedia


class MockResponse:
    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            from requests.exceptions import HTTPError
            raise HTTPError(f"HTTP {self.status_code}")


@pytest.fixture(autouse=True)
def openai_stub(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def test_wiki_lookup_success(monkeypatch):
    """Test successful Wikipedia lookup."""
    # Mock successful Wikipedia API response
    mock_wikipedia_response = {
        "title": "Python (programming language)",
        "extract": "Python is a high-level programming language known for its simplicity and readability.",
        "content_urls": {
            "desktop": {
                "page": "https://en.wikipedia.org/wiki/Python_(programming_language)"
            }
        }
    }

    config = {
        "knowledge_providers": {
            "wiki_lookup": {
                "enabled": True,
                "cache_dir": "data/cache/knowledge",
                "cache_ttl_hours": 24,
                "timeout_seconds": 10,
                "max_retries": 2
            }
        }
    }

    def mock_requests_get(url, timeout=None):
        return MockResponse(mock_wikipedia_response)

    def mock_load_config():
        return config

    monkeypatch.setattr("src.knowledge_providers.wiki.requests.get", mock_requests_get)
    monkeypatch.setattr("src.utils.load_config", mock_load_config)

    result = lookup_wikipedia("SomeVeryUnlikelyCachedQuery12345", None)  # Force it to call load_config

    assert not result.error
    assert result.title == "Python (programming language)"
    assert "Python is a high-level" in result.summary
    assert result.url == "https://en.wikipedia.org/wiki/Python_(programming_language)"
    assert result.confidence == 1.0
    assert result.error_type == ""
    assert result.error_message == ""


def test_wiki_lookup_not_found(monkeypatch):
    """Test Wikipedia lookup for non-existent page."""
    config = {
        "knowledge_providers": {
            "wiki_lookup": {
                "enabled": True,
                "cache_dir": "data/cache/knowledge",
                "cache_ttl_hours": 24,
                "timeout_seconds": 10,
                "max_retries": 2
            }
        }
    }

    def mock_requests_get(url, timeout=None):
        # Simulate 404 response
        return MockResponse({}, status_code=404)

    def mock_load_config():
        return config

    monkeypatch.setattr("src.knowledge_providers.wiki.requests.get", mock_requests_get)
    monkeypatch.setattr("src.utils.load_config", mock_load_config)

    result = lookup_wikipedia("NonExistentPage12345", config)

    assert result.error
    assert result.error_type == "NotFound"
    assert "No Wikipedia page found" in result.error_message
    assert result.title == ""
    assert result.summary == ""
    assert result.url == ""
    assert result.confidence == 0.0


def test_wiki_lookup_timeout(monkeypatch):
    """Test Wikipedia lookup with timeout."""
    config = {
        "knowledge_providers": {
            "wiki_lookup": {
                "enabled": True,
                "cache_dir": "data/cache/knowledge",
                "cache_ttl_hours": 24,
                "timeout_seconds": 10,
                "max_retries": 2
            }
        }
    }

    def mock_requests_get(url, timeout=None):
        from requests.exceptions import Timeout
        raise Timeout("Connection timed out")

    def mock_load_config():
        return config

    monkeypatch.setattr("src.knowledge_providers.wiki.requests.get", mock_requests_get)
    monkeypatch.setattr("src.utils.load_config", mock_load_config)

    result = lookup_wikipedia("SomeVeryUnlikelyCachedQuery12345", None)  # Force it to call load_config

    assert result.error
    assert result.error_type == "Timeout"
    assert "Wikipedia API timeout" in result.error_message
    assert result.confidence == 0.0


def test_wiki_lookup_network_error(monkeypatch):
    """Test Wikipedia lookup with network error."""
    config = {
        "knowledge_providers": {
            "wiki_lookup": {
                "enabled": True,
                "cache_dir": "data/cache/knowledge",
                "cache_ttl_hours": 24,
                "timeout_seconds": 10,
                "max_retries": 2
            }
        }
    }

    def mock_requests_get(url, timeout=None):
        from requests.exceptions import RequestException
        raise RequestException("Network error")

    def mock_load_config():
        return config

    monkeypatch.setattr("src.knowledge_providers.wiki.requests.get", mock_requests_get)
    monkeypatch.setattr("src.utils.load_config", mock_load_config)

    result = lookup_wikipedia("SomeVeryUnlikelyCachedQuery12345", None)  # Force it to call load_config

    assert result.error
    assert result.error_type == "NetworkError"
    assert "Network error" in result.error_message
    assert result.confidence == 0.0


def test_wiki_lookup_disabled(monkeypatch):
    """Test Wikipedia lookup when disabled in config."""
    config = {
        "knowledge_providers": {
            "wiki_lookup": {
                "enabled": False
            }
        }
    }

    def mock_load_config():
        return config

    monkeypatch.setattr("src.utils.load_config", mock_load_config)

    result = lookup_wikipedia("SomeVeryUnlikelyCachedQuery12345", None)  # Force it to call load_config

    assert result.error
    assert result.error_type == "DisabledProvider"
    assert "Wikipedia lookup is disabled" in result.error_message
    assert result.confidence == 0.0


def test_wiki_lookup_with_cache(monkeypatch, tmp_path):
    """Test Wikipedia lookup with caching."""
    cache_dir = tmp_path / "cache"
    test_query = "CachedTestQuery"

    # Create cache directory
    cache_dir.mkdir(parents=True)

    # Create existing cache file for the test query
    cached_data = {
        "title": "Test Article",
        "summary": "Cached summary content",
        "url": "https://en.wikipedia.org/wiki/Test_Article",
        "confidence": 1.0,
        "error": False,
        "error_type": "",
        "error_message": ""
    }

    # Create the cache file with the correct name
    safe_name = "".join(c for c in test_query if c.isalnum() or c in "._- ").replace(" ", "_")
    cache_file = cache_dir / f"wiki_{safe_name}.json"

    with open(cache_file, 'w') as f:
        json.dump(cached_data, f)

    config = {
        "knowledge_providers": {
            "wiki_lookup": {
                "enabled": True,
                "cache_dir": str(cache_dir),
                "cache_ttl_hours": 24,
                "timeout_seconds": 10,
                "max_retries": 2
            }
        }
    }

    def mock_load_config():
        return config

    # Mock requests.get to ensure it's not called
    requests_get_called = False
    def mock_requests_get(url, timeout=None):
        nonlocal requests_get_called
        requests_get_called = True
        return MockResponse({})

    monkeypatch.setattr("src.utils.load_config", mock_load_config)
    monkeypatch.setattr("src.knowledge_providers.wiki.requests.get", mock_requests_get)

    result = lookup_wikipedia(test_query, None)  # Force it to call load_config

    # Should use cached result, not make API call
    assert not requests_get_called
    assert not result.error
    assert result.title == "Test Article"
    assert result.summary == "Cached summary content"
    assert result.confidence == 1.0


def test_wiki_lookup_json_parse_error(monkeypatch):
    """Test Wikipedia lookup with invalid JSON response."""
    config = {
        "knowledge_providers": {
            "wiki_lookup": {
                "enabled": True,
                "cache_dir": "data/cache/knowledge",
                "cache_ttl_hours": 24,
                "timeout_seconds": 10,
                "max_retries": 2
            }
        }
    }

    class BadJsonResponse:
        def json(self):
            raise ValueError("Invalid JSON")

        def raise_for_status(self):
            pass

    def mock_requests_get(url, timeout=None):
        return BadJsonResponse()

    def mock_load_config():
        return config

    monkeypatch.setattr("src.knowledge_providers.wiki.requests.get", mock_requests_get)
    monkeypatch.setattr("src.utils.load_config", mock_load_config)

    result = lookup_wikipedia("SomeVeryUnlikelyCachedQuery12345", None)  # Force it to call load_config

    assert result.error
    assert result.error_type == "ParseError"
    assert "Failed to parse Wikipedia response" in result.error_message
    assert result.confidence == 0.0
