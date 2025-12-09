from src.utils.slack_links import build_slack_deep_link, build_slack_permalink


def test_build_slack_permalink_with_workspace_url():
    result = build_slack_permalink("C123", "1700000000.123456", workspace_url="https://example.slack.com")
    assert result == "https://example.slack.com/archives/C123/p1700000000123456"


def test_build_slack_permalink_falls_back_to_app_redirect():
    result = build_slack_permalink("C999", "1700000000.654321", team_id="T123")
    assert result == "https://slack.com/app_redirect?channel=C999&team=T123&message=1700000000654321"


def test_build_slack_permalink_handles_missing_inputs():
    assert build_slack_permalink(None, "1700000000.123") is None
    assert build_slack_permalink("C123", None, team_id=None, workspace_url=None) is None


def test_build_slack_deep_link_prefers_native_scheme():
    assert (
        build_slack_deep_link("C123", "1700000000.123456", team_id="T123")
        == "slack://channel?team=T123&id=C123&message=1700000000123456"
    )
    assert build_slack_deep_link("C123", "1700000000.123456") is None

