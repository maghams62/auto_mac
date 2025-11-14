from typing import Any, Dict, List

import pytest
from unittest.mock import patch

from src.agent.agent_registry import AgentRegistry


def test_agent_registry_tools_execute_smoke():
    registry = AgentRegistry(config={})
    agent_names = sorted(registry._agent_classes.keys())

    assert agent_names, "Agent registry returned no agents to validate"

    for agent_name in agent_names:
        agent = registry.get_agent(agent_name)
        assert agent is not None, f"Failed to initialize agent '{agent_name}'"

        tools = agent.get_tools()
        if isinstance(tools, dict):
            tool_objects = list(tools.values())
        else:
            tool_objects = list(tools)

        assert tool_objects, f"Agent '{agent_name}' did not expose any tools"

        tool_to_patch = None
        tool_name = None

        for candidate in tool_objects:
            candidate_name = getattr(candidate, "name", None)
            if candidate_name and hasattr(candidate, "invoke"):
                tool_to_patch = candidate
                tool_name = candidate_name
                break

        if (tool_to_patch is None or tool_name is None) and hasattr(agent, "tools"):
            if isinstance(agent.tools, dict):
                for candidate_name, candidate in agent.tools.items():
                    if hasattr(candidate, "invoke"):
                        tool_to_patch = candidate
                        tool_name = candidate_name
                        break
            elif isinstance(agent.tools, list):
                for candidate in agent.tools:
                    candidate_name = getattr(candidate, "name", None)
                    if candidate_name and hasattr(candidate, "invoke"):
                        tool_to_patch = candidate
                        tool_name = candidate_name
                        break

        if tool_to_patch is None or tool_name is None:
            pytest.fail(f"Agent '{agent_name}' did not expose an invokable tool for smoke testing")

        invocation_calls: List[Dict[str, Any]] = []

        def _fake_invoke(self, *args, **kwargs):
            invocation_calls.append({"args": args, "kwargs": kwargs})
            return {"ok": True}

        try:
            with patch.object(tool_to_patch.__class__, "invoke", new=_fake_invoke):
                result = agent.execute(tool_name, {})
                assert result == {"ok": True}, f"Agent '{agent_name}' returned unexpected result"
                assert len(invocation_calls) == 1, f"Tool '{tool_name}' was not invoked exactly once for agent '{agent_name}'"
        except Exception as exc:
            pytest.fail(f"Failed to execute '{tool_name}' for agent '{agent_name}': {exc}")
