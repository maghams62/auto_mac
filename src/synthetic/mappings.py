from __future__ import annotations

from typing import Dict, Iterable, List, Set

API_COMPONENT_MAP: Dict[str, str] = {
    "/v1/payments/create": "core.payments",
    "/v1/notifications/send": "notifications.dispatch",
}

DOC_COMPONENT_MAP: Dict[str, List[str]] = {
    "docs/payments_api.md": ["docs.payments", "core.payments"],
    "docs/billing_flows.md": ["docs.payments", "billing.checkout"],
    "docs/notification_playbook.md": ["docs.notifications", "notifications.dispatch"],
    "docs/api_usage.md": ["docs.payments", "billing.checkout"],
    "docs/billing_onboarding.md": ["docs.payments", "billing.checkout"],
    "docs/changelog.md": ["docs.notifications"],
}

DOC_API_MAP: Dict[str, List[str]] = {
    "docs/payments_api.md": ["/v1/payments/create"],
    "docs/billing_flows.md": ["/v1/payments/create"],
    "docs/notification_playbook.md": ["/v1/notifications/send"],
    "docs/api_usage.md": ["/v1/payments/create"],
    "docs/billing_onboarding.md": ["/v1/payments/create"],
    "docs/changelog.md": ["/v1/notifications/send"],
}

COMPONENT_SERVICE_MAP: Dict[str, str] = {
    "core.payments": "core-api-service",
    "core.webhooks": "core-api-service",
    "billing.checkout": "billing-service",
    "notifications.dispatch": "notifications-service",
    "docs.payments": "docs-portal",
    "docs.notifications": "docs-portal",
}


def services_for_components(component_ids: Iterable[str]) -> List[str]:
    services: Set[str] = set()
    for component_id in component_ids:
        service_id = COMPONENT_SERVICE_MAP.get(component_id)
        if service_id:
            services.add(service_id)
    return sorted(services)

