#!/usr/bin/env python3
"""
CLI demo for the Activity Graph service.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from src.activity_graph.models import TimeWindow
from src.activity_graph.service import ActivityGraphService
from src.utils import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Activity Graph demo (Option 1).")
    parser.add_argument("--component", help="Component ID (e.g., core.payments)")
    parser.add_argument("--top", type=int, help="Show top N dissatisfied components")
    parser.add_argument("--window", default="7d", help="Time window label (e.g., 7d, 24h)")
    parser.add_argument("--debug", action="store_true", help="Include weighted breakdowns.")
    args = parser.parse_args()

    config = load_config()
    service = ActivityGraphService(config)

    if args.component:
        window = TimeWindow.from_label(args.window)
        activity = service.compute_component_activity(args.component, window, include_debug=args.debug)
        print(json.dumps(asdict(activity), indent=2))
    elif args.top:
        window = TimeWindow.from_label(args.window)
        rows = service.top_dissatisfied_components(limit=args.top, time_window=window)
        if args.debug:
            rows = [
                service.compute_component_activity(row.component_id, window, include_debug=True)
                for row in rows
            ]
        for row in rows:
            print(json.dumps(asdict(row), indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

