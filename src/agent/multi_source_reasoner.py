"""
Multi-Source Reasoning Engine - Orchestrate evidence gathering and analysis.

This module provides the core reasoning engine that:
1. Infers relevant sources from a query
2. Gathers evidence from multiple retrievers
3. Uses LLM to detect conflicts between sources
4. Uses LLM to detect gaps (missing information)
5. Generates comprehensive summaries with source attribution
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Set

from .evidence import Evidence, EvidenceCollection
from src.activity_graph.prioritization import DOC_SEVERITY_WEIGHTS, get_activity_signal_weights
from src.settings.policy import get_priority_list
from .evidence_retrievers import get_retriever

logger = logging.getLogger(__name__)


# Keywords that suggest specific sources
SOURCE_KEYWORDS = {
    "git": [
        "pr", "pull request", "commit", "merge", "branch", "code",
        "diff", "changed", "implemented", "fixed", "refactor",
    ],
    "slack": [
        "discuss", "discussed", "said", "mentioned", "talk", "conversation",
        "chat", "message", "slack", "asked", "team",
    ],
    "docs": [
        "documentation", "docs", "guide", "readme", "wiki", "manual",
        "documented", "reference",
    ],
    "issues": [
        "issue", "bug", "ticket", "reported", "tracking", "assigned",
        "priority", "severity",
    ],
    "doc_issues": [
        "doc issue", "doc issues", "documentation bug", "doc drift",
        "docs mismatch", "documentation gap", "docs broken",
    ],
    "activity_graph": [
        "activity", "dissatisfaction", "hotspot", "priority",
        "component status", "component activity", "which component", "needs docs",
        "comp:",
    ],
}

_DEFAULT_PRIORITY_ORDER = ["git", "docs", "doc_issues", "activity_graph", "issues", "slack", "unknown"]

# Generic drift patterns (version + requirement language). Intentionally NOT vat-code specific.
VERSION_PATTERN = re.compile(r"(?:/v(?P<path_version>\d+))|\bv(?P<token_version>\d+)\b", re.IGNORECASE)
OPTIONAL_PATTERN = re.compile(r"\boptional\b", re.IGNORECASE)
REQUIRED_PATTERN = re.compile(r"\brequired\b", re.IGNORECASE)


def _priority_mapping() -> Dict[str, int]:
    try:
        priority = get_priority_list("api_params")
    except Exception as exc:  # pragma: no cover - settings failures rare
        logger.warning("[REASONER] Falling back to default source priority: %s", exc)
        priority = []
    mapping: Dict[str, int] = {}
    if priority:
        for idx, source in enumerate(priority):
            mapping[source] = idx + 1
    rank = len(mapping) + 1
    for source in _DEFAULT_PRIORITY_ORDER:
        if source not in mapping:
            mapping[source] = rank
            rank += 1
    return mapping


class MultiSourceReasoner:
    """
    Orchestrates evidence gathering and analysis across multiple sources.

    This engine:
    - Infers which sources to query based on the user's question
    - Gathers evidence from Git, Slack, docs, issues, etc.
    - Detects conflicts between sources using LLM
    - Detects information gaps using LLM
    - Generates a comprehensive summary with source attribution
    """

    def __init__(self, config: Dict[str, Any], llm_client: Optional[Any] = None):
        """
        Initialize the reasoning engine.

        Args:
            config: Configuration dictionary
            llm_client: Optional LLM client for analysis (if None, will be created)
        """
        self.config = config
        self.llm_client = llm_client
        self.enabled_sources = self.determine_enabled_sources(config)

        # Initialize retrievers for enabled sources only
        self.retrievers = {}
        for source_type in self.enabled_sources:
            retriever = get_retriever(source_type, config)
            if retriever:
                self.retrievers[source_type] = retriever

        logger.info(
            "[REASONER] Initialized with %s retrievers (enabled sources=%s)",
            len(self.retrievers),
            self.enabled_sources,
        )

    def query(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        git_limit: int = 10,
        slack_limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Execute a multi-source query with reasoning.

        Args:
            query: User's question or search query
            sources: Optional list of sources to query (if None, will be inferred)
            git_limit: Max PRs to retrieve from Git
            slack_limit: Max messages to retrieve from Slack

        Returns:
            Dictionary with evidence, analysis, and summary
        """
        logger.info(f"[REASONER] Processing query: {query}")

        # Step 1: Infer relevant sources if not provided
        if not sources:
            sources = self._infer_relevant_sources(query)
            logger.info(f"[REASONER] Inferred sources: {sources}")
        else:
            sources = [src for src in sources if src in self.enabled_sources]
            if not sources:
                sources = self._infer_relevant_sources(query)
                logger.info(
                    "[REASONER] Requested sources disabled, falling back to inferred: %s",
                    sources,
                )
            else:
                logger.info(f"[REASONER] Using provided sources: {sources}")

        # Step 2: Gather evidence from each source
        all_evidence = EvidenceCollection(query=query)

        for source_type in sources:
            retriever = self.retrievers.get(source_type)
            if not retriever:
                logger.warning(f"[REASONER] No retriever available for: {source_type}")
                continue

            try:
                if source_type == "git":
                    evidence = retriever.retrieve(query, limit=git_limit)
                elif source_type == "slack":
                    evidence = retriever.retrieve(query, limit=slack_limit)
                else:
                    evidence = retriever.retrieve(query)

                # Merge into main collection
                for e in evidence.evidence_list:
                    all_evidence.add(e)

                logger.info(f"[REASONER] Gathered {len(evidence)} evidence from {source_type}")

            except Exception as exc:
                logger.exception(f"[REASONER] Error retrieving from {source_type}: {exc}")

        # Step 3: Build per-source stats and simple relevance signals
        stats_by_source = all_evidence.stats_by_source()
        counts_by_source = {source: data.get("count", 0) for source, data in stats_by_source.items()}
        latest_timestamp_by_source = {
            source: data.get("latest_timestamp") for source, data in stats_by_source.items()
        }
        sources_without_evidence = [source for source in sources if source not in stats_by_source]

        relevant_evidence, relevant_sources = self._compute_relevant_evidence(query, all_evidence)
        has_relevant_sources = bool(relevant_sources)

        # If nothing in the evidence set appears related to the query concepts,
        # short-circuit with a safe \"no relevant evidence\" summary.
        if not has_relevant_sources:
            logger.info(
                "[REASONER] No relevant evidence found for query=%s (sources=%s, evidence_count=%s)",
                query,
                sources,
                len(all_evidence),
            )
            gaps = [
                {
                    "type": "missing_source",
                    "description": (
                        f'No relevant evidence found for \"{query}\" across '
                        "Slack, Git, Docs, doc issues, Issues, and Activity graph."
                    ),
                }
            ]
            summary = self._build_no_evidence_summary(
                query=query,
                sources=sources,
                counts_by_source=counts_by_source,
            )
            return {
                "query": query,
                "sources_queried": sources,
                "evidence_count": len(all_evidence),
                "evidence": all_evidence.to_dict(),
                "summary_context": {
                    "counts_by_source": counts_by_source,
                    "latest_timestamp_by_source": latest_timestamp_by_source,
                },
                "sources_without_evidence": sources_without_evidence,
                "drift_hints": {},
                "conflicts": [],
                "gaps": gaps,
                "summary": summary,
                "relevant_sources": sorted(relevant_sources),
            }

        # Step 4: Analyze evidence for conflicts, gaps, and drift when we have relevant hits
        conflicts = self._detect_conflicts(all_evidence)
        gaps = self._detect_gaps(all_evidence, query)
        drift_hints = self._detect_drift(all_evidence)

        # Step 5: Generate summary via LLM
        summary = self._generate_summary(
            all_evidence,
            conflicts,
            gaps,
            summary_context={
                "counts_by_source": counts_by_source,
                "latest_timestamp_by_source": latest_timestamp_by_source,
            },
            drift_hints=drift_hints,
            sources_without_evidence=sources_without_evidence,
        )

        return {
            "query": query,
            "sources_queried": sources,
            "evidence_count": len(all_evidence),
            "evidence": all_evidence.to_dict(),
            "summary_context": {
                "counts_by_source": counts_by_source,
                "latest_timestamp_by_source": latest_timestamp_by_source,
            },
            "sources_without_evidence": sources_without_evidence,
            "drift_hints": drift_hints,
            "conflicts": conflicts,
            "gaps": gaps,
            "summary": summary,
        }

    def infer_sources(self, query: str) -> List[str]:
        """
        Public helper to expose source inference without running full pipeline.
        """
        return self._infer_relevant_sources(query)

    def _infer_relevant_sources(self, query: str) -> List[str]:
        """
        Infer which sources are relevant based on query keywords.

        Args:
            query: User's query

        Returns:
            List of relevant source types
        """
        query_lower = query.lower()
        relevant_sources = set()

        # Check for keyword matches
        for source_type, keywords in SOURCE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query_lower:
                    relevant_sources.add(source_type)
                    break

        # Default: if no specific keywords, query git and slack
        # (these are the most commonly useful sources)
        if not relevant_sources:
            relevant_sources = {"git", "slack", "docs"}

        # Sort by priority then filter by enabled sources
        priority_order = _priority_mapping()
        ordered = sorted(relevant_sources, key=lambda s: priority_order.get(s, 99))
        filtered = [source for source in ordered if source in self.enabled_sources]

        if not filtered:
            # fallback to preferred defaults within enabled sources
            fallback = [src for src in ["git", "slack", "docs"] if src in self.enabled_sources]
            filtered = fallback or list(self.enabled_sources)

        return filtered

    def _compute_relevant_evidence(
        self,
        query: str,
        evidence: EvidenceCollection,
    ) -> tuple[list[Evidence], Set[str]]:
        """
        Compute a very cheap relevance signal between the query and each evidence item.

        We intentionally keep this lexical and conservative: only evidence that shares
        at least one salient keyword (e.g., \"vat\", \"billing\", \"langgraph\") with
        the query is treated as relevant.
        """
        query_terms: Set[str] = set()
        for raw in re.split(r"[^a-zA-Z0-9]+", (query or "").lower()):
            if not raw or len(raw) < 4:
                continue
            if raw in {
                "what",
                "whats",
                "with",
                "that",
                "this",
                "there",
                "about",
                "issue",
                "issues",
                "problem",
                "problems",
                "please",
                "kindly",
                "help",
                "summarize",
                "summary",
            }:
                continue
            query_terms.add(raw)

        if not query_terms or len(evidence) == 0:
            return [], set()

        relevant: list[Evidence] = []
        relevant_sources: Set[str] = set()
        for item in evidence.evidence_list:
            haystack_parts: list[str] = [
                item.source_name.lower(),
                (item.content or "").lower(),
            ]
            metadata = item.metadata or {}
            for key in ("doc_id", "doc_path", "title", "summary"):
                value = metadata.get(key)
                if isinstance(value, str):
                    haystack_parts.append(value.lower())
            haystack = " ".join(haystack_parts)
            if any(term in haystack for term in query_terms):
                relevant.append(item)
                relevant_sources.add(str(item.source_type or "unknown"))

        return relevant, relevant_sources

    def _build_no_evidence_summary(
        self,
        *,
        query: str,
        sources: List[str],
        counts_by_source: Dict[str, int],
    ) -> str:
        """
        Build a structured abstain-style summary when no evidence is relevant.

        This mirrors the normal SOURCE EVIDENCE → DRIFT → CANONICAL CURRENT TRUTH →
        ACTIONS → GAPS → INCIDENT SUGGESTION flow, but explicitly communicates that
        nothing in the current evidence set matches the query concepts.
        """
        # Normalize source order to the same order the LLM prompt uses.
        ordered_sources = ["slack", "git", "docs", "doc_issues", "issues", "activity_graph"]
        queried = set(sources)

        def _row(label: str, key: str) -> str:
            if key in {"docs", "doc_issues"}:
                # Treat docs + doc_issues as a single row in the human-readable summary.
                docs_count = counts_by_source.get("docs", 0)
                doc_issues_count = counts_by_source.get("doc_issue", 0)
                total = docs_count + doc_issues_count
                if key == "docs":
                    # Only emit this once.
                    return f"- {label}: {total} item(s), none mentioning the query terms."
                return ""
            count = counts_by_source.get(key, 0)
            if key not in queried and count == 0:
                return f"- {label}: not queried for this request."
            return f"- {label}: {count} item(s), none mentioning the query terms."

        lines: List[str] = []
        lines.append("SOURCE EVIDENCE:")
        lines.append(_row("Slack", "slack"))
        lines.append(_row("Git", "git"))
        docs_row = _row("Docs / doc issues", "docs")
        if docs_row:
            lines.append(docs_row)
        lines.append(_row("Issues", "issues"))
        lines.append(_row("Activity graph", "activity_graph"))
        lines.append("")
        lines.append("DRIFT:")
        lines.append("- Previous state: No relevant historical evidence available for this query.")
        lines.append("- Current behavior: No relevant evidence available for this query.")
        lines.append("- Drift type: none.")
        lines.append("")
        lines.append("CANONICAL CURRENT TRUTH:")
        lines.append(
            f'- No relevant evidence was found for the query "{query}" across the available sources.'
        )
        lines.append("")
        lines.append("ACTIONS:")
        lines.append(
            "- Consider instrumenting logs, adding monitoring, or creating a new issue specifically for this query."
        )
        lines.append(
            "- Re-run Cerebros after new Slack, Git, Docs, Issues, or Activity graph signals referencing this query exist."
        )
        lines.append("")
        lines.append("GAPS:")
        lines.append(
            f'- missing_source: No Slack, Git, Docs, Issues, or Activity graph entries mention "{query}".'
        )
        lines.append("")
        lines.append("INCIDENT SUGGESTION:")
        lines.append("- no – no relevant evidence was found for this query.")
        return "\n".join(lines)

    @staticmethod
    def determine_enabled_sources(config: Optional[Dict[str, Any]]) -> List[str]:
        config = config or {}
        search_modalities = ((config.get("search") or {}).get("modalities") or {})

        enabled: List[str] = []

        if search_modalities:
            for modality, settings in search_modalities.items():
                mapped = MultiSourceReasoner._map_modality_to_source(modality)
                if not mapped:
                    continue
                if not MultiSourceReasoner._modality_enabled(settings):
                    continue
                if mapped not in enabled:
                    enabled.append(mapped)
        else:
            enabled.extend(["git", "slack", "docs"])

        if "issues" not in enabled:
            include_issues = (
                (config.get("activity_ingest") or {})
                .get("git", {})
                .get("include_issues", True)
            )
            if include_issues:
                enabled.append("issues")

        if "doc_issues" not in enabled:
            doc_ingest_cfg = (config.get("activity_ingest") or {}).get("doc_issues") or {}
            doc_enabled = doc_ingest_cfg.get("enabled", True)
            doc_path = (
                (config.get("activity_graph") or {}).get("doc_issues_path")
                or doc_ingest_cfg.get("path")
            )
            if doc_enabled and doc_path:
                enabled.append("doc_issues")

        graph_enabled = bool((config.get("graph") or {}).get("enabled", False))
        activity_graph_cfg = config.get("activity_graph") or {}
        if graph_enabled and activity_graph_cfg and "activity_graph" not in enabled:
            enabled.append("activity_graph")

        return enabled

    @staticmethod
    def _map_modality_to_source(modality: str) -> Optional[str]:
        mapping = {
            "git": "git",
            "slack": "slack",
            "docs": "docs",
            "files": "docs",
            "issues": "issues",
            "doc_issues": "doc_issues",
            "activity_graph": "activity_graph",
        }
        return mapping.get(modality.lower())

    @staticmethod
    def _modality_enabled(settings: Dict[str, Any]) -> bool:
        if settings is None:
            return True
        if isinstance(settings, dict) and "enabled" in settings:
            return bool(settings["enabled"])
        return True

    def _detect_conflicts(self, evidence: EvidenceCollection) -> List[Dict[str, Any]]:
        """
        Detect conflicts between evidence from different sources.

        Uses LLM to identify cases where sources provide contradictory information.

        Args:
            evidence: Evidence collection to analyze

        Returns:
            List of detected conflicts
        """
        if len(evidence) < 2:
            return []

        # Build prompt for LLM
        prompt = self._build_conflict_detection_prompt(evidence)

        try:
            # Use LLM to detect conflicts
            conflicts_text = self._call_llm(prompt)

            # Parse LLM response
            conflicts = self._parse_conflict_response(conflicts_text)

            logger.info(f"[REASONER] Detected {len(conflicts)} conflicts")
            return conflicts

        except Exception as exc:
            logger.exception(f"[REASONER] Error detecting conflicts: {exc}")
            return []

    def _detect_gaps(self, evidence: EvidenceCollection, query: str) -> List[Dict[str, Any]]:
        """
        Detect information gaps - questions that remain unanswered.

        Uses LLM to identify missing information that would help answer the query.

        Args:
            evidence: Evidence collection to analyze
            query: Original user query

        Returns:
            List of detected gaps
        """
        if len(evidence) == 0:
            return [{
                "type": "no_evidence",
                "description": "No evidence found from any source.",
            }]

        # Build prompt for LLM
        prompt = self._build_gap_detection_prompt(evidence, query)

        try:
            # Use LLM to detect gaps
            gaps_text = self._call_llm(prompt)

            # Parse LLM response
            gaps = self._parse_gap_response(gaps_text)

            logger.info(f"[REASONER] Detected {len(gaps)} gaps")
            return gaps

        except Exception as exc:
            logger.exception(f"[REASONER] Error detecting gaps: {exc}")
            return []

    def _generate_summary(
        self,
        evidence: EvidenceCollection,
        conflicts: List[Dict[str, Any]],
        gaps: List[Dict[str, Any]],
        summary_context: Optional[Dict[str, Any]] = None,
        drift_hints: Optional[Dict[str, Any]] = None,
        sources_without_evidence: Optional[List[str]] = None,
    ) -> str:
        """
        Generate comprehensive summary with source attribution.

        Args:
            evidence: Evidence collection
            conflicts: Detected conflicts
            gaps: Detected gaps

        Returns:
            Summary text
        """
        if len(evidence) == 0:
            return "No evidence found to answer this query."

        # Build prompt for LLM
        prompt = self._build_summary_prompt(
            evidence,
            conflicts,
            gaps,
            summary_context=summary_context,
            drift_hints=drift_hints,
            sources_without_evidence=sources_without_evidence,
        )
        logger.debug("[CEREBROS_SUMMARY_PROMPT]\n%s", prompt)

        try:
            summary = self._call_llm(prompt)
            logger.info(f"[REASONER] Generated summary ({len(summary)} chars)")
            return summary

        except Exception as exc:
            logger.exception(f"[REASONER] Error generating summary: {exc}")
            return "Error generating summary. See evidence for details."

    def _build_conflict_detection_prompt(self, evidence: EvidenceCollection) -> str:
        """Build LLM prompt for conflict detection."""
        prompt = f"""You are analyzing evidence from multiple sources to detect conflicts.

{evidence.format_for_llm()}

TASK: Identify any contradictions or conflicts between the evidence from different sources.

For each conflict, respond in this format:
CONFLICT:
- Source 1: [source name]
- Source 2: [source name]
- Description: [what contradicts]

If no conflicts exist, respond with:
NO_CONFLICTS

Your response:"""
        return prompt

    def _build_gap_detection_prompt(self, evidence: EvidenceCollection, query: str) -> str:
        """Build LLM prompt for gap detection."""
        prompt = f"""You are analyzing evidence to detect information gaps.

QUERY: {query}

{evidence.format_for_llm()}

TASK: Identify what information is MISSING that would help fully answer the query.
Focus on gaps, not conflicts. What questions remain unanswered?

For each gap, respond in this format:
GAP:
- Type: [missing_source | incomplete_data | unclear]
- Description: [what's missing]

If no significant gaps exist, respond with:
NO_GAPS

Your response:"""
        return prompt

    def _build_summary_prompt(
        self,
        evidence: EvidenceCollection,
        conflicts: List[Dict[str, Any]],
        gaps: List[Dict[str, Any]],
        summary_context: Optional[Dict[str, Any]] = None,
        drift_hints: Optional[Dict[str, Any]] = None,
        sources_without_evidence: Optional[List[str]] = None,
    ) -> str:
        """Build LLM prompt for summary generation."""
        metadata_block = self._metadata_block(evidence)

        conflicts_section = ""
        if conflicts:
            conflicts_section = "\n\nCONFLICTS DETECTED:\n" + "\n".join(
                f"- {c.get('description', 'Unknown conflict')}" for c in conflicts
            )

        gaps_section = ""
        if gaps:
            gaps_section = "\n\nINFORMATION GAPS (AUTO-DETECTED):\n" + "\n".join(
                f"- {g.get('description', 'Unknown gap')}" for g in gaps
            )

        weight_hint = self._signal_weight_hint()
        weight_section = ""
        if weight_hint:
            weight_section = f"\nSOURCE WEIGHTS:\n{weight_hint}\n"

        structured_context_block = self._structured_context_block(
            summary_context,
            sources_without_evidence or [],
        )
        drift_hint_block = self._drift_hints_block(drift_hints)
        examples = self._summary_examples()
        stats_block = self._evidence_stats_block(evidence)

        # The model should output exactly these headings, in this order.
        response_format = (
            "\nRESPONSE FORMAT (emit these headings verbatim, in this order):\n"
            "SOURCE EVIDENCE:\n"
            "GRAPH EVIDENCE:\n"
            "DRIFT:\n"
            "CANONICAL CURRENT TRUTH:\n"
            "ACTIONS:\n"
            "GAPS:\n"
            "INCIDENT SUGGESTION:\n"
        )

        prompt = f"""You are the Cerebros multi-source drift analysis engine.

Your job is to:
1. Read evidence from multiple sources (Slack, Git, Docs/doc issues, Issues, Activity graph).
2. Understand what the user query is actually about (feature, endpoint, field, component, version, quota, etc.).
3. Explain what each source says **specifically about that query**.
4. Explain how those sources drift from each other over time.
5. Decide what is **canonically true right now**, using recency and source weights.
6. Recommend concrete actions and explicitly list gaps / missing information.
7. Decide whether this should be treated as an incident.

You are operating on **pre-fetched graph results and summaries** – do NOT hallucinate new entities, endpoints, fields, or numbers that are not present in the evidence or structured context.

QUERY (from user / investigation):

{evidence.query}

RAW EVIDENCE (grouped by source, already filtered by the system):

{evidence.format_for_llm()}
{metadata_block}
{structured_context_block}
{drift_hint_block}
{conflicts_section}
{gaps_section}
{weight_section}
{stats_block}
{examples}

TRUST & PRIORITY MODEL (how to weigh sources):

- Default trust ordering when facts conflict:
  1) Git (code, PRs, migrations, configs)
  2) Docs / doc issues (published and tracked documentation state)
  3) Slack (messages, announcements, incident threads)
  4) Issues / incident records
  5) Activity graph / aggregate signals

- Modify this using:
  - **Recency**: Newer evidence generally outweighs older evidence.
  - **Ownership**: Evidence from relevant teams (e.g., payments-team, billing-service owners, docs-portal maintainers) is more authoritative for their area.
  - **Severity / blast radius**: High-severity doc issues or incident channels can temporarily outweigh stale Git/docs if they describe active breakage.
  - **Multiplicity**: Many consistent PRs and docs pointing one way are stronger than a single Slack message pointing the other way.

Use this default reasoning:
- When Git and Docs disagree: favor Git unless Docs are significantly newer or explicitly canonical.
- When Slack vs Git + Docs: favor Git + Docs, but allow **very recent Slack in incident/ops channels** to describe “current behavior” before Git/docs catch up.
- When Activity graph shows a hotspot: treat it as a signal that drift matters and should be prioritized, not as ground truth.

INTERNAL REASONING STEPS (think this through silently; do NOT print these steps):

1. **Understand the query**
   - Extract the core subject(s): endpoint paths (/v1/payments/create, /v4/payments/create), fields (vat_code, api_key), components (comp:payments), services, quotas, versions, or specific errors.
   - Identify explicit version markers (v1, v2, v4), “optional” vs “required” language, quantity limits, and other policy-like statements.

2. **Identify relevant evidence per source**
   - For each source group (Slack, Git, Docs/doc issues, Issues, Activity graph), pick evidence that clearly mentions the query concepts.
   - Use METADATA YOU MUST USE and STRUCTURED CONTEXT to understand which components, services, docs, doc issues, and graph entities are in play.
   - If a source was queried but has **no relevant evidence**, mark it as “0 (queried, no matching evidence found)” and do **not** fabricate content.

3. **Graph reasoning**
   - From metadata (component_ids, service_ids, doc_path, doc_issue_id, entity_id) infer the key nodes (Components, Services, Docs, DocIssues, APIEndpoints, Issues) and relationships (EXPOSES_ENDPOINT, OWNS_CODE, DEPENDS_ON, SUPPORTS, EMITTED).
   - Identify which nodes and edges are actually touched for this query.
   - Summarize the minimal connected subgraph relevant to the query; do not describe the entire graph.

4. **Drift analysis**
   - Using DRIFT HINTS and timestamps, contrast:
     - Previous state: what older docs/git/slack promised or enforced.
     - Current behavior: what newer git/slack/docs show now.
   - Decide drift kind: **field requirement drift**, **version drift**, **quota drift**, **copy/docs drift**, or **none**.
   - Always tie drift back to **specific sources**, citing PRs, doc paths, and channels by name.

5. **Canonical current truth**
   - Combine trust ordering + recency + severity to decide what is true **right now**.
   - Explicitly state which sources you are trusting and why, e.g.:
     - “Git PR #2041 + Slack #incidents (Dec 8) are the newest and override payments_api.md (Dec 1).”
     - “Docs and multiple PRs agree, while Slack chatter is older and inconsistent.”
   - Include key numeric/policy details (limits, required fields, **rolling 24h ceilings**, etc.) from the trusted evidence, even if the user did not explicitly ask for all of them, as long as they are relevant to the query.
   - Make it clear when you are making a **best-effort judgment** due to partial/conflicting information.

6. **Actions**
   - Propose concrete next steps.
   - Prioritize:
     1) Fix docs and user-facing communication when drift exists.
     2) Align code behavior with the decision.
     3) Communication / follow-up investigations (which team/channel).
   - Use doc path / component / service metadata to hint at owners (e.g., “docs-portal owner”, “billing-service team”, “#payments-team”).

7. **Gaps**
   - Explicitly list **missing evidence** (sources with 0 relevant items) and **missing details** (e.g., no Git diff for behavior described only in Slack).
   - For each gap, say what follow-up would help: “Need PR or changelog to match Slack announcement”, “Need billing-engineering confirmation on temporary quota”, etc.
   - Call out **educated guesses** you had to make where data was incomplete.

8. **Incident suggestion**
   - Decide if this should be treated as an incident and justify briefly.
   - Consider severity, blast radius, and whether customers/users are being broken or misled.
   - Answer: “yes – …reason…” or “no – …reason…”.

Now produce a **single final answer** using exactly the following headings and behavior:

{response_format}

DETAILED REQUIREMENTS FOR EACH HEADING:

1) SOURCE EVIDENCE:
- Goal: For each source, answer: “Given this query, what did this source actually say about it?”
- Emit exactly one bullet per source in this fixed order:
  - Slack
  - Git
  - Docs / doc issues
  - Issues
  - Activity graph
- Each line must:
  - Start with the source and a brief, query-specific summary:
    - e.g., “Slack: 3 messages (latest 0.5h ago) in #payments-team reporting 400 errors on /v1/payments/create when vat_code is missing.”
    - e.g., “Git: 1 PR (PR #2041) changing /v1/payments/create to require vat_code.”
    - e.g., “Docs / doc issues: payments_api.md still marks vat_code optional; docissue-coreapi-vat tracks this drift as high severity.”
  - Include counts and recency from STRUCTURED CONTEXT.
  - If the source was queried but has no matches: say “0 (queried, no matching evidence found)” and do **not** invent content.
  - If the source was not queried: explicitly say “not queried for this request.”

2) GRAPH EVIDENCE:
- Summarize the **nodes and relationships** touched for this query:
  - Mention components, services, docs, doc issues, API endpoints, and issues by ID/path where available.
  - Describe key relationships in simple language:
    - e.g., “comp:payments EXPOSES_ENDPOINT /v1/payments/create documented in doc:payments_api.md and linked to docissue:docissue-coreapi-vat.”
- Focus on the minimal subgraph that explains drift; if graph metadata is too sparse, say so briefly.

3) DRIFT:
- Use three bullets:
  - “Previous state:” what older docs/git/slack said, with explicit citations (doc paths, PR IDs, channels, dates).
  - “Current behavior:” what newer sources say now, with explicit citations.
  - “Drift type:” one of [field requirement drift | version drift | quota drift | copy/docs drift | none].

4) CANONICAL CURRENT TRUTH:
- 1–3 sentences describing what is true **right now** about the query.
- Explicitly mention which sources are trusted and why, and include key fields/versions/limits.

5) ACTIONS:
- Numbered list (“1.”, “2.”, …) with “Owner · Action (purpose)” format.
- Order actions: docs/communication first, then code/owners, then comms/follow-up.

6) GAPS:
- Each gap on its own bullet with a short type label:
  - “missing_source: …”
  - “incomplete_data: …”
  - “unclear: …”
- Mention what follow-up would close each gap.

7) INCIDENT SUGGESTION:
- Single line: “yes – <short justification>” or “no – <short justification>”.

IMPORTANT GUARDRAILS:
- Do NOT reuse VAT/version/quota examples unless the query and evidence clearly match.
- Do NOT invent PR numbers, doc names, or channels.
- If no relevant evidence exists, make that explicit in SOURCE EVIDENCE, DRIFT, and CANONICAL CURRENT TRUTH, and set INCIDENT SUGGESTION accordingly.

Your structured summary:"""
        return prompt

    @staticmethod
    def _source_priority_hint() -> Optional[str]:
        mapping = _priority_mapping()
        ordered = [source for source, _ in sorted(mapping.items(), key=lambda item: item[1])]
        return " > ".join(ordered) if ordered else None

    def _signal_weight_hint(self) -> Optional[str]:
        try:
            weights = get_activity_signal_weights(self.config)
        except Exception:
            weights = {}
        activity_hint = ", ".join(f"{key}: {round(value, 2)}" for key, value in (weights or {}).items())
        severity_hint = ", ".join(
            f"{key}: {round(value, 2)}" for key, value in DOC_SEVERITY_WEIGHTS.items()
        )
        parts: List[str] = []
        if activity_hint:
            parts.append(f"activity weights ({activity_hint})")
        if severity_hint:
            parts.append(f"doc severity multipliers ({severity_hint})")
        return " | ".join(parts) if parts else None

    def _evidence_stats_block(self, evidence: EvidenceCollection) -> str:
        if len(evidence) == 0:
            return "\nEVIDENCE SUMMARY:\n- No evidence retrieved for this query.\n"
        counts = Counter(entry.source_type for entry in evidence.evidence_list)
        ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
        lines = ["EVIDENCE SUMMARY:", f"- Total evidence items: {len(evidence)}"]
        for source, count in ordered:
            lines.append(f"- {source}: {count} item(s)")
        return "\n".join(lines)

    @staticmethod
    def _summary_examples() -> str:
        return (
            "\nREFERENCE FORMATS:\n"
            "Example – VAT field requirement drift:\n"
            "SOURCE EVIDENCE:\n"
            "- Slack: 3 messages (latest 0.0h ago) reporting VAT failures when vat_code missing and referencing vat_code=676767.\n"
            "- Git: 1 PR (PR #2041) enforcing vat_code on /v1/payments/create.\n"
            "- Docs / doc issues: payments_api.md + docissue-coreapi-vat still say vat_code optional.\n"
            "- Issues: 1 doc issue (severity high).\n"
            "- Activity graph: 2 components, 5 downstream nodes affected.\n"
            "DRIFT:\n"
            "- Previous state: Docs/payments_api.md promised vat_code optional.\n"
            "- Current behavior: Git + Slack show vat_code now required and teams use vat_code=676767.\n"
            "- Drift type: field requirement drift.\n"
            "CANONICAL CURRENT TRUTH:\n"
            "- Core API currently rejects requests without vat_code; Git + Slack (recent) outweigh stale docs.\n"
            "ACTIONS:\n"
            "1. Docs portal owner – Update payments_api.md to mark vat_code required and document 676767 usage.\n"
            "2. Core API owner – Confirm whether 676767 is configurable and broadcast the requirement in #payments-team.\n"
            "GAPS:\n"
            "- No changelog describing why the requirement changed; no doc describing what 676767 represents.\n"
            "INCIDENT SUGGESTION:\n"
            "- yes – High doc drift + merchant failures.\n"
            "\n(Note: Only use this VAT scenario when the query and evidence explicitly reference VAT or vat_code; otherwise you must base your answer solely on the actual query and evidence.)\n"
            "\nExample – Version drift (/v1 → /v4):\n"
            "SOURCE EVIDENCE:\n"
            "- Slack: 1 message (latest 0.0h ago) announcing /v4/payments/create.\n"
            "- Git: 2 PRs last week moving from /v1 to /v2 (no PR yet for /v4).\n"
            "- Docs / doc issues: integration guide still references /v1; doc issue open for /v1→/v2 drift.\n"
            "- Issues: 0 incidents.\n"
            "- Activity graph: 1 core component, 3 downstream services.\n"
            "DRIFT:\n"
            "- Previous state: Docs + older Git say /v1 (and partially /v2).\n"
            "- Current behavior: Slack guidance says /v4 is live, but code/docs have not caught up.\n"
            "- Drift type: version drift.\n"
            "CANONICAL CURRENT TRUTH:\n"
            "- Slack is the freshest signal, so assume /v4 is current while acknowledging code/docs lag.\n"
            "ACTIONS:\n"
            "1. API owners – Confirm /v4 deployment and update routing/tests.\n"
            "2. Docs owner – Revise integration guide to /v4 and describe migration steps.\n"
            "GAPS:\n"
            "- No Git evidence yet for /v4; need confirmation before docs update.\n"
            "INCIDENT SUGGESTION:\n"
            "- no (yet) – Track as doc drift unless /v4 causes production impact.\n"
            "\nExample – Free tier quota drift:\n"
            "SOURCE EVIDENCE:\n"
            "- Slack: 2 messages (latest 0.5h ago) warn that free tier customers are throttled at 500 requests/day until the new quota system lands.\n"
            "- Git: 0 (queried, no matching evidence found).\n"
            "- Docs / doc issues: rate_limits.md (updated 3d ago) still advertises 1000 requests/day plus 77,777,777 requests per rolling 24h window; pricing.md echoes the legacy copy.\n"
            "- Issues: 0 (queried, no matching evidence found).\n"
            "- Activity graph: 0 (not queried).\n"
            "DRIFT:\n"
            "- Previous state: rate_limits.md + pricing.md promised 1000/day and a 77,777,777 rolling 24h ceiling.\n"
            "- Current behavior: Slack #incidents (Dec 8) states the limit is temporarily 500/day until billing ships the new quota system; no Git confirmation yet.\n"
            "- Drift type: quota drift.\n"
            "CANONICAL CURRENT TRUTH:\n"
            "- Slack (Dec 8) is the freshest signal, so assume 500/day is enforced even though docs still advertise 1000/day + 77,777,777 per rolling 24h.\n"
            "ACTIONS:\n"
            "1. Docs-portal owner – Update rate_limits.md and pricing.md to reflect the temporary 500/day cap while retaining the rolling-window explanation.\n"
            "2. Billing-service lead – Confirm rollout timing for the new quota system and announce in #billing-team.\n"
            "GAPS:\n"
            "- No Git or incident record describing the deployment that reduced the cap; need billing-engineering confirmation to know when docs can revert.\n"
            "- Need comms plan for merchants impacted by the 500/day temporary limit.\n"
            "INCIDENT SUGGESTION:\n"
            "- yes – Doc drift on publicly advertised quota + customer throttling requires coordination.\n"
        )

    def _metadata_block(self, evidence: EvidenceCollection) -> str:
        if len(evidence) == 0:
            return "\nMETADATA YOU MUST USE:\n- None available beyond the query context.\n"

        components: set[str] = set()
        docs: set[str] = set()
        services: set[str] = set()
        drifts: list[str] = []

        for item in evidence.evidence_list:
            metadata = item.metadata or {}
            for comp_id in metadata.get("component_ids") or []:
                if comp_id:
                    components.add(str(comp_id))
            component_id = metadata.get("component_id")
            if component_id:
                components.add(str(component_id))
            for service_id in metadata.get("service_ids") or []:
                if service_id:
                    services.add(str(service_id))
            doc_path = metadata.get("doc_path")
            if doc_path:
                docs.add(str(doc_path))
            entity_id = item.entity_id
            if entity_id and entity_id.startswith("doc:"):
                docs.add(entity_id)
            if item.source_type == "doc_issue":
                doc_id = metadata.get("doc_issue_id") or doc_path or item.source_name
                severity = metadata.get("severity", "unknown")
                components_hint = ", ".join(metadata.get("component_ids") or []) or "n/a"
                drifts.append(
                    f"- {doc_id} (severity={severity}, components={components_hint}): {item.content.splitlines()[0]}"
                )

        lines = ["\nMETADATA YOU MUST USE:"]
        if components:
            lines.append(f"- Components mentioned: {', '.join(sorted(components))}")
        if services:
            lines.append(f"- Services mentioned: {', '.join(sorted(services))}")
        if docs:
            lines.append(f"- Docs referenced: {', '.join(sorted(docs))}")
        if drifts:
            lines.append("- Doc drift candidates:")
            lines.extend(drifts)
        else:
            lines.append("- Doc drift candidates: none captured in evidence.")

        return "\n".join(lines)

    def _detect_drift(self, evidence: EvidenceCollection) -> Dict[str, Any]:
        if len(evidence) == 0:
            return {}

        version_candidates: List[Dict[str, Any]] = []
        requirement_candidates: List[Dict[str, Any]] = []

        for item in evidence.evidence_list:
            text = (item.content or "")
            lowered = text.lower()
            timestamp = item.timestamp
            snippet = text.strip().replace("\n", " ")[:200]

            for match in VERSION_PATTERN.finditer(text):
                token = match.group(0).lower()
                version_candidates.append(
                    self._build_drift_candidate(item, token, snippet, timestamp)
                )

            if OPTIONAL_PATTERN.search(lowered):
                requirement_candidates.append(
                    self._build_drift_candidate(item, "optional", snippet, timestamp)
                )
            if REQUIRED_PATTERN.search(lowered):
                requirement_candidates.append(
                    self._build_drift_candidate(item, "required", snippet, timestamp)
                )

        version_hint = self._build_drift_hint(version_candidates)
        if version_hint:
            return {"drift_kind": "version_drift", **version_hint}

        requirement_hint = self._build_requirement_hint(requirement_candidates)
        if requirement_hint:
            return {"drift_kind": "field_requirement_drift", **requirement_hint}

        return {}

    @staticmethod
    def _build_drift_candidate(
        item: Evidence,
        token: str,
        snippet: str,
        timestamp: Optional[datetime],
    ) -> Dict[str, Any]:
        # Normalize timestamp to a comparable numeric value (UTC epoch seconds)
        ts_value: Optional[float] = None
        if timestamp:
            try:
                if timestamp.tzinfo is None:
                    # Treat naive timestamps as UTC
                    ts_norm = timestamp.replace(tzinfo=timezone.utc)
                else:
                    ts_norm = timestamp.astimezone(timezone.utc)
                ts_value = ts_norm.timestamp()
            except Exception:
                ts_value = None
        return {
            "token": token,
            "source": item.source_type,
            "source_name": item.source_name,
            "entity_id": item.entity_id,
            "timestamp": timestamp.isoformat() if timestamp else None,
            "snippet": snippet,
            "_ts": ts_value,
        }

    @staticmethod
    def _build_drift_hint(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        unique_tokens = {cand.get("token") for cand in candidates if cand.get("token")}
        if len(unique_tokens) < 2:
            return None

        sorted_candidates = sorted(
            candidates,
            key=lambda c: c.get("_ts") if c.get("_ts") is not None else float("-inf"),
        )

        previous_token = sorted_candidates[0].get("token")
        current_token = sorted_candidates[-1].get("token")

        previous_candidates = [
            MultiSourceReasoner._clean_candidate(c)
            for c in sorted_candidates
            if c.get("token") == previous_token
        ][:3]
        current_candidates = [
            MultiSourceReasoner._clean_candidate(c)
            for c in reversed(sorted_candidates)
            if c.get("token") == current_token
        ][:3]

        return {
            "previous_candidates": previous_candidates,
            "current_candidates": current_candidates,
        }

    @staticmethod
    def _build_requirement_hint(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        states = {cand.get("token") for cand in candidates}
        if not {"optional", "required"}.issubset(states):
            return None

        sorted_candidates = sorted(
            candidates,
            key=lambda c: c.get("_ts") if c.get("_ts") is not None else float("-inf"),
        )

        previous_candidates = [
            MultiSourceReasoner._clean_candidate(c)
            for c in sorted_candidates
            if c.get("token") == "optional"
        ][:3]
        current_candidates = [
            MultiSourceReasoner._clean_candidate(c)
            for c in sorted_candidates
            if c.get("token") == "required"
        ][:3]

        return {
            "previous_candidates": previous_candidates,
            "current_candidates": current_candidates,
        }

    @staticmethod
    def _clean_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = dict(candidate)
        cleaned.pop("_ts", None)
        return cleaned

    def _structured_context_block(
        self,
        summary_context: Optional[Dict[str, Any]],
        sources_without_evidence: List[str],
    ) -> str:
        counts = ((summary_context or {}).get("counts_by_source") or {}).copy()
        latest = (summary_context or {}).get("latest_timestamp_by_source") or {}

        def aggregate(keys: List[str]) -> Dict[str, Any]:
            total = sum(counts.get(key, 0) for key in keys)
            latest_candidates = [latest.get(key) for key in keys if latest.get(key)]
            latest_value = None
            if latest_candidates:
                latest_value = max(latest_candidates)
            queried_missing = any(key in sources_without_evidence for key in keys)
            return {
                "count": total,
                "latest": latest_value,
                "queried_missing": queried_missing,
            }

        lines = ["\nSTRUCTURED CONTEXT:"]
        mappings = [
            ("Slack", ["slack"]),
            ("Git", ["git"]),
            ("Docs / doc issues", ["doc", "docs", "doc_issue", "doc_issues"]),
            ("Issues", ["issues"]),
            ("Activity graph", ["activity_graph"]),
        ]

        for label, keys in mappings:
            aggregated = aggregate(keys)
            count = aggregated["count"]
            latest_text = aggregated["latest"] or "none"
            if count == 0 and aggregated["queried_missing"]:
                lines.append(f"- {label}: 0 (queried, no matching evidence found)")
            else:
                lines.append(f"- {label}: {count} item(s) · latest: {latest_text}")

        severity_context = (summary_context or {}).get("severity")
        if severity_context:
            label = severity_context.get("label")
            score = severity_context.get("score_0_10") or severity_context.get("score")
            breakdown = severity_context.get("breakdown")
            lines.append(
                f"- Severity: {label} ({score}/10) breakdown={breakdown}"
            )

        return "\n".join(lines)

    def _drift_hints_block(self, drift_hints: Optional[Dict[str, Any]]) -> str:
        if not drift_hints:
            return ""
        lines = ["\nDRIFT HINTS:"]
        drift_kind = drift_hints.get("drift_kind", "unknown")
        lines.append(f"- drift_kind: {drift_kind}")

        previous = [
            self._format_candidate_summary(candidate)
            for candidate in drift_hints.get("previous_candidates") or []
        ]
        current = [
            self._format_candidate_summary(candidate)
            for candidate in drift_hints.get("current_candidates") or []
        ]
        if previous:
            lines.append(f"- previous_candidates: { '; '.join(previous) }")
        if current:
            lines.append(f"- current_candidates: { '; '.join(current) }")
        return "\n".join(lines)

    @staticmethod
    def _format_candidate_summary(candidate: Dict[str, Any]) -> str:
        token = candidate.get("token")
        source = candidate.get("source")
        timestamp = candidate.get("timestamp") or "unknown time"
        entity = candidate.get("entity_id") or candidate.get("source_name")
        return f"{token} via {source} ({entity}, {timestamp})"

    def _call_llm(self, prompt: str) -> str:
        """
        Call LLM with a prompt.

        Args:
            prompt: Prompt text

        Returns:
            LLM response
        """
        if not self.llm_client:
            # Initialize LLM client if not provided
            try:
                from langchain_openai import ChatOpenAI
                self.llm_client = ChatOpenAI(
                    model=self.config.get("llm", {}).get("model", "gpt-4"),
                    temperature=0.0,
                )
            except Exception as exc:
                logger.error(f"[REASONER] Failed to initialize LLM: {exc}")
                raise

        try:
            response = self.llm_client.invoke(prompt)
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as exc:
            logger.exception(f"[REASONER] LLM call failed: {exc}")
            raise

    def _parse_conflict_response(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse LLM response for conflicts.

        Args:
            response: LLM response text

        Returns:
            List of conflict dictionaries
        """
        if "NO_CONFLICTS" in response:
            return []

        conflicts = []
        current_conflict = {}

        for line in response.strip().split("\n"):
            line = line.strip()

            if line.startswith("CONFLICT:"):
                if current_conflict:
                    conflicts.append(current_conflict)
                current_conflict = {}

            elif line.startswith("- Source 1:"):
                current_conflict["source1"] = line.replace("- Source 1:", "").strip()

            elif line.startswith("- Source 2:"):
                current_conflict["source2"] = line.replace("- Source 2:", "").strip()

            elif line.startswith("- Description:"):
                current_conflict["description"] = line.replace("- Description:", "").strip()

        # Add last conflict
        if current_conflict:
            conflicts.append(current_conflict)

        return conflicts

    def _parse_gap_response(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse LLM response for gaps.

        Args:
            response: LLM response text

        Returns:
            List of gap dictionaries
        """
        if "NO_GAPS" in response:
            return []

        gaps = []
        current_gap = {}

        for line in response.strip().split("\n"):
            line = line.strip()

            if line.startswith("GAP:"):
                if current_gap:
                    gaps.append(current_gap)
                current_gap = {}

            elif line.startswith("- Type:"):
                current_gap["type"] = line.replace("- Type:", "").strip()

            elif line.startswith("- Description:"):
                current_gap["description"] = line.replace("- Description:", "").strip()

        # Add last gap
        if current_gap:
            gaps.append(current_gap)

        return gaps
