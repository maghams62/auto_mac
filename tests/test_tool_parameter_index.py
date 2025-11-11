"""
Tests for tool parameter metadata index used by planner/executor validation.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.orchestrator.tools_catalog import build_tool_parameter_index  # noqa: E402


def test_compose_email_required_parameters():
    """compose_email should require subject and body parameters."""
    index = build_tool_parameter_index()
    assert "compose_email" in index

    compose_meta = index["compose_email"]
    required = set(compose_meta["required"])
    optional = set(compose_meta["optional"])

    assert {"subject", "body"}.issubset(required)
    assert "recipient" in optional
    assert "attachments" in optional
    assert "send" in optional


def test_create_zip_archive_parameter_defaults():
    """create_zip_archive exposes optional include/exclude filter parameters."""
    index = build_tool_parameter_index()
    assert "create_zip_archive" in index

    zip_meta = index["create_zip_archive"]
    required = set(zip_meta["required"])
    optional = set(zip_meta["optional"])

    # All parameters are optional; planner should still see them
    assert not required
    for param in {"source_path", "zip_name", "include_pattern", "include_extensions", "exclude_extensions"}:
        assert param in optional
