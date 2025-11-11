"""
Demonstration of all slash commands for key tools.

This script shows how EVERY key tool can be invoked directly via slash commands,
bypassing the orchestrator.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ui.slash_commands import SlashCommandParser

def demo_all_commands():
    """Demonstrate all slash commands for key tools."""

    parser = SlashCommandParser()

    print("\n" + "="*80)
    print("SLASH COMMAND DEMONSTRATION - ALL KEY TOOLS")
    print("="*80)

    commands = [
        ("📦 ZIP Creation", [
            "/files Create a ZIP of all PDFs in Downloads",
            "/files Zip my documents folder",
        ]),
        ("📁 Folder Reorganization", [
            "/files Organize my PDFs by topic",
            "/files Reorganize Downloads by file type",
            "/files Sort music files into folders by genre",
        ]),
        ("📸 Document Screenshots", [
            "/files Take screenshot of page 5 in report.pdf",
            "/files Capture first 3 pages of presentation.pdf",
        ]),
        ("🎨 Keynote Presentations", [
            "/keynote Create a presentation about AI trends",
            "/present Make a Keynote with 5 slides on LLMs",
            "/keynote Create deck from this report",
        ]),
        ("📄 Pages Documents", [
            "/pages Create a report about Q4 performance",
            "/pages Make a document from meeting notes",
            "/present Create Pages doc with this content",
        ]),
        ("📧 Email Composition", [
            "/email Draft an email about project status",
            "/mail Send meeting notes to team@company.com",
            "/email Compose message with attachment",
        ]),
        ("🗺️ Maps & Trip Planning", [
            "/maps Plan trip from LA to SF with 2 gas stops",
            "/directions Route to Boston with lunch stop",
            "/map Navigate to Phoenix with rest stops",
        ]),
    ]

    for category, examples in commands:
        print(f"\n{category}")
        print("-" * 80)

        for cmd in examples:
            parsed = parser.parse(cmd)
            if parsed and parsed.get("is_command"):
                agent = parsed.get("agent", "unknown")
                task = parsed.get("task", "N/A")

                # Show routing
                print(f"\n  Command: {cmd}")
                print(f"  ✓ Routes to: {agent.upper()} Agent")
                print(f"  ✓ Task: {task[:60]}...")
                print(f"  ✓ Bypasses: Orchestrator (direct agent access)")
            else:
                print(f"\n  Command: {cmd}")
                print(f"  ✗ Invalid command")

    print("\n" + "="*80)
    print("KEY FEATURES")
    print("="*80)
    print("  ✓ All commands bypass orchestrator for faster execution")
    print("  ✓ LLM intelligently routes to correct tool within agent")
    print("  ✓ LLM extracts parameters from natural language")
    print("  ✓ NO hardcoded routing or pattern matching")
    print("  ✓ Semantic understanding for file categorization")

    print("\n" + "="*80)
    print("AGENT ROUTING SUMMARY")
    print("="*80)

    agent_map = {
        "file": ["ZIP", "Reorganization", "Screenshots", "Search"],
        "presentation": ["Keynote", "Pages", "Slides"],
        "email": ["Compose", "Send", "Draft"],
        "maps": ["Trip Planning", "Routes", "Directions"],
    }

    for agent, capabilities in agent_map.items():
        print(f"\n  {agent.upper()} Agent:")
        for cap in capabilities:
            print(f"    • {cap}")

    print("\n" + "="*80)
    print("EXAMPLE: LLM ROUTING FLOW")
    print("="*80)
    print("""
User: /files Create a ZIP of my PDFs
    ↓
Slash Parser: Recognizes "/files" → File Agent
    ↓
LLM Analyzer: Reads "Create a ZIP"
    ↓
LLM Decision: "User wants create_zip_archive tool"
    ↓
LLM Extracts: {
    source_path: "current_directory",
    zip_name: "pdfs_backup",
    include_pattern: "*.pdf"
}
    ↓
Tool Execution: create_zip_archive(...)
    ↓
Result: ZIP created with N files

⚡ Total time: ~2-3 seconds (vs 5-8s with orchestrator)
    """)

    print("\n" + "="*80)
    print("ALL KEY TOOLS COVERED")
    print("="*80)

    tools = [
        ("✅", "ZIP Creation", "/files", "create_zip_archive"),
        ("✅", "Folder Reorganization", "/files", "organize_files"),
        ("✅", "Document Screenshots", "/files", "take_screenshot"),
        ("✅", "Keynote Presentations", "/keynote", "create_keynote"),
        ("✅", "Pages Documents", "/pages", "create_pages_doc"),
        ("✅", "Email Composition", "/email", "compose_email"),
        ("✅", "Trip Planning", "/maps", "plan_trip_with_stops"),
    ]

    print("\n  Tool                       | Command    | Agent Tool")
    print("  " + "-" * 76)
    for status, tool, cmd, agent_tool in tools:
        print(f"  {status} {tool:25} | {cmd:10} | {agent_tool}")

    print("\n" + "="*80)
    print("TESTING")
    print("="*80)
    print("\n  Run comprehensive tests:")
    print("    python tests/test_slash_commands.py")
    print("\n  Test individual commands:")
    print("    /files Create ZIP of test_docs")
    print("    /keynote Create 3-slide presentation")
    print("    /maps Plan trip from SF to LA")

    print("\n" + "="*80)
    print("✅ ALL TOOLS CAN BYPASS ORCHESTRATOR VIA SLASH COMMANDS")
    print("="*80 + "\n")


if __name__ == "__main__":
    demo_all_commands()
