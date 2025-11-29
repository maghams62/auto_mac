#!/usr/bin/env python3
"""
Lightweight preflight checks orchestrator.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent

CHECK_COMMANDS: Dict[str, List[str]] = {
    "vectordb": [sys.executable, str(SCRIPTS_DIR / "verify_vectordb.py")],
}


def run_check(name: str) -> int:
    cmd = CHECK_COMMANDS[name]
    print(f"\n=== Running check: {name} ===")
    result = subprocess.run(cmd, cwd=REPO_ROOT, text=True)
    if result.returncode == 0:
        print(f"=== Check '{name}' passed ===")
    else:
        print(f"=== Check '{name}' failed with exit code {result.returncode} ===")
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run project sanity checks.")
    parser.add_argument("--vectordb", action="store_true", help="Run the Qdrant connectivity check.")
    parser.add_argument("--all", action="store_true", help="Run every available check.")
    parser.add_argument("--list", action="store_true", help="List available checks and exit.")
    args = parser.parse_args()

    if args.list:
        print("Available checks:")
        for name in sorted(CHECK_COMMANDS):
            print(f" - {name}")
        return 0

    selected = []
    if args.vectordb:
        selected.append("vectordb")

    if args.all or not selected:
        selected = list(CHECK_COMMANDS)

    exit_code = 0
    for check_name in selected:
        rc = run_check(check_name)
        if rc != 0:
            exit_code = rc

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

