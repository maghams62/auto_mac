#!/usr/bin/env python3
"""Replay synthetic Slack conversations into a real workspace."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


@dataclass
class SlackEntry:
    channel: str
    thread_ts: str
    message_ts: str
    timestamp: str
    user: str
    text_raw: str
    service_ids: List[str]
    component_ids: List[str]
    related_apis: List[str]
    labels: List[str]
    source_type: str

    @classmethod
    def from_json(cls, payload: Dict[str, Any]) -> "SlackEntry":
        return cls(
            channel=payload.get("channel", ""),
            thread_ts=str(payload.get("thread_ts", "")),
            message_ts=str(payload.get("message_ts", "")),
            timestamp=payload.get("timestamp") or "",
            user=payload.get("user") or "unknown",
            text_raw=payload.get("text_raw") or "",
            service_ids=list(payload.get("service_ids") or []),
            component_ids=list(payload.get("component_ids") or []),
            related_apis=list(payload.get("related_apis") or []),
            labels=list(payload.get("labels") or []),
            source_type=payload.get("source_type") or "slack_message",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay slack_events.json into a Slack workspace."
    )
    parser.add_argument(
        "--dataset",
        default="slack_events.json",
        help="Path to the slack_events.json file (default: %(default)s).",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Slack bot token. Defaults to SLACK_BOT_TOKEN from the environment.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without creating channels or posting messages.",
    )
    parser.add_argument(
        "--post-summaries",
        action="store_true",
        help="Also replay slack_thread_summary entries as recap replies.",
    )
    return parser.parse_args()


def load_dataset(dataset_path: Path) -> List[SlackEntry]:
    with dataset_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [SlackEntry.from_json(item) for item in payload]


def partition_entries(
    entries: Iterable[SlackEntry],
) -> Tuple[List[SlackEntry], List[SlackEntry]]:
    messages: List[SlackEntry] = []
    summaries: List[SlackEntry] = []
    for entry in entries:
        if entry.source_type == "slack_thread_summary":
            summaries.append(entry)
        elif entry.source_type == "slack_message":
            messages.append(entry)
    return messages, summaries


def iso_to_epoch(timestamp: str) -> float:
    if not timestamp:
        return 0.0
    candidate = timestamp
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(candidate).timestamp()
    except ValueError:
        return 0.0


def group_messages(
    entries: Iterable[SlackEntry],
) -> Dict[str, Dict[str, List[SlackEntry]]]:
    grouped: DefaultDict[str, DefaultDict[str, List[SlackEntry]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for entry in entries:
        channel = canonical_channel_name(entry.channel)
        grouped[channel][entry.thread_ts].append(entry)

    for channel_threads in grouped.values():
        for thread_entries in channel_threads.values():
            thread_entries.sort(
                key=lambda item: (iso_to_epoch(item.timestamp), item.message_ts)
            )
    return grouped


def build_summary_lookup(
    summaries: Iterable[SlackEntry],
) -> Dict[Tuple[str, str], List[SlackEntry]]:
    lookup: DefaultDict[Tuple[str, str], List[SlackEntry]] = defaultdict(list)
    for entry in summaries:
        channel = canonical_channel_name(entry.channel)
        lookup[(channel, entry.thread_ts)].append(entry)
    return lookup


def canonical_channel_name(channel: str) -> str:
    return channel.lstrip("#").strip()


def fetch_existing_channels(client: WebClient) -> Dict[str, str]:
    channels: Dict[str, str] = {}
    cursor: Optional[str] = None
    while True:
        response = safe_slack_call(
            client.conversations_list,
            limit=1000,
            cursor=cursor,
            types="public_channel,private_channel",
        )
        for channel in response.get("channels", []):
            channels[channel["name"]] = channel["id"]
        cursor = response.get("response_metadata", {}).get("next_cursor") or None
        if not cursor:
            break
    return channels


def safe_slack_call(func, *args, **kwargs):
    while True:
        try:
            return func(*args, **kwargs)
        except SlackApiError as exc:
            status = exc.response.status_code
            error = exc.response.get("error")
            if status == 429:
                retry_after = int(exc.response.headers.get("Retry-After", "1"))
                print(
                    f"Rate limited by Slack ({error}). Retrying in {retry_after}s...",
                    file=sys.stderr,
                )
                time.sleep(retry_after + 0.1)
                continue
            raise


def ensure_channel(
    client: Optional[WebClient],
    channel_cache: Dict[str, str],
    channel_name: str,
    dry_run: bool,
) -> str:
    if channel_name in channel_cache:
        return channel_cache[channel_name]

    if dry_run:
        synthetic_id = f"DRYRUN-{channel_name}"
        channel_cache[channel_name] = synthetic_id
        print(f"[dry-run] Would ensure channel #{channel_name}")
        return synthetic_id

    print(f"Ensuring channel #{channel_name} exists...")
    try:
        response = safe_slack_call(client.conversations_create, name=channel_name)
    except SlackApiError as exc:
        if exc.response.get("error") == "name_taken":
            print(f"Channel #{channel_name} already exists; refreshing cache.")
            channel_cache.update(fetch_existing_channels(client))
            if channel_name in channel_cache:
                return channel_cache[channel_name]
        raise
    channel_id = response["channel"]["id"]
    channel_cache[channel_name] = channel_id
    return channel_id


def format_message(entry: SlackEntry) -> str:
    base = f"[{entry.user}] {entry.text_raw}".strip()
    details: List[str] = []
    if entry.timestamp:
        details.append(f"orig_ts: {entry.timestamp}")
    if entry.service_ids:
        details.append(f"services: {', '.join(entry.service_ids)}")
    if entry.component_ids:
        details.append(f"components: {', '.join(entry.component_ids)}")
    if entry.related_apis:
        details.append(f"apis: {', '.join(entry.related_apis)}")
    if entry.labels:
        details.append(f"labels: {', '.join(entry.labels)}")
    if details:
        base = f"{base}\n_{' | '.join(details)}_"
    return base


def replay_thread(
    client: Optional[WebClient],
    channel_id: str,
    channel_name: str,
    entries: List[SlackEntry],
    dry_run: bool,
) -> str:
    real_thread_ts: Optional[str] = None
    for entry in entries:
        text = format_message(entry)
        if dry_run:
            if real_thread_ts is None:
                real_thread_ts = f"dryrun-{channel_name}-{entry.thread_ts}"
            target = f"#{channel_name}"
            prefix = "thread root" if entry.thread_ts == entry.message_ts else "reply"
            print(f"[dry-run] {target} ({prefix}): {text}")
            continue

        payload = {"channel": channel_id, "text": text}
        if real_thread_ts:
            payload["thread_ts"] = real_thread_ts
        response = safe_slack_call(client.chat_postMessage, **payload)
        if real_thread_ts is None:
            real_thread_ts = response["ts"]
    assert real_thread_ts is not None
    return real_thread_ts


def post_summary(
    client: Optional[WebClient],
    channel_id: str,
    channel_name: str,
    thread_ts: str,
    summary: SlackEntry,
    dry_run: bool,
) -> None:
    text = f"(thread summary) {format_message(summary)}"
    if dry_run:
        print(f"[dry-run] #{channel_name} summary reply: {text}")
        return
    safe_slack_call(
        client.chat_postMessage,
        channel=channel_id,
        thread_ts=thread_ts,
        text=text,
    )


def main() -> None:
    args = parse_args()
    dataset_path = Path(args.dataset).expanduser().resolve()

    if not dataset_path.exists():
        print(f"Dataset not found: {dataset_path}", file=sys.stderr)
        sys.exit(1)

    load_dotenv()
    token = args.token or os.getenv("SLACK_BOT_TOKEN")
    if not token and not args.dry_run:
        print("Missing Slack token. Set SLACK_BOT_TOKEN or pass --token.", file=sys.stderr)
        sys.exit(1)

    entries = load_dataset(dataset_path)
    messages, summaries = partition_entries(entries)
    if not messages:
        print("No slack_message entries found. Nothing to replay.", file=sys.stderr)
        return

    grouped = group_messages(messages)
    summary_lookup = build_summary_lookup(summaries)

    client = WebClient(token=token) if not args.dry_run else None
    channel_cache = fetch_existing_channels(client) if client else {}

    real_thread_index: Dict[Tuple[str, str], str] = {}

    for channel_name in sorted(grouped.keys()):
        channel_id = ensure_channel(client, channel_cache, channel_name, args.dry_run)
        channel_threads = grouped[channel_name]

        sorted_threads = sorted(
            channel_threads.items(),
            key=lambda item: iso_to_epoch(item[1][0].timestamp),
        )
        for synthetic_thread_ts, thread_entries in sorted_threads:
            real_ts = replay_thread(
                client=client,
                channel_id=channel_id,
                channel_name=channel_name,
                entries=thread_entries,
                dry_run=args.dry_run,
            )
            real_thread_index[(channel_name, synthetic_thread_ts)] = real_ts

            if args.post_summaries:
                for summary in summary_lookup.get((channel_name, synthetic_thread_ts), []):
                    post_summary(
                        client=client,
                        channel_id=channel_id,
                        channel_name=channel_name,
                        thread_ts=real_ts,
                        summary=summary,
                        dry_run=args.dry_run,
                    )

    print("Replay complete.")


if __name__ == "__main__":
    main()

