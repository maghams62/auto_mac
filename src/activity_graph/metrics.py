from __future__ import annotations

import threading
from collections import Counter, defaultdict
from typing import Dict


class ActivityGraphMetrics:
    def __init__(self):
        self.request_counts: Counter[str] = Counter()
        self.latency_totals: Dict[str, Dict[str, float]] = defaultdict(lambda: {"total_ms": 0.0, "count": 0.0})
        self.cache_hits = 0
        self.cache_misses = 0
        self._lock = threading.Lock()

    def record_request(self, route: str, duration_ms: float) -> None:
        with self._lock:
            self.request_counts[route] += 1
            entry = self.latency_totals[route]
            entry["total_ms"] += duration_ms
            entry["count"] += 1

    def cache_hit(self) -> None:
        with self._lock:
            self.cache_hits += 1

    def cache_miss(self) -> None:
        with self._lock:
            self.cache_misses += 1

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            latency = {
                route: {
                    "count": entry["count"],
                    "avg_ms": entry["total_ms"] / entry["count"] if entry["count"] else 0.0,
                }
                for route, entry in self.latency_totals.items()
            }
            return {
                "requests_total": dict(self.request_counts),
                "cache_hits_total": self.cache_hits,
                "cache_misses_total": self.cache_misses,
                "latency_ms": latency,
            }


activity_graph_metrics = ActivityGraphMetrics()

