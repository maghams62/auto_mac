from src.integrations.slash_slack_tooling import SlashSlackToolingAdapter


class DummySlackClient:
    def __init__(self, team_id: str = "T123TEST"):
        self._team_id = team_id
        self.auth_calls = 0

    def auth_test(self):
        self.auth_calls += 1
        return {"ok": True, "team_id": self._team_id}


class DummyMetadataService:
    def get_channel(self, channel_id):
        return None

    def refresh_channels(self, *, force: bool = False):
        return []

    def get_user(self, user_id):
        return None


def test_tooling_populates_deep_link_from_auth_test_when_team_id_missing():
    client = DummySlackClient(team_id="T123CORE")
    adapter = SlashSlackToolingAdapter(
        config={},
        client=client,
        metadata_service=DummyMetadataService(),
    )
    adapter.team_id = None

    normalized = adapter._normalize_message(
        {
            "text": "Release approval recorded",
            "ts": "1700000000.123456",
            "permalink": "https://workspace.slack.com/archives/C123/p1700000000123456",
        },
        "C123COREAPI",
        "core-api",
    )

    assert normalized.deep_link == "slack://channel?team=T123CORE&id=C123COREAPI&message=1700000000123456"
    assert client.auth_calls == 1

