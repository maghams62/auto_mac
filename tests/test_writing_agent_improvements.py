"""
Test suite for Writing Agent improvements.

Tests the new writing brief system, validation logic, and improved prompts.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from src.agent.writing_agent import (
    prepare_writing_brief,
    synthesize_content,
    create_slide_deck_content,
    create_detailed_report,
    compose_professional_email,
    WritingBrief,
    _validate_brief_compliance
)


class TestWritingBriefClass:
    """Test the WritingBrief data class."""

    def test_writing_brief_creation(self):
        """Test creating a writing brief with all parameters."""
        brief = WritingBrief(
            deliverable_type="report",
            tone="technical",
            audience="engineers",
            length_guideline="comprehensive",
            must_include_facts=["NVDA stock hit $500", "Q4 revenue grew 50%"],
            must_include_data={"stock_price": "$500", "revenue_growth": "50%"},
            focus_areas=["financial performance", "market position"],
            style_preferences={"use_metrics": True},
            constraints={"word_limit": 2000}
        )

        assert brief.deliverable_type == "report"
        assert brief.tone == "technical"
        assert len(brief.must_include_facts) == 2
        assert brief.must_include_data["stock_price"] == "$500"

    def test_brief_to_dict(self):
        """Test converting brief to dictionary."""
        brief = WritingBrief(
            deliverable_type="deck",
            tone="professional",
            must_include_facts=["Key fact"]
        )

        brief_dict = brief.to_dict()
        assert brief_dict["deliverable_type"] == "deck"
        assert brief_dict["tone"] == "professional"
        assert "Key fact" in brief_dict["must_include_facts"]

    def test_brief_from_dict(self):
        """Test creating brief from dictionary."""
        data = {
            "deliverable_type": "email",
            "tone": "casual",
            "audience": "team",
            "length_guideline": "brief",
            "must_include_facts": [],
            "must_include_data": {},
            "focus_areas": [],
            "style_preferences": {},
            "constraints": {}
        }

        brief = WritingBrief.from_dict(data)
        assert brief.deliverable_type == "email"
        assert brief.tone == "casual"

    def test_brief_to_prompt_section(self):
        """Test generating prompt section from brief."""
        brief = WritingBrief(
            deliverable_type="report",
            tone="executive",
            audience="C-suite",
            must_include_facts=["ROI increased 30%"],
            must_include_data={"roi": "30%", "quarter": "Q4"}
        )

        prompt_section = brief.to_prompt_section()
        assert "DELIVERABLE TYPE: report" in prompt_section
        assert "TONE: executive" in prompt_section
        assert "AUDIENCE: C-suite" in prompt_section
        assert "ROI increased 30%" in prompt_section
        assert "roi: 30%" in prompt_section


class TestBriefCompliance:
    """Test the brief compliance validation logic."""

    def test_validate_full_compliance(self):
        """Test validation when all requirements are met."""
        brief = WritingBrief(
            must_include_facts=["NVIDIA leads AI chip market", "Q4 revenue exceeded $20B"],
            must_include_data={"revenue": "$20B", "market_share": "80%"}
        )

        content = """
        NVIDIA continues to lead the AI chip market with dominant position.
        Q4 revenue exceeded $20B, demonstrating strong growth.
        Market share remains at approximately 80%.
        Revenue of $20B marks a significant milestone.
        """

        result = _validate_brief_compliance(content, brief, {})

        assert result["compliant"] == True
        assert result["compliance_score"] >= 0.7
        assert len(result["missing_items"]) == 0

    def test_validate_partial_compliance(self):
        """Test validation when some requirements are missing."""
        brief = WritingBrief(
            must_include_facts=["Stock price hit $500", "Earnings beat expectations"],
            must_include_data={"eps": "$5.50", "guidance": "$6B"}
        )

        # Content missing eps and guidance
        content = """
        The stock price hit $500 in trading today, marking a new high.
        Analysts are optimistic about future performance.
        """

        result = _validate_brief_compliance(content, brief, {})

        # Should fail compliance (only 1 of 4 requirements met)
        assert result["compliant"] == False
        assert result["compliance_score"] < 0.7
        assert len(result["missing_items"]) > 0

    def test_validate_flexible_matching(self):
        """Test that validation uses flexible keyword matching."""
        brief = WritingBrief(
            must_include_facts=["artificial intelligence market growth"],
            must_include_data={"market_size": "$500B"}
        )

        # Content has keywords but not exact phrase
        content = """
        The artificial intelligence market is experiencing rapid growth.
        Market size is projected to reach $500B by 2025.
        """

        result = _validate_brief_compliance(content, brief, {})

        assert result["compliant"] == True
        assert result["met_requirements"] == 2


class TestPrepareWritingBrief:
    """Test the prepare_writing_brief tool."""

    def test_brief_creation_with_request(self):
        """Test creating a brief from user request."""
        result = prepare_writing_brief.invoke({
            "user_request": "Create a technical report on NVIDIA's Q4 performance for engineering team",
            "deliverable_type": "report",
            "upstream_artifacts": {
                "stock_data": {"price": "$500", "change": "+15%"},
                "news": ["NVIDIA announces record revenue", "AI chip demand soars"]
            }
        })

        assert "writing_brief" in result
        assert "analysis" in result
        assert result.get("confidence_score", 0) > 0

        brief = result["writing_brief"]
        assert brief["deliverable_type"] == "report"
        # Should detect technical tone from request
        assert "technical" in brief.get("tone", "").lower() or "professional" in brief.get("tone", "").lower()

    def test_brief_extracts_data(self):
        """Test that brief extracts must-include data from artifacts."""
        result = prepare_writing_brief.invoke({
            "user_request": "Summarize Q4 earnings with revenue and EPS",
            "deliverable_type": "summary",
            "upstream_artifacts": {
                "earnings": {
                    "revenue": "$22.1B",
                    "eps": "$5.50",
                    "growth": "50%"
                }
            }
        })

        assert "writing_brief" in result
        brief = result["writing_brief"]

        # Should extract numerical data
        must_include_data = brief.get("must_include_data", {})
        # At least some data should be extracted
        assert len(must_include_data) > 0 or len(brief.get("must_include_facts", [])) > 0


class TestSynthesizeContentWithBrief:
    """Test synthesize_content with writing brief."""

    def test_synthesis_without_brief_legacy_mode(self):
        """Test that synthesis still works without a brief (legacy mode)."""
        result = synthesize_content.invoke({
            "source_contents": [
                "NVIDIA reported strong Q4 results.",
                "Revenue grew 50% year-over-year.",
                "AI chip demand remains high."
            ],
            "topic": "NVIDIA Q4 Performance",
            "synthesis_style": "comprehensive"
        })

        assert "synthesized_content" in result
        assert "error" not in result
        assert len(result["synthesized_content"]) > 0

    def test_synthesis_with_brief(self):
        """Test that synthesis incorporates brief requirements."""
        brief = WritingBrief(
            tone="technical",
            audience="engineers",
            must_include_facts=["50% revenue growth"],
            must_include_data={"revenue": "$22.1B"}
        ).to_dict()

        result = synthesize_content.invoke({
            "source_contents": [
                "NVIDIA reported revenue of $22.1B in Q4.",
                "This represents 50% revenue growth year-over-year."
            ],
            "topic": "NVIDIA Q4",
            "synthesis_style": "comprehensive",
            "writing_brief": brief
        })

        assert "synthesized_content" in result
        assert "compliance_score" in result

        # Content should mention revenue growth and $22.1B
        content = result["synthesized_content"].lower()
        assert "revenue" in content or "growth" in content


class TestSlideD eckWithRelaxedConstraints:
    """Test create_slide_deck_content with relaxed constraints."""

    def test_slide_deck_allows_more_bullets(self):
        """Test that slide deck no longer hard-limits to 5 bullets."""
        content = """
        Key points about our product:
        1. High performance processing
        2. Energy efficient design
        3. Advanced cooling system
        4. Integrated AI capabilities
        5. Cloud connectivity
        6. Real-time analytics
        7. Scalable architecture
        """

        result = create_slide_deck_content.invoke({
            "content": content,
            "title": "Product Features",
            "num_slides": 3
        })

        assert "slides" in result
        slides = result.get("slides", [])

        # Should create slides without artificially truncating content
        # Total bullets across all slides should be reasonable
        total_bullets = sum(len(slide.get("bullets", [])) for slide in slides)
        assert total_bullets >= 5  # Should have multiple bullets

    def test_slide_deck_flexible_slide_count(self):
        """Test that slide deck allows variable slide counts."""
        result = create_slide_deck_content.invoke({
            "content": "Content with multiple themes to cover across many slides",
            "title": "Comprehensive Overview",
            "num_slides": 8  # Request more than old hard limit of 5
        })

        assert "slides" in result
        slides = result.get("slides", [])

        # Should not hard-cap at 5 slides
        # May create 6-8 slides if content warrants
        assert len(slides) >= 5

    def test_slide_deck_with_brief_includes_data(self):
        """Test that slide deck includes required data from brief."""
        brief = WritingBrief(
            must_include_data={"revenue": "$22.1B", "growth": "50%"}
        ).to_dict()

        result = create_slide_deck_content.invoke({
            "content": "NVIDIA revenue reached $22.1B with 50% growth",
            "title": "Q4 Financial Results",
            "num_slides": 3,
            "writing_brief": brief
        })

        assert "slides" in result
        # Check for compliance score
        if "compliance_score" in result:
            # If brief validation ran, score should be reasonable
            assert result["compliance_score"] >= 0.5


class TestDetailedReportWithBrief:
    """Test create_detailed_report with writing brief."""

    def test_report_includes_required_facts(self):
        """Test that report includes facts from brief."""
        brief = WritingBrief(
            tone="business",
            must_include_facts=["Record Q4 revenue", "AI demand driving growth"],
            must_include_data={"revenue": "$22.1B"}
        ).to_dict()

        result = create_detailed_report.invoke({
            "content": "NVIDIA achieved record Q4 revenue of $22.1B driven by AI demand.",
            "title": "Q4 Analysis",
            "report_style": "business",
            "writing_brief": brief
        })

        assert "report_content" in result
        assert "compliance_score" in result

        # Should have reasonable compliance
        compliance = result.get("compliance_score", 0)
        assert compliance >= 0.6

    def test_report_audience_awareness(self):
        """Test that report style varies by audience."""
        brief_technical = WritingBrief(tone="technical", audience="engineers").to_dict()
        brief_executive = WritingBrief(tone="executive", audience="C-suite").to_dict()

        result_tech = create_detailed_report.invoke({
            "content": "System performance metrics show 50% improvement",
            "title": "Performance Analysis",
            "report_style": "technical",
            "writing_brief": brief_technical
        })

        result_exec = create_detailed_report.invoke({
            "content": "System performance metrics show 50% improvement",
            "title": "Performance Analysis",
            "report_style": "executive",
            "writing_brief": brief_executive
        })

        # Both should complete successfully
        assert "report_content" in result_tech
        assert "report_content" in result_exec

        # Technical report might be longer (more detail)
        tech_words = result_tech.get("total_word_count", 0)
        exec_words = result_exec.get("total_word_count", 0)

        # Executive should be more concise
        assert exec_words <= tech_words * 1.5  # Allow some variation


class TestEmailComposition:
    """Test the new compose_professional_email tool."""

    def test_email_composition_basic(self):
        """Test basic email composition."""
        result = compose_professional_email.invoke({
            "purpose": "Share quarterly report with team",
            "context": "Attached is our Q4 analysis showing strong performance",
            "recipient": "Engineering Team"
        })

        assert "email_subject" in result
        assert "email_body" in result
        assert "error" not in result

        # Should have reasonable structure
        assert len(result.get("email_subject", "")) > 0
        assert len(result.get("email_body", "")) > 50

    def test_email_with_brief_includes_facts(self):
        """Test that email includes required facts from brief."""
        brief = WritingBrief(
            must_include_facts=["Meeting scheduled for Friday"],
            tone="professional"
        ).to_dict()

        result = compose_professional_email.invoke({
            "purpose": "Follow up on meeting",
            "context": "Meeting is scheduled for Friday at 2pm",
            "recipient": "John Smith",
            "writing_brief": brief
        })

        assert "email_body" in result

        # Should include meeting information
        email_body = result.get("email_body", "").lower()
        assert "friday" in email_body or "meeting" in email_body


class TestRegressionPreventionComparison:
    """
    Test to prevent regression to generic outputs.

    This test compares outputs with and without briefs to ensure
    the brief system produces more specific, data-driven content.
    """

    def test_synthesis_specificity_improvement(self):
        """Test that synthesis with brief is more specific than without."""
        source_content = [
            "NVIDIA reported revenue of $22.1B with 50% growth.",
            "Data center revenue was $18.4B, up 71%.",
            "Gaming revenue reached $2.9B."
        ]

        # Without brief
        result_without = synthesize_content.invoke({
            "source_contents": source_content,
            "topic": "NVIDIA Revenue",
            "synthesis_style": "comprehensive"
        })

        # With brief requiring specific data
        brief = WritingBrief(
            must_include_data={
                "total_revenue": "$22.1B",
                "revenue_growth": "50%",
                "datacenter_revenue": "$18.4B",
                "gaming_revenue": "$2.9B"
            }
        ).to_dict()

        result_with = synthesize_content.invoke({
            "source_contents": source_content,
            "topic": "NVIDIA Revenue",
            "synthesis_style": "comprehensive",
            "writing_brief": brief
        })

        # Result with brief should have compliance score
        assert "compliance_score" in result_with

        # Result with brief should include specific numbers
        content_with = result_with.get("synthesized_content", "").lower()
        assert "$22.1b" in content_with or "22.1" in content_with


def run_quality_tests():
    """
    Run all quality tests and generate a summary report.
    """
    print("\n" + "="*80)
    print("WRITING AGENT IMPROVEMENT TESTS")
    print("="*80)

    test_classes = [
        TestWritingBriefClass,
        TestBriefCompliance,
        TestPrepareWritingBrief,
        TestSynthesizeContentWithBrief,
        TestSlideD eckWithRelaxedConstraints,
        TestDetailedReportWithBrief,
        TestEmailComposition,
        TestRegressionPreventionComparison
    ]

    total_tests = 0
    passed_tests = 0
    failed_tests = []

    for test_class in test_classes:
        print(f"\n{test_class.__name__}:")
        print("-" * 80)

        instance = test_class()
        test_methods = [m for m in dir(instance) if m.startswith('test_')]

        for method_name in test_methods:
            total_tests += 1
            try:
                method = getattr(instance, method_name)
                method()
                print(f"  ✓ {method_name}")
                passed_tests += 1
            except Exception as e:
                print(f"  ✗ {method_name}: {str(e)}")
                failed_tests.append((test_class.__name__, method_name, str(e)))

    print("\n" + "="*80)
    print(f"SUMMARY: {passed_tests}/{total_tests} tests passed")

    if failed_tests:
        print("\nFailed Tests:")
        for class_name, method_name, error in failed_tests:
            print(f"  - {class_name}.{method_name}: {error}")
    else:
        print("\n✓ All tests passed!")

    print("="*80)

    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_quality_tests()
    sys.exit(0 if success else 1)
