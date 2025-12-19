from __future__ import annotations

import concurrent.futures
import logging
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from telemetry.config import log_structured

from ..graph.service import GraphService
from ..search import SearchRegistry
from ..search.query_planner import plan_modalities
from ..search.query_trace import ChunkRef, QueryTrace, QueryTraceStore
from ..services.slash_query_plan import SlashQueryIntent
from ..utils import load_config

if TYPE_CHECKING:
    from ..services.slash_query_plan import SlashQueryPlan

logger = logging.getLogger(__name__)


class CerebrosCommand:
    """
    Universal semantic search orchestrator for /cerebros.
    """

    def __init__(
        self,
        registry: SearchRegistry,
        *,
        trace_store: Optional[QueryTraceStore] = None,
        graph_service: Optional[GraphService] = None,
    ):
        self.registry = registry
        self.trace_store = trace_store or QueryTraceStore()
        self.graph_service = graph_service
        if self.graph_service is None:
            try:
                self.graph_service = GraphService(load_config())
            except Exception:
                self.graph_service = None

    def search(
        self,
        query: str,
        *,
        plan: Optional["SlashQueryPlan"] = None,
    ) -> Dict[str, Any]:
        query = (query or "").strip()
        if not query:
            return {"status": "error", "message": "Ask a question after /cerebros."}
        if not self.registry.config.enabled:
            return {
                "status": "error",
                "message": "Universal search disabled. Enable `search.enabled` in config.yaml.",
            }

        query_id = str(uuid.uuid4())
        plan_dict = plan.to_dict() if plan else None

        effective_query = self._augment_query_with_plan(query, plan)
        primary_results, primary_modalities = self._run_queries(
            effective_query,
            include_fallback=False,
            plan=plan,
        )
        modalities_used = list(primary_modalities)
        if not primary_results:
            fallback_results, fallback_modalities = self._run_queries(
                effective_query,
                include_fallback=True,
                plan=plan,
            )
            modalities_used = _dedupe_preserve_order(modalities_used, fallback_modalities)
            log_structured(
                "info",
                "/cerebros fallback engaged",
                query=query,
                fallback_modalities=fallback_modalities,
            )
        else:
            fallback_results = []

        aggregated = sorted(primary_results + fallback_results, key=lambda item: item["score"], reverse=True)
        modalities_used = _dedupe_preserve_order([], modalities_used)
        message = _format_summary(query, aggregated)
        self._record_trace(
            query_id=query_id,
            question=query,
            modalities_used=modalities_used,
            aggregated_results=aggregated,
        )

        data = {
            "status": "success",
                "results": aggregated[:10],
                "total": len(aggregated),
                "query_id": query_id,
                "modalities_used": modalities_used,
                "brain_trace_url": f"/brain/trace/{query_id}",
                "brain_universe_url": "/brain/universe",
        }
        if plan_dict:
            data["query_plan"] = plan_dict
        graph_context = self._build_graph_context(plan)
        if graph_context:
            data["graph_context"] = graph_context

        return {
            "status": "success",
            "message": message,
            "data": data,
        }
        log_structured(
            "info",
            "/cerebros completed",
            query=query,
            query_id=query_id,
            modalities_used=modalities_used,
            total_results=len(aggregated),
        )

    # ------------------------------------------------------------------ #
    def _run_queries(
        self,
        query: str,
        *,
        include_fallback: bool,
        plan: Optional["SlashQueryPlan"],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        planned_modalities = plan_modalities(query, self.registry.config, include_fallback=include_fallback)
        if not planned_modalities:
            return [], []
        hints = self._modality_hints_from_plan(plan)
        if hints:
            filtered = [modality for modality in planned_modalities if modality in hints]
            if filtered:
                planned_modalities = filtered
        logger.info(
            "[SEARCH][CEREBROS] Planner selected modalities",
            extra={"modality_ids": planned_modalities, "include_fallback": include_fallback},
        )
        log_structured(
            "info",
            "/cerebros planner decision",
            query=query,
            planned_modalities=planned_modalities,
            include_fallback=include_fallback,
        )
        handlers = list(
            self.registry.iter_query_handlers(
                include_fallback=include_fallback,
                modalities=planned_modalities,
            )
        )
        if not handlers:
            return [], []

        results: List[Dict[str, Any]] = []
        executed_modalities: List[str] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(handlers)) as executor:
            future_map: Dict[concurrent.futures.Future, Tuple[str, int]] = {}
            for handler, config, _state in handlers:
                timeout_sec = max(1.0, config.timeout_ms / 1000.0)
                future = executor.submit(handler.query, query, limit=config.max_results)
                future_map[future] = (config.modality_id, timeout_sec)
                executed_modalities.append(config.modality_id)

            for future, (modality_id, timeout_sec) in future_map.items():
                try:
                    results.extend(future.result(timeout=timeout_sec))
                except concurrent.futures.TimeoutError:
                    logger.warning("[SEARCH][CEREBROS] %s query timed out after %ss", modality_id, timeout_sec)
                except Exception:
                    logger.exception("[SEARCH][CEREBROS] %s query failed", modality_id)

        return results, executed_modalities

    def _record_trace(
        self,
        *,
        query_id: str,
        question: str,
        modalities_used: List[str],
        aggregated_results: List[Dict[str, Any]],
    ) -> None:
        if not self.trace_store:
            return
        retrieved = [_result_to_chunk_ref(entry) for entry in aggregated_results]
        chosen = retrieved[:3]
        trace = QueryTrace(
            query_id=query_id,
            question=question,
            modalities_used=modalities_used,
            retrieved_chunks=retrieved,
            chosen_chunks=chosen,
        )
        try:
            self.trace_store.append(trace)
        except Exception:
            logger.warning("[SEARCH][TRACE] Failed to persist query trace %s", query_id, exc_info=True)

    def _augment_query_with_plan(self, query: str, plan: Optional["SlashQueryPlan"]) -> str:
        if not plan:
            return query
        tokens: List[str] = []
        if query:
            tokens.append(query)
        for target in plan.targets:
            label = target.label or target.identifier or target.raw
            if label:
                tokens.append(label)
        tokens.extend(plan.keywords)
        tokens.extend(plan.required_outputs)
        deduped: List[str] = []
        seen: set[str] = set()
        for token in tokens:
            normalized = (token or "").strip()
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(normalized)
        return " ".join(deduped) if deduped else query

    def _modality_hints_from_plan(self, plan: Optional["SlashQueryPlan"]) -> List[str]:
        if not plan:
            return []
        hints: set[str] = set()
        for target in plan.targets:
            ttype = (target.target_type or "").lower()
            if ttype in {"slack_channel", "incident"}:
                hints.add("slack")
            if ttype in {"component", "service", "repository", "incident"}:
                hints.add("git")
            if ttype in {"doc", "doc_issue"}:
                hints.add("docs")
        if plan.intent in {SlashQueryIntent.COMPARE, SlashQueryIntent.INVESTIGATE}:
            hints.update({"slack", "git"})
        return list(hints)

    def _build_graph_context(self, plan: Optional["SlashQueryPlan"]) -> Optional[Dict[str, Any]]:
        if not plan or not plan.targets:
            return None
        if not self.graph_service or not self.graph_service.is_available():
            return None
        component_summaries: List[Dict[str, Any]] = []
        highlight_nodes: set[str] = set()
        for target in plan.targets:
            if (target.target_type or "").lower() == "component" and target.identifier:
                summary = self.graph_service.get_component_neighborhood(target.identifier)
                if not summary:
                    continue
                component_summaries.append(
                    {
                        "component_id": summary.component_id,
                        "docs": summary.docs,
                        "issues": summary.issues,
                        "pull_requests": summary.pull_requests,
                        "slack_threads": summary.slack_threads,
                        "api_endpoints": summary.api_endpoints,
                    }
                )
                highlight_nodes.add(f"component:{summary.component_id}")
                for doc_id in summary.docs:
                    highlight_nodes.add(f"doc:{doc_id}")
                for issue_id in summary.issues:
                    highlight_nodes.add(f"issue:{issue_id}")
                for pr_id in summary.pull_requests:
                    highlight_nodes.add(f"pr:{pr_id}")
                for thread_id in summary.slack_threads:
                    highlight_nodes.add(f"slack_thread:{thread_id}")
        if not component_summaries and not highlight_nodes:
            return None
        return {
            "components": component_summaries,
            "highlight_node_ids": sorted(highlight_nodes),
        }


def _format_summary(query: str, results: List[Dict[str, Any]]) -> str:
    if not results:
        return f'No indexed sources had relevant matches for "{query}". Try re-indexing or enabling more modalities.'

    lines = [f'Top matches for "{query}":']
    for item in results[:5]:
        modality = item.get("modality") or item.get("source_type")
        title = item.get("title") or "result"
        score = float(item.get("score", 0.0))
        url = item.get("url")
        snippet = item.get("text") or ""
        line = f"- [{modality}] {title} (score={score:.2f})"
        if url:
            line += f" — {url}"
        lines.append(line)
        if snippet:
            lines.append(f"    {snippet[:200]}")
    return "\n".join(lines)


def _result_to_chunk_ref(result: Dict[str, Any]) -> ChunkRef:
    metadata = result.get("metadata") or {}
    score = result.get("score")
    try:
        score_val = float(score) if score is not None else None
    except (TypeError, ValueError):
        score_val = None

    return ChunkRef(
        chunk_id=result.get("chunk_id") or metadata.get("chunk_id"),
        source_type=result.get("source_type") or metadata.get("source_type"),
        source_id=result.get("entity_id") or metadata.get("source_id") or metadata.get("entity_id"),
        modality=result.get("modality"),
        title=result.get("title"),
        score=score_val,
        url=result.get("url"),
        metadata=metadata,
    )


def _dedupe_preserve_order(existing: List[str], new_values: List[str]) -> List[str]:
    seen = set(existing)
    ordered = list(existing)
    for value in new_values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
