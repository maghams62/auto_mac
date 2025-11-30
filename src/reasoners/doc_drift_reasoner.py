from __future__ import annotations

import json
import logging
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..demo.graph_summary import GraphNeighborhoodSummarizer, GraphSummary
from ..demo.scenario_classifier import DemoScenario, classify_question
from ..demo.vector_retriever import VectorRetriever, VectorRetrievalBundle, VectorSnippet
from ..utils import parse_json_with_retry
from ..utils.openai_client import PooledOpenAIClient

logger = logging.getLogger(__name__)

MAX_SNIPPET_CHARS = 480
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROMPT_PATH = REPO_ROOT / "prompts" / "doc_drift" / "doc_drift_reasoner.md"


@dataclass
class DocDriftAnswer:
    """Structured result returned by the doc drift reasoner."""

    question: str
    scenario: DemoScenario
    summary: str
    sections: Dict[str, Any]
    impacted: Dict[str, List[str]]
    evidence: List[Dict[str, Any]]
    graph_summary: GraphSummary
    vector_bundle: VectorRetrievalBundle
    structured_sections: List[Dict[str, Any]] = field(default_factory=list)
    impacted_entities: List[Dict[str, Any]] = field(default_factory=list)
    doc_drift: List[Dict[str, Any]] = field(default_factory=list)
    doc_drift_facts: List[Dict[str, Any]] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    reasoner_evidence: List[Dict[str, Any]] = field(default_factory=list)
    raw_response: Optional[str] = None
    prompt: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    debug_metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.error is None


class DocDriftReasoner:
    """
    Shared reasoning service that fuses vector retrieval + graph summaries + a single LLM call.

    Used by slash /slack and /git flows so they can surface grounded doc-drift narratives
    without duplicating the demo harness logic.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        *,
        vector_retriever: Optional[VectorRetriever] = None,
        graph_summarizer: Optional[GraphNeighborhoodSummarizer] = None,
        llm_client: Optional[Any] = None,
    ):
        self.config = config
        self.vector_retriever = vector_retriever or VectorRetriever(config)
        self.graph_summarizer = graph_summarizer or GraphNeighborhoodSummarizer(config)
        self.llm_client = llm_client
        self.model = (config.get("openai") or {}).get("model", "gpt-4o")
        self.temperature = (config.get("openai") or {}).get("temperature", 0.2)
        self.prompt_template_path, self.prompt_template = self._load_prompt_template()

    # ------------------------------------------------------------------
    def answer_question(self, question: str, *, source: str = "slack") -> DocDriftAnswer:
        """Main entrypoint – builds context, calls the LLM, and returns structured answer."""
        normalized_question = (question or "").strip()
        if not normalized_question:
            return DocDriftAnswer(
                question="",
                scenario=classify_question(""),
                summary="Provide a Slack or Git drift question so I know what to diagnose.",
                sections=self._default_sections("Provide a Slack or Git drift question so I know what to diagnose."),
                impacted=self._default_impacted(classify_question(""), GraphSummary(api=""), []),
                evidence=[],
                graph_summary=GraphSummary(api=""),
                vector_bundle=VectorRetrievalBundle(),
                error="Question is required.",
            )

        scenario = classify_question(normalized_question)
        vector_bundle = self.vector_retriever.fetch_context(scenario, question=normalized_question)
        graph_summary = self.graph_summarizer.summarize(scenario)
        evidence_entries = self._build_evidence_entries(vector_bundle)

        if not evidence_entries and not self._has_graph_context(graph_summary):
            summary = (
                f"No indexed Slack, Git, or doc evidence was found for {scenario.api}. "
                "Re-run the ingesters or widen the timeframe."
            )
            return DocDriftAnswer(
                question=normalized_question,
                scenario=scenario,
                summary=summary,
                sections=self._default_sections(summary),
                impacted=self._default_impacted(scenario, graph_summary, evidence_entries),
                evidence=evidence_entries,
                graph_summary=graph_summary,
                vector_bundle=vector_bundle,
                next_steps=["Rebuild the vector indexes", "Re-run the Neo4j ingester"],
                metadata={"source": source, "scenario": scenario.name},
            )

        prompt = self._build_prompt(
            question=normalized_question,
            scenario=scenario,
            graph_summary=graph_summary,
            evidence=evidence_entries,
            source=source,
        )

        parsed, raw_response, error = self._call_llm(prompt)
        summary, sections, structured_sections, next_steps = self._extract_sections(parsed, evidence_entries)
        impacted, impacted_entities = self._extract_impacted(parsed, scenario, graph_summary, evidence_entries)
        doc_drift, doc_drift_facts = self._build_doc_drift_entries(parsed, impacted, graph_summary)
        reasoner_evidence = parsed.get("evidence") if parsed and isinstance(parsed.get("evidence"), list) else []
        debug_metadata = parsed.get("debug_metadata") if parsed else {}
        warnings = parsed.get("warnings") if parsed and isinstance(parsed.get("warnings"), list) else []

        metadata = {
            "source": source,
            "scenario": scenario.name,
            "api": scenario.api,
        }
        if self.prompt_template_path:
            metadata["prompt_template"] = str(self.prompt_template_path)
        if parsed and parsed.get("scenario_id"):
            metadata["scenario_hint"] = parsed.get("scenario_id")
        if warnings:
            metadata["warnings"] = warnings

        return DocDriftAnswer(
            question=normalized_question,
            scenario=scenario,
            summary=summary,
            sections=sections,
            structured_sections=structured_sections,
            impacted=impacted,
            impacted_entities=impacted_entities,
            evidence=evidence_entries,
            graph_summary=graph_summary,
            vector_bundle=vector_bundle,
            doc_drift=doc_drift,
            doc_drift_facts=doc_drift_facts,
            next_steps=next_steps,
            reasoner_evidence=reasoner_evidence,
            raw_response=raw_response,
            prompt=prompt,
            error=error,
            metadata=metadata,
            debug_metadata=debug_metadata or {},
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    def _call_llm(self, prompt: str) -> Tuple[Optional[Dict[str, Any]], str, Optional[str]]:
        """Invoke OpenAI and parse JSON response."""
        if self.llm_client is None:
            try:
                self.llm_client = PooledOpenAIClient.get_client(self.config)
            except Exception as exc:  # pragma: no cover - network failure
                logger.warning("[DOC DRIFT] Unable to initialize OpenAI client: %s", exc)
                return None, "", str(exc)

        try:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are Oqoqo's doc-drift analyst. "
                            "Respond with concise JSON only, no markdown."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            raw = (response.choices[0].message.content or "").strip()
        except Exception as exc:  # pragma: no cover - network failure
            logger.warning("[DOC DRIFT] LLM invocation failed: %s", exc)
            return None, "", str(exc)

        if not raw:
            return None, "", "Empty response from LLM."

        parsed, parse_error = parse_json_with_retry(raw)
        if parsed:
            return parsed, raw, None
        logger.warning("[DOC DRIFT] Failed to parse LLM JSON: %s", parse_error)
        return None, raw, parse_error or "Failed to parse LLM output."

    # ------------------------------------------------------------------
    def _build_prompt(
        self,
        *,
        question: str,
        scenario: DemoScenario,
        graph_summary: GraphSummary,
        evidence: List[Dict[str, Any]],
        source: str,
    ) -> str:
        if self.prompt_template:
            try:
                return self._render_prompt_template(
                    template=self.prompt_template,
                    question=question,
                    scenario=scenario,
                    graph_summary=graph_summary,
                    evidence=evidence,
                    source=source,
                )
            except Exception as exc:
                logger.warning("[DOC DRIFT] Prompt template render failed, falling back: %s", exc)

        return self._build_fallback_prompt(
            question=question,
            scenario=scenario,
            graph_summary=graph_summary,
            evidence=evidence,
            source=source,
        )

    def _build_fallback_prompt(
        self,
        *,
        question: str,
        scenario: DemoScenario,
        graph_summary: GraphSummary,
        evidence: List[Dict[str, Any]],
        source: str,
    ) -> str:
        graph_lines = self._graph_summary_lines(graph_summary)
        evidence_block = json.dumps(evidence, indent=2, ensure_ascii=False)
        schema_block = textwrap.dedent(
            """
            Return JSON with the following keys:
            {
              "summary": "2-3 sentence overview",
              "sections": {
                "topics": [{"title": "", "insight": "", "evidence_ids": []}],
                "decisions": [{"text": "", "participants": [], "timestamp": "", "evidence_ids": []}],
                "tasks": [{"description": "", "assignees": [], "due": "", "evidence_ids": []}],
                "open_questions": [{"text": "", "owner": "", "evidence_ids": []}],
                "references": [{"title": "", "url": "", "kind": "slack|github|doc", "evidence_ids": []}]
              },
              "impacted": {
                "apis": [],
                "services": [],
                "components": [],
                "docs": []
              },
              "next_steps": ["..."],
              "doc_drift": [
                {
                  "doc": "",
                  "issue": "",
                  "services": [],
                  "components": [],
                  "apis": [],
                  "labels": ["doc_drift"],
                  "evidence_ids": []
                }
              ]
            }
            """
        ).strip()

        prompt = textwrap.dedent(
            f"""
            You are diagnosing doc drift across Slack and Git telemetry for the Oqoqo stack.
            Source command: /{source}
            Scenario: {scenario.description} (API {scenario.api})

            ## User Question
            {question}

            ## Graph Summary
            {chr(10).join(graph_lines)}

            ## Evidence (each entry has `id` to cite in evidence_ids)
            {evidence_block}

            ## Instructions
            - Use only the evidence provided (no fabrication).
            - Cite evidence via evidence_ids arrays so downstream graph loaders can follow links.
            - Highlight mismatches between code, docs, and Slack complaints.
            - Emphasize what changed, why it matters, and which docs/services must update.
            - {schema_block}
            - Output valid JSON only.
            """
        ).strip()
        return prompt

    def _render_prompt_template(
        self,
        *,
        template: str,
        question: str,
        scenario: DemoScenario,
        graph_summary: GraphSummary,
        evidence: List[Dict[str, Any]],
        source: str,
    ) -> str:
        graph_lines = self._graph_summary_lines(graph_summary)
        evidence_block = json.dumps(evidence, indent=2, ensure_ascii=False) if evidence else "[]"
        replacements = {
            "SOURCE_COMMAND": f"/{source}",
            "SCENARIO_NAME": scenario.name,
            "SCENARIO_API": scenario.api,
            "SCENARIO_DESCRIPTION": scenario.description,
            "USER_QUESTION": question,
            "GRAPH_NEIGHBORHOOD": "\n".join(graph_lines),
            "EVIDENCE_JSON": evidence_block,
        }
        rendered = template
        for key, value in replacements.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", value)
        return rendered

    def _graph_summary_lines(self, graph_summary: GraphSummary) -> List[str]:
        return [
            f"- API: {graph_summary.api or 'n/a'}",
            f"- Services: {', '.join(graph_summary.services) or 'n/a'}",
            f"- Components: {', '.join(graph_summary.components) or 'n/a'}",
            f"- Docs: {', '.join(graph_summary.docs) or 'n/a'}",
            f"- Recent Git Events: {', '.join(graph_summary.git_events) or 'n/a'}",
            f"- Recent Slack Events: {', '.join(graph_summary.slack_events) or 'n/a'}",
        ]

    def _load_prompt_template(self) -> Tuple[Optional[Path], Optional[str]]:
        prompt_cfg = self.config.get("doc_drift_reasoner") or {}
        override_path = prompt_cfg.get("prompt_path")
        candidates: List[Path] = []
        if override_path:
            custom_path = Path(override_path).expanduser()
            if not custom_path.is_absolute():
                custom_path = (REPO_ROOT / custom_path).resolve()
            candidates.append(custom_path)
        candidates.append(DEFAULT_PROMPT_PATH)

        for candidate in candidates:
            try:
                if candidate.exists():
                    try:
                        content = candidate.read_text()
                        logger.info("[DOC DRIFT] Loaded prompt template from %s", candidate)
                        return candidate, content
                    except Exception as exc:
                        logger.warning("[DOC DRIFT] Failed to read prompt template %s: %s", candidate, exc)
            except Exception as exc:
                logger.warning("[DOC DRIFT] Error evaluating prompt template path %s: %s", candidate, exc)

        logger.warning("[DOC DRIFT] Prompt template not found; falling back to inline builder.")
        return None, None

    # ------------------------------------------------------------------
    def _extract_sections(
        self,
        parsed: Optional[Dict[str, Any]],
        evidence_entries: List[Dict[str, Any]],
    ) -> Tuple[str, Dict[str, Any], List[Dict[str, Any]], List[str]]:
        if not parsed:
            fallback = "Doc drift summary unavailable."
            return fallback, self._default_sections(fallback), [], []

        summary = parsed.get("summary") or "Doc drift summary unavailable."
        structured_sections = parsed.get("sections") or []
        sections = self._structured_sections_to_legacy(structured_sections, summary)
        next_steps = parsed.get("next_steps") or []

        # Ensure references include basic metadata even if missing
        references = sections.get("references") or []
        if not references:
            references = [
                {
                    "title": ev.get("id"),
                    "url": ev.get("permalink"),
                    "kind": ev.get("source"),
                    "evidence_ids": [ev.get("id")],
                }
                for ev in evidence_entries
                if ev.get("permalink")
            ][:5]
            if references:
                sections["references"] = references
        return summary, sections, structured_sections, next_steps

    def _structured_sections_to_legacy(
        self,
        structured_sections: List[Dict[str, Any]],
        summary: str,
    ) -> Dict[str, Any]:
        if not structured_sections:
            return self._default_sections(summary)

        topics = []
        for section in structured_sections:
            topics.append(
                {
                    "title": section.get("title") or "Doc drift insight",
                    "insight": section.get("body") or "",
                    "importance": section.get("importance"),
                    "evidence_ids": section.get("evidence_ids") or [],
                }
            )

        return {
            "topics": topics,
            "decisions": [],
            "tasks": [],
            "open_questions": [],
            "references": [],
        }

    def _extract_impacted(
        self,
        parsed: Optional[Dict[str, Any]],
        scenario: DemoScenario,
        graph_summary: GraphSummary,
        evidence: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, List[str]], List[Dict[str, Any]]]:
        impacted_entities: List[Dict[str, Any]] = []
        if parsed:
            impacted_entities = parsed.get("impacted_entities") or []
            if parsed.get("impacted"):
                legacy = parsed["impacted"]
                impacted = {
                    "apis": sorted(set(legacy.get("apis") or [scenario.api])),
                    "services": sorted(
                        set(legacy.get("services") or graph_summary.services or scenario.services)
                    ),
                    "components": sorted(
                        set(legacy.get("components") or graph_summary.components or scenario.components)
                    ),
                    "docs": sorted(set(legacy.get("docs") or graph_summary.docs or scenario.docs)),
                }
                if impacted_entities:
                    merged = self._aggregate_impacted_from_entities(
                        impacted_entities, scenario, graph_summary, evidence
                    )
                    impacted = self._merge_impacted_dicts(impacted, merged)
                return impacted, impacted_entities

        if impacted_entities:
            aggregated = self._aggregate_impacted_from_entities(
                impacted_entities, scenario, graph_summary, evidence
            )
            return aggregated, impacted_entities

        return self._default_impacted(scenario, graph_summary, evidence), impacted_entities

    def _aggregate_impacted_from_entities(
        self,
        impacted_entities: List[Dict[str, Any]],
        scenario: DemoScenario,
        graph_summary: GraphSummary,
        evidence: List[Dict[str, Any]],
    ) -> Dict[str, List[str]]:
        base = self._default_impacted(scenario, graph_summary, evidence)
        apis: set[str] = set(base.get("apis", []))
        services = set(base.get("services", []))
        components = set(base.get("components", []))
        docs = set(base.get("docs", []))

        for entity in impacted_entities:
            entity_type = (entity.get("type") or "").lower()
            name = entity.get("name") or entity.get("id")
            if not name:
                continue
            if entity_type == "api":
                apis.add(name)
            elif entity_type == "service":
                services.add(name)
            elif entity_type == "component":
                components.add(name)
            elif entity_type == "doc":
                docs.add(name)

        return {
            "apis": sorted(filter(None, apis)),
            "services": sorted(filter(None, services)),
            "components": sorted(filter(None, components)),
            "docs": sorted(filter(None, docs)),
        }

    def _merge_impacted_dicts(
        self,
        base: Dict[str, List[str]],
        additional: Dict[str, List[str]],
    ) -> Dict[str, List[str]]:
        merged: Dict[str, List[str]] = {}
        for key in {"apis", "services", "components", "docs"}:
            merged[key] = sorted(set(base.get(key, []) + additional.get(key, [])))
        return merged

    def _default_sections(self, summary: str) -> Dict[str, Any]:
        return {
            "topics": [{"title": "Doc drift overview", "insight": summary, "evidence_ids": []}],
            "decisions": [],
            "tasks": [],
            "open_questions": [],
            "references": [],
        }

    def _default_impacted(
        self,
        scenario: DemoScenario,
        graph_summary: GraphSummary,
        evidence: List[Dict[str, Any]],
    ) -> Dict[str, List[str]]:
        services = set(scenario.services or []) | set(graph_summary.services or [])
        components = set(scenario.components or []) | set(graph_summary.components or [])
        docs = set(scenario.docs or []) | set(graph_summary.docs or [])
        apis: set[str] = {scenario.api}
        if graph_summary.api:
            if isinstance(graph_summary.api, (list, tuple, set)):
                apis.update(graph_summary.api)  # type: ignore[arg-type]
            else:
                apis.add(graph_summary.api)

        for entry in evidence:
            services.update(entry.get("services") or [])
            components.update(entry.get("components") or [])
            docs.update(entry.get("docs") or [])
            apis.update(entry.get("apis") or [])

        return {
            "apis": sorted(filter(None, apis)),
            "services": sorted(filter(None, services)),
            "components": sorted(filter(None, components)),
            "docs": sorted(filter(None, docs)),
        }

    def _build_doc_drift_entries(
        self,
        parsed: Optional[Dict[str, Any]],
        impacted: Dict[str, List[str]],
        graph_summary: GraphSummary,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        doc_drift_facts: List[Dict[str, Any]] = []
        if parsed:
            doc_drift_facts = parsed.get("doc_drift_facts") or parsed.get("doc_drift") or []

        if doc_drift_facts:
            entries: List[Dict[str, Any]] = []
            for fact in doc_drift_facts:
                doc_name = fact.get("doc") or fact.get("name") or fact.get("id") or ""
                issue_text = fact.get("description") or fact.get("issue") or ""
                entries.append(
                    {
                        "doc": doc_name,
                        "issue": issue_text,
                        "services": fact.get("services") or impacted.get("services") or [],
                        "components": fact.get("components") or impacted.get("components") or [],
                        "apis": fact.get("apis") or impacted.get("apis") or [graph_summary.api],
                        "labels": fact.get("labels") or ["doc_drift"],
                        "evidence_ids": fact.get("evidence_ids") or [],
                    }
                )
            return entries, doc_drift_facts

        docs = impacted.get("docs") or graph_summary.docs or []
        if not docs:
            return [], doc_drift_facts

        fallback = [
            {
                "doc": doc,
                "issue": f"Potential drift vs {', '.join(impacted.get('apis') or []) or graph_summary.api}",
                "services": impacted.get("services") or [],
                "components": impacted.get("components") or [],
                "apis": impacted.get("apis") or [graph_summary.api],
                "labels": ["doc_drift"],
                "evidence_ids": [],
            }
            for doc in docs
        ]
        return fallback, doc_drift_facts

    # ------------------------------------------------------------------
    def _build_evidence_entries(self, bundle: VectorRetrievalBundle) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []

        def _ingest(snippets: List[VectorSnippet], label: str) -> None:
            for idx, snippet in enumerate(snippets, 1):
                metadata = snippet.metadata or {}
                entry_id = metadata.get("event_id") or f"{label.lower()}-{idx}"
                entries.append(
                    {
                        "id": entry_id,
                        "source": label.lower(),
                        "score": round(float(snippet.score or 0.0), 4),
                        "text": self._truncate(snippet.text),
                        "permalink": metadata.get("permalink") or metadata.get("url"),
                        "channel": metadata.get("channel_name") or metadata.get("channel_id"),
                        "ts": metadata.get("timestamp") or metadata.get("ts"),
                        "services": metadata.get("service_ids") or [],
                        "components": metadata.get("component_ids") or [],
                        "apis": metadata.get("apis") or metadata.get("related_apis") or [],
                        "labels": metadata.get("labels") or [],
                        "docs": [metadata.get("doc_path")] if metadata.get("doc_path") else [],
                    }
                )

        _ingest(bundle.slack, "Slack")
        _ingest(bundle.git, "Git")
        _ingest(bundle.docs, "Doc")
        return entries

    def _truncate(self, text: str) -> str:
        if not text:
            return ""
        stripped = text.strip().replace("\n", " ")
        if len(stripped) <= MAX_SNIPPET_CHARS:
            return stripped
        return stripped[: MAX_SNIPPET_CHARS - 3] + "..."

    @staticmethod
    def _has_graph_context(summary: GraphSummary) -> bool:
        return any(
            [
                summary.services,
                summary.components,
                summary.docs,
                summary.git_events,
                summary.slack_events,
            ]
        )


