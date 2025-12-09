import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = """You classify short user inputs.
Labels:
- CONTROL: User wants to stop, cancel, or pause.
- NOISE: Input is accidental, empty, or nonsensical.
- ACTIONABLE: Clear instruction to perform a task.

Respond with exactly one label."""


class LowSignalClassifier:
    """Optional LLM-based classifier for ambiguous short requests."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, llm_client=None):
        fallback_cfg = (config or {}).get("fallbacks", {})
        classifier_cfg = fallback_cfg.get("llm_classifier", {})
        self.enabled = fallback_cfg.get("enable_low_signal_classifier", False)
        self.max_chars = classifier_cfg.get("max_chars", 160)
        self.model = classifier_cfg.get("model", "gpt-4o-mini")
        self.temperature = classifier_cfg.get("temperature", 0.0)
        self.max_tokens = classifier_cfg.get("max_tokens", 120)
        self.system_prompt = classifier_cfg.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
        self.llm_client = llm_client

    def should_classify(self, text: Optional[str]) -> bool:
        if not self.enabled:
            return False
        stripped = (text or "").strip()
        if not stripped:
            return False
        return len(stripped) <= self.max_chars

    def classify(self, text: str) -> str:
        if not self.should_classify(text):
            return "actionable"

        client = self._ensure_client()
        if not client:
            return "unknown"

        try:
            from langchain.schema import HumanMessage, SystemMessage
        except Exception as exc:  # pragma: no cover - langchain import failure
            logger.warning("[LOW SIGNAL] Missing langchain dependency: %s", exc)
            return "unknown"

        try:
            response = client.invoke(
                [
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=text.strip()),
                ]
            )
            label = (getattr(response, "content", "") or "").strip().split()[0].lower()
            if label in {"control", "cancel"}:
                return "control"
            if label in {"noise", "junk"}:
                return "noise"
            if label in {"actionable", "task"}:
                return "actionable"
            return "unknown"
        except Exception as exc:  # pragma: no cover - network issues
            logger.debug("[LOW SIGNAL] Classifier failed: %s", exc)
            return "unknown"

    def _ensure_client(self):
        if self.llm_client or not self.enabled:
            return self.llm_client

        try:
            from langchain_openai import ChatOpenAI
        except Exception as exc:  # pragma: no cover
            logger.warning("[LOW SIGNAL] Cannot initialize ChatOpenAI: %s", exc)
            return None

        try:
            self.llm_client = ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("[LOW SIGNAL] Failed to create LLM client: %s", exc)
            self.llm_client = None

        return self.llm_client

