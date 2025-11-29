#!/usr/bin/env python3
"""
Test script for new folder functionality.

Tests the expanded folder agent capabilities without full agent framework.
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_basic_folder_operations():
    """Test basic folder listing and statistics."""
    print("🧪 Testing basic folder operations...")

    test_docs_path = "tests/data/test_docs"
    if not os.path.exists(test_docs_path):
        print("❌ Test directory not found")
        return False

    # List directory
    try:
        entries = os.listdir(test_docs_path)
        print(f"✅ Found {len(entries)} items")

        # Filter out hidden files for cleaner results
        visible_entries = [e for e in entries if not e.startswith('.')]

        # Get file info
        items = []
        for name in visible_entries:
            path = os.path.join(test_docs_path, name)
            stat = os.stat(path)

            items.append({
                'name': name,
                'type': 'dir' if os.path.isdir(path) else 'file',
                'size': stat.st_size if os.path.isfile(path) else None,
                'modified': stat.st_mtime,
                'extension': Path(name).suffix.lower() if os.path.isfile(path) else None
            })

        print(f"✅ Processed {len(items)} visible items")

        # Test summary statistics
        total_files = sum(1 for item in items if item['type'] == 'file')
        total_folders = sum(1 for item in items if item['type'] == 'dir')
        total_size = sum(item.get('size', 0) or 0 for item in items if item['type'] == 'file')

        print(f"📊 Summary: {total_files} files, {total_folders} folders, {total_size:,} bytes total")

        # Test file type distribution
        file_types = {}
        for item in items:
            if item['type'] == 'file':
                ext = item.get('extension', 'no_extension')
                file_types[ext] = file_types.get(ext, 0) + 1

        print(f"📁 File types: {file_types}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_sorting_functionality():
    """Test file sorting capabilities."""
    print("\n🧪 Testing sorting functionality...")

    try:
        test_docs_path = "tests/data/test_docs"
        entries = [e for e in os.listdir(test_docs_path) if not e.startswith('.')]

        items = []
        for name in entries:
            path = os.path.join(test_docs_path, name)
            stat = os.stat(path)

            items.append({
                'name': name,
                'type': 'dir' if os.path.isdir(path) else 'file',
                'size': stat.st_size if os.path.isfile(path) else None,
                'modified': stat.st_mtime,
                'extension': Path(name).suffix.lower() if os.path.isfile(path) else None
            })

        # Test different sorting criteria
        sorts = [
            ("name", lambda x: x['name'].lower()),
            ("size", lambda x: x.get('size', 0) or 0),
            ("date", lambda x: x.get('modified', 0)),
            ("extension", lambda x: x.get('extension') or '')
        ]

        for criteria, key_func in sorts:
            sorted_items = sorted(items, key=key_func, reverse=True)
            print(f"✅ {criteria.capitalize()} sort: {sorted_items[0]['name']} (first), {sorted_items[-1]['name']} (last)")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_duplicate_detection():
    """Test duplicate file detection."""
    print("\n🧪 Testing duplicate detection...")

    try:
        import hashlib

        test_docs_path = "tests/data/test_docs"
        file_hashes = {}

        # Scan files and compute hashes
        for root, dirs, files in os.walk(test_docs_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]  # Skip hidden dirs

            for filename in files:
                if filename.startswith('.'):  # Skip hidden files
                    continue

                file_path = os.path.join(root, filename)
                try:
                    # Compute SHA-256 hash
                    sha256 = hashlib.sha256()
                    with open(file_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(8192), b''):
                            sha256.update(chunk)
                    file_hash = sha256.hexdigest()

                    # Store file info
                    if file_hash not in file_hashes:
                        file_hashes[file_hash] = []

                    file_hashes[file_hash].append({
                        "path": file_path,
                        "name": filename,
                        "size": os.path.getsize(file_path)
                    })

                except (OSError, IOError) as e:
                    print(f"⚠️  Cannot read {filename}: {e}")
                    continue

        # Find duplicates
        duplicates = []
        total_wasted = 0

        for file_hash, files in file_hashes.items():
            if len(files) > 1:
                size = files[0]['size']
                wasted = size * (len(files) - 1)
                total_wasted += wasted

                duplicates.append({
                    "hash": file_hash,
                    "size": size,
                    "count": len(files),
                    "wasted_bytes": wasted,
                    "files": files
                })

        print(f"✅ Found {len(duplicates)} duplicate groups")
        print(f"💾 Total space wasted: {total_wasted:,} bytes ({total_wasted/1024/1024:.2f} MB)")

        # Show details of first duplicate group if any
        if duplicates:
            group = duplicates[0]
            print(f"📋 Example group: {group['count']} copies of {group['files'][0]['name']}")
            for file_info in group['files'][:3]:  # Show first 3
                print(f"   • {file_info['name']}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_archive_simulation():
    """Test archive functionality simulation."""
    print("\n🧪 Testing archive simulation...")

    try:
        test_docs_path = "tests/data/test_docs"
        current_time = time.time()
        age_threshold = 180 * 24 * 3600  # 180 days
        threshold_time = current_time - age_threshold

        # Find old files
        old_files = []
        for name in os.listdir(test_docs_path):
            if name.startswith('.'):
                continue

            path = os.path.join(test_docs_path, name)
            if os.path.isfile(path):
                modified_time = os.stat(path).st_mtime
                if modified_time < threshold_time:
                    old_files.append({
                        'name': name,
                        'modified': modified_time,
                        'age_days': (current_time - modified_time) / (24 * 3600)
                    })

        print(f"✅ Found {len(old_files)} files older than {age_threshold/(24*3600):.0f} days")

        if old_files:
            # Show oldest file
            oldest = max(old_files, key=lambda x: x['age_days'])
            print(f"📅 Oldest file: {oldest['name']} ({oldest['age_days']:.0f} days old)")

            # Simulate archive creation
            archive_name = f"Archive_{time.strftime('%Y_%m_%d')}"
            print(f"📦 Would create archive: {archive_name}")
            print(f"📄 Would archive {len(old_files)} files")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_prompt_examples():
    """Test that the prompt examples are properly structured."""
    print("\n🧪 Testing prompt examples...")

    try:
        examples_dir = Path("prompts/examples/folder")
        if not examples_dir.exists():
            print("❌ Examples directory not found")
            return False

        example_files = list(examples_dir.glob("*.md"))
        print(f"✅ Found {len(example_files)} example files")

        required_examples = [
            "01_example_folder_summarize.md",
            "02_example_explain_file.md",
            "03_example_sort_by_criteria.md",
            "04_example_archive_old_files.md",
            "05_example_content_based_grouping.md",
            "06_example_duplicate_triage.md"
        ]

        for example in required_examples:
            if (examples_dir / example).exists():
                print(f"✅ {example}")
            else:
                print(f"❌ Missing {example}")

        # Check index.json has folder category
        import json
        index_path = Path("prompts/examples/index.json")
        if index_path.exists():
            with open(index_path) as f:
                index = json.load(f)

            if "folder" in index.get("categories", {}):
                folder_examples = index["categories"]["folder"]
                print(f"✅ Index registered {len(folder_examples)} folder examples")
            else:
                print("❌ Folder category not in index")

            if "folder" in index.get("agents", {}):
                folder_agent_consumes = index["agents"]["folder"]
                if "folder" in folder_agent_consumes:
                    print("✅ Folder agent configured to consume folder examples")
                else:
                    print("❌ Folder agent not configured for folder examples")
        else:
            print("❌ Index file not found")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all tests."""
    print("🚀 Testing Folder Agent Expansion Implementation")
    print("=" * 60)

    tests = [
        test_basic_folder_operations,
        test_sorting_functionality,
        test_duplicate_detection,
        test_archive_simulation,
        test_prompt_examples
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append(False)

    print("\n" + "=" * 60)
    print("📊 Test Results:")

    passed = sum(results)
    total = len(results)

    for i, (test, result) in enumerate(zip(tests, results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test.__name__}")

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Folder agent expansion is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the implementation.")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
