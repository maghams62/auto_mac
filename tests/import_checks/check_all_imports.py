#!/usr/bin/env python3
"""
Comprehensive import checker - finds all problematic imports in the codebase.
"""

import os
import re
from pathlib import Path
from typing import List, Tuple

# Problematic patterns: importing internal modules without 'src.' prefix
PROBLEMATIC_PATTERNS = [
    r'^from automation[^.]',
    r'^from documents[^.]',
    r'^from integrations[^.]',
    r'^from orchestrator[^.]',
    r'^from llm[^.]',
    r'^from memory[^.]',
    r'^from agent[^.]',
    r'^from utils[^.]',
    r'^from ui[^.]',
    r'^from config[^.](?!_)',  # Exclude config_manager, config_validator
]

# Standard library and third-party packages to exclude
SAFE_PATTERNS = [
    'typing', 'pathlib', 'datetime', 'json', 'os', 'sys', 're',
    'logging', 'subprocess', 'threading', 'asyncio', 'time',
    'openai', 'langchain', 'rich', 'flask', 'fastapi', 'pydantic',
    'dataclasses', 'enum', 'difflib', 'dotenv', 'werkzeug',
]

def is_problematic_import(line: str) -> bool:
    """Check if an import line is problematic."""
    line = line.strip()

    # Skip if it already uses 'src.' prefix
    if 'from src.' in line:
        return False

    # Check against problematic patterns
    for pattern in PROBLEMATIC_PATTERNS:
        if re.match(pattern, line):
            return True

    return False

def scan_file(file_path: Path) -> List[Tuple[int, str]]:
    """Scan a file for problematic imports."""
    issues = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if is_problematic_import(line):
                    issues.append((line_num, line.strip()))
    except Exception as e:
        pass  # Skip files that can't be read

    return issues

def scan_directory(root_dir: Path) -> dict:
    """Scan all Python files in a directory."""
    results = {}

    # Only scan src directory
    src_dir = root_dir / "src"
    if not src_dir.exists():
        return results

    for py_file in src_dir.rglob("*.py"):
        # Skip __pycache__ and venv
        if '__pycache__' in str(py_file) or 'venv' in str(py_file):
            continue

        issues = scan_file(py_file)
        if issues:
            results[py_file] = issues

    return results

def main():
    root_dir = Path(__file__).parent

    print("\n" + "="*80)
    print("COMPREHENSIVE IMPORT CHECKER")
    print("="*80 + "\n")

    print("Scanning for problematic imports in src/ directory...\n")

    results = scan_directory(root_dir)

    if not results:
        print("✅ No problematic imports found! All imports are using correct 'src.' prefix.\n")
        print("="*80 + "\n")
        return 0

    print(f"❌ Found problematic imports in {len(results)} file(s):\n")

    total_issues = 0
    for file_path, issues in sorted(results.items()):
        rel_path = file_path.relative_to(root_dir)
        print(f"\n📁 {rel_path}")
        print("   " + "-"*76)

        for line_num, line in issues:
            print(f"   Line {line_num:4d}: {line}")
            total_issues += 1

    print("\n" + "="*80)
    print(f"SUMMARY: {total_issues} problematic import(s) in {len(results)} file(s)")
    print("="*80 + "\n")

    print("💡 To fix: Replace 'from <module>' with 'from src.<module>'")
    print("   Example: 'from utils import' → 'from src.utils import'\n")

    return 1

if __name__ == "__main__":
    exit(main())
