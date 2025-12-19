from src.ui.slash_commands import SlashCommandParser


def test_slash_alias_maps_to_slack():
    parser = SlashCommandParser()
    parsed = parser.parse("/sl recap #payments")
    assert parsed is not None
    assert parsed["agent"] == "slack"
    assert parsed["task"] == "recap #payments"


def test_unknown_command_returns_invalid():
    parser = SlashCommandParser()
    parsed = parser.parse("/xyz do something")
    assert parsed is not None
    assert parsed["command"] == "invalid"
    assert "I don't recognize" in parsed["error"]


def test_stop_command_short_circuits():
    parser = SlashCommandParser()
    parsed = parser.parse("/stop")
    assert parsed["command"] == "stop"
    assert parsed["agent"] is None

