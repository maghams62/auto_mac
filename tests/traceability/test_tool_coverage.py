import pytest

from src.agent.agent import AutomationAgent
from src.traceability.tool_coverage import TOOL_COVERAGE_REGISTRY, validate_tool_coverage


def test_slash_commands_have_traceability_coverage():
    slash_tools = [f"slash:{name}" for name in AutomationAgent.SLASH_PLAN_DEFINITIONS.keys()]
    validate_tool_coverage(slash_tools)


def test_registry_includes_documented_entries():
    assert "slash:slack" in TOOL_COVERAGE_REGISTRY
    assert TOOL_COVERAGE_REGISTRY["slash:slack"].produces_evidence

