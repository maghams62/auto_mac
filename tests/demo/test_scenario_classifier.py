from src.demo.scenario_classifier import (
    PAYMENTS_SCENARIO,
    NOTIFICATIONS_SCENARIO,
    classify_question,
)


def test_classifier_detects_payments_keywords():
    scenario = classify_question("Why are people complaining about payments VAT?")
    assert scenario is PAYMENTS_SCENARIO
    assert scenario.api == "/v1/payments/create"


def test_classifier_detects_notifications_keywords():
    scenario = classify_question("What is wrong with notifications receipts template_version?")
    assert scenario is NOTIFICATIONS_SCENARIO
    assert "notifications-service" in scenario.services


def test_classifier_defaults_to_payments():
    scenario = classify_question("Tell me about docs drift?")
    assert scenario is PAYMENTS_SCENARIO

