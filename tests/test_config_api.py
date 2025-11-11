"""
Tests for config API endpoints.
"""

import pytest
import json
from fastapi.testclient import TestClient
from pathlib import Path
import yaml
import tempfile
import os

# Import after setting up test environment
from api_server import app, config_manager


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def temp_config():
    """Create temporary config file for testing."""
    temp_dir = tempfile.mkdtemp()
    config_path = Path(temp_dir) / "test_config.yaml"
    
    test_config = {
        "openai": {
            "api_key": "test-key",
            "model": "gpt-4o"
        },
        "email": {
            "default_recipient": "test@example.com",
            "default_subject_prefix": "[Test]"
        },
        "documents": {
            "folders": ["/test/folder1", "/test/folder2"]
        }
    }
    
    with open(config_path, 'w') as f:
        yaml.dump(test_config, f)
    
    yield config_path
    
    # Cleanup
    if config_path.exists():
        config_path.unlink()


def test_get_config(client):
    """Test GET /api/config endpoint."""
    response = client.get("/api/config")
    assert response.status_code == 200
    
    data = response.json()
    assert "email" in data
    assert "documents" in data
    
    # Verify API key is redacted
    if "openai" in data:
        assert data["openai"]["api_key"] == "***REDACTED***"


def test_update_config(client):
    """Test PUT /api/config endpoint."""
    updates = {
        "email": {
            "default_recipient": "newemail@example.com"
        }
    }
    
    response = client.put("/api/config", json={"updates": updates})
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert "message" in data
    assert "config" in data
    
    # Verify update was applied
    assert data["config"]["email"]["default_recipient"] == "newemail@example.com"


def test_update_config_nested(client):
    """Test updating nested config values."""
    updates = {
        "documents": {
            "folders": ["/new/folder1", "/new/folder2"]
        }
    }
    
    response = client.put("/api/config", json={"updates": updates})
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    
    # Verify folders were updated
    folders = data["config"]["documents"]["folders"]
    assert "/new/folder1" in folders
    assert "/new/folder2" in folders


def test_reload_config(client):
    """Test POST /api/config/reload endpoint."""
    response = client.post("/api/config/reload")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert "message" in data


def test_config_sanitization(client):
    """Test that sensitive fields are sanitized."""
    response = client.get("/api/config")
    assert response.status_code == 200
    
    data = response.json()
    
    # Check OpenAI API key is redacted
    if "openai" in data and "api_key" in data["openai"]:
        assert data["openai"]["api_key"] == "***REDACTED***"
    
    # Check Discord credentials are masked
    if "discord" in data and "credentials" in data["discord"]:
        creds = data["discord"]["credentials"]
        if "password" in creds and creds["password"]:
            assert creds["password"] == "***REDACTED***"
        if "mfa_code" in creds and creds["mfa_code"]:
            assert creds["mfa_code"] == "***REDACTED***"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

