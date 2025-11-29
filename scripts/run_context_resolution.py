#!/usr/bin/env python3
"""
CLI helper to evaluate cross-system impact analysis.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.config_manager import get_config
from src.graph import GraphService
from src.services.context_resolution_service import ContextResolutionService


def main() -> int:
    parser = argparse.ArgumentParser(description="Run context resolution impact analysis.")
    parser.add_argument("--api-id", dest="api_id", help="API endpoint ID (e.g., api:payments:/charge)")
    parser.add_argument("--component-id", dest="component_id", help="Component ID (e.g., comp:payments)")
    parser.add_argument("--artifact-id", dest="artifact_ids", action="append", help="CodeArtifact ID that changed (repeatable)")
    parser.add_argument("--max-depth", dest="max_depth", type=int, default=None)
    parser.add_argument(
        "--activity-window",
        dest="activity_window",
        type=int,
        default=None,
        help="Hours of activity to consider for change impacts (default from config)",
    )
    parser.add_argument(
        "--no-cross-repo",
        dest="no_cross_repo",
        action="store_true",
        help="Limit change-impact expansion to artifacts within the same repo",
    )
    args = parser.parse_args()

    if not args.api_id and not args.component_id and not args.artifact_ids:
        parser.error("Provide --api-id, --component-id, or --artifact-id")

    config = get_config()
    graph_service = GraphService(config)
    service = ContextResolutionService(
        graph_service,
        default_max_depth=config.get("context_resolution", {})
        .get("impact", {})
        .get("default_max_depth", 2),
        context_config=config.get("context_resolution", {}),
    )

    if not service.is_available():
        print("Graph service unavailable. Enable Neo4j to run this tool.")
        return 1

    if args.artifact_ids:
        result = service.resolve_change_impacts(
            component_id=args.component_id,
            artifact_ids=args.artifact_ids,
            max_depth=args.max_depth,
            include_docs=True,
            include_activity=True,
            include_cross_repo=not args.no_cross_repo,
            activity_window_hours=args.activity_window,
        )
    else:
        result = service.resolve_impacts(
            api_id=args.api_id,
            component_id=args.component_id,
            max_depth=args.max_depth,
            include_docs=True,
            include_services=True,
        )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

