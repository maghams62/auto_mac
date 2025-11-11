"""Level 2 agent router that narrows tool catalogs based on intent."""

from __future__ import annotations

from typing import Dict, Any, List
import logging


logger = logging.getLogger(__name__)


class AgentRouter:
    """Coordinates agent selection and produces filtered tool catalogs."""

    def __init__(self) -> None:
        pass

    def route(
        self,
        intent: Dict[str, Any],
        tool_catalog: List[Any],
        registry
    ) -> Dict[str, Any]:
        """Return routing metadata and filtered tools based on intent."""

        involved_agents = intent.get("involved_agents") or []
        primary_agent = intent.get("primary_agent")

        if primary_agent and primary_agent not in involved_agents:
            involved_agents.append(primary_agent)

        if not involved_agents:
            logger.info("[AGENT ROUTER] No specific agents identified; using full tool catalog")
            return {
                "mode": "full",
                "tool_catalog": tool_catalog,
                "intent": intent,
            }

        allowed_agents = {agent for agent in involved_agents if agent in registry.agents}
        if not allowed_agents:
            logger.info("[AGENT ROUTER] Identified agents missing in registry; using full catalog")
            return {
                "mode": "full",
                "tool_catalog": tool_catalog,
                "intent": intent,
            }

        filtered_tools: List[Any] = []
        for spec in tool_catalog:
            agent_name = registry.tool_to_agent.get(getattr(spec, "name", None))
            if agent_name in allowed_agents:
                filtered_tools.append(spec)

        if not filtered_tools:
            logger.warning("[AGENT ROUTER] Filtering removed all tools; falling back to full catalog")
            filtered_tools = tool_catalog
        else:
            logger.info(
                "[AGENT ROUTER] Filtered tool catalog to %d tools for agents %s",
                len(filtered_tools),
                sorted(allowed_agents),
            )

        return {
            "mode": "filtered",
            "tool_catalog": filtered_tools,
            "intent": intent,
        }
