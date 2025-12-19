"""
Pytest configuration and fixtures for test environment.

This file provides:
- Pytest configuration
- Common fixtures for test setup
- Mock configurations for test environment
- Test data directories
"""

import pytest
import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))


@pytest.fixture(scope="session")
def test_data_dir():
    """Provide test data directory."""
    data_dir = BASE_DIR / "data" / "test_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture(scope="function")
def temp_dir():
    """Provide temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture(scope="function")
def temp_file():
    """Provide temporary file path."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)
        yield tmp_path
        if tmp_path.exists():
            tmp_path.unlink()


@pytest.fixture(scope="session")
def test_config():
    """Provide test configuration."""
    # Load minimal config for testing
    try:
        from src.utils import load_config
        config = load_config()
        return config
    except Exception:
        # Return minimal config if loading fails
        return {
            "openai": {
                "api_key": os.getenv("OPENAI_API_KEY", ""),
                "model": "gpt-4o-mini"
            }
        }


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Set up test environment variables."""
    # Set test mode
    monkeypatch.setenv("TEST_MODE", "true")
    
    # Set agent ID if not present
    if not os.getenv("AGENT_ID"):
        monkeypatch.setenv("AGENT_ID", "test_agent")


# Pytest configuration
def pytest_configure(config):
    """Configure pytest."""
    # Add custom markers
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection."""
    for item in items:
        # Auto-mark tests based on file location
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        else:
            # Default to unit test
            item.add_marker(pytest.mark.unit)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to save test results after execution."""
    outcome = yield
    report = outcome.get_result()
    
    # Only save results for actual test calls (not setup/teardown)
    if call.when == "call" and report.outcome in ("passed", "failed", "error"):
        try:
            from src.utils.test_results import save_test_result
            
            # Extract test name from file (e.g., "test_email_attachments.py" -> "email_attachments")
            test_file = Path(item.fspath).stem
            if test_file.startswith("test_"):
                test_name = test_file.replace("test_", "")
            else:
                test_name = test_file
            
            # Save result (will be aggregated per test file)
            save_test_result(test_name, {
                "status": "passed" if report.outcome == "passed" else "failed",
                "pass_count": 1 if report.outcome == "passed" else 0,
                "fail_count": 0 if report.outcome == "passed" else 1,
                "test_function": item.name,
                "outcome": report.outcome,
                "details": {
                    "longrepr": str(report.longrepr) if hasattr(report, 'longrepr') else None,
                    "duration": report.duration if hasattr(report, 'duration') else None
                }
            })
        except Exception as e:
            # Don't fail tests if result saving fails
            import logging
            logging.getLogger(__name__).warning(f"Failed to save test result: {e}")

