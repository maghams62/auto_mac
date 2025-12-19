from src.services import ttl_cache
from src.services.ttl_cache import TTLCache


def test_cache_set_get_and_expire(monkeypatch):
    current = {"value": 1000.0}

    def fake_time():
        return current["value"]

    monkeypatch.setattr(ttl_cache.time, "time", fake_time)

    cache = TTLCache(ttl_seconds=10, label="test")
    assert cache.get("missing") is None
    cache.set("foo", "bar")
    assert cache.get("foo") == "bar"

    current["value"] += 11
    assert cache.get("foo") is None

    stats = cache.describe()
    assert stats.label == "test"
    assert stats.hits == 1
    assert stats.misses == 2  # one for first miss, one after expiry


def test_cache_invalidate():
    cache = TTLCache(ttl_seconds=60)
    cache.set("key", "value")
    assert cache.get("key") == "value"
    cache.invalidate("key")
    assert cache.get("key") is None

    cache.set("a", 1)
    cache.set("b", 2)
    cache.invalidate()
    assert cache.describe().size == 0

