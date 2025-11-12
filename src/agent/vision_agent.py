"""
Vision Agent - Reason about UI screenshots to unblock complex navigation flows.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Any, List, Optional

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from ..utils import load_config, get_temperature_for_model


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are a UI automation specialist. Given a screenshot path and metadata, "
    "you must deduce what is currently shown, identify blockers, and propose the "
    "next concrete UI action(s). Respond ONLY with JSON in the following schema:\n"
    "{\n"
    '  "summary": "Short human-readable summary",\n'
    '  "status": "resolved" | "action_required" | "uncertain",\n'
    '  "actions": [\n'
    '    {\n'
    '      "description": "What to do next",\n'
    '      "confidence": 0.0 - 1.0,\n'
    '      "notes": "Additional context or assumptions"\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "If the screenshot likely reflects a completed task, set status to \"resolved\" "
    "with an empty actions array. Never include explanatory text outside the JSON."
)


@tool
def analyze_ui_screenshot(
    screenshot_path: str,
    goal: str,
    tool_name: str,
    recent_errors: Optional[List[str]] = None,
    attempt: int = 0
) -> Dict[str, Any]:
    """
    Analyze a UI screenshot and recommend next actions to continue automation.

    Args:
        screenshot_path: Path to captured screenshot (PNG).
        goal: High-level user goal or step description.
        tool_name: Name of the original tool/action we attempted.
        recent_errors: Optional list of error messages encountered so far.
        attempt: Current attempt count for the tool.

    Returns:
        Structured analysis dict with summary, status, and recommended actions.
    """
    logger.info(
        "[VISION AGENT] Analyzing screenshot %s (tool=%s, attempt=%s)",
        screenshot_path,
        tool_name,
        attempt,
    )

    try:
        config = load_config()
        openai_config = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.0),
            api_key=openai_config.get("api_key")
        )

        error_text = ""
        if recent_errors:
            error_text = "\nRecent errors:\n- " + "\n- ".join(recent_errors[:5])

        prompt = (
            f"Screenshot path: {screenshot_path}\n"
            f"Current goal: {goal}\n"
            f"Original tool: {tool_name}\n"
            f"Attempt: {attempt}\n"
            f"{error_text}\n"
            "Describe the visible UI state and recommend the next action."
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        response = llm.invoke(messages)
        raw = response.content.strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("[VISION AGENT] Invalid JSON response, wrapping fallback text")
            data = {
                "summary": raw,
                "status": "action_required",
                "actions": [],
            }

        data.setdefault("status", "action_required")
        data.setdefault("actions", [])
        data["screenshot_path"] = screenshot_path

        return data

    except Exception as exc:
        logger.error(f"[VISION AGENT] Analysis failed: {exc}")
        return {
            "error": True,
            "error_type": "VisionAnalysisError",
            "error_message": str(exc),
            "screenshot_path": screenshot_path,
            "retry_possible": False
        }


VISION_AGENT_TOOLS = [
    analyze_ui_screenshot,
]

VISION_AGENT_HIERARCHY = """
Vision Agent Hierarchy:
======================

LEVEL 1: Screenshot Analysis
└─ analyze_ui_screenshot(screenshot_path, goal, tool_name, recent_errors=None, attempt=0)
     → Uses multimodal reasoning to summarise state and recommend next actions.
"""


class VisionAgent:
    """
    Thin wrapper so the Vision tools can be lazily initialised via AgentRegistry.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in VISION_AGENT_TOOLS}

    def get_tools(self):
        return VISION_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        return VISION_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Vision agent tool '{tool_name}' not found",
            }
        tool = self.tools[tool_name]
        return tool.invoke(inputs)
