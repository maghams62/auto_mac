from datetime import datetime, timezone

from src.graph.activity_service import ActivityService


class FakeGraphService:
    def __init__(self, *, available: bool = True, records=None):
        self._available = available
        self._records = records or []
        self.last_params = None

    def is_available(self) -> bool:
        return self._available

    def run_query(self, query, params=None):
        self.last_params = params or {}
        return self._records


def test_get_activity_for_component_when_graph_disabled():
    service = ActivityService(config={}, graph_service=FakeGraphService(available=False))
    result = service.get_activity_for_component("core.payments", window_days=7)
    assert result["component_id"] == "core.payments"
    assert result["git_events"] == 0
    assert result["activity_score"] == 0.0


def test_get_activity_for_component_happy_path():
    records = [
        {
            "component_id": "core.payments",
            "git_events": 2,
            "git_last": datetime(2025, 11, 29, 12, 0, tzinfo=timezone.utc),
            "slack_events": 3,
            "doc_drift_events": 1,
            "slack_last": datetime(2025, 11, 30, 8, 30, tzinfo=timezone.utc),
        }
    ]
    fake_graph = FakeGraphService(records=records)
    service = ActivityService(config={}, graph_service=fake_graph)

    result = service.get_activity_for_component("core.payments", window_days=14)
    assert result["git_events"] == 2
    assert result["slack_events"] == 3
    assert result["doc_drift_events"] == 1
    assert result["activity_score"] > 0
    assert result["last_event_at"].startswith("2025-11-30T08:30:00")
    assert fake_graph.last_params["cutoff"] is not None


def test_get_top_components_by_doc_drift():
    records = [
        {
            "component_id": "core.payments",
            "slack_events": 4,
            "doc_drift_events": 2,
            "git_events": 1,
            "doc_count": 3,
        },
        {
            "component_id": "notifications.dispatch",
            "slack_events": 2,
            "doc_drift_events": 1,
            "git_events": 0,
            "doc_count": 2,
        },
    ]
    fake_graph = FakeGraphService(records=records)
    service = ActivityService(config={}, graph_service=fake_graph)

    results = service.get_top_components_by_doc_drift(limit=5, window_days=30)
    assert len(results) == 2
    assert results[0]["component_id"] == "core.payments"
    assert results[0]["doc_drift_events"] == 2
    assert results[0]["activity_score"] > results[1]["activity_score"]
    assert fake_graph.last_params["limit"] == 5

