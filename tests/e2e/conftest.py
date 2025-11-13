"""
End-to-End Test Configuration and Fixtures

This module provides:
- Pytest fixtures for e2e test setup
- Mock configurations for external services
- Test data management
- API client utilities
- UI test helpers
- Telemetry capture utilities
"""

import pytest
import asyncio
import json
import os
import tempfile
import shutil
import time
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional, Generator
from datetime import datetime, timedelta
from contextlib import contextmanager

# Test configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
UI_BASE_URL = os.getenv("UI_BASE_URL", "http://localhost:3000")
TEST_TIMEOUT = int(os.getenv("TEST_TIMEOUT", "120"))

# Test data directories
E2E_TEST_DATA_DIR = Path(__file__).parent / "data"
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
REPORTS_DIR = Path(__file__).parent.parent / "data" / "test_results"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_session_id():
    """Generate a unique test session ID."""
    return f"e2e-{int(time.time())}"


@pytest.fixture(scope="session")
def api_client(test_session_id):
    """Provide an API client for making requests to the backend."""
    class APIClient:
        def __init__(self, base_url: str, session_id: str):
            self.base_url = base_url
            self.session_id = session_id
            self.session = requests.Session()

        def post(self, endpoint: str, data: Dict[str, Any], timeout: int = TEST_TIMEOUT) -> Dict[str, Any]:
            """Make a POST request to the API."""
            url = f"{self.base_url}{endpoint}"
            payload = {"session_id": self.session_id, **data}

            try:
                response = self.session.post(url, json=payload, timeout=timeout)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                return {"error": str(e), "status_code": getattr(response, 'status_code', None)}

        def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, timeout: int = TEST_TIMEOUT) -> Dict[str, Any]:
            """Make a GET request to the API."""
            url = f"{self.base_url}{endpoint}"

            try:
                response = self.session.get(url, params=params, timeout=timeout)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                return {"error": str(e), "status_code": getattr(response, 'status_code', None)}

        def chat(self, message: str, **kwargs) -> Dict[str, Any]:
            """Send a chat message."""
            return self.post("/api/chat", {"message": message, **kwargs})

        def wait_for_completion(self, max_wait: int = 60) -> List[Dict[str, Any]]:
            """Wait for workflow completion and return all messages."""
            messages = []
            start_time = time.time()

            while time.time() - start_time < max_wait:
                response = self.get("/api/messages")
                if response.get("error"):
                    break

                new_messages = response.get("messages", [])
                if new_messages:
                    messages.extend(new_messages)
                    # Check if workflow is complete
                    latest_message = new_messages[-1]
                    if latest_message.get("type") in ["completion", "error"]:
                        break

                time.sleep(1)

            return messages

    return APIClient(API_BASE_URL, test_session_id)


@pytest.fixture(scope="session")
def mock_services():
    """Provide mock service configurations for testing."""
    return {
        "gmail": {
            "enabled": True,
            "mock_emails": [
                {
                    "id": "test_001",
                    "subject": "Test Email 1",
                    "sender": "test@example.com",
                    "body": "This is a test email body",
                    "timestamp": datetime.now().isoformat()
                }
            ]
        },
        "calendar": {
            "enabled": True,
            "mock_events": [
                {
                    "id": "event_001",
                    "title": "Test Meeting",
                    "start": (datetime.now() + timedelta(hours=1)).isoformat(),
                    "end": (datetime.now() + timedelta(hours=2)).isoformat(),
                    "location": "Conference Room A"
                }
            ]
        },
        "spotify": {
            "enabled": True,
            "mock_tracks": [
                {
                    "id": "track_001",
                    "name": "Test Song",
                    "artist": "Test Artist",
                    "uri": "spotify:track:test123"
                }
            ]
        },
        "bluesky": {
            "enabled": True,
            "mock_posts": [
                {
                    "id": "post_001",
                    "text": "Test Bluesky post",
                    "author": "test.bsky.social",
                    "timestamp": datetime.now().isoformat()
                }
            ]
        }
    }


@pytest.fixture(scope="function")
def temp_test_dir():
    """Provide a temporary directory for test artifacts."""
    temp_path = tempfile.mkdtemp(prefix="e2e_test_")
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture(scope="function")
def test_artifacts_dir(temp_test_dir):
    """Provide directories for storing test artifacts."""
    artifacts = {
        "screenshots": temp_test_dir / "screenshots",
        "presentations": temp_test_dir / "presentations",
        "emails": temp_test_dir / "emails",
        "reports": temp_test_dir / "reports"
    }

    for dir_path in artifacts.values():
        dir_path.mkdir(parents=True, exist_ok=True)

    return artifacts


@pytest.fixture(scope="session")
def telemetry_collector():
    """Provide a telemetry collector for capturing test execution data."""
    class TelemetryCollector:
        def __init__(self):
            self.events = []

        def record_event(self, event_type: str, data: Dict[str, Any]):
            """Record a telemetry event."""
            event = {
                "timestamp": datetime.now().isoformat(),
                "type": event_type,
                "data": data
            }
            self.events.append(event)

        def get_events(self, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
            """Get recorded events, optionally filtered by type."""
            if event_type:
                return [e for e in self.events if e["type"] == event_type]
            return self.events

        def save_to_file(self, file_path: Path):
            """Save telemetry data to file."""
            with open(file_path, 'w') as f:
                json.dump(self.events, f, indent=2)

    return TelemetryCollector()


@pytest.fixture(scope="function")
def success_criteria_checker():
    """Provide a utility for checking test success criteria."""
    class SuccessCriteriaChecker:
        def __init__(self):
            self.criteria_results = {}

        def check_response_length(self, response: str, min_length: int) -> bool:
            """Check if response meets minimum length requirement."""
            result = len(response.strip()) >= min_length
            self.criteria_results["response_length"] = {
                "required": min_length,
                "actual": len(response.strip()),
                "passed": result
            }
            return result

        def check_keywords_present(self, response: str, keywords: List[str]) -> bool:
            """Check if required keywords are present in response."""
            response_lower = response.lower()
            results = {}

            for keyword in keywords:
                present = keyword.lower() in response_lower
                results[keyword] = present

            passed = all(results.values())
            self.criteria_results["keywords_present"] = {
                "required": keywords,
                "results": results,
                "passed": passed
            }
            return passed

        def check_no_errors(self, response: Dict[str, Any]) -> bool:
            """Check that response contains no errors."""
            has_error = "error" in response or "failed" in response.get("message", "").lower()
            self.criteria_results["no_errors"] = {
                "has_error": has_error,
                "passed": not has_error
            }
            return not has_error

        def check_attachment_present(self, attachments: List[Dict[str, Any]], filename_pattern: str) -> bool:
            """Check if attachment with specific filename pattern is present."""
            for attachment in attachments:
                if filename_pattern in attachment.get("filename", ""):
                    self.criteria_results["attachment_present"] = {
                        "pattern": filename_pattern,
                        "found": True,
                        "passed": True
                    }
                    return True

            self.criteria_results["attachment_present"] = {
                "pattern": filename_pattern,
                "found": False,
                "passed": False
            }
            return False

        def check_workflow_steps(self, messages: List[Dict[str, Any]], expected_steps: List[str]) -> bool:
            """Check if workflow executed expected steps."""
            executed_steps = []
            for message in messages:
                if message.get("type") == "tool_call":
                    tool_name = message.get("tool_name")
                    if tool_name:
                        executed_steps.append(tool_name)

            results = {}
            for step in expected_steps:
                found = any(step in executed for executed in executed_steps)
                results[step] = found

            passed = all(results.values())
            self.criteria_results["workflow_steps"] = {
                "expected": expected_steps,
                "executed": executed_steps,
                "results": results,
                "passed": passed
            }
            return passed

        def get_results(self) -> Dict[str, Any]:
            """Get all criteria check results."""
            return self.criteria_results

        def all_passed(self) -> bool:
            """Check if all criteria passed."""
            return all(result.get("passed", False) for result in self.criteria_results.values())

    return SuccessCriteriaChecker()


@pytest.fixture(scope="function")
def test_data_loader():
    """Provide a utility for loading test data."""
    class TestDataLoader:
        def load_json_fixture(self, filename: str) -> Dict[str, Any]:
            """Load JSON fixture data."""
            fixture_path = FIXTURES_DIR / filename
            if fixture_path.exists():
                with open(fixture_path, 'r') as f:
                    return json.load(f)
            return {}

        def load_email_fixture(self, name: str) -> Dict[str, Any]:
            """Load email test data."""
            return self.load_json_fixture(f"emails/{name}.json")

        def load_calendar_fixture(self, name: str) -> Dict[str, Any]:
            """Load calendar test data."""
            return self.load_json_fixture(f"calendar/{name}.json")

        def load_spotify_fixture(self, name: str) -> Dict[str, Any]:
            """Load Spotify test data."""
            return self.load_json_fixture(f"spotify/{name}.json")

    return TestDataLoader()


# Pytest configuration
def pytest_configure(config):
    """Configure pytest for e2e tests."""
    config.addinivalue_line("markers", "e2e: mark test as end-to-end test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "ui: mark test as UI test")
    config.addinivalue_line("markers", "backend: mark test as backend test")
    config.addinivalue_line("markers", "integration: mark test as integration test")


def pytest_collection_modifyitems(config, items):
    """Modify test collection for e2e tests."""
    for item in items:
        # Auto-mark e2e tests
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)

        # Add timeout to slow tests
        if "slow" in [mark.name for mark in item.iter_markers()]:
            item.add_marker(pytest.mark.timeout(300))
