from pathlib import Path

from src.config_manager import ConfigManager
from src.graph.synthetic_ingester import SyntheticGraphIngester


def _ingester(tmp_path=None):
    config = ConfigManager().get_config()
    return SyntheticGraphIngester(
        config,
        slack_path=Path("data/synthetic_slack/slack_events.json"),
        git_events_path=Path("data/synthetic_git/git_events.json"),
        git_prs_path=Path("data/synthetic_git/git_prs.json"),
    )


def test_payload_contains_expected_nodes():
    ingester = _ingester()
    payload = ingester.build_payload()

    assert "core-api-service" in payload.services
    assert "core.payments" in payload.components
    assert "/v1/payments/create" in payload.apis

    core_service_components = payload.service_components.get("core-api-service")
    assert core_service_components and "core.payments" in core_service_components

    assert payload.git_events
    assert payload.slack_events


def test_docs_linked_to_expected_apis():
    ingester = _ingester()
    payload = ingester.build_payload()

    notification_doc = payload.docs["docs/notification_playbook.md"]
    assert "/v1/notifications/send" in notification_doc["apis"]
    assert "notifications.dispatch" in notification_doc["components"]


def test_ingest_returns_summary_when_graph_disabled():
    ingester = _ingester()
    summary = ingester.ingest()
    assert summary["services"] >= 1
    assert summary["git_events"] >= 1

