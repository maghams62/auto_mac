"""
Performance monitoring and telemetry system.

Tracks key performance metrics to validate optimization effectiveness:
- Connection pool usage
- Cache hit rates
- Parallel execution speedup
- Batch sizes
- Rate limiter throttling
- Memory operation latencies
"""

import time
import logging
from typing import Dict, Any, List, Optional
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock

from .trajectory_logger import get_trajectory_logger

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    # Connection pooling
    connection_pool_requests: int = 0
    connection_pool_reuses: int = 0
    connection_pool_new_connections: int = 0
    
    # Caching
    cache_hits: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    cache_misses: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Parallel execution
    parallel_executions: int = 0
    sequential_executions: int = 0
    parallel_speedup_ratios: List[float] = field(default_factory=list)
    
    # Batch processing
    batch_operations: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    batch_sizes: Dict[str, List[int]] = field(default_factory=lambda: defaultdict(list))
    
    # Rate limiting
    rate_limit_waits: int = 0
    rate_limit_total_wait_time: float = 0.0
    rate_limit_throttles: int = 0
    
    # Memory operations
    memory_operation_times: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    
    # General
    total_requests: int = 0
    request_latencies: List[float] = field(default_factory=list)
    
    # Alerts / anomalies
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    
    def get_cache_hit_rate(self, cache_name: str) -> float:
        """Get cache hit rate for a specific cache."""
        hits = self.cache_hits.get(cache_name, 0)
        misses = self.cache_misses.get(cache_name, 0)
        total = hits + misses
        return hits / total if total > 0 else 0.0
    
    def get_avg_parallel_speedup(self) -> float:
        """Get average parallel execution speedup."""
        if not self.parallel_speedup_ratios:
            return 1.0
        return sum(self.parallel_speedup_ratios) / len(self.parallel_speedup_ratios)
    
    def get_avg_batch_size(self, operation_type: str) -> float:
        """Get average batch size for an operation type."""
        sizes = self.batch_sizes.get(operation_type, [])
        return sum(sizes) / len(sizes) if sizes else 0.0
    
    def get_avg_memory_operation_time(self, operation: str) -> float:
        """Get average time for a memory operation."""
        times = self.memory_operation_times.get(operation, [])
        return sum(times) / len(times) if times else 0.0
    
    def get_avg_request_latency(self) -> float:
        """Get average request latency."""
        return sum(self.request_latencies) / len(self.request_latencies) if self.request_latencies else 0.0
    
    def get_p95_latency(self) -> float:
        """Get 95th percentile latency."""
        if not self.request_latencies:
            return 0.0
        sorted_latencies = sorted(self.request_latencies)
        index = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[index]
    
    def get_connection_pool_reuse_rate(self) -> float:
        """Get connection pool reuse rate."""
        total = self.connection_pool_requests
        return self.connection_pool_reuses / total if total > 0 else 0.0


class PerformanceMonitor:
    """
    Global performance monitoring singleton.
    
    Tracks metrics across the application to validate optimization effectiveness.
    """
    
    _instance: Optional['PerformanceMonitor'] = None
    _lock = Lock()
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize performance monitor."""
        self.metrics = PerformanceMetrics()
        self._request_start_times: Dict[str, float] = {}
        self._operation_start_times: Dict[str, float] = {}
        self.config = config or {}
        self.trajectory_logger = get_trajectory_logger(config)
        logger.info("[PERFORMANCE MONITOR] Initialized")
    
    @classmethod
    def get_instance(cls) -> 'PerformanceMonitor':
        """Get or create global performance monitor instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def record_connection_pool_request(self, reused: bool = False):
        """Record a connection pool request."""
        self.metrics.connection_pool_requests += 1
        if reused:
            self.metrics.connection_pool_reuses += 1
        else:
            self.metrics.connection_pool_new_connections += 1
    
    def record_cache_hit(self, cache_name: str):
        """Record a cache hit."""
        self.metrics.cache_hits[cache_name] += 1
    
    def record_cache_miss(self, cache_name: str):
        """Record a cache miss."""
        self.metrics.cache_misses[cache_name] += 1
    
    def record_parallel_execution(self, sequential_time: float, parallel_time: float, 
                                  session_id: Optional[str] = None, interaction_id: Optional[str] = None):
        """Record parallel execution metrics."""
        self.metrics.parallel_executions += 1
        if sequential_time > 0:
            speedup = sequential_time / parallel_time
            self.metrics.parallel_speedup_ratios.append(speedup)
            logger.debug(f"[PERFORMANCE MONITOR] Parallel speedup: {speedup:.2f}x")
            
            # Log to trajectory
            self.trajectory_logger.log_trajectory(
                session_id=session_id or "unknown",
                interaction_id=interaction_id,
                phase="execution",
                component="performance_monitor",
                decision_type="parallel_execution",
                input_data={
                    "sequential_time_ms": sequential_time * 1000,
                    "parallel_time_ms": parallel_time * 1000
                },
                output_data={
                    "speedup": speedup,
                    "time_saved_ms": (sequential_time - parallel_time) * 1000
                },
                reasoning=f"Parallel execution achieved {speedup:.2f}x speedup",
                success=True
            )
    
    def record_sequential_execution(self):
        """Record sequential execution."""
        self.metrics.sequential_executions += 1
    
    def record_batch_operation(self, operation_type: str, batch_size: int):
        """Record a batch operation."""
        self.metrics.batch_operations[operation_type] += 1
        self.metrics.batch_sizes[operation_type].append(batch_size)
    
    def record_rate_limit_wait(self, wait_time: float, session_id: Optional[str] = None, 
                               interaction_id: Optional[str] = None, tokens_requested: Optional[int] = None):
        """Record rate limiter wait time."""
        self.metrics.rate_limit_waits += 1
        self.metrics.rate_limit_total_wait_time += wait_time
        if wait_time > 0:
            self.metrics.rate_limit_throttles += 1
            
            # Log rate limiting event to trajectory
            self.trajectory_logger.log_trajectory(
                session_id=session_id or "unknown",
                interaction_id=interaction_id,
                phase="execution",
                component="rate_limiter",
                decision_type="rate_limit_throttle",
                input_data={
                    "tokens_requested": tokens_requested,
                    "wait_time_ms": wait_time * 1000
                },
                output_data={
                    "throttled": True,
                    "total_waits": self.metrics.rate_limit_waits,
                    "total_throttles": self.metrics.rate_limit_throttles
                },
                reasoning=f"Rate limit throttling: waited {wait_time:.3f}s",
                success=True
            )
    
    def record_memory_operation(self, operation: str, duration: float):
        """Record memory operation duration."""
        self.metrics.memory_operation_times[operation].append(duration)
    
    def record_alert(self, alert_type: str, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Record an alert/anomaly for telemetry."""
        alert_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": alert_type,
            "message": message,
            "metadata": metadata or {}
        }
        self.metrics.alerts.append(alert_entry)
        if len(self.metrics.alerts) > 500:
            self.metrics.alerts = self.metrics.alerts[-500:]
        logger.warning(f"[PERFORMANCE MONITOR] ALERT {alert_type}: {message}")
        if metadata:
            logger.debug(f"[PERFORMANCE MONITOR] Alert metadata: {metadata}")

    def start_request(self, request_id: str):
        """Start tracking a request."""
        self._request_start_times[request_id] = time.time()
        self.metrics.total_requests += 1
    
    def end_request(self, request_id: str, session_id: Optional[str] = None, 
                    interaction_id: Optional[str] = None, phase: Optional[str] = None):
        """End tracking a request and record latency."""
        if request_id in self._request_start_times:
            duration = time.time() - self._request_start_times[request_id]
            self.metrics.request_latencies.append(duration)
            
            # Log performance metrics to trajectory
            if phase:
                self.trajectory_logger.log_trajectory(
                    session_id=session_id or "unknown",
                    interaction_id=interaction_id,
                    phase=phase,
                    component="performance_monitor",
                    decision_type="performance_metrics",
                    input_data={
                        "request_id": request_id,
                        "phase": phase
                    },
                    output_data={
                        "latency_ms": duration * 1000,
                        "total_requests": self.metrics.total_requests,
                        "avg_latency_ms": self.metrics.get_avg_request_latency() * 1000,
                        "p95_latency_ms": self.metrics.get_p95_latency() * 1000
                    },
                    reasoning=f"Request {request_id} completed in {duration*1000:.2f}ms",
                    latency_ms=duration * 1000,
                    success=True
                )
            
            del self._request_start_times[request_id]
            
            # Keep only last 1000 latencies to prevent memory growth
            if len(self.metrics.request_latencies) > 1000:
                self.metrics.request_latencies = self.metrics.request_latencies[-1000:]
    
    def start_operation(self, operation_id: str):
        """Start tracking an operation."""
        self._operation_start_times[operation_id] = time.time()
    
    def end_operation(self, operation_id: str, operation_type: str):
        """End tracking an operation and record duration."""
        if operation_id in self._operation_start_times:
            duration = time.time() - self._operation_start_times[operation_id]
            self.record_memory_operation(operation_type, duration)
            del self._operation_start_times[operation_id]
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get performance summary.
        
        Returns:
            Dictionary with performance metrics
        """
        return {
            "connection_pooling": {
                "total_requests": self.metrics.connection_pool_requests,
                "reuses": self.metrics.connection_pool_reuses,
                "new_connections": self.metrics.connection_pool_new_connections,
                "reuse_rate": self.metrics.get_connection_pool_reuse_rate()
            },
            "caching": {
                cache_name: {
                    "hits": self.metrics.cache_hits.get(cache_name, 0),
                    "misses": self.metrics.cache_misses.get(cache_name, 0),
                    "hit_rate": self.metrics.get_cache_hit_rate(cache_name)
                }
                for cache_name in set(list(self.metrics.cache_hits.keys()) + list(self.metrics.cache_misses.keys()))
            },
            "parallel_execution": {
                "parallel_count": self.metrics.parallel_executions,
                "sequential_count": self.metrics.sequential_executions,
                "avg_speedup": self.metrics.get_avg_parallel_speedup()
            },
            "batch_processing": {
                op_type: {
                    "count": self.metrics.batch_operations.get(op_type, 0),
                    "avg_batch_size": self.metrics.get_avg_batch_size(op_type)
                }
                for op_type in self.metrics.batch_operations.keys()
            },
            "rate_limiting": {
                "total_waits": self.metrics.rate_limit_waits,
                "total_wait_time": self.metrics.rate_limit_total_wait_time,
                "throttles": self.metrics.rate_limit_throttles,
                "avg_wait_time": (
                    self.metrics.rate_limit_total_wait_time / self.metrics.rate_limit_waits
                    if self.metrics.rate_limit_waits > 0 else 0.0
                )
            },
            "memory_operations": {
                op: {
                    "count": len(self.metrics.memory_operation_times.get(op, [])),
                    "avg_time": self.metrics.get_avg_memory_operation_time(op)
                }
                for op in self.metrics.memory_operation_times.keys()
            },
            "requests": {
                "total": self.metrics.total_requests,
                "avg_latency": self.metrics.get_avg_request_latency(),
                "p95_latency": self.metrics.get_p95_latency()
            },
            "alerts": {
                "count": len(self.metrics.alerts),
                "recent": list(self.metrics.alerts[-5:])
            }
        }
    
    def log_summary(self):
        """Log performance summary."""
        summary = self.get_summary()
        logger.info("=" * 80)
        logger.info("PERFORMANCE METRICS SUMMARY")
        logger.info("=" * 80)
        
        # Connection pooling
        cp = summary["connection_pooling"]
        logger.info(f"Connection Pool: {cp['reuses']}/{cp['total_requests']} reuses ({cp['reuse_rate']*100:.1f}%)")
        
        # Caching
        for cache_name, stats in summary["caching"].items():
            logger.info(f"Cache '{cache_name}': {stats['hit_rate']*100:.1f}% hit rate ({stats['hits']} hits, {stats['misses']} misses)")
        
        # Parallel execution
        pe = summary["parallel_execution"]
        logger.info(f"Parallel Execution: {pe['parallel_count']} parallel, {pe['sequential_count']} sequential, {pe['avg_speedup']:.2f}x avg speedup")
        
        # Batch processing
        for op_type, stats in summary["batch_processing"].items():
            logger.info(f"Batch '{op_type}': {stats['count']} operations, {stats['avg_batch_size']:.1f} avg batch size")
        
        # Rate limiting
        rl = summary["rate_limiting"]
        if rl["total_waits"] > 0:
            logger.info(f"Rate Limiting: {rl['throttles']} throttles, {rl['avg_wait_time']:.3f}s avg wait")
        
        # Memory operations
        for op, stats in summary["memory_operations"].items():
            logger.info(f"Memory '{op}': {stats['count']} operations, {stats['avg_time']:.3f}s avg time")
        
        # Requests
        req = summary["requests"]
        logger.info(f"Requests: {req['total']} total, {req['avg_latency']:.3f}s avg, {req['p95_latency']:.3f}s p95")
        
        alerts_summary = summary["alerts"]
        if alerts_summary["count"] > 0 and alerts_summary["recent"]:
            latest_alert = alerts_summary["recent"][-1]
            logger.info(f"Alerts: {alerts_summary['count']} recorded (latest: {latest_alert.get('type')} @ {latest_alert.get('timestamp')})")
        elif alerts_summary["count"] > 0:
            logger.info(f"Alerts: {alerts_summary['count']} recorded")
        
        logger.info("=" * 80)
    
    def reset(self):
        """Reset all metrics."""
        self.metrics = PerformanceMetrics()
        self._request_start_times.clear()
        self._operation_start_times.clear()
        logger.info("[PERFORMANCE MONITOR] Metrics reset")


# Global instance accessor
def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance."""
    return PerformanceMonitor.get_instance()
