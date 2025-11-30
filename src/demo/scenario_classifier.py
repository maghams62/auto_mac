from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class DemoScenario:
    """Represents one of the curated synthetic storylines."""

    name: str
    api: str
    services: List[str]
    components: List[str]
    docs: List[str]
    description: str
    keywords: List[str]


PAYMENTS_SCENARIO = DemoScenario(
    name="payments_vat",
    api="/v1/payments/create",
    services=["core-api-service", "billing-service", "docs-portal"],
    components=["core.payments", "billing.checkout", "docs.payments"],
    docs=["docs/payments_api.md", "docs/billing_flows.md", "docs/api_usage.md", "docs/billing_onboarding.md"],
    description="VAT payload drift between core-api, billing-service, and docs.",
    keywords=[
        "payment",
        "vat",
        "/v1/payments/create",
        "billing",
    ],
)

NOTIFICATIONS_SCENARIO = DemoScenario(
    name="notifications_template_version",
    api="/v1/notifications/send",
    services=["notifications-service", "docs-portal"],
    components=["notifications.dispatch", "docs.notifications"],
    docs=["docs/notification_playbook.md", "docs/changelog.md"],
    description="Notification receipts now require template_version; docs lag behind.",
    keywords=[
        "notification",
        "template version",
        "template_version",
        "/v1/notifications/send",
        "receipt",
    ],
)

SCENARIOS = [NOTIFICATIONS_SCENARIO, PAYMENTS_SCENARIO]


def classify_question(question: str) -> DemoScenario:
    """
    Map a natural language question onto one of the curated demo scenarios.

    Defaults to the payments VAT storyline when no keywords match.
    """
    text = (question or "").lower()
    for scenario in SCENARIOS:
        if any(keyword in text for keyword in scenario.keywords):
            return scenario
    return PAYMENTS_SCENARIO

