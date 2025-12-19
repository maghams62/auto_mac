#!/usr/bin/env python3
"""
Run graph validation checks and print results.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.config_manager import get_config
from src.graph import GraphService
from src.graph.validation import GraphValidator


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Neo4j graph validation checks.")
    parser.parse_args()

    config = get_config()
    graph_service = GraphService(config)
    validator = GraphValidator(graph_service)

    result = validator.run_checks()
    print(result)
    if not result.get("available"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

