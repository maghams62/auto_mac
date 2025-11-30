#!/usr/bin/env python
"""
Manual demo harness: vector retrieval + graph summary + single LLM call.
"""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path
import sys
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config_manager import ConfigManager
from src.demo.scenario_classifier import classify_question, PAYMENTS_SCENARIO, NOTIFICATIONS_SCENARIO
from src.demo.vector_retriever import VectorRetriever
from src.demo.graph_summary import GraphNeighborhoodSummarizer
from src.utils.openai_client import PooledOpenAIClient

PRESET_QUESTIONS = {
    "payments": "Why are people complaining about the payments API?",
    "notifications": "What is going on with notifications receipts and template_version?",
}


def build_prompt(question, scenario, vector_bundle, graph_summary):
    graph_lines = [
        f"API: {graph_summary.api}",
        f"Services: {', '.join(graph_summary.services) or 'n/a'}",
        f"Components: {', '.join(graph_summary.components) or 'n/a'}",
        f"Docs: {', '.join(graph_summary.docs) or 'n/a'}",
        f"Recent Git Events: {', '.join(graph_summary.git_events) or 'n/a'}",
        f"Recent Slack Events: {', '.join(graph_summary.slack_events) or 'n/a'}",
    ]
    graph_block = "\n".join(graph_lines)

    snippet_lines = []
    for snippet in vector_bundle.slack + vector_bundle.git + vector_bundle.docs:
        snippet_text = _truncate(snippet.text.strip().replace("\n", " "), 400)
        snippet_lines.append(f"[{snippet.source}] score={snippet.score:.2f} :: {snippet_text}")
    if not snippet_lines:
        snippet_lines.append("(no vector snippets available)")

    snippets_block = "\n".join(snippet_lines)

    return textwrap.dedent(
        f"""
        You are an engineer diagnosing doc drift and API changes for the Oqoqo payments/notifications stack.
        Use the graph summary and retrieved snippets to explain what changed, why it broke, and which docs/services need attention.

        ## User Question
        {question.strip()}

        ## Scenario
        {scenario.description} (API {scenario.api})

        ## Graph Summary
        {graph_block}

        ## Retrieved Evidence
        {snippets_block}

        ## Instructions
        - Summarize the incident in 2-3 sentences.
        - Call out the relevant services/components/docs.
        - Explain the root cause, current risk, and the doc updates required.
        - Finish with a short \"Next Steps\" bullet list.
        """
    ).strip()


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def run_demo(question: str, preset: Optional[str] = None, context_only: bool = False) -> None:
    config = ConfigManager().get_config()
    scenario = classify_question(question)

    print(f"🧭 Scenario: {scenario.name} (API {scenario.api})")

    vector_retriever = VectorRetriever(config)
    bundle = vector_retriever.fetch_context(
        scenario,
        question=question,
        top_k_slack=4,
        top_k_git=4,
        top_k_docs=3,
    )

    summarizer = GraphNeighborhoodSummarizer(config)
    graph_summary = summarizer.summarize(scenario)

    prompt = build_prompt(question, scenario, bundle, graph_summary)

    if context_only:
        print(prompt)
        return

    client = PooledOpenAIClient.get_client(config)
    model = config.get("openai", {}).get("model", "gpt-4o")

    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": "You are Oqoqo's doc-drift analyst. Respond clearly and cite services/components/docs explicitly.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    answer = response.choices[0].message.content.strip()
    print("\n===== LLM Answer =====\n")
    print(answer)

    print("\n===== Debug Summary =====\n")
    print(f"Scenario: {scenario.name}")
    print(f"Slack snippets: {len(bundle.slack)} | Git snippets: {len(bundle.git)} | Doc snippets: {len(bundle.docs)}")
    print(f"Graph services: {graph_summary.services}")
    print(f"Graph docs: {graph_summary.docs}")


def main():
    parser = argparse.ArgumentParser(description="LLM demo over vector + graph context.")
    parser.add_argument("--question", type=str, help="Natural language question to run.")
    parser.add_argument(
        "--preset",
        choices=list(PRESET_QUESTIONS.keys()),
        default="payments",
        help="Shortcut question preset.",
    )
    parser.add_argument(
        "--context-only",
        action="store_true",
        help="Print the constructed prompt/context without calling the LLM.",
    )
    args = parser.parse_args()

    question = args.question or PRESET_QUESTIONS[args.preset]
    run_demo(question, preset=args.preset, context_only=args.context_only)


if __name__ == "__main__":
    main()

