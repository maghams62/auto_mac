"""
Demo script for /folder slash command.

Shows examples of:
1. Listing folder contents
2. Organizing with normalization
3. Checking sandbox scope
4. Error handling
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.folder_agent import FolderAgent
from src.agent.folder_agent_llm import FolderAgentOrchestrator
from src.utils import load_config
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def create_demo_folder():
    """Create a demo folder with sample files."""
    demo_dir = tempfile.mkdtemp(prefix="folder_demo_")

    files = [
        ("My Vacation Photos 2023.jpg", "image"),
        ("Work Report - Q4.pdf", "document"),
        ("random FILE name.txt", "text"),
        ("IMPORTANT Document.docx", "document"),
        ("music notes - guitar.pdf", "music"),
        ("screenshot 2023-11-10.png", "image"),
        ("Meeting Notes Nov 10.txt", "text")
    ]

    for filename, category in files:
        with open(os.path.join(demo_dir, filename), 'w') as f:
            f.write(f"Demo content for {filename}\nCategory: {category}")

    # Create a subfolder
    subfolder = os.path.join(demo_dir, "Old Files 2022")
    os.makedirs(subfolder)
    with open(os.path.join(subfolder, "archived item.txt"), 'w') as f:
        f.write("Archived content")

    return demo_dir


def demo_list():
    """Demo: List folder contents."""
    print("\n" + "="*80)
    print("DEMO 1: List Folder Contents")
    print("="*80)
    print("Command: /folder list")
    print()

    demo_dir = create_demo_folder()

    try:
        config = {
            'documents': {
                'folders': [demo_dir]
            }
        }
        agent = FolderAgent(config)

        # Execute list
        result = agent.execute('folder_list', {'folder_path': None})

        # Display results
        print(f"🔒 Folder scope: {Path(demo_dir).name} (absolute: {demo_dir})")
        print()
        print(f"📁 Contents: {result['total_count']} items")
        print()
        print("NAME" + " " * 28 + "TYPE    SIZE")
        print("─" * 60)

        for item in result['items']:
            name = item['name'][:32].ljust(32)
            item_type = item['type'].ljust(7)

            if item['type'] == 'file':
                size = f"{item.get('size', 0)} B"
            else:
                size = "-"

            print(f"{name} {item_type} {size}")

        print("\n✅ Folder listing complete")

    finally:
        shutil.rmtree(demo_dir)


def demo_organize():
    """Demo: Organize folder with normalization."""
    print("\n" + "="*80)
    print("DEMO 2: Organize Folder (Normalization)")
    print("="*80)
    print("Command: /folder organize alpha")
    print()

    demo_dir = create_demo_folder()

    try:
        config = {
            'documents': {
                'folders': [demo_dir]
            }
        }
        agent = FolderAgent(config)

        # Step 1: Show current state
        print("📁 Current State:")
        list_result = agent.execute('folder_list', {'folder_path': None})
        for item in list_result['items'][:5]:
            print(f"  - {item['name']}")
        print()

        # Step 2: Generate plan
        print("📋 Generating normalization plan...")
        plan_result = agent.execute('folder_plan_alpha', {'folder_path': None})

        print()
        print(f"Plan: {plan_result['changes_count']} changes needed")
        print()
        print("CURRENT NAME" + " " * 20 + "→  PROPOSED NAME")
        print("─" * 70)

        for item in plan_result['plan']:
            if item.get('needs_change'):
                current = item['current_name'][:30].ljust(30)
                proposed = item['proposed_name'][:30]
                print(f"{current} →  {proposed}")

        print()
        print("⚠️ Confirmation required to proceed")
        print()

        # Step 3: Dry-run (simulate user confirmation)
        print("User confirmed. Running dry-run validation...")
        apply_result = agent.execute('folder_apply', {
            'plan': plan_result['plan'],
            'folder_path': None,
            'dry_run': True
        })

        print(f"✓ Dry-run validated {len(apply_result['applied'])} changes")
        print()

        # Step 4: Actual execution (simulate user confirmation)
        print("User confirmed final execution. Applying changes...")
        apply_result = agent.execute('folder_apply', {
            'plan': plan_result['plan'],
            'folder_path': None,
            'dry_run': False
        })

        print(f"✅ Successfully renamed {len(apply_result['applied'])} items")
        print()

        # Step 5: Show final state
        print("📁 Final State:")
        list_result = agent.execute('folder_list', {'folder_path': None})
        for item in list_result['items'][:5]:
            print(f"  - {item['name']}")

    finally:
        shutil.rmtree(demo_dir)


def demo_scope_check():
    """Demo: Check sandbox scope."""
    print("\n" + "="*80)
    print("DEMO 3: Check Sandbox Scope")
    print("="*80)
    print("Command: /folder check scope")
    print()

    demo_dir = create_demo_folder()

    try:
        config = {
            'documents': {
                'folders': [demo_dir]
            }
        }
        agent = FolderAgent(config)

        # Check valid path
        print("Checking sandbox path...")
        result = agent.execute('folder_check_sandbox', {'path': demo_dir})

        if result['is_safe']:
            print(f"✅ {result['message']}")
            print(f"   Resolved: {result['resolved_path']}")
            print(f"   Allowed:  {result['allowed_folder']}")
        print()

        # Check invalid path
        print("Checking path outside sandbox (/tmp)...")
        result = agent.execute('folder_check_sandbox', {'path': '/tmp'})

        if not result['is_safe']:
            print(f"🚫 {result['message']}")
            print(f"   Attempted: /tmp")
            print(f"   Allowed:   {result['allowed_folder']}")

        print()
        print("🔒 All operations are sandboxed for security")

    finally:
        shutil.rmtree(demo_dir)


def demo_error_handling():
    """Demo: Error handling with conflicts."""
    print("\n" + "="*80)
    print("DEMO 4: Error Handling (Conflicts)")
    print("="*80)
    print()

    demo_dir = tempfile.mkdtemp(prefix="folder_demo_")

    try:
        # Create files that will conflict
        with open(os.path.join(demo_dir, "File One.txt"), 'w') as f:
            f.write("Original")
        with open(os.path.join(demo_dir, "file_one.txt"), 'w') as f:
            f.write("Already normalized")

        config = {
            'documents': {
                'folders': [demo_dir]
            }
        }
        agent = FolderAgent(config)

        print("Files with naming conflict:")
        list_result = agent.execute('folder_list', {'folder_path': None})
        for item in list_result['items']:
            print(f"  - {item['name']}")
        print()

        # Try to organize
        print("Attempting to normalize...")
        plan_result = agent.execute('folder_plan_alpha', {'folder_path': None})
        apply_result = agent.execute('folder_apply', {
            'plan': plan_result['plan'],
            'folder_path': None,
            'dry_run': False
        })

        if apply_result['errors']:
            print("⚠️ Conflicts detected:")
            for error in apply_result['errors']:
                print(f"  - {error['current_name']}: {error['error']}")
            print()

        print("✓ Gracefully handled conflicts")
        print("  Options: Skip, rename with suffix, manual resolution")

    finally:
        shutil.rmtree(demo_dir)


def run_all_demos():
    """Run all demos."""
    print("\n" + "="*80)
    print("FOLDER AGENT DEMOS")
    print("="*80)
    print()
    print("These demos show the /folder command capabilities:")
    print("  1. Listing folder contents")
    print("  2. Organizing with normalization (LLM-driven)")
    print("  3. Checking sandbox scope")
    print("  4. Error handling")
    print()
    input("Press Enter to start demos...")

    demo_list()
    input("\nPress Enter for next demo...")

    demo_organize()
    input("\nPress Enter for next demo...")

    demo_scope_check()
    input("\nPress Enter for next demo...")

    demo_error_handling()

    print("\n" + "="*80)
    print("DEMOS COMPLETE")
    print("="*80)
    print()
    print("Try these commands in the UI:")
    print("  /folder list")
    print("  /folder organize alpha")
    print("  /organize")
    print("  /folder check scope")
    print()


if __name__ == "__main__":
    run_all_demos()
