"""Helpers for computing derived KPI metrics surfaced by the dashboard."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

FRESHNESS_THRESHOLD_DAYS = 7.0


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_average(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _safe_pct(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return (numerator / denominator) * 100.0


def count_overdue_components(
    components: Sequence[Dict[str, Any]],
    *,
    freshness_threshold: float = FRESHNESS_THRESHOLD_DAYS,
) -> int:
    overdue = 0
    for component in components:
        freshness = _safe_float(component.get("docFreshnessDays"))
        if freshness is None:
            continue
        if freshness > freshness_threshold and (component.get("openIssues") or 0) > 0:
            overdue += 1
    return overdue


def _doc_freshness_stats(
    components: Sequence[Dict[str, Any]]
) -> Tuple[int, int, float, float]:
    freshness_values: List[float] = []
    fresh_within_threshold = 0
    for component in components:
        freshness = _safe_float(component.get("docFreshnessDays"))
        if freshness is None:
            continue
        freshness_values.append(freshness)
        if freshness <= FRESHNESS_THRESHOLD_DAYS:
            fresh_within_threshold += 1
    avg_age = _safe_average(freshness_values)
    percent_fresh = _safe_pct(fresh_within_threshold, len(freshness_values))
    return len(freshness_values), fresh_within_threshold, avg_age, percent_fresh


def _volatility_stats(
    components: Sequence[Dict[str, Any]]
) -> Tuple[float, Optional[Dict[str, Any]]]:
    scored_components: List[Tuple[float, Dict[str, Any]]] = []
    for component in components:
        change_velocity = _safe_float(component.get("changeVelocity")) or 0.0
        blast_radius = _safe_float(component.get("blastRadius")) or 0.0
        score = change_velocity * max(blast_radius, 1.0)
        scored_components.append((score, component))
    avg_score = _safe_average([score for score, _ in scored_components])
    top_component: Optional[Dict[str, Any]] = None
    if scored_components:
        top_component = max(scored_components, key=lambda item: item[0])[1]
    return avg_score, top_component


def _support_pressure_stats(
    components: Sequence[Dict[str, Any]]
) -> Tuple[float, Optional[Dict[str, Any]]]:
    pressures: List[float] = []
    for component in components:
        pressures.append(_safe_float(component.get("supportPressure")) or 0.0)
    avg_pressure = _safe_average(pressures)
    top_component: Optional[Dict[str, Any]] = None
    if components:
        top_component = max(
            components,
            key=lambda comp: _safe_float(comp.get("supportPressure")) or 0.0,
        )
    return avg_pressure, top_component


def _trend(current: float, previous: Optional[float]) -> Optional[float]:
    if previous is None:
        return None
    return round(current - previous, 2)


def build_graph_kpis(
    components: Sequence[Dict[str, Any]],
    *,
    previous_components: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    previous_components = previous_components or []

    (
        doc_samples,
        doc_recent,
        doc_avg_age,
        doc_percent_fresh,
    ) = _doc_freshness_stats(components)
    (
        prev_doc_samples,
        prev_doc_recent,
        _,
        prev_doc_percent_fresh,
    ) = _doc_freshness_stats(previous_components)

    doc_trend = _trend(doc_percent_fresh, prev_doc_percent_fresh if prev_doc_samples else None)

    doc_kpi = {
        "key": "doc_freshness",
        "label": "Docs updated <7d",
        "value": round(doc_percent_fresh, 1),
        "unit": "%",
        "trend": doc_trend,
        "meta": {
            "avgDocAgeDays": round(doc_avg_age, 1) if doc_samples else None,
            "coveredComponents": doc_samples,
            "freshComponents": doc_recent,
        },
    }

    volatility_avg, volatility_top = _volatility_stats(components)
    prev_volatility_avg, _ = _volatility_stats(previous_components)
    volatility_kpi = {
        "key": "dependency_volatility",
        "label": "Dependency volatility",
        "value": round(volatility_avg, 2),
        "unit": "score",
        "trend": _trend(volatility_avg, prev_volatility_avg if previous_components else None),
        "meta": {
            "topComponentId": volatility_top.get("id") if volatility_top else None,
            "topComponentName": volatility_top.get("name") if volatility_top else None,
            "blastRadius": volatility_top.get("blastRadius") if volatility_top else None,
        },
    }

    overdue_components = count_overdue_components(components)
    prev_overdue_components = count_overdue_components(previous_components)
    total_components = len(components)
    sla_percent_overdue = _safe_pct(overdue_components, total_components)
    prev_sla_percent = (
        _safe_pct(prev_overdue_components, len(previous_components))
        if previous_components
        else None
    )
    sla_kpi = {
        "key": "sla_trend",
        "label": "Components breaching SLA",
        "value": round(sla_percent_overdue, 1),
        "unit": "%",
        "trend": _trend(sla_percent_overdue, prev_sla_percent),
        "meta": {
            "overdueComponents": overdue_components,
            "totalComponents": total_components,
        },
    }

    support_avg, support_top = _support_pressure_stats(components)
    prev_support_avg, _ = _support_pressure_stats(previous_components)
    support_kpi = {
        "key": "support_pressure",
        "label": "Support pressure",
        "value": round(support_avg, 2),
        "unit": "avg_weight",
        "trend": _trend(support_avg, prev_support_avg if previous_components else None),
        "meta": {
            "topComponentId": support_top.get("id") if support_top else None,
            "topComponentName": support_top.get("name") if support_top else None,
        },
    }

    return [doc_kpi, volatility_kpi, sla_kpi, support_kpi]


__all__ = ["build_graph_kpis", "count_overdue_components"]

