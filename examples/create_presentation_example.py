"""
Example: Creating Keynote Presentations with the Orchestrator

This example demonstrates how the LangGraph orchestrator creates
professional Keynote presentations from your documents.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import load_config, setup_logging
from src.documents import DocumentIndexer
from src.orchestrator import LangGraphOrchestrator
from src.orchestrator.state import Budget


def example_1_basic_presentation():
    """
    Example 1: Create a simple presentation from a document.
    """
    print("\n" + "=" * 80)
    print("Example 1: Basic Presentation Creation")
    print("=" * 80 + "\n")

    # Initialize
    config = load_config()
    setup_logging(config)
    indexer = DocumentIndexer(config)
    orchestrator = LangGraphOrchestrator(config, indexer)

    # Execute
    result = orchestrator.execute(
        goal="Create a Keynote presentation from the AI agents document",
        context={
            "presentation_style": "professional",
            "max_slides": 10
        },
        budget=Budget(tokens=50000, time_s=300, steps=20)
    )

    # Display result
    print(f"\n✓ Success: {result['success']}")
    print(f"Summary: {result['summary']}")

    if "key_outputs" in result:
        for key, value in result["key_outputs"].items():
            print(f"  {key}: {value}")


def example_2_technical_presentation():
    """
    Example 2: Create a technical presentation with specific requirements.
    """
    print("\n" + "=" * 80)
    print("Example 2: Technical Presentation with Requirements")
    print("=" * 80 + "\n")

    config = load_config()
    indexer = DocumentIndexer(config)
    orchestrator = LangGraphOrchestrator(config, indexer)

    result = orchestrator.execute(
        goal="Find my Tesla Autopilot document and create a technical presentation",
        context={
            "presentation_style": "technical",
            "max_slides": 15,
            "include_diagrams": True,
            "audience": "engineers",
            "focus": ["architecture", "safety", "performance"]
        },
        budget=Budget(tokens=75000, time_s=400, steps=25)
    )

    print(f"\n✓ Success: {result['success']}")
    print(f"Summary: {result['summary']}")


def example_3_multi_document_presentation():
    """
    Example 3: Create presentation from multiple documents.
    """
    print("\n" + "=" * 80)
    print("Example 3: Multi-Document Presentation")
    print("=" * 80 + "\n")

    config = load_config()
    indexer = DocumentIndexer(config)
    orchestrator = LangGraphOrchestrator(config, indexer)

    result = orchestrator.execute(
        goal="Create a presentation summarizing all guitar tabs I have",
        context={
            "presentation_style": "educational",
            "max_slides": 20,
            "include_preview_images": True,
            "organize_by": "difficulty"
        },
        budget=Budget(tokens=100000, time_s=600, steps=30)
    )

    print(f"\n✓ Success: {result['success']}")
    print(f"Summary: {result['summary']}")


def example_4_presentation_with_custom_template():
    """
    Example 4: Create presentation with custom styling.
    """
    print("\n" + "=" * 80)
    print("Example 4: Custom Styled Presentation")
    print("=" * 80 + "\n")

    config = load_config()
    indexer = DocumentIndexer(config)
    orchestrator = LangGraphOrchestrator(config, indexer)

    result = orchestrator.execute(
        goal="Create a modern, minimalist presentation about machine learning",
        context={
            "presentation_style": "modern",
            "color_scheme": "dark",
            "font_preference": "sans-serif",
            "max_slides": 12,
            "slide_structure": {
                "title_slide": True,
                "table_of_contents": True,
                "section_dividers": True,
                "conclusion_slide": True
            }
        },
        budget=Budget(tokens=60000, time_s=350, steps=22)
    )

    print(f"\n✓ Success: {result['success']}")
    print(f"Summary: {result['summary']}")


def example_5_what_the_orchestrator_does():
    """
    Example 5: Show what happens behind the scenes.
    """
    print("\n" + "=" * 80)
    print("Example 5: Behind the Scenes - What the Orchestrator Does")
    print("=" * 80 + "\n")

    print("""
When you ask to create a presentation, the orchestrator:

1. PLAN Phase:
   - Analyzes your goal
   - Determines which document(s) to use
   - Creates a multi-step plan:
     • Search for relevant documents
     • Extract content from document
     • Analyze content and identify key points (LlamaIndex worker)
     • Generate presentation structure (slides with titles/content)
     • Create Keynote presentation via AppleScript
     • Save to specified location

2. VALIDATE Phase:
   - Checks all tools exist
   - Verifies dependencies are correct
   - Ensures inputs are provided
   - Validates against budget

3. EXECUTE Phase:
   Step 1: search_documents("AI agents")
     → doc_path: /path/to/ai_agents.pdf

   Step 2: extract_section(doc_path, "all")
     → extracted_text: "..."
     → word_count: 5000

   Step 3: llamaindex_worker (analyze and structure)
     → Analyzes content using RAG
     → Creates outline with key sections
     → Generates slide titles and content

   Step 4: create_keynote(title, slides)
     → Opens Keynote via AppleScript
     → Creates new presentation
     → Adds title slide
     → Adds content slides with formatted text
     → Saves file

4. EVALUATE Phase:
   - Checks each step succeeded
   - Verifies presentation file exists
   - Validates slide count matches requirements

5. SYNTHESIZE Phase:
   - Returns summary of what was created
   - Provides file path
   - Suggests next actions (open presentation, review, etc.)

Real Example Output:
{
    "success": true,
    "summary": "Created Keynote presentation 'AI Agents Overview' with 10 slides",
    "key_outputs": {
        "presentation_path": "~/Documents/AI_Agents_Overview.key",
        "slide_count": 10,
        "source_document": "ai_agents_presentation.pdf"
    },
    "next_actions": [
        "Open the presentation in Keynote",
        "Review slide content and formatting",
        "Customize theme if needed"
    ]
}
    """)


def show_presentation_capabilities():
    """
    Show all presentation-related capabilities.
    """
    print("\n" + "=" * 80)
    print("Presentation Capabilities")
    print("=" * 80 + "\n")

    print("""
The Orchestrator can:

✓ Create Presentations From:
  - Single documents (PDF, DOCX, TXT)
  - Multiple documents (synthesized)
  - Specific sections or pages
  - Search results across document library

✓ Presentation Styles:
  - Professional (business)
  - Technical (engineering)
  - Educational (teaching)
  - Modern (minimalist)
  - Academic (research)

✓ Automatic Features:
  - Title slide generation
  - Content structuring (intro, body, conclusion)
  - Key point extraction
  - Slide layout optimization
  - Text formatting

✓ Integration with Workflow:
  - Can combine with email (create & send)
  - Can extract screenshots for slides
  - Can analyze multiple sources
  - Can use RAG for intelligent content selection

✓ Tools Used:
  - search_documents: Find source material
  - extract_section: Get document content
  - llamaindex_worker: Analyze & structure (RAG-powered)
  - create_keynote: Generate Keynote file

Example Requests:

1. "Create a presentation about machine learning from my research papers"

2. "Find guitar tabs and make a teaching slideshow"

3. "Create slides summarizing this week's meeting notes"

4. "Make a professional presentation for the Tesla Autopilot report"

5. "Create a technical overview of my Python projects with code examples"

    """)


if __name__ == "__main__":
    import sys

    print("\n" + "=" * 80)
    print("Keynote Presentation Examples")
    print("=" * 80)

    # Show capabilities first
    show_presentation_capabilities()

    # Show what happens behind the scenes
    example_5_what_the_orchestrator_does()

    # Ask which examples to run
    print("\n" + "=" * 80)
    print("Available Examples:")
    print("=" * 80)
    print("1. Basic Presentation Creation")
    print("2. Technical Presentation with Requirements")
    print("3. Multi-Document Presentation")
    print("4. Custom Styled Presentation")
    print("5. Exit")

    while True:
        choice = input("\nSelect example (1-5): ").strip()

        if choice == "1":
            example_1_basic_presentation()
        elif choice == "2":
            example_2_technical_presentation()
        elif choice == "3":
            example_3_multi_document_presentation()
        elif choice == "4":
            example_4_presentation_with_custom_template()
        elif choice == "5":
            print("\nGoodbye!")
            break
        else:
            print("Invalid choice. Please select 1-5.")

        cont = input("\nRun another example? (y/n): ").strip().lower()
        if cont != 'y':
            break

    print("\nAll examples completed!")
