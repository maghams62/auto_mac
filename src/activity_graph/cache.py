from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    import redis  # type: ignore
except ImportError:  # pragma: no cover - redis is optional
    redis = None  # type: ignore


class ActivityGraphCache:
    def get(self, key: str) -> Optional[Any]:  # pragma: no cover - interface only
        raise NotImplementedError

    def set(self, key: str, value: Any) -> None:  # pragma: no cover - interface only
        raise NotImplementedError


class InMemoryActivityCache(ActivityGraphCache):
    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, Any] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if expires_at < time.time():
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time() + self.ttl_seconds, value)


class RedisActivityCache(ActivityGraphCache):
    def __init__(self, url: str, ttl_seconds: int):
        if not redis:  # pragma: no cover - requires redis dependency
            raise RuntimeError("redis package is not installed")
        self.ttl_seconds = ttl_seconds
        self.client = redis.from_url(url)

    def get(self, key: str) -> Optional[Any]:
        payload = self.client.get(key)
        if not payload:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    def set(self, key: str, value: Any) -> None:
        self.client.setex(key, self.ttl_seconds, json.dumps(value))


def build_cache(config: Dict[str, Any]) -> Optional[ActivityGraphCache]:
    cache_cfg = (config.get("activity_graph") or {}).get("cache") or {}
    if not cache_cfg.get("enabled", False):
        return None

    ttl_seconds = int(cache_cfg.get("ttl_seconds", 30))
    backend = cache_cfg.get("backend", "memory").lower()

    if backend == "redis":
        redis_url = cache_cfg.get("redis_url")
        if redis_url:
            try:
                logger.info("[ACTIVITY GRAPH] Using Redis cache backend at %s", redis_url)
                return RedisActivityCache(redis_url, ttl_seconds)
            except Exception as exc:
                logger.warning("[ACTIVITY GRAPH] Redis cache unavailable (%s); falling back to in-memory", exc)
        else:
            logger.warning("[ACTIVITY GRAPH] redis backend selected without redis_url; falling back to memory")

    logger.info("[ACTIVITY GRAPH] Using in-memory cache backend (ttl=%ss)", ttl_seconds)
    return InMemoryActivityCache(ttl_seconds)

