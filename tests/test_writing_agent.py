"""
Test script for Writing Agent functionality.

Tests all Writing Agent tools:
1. synthesize_content
2. create_slide_deck_content
3. create_detailed_report
4. create_meeting_notes
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import load_config
from src.agent.writing_agent import WritingAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_synthesize_content():
    """Test content synthesis from multiple sources."""
    print("\n" + "="*80)
    print("TEST 1: SYNTHESIZE CONTENT")
    print("="*80)

    config = load_config()
    agent = WritingAgent(config)

    # Sample sources
    source1 = """
    Artificial Intelligence has made significant progress in recent years.
    Machine learning algorithms can now perform complex tasks like image recognition,
    natural language processing, and game playing at superhuman levels.
    Deep learning, a subset of machine learning, has been particularly successful.
    """

    source2 = """
    The field of AI has seen breakthrough developments. Neural networks with billions
    of parameters can generate human-like text and images. However, concerns about
    AI safety, bias, and ethical implications have also grown. Researchers are working
    on making AI systems more interpretable and aligned with human values.
    """

    source3 = """
    AI applications are now widespread in industry. From autonomous vehicles to
    medical diagnosis systems, AI is transforming how we work and live. The economic
    impact is expected to be substantial, with some estimates suggesting AI could
    contribute trillions to global GDP in the coming decades.
    """

    result = agent.execute("synthesize_content", {
        "source_contents": [source1, source2, source3],
        "topic": "Recent Progress in Artificial Intelligence",
        "synthesis_style": "comprehensive"
    })

    if result.get("error"):
        print(f"❌ ERROR: {result.get('error_message')}")
        return False

    print(f"✅ Synthesized {result.get('source_count')} sources")
    print(f"📊 Word count: {result.get('word_count')}")
    print(f"🔑 Key points: {len(result.get('key_points', []))}")
    print(f"🎯 Themes: {result.get('themes_identified', [])}")
    print(f"\n📝 Synthesized Content Preview:")
    print(result.get('synthesized_content', '')[:300] + "...")

    return True


def test_slide_deck_content():
    """Test slide deck content creation."""
    print("\n" + "="*80)
    print("TEST 2: CREATE SLIDE DECK CONTENT")
    print("="*80)

    config = load_config()
    agent = WritingAgent(config)

    content = """
    Our Q4 marketing strategy focuses on three key areas: digital transformation,
    customer engagement, and brand awareness. We will invest heavily in social media
    advertising, particularly on platforms where our target demographic is most active.
    Personalized email campaigns will be launched to re-engage dormant customers.
    We're also planning a major rebranding initiative to modernize our image and appeal
    to younger audiences. Key performance indicators include a 25% increase in website
    traffic, 15% growth in social media followers, and 10% improvement in conversion rates.
    """

    result = agent.execute("create_slide_deck_content", {
        "content": content,
        "title": "Q4 Marketing Strategy",
        "num_slides": 3
    })

    if result.get("error"):
        print(f"❌ ERROR: {result.get('error_message')}")
        return False

    print(f"✅ Created {result.get('total_slides')} slides")
    print(f"\n📊 Slide Structure:")
    for slide in result.get('slides', []):
        print(f"\n  Slide {slide['slide_number']}: {slide['title']}")
        for bullet in slide.get('bullets', []):
            print(f"    • {bullet}")

    return True


def test_detailed_report():
    """Test detailed report creation."""
    print("\n" + "="*80)
    print("TEST 3: CREATE DETAILED REPORT")
    print("="*80)

    config = load_config()
    agent = WritingAgent(config)

    content = """
    Security audit findings: Network infrastructure has several vulnerabilities.
    Outdated firewall rules, unpatched systems, weak password policies.
    Recommendations: Update all systems, implement MFA, conduct security training,
    establish incident response plan. Critical issues must be addressed within 30 days.
    """

    result = agent.execute("create_detailed_report", {
        "content": content,
        "title": "Q3 Security Audit Report",
        "report_style": "technical",
        "include_sections": None  # Auto-generate
    })

    if result.get("error"):
        print(f"❌ ERROR: {result.get('error_message')}")
        return False

    print(f"✅ Created {result.get('report_style')} report")
    print(f"📊 Total words: {result.get('total_word_count')}")
    print(f"📋 Sections: {len(result.get('sections', []))}")
    print(f"\n🎯 Executive Summary:")
    print(result.get('executive_summary', ''))
    print(f"\n📝 Report Preview:")
    print(result.get('report_content', '')[:400] + "...")

    return True


def test_meeting_notes():
    """Test meeting notes creation."""
    print("\n" + "="*80)
    print("TEST 4: CREATE MEETING NOTES")
    print("="*80)

    config = load_config()
    agent = WritingAgent(config)

    content = """
    Meeting started at 10am. Alice presented Q1 results - revenue up 15%.
    Bob raised concerns about rising costs. Decided to freeze hiring until Q2.
    Charlie will prepare cost analysis by next Friday. Alice to reach out to
    top 10 clients for feedback. Next meeting scheduled for March 15th.
    """

    result = agent.execute("create_meeting_notes", {
        "content": content,
        "meeting_title": "Q1 Review Meeting",
        "attendees": ["Alice", "Bob", "Charlie"],
        "include_action_items": True
    })

    if result.get("error"):
        print(f"❌ ERROR: {result.get('error_message')}")
        return False

    print(f"✅ Created notes for: {result.get('meeting_title')}")
    print(f"👥 Attendees: {', '.join(result.get('attendees', []))}")
    print(f"💬 Discussion points: {len(result.get('discussion_points', []))}")
    print(f"✅ Decisions: {len(result.get('decisions', []))}")
    print(f"📋 Action items: {len(result.get('action_items', []))}")

    print(f"\n📋 Action Items:")
    for action in result.get('action_items', []):
        owner = action.get('owner', 'Unassigned')
        deadline = action.get('deadline', 'No deadline')
        print(f"  • {action['item']} ({owner} - {deadline})")

    return True


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("WRITING AGENT TEST SUITE")
    print("="*80)

    tests = [
        ("Synthesize Content", test_synthesize_content),
        ("Create Slide Deck Content", test_slide_deck_content),
        ("Create Detailed Report", test_detailed_report),
        ("Create Meeting Notes", test_meeting_notes),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            logger.error(f"Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status}: {test_name}")

    passed = sum(1 for _, success in results if success)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
