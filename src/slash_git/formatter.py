"""
LLM formatter for Slash Git responses.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..utils import get_llm_params, parse_json_with_retry
from .models import GitQueryPlan

logger = logging.getLogger(__name__)

MAX_COMMITS = 20
MAX_PRS = 15
MAX_ISSUES = 15


class SlashGitPromptBundle:
    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root or Path(__file__).resolve().parents[2]
        prompts_dir = self.repo_root / "prompts" / "slash"
        agents_dir = self.repo_root / "agents" / "slash_git"
        self.reasoner_path = prompts_dir / "slash_git_reasoner.md"
        self.agent_context_path = agents_dir / "context.md"
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
        parts = [
            "You are the Cerebros /git reasoner. Summarize Git changes faithfully.",
            self.agent_context,
            self.reasoner_block,
        ]
        return "\n\n".join(part for part in parts if part)


class SlashGitLLMFormatter:
    def __init__(
        self,
        config: Dict[str, Any],
        *,
        llm_client: Optional[ChatOpenAI] = None,
        prompt_bundle: Optional[SlashGitPromptBundle] = None,
    ):
        self.config = config
        self.prompt_bundle = prompt_bundle or SlashGitPromptBundle()
        self._llm = llm_client
        self._llm_params = None
        if llm_client is None:
            self._llm_params = get_llm_params(
                config,
                default_temperature=0.2,
                max_tokens=1200,
                component="slash_git",
            )

    def generate(
        self,
        plan: GitQueryPlan,
        snapshot: Dict[str, Any],
        *,
        graph: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        payload = self._build_payload(plan, snapshot, graph or {})
        prompt_block = json.dumps(payload, indent=2, ensure_ascii=False)
        instructions = self.prompt_bundle.system_prompt or "You are the /git reasoner."

        messages = [
            SystemMessage(content=instructions),
            HumanMessage(
                content=(
                    "Use the schema above. Return ONLY valid JSON.\n"
                    f"{prompt_block}"
                )
            ),
        ]

        try:
            response = self._get_llm().invoke(messages)
        except Exception as exc:
            logger.warning("[SLASH GIT] LLM invocation failed: %s", exc)
            return None, str(exc)

        parsed, error = parse_json_with_retry(response.content)
        if not parsed:
            logger.warning("[SLASH GIT] LLM returned non-JSON payload: %s", error)
            return None, error or "LLM returned non-JSON payload."

        valid, validation_error = self._validate_response(parsed)
        if not valid:
            logger.warning("[SLASH GIT] Schema validation failed: %s", validation_error)
            return None, validation_error
        return parsed, None

    def _build_payload(self, plan: GitQueryPlan, snapshot: Dict[str, Any], graph: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "plan": self._serialize_plan(plan),
            "snapshot": self._serialize_snapshot(snapshot),
            "graph": graph,
        }
        return payload

    def _serialize_plan(self, plan: GitQueryPlan) -> Dict[str, Any]:
        return {
            "mode": plan.mode.value,
            "repo_id": plan.repo_id,
            "component_id": plan.component_id,
            "time_window": plan.time_window.to_dict() if plan.time_window else None,
            "authors": plan.authors,
            "labels": plan.labels,
            "topic": plan.topic,
            "user_query": plan.user_query,
        }

    def _serialize_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        commits = snapshot.get("commits") or []
        prs = snapshot.get("prs") or []
        issues = snapshot.get("issues") or []
        return {
            "commits": commits[:MAX_COMMITS],
            "prs": prs[:MAX_PRS],
            "issues": issues[:MAX_ISSUES],
            "meta": snapshot.get("meta") or {},
        }

    def _validate_response(self, response: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        required = [
            "summary",
            "sections",
            "notable_prs",
            "breaking_changes",
            "next_actions",
            "references",
            "debug_metadata",
        ]
        missing = [key for key in required if key not in response]
        if missing:
            return False, f"Missing keys: {missing}"
        list_fields = ["sections", "notable_prs", "breaking_changes", "next_actions", "references"]
        for field in list_fields:
            if not isinstance(response.get(field), list):
                return False, f"{field} must be a list."
        if not isinstance(response.get("debug_metadata"), dict):
            return False, "debug_metadata must be an object."
        return True, None

    def _get_llm(self) -> ChatOpenAI:
        if self._llm is None:
            if not self._llm_params:
                raise RuntimeError("LLM parameters not configured.")
            self._llm = ChatOpenAI(**self._llm_params)
        return self._llm

