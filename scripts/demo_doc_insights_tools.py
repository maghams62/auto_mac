#!/usr/bin/env python
"""
Lightweight developer script to verify that NL requests hit the Doc Insights tools.

Usage:
    python scripts/demo_doc_insights_tools.py --query "What is the activity around core-api this week?"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.agent.agent import AutomationAgent
from src.agent.agent_registry import AgentRegistry
from src.memory import SessionManager
from src.utils import load_config


def _summarize_tool_usage(final_result: dict) -> list[str]:
    step_results = final_result.get("step_results") or {}
    tool_names = []
    for step in step_results.values():
        if isinstance(step, dict):
            tool = step.get("tool")
            if tool:
                tool_names.append(tool)
    return tool_names


def main() -> None:
    parser = argparse.ArgumentParser(description="Doc Insights sanity check")
    parser.add_argument(
        "--query",
        default="What’s the activity around core-api this week?",
        help="Natural language request to send through the automation agent.",
    )
    args = parser.parse_args()

    config = load_config()
    session_manager = SessionManager(config)
    registry = AgentRegistry(config, session_manager=session_manager)
    agent = AutomationAgent(config, session_manager=session_manager)

    print(f"Running doc insights sanity check for query: {args.query}\n")
    result = agent.run(args.query.strip() or "What’s happening in core-api?")
    final_result = result.get("final_result") or {}

    print("Response message:")
    print(result.get("message") or "<no message>")
    print("\nTools invoked:")
    tool_names = _summarize_tool_usage(final_result)
    if tool_names:
        for tool in tool_names:
            print(f" • {tool}")
    else:
        print(" • <no step-level tools recorded>")

    output_path = Path("data") / "logs" / "last_doc_insights_run.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2))
    print(f"\nFull payload written to {output_path}")


if __name__ == "__main__":
    main()

