#!/usr/bin/env python3
"""
Run the dependency mapper to populate component/code dependencies.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.config_manager import get_config
from src.ingestion import DependencyMapper


def main() -> int:
    parser = argparse.ArgumentParser(description="Populate Neo4j with dependency metadata.")
    parser.parse_args()

    config = get_config()
    mapper = DependencyMapper(config)
    result = mapper.ingest()
    print(f"[DEPENDENCY MAPPER] {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

