from __future__ import annotations

import json
import logging
from collections import Counter
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
        self.reasoner_path = prompts_dir / "slash_slack_reasoner.md"
        self.agent_context_path = agents_dir / "context.md"

        self.system_instructions = self._read_file(self.system_path)
        self.examples_block = self._read_file(self.examples_path)
        self.reasoner_block = self._read_file(self.reasoner_path)
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
        parts = [self.system_instructions, self.agent_context, self.reasoner_block]
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
        graph: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        if not messages:
            return None, "No Slack messages available for summarization."

        payload = self._build_prompt_payload(
            query=query,
            context=context,
            sections=sections or {},
            messages=messages,
            graph=graph or {},
        )

        prompt_block = json.dumps(payload, indent=2, ensure_ascii=False)
        instructions = self.prompt_bundle.system_prompt or "You are the /slack agent."
        if self.prompt_bundle.examples_block:
            instructions = "\n\n".join([instructions, "Legacy examples:\n" + self.prompt_bundle.examples_block])

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
            valid, validation_error = self._validate_response(parsed)
            if not valid:
                logger.warning("[SLASH SLACK] LLM schema validation failed: %s", validation_error)
                return None, validation_error
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

    def _build_prompt_payload(
        self,
        *,
        query: Dict[str, Any],
        context: Dict[str, Any],
        sections: Dict[str, Any],
        messages: List[Dict[str, Any]],
        graph: Dict[str, Any],
    ) -> Dict[str, Any]:
        channel_id = context.get("channel_id") or query.get("channel_id")
        channel_name = context.get("channel_name") or query.get("channel_name")
        channel_label = context.get("channel_label") or self._format_channel_label(channel_name, channel_id)
        time_range = query.get("time_range") or {}
        thread_ts = query.get("thread_ts")

        prepared_messages = self._prepare_messages(messages)
        payload = {
            "mode": query.get("mode"),
            "user_query": query.get("raw"),
            "channel": {
                "id": channel_id,
                "name": channel_name,
                "label": channel_label,
            },
            "time_window": {
                "from": time_range.get("start"),
                "to": time_range.get("end"),
                "label": context.get("time_window_label"),
            },
            "thread": {
                "ts": thread_ts,
                "permalink": self._find_thread_permalink(thread_ts, messages),
            },
            "graph": graph or {},
            "graph_highlights": self._build_graph_highlights(prepared_messages, graph),
            "analysis_hints": sections,
            "messages": prepared_messages,
        }
        return payload

    @staticmethod
    def _format_channel_label(channel_name: Optional[str], channel_id: Optional[str]) -> Optional[str]:
        if channel_name:
            if channel_name.startswith("#"):
                return channel_name
            return f"#{channel_name}"
        return channel_id

    @staticmethod
    def _find_thread_permalink(thread_ts: Optional[str], messages: List[Dict[str, Any]]) -> Optional[str]:
        if not thread_ts:
            return None
        for message in messages:
            if message.get("ts") == thread_ts or message.get("thread_ts") == thread_ts:
                return message.get("permalink")
        return None

    def _build_graph_highlights(
        self,
        messages: List[Dict[str, Any]],
        graph: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not messages and not graph:
            return {}

        def _collect_unique(key: str) -> List[str]:
            values = set()
            for message in messages:
                for value in message.get(key) or []:
                    if value:
                        values.add(value)
            return sorted(values)

        services = _collect_unique("service_ids")
        components = _collect_unique("component_ids")
        apis = _collect_unique("related_apis")
        labels = _collect_unique("labels")

        participant_counts: Counter[str] = Counter()
        for message in messages:
            user = message.get("user")
            if not user:
                continue
            participant_counts[user] += 1
        top_participants = [
            {"user": user, "messages": count}
            for user, count in participant_counts.most_common(5)
        ]

        topic_samples: List[Dict[str, Any]] = []
        decision_count = 0
        task_count = 0
        nodes = (graph or {}).get("nodes", [])
        for node in nodes or []:
            node_type = node.get("type")
            props = node.get("props") or {}
            if node_type == "Topic":
                topic_name = props.get("name") or props.get("topic")
                if topic_name:
                    topic_samples.append(
                        {
                            "topic": topic_name,
                            "sample": props.get("sample"),
                            "mentions": props.get("mentions"),
                        }
                    )
            elif node_type == "Decision":
                decision_count += 1
            elif node_type == "Task":
                task_count += 1

        highlights = {
            "services": services,
            "components": components,
            "apis": apis,
            "labels": labels,
            "top_participants": top_participants,
            "topic_samples": topic_samples[:5],
            "decision_count": decision_count,
            "task_count": task_count,
        }
        return highlights

    def _validate_response(self, response: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        required_keys = [
            "summary",
            "sections",
            "key_decisions",
            "next_actions",
            "open_questions",
            "references",
            "entities",
            "debug_metadata",
        ]
        missing = [key for key in required_keys if key not in response]
        if missing:
            return False, f"Missing keys: {missing}"
        if not isinstance(response.get("sections"), list):
            return False, "sections must be a list."
        if not isinstance(response.get("key_decisions"), list):
            return False, "key_decisions must be a list."
        if not isinstance(response.get("next_actions"), list):
            return False, "next_actions must be a list."
        if not isinstance(response.get("open_questions"), list):
            return False, "open_questions must be a list."
        if not isinstance(response.get("references"), list):
            return False, "references must be a list."
        if not isinstance(response.get("entities"), list):
            return False, "entities must be a list."
        return True, None

