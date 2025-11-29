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
from typing import Any, Dict, List, Optional

from .evidence import Evidence, EvidenceCollection, SOURCE_PRIORITY
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
    "activity_graph": [
        "activity", "dissatisfaction", "hotspot", "priority",
        "component status", "component activity", "which component", "needs docs",
        "comp:",
    ],
}


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

        # Initialize retrievers
        self.retrievers = {}
        for source_type in ["git", "slack", "docs", "issues", "activity_graph"]:
            retriever = get_retriever(source_type, config)
            if retriever:
                self.retrievers[source_type] = retriever

        logger.info(f"[REASONER] Initialized with {len(self.retrievers)} retrievers")

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

        # Step 3: Analyze evidence for conflicts and gaps
        conflicts = self._detect_conflicts(all_evidence)
        gaps = self._detect_gaps(all_evidence, query)

        # Step 4: Generate summary
        summary = self._generate_summary(all_evidence, conflicts, gaps)

        return {
            "query": query,
            "sources_queried": sources,
            "evidence_count": len(all_evidence),
            "evidence": all_evidence.to_dict(),
            "conflicts": conflicts,
            "gaps": gaps,
            "summary": summary,
        }

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
            relevant_sources = {"git", "slack"}

        # Sort by priority
        return sorted(relevant_sources, key=lambda s: SOURCE_PRIORITY.get(s, 99))

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
        gaps: List[Dict[str, Any]]
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
        prompt = self._build_summary_prompt(evidence, conflicts, gaps)

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
        gaps: List[Dict[str, Any]]
    ) -> str:
        """Build LLM prompt for summary generation."""
        conflicts_section = ""
        if conflicts:
            conflicts_section = "\n\nCONFLICTS DETECTED:\n" + "\n".join(
                f"- {c.get('description', 'Unknown conflict')}" for c in conflicts
            )

        gaps_section = ""
        if gaps:
            gaps_section = "\n\nINFORMATION GAPS:\n" + "\n".join(
                f"- {g.get('description', 'Unknown gap')}" for g in gaps
            )

        prompt = f"""You are analyzing evidence from multiple sources to answer a query.

QUERY: {evidence.query}

{evidence.format_for_llm()}
{conflicts_section}
{gaps_section}

TASK: Generate a comprehensive summary that:
1. Directly answers the query based on the evidence
2. Attributes information to specific sources (use source names)
3. Notes any conflicts between sources (prioritize by source priority: git > docs > issues > slack)
4. Mentions information gaps where relevant
5. Is concise but complete

Your summary:"""
        return prompt

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
