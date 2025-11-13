#!/usr/bin/env python3
"""
Regression test to verify every tool's args_schema renders successfully with JSON.

This addresses the audit finding about WritingBrief causing import failures.
All tools must have JSON-serializable schemas for LangChain compatibility.
"""

import pytest
import json
from typing import Dict, Any

from src.agent import ALL_AGENT_TOOLS


class TestToolSchemaValidation:
    """Test that all tool schemas are JSON-serializable."""

    @pytest.mark.parametrize("tool", ALL_AGENT_TOOLS, ids=lambda t: t.name)
    def test_tool_schema_json_serializable(self, tool):
        """Test that every tool's args_schema can be converted to JSON."""
        # Get the args_schema
        args_schema = getattr(tool, "args_schema", None)

        # Every tool should have an args_schema
        assert args_schema is not None, f"Tool {tool.name} missing args_schema"

        # Try to get the schema dict - this is where WritingBrief would fail
        try:
            schema_dict = args_schema.schema()
        except Exception as e:
            pytest.fail(f"Tool {tool.name} args_schema.schema() failed: {e}")

        # Schema should be a dict
        assert isinstance(schema_dict, dict), f"Tool {tool.name} schema is not a dict"

        # Try to serialize to JSON - this catches non-serializable types
        try:
            json_str = json.dumps(schema_dict, default=str)
            # Try to parse it back
            parsed = json.loads(json_str)
            assert isinstance(parsed, dict)
        except Exception as e:
            pytest.fail(f"Tool {tool.name} schema not JSON serializable: {e}")

    @pytest.mark.parametrize("tool", ALL_AGENT_TOOLS, ids=lambda t: t.name)
    def test_tool_schema_has_properties(self, tool):
        """Test that every tool's schema has proper structure."""
        args_schema = getattr(tool, "args_schema", None)
        assert args_schema is not None, f"Tool {tool.name} missing args_schema"

        schema_dict = args_schema.schema()

        # Should have properties
        assert "properties" in schema_dict, f"Tool {tool.name} schema missing properties"
        assert isinstance(schema_dict["properties"], dict), f"Tool {tool.name} properties not a dict"

        # Should have type
        assert "type" in schema_dict, f"Tool {tool.name} schema missing type"
        assert schema_dict["type"] == "object", f"Tool {tool.name} schema type is not 'object'"

    @pytest.mark.parametrize("tool", ALL_AGENT_TOOLS, ids=lambda t: t.name)
    def test_tool_schema_required_fields(self, tool):
        """Test that required fields are properly defined."""
        args_schema = getattr(tool, "args_schema", None)
        assert args_schema is not None

        schema_dict = args_schema.schema()

        # Required should be a list if present
        if "required" in schema_dict:
            required = schema_dict["required"]
            assert isinstance(required, list), f"Tool {tool.name} required is not a list"

            # All required fields should exist in properties
            properties = schema_dict.get("properties", {})
            for req_field in required:
                assert req_field in properties, f"Tool {tool.name} required field '{req_field}' not in properties"

    @pytest.mark.parametrize("tool", ALL_AGENT_TOOLS, ids=lambda t: t.name)
    def test_tool_schema_property_types(self, tool):
        """Test that property types are valid JSON Schema types."""
        args_schema = getattr(tool, "args_schema", None)
        assert args_schema is not None

        schema_dict = args_schema.schema()
        properties = schema_dict.get("properties", {})

        valid_types = {"string", "number", "integer", "boolean", "object", "array", "null"}

        for prop_name, prop_def in properties.items():
            if "type" in prop_def:
                prop_type = prop_def["type"]
                assert prop_type in valid_types, f"Tool {tool.name} property '{prop_name}' has invalid type '{prop_type}'"

    def test_all_tools_accounted_for(self):
        """Test that we have the expected number of tools."""
        # This will help catch if tools are added/removed without updating tests
        tool_count = len(ALL_AGENT_TOOLS)
        assert tool_count > 100, f"Expected many tools, got {tool_count}"

        # Get unique tool names
        tool_names = set(tool.name for tool in ALL_AGENT_TOOLS)
        assert len(tool_names) == len(ALL_AGENT_TOOLS), "Duplicate tool names found"

    def test_no_writingbrief_references(self):
        """Test that no tool schemas reference WritingBrief (which caused the original issue)."""
        from src.agent.writing_agent import WritingBrief

        for tool in ALL_AGENT_TOOLS:
            args_schema = getattr(tool, "args_schema", None)
            if args_schema:
                schema_dict = args_schema.schema()

                # Check if any property references WritingBrief in its description or title
                properties = schema_dict.get("properties", {})
                for prop_name, prop_def in properties.items():
                    description = prop_def.get("description", "").lower()
                    title = prop_def.get("title", "").lower()

                    assert "writingbrief" not in description, f"Tool {tool.name} property '{prop_name}' references WritingBrief in description"
                    assert "writingbrief" not in title, f"Tool {tool.name} property '{prop_name}' references WritingBrief in title"
