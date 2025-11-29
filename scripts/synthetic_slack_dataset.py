#!/usr/bin/env python3
"""
Create a synthetic Slack dataset focused on the vat_code incident storyline.

The script emits a single JSON array (`slack_events.json` by default) containing
both `slack_message` and `slack_thread_summary` records. Configuration such as
workspace name, output path, and timezone is read from environment variables
with CLI overrides to keep it flexible for demos.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from dotenv import load_dotenv
from zoneinfo import ZoneInfo
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)

DEFAULT_CHANNEL_MAP = {
    "#billing-dev": "C123BILLING",
    "#core-api": "C123COREAPI",
    "#docs": "C123DOCS",
    "#support": "C123SUPPORT",
    "#incidents": "C123INCIDENTS",
    "#notifications": "C123NOTIFY",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MessageSpec:
    channel: str
    user: str
    text: str
    service_ids: Sequence[str]
    component_ids: Sequence[str]
    related_apis: Sequence[str]
    labels: Sequence[str]
    offset_minutes: int = 0


@dataclass(frozen=True)
class ThreadSpec:
    key: str
    channel: str
    start_offset_minutes: int
    summary_text: str
    summary_labels: Sequence[str]
    summary_service_ids: Sequence[str]
    summary_component_ids: Sequence[str]
    summary_related_apis: Sequence[str]
    messages: Sequence[MessageSpec] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Storylines
# ---------------------------------------------------------------------------


def build_thread_specs() -> List[ThreadSpec]:
    """Curated Slack threads covering incidents, debugging, docs, support, and noise."""
    return [
        ThreadSpec(
            key="incident-vat-code",
            channel="#incidents",
            start_offset_minutes=0,
            summary_text=(
                "Incident thread where Dina escalates EU merchants receiving 400 errors "
                "from /v1/payments/create. Alice confirms core-api now requires vat_code, "
                "Bob owns the billing fix, and everyone notes that docs/onboarding guides "
                "still show the old payload."
            ),
            summary_labels=["incident_summary", "doc_drift", "cross_service_impact"],
            summary_service_ids=["core-api-service", "billing-service"],
            summary_component_ids=["core.payments", "billing.checkout"],
            summary_related_apis=["/v1/payments/create"],
            messages=[
                MessageSpec(
                    channel="#incidents",
                    user="dina",
                    text=(
                        "🔥 Seeing a spike in 400s from `/v1/payments/create` for EU merchants "
                        "since 09:00. Logs say `missing vat_code` but our docs still only "
                        "show `amount` + `currency` 🤔"
                    ),
                    service_ids=["core-api-service", "billing-service"],
                    component_ids=["core.payments", "billing.checkout"],
                    related_apis=["/v1/payments/create"],
                    labels=["incident", "doc_confusion", "api_change"],
                ),
                MessageSpec(
                    channel="#incidents",
                    user="bob",
                    text=(
                        "billing-service didn't ship anything today. Checkout payload still "
                        "matches `billing_onboarding.md` (no vat_code field)."
                    ),
                    service_ids=["billing-service"],
                    component_ids=["billing.checkout"],
                    related_apis=["/v1/payments/create"],
                    labels=["incident", "debugging"],
                    offset_minutes=3,
                ),
                MessageSpec(
                    channel="#incidents",
                    user="alice",
                    text=(
                        "We merged https://github.com/acme/core-api/pull/2041 yesterday—"
                        "`vat_code` is now required for EU regions. Docs portal update is still pending."
                    ),
                    service_ids=["core-api-service"],
                    component_ids=["core.payments"],
                    related_apis=["/v1/payments/create"],
                    labels=["incident", "api_change"],
                    offset_minutes=6,
                ),
                MessageSpec(
                    channel="#incidents",
                    user="frank",
                    text=(
                        "Treating this as sev2 until code + docs are fixed. @bob please prioritize "
                        "sending vat_code from checkout."
                    ),
                    service_ids=["core-api-service", "billing-service"],
                    component_ids=["core.payments", "billing.checkout"],
                    related_apis=["/v1/payments/create"],
                    labels=["incident", "coordination"],
                    offset_minutes=10,
                ),
                MessageSpec(
                    channel="#incidents",
                    user="dina",
                    text=(
                        "Attaching merchant logs (`status=400`, `error=missing vat_code`). "
                        "Support can't point to docs because onboarding guide is outdated."
                    ),
                    service_ids=["billing-service"],
                    component_ids=["billing.checkout"],
                    related_apis=["/v1/payments/create"],
                    labels=["incident", "doc_confusion"],
                    offset_minutes=13,
                ),
                MessageSpec(
                    channel="#incidents",
                    user="bob",
                    text="Coding a patch now—EU carts will pass vat_code + region flag. ETA 30m.",
                    service_ids=["billing-service"],
                    component_ids=["billing.checkout"],
                    related_apis=["/v1/payments/create"],
                    labels=["incident", "debugging"],
                    offset_minutes=18,
                ),
                MessageSpec(
                    channel="#incidents",
                    user="alice",
                    text=(
                        "I'll add follow-up tasks on the PR to refresh `docs/payments_api.md` "
                        "and `docs/billing_flows.md`."
                    ),
                    service_ids=["core-api-service", "docs-portal"],
                    component_ids=["core.payments", "docs.payments"],
                    related_apis=["/v1/payments/create"],
                    labels=["incident", "doc_drift"],
                    offset_minutes=22,
                ),
            ],
        ),
        ThreadSpec(
            key="billing-dev-debug",
            channel="#billing-dev",
            start_offset_minutes=40,
            summary_text=(
                "Billing developers reproduce the 400 errors from /v1/payments/create, "
                "point out that `billing_onboarding.md` is stale, and agree to ship a "
                "vat_code patch plus doc tickets."
            ),
            summary_labels=["debugging_summary", "doc_drift"],
            summary_service_ids=["billing-service", "core-api-service"],
            summary_component_ids=["billing.checkout", "core.payments"],
            summary_related_apis=["/v1/payments/create"],
            messages=[
                MessageSpec(
                    channel="#billing-dev",
                    user="bob",
                    text=(
                        "Anyone else still getting `400 Bad Request (missing vat_code)` from "
                        "`core_api_client.create_payment` when `cart.region == 'EU'`?"
                    ),
                    service_ids=["billing-service"],
                    component_ids=["billing.checkout"],
                    related_apis=["/v1/payments/create"],
                    labels=["debugging", "api_change"],
                ),
                MessageSpec(
                    channel="#billing-dev",
                    user="carol",
                    text=(
                        "Yeah repro'd on staging. Our client still posts `{\"amount\": total, "
                        "\"currency\": currency}` exactly how `billing_onboarding.md` documents it."
                    ),
                    service_ids=["billing-service"],
                    component_ids=["billing.checkout"],
                    related_apis=["/v1/payments/create"],
                    labels=["debugging", "doc_drift"],
                    offset_minutes=4,
                ),
                MessageSpec(
                    channel="#billing-dev",
                    user="alice",
                    text=(
                        "`vat_code` became mandatory for EU in yesterday's deploy. Example payload: "
                        "`{\"amount\":1000,\"currency\":\"EUR\",\"region\":\"EU\",\"vat_code\":\"DE123\"}`."
                    ),
                    service_ids=["core-api-service"],
                    component_ids=["core.payments"],
                    related_apis=["/v1/payments/create"],
                    labels=["api_change"],
                    offset_minutes=7,
                ),
                MessageSpec(
                    channel="#billing-dev",
                    user="bob",
                    text=(
                        "Cool, pushing a patch to thread vat_code through checkout + updating "
                        "`src/core_api_client.py`. Will open a doc bug for `billing_onboarding.md`."
                    ),
                    service_ids=["billing-service"],
                    component_ids=["billing.checkout"],
                    related_apis=["/v1/payments/create"],
                    labels=["debugging", "doc_drift"],
                    offset_minutes=12,
                ),
                MessageSpec(
                    channel="#billing-dev",
                    user="frank",
                    text=(
                        "Thanks team. After patch ships, let's sync with docs on the portal plus "
                        "merchant guide updates."
                    ),
                    service_ids=["billing-service", "docs-portal"],
                    component_ids=["billing.checkout", "docs.payments"],
                    related_apis=["/v1/payments/create"],
                    labels=["coordination", "doc_drift"],
                    offset_minutes=17,
                ),
            ],
        ),
        ThreadSpec(
            key="docs-drift",
            channel="#docs",
            start_offset_minutes=80,
            summary_text=(
                "Eve highlights that `docs/payments_api.md` and `docs/billing_flows.md` still "
                "describe the old contract, coordinating updates with Alice and Bob."
            ),
            summary_labels=["doc_drift_summary"],
            summary_service_ids=["docs-portal", "core-api-service", "billing-service"],
            summary_component_ids=["docs.payments", "core.payments", "billing.checkout"],
            summary_related_apis=["/v1/payments/create"],
            messages=[
                MessageSpec(
                    channel="#docs",
                    user="eve",
                    text=(
                        "Heads-up: `docs/payments_api.md` and `docs/billing_flows.md` still show "
                        "`POST /v1/payments/create` without vat_code. Need authoritative text ASAP."
                    ),
                    service_ids=["docs-portal"],
                    component_ids=["docs.payments"],
                    related_apis=["/v1/payments/create"],
                    labels=["doc_drift"],
                ),
                MessageSpec(
                    channel="#docs",
                    user="alice",
                    text=(
                        "From core-api side the contract is: amount, currency, region, vat_code "
                        "(required for EU). I can drop a snippet for the reference section."
                    ),
                    service_ids=["core-api-service"],
                    component_ids=["core.payments"],
                    related_apis=["/v1/payments/create"],
                    labels=["doc_drift", "coordination"],
                    offset_minutes=5,
                ),
                MessageSpec(
                    channel="#docs",
                    user="bob",
                    text=(
                        "`billing_onboarding.md` also needs a rewrite because merchants copy that "
                        "payload verbatim. I'll send you the new sample later today."
                    ),
                    service_ids=["billing-service"],
                    component_ids=["billing.checkout"],
                    related_apis=["/v1/payments/create"],
                    labels=["doc_drift", "coordination"],
                    offset_minutes=9,
                ),
                MessageSpec(
                    channel="#docs",
                    user="eve",
                    text="Perfect—I'll update the docs portal once both snippets land. 🙏",
                    service_ids=["docs-portal"],
                    component_ids=["docs.payments"],
                    related_apis=["/v1/payments/create"],
                    labels=["doc_drift", "coordination"],
                    offset_minutes=12,
                ),
            ],
        ),
        ThreadSpec(
            key="support-escalation",
            channel="#support",
            start_offset_minutes=120,
            summary_text=(
                "Support shares merchant complaints about checkout failures, tags Alice/Bob, "
                "and references the vat_code change plus stale docs."
            ),
            summary_labels=["support_summary", "incident_related"],
            summary_service_ids=["billing-service", "core-api-service"],
            summary_component_ids=["billing.checkout", "core.payments"],
            summary_related_apis=["/v1/payments/create"],
            messages=[
                MessageSpec(
                    channel="#support",
                    user="dina",
                    text=(
                        "3 merchants filed tickets since 09:30 (EU only). Error snippet: "
                        "`400 missing vat_code`. Tagging @bob @alice for visibility."
                    ),
                    service_ids=["billing-service", "core-api-service"],
                    component_ids=["billing.checkout", "core.payments"],
                    related_apis=["/v1/payments/create"],
                    labels=["support_complaint", "api_change"],
                ),
                MessageSpec(
                    channel="#support",
                    user="bob",
                    text=(
                        "Fix is in review—billing will now send vat_code for EU carts. Sorry for the churn!"
                    ),
                    service_ids=["billing-service"],
                    component_ids=["billing.checkout"],
                    related_apis=["/v1/payments/create"],
                    labels=["support_complaint", "coordination"],
                    offset_minutes=6,
                ),
                MessageSpec(
                    channel="#support",
                    user="alice",
                    text=(
                        "Docs were lagging but we're updating the portal + merchant guide so support has "
                        "something accurate to link soon."
                    ),
                    service_ids=["core-api-service", "docs-portal"],
                    component_ids=["core.payments", "docs.payments"],
                    related_apis=["/v1/payments/create"],
                    labels=["doc_drift", "coordination"],
                    offset_minutes=10,
                ),
            ],
        ),
        ThreadSpec(
            key="notifications-status",
            channel="#notifications",
            start_offset_minutes=150,
            summary_text=(
                "Lightweight notifications thread confirming /v1/notifications/send is unaffected "
                "by the vat_code rollout but monitoring remains in place."
            ),
            summary_labels=["status_update"],
            summary_service_ids=["notifications-service", "core-api-service"],
            summary_component_ids=["notifications.dispatch", "core.payments"],
            summary_related_apis=["/v1/notifications/send"],
            messages=[
                MessageSpec(
                    channel="#notifications",
                    user="carol",
                    text=(
                        "FYI: receipts still go out via `/v1/notifications/send`. Seeing normal "
                        "latency even while billing fixes vat_code."
                    ),
                    service_ids=["notifications-service"],
                    component_ids=["notifications.dispatch"],
                    related_apis=["/v1/notifications/send"],
                    labels=["status_update"],
                ),
                MessageSpec(
                    channel="#notifications",
                    user="alice",
                    text=(
                        "Thanks! Core-api only touched payments this week, so notifications "
                        "pipeline should stay green—appreciate the confirmation."
                    ),
                    service_ids=["core-api-service", "notifications-service"],
                    component_ids=["core.payments", "notifications.dispatch"],
                    related_apis=["/v1/notifications/send"],
                    labels=["coordination"],
                    offset_minutes=4,
                ),
                MessageSpec(
                    channel="#notifications",
                    user="frank",
                    text="Log the check in ops runbook so we have an audit trail. 👍",
                    service_ids=["notifications-service"],
                    component_ids=["notifications.dispatch"],
                    related_apis=["/v1/notifications/send"],
                    labels=["coordination"],
                    offset_minutes=6,
                ),
            ],
        ),
        ThreadSpec(
            key="core-api-noise",
            channel="#core-api",
            start_offset_minutes=180,
            summary_text="Low-signal chatter about log levels for webhook retries.",
            summary_labels=["noise"],
            summary_service_ids=["core-api-service"],
            summary_component_ids=["core.webhooks"],
            summary_related_apis=[],
            messages=[
                MessageSpec(
                    channel="#core-api",
                    user="carol",
                    text="Anyone mind if I drop webhook retry logs to DEBUG? Channel is 🔥 right now.",
                    service_ids=["core-api-service"],
                    component_ids=["core.webhooks"],
                    related_apis=[],
                    labels=["noise"],
                ),
                MessageSpec(
                    channel="#core-api",
                    user="frank",
                    text="Do it, but only on staging. Prod still needs INFO until after Q4.",
                    service_ids=["core-api-service"],
                    component_ids=["core.webhooks"],
                    related_apis=[],
                    labels=["noise"],
                    offset_minutes=3,
                ),
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the synthetic Slack dataset.")
    parser.add_argument("--workspace", help="Workspace name override (default from SLACK_WORKSPACE).")
    parser.add_argument("--output", help="Explicit output path for slack_events.json.")
    parser.add_argument("--data-dir", help="Directory override (default SLACK_DATA_DIR).")
    parser.add_argument("--filename", help="Output filename override (default SLACK_EVENTS_FILE).")
    parser.add_argument("--timezone", help="Timezone name override (default SLACK_DEFAULT_TIMEZONE).")
    parser.add_argument("--base-time", help="ISO timestamp for the first thread (default SLACK_BASE_TIME).")
    parser.add_argument("--channel-map", help="Comma-separated or JSON map of channel names to IDs.")
    parser.add_argument("--config", help="Path to config.yaml for channel metadata.")
    parser.add_argument("--force", action="store_true", help="Overwrite file if it already exists.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    return parser.parse_args()


def resolve_timezone(name: str | None) -> ZoneInfo:
    tz_name = name or os.getenv("SLACK_DEFAULT_TIMEZONE", "UTC")
    return ZoneInfo(tz_name)


def parse_start_time(value: str | None, tz: ZoneInfo) -> datetime:
    raw = value or os.getenv("SLACK_BASE_TIME", "2025-11-26T09:00:00")
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def resolve_workspace(arg_workspace: str | None) -> str:
    return arg_workspace or os.getenv("SLACK_WORKSPACE", "acme")


def resolve_output_path(args: argparse.Namespace) -> Path:
    if args.output:
        return Path(args.output).expanduser()

    data_dir = Path(args.data_dir or os.getenv("SLACK_DATA_DIR", "data/synthetic_slack")).expanduser()
    filename = args.filename or os.getenv("SLACK_EVENTS_FILE", "slack_events.json")
    return data_dir / filename


def normalize_channel_name(name: str) -> str:
    name = name.strip()
    if not name:
        return name
    return name if name.startswith("#") else f"#{name}"


def parse_mapping_string(raw: str | None) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not raw:
        return mapping

    raw = raw.strip()
    if not raw:
        return mapping

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        for key, value in parsed.items():
            if isinstance(key, str) and isinstance(value, str):
                norm = normalize_channel_name(key)
                if norm and value.strip():
                    mapping[norm] = value.strip()
        return mapping

    for pair in raw.split(","):
        if "=" not in pair:
            continue
        name, channel_id = pair.split("=", 1)
        norm = normalize_channel_name(name)
        if norm and channel_id.strip():
            mapping[norm] = channel_id.strip()
    return mapping


def load_config_channels(path: Path) -> Dict[str, str]:
    path = path.expanduser()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
    except Exception:
        return {}

    channels = (
        config.get("activity_ingest", {})
        .get("slack", {})
        .get("channels", [])
    )
    mapping: Dict[str, str] = {}
    if isinstance(channels, list):
        for entry in channels:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            channel_id = entry.get("id")
            if isinstance(name, str) and isinstance(channel_id, str):
                norm = normalize_channel_name(name)
                if norm:
                    mapping[norm] = channel_id
    return mapping


def build_channel_map(args: argparse.Namespace) -> Dict[str, str]:
    config_path = Path(
        args.config
        or os.getenv("SLACK_CONFIG_PATH")
        or PROJECT_ROOT / "config.yaml"
    )
    mapping: Dict[str, str] = dict(DEFAULT_CHANNEL_MAP)
    mapping.update(load_config_channels(config_path))
    mapping.update(parse_mapping_string(os.getenv("SLACK_CHANNEL_MAP")))
    mapping.update(parse_mapping_string(args.channel_map))
    return mapping


def dt_to_ts(dt: datetime) -> str:
    return f"{dt.timestamp():.5f}"


def build_events(
    workspace: str,
    start_time: datetime,
    specs: Iterable[ThreadSpec],
    channel_map: Dict[str, str],
) -> List[dict]:
    events: List[dict] = []

    for thread in specs:
        thread_start = start_time + timedelta(minutes=thread.start_offset_minutes)
        thread_ts = None
        thread_first_dt: datetime | None = None
        thread_last_dt: datetime | None = None

        for message in thread.messages:
            msg_dt = thread_start + timedelta(minutes=message.offset_minutes)
            if thread_first_dt is None or msg_dt < thread_first_dt:
                thread_first_dt = msg_dt
            thread_last_dt = msg_dt

            ts = dt_to_ts(msg_dt)
            if thread_ts is None:
                thread_ts = ts

            channel_id = channel_map.get(message.channel)
            events.append(
                {
                    "id": f"slack_message:{message.channel}:{ts}",
                    "source_type": "slack_message",
                    "workspace": workspace,
                    "channel": message.channel,
                    "channel_id": channel_id,
                    "thread_ts": thread_ts,
                    "message_ts": ts,
                    "user": message.user,
                    "timestamp": msg_dt.isoformat(),
                    "text_raw": message.text,
                    "service_ids": list(message.service_ids),
                    "component_ids": list(message.component_ids),
                    "related_apis": list(message.related_apis),
                    "labels": list(message.labels),
                }
            )

        if thread_first_dt and thread_last_dt and thread_ts:
            channel_id = channel_map.get(thread.channel)
            summary_ts = dt_to_ts(thread_last_dt)
            events.append(
                {
                    "id": f"slack_thread:{thread.channel}:{thread_ts}",
                    "source_type": "slack_thread_summary",
                    "workspace": workspace,
                    "channel": thread.channel,
                    "channel_id": channel_id,
                    "thread_ts": thread_ts,
                    "message_ts": summary_ts,
                    "timestamp": thread_last_dt.isoformat(),
                    "start_timestamp": thread_first_dt.isoformat(),
                    "end_timestamp": thread_last_dt.isoformat(),
                    "text_raw": thread.summary_text,
                    "service_ids": list(thread.summary_service_ids),
                    "component_ids": list(thread.summary_component_ids),
                    "related_apis": list(thread.summary_related_apis),
                    "labels": list(thread.summary_labels),
                }
            )

    return events


def write_dataset(path: Path, events: Sequence[dict], pretty: bool, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        raise SystemExit(f"{path} already exists. Re-run with --force to overwrite.")
    with path.open("w", encoding="utf-8") as handle:
        json.dump(events, handle, indent=2 if pretty else None)
        if pretty:
            handle.write("\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = parse_args()
    workspace = resolve_workspace(args.workspace)
    tz = resolve_timezone(args.timezone)
    start_time = parse_start_time(args.base_time, tz)
    output_path = resolve_output_path(args)
    channel_map = build_channel_map(args)

    specs = build_thread_specs()
    events = build_events(workspace, start_time, specs, channel_map)

    missing_channels = sorted(
        {thread.channel for thread in specs if thread.channel not in channel_map}
    )
    if missing_channels:
        print(
            "Warning: missing channel IDs for "
            + ", ".join(missing_channels)
            + ". Update SLACK_CHANNEL_MAP or config.yaml to silence this warning."
        )

    write_dataset(output_path, events, pretty=args.pretty, force=args.force)

    print(f"Wrote {len(events)} Slack records to {output_path}")


if __name__ == "__main__":
    main()
