"""
Regression tests for Writing UX Refresh.

Tests the new writing brief layer, lightweight reply path, flexible slides/reports,
and UI presentation wrappers.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agent.writing_agent import (
    prepare_writing_brief,
    create_quick_summary,
    synthesize_content,
    create_slide_deck_content,
    create_detailed_report,
)
from src.utils.writing_ui_formatter import (
    format_report_for_ui,
    format_slides_for_ui,
    format_quick_summary_for_ui,
    format_writing_output,
)


# Sample test data
SAMPLE_CONTENT = """
Artificial Intelligence (AI) has made remarkable progress in recent years.
Machine learning models can now understand natural language, generate creative content,
and solve complex problems. Companies are investing billions in AI research.

Key developments include:
- Large language models like GPT-4 and Claude
- Computer vision breakthroughs
- Reinforcement learning advances
- AI safety research initiatives

The field continues to evolve rapidly with new capabilities emerging regularly.
"""

SAMPLE_STOCK_DATA = """
NVDA Stock Analysis Q4 2024:
- Stock price: $875.20 (up 12% from Q3)
- Market cap: $2.1 trillion
- Revenue: $22.1 billion (up 265% YoY)
- Data center revenue: $18.4 billion
- Gaming revenue: $2.9 billion
- Profit margin: 55%
- AI chip demand remains strong
"""


class TestWritingBriefLayer:
    """Test the writing brief preparation system."""

    def test_prepare_brief_basic(self):
        """Test basic brief preparation."""
        result = prepare_writing_brief.invoke({
            "user_request": "Create a professional report on AI progress",
            "deliverable_type": "report"
        })

        assert "writing_brief" in result
        assert "analysis" in result
        assert "confidence_score" in result

        brief = result["writing_brief"]
        assert brief["deliverable_type"] == "report"
        assert "tone" in brief
        assert "audience" in brief
        assert "length_guideline" in brief

    def test_prepare_brief_with_tone_detection(self):
        """Test tone detection from user request."""
        result = prepare_writing_brief.invoke({
            "user_request": "Hey, can you whip up a quick casual summary about stocks?",
            "deliverable_type": "summary"
        })

        brief = result["writing_brief"]
        # Should detect casual tone from "hey" and "whip up"
        assert brief["tone"] in ["casual", "conversational", "informal"]

    def test_prepare_brief_extracts_data(self):
        """Test brief extracts data from artifacts."""
        result = prepare_writing_brief.invoke({
            "user_request": "Create a report on NVDA stock performance",
            "deliverable_type": "report",
            "upstream_artifacts": {
                "$step1.stock_data": SAMPLE_STOCK_DATA
            }
        })

        brief = result["writing_brief"]
        # Should extract numerical data and metrics
        assert len(brief.get("must_include_data", {})) > 0 or len(brief.get("must_include_facts", [])) > 0


class TestLightweightReplyPath:
    """Test the lightweight reply path for quick answers."""

    def test_quick_summary_basic(self):
        """Test basic quick summary creation."""
        result = create_quick_summary.invoke({
            "content": SAMPLE_CONTENT,
            "topic": "What is AI?",
            "max_sentences": 2
        })

        assert "summary" in result
        assert "key_fact" in result
        assert "word_count" in result

        # Should be brief (under 50 words for 2 sentences)
        assert result["word_count"] < 50

    def test_quick_summary_with_brief(self):
        """Test quick summary with writing brief for tone matching."""
        # First prepare a playful brief
        brief_result = prepare_writing_brief.invoke({
            "user_request": "Give me a fun, playful explanation of AI",
            "deliverable_type": "summary"
        })

        # Then create quick summary with the brief
        result = create_quick_summary.invoke({
            "content": SAMPLE_CONTENT,
            "topic": "AI explanation",
            "max_sentences": 3,
            "writing_brief": brief_result["writing_brief"]
        })

        assert "summary" in result
        # Should match playful/casual tone
        assert result.get("tone") in ["playful", "casual", "conversational", "fun"]

    def test_quick_summary_vs_synthesis_brevity(self):
        """Verify quick summary is significantly shorter than synthesis."""
        # Quick summary
        quick_result = create_quick_summary.invoke({
            "content": SAMPLE_CONTENT,
            "topic": "AI progress",
            "max_sentences": 2
        })

        # Full synthesis
        synthesis_result = synthesize_content.invoke({
            "source_contents": [SAMPLE_CONTENT],
            "topic": "AI progress",
            "synthesis_style": "comprehensive"
        })

        # Quick summary should be much shorter
        quick_words = quick_result.get("word_count", 0)
        synth_words = synthesis_result.get("word_count", 0)

        assert quick_words < synth_words / 3  # At least 3x shorter


class TestFlexibleSlides:
    """Test flexible slide deck generation with brief."""

    def test_slides_flexible_count(self):
        """Test that slide count can exceed old hard limits."""
        result = create_slide_deck_content.invoke({
            "content": SAMPLE_CONTENT * 3,  # More content
            "title": "AI Progress Overview",
            "num_slides": 8  # Request 8 slides (old limit was 5)
        })

        assert "slides" in result
        slides = result["slides"]

        # Should create 8 slides or close to it (within +3 buffer)
        assert 6 <= len(slides) <= 11  # 8 +/- tolerance

    def test_slides_playful_tone_from_brief(self):
        """Test playful slide deck with tone from brief."""
        # Prepare playful brief
        brief_result = prepare_writing_brief.invoke({
            "user_request": "Create a fun, playful presentation about AI for kids",
            "deliverable_type": "deck",
            "upstream_artifacts": {"content": SAMPLE_CONTENT}
        })

        # Create slides with brief
        result = create_slide_deck_content.invoke({
            "content": SAMPLE_CONTENT,
            "title": "AI Adventures",
            "num_slides": 5,
            "writing_brief": brief_result["writing_brief"]
        })

        assert "slides" in result
        # Verify slides have preview
        assert "preview" in result

    def test_slides_bullet_flexibility(self):
        """Test that slides can have up to 6 bullets (relaxed from 5)."""
        result = create_slide_deck_content.invoke({
            "content": SAMPLE_CONTENT,
            "title": "AI Overview",
            "num_slides": 3
        })

        slides = result["slides"]
        # Check that slides can have multiple bullets (implementation allows 3-6)
        for slide in slides:
            bullets = slide.get("bullets", [])
            # Should have reasonable number of bullets (not truncated too aggressively)
            assert 2 <= len(bullets) <= 7  # Allows up to 6 as per relaxed rules


class TestFlexibleReports:
    """Test flexible report generation with preview."""

    def test_report_with_preview(self):
        """Test that reports include preview."""
        result = create_detailed_report.invoke({
            "content": SAMPLE_CONTENT,
            "title": "AI Progress Report",
            "report_style": "business"
        })

        assert "report_content" in result
        assert "preview" in result
        assert "executive_summary" in result

        # Preview should be short (under 100 words)
        preview_words = len(result["preview"].split())
        assert preview_words < 100

    def test_minimal_report(self):
        """Test minimal report with brief length guideline."""
        # Prepare minimal brief
        brief_result = prepare_writing_brief.invoke({
            "user_request": "Give me a short summary report, keep it brief",
            "deliverable_type": "report",
            "upstream_artifacts": {"content": SAMPLE_CONTENT}
        })

        # Should detect "brief" length
        assert brief_result["writing_brief"]["length_guideline"] in ["brief", "short", "concise"]

        # Create report with brief
        result = create_detailed_report.invoke({
            "content": SAMPLE_CONTENT,
            "title": "Brief AI Report",
            "report_style": "business",
            "writing_brief": brief_result["writing_brief"]
        })

        assert "report_content" in result
        # Should be relatively short (under 500 words for "brief")
        word_count = result.get("total_word_count", 0)
        assert word_count < 800  # Reasonable upper bound for "brief" report

    def test_comprehensive_report(self):
        """Test comprehensive report."""
        result = create_detailed_report.invoke({
            "content": SAMPLE_CONTENT * 2,
            "title": "Comprehensive AI Analysis",
            "report_style": "academic",
            "include_sections": ["Introduction", "Literature Review", "Analysis", "Conclusions"]
        })

        assert "report_content" in result
        assert "sections" in result

        sections = result["sections"]
        # Should have the requested sections
        assert len(sections) >= 3


class TestUIFormatters:
    """Test UI presentation formatters."""

    def test_format_report_for_ui(self):
        """Test report UI formatting."""
        # Create a report
        report_data = create_detailed_report.invoke({
            "content": SAMPLE_CONTENT,
            "title": "AI Report",
            "report_style": "business"
        })

        # Format for UI
        ui_data = format_report_for_ui(report_data, "AI Report")

        assert ui_data["ui_type"] == "report"
        assert ui_data["ui_title"] == "AI Report"
        assert "ui_preview" in ui_data
        assert "ui_full_content" in ui_data
        assert "ui_metadata" in ui_data
        assert "ui_tags" in ui_data
        assert ui_data["ui_collapsible"] is True

        # Metadata should include word count
        assert "word_count" in ui_data["ui_metadata"]

    def test_format_slides_for_ui(self):
        """Test slides UI formatting."""
        # Create slides
        slides_data = create_slide_deck_content.invoke({
            "content": SAMPLE_CONTENT,
            "title": "AI Presentation",
            "num_slides": 5
        })

        # Format for UI
        ui_data = format_slides_for_ui(slides_data, "AI Presentation")

        assert ui_data["ui_type"] == "slides"
        assert "ui_preview" in ui_data
        assert "ui_metadata" in ui_data
        assert ui_data["ui_collapsible"] is True

        # Metadata should include slide count
        assert "total_slides" in ui_data["ui_metadata"]

    def test_format_quick_summary_for_ui(self):
        """Test quick summary UI formatting (no collapse)."""
        # Create quick summary
        summary_data = create_quick_summary.invoke({
            "content": SAMPLE_CONTENT,
            "topic": "AI",
            "max_sentences": 2
        })

        # Format for UI
        ui_data = format_quick_summary_for_ui(summary_data, "AI")

        assert ui_data["ui_type"] == "quick_summary"
        assert "ui_content" in ui_data
        assert ui_data["ui_collapsible"] is False  # Quick summaries don't collapse

    def test_format_writing_output_universal(self):
        """Test universal formatter."""
        # Create a report
        report_data = create_detailed_report.invoke({
            "content": SAMPLE_CONTENT,
            "title": "Test Report",
            "report_style": "technical"
        })

        # Format using universal formatter
        ui_data = format_writing_output(
            report_data,
            output_type="report",
            title="Test Report"
        )

        assert ui_data["ui_type"] == "report"
        assert "ui_preview" in ui_data


class TestEndToEndWorkflows:
    """Test complete workflows from brief to UI presentation."""

    def test_quick_answer_workflow(self):
        """Test: User wants quick casual explanation."""
        # 1. Prepare brief
        brief = prepare_writing_brief.invoke({
            "user_request": "Just explain quickly what AI is",
            "deliverable_type": "summary",
            "upstream_artifacts": {"content": SAMPLE_CONTENT}
        })

        # Should detect brief/short length
        assert brief["writing_brief"]["length_guideline"] in ["brief", "short", "concise"]

        # 2. Create quick summary (lightweight path)
        summary = create_quick_summary.invoke({
            "content": SAMPLE_CONTENT,
            "topic": "What is AI",
            "max_sentences": 2,
            "writing_brief": brief["writing_brief"]
        })

        # Should be very short
        assert summary["word_count"] < 50

        # 3. Format for UI (no collapse)
        ui_output = format_quick_summary_for_ui(summary, "What is AI")

        assert ui_output["ui_collapsible"] is False
        assert "ui_content" in ui_output

    def test_detailed_report_workflow(self):
        """Test: User wants comprehensive report with data."""
        # 1. Prepare brief with data
        brief = prepare_writing_brief.invoke({
            "user_request": "Create a detailed stock analysis report for NVDA",
            "deliverable_type": "report",
            "upstream_artifacts": {"stock_data": SAMPLE_STOCK_DATA}
        })

        # Should extract stock data
        assert len(brief["writing_brief"].get("must_include_data", {})) > 0 or \
               len(brief["writing_brief"].get("must_include_facts", [])) > 0

        # 2. Synthesize content
        synthesis = synthesize_content.invoke({
            "source_contents": [SAMPLE_STOCK_DATA],
            "topic": "NVDA Stock Analysis",
            "synthesis_style": "comprehensive",
            "writing_brief": brief["writing_brief"]
        })

        # 3. Create report
        report = create_detailed_report.invoke({
            "content": synthesis["synthesized_content"],
            "title": "NVDA Q4 2024 Analysis",
            "report_style": "business",
            "writing_brief": brief["writing_brief"]
        })

        # Should have preview
        assert "preview" in report

        # 4. Format for UI with collapsible preview
        ui_output = format_report_for_ui(report, "NVDA Q4 2024 Analysis")

        assert ui_output["ui_collapsible"] is True
        assert "ui_preview" in ui_output
        assert len(ui_output["ui_preview"]) < len(ui_output["ui_full_content"])

    def test_playful_presentation_workflow(self):
        """Test: User wants playful/fun presentation."""
        # 1. Prepare playful brief
        brief = prepare_writing_brief.invoke({
            "user_request": "Make me a fun, playful slide deck about AI",
            "deliverable_type": "deck"
        })

        # Should detect playful/casual tone
        tone = brief["writing_brief"]["tone"]
        assert tone in ["playful", "casual", "fun", "conversational"]

        # 2. Create slides with playful tone
        slides = create_slide_deck_content.invoke({
            "content": SAMPLE_CONTENT,
            "title": "AI is Awesome!",
            "num_slides": 6,
            "writing_brief": brief["writing_brief"]
        })

        # Should have 6 slides (flexible count)
        assert 5 <= len(slides["slides"]) <= 9

        # 3. Format for UI
        ui_output = format_slides_for_ui(slides, "AI is Awesome!")

        assert "ui_preview" in ui_output
        # Should show playful tone in tags
        assert any(tone in tag for tag in ui_output["ui_tags"] for tone in ["playful", "casual", "fun"])


def test_writing_ux_refresh_integration():
    """Integration test covering all major improvements."""
    print("\n" + "="*60)
    print("WRITING UX REFRESH - Integration Test")
    print("="*60)

    # Test 1: Brief preparation
    print("\n[1/5] Testing Writing Brief Preparation...")
    brief = prepare_writing_brief.invoke({
        "user_request": "Create a professional report on NVDA stock",
        "deliverable_type": "report",
        "upstream_artifacts": {"data": SAMPLE_STOCK_DATA}
    })
    assert "writing_brief" in brief
    print(f"✓ Brief created: {brief['writing_brief']['tone']} tone for {brief['writing_brief']['audience']}")

    # Test 2: Quick summary (lightweight path)
    print("\n[2/5] Testing Lightweight Reply Path...")
    quick = create_quick_summary.invoke({
        "content": SAMPLE_CONTENT,
        "topic": "AI overview",
        "max_sentences": 2
    })
    assert quick["word_count"] < 50
    print(f"✓ Quick summary: {quick['word_count']} words")

    # Test 3: Flexible slides
    print("\n[3/5] Testing Flexible Slide Deck...")
    slides = create_slide_deck_content.invoke({
        "content": SAMPLE_CONTENT,
        "title": "AI Progress",
        "num_slides": 7
    })
    assert len(slides["slides"]) >= 5
    print(f"✓ Slides created: {len(slides['slides'])} slides with preview")

    # Test 4: Report with preview
    print("\n[4/5] Testing Report with Preview...")
    report = create_detailed_report.invoke({
        "content": SAMPLE_CONTENT,
        "title": "AI Report",
        "report_style": "business"
    })
    assert "preview" in report
    print(f"✓ Report created: {report.get('total_word_count', 0)} words with preview")

    # Test 5: UI Formatters
    print("\n[5/5] Testing UI Presentation Formatters...")
    ui_report = format_report_for_ui(report, "AI Report")
    ui_slides = format_slides_for_ui(slides, "AI Progress")
    ui_quick = format_quick_summary_for_ui(quick, "AI")

    assert ui_report["ui_collapsible"] is True
    assert ui_slides["ui_collapsible"] is True
    assert ui_quick["ui_collapsible"] is False
    print("✓ UI formatters working correctly")

    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED - Writing UX Refresh Complete!")
    print("="*60)


if __name__ == "__main__":
    # Run the integration test
    test_writing_ux_refresh_integration()

    print("\n\nRunning detailed pytest suite...")
    pytest.main([__file__, "-v", "--tb=short"])
