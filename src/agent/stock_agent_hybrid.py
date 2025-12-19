"""
Hybrid Stock Agent - blends first-party market data with targeted DuckDuckGo lookups.

The agent exposes a single high-level tool that:
1. Normalizes user-specified periods into yfinance-supported windows (Lane 1).
2. Falls back to DuckDuckGo search when structured history is incomplete (Lane 2).
3. Surfaces a meta-level reflection when uncertainty remains (Lane 3).

Each response includes:
- normalized_period & normalization_note (if the original request was adjusted)
- confidence_level (high/medium/low)
- reasoning_channels (diverse lanes the LLM can reference)
- search metadata (query, reason, results) when DuckDuckGo is used
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from .stock_agent import (  # Reuse structured helpers & first-party data tools
    _normalize_history_period,
    _fallback_stock_history_via_search,
    get_stock_price as _core_get_stock_price,
    get_stock_history as _core_get_stock_history,
    search_stock_symbol as _core_search_stock_symbol,
)

logger = logging.getLogger(__name__)


def _invoke_tool(tool_obj, params: Dict[str, Any]) -> Dict[str, Any]:
    """Call LangChain tool objects safely whether they expose invoke() or are plain functions."""
    try:
        if hasattr(tool_obj, "invoke"):
            return tool_obj.invoke(params)
        return tool_obj(**params)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.error("Tool invocation failed: %s", exc)
        return {
            "error": True,
            "error_type": "ToolInvocationError",
            "error_message": str(exc),
            "retry_possible": False,
        }


def _build_reasoning_lane(
    lane: str,
    confidence: str,
    summary: str,
    justification: str,
    search_query: Optional[str] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Structure reasoning metadata for downstream LLM steps."""
    payload: Dict[str, Any] = {
        "lane": lane,
        "confidence": confidence,
        "summary": summary,
        "justification": justification,
    }
    if search_query:
        payload["search_query"] = search_query
    if sources:
        payload["sources"] = sources
    return payload


def _should_trigger_search(history_result: Dict[str, Any]) -> bool:
    """Decide whether DuckDuckGo should be used based on the primary history payload."""
    if not history_result:
        return True
    if history_result.get("error"):
        return True
    if history_result.get("fallback_used"):
        return True
    if not history_result.get("data_points"):
        return True
    return False


def _calculate_confidence(
    price_result: Dict[str, Any],
    history_result: Dict[str, Any],
    used_search: bool,
) -> str:
    """Compute confidence level for the final response."""
    if price_result.get("error"):
        return "low"
    if history_result.get("error"):
        return "low"
    if used_search:
        return "medium" if history_result.get("history") else "low"
    return "high"


def _refine_search_payload(
    symbol: str,
    normalized_period: str,
    original_reason: Optional[str],
    region_hint: str = "US market",
) -> Dict[str, Any]:
    """
    Invoke DuckDuckGo fallback with an explicit region/time hint so the LLM sees structured metadata.
    """
    refined_reason = original_reason or "Insufficient structured history"
    fallback_result = _fallback_stock_history_via_search(
        symbol,
        normalized_period,
        original_error=refined_reason,
    )

    if not fallback_result.get("error"):
        search_query = fallback_result.get("search_query") or ""
        search_query = f"{search_query} {region_hint}".strip()
        fallback_result["search_query"] = search_query
        fallback_result.setdefault("fallback_reason", refined_reason)
        fallback_result["fallback_used"] = True

    return fallback_result


@tool
def hybrid_stock_brief(
    symbol: str,
    period: str = "1mo",
    allow_search: bool = True,
    region_hint: str = "US market",
) -> Dict[str, Any]:
    """
    Produce a concise stock briefing with multi-lane reasoning.

    Args:
        symbol: Stock ticker or company string (e.g., "AAPL", "NVIDIA").
        period: Natural language period (e.g., "past week", "2 months", "ytd").
        allow_search: Whether DuckDuckGo can be used when confidence is low.
        region_hint: Optional region to append to fallback search queries.

    Returns:
        Dict containing price snapshot, historical summary, reasoning channels, and confidence level.
    """
    symbol_clean = symbol.upper().strip()
    normalized_period, normalization_note = _normalize_history_period(period)

    logger.info(
        "[STOCK HYBRID] Requested %s for %s (normalized -> %s)",
        period,
        symbol_clean,
        normalized_period,
    )

    reasoning_channels: List[Dict[str, Any]] = []
    search_reason: Optional[str] = None
    fallback_payload: Optional[Dict[str, Any]] = None
    used_search = False
    primary_lane = "local_confident"

    price_result = _invoke_tool(_core_get_stock_price, {"symbol": symbol_clean})
    history_result = _invoke_tool(
        _core_get_stock_history,
        {"symbol": symbol_clean, "period": normalized_period},
    )

    if _should_trigger_search(history_result):
        primary_lane = "investigative_duckduckgo"
        used_search = allow_search
        search_reason = (
            history_result.get("fallback_reason")
            or history_result.get("error_message")
            or "Structured history incomplete"
        )

        justification = (
            f"History lookup for {symbol_clean} over {normalized_period} returned "
            f"{'an error' if history_result.get('error') else 'insufficient data'}."
        )
        reasoning_channels.append(
            _build_reasoning_lane(
                lane="local_confident",
                confidence="low",
                summary="Structured feed incomplete",
                justification=justification,
            )
        )

        if allow_search:
            fallback_payload = _refine_search_payload(
                symbol_clean,
                normalized_period,
                original_reason=search_reason,
                region_hint=region_hint,
            )
            history_result = fallback_payload
            reasoning_channels.append(
                _build_reasoning_lane(
                    lane="investigative_duckduckgo",
                    confidence="medium"
                    if not fallback_payload.get("error")
                    else "low",
                    summary=f"DuckDuckGo query executed for {symbol_clean}",
                    justification=(
                        f"Used search query '{fallback_payload.get('search_query')}' "
                        f"to supplement missing history."
                    ),
                    search_query=fallback_payload.get("search_query"),
                    sources=fallback_payload.get("history"),
                )
            )
        else:
            reasoning_channels.append(
                _build_reasoning_lane(
                    lane="investigative_duckduckgo",
                    confidence="low",
                    summary="Search disabled by configuration",
                    justification="allow_search set to False; skipping DuckDuckGo.",
                )
            )
    else:
        change = history_result.get("period_change")
        change_pct = history_result.get("period_change_percent")
        summary_parts = [
            f"{symbol_clean} over {normalized_period}:",
            f"change {change:+.2f}" if change is not None else "no change data",
            f"({change_pct:+.2f}%)" if change_pct is not None else "",
        ]
        reasoning_channels.append(
            _build_reasoning_lane(
                lane="local_confident",
                confidence="high",
                summary=" ".join(part for part in summary_parts if part).strip(),
                justification="Structured history returned sufficent data; no search required.",
            )
        )

    confidence_level = _calculate_confidence(price_result, history_result, used_search)

    if confidence_level == "low":
        meta_summary = (
            f"Unable to secure high-confidence data for {symbol_clean} ({normalized_period}). "
            "Recommend user clarification or alternative timeframe."
        )
        reasoning_channels.append(
            _build_reasoning_lane(
                lane="meta_reflection",
                confidence="low",
                summary=meta_summary,
                justification="Multiple attempts failed to produce reliable data.",
                search_query=history_result.get("search_query") if history_result else None,
            )
        )

    response: Dict[str, Any] = {
        "symbol": symbol_clean,
        "requested_period": period,
        "normalized_period": normalized_period,
        "confidence_level": confidence_level,
        "primary_lane": primary_lane,
        "reasoning_channels": reasoning_channels,
        "price_snapshot": price_result,
        "history": history_result,
        "fallback_used": bool(history_result.get("fallback_used")) if history_result else False,
    }

    if normalization_note:
        response["normalization_note"] = normalization_note

    if history_result:
        if history_result.get("search_query"):
            response["search_query"] = history_result.get("search_query")
        if history_result.get("fallback_reason"):
            response["search_reason"] = history_result.get("fallback_reason")
        if "history" in history_result:
            response["search_results"] = history_result.get("history")

    if search_reason and "search_reason" not in response:
        response["search_reason"] = search_reason

    return response


@tool
def hybrid_search_stock_symbol(query: str) -> Dict[str, Any]:
    """Wrapper around the core search tool to keep naming consistent in hybrid workflows."""
    return _invoke_tool(_core_search_stock_symbol, {"query": query})


STOCK_AGENT_TOOLS = [
    hybrid_stock_brief,
    hybrid_search_stock_symbol,
]

STOCK_AGENT_HIERARCHY = {
    "LEVEL 1 - Primary": [
        "hybrid_stock_brief",
        "hybrid_search_stock_symbol",
    ],
}
