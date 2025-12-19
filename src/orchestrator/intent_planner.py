"""Level 1 intent planner - determines agent involvement for requests."""

from __future__ import annotations

import json
import logging
import asyncio
from typing import Dict, Any, List
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from ..utils import get_temperature_for_model
from ..utils.openai_client import PooledOpenAIClient
from ..utils.trajectory_logger import get_trajectory_logger
from ..utils.llm_wrapper import log_llm_call, extract_token_usage
import time


logger = logging.getLogger(__name__)


PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "intent_disambiguation.md"


def _load_prompt_template() -> str:
    if PROMPT_PATH.exists():
        try:
            return PROMPT_PATH.read_text(encoding="utf-8")
        except Exception as exc:  # pragma: no cover - fallback
            logger.warning("[INTENT PLANNER] Failed to read prompt file: %s", exc)

    # Minimal fallback prompt
    return (
        "You map user requests to agent responsibilities. "
        "Return compact JSON with intent, primary_agent, involved_agents, goal, task_type."
    )


class IntentPlanner:
    """Determines which agents are required for a user goal."""

    def __init__(self, config: Dict[str, Any]):
        openai_cfg = config.get("openai", {})
        
        # Use pooled client for better performance
        pooled_client = PooledOpenAIClient.get_client(config)
        
        self.llm = ChatOpenAI(
            model=openai_cfg.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.1),
            api_key=openai_cfg.get("api_key"),
            http_client=pooled_client._http_client if hasattr(pooled_client, '_http_client') else None
        )
        logger.info("[INTENT PLANNER] Using pooled OpenAI client")
        self.prompt_template = _load_prompt_template()
        self.config = config
        self.trajectory_logger = get_trajectory_logger(config)

    async def analyze(self, goal: str, agent_capabilities: List[Dict[str, Any]], session_id: Optional[str] = None, interaction_id: Optional[str] = None) -> Dict[str, Any]:
        """Analyze goal and return structured intent data (async for performance)."""

        capability_block = json.dumps(agent_capabilities, indent=2)
        prompt = self.prompt_template.format(goal=goal, capabilities=capability_block)
        
        session_id = session_id or "unknown"

        try:
            # Log LLM call with timing
            llm_start_time = time.time()
            model_name = self.llm.model_name if hasattr(self.llm, 'model_name') else str(self.llm.model) if hasattr(self.llm, 'model') else "unknown"
            
            response = await self.llm.ainvoke([
                SystemMessage(content="You are the Intent Planner."),
                HumanMessage(content=prompt)
            ])
            raw_text = response.content.strip()
            llm_latency_ms = (time.time() - llm_start_time) * 1000
            
            # Extract token usage
            tokens_used = extract_token_usage(response)
            
            logger.debug("[INTENT PLANNER] Raw response: %s", raw_text)
            
            # Log LLM call
            log_llm_call(
                model=model_name,
                prompt=prompt[:2000] + "..." if len(prompt) > 2000 else prompt,
                response=raw_text[:2000] + "..." if len(raw_text) > 2000 else raw_text,
                latency_ms=llm_latency_ms,
                success=True,
                session_id=session_id,
                interaction_id=interaction_id,
                component="intent_planner",
                decision_type="intent_analysis"
            )

            data = self._parse_json(raw_text)
            if not isinstance(data, dict):
                raise ValueError("intent planner response is not a dict")

            # Ensure mandatory fields
            data.setdefault("intent", "multi_agent")
            data.setdefault("goal", goal)
            data.setdefault("involved_agents", [])
            if data.get("intent") == "single_agent" and not data.get("primary_agent"):
                if data["involved_agents"]:
                    data["primary_agent"] = data["involved_agents"][0]
            
            # Extract confidence if available
            confidence = data.get("confidence")
            if confidence is None:
                # Try to infer confidence from intent clarity
                if data.get("intent") == "single_agent" and data.get("primary_agent"):
                    confidence = 0.9  # High confidence for single agent
                elif len(data.get("involved_agents", [])) > 0:
                    confidence = 0.7  # Medium confidence for multi-agent
                else:
                    confidence = 0.5  # Low confidence for fallback
            
            # Log intent analysis trajectory
            self.trajectory_logger.log_trajectory(
                session_id=session_id,
                interaction_id=interaction_id,
                phase="planning",
                component="intent_planner",
                decision_type="intent_analysis",
                input_data={
                    "goal": goal,
                    "agent_capabilities_count": len(agent_capabilities)
                },
                output_data={
                    "intent": data.get("intent"),
                    "primary_agent": data.get("primary_agent"),
                    "involved_agents": data.get("involved_agents", []),
                    "task_type": data.get("task_type")
                },
                reasoning=f"Analyzed goal and determined intent: {data.get('intent')} with agents: {data.get('involved_agents', [])}",
                confidence=confidence,
                model_used=model_name,
                tokens_used=tokens_used,
                latency_ms=llm_latency_ms,
                success=True
            )

            return data
        except Exception as exc:
            logger.warning("[INTENT PLANNER] Falling back to default intent due to error: %s", exc)
            
            # Log error trajectory
            self.trajectory_logger.log_trajectory(
                session_id=session_id,
                interaction_id=interaction_id,
                phase="planning",
                component="intent_planner",
                decision_type="intent_analysis",
                input_data={
                    "goal": goal,
                    "agent_capabilities_count": len(agent_capabilities)
                },
                output_data={
                    "intent": "multi_agent",
                    "involved_agents": [],
                    "task_type": "unspecified"
                },
                reasoning=f"Error during intent analysis, falling back to default: {str(exc)}",
                confidence=0.3,  # Low confidence for fallback
                success=False,
                error={
                    "type": type(exc).__name__,
                    "message": str(exc)
                }
            )
            
            return {
                "intent": "multi_agent",
                "goal": goal,
                "involved_agents": [],
                "task_type": "unspecified",
            }

    @staticmethod
    def _parse_json(text: str) -> Any:
        """Extract JSON from the model response."""

        text = text.strip()
        if text.startswith("```"):
            parts = text.strip("`").split("\n", 1)
            if len(parts) == 2:
                text = parts[1]

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Attempt to extract JSON substring
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                return json.loads(text[start:end + 1])
            raise
