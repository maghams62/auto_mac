from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional


class SlackConversationAnalyzer:
    """Heuristic analyzer that extracts structured facts from Slack messages."""

    DECISION_KEYWORDS = [
        "decided",
        "decision",
        "agree",
        "agreed",
        "approved",
        "final",
        "go with",
        "let's ship",
        "green light",
        "consensus",
    ]
    TASK_KEYWORDS = [
        "todo",
        "to-do",
        "follow up",
        "follow-up",
        "take care",
        "action item",
        "next step",
        "will do",
        "i will",
        "assign",
        "can you",
        "needs to",
        "scheduled",
    ]
    QUESTION_KEYWORDS = [
        "blocker",
        "unknown",
        "need clarity",
        "open question",
        "unclear",
        "pending",
    ]
    STOPWORDS = {
        "the",
        "and",
        "that",
        "this",
        "with",
        "from",
        "have",
        "will",
        "they",
        "there",
        "what",
        "when",
        "where",
        "about",
        "need",
        "just",
        "into",
        "onto",
        "already",
        "also",
        "maybe",
        "need",
        "next",
        "step",
        "steps",
        "then",
        "here",
        "been",
        "after",
        "before",
        "would",
        "could",
        "should",
        "like",
        "love",
    }

    def __init__(self, messages: List[Dict[str, Any]]):
        self.messages = messages or []

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def build_sections(self, keywords: Optional[List[str]] = None) -> Dict[str, Any]:
        topics = self._extract_topics(keywords or [])
        decisions = self._extract_decisions()
        tasks = self._extract_tasks()
        open_questions = self._extract_open_questions()
        references = self._collect_references()

        return {
            "topics": topics,
            "decisions": decisions,
            "tasks": tasks,
            "open_questions": open_questions,
            "references": references,
        }

    def build_summary(self, context: Dict[str, Any], sections: Dict[str, Any]) -> str:
        channel_label = context.get("channel_label", context.get("channel_id", "Slack"))
        time_span = context.get("time_window_label", "recently")
        total_messages = len(self.messages)
        topic_names = [topic["topic"] for topic in sections.get("topics", [])[:3]]

        parts = [
            f"{channel_label} {time_span} saw {total_messages} message{'s' if total_messages != 1 else ''}",
        ]
        if topic_names:
            parts.append(f"touching on {', '.join(topic_names)}")

        if sections.get("decisions"):
            parts.append(f"{len(sections['decisions'])} decision(s)")
        if sections.get("tasks"):
            parts.append(f"{len(sections['tasks'])} follow-up item(s)")

        summary = "; ".join([p for p in parts if p]) + "."
        if sections.get("open_questions"):
            summary += f" {len(sections['open_questions'])} open question(s) remain."
        return summary

    def build_graph(self, context: Dict[str, Any], sections: Dict[str, Any]) -> Dict[str, Any]:
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        conversation_id = context["conversation_id"]
        conversation_node = {
            "id": conversation_id,
            "type": "Conversation",
            "props": {
                "channel_id": context.get("channel_id"),
                "channel_name": context.get("channel_name"),
                "thread_ts": context.get("thread_ts"),
                "time_window": context.get("time_window"),
                "mode": context.get("mode"),
            },
        }
        nodes.append(conversation_node)

        # Participants
        participants = self._collect_participants()
        for user_id, name in participants.items():
            participant_id = self._stable_id("participant", user_id)
            nodes.append({"id": participant_id, "type": "Participant", "props": {"user_id": user_id, "name": name}})
            edges.append({"from": participant_id, "to": conversation_id, "type": "PARTICIPATED_IN"})

        # Topics
        for topic in sections.get("topics", []):
            topic_id = self._stable_id("topic", topic["topic"])
            nodes.append({
                "id": topic_id,
                "type": "Topic",
                "props": {"name": topic["topic"], "mentions": topic.get("mentions"), "sample": topic.get("sample")},
            })
            edges.append({"from": conversation_id, "to": topic_id, "type": "DISCUSS"})

        # Decisions
        for decision in sections.get("decisions", []):
            decision_id = self._stable_id("decision", decision["timestamp"], decision.get("text"))
            nodes.append({
                "id": decision_id,
                "type": "Decision",
                "props": decision,
            })
            edges.append({"from": conversation_id, "to": decision_id, "type": "RESULTED_IN"})
            if decision.get("participant_id"):
                participant_id = self._stable_id("participant", decision["participant_id"])
                edges.append({"from": participant_id, "to": decision_id, "type": "PROPOSED_BY"})

        # Tasks
        for task in sections.get("tasks", []):
            task_id = self._stable_id("task", task["timestamp"], task.get("description"))
            nodes.append({"id": task_id, "type": "Task", "props": task})
            edges.append({"from": conversation_id, "to": task_id, "type": "NEXT_STEP"})
            if task.get("assignee_id"):
                participant_id = self._stable_id("participant", task["assignee_id"])
                edges.append({"from": participant_id, "to": task_id, "type": "ASSIGNED_TO"})

        # References
        for reference in sections.get("references", []):
            ref_id = self._stable_id("reference", reference["url"])
            nodes.append({"id": ref_id, "type": "Reference", "props": reference})
            edges.append({"from": conversation_id, "to": ref_id, "type": "MENTIONS"})

        return {"nodes": nodes, "edges": edges}

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------
    def _extract_topics(self, seed_keywords: List[str]) -> List[Dict[str, Any]]:
        counter: Counter[str] = Counter()
        for message in self.messages:
            for token in self._tokenize(message.get("text", "")):
                counter[token] += 1

        for keyword in seed_keywords:
            if keyword:
                counter[keyword.lower()] += 2

        topics: List[Dict[str, Any]] = []
        for topic, count in counter.most_common(5):
            sample = self._find_snippet(topic)
            topics.append({"topic": topic, "mentions": count, "sample": sample})
        return topics

    def _extract_decisions(self) -> List[Dict[str, Any]]:
        decisions: List[Dict[str, Any]] = []
        for message in self.messages:
            text = message.get("text", "")
            lower = text.lower()
            if any(keyword in lower for keyword in self.DECISION_KEYWORDS):
                decisions.append({
                    "text": text.strip(),
                    "timestamp": message.get("ts"),
                    "participant": message.get("user_name"),
                    "participant_id": message.get("user_id"),
                    "permalink": message.get("permalink"),
                })
        return decisions

    def _extract_tasks(self) -> List[Dict[str, Any]]:
        tasks: List[Dict[str, Any]] = []
        for message in self.messages:
            text = message.get("text", "")
            lower = text.lower()
            mention = message.get("mentions", [])
            has_keyword = any(keyword in lower for keyword in self.TASK_KEYWORDS)
            if has_keyword or mention:
                assignee = mention[0]["display"] if mention else message.get("user_name")
                assignee_id = mention[0]["user_id"] if mention else message.get("user_id")
                tasks.append({
                    "description": text.strip(),
                    "timestamp": message.get("ts"),
                    "assignee": assignee,
                    "assignee_id": assignee_id,
                    "permalink": message.get("permalink"),
                })
        return tasks

    def _extract_open_questions(self) -> List[Dict[str, Any]]:
        questions: List[Dict[str, Any]] = []
        for message in self.messages:
            text = message.get("text", "")
            lower = text.lower()
            if "?" in text or any(keyword in lower for keyword in self.QUESTION_KEYWORDS):
                questions.append({
                    "text": text.strip(),
                    "timestamp": message.get("ts"),
                    "participant": message.get("user_name"),
                    "permalink": message.get("permalink"),
                })
        return questions

    def _collect_references(self) -> List[Dict[str, Any]]:
        references: List[Dict[str, Any]] = []
        for message in self.messages:
            for reference in message.get("references", []):
                reference_copy = dict(reference)
                reference_copy.setdefault("message_ts", message.get("ts"))
                references.append(reference_copy)
        return references

    def _collect_participants(self) -> Dict[str, str]:
        participants: Dict[str, str] = {}
        for message in self.messages:
            user_id = message.get("user_id")
            user_name = message.get("user_name") or user_id
            if user_id and user_name:
                participants[user_id] = user_name
        return participants

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _tokenize(self, text: str) -> List[str]:
        tokens: List[str] = []
        for token in re.findall(r"[A-Za-z0-9_/.-]+", text.lower()):
            if len(token) < 4:
                continue
            if token in self.STOPWORDS:
                continue
            tokens.append(token)
        return tokens

    def _find_snippet(self, token: str) -> Optional[str]:
        for message in self.messages:
            if token in message.get("text", "").lower():
                return message.get("text", "")[:240]
        return None

    @staticmethod
    def _stable_id(*parts: Optional[str]) -> str:
        joined = "|".join([part for part in parts if part])
        if not joined:
            joined = datetime.utcnow().isoformat()
        return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:20]

