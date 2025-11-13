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

    async def analyze(self, goal: str, agent_capabilities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze goal and return structured intent data (async for performance)."""

        capability_block = json.dumps(agent_capabilities, indent=2)
        prompt = self.prompt_template.format(goal=goal, capabilities=capability_block)

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="You are the Intent Planner."),
                HumanMessage(content=prompt)
            ])
            raw_text = response.content.strip()
            logger.debug("[INTENT PLANNER] Raw response: %s", raw_text)

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

            return data
        except Exception as exc:
            logger.warning("[INTENT PLANNER] Falling back to default intent due to error: %s", exc)
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
