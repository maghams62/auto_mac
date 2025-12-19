import pytest

from src.agent.control_input_guard import ControlInputGuard


@pytest.fixture
def guard():
    return ControlInputGuard(config=None)


def test_cancel_keyword_short_circuits(guard):
    decision = guard.inspect("Please cancel the last task", slash_token=None)
    assert decision is not None
    assert decision["status"] == "cancelled"
    assert decision["reason"] == "cancel_keyword"


def test_acknowledgement_keyword_returns_noop(guard):
    decision = guard.inspect("ok", slash_token=None)
    assert decision is not None
    assert decision["status"] == "noop"
    assert decision["reason"] == "acknowledgement"


def test_symbol_only_input_returns_noop(guard):
    decision = guard.inspect("👍", slash_token=None)
    assert decision is not None
    assert decision["status"] == "noop"
    assert decision["reason"] == "symbol_only"


def test_slash_stop_triggers_cancel(guard):
    decision = guard.inspect("/stop", slash_token="stop")
    assert decision is not None
    assert decision["status"] == "cancelled"
    assert decision["reason"] == "slash_control"

