from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ...utils import get_llm_params, parse_json_with_retry

logger = logging.getLogger(__name__)

MAX_MESSAGES_FOR_LLM = 60
MAX_TEXT_CHARS = 700


class SlashSlackPromptBundle:
    """Loads the slash-specific prompt assets from the repo."""

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root or Path(__file__).resolve().parents[3]
        prompts_dir = self.repo_root / "prompts" / "slash"
        agents_dir = self.repo_root / "agents" / "slash_slack"

        self.system_path = prompts_dir / "slack_system.md"
        self.examples_path = prompts_dir / "slack_examples.md"
        self.agent_context_path = agents_dir / "context.md"

        self.system_instructions = self._read_file(self.system_path)
        self.examples_block = self._read_file(self.examples_path)
        self.agent_context = self._read_file(self.agent_context_path)

    @staticmethod
    def _read_file(path: Path) -> str:
        try:
            if path.exists():
                return path.read_text().strip()
        except Exception as exc:
            logger.warning("Failed to read prompt asset %s: %s", path, exc)
        return ""

    @property
    def system_prompt(self) -> str:
        parts = [self.system_instructions, self.agent_context]
        return "\n\n".join([part for part in parts if part])


class SlashSlackLLMFormatter:
    """Encapsulates the LLM call that turns Slack data into structured output."""

    def __init__(
        self,
        config: Dict[str, Any],
        *,
        llm_client: Optional[ChatOpenAI] = None,
        prompt_bundle: Optional[SlashSlackPromptBundle] = None,
        max_messages: int = MAX_MESSAGES_FOR_LLM,
    ):
        self.config = config
        self.prompt_bundle = prompt_bundle or SlashSlackPromptBundle()
        self.max_messages = max_messages

        if llm_client is not None:
            self.llm = llm_client
        else:
            llm_params = get_llm_params(
                config,
                default_temperature=0.2,
                max_tokens=1400,
                component="slash_slack",
            )
            self.llm = ChatOpenAI(**llm_params)

    def generate(
        self,
        *,
        query: Dict[str, Any],
        context: Dict[str, Any],
        sections: Dict[str, Any],
        messages: List[Dict[str, Any]],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        if not messages:
            return None, "No Slack messages available for summarization."

        payload = {
            "query": query,
            "context": context,
            "analysis_hints": sections or {},
            "messages": self._prepare_messages(messages),
        }

        prompt_block = json.dumps(payload, indent=2, ensure_ascii=False)
        instructions = self.prompt_bundle.system_prompt or "You are the /slack agent."
        if self.prompt_bundle.examples_block:
            instructions = "\n\n".join([instructions, "Reference examples:\n" + self.prompt_bundle.examples_block])

        chat_messages = [
            SystemMessage(content=instructions),
            HumanMessage(
                content=(
                    "Use the schema described above to summarize these Slack records. "
                    "Return ONLY valid JSON.\n"
                    f"{prompt_block}"
                )
            ),
        ]

        try:
            response = self.llm.invoke(chat_messages)
        except Exception as exc:
            logger.warning("[SLASH SLACK] LLM invocation failed: %s", exc)
            return None, str(exc)

        parsed, error = parse_json_with_retry(response.content)
        if parsed:
            return parsed, None

        logger.warning("[SLASH SLACK] LLM returned non-JSON payload: %s", error)
        return None, error or "LLM returned non-JSON payload."

    def _prepare_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        prepared: List[Dict[str, Any]] = []
        for message in messages[: self.max_messages]:
            prepared.append({
                "ts": message.get("ts"),
                "iso_time": message.get("iso_time"),
                "user": message.get("user_name") or message.get("user_id"),
                "text": self._truncate(message.get("text") or message.get("text_raw") or ""),
                "permalink": message.get("permalink"),
                "channel_id": message.get("channel_id"),
                "channel_name": message.get("channel_name"),
                "thread_ts": message.get("thread_ts"),
                "mentions": message.get("mentions"),
                "references": message.get("references"),
                "reactions": message.get("reactions"),
                "files": message.get("files"),
                "service_ids": message.get("service_ids") or message.get("services") or [],
                "component_ids": message.get("component_ids") or message.get("components") or [],
                "related_apis": message.get("related_apis") or message.get("apis") or [],
                "labels": message.get("labels") or [],
            })
        return prepared

    @staticmethod
    def _truncate(text: str) -> str:
        if len(text) <= MAX_TEXT_CHARS:
            return text
        return text[: MAX_TEXT_CHARS - 3] + "..."

