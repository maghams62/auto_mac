import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ControlInputGuard:
    """Detect cancel/stop/no-op inputs before expensive orchestration."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        fallback_cfg = (config or {}).get("fallbacks", {})
        self.cancel_keywords = set(
            kw.strip().lower()
            for kw in fallback_cfg.get(
                "cancel_keywords",
                [
                    "cancel",
                    "never mind",
                    "nevermind",
                    "stop",
                    "abort",
                    "hold on",
                    "wait",
                    "forget it",
                    "nvm",
                    "quit",
                    "halt",
                ],
            )
        )
        self.ack_keywords = set(
            kw.strip().lower()
            for kw in fallback_cfg.get(
                "ack_keywords",
                ["ok", "okay", "k", "thanks", "thank you", "got it", "cool"],
            )
        )
        self.short_token_limit = fallback_cfg.get("short_token_limit", 3)
        self.heuristics_only_length = fallback_cfg.get("heuristics_only_length", 24)
        self.stop_commands = set(fallback_cfg.get("slash_stop_commands", ["stop", "cancel"]))
        self._emoji_pattern = re.compile(r"^[^\w\d]+$")

    def inspect(self, raw_request: str, slash_token: Optional[str] = None) -> Optional[Dict[str, str]]:
        """Return decision dict when input should short-circuit."""
        text = (raw_request or "").strip()
        if not text:
            return self._build_decision("noop", "No input detected. Ping me when you're ready.", "empty_input")

        lowered = text.lower()

        if slash_token:
            token_lower = slash_token.lower()
            if token_lower in self.stop_commands and len(text.split()) == 1:
                return self._build_decision("cancelled", "Okay, stopping here.", "slash_control")
            # Other slash commands are handled by the slash subsystem.
            return None

        if any(keyword in lowered for keyword in self.cancel_keywords):
            return self._build_decision("cancelled", "Got it — cancelling the request.", "cancel_keyword")

        if lowered in self.ack_keywords and len(text) <= self.heuristics_only_length:
            return self._build_decision("noop", "👍 Noted. Let me know when you need anything else.", "acknowledgement")

        if len(text) <= self.short_token_limit and text.isalpha():
            return self._build_decision("noop", "I didn't get that. Share a bit more detail when ready.", "short_token")

        if len(text) <= self.heuristics_only_length and not any(char.isalnum() for char in text):
            return self._build_decision("noop", "I'll wait for your next instruction.", "symbol_only")

        if (
            len(text) <= self.heuristics_only_length
            and len(text.split()) == 1
            and lowered not in self.stop_commands
            and not self._contains_action_keyword(lowered)
        ):
            return self._build_decision("noop", "I didn't quite catch that. Try rephrasing the request.", "low_signal_token")

        return None

    def _build_decision(self, status: str, message: str, reason: str) -> Dict[str, str]:
        return {"status": status, "message": message, "reason": reason}

    @staticmethod
    def _contains_action_keyword(lowered: str) -> bool:
        action_keywords = {
            "find",
            "search",
            "send",
            "email",
            "write",
            "open",
            "scan",
            "show",
            "plan",
            "map",
            "run",
            "start",
            "summarize",
            "summarise",
            "explain",
        }
        return any(lowered.startswith(keyword) for keyword in action_keywords)

