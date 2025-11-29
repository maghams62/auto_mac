#!/usr/bin/env python3
"""
Validate synthetic Slack and Git datasets for graph/vector readiness.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


def load_records(path: Path) -> List[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    if path.suffix == ".jsonl":
        records = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
        return records
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_fields(record: dict, required: Sequence[str], errors: List[str], context: str) -> None:
    missing = [field for field in required if field not in record]
    if missing:
        errors.append(f"{context} missing fields: {missing}")


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate synthetic Slack and Git datasets.")
    parser.add_argument("--slack", default="data/synthetic_slack/slack_events.json")
    parser.add_argument("--git", default="data/synthetic_git/git_events.json")
    args = parser.parse_args()

    slack_records = load_records(Path(args.slack))
    git_records = load_records(Path(args.git))

    errors: List[str] = []
    warnings: List[str] = []

    required_slack_common = {
        "id",
        "source_type",
        "workspace",
        "channel",
        "channel_id",
        "thread_ts",
        "message_ts",
        "timestamp",
        "text_raw",
        "service_ids",
        "component_ids",
        "labels",
    }
    slack_services = set()
    slack_components = set()
    slack_apis = set()
    slack_threads = set()
    slack_channel_counts = Counter()

    for record in slack_records:
        context = record.get("id", "slack_record")
        ensure_fields(record, required_slack_common, errors, context)

        if isinstance(record.get("service_ids"), list):
            slack_services.update(record["service_ids"])
        if isinstance(record.get("component_ids"), list):
            slack_components.update(record["component_ids"])
        if isinstance(record.get("related_apis"), list):
            slack_apis.update(record["related_apis"])

        channel_id = record.get("channel_id")
        if not channel_id:
            errors.append(f"{context} missing channel_id mapping")

        source_type = record.get("source_type")
        if source_type == "slack_thread_summary":
            ensure_fields(record, ["start_timestamp", "end_timestamp"], errors, context)

        slack_channel_counts[record.get("channel")] += 1
        slack_threads.add(record.get("thread_ts"))

    if not slack_records:
        errors.append("Slack dataset is empty")

    required_git = {
        "id",
        "source_type",
        "repo",
        "branch",
        "timestamp",
        "text_for_embedding",
        "service_ids",
        "component_ids",
    }
    git_services = set()
    git_components = set()
    git_apis = set()
    git_timestamps: List[datetime] = []

    for record in git_records:
        if record.get("source_type") != "git_commit":
            continue
        context = record.get("id", "git_record")
        ensure_fields(record, required_git, errors, context)
        for field in ("commit_sha", "files_changed"):
            if not record.get(field):
                errors.append(f"{context} missing {field}")

        git_services.update(record.get("service_ids", []))
        git_components.update(record.get("component_ids", []))
        git_apis.update(record.get("changed_apis", []))
        ts = parse_dt(record.get("timestamp"))
        if ts:
            git_timestamps.append(ts)

    if not git_records:
        errors.append("Git dataset is empty")

    # Notifications coverage
    if "notifications-service" not in slack_services and "/v1/notifications/send" not in slack_apis:
        errors.append("Slack dataset lacks notifications-service or /v1/notifications/send coverage")

    # Cross-link checks
    if not (slack_services & git_services):
        errors.append("No overlap between Slack and Git service_ids")
    if not (slack_components & git_components):
        errors.append("No overlap between Slack and Git component_ids")
    if not (slack_apis & git_apis):
        errors.append("No overlap between Slack related_apis and Git changed_apis")

    # Temporal overlap check (warning only)
    slack_times = [parse_dt(rec.get("timestamp")) for rec in slack_records if rec.get("timestamp")]
    slack_times = [ts for ts in slack_times if ts]
    if slack_times and git_timestamps:
        slack_range = min(slack_times), max(slack_times)
        git_range = min(git_timestamps), max(git_timestamps)
        if slack_range[0] > git_range[1] or git_range[0] > slack_range[1]:
            warnings.append("Slack and Git timestamps do not overlap; downstream correlation will be weak.")

    # Activity summaries (informational)
    top_components = Counter()
    for comp in slack_components:
        top_components[comp] += sum(comp in rec.get("component_ids", []) for rec in slack_records)
    for comp in git_components:
        top_components[comp] += sum(comp in rec.get("component_ids", []) for rec in git_records)

    print("Slack events:", len(slack_records))
    print("Git events:", len(git_records))
    print("Slack channels:", slack_channel_counts)
    print("Top components (combined counts):", top_components.most_common(5))
    print("Service overlap:", slack_services & git_services)
    print("Component overlap:", slack_components & git_components)
    print("API overlap:", slack_apis & git_apis)

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")

    if errors:
        print("\nErrors:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("\nValidation passed ✅")


if __name__ == "__main__":
    main()

