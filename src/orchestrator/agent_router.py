"""Level 2 agent router that narrows tool catalogs based on intent."""

from __future__ import annotations

from typing import Dict, Any, List, Optional
import logging

from ..utils.trajectory_logger import get_trajectory_logger


logger = logging.getLogger(__name__)


class AgentRouter:
    """Coordinates agent selection and produces filtered tool catalogs."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.trajectory_logger = get_trajectory_logger(config)

    def route(
        self,
        intent: Dict[str, Any],
        tool_catalog: List[Any],
        registry,
        session_id: Optional[str] = None,
        interaction_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Return routing metadata and filtered tools based on intent."""

        involved_agents = intent.get("involved_agents") or []
        primary_agent = intent.get("primary_agent")

        if primary_agent and primary_agent not in involved_agents:
            involved_agents.append(primary_agent)

        if not involved_agents:
            logger.info("[AGENT ROUTER] No specific agents identified; using full tool catalog")
            
            # Log routing decision
            self.trajectory_logger.log_trajectory(
                session_id=session_id or "unknown",
                interaction_id=interaction_id,
                phase="planning",
                component="agent_router",
                decision_type="agent_routing",
                input_data={
                    "intent": intent,
                    "total_tools": len(tool_catalog),
                    "involved_agents": involved_agents
                },
                output_data={
                    "mode": "full",
                    "filtered_tools_count": len(tool_catalog),
                    "reason": "No specific agents identified"
                },
                reasoning="No specific agents identified by intent planner; using full tool catalog",
                confidence=0.5,  # Medium confidence for fallback
                success=True
            )
            
            return {
                "mode": "full",
                "tool_catalog": tool_catalog,
                "intent": intent,
            }

        allowed_agents = {agent for agent in involved_agents if agent in registry.agents}
        if not allowed_agents:
            logger.info("[AGENT ROUTER] Identified agents missing in registry; using full catalog")
            
            # Log routing decision
            self.trajectory_logger.log_trajectory(
                session_id=session_id or "unknown",
                interaction_id=interaction_id,
                phase="planning",
                component="agent_router",
                decision_type="agent_routing",
                input_data={
                    "intent": intent,
                    "total_tools": len(tool_catalog),
                    "involved_agents": involved_agents,
                    "requested_agents": list(involved_agents)
                },
                output_data={
                    "mode": "full",
                    "filtered_tools_count": len(tool_catalog),
                    "reason": "Identified agents missing in registry"
                },
                reasoning=f"Requested agents {involved_agents} not found in registry; using full catalog",
                confidence=0.6,
                success=True
            )
            
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
            
            # Log fallback decision
            self.trajectory_logger.log_trajectory(
                session_id=session_id or "unknown",
                interaction_id=interaction_id,
                phase="planning",
                component="agent_router",
                decision_type="agent_routing",
                input_data={
                    "intent": intent,
                    "total_tools": len(tool_catalog),
                    "allowed_agents": list(allowed_agents)
                },
                output_data={
                    "mode": "full",
                    "filtered_tools_count": len(tool_catalog),
                    "reason": "Filtering removed all tools"
                },
                reasoning=f"Filtering by agents {allowed_agents} removed all tools; falling back to full catalog",
                confidence=0.4,  # Low confidence for fallback
                success=True
            )
        else:
            logger.info(
                "[AGENT ROUTER] Filtered tool catalog to %d tools for agents %s",
                len(filtered_tools),
                sorted(allowed_agents),
            )
            
            # Log successful filtering decision
            self.trajectory_logger.log_trajectory(
                session_id=session_id or "unknown",
                interaction_id=interaction_id,
                phase="planning",
                component="agent_router",
                decision_type="agent_routing",
                input_data={
                    "intent": intent,
                    "total_tools": len(tool_catalog),
                    "allowed_agents": list(allowed_agents),
                    "primary_agent": primary_agent
                },
                output_data={
                    "mode": "filtered",
                    "filtered_tools_count": len(filtered_tools),
                    "filtered_tool_names": [getattr(spec, "name", "unknown") for spec in filtered_tools[:20]]  # Limit to 20
                },
                reasoning=f"Filtered tool catalog to {len(filtered_tools)} tools for agents: {sorted(allowed_agents)}",
                confidence=0.8,  # High confidence for successful filtering
                success=True
            )

        return {
            "mode": "filtered" if filtered_tools != tool_catalog else "full",
            "tool_catalog": filtered_tools,
            "intent": intent,
        }
