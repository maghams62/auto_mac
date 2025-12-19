"""
Writing UI Formatter - Format writing agent outputs for clean UI presentation.

This module provides utilities to wrap writing agent outputs with collapsible
previews and detail cards for better chat interface presentation.
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def format_report_for_ui(
    report_data: Dict[str, Any],
    title: str,
    include_metadata: bool = True
) -> Dict[str, Any]:
    """
    Format a report for UI presentation with collapsible preview.

    Args:
        report_data: The report data from create_detailed_report
        title: Report title
        include_metadata: Whether to include metadata (word count, sections, etc.)

    Returns:
        Dictionary with ui_preview, ui_full_content, ui_metadata, and ui_tags
    """
    preview = report_data.get("preview", "")
    if not preview and report_data.get("executive_summary"):
        # Use first 2 sentences from executive summary
        exec_summary = report_data["executive_summary"]
        sentences = exec_summary.split(". ")
        preview = ". ".join(sentences[:2]) + "." if len(sentences) > 1 else exec_summary[:200]

    full_content = report_data.get("report_content", "")

    # Create metadata
    metadata = {}
    if include_metadata:
        metadata = {
            "word_count": report_data.get("total_word_count", 0),
            "sections": len(report_data.get("sections", [])),
            "style": report_data.get("report_style", "business"),
        }
        if report_data.get("compliance_score"):
            metadata["compliance_score"] = report_data["compliance_score"]

    # Create tags (tone, audience indicators)
    tags = []
    if report_data.get("report_style"):
        tags.append(report_data["report_style"])

    # Extract tone/audience from brief if available
    brief_data = report_data.get("writing_brief")
    if brief_data:
        if isinstance(brief_data, dict):
            if brief_data.get("tone"):
                tags.append(brief_data["tone"])
            if brief_data.get("audience"):
                tags.append(f"for {brief_data['audience']}")

    return {
        "ui_type": "report",
        "ui_title": title,
        "ui_preview": preview,
        "ui_full_content": full_content,
        "ui_metadata": metadata,
        "ui_tags": tags,
        "ui_collapsible": True,
        "raw_data": report_data
    }


def format_slides_for_ui(
    slides_data: Dict[str, Any],
    title: str,
    include_metadata: bool = True
) -> Dict[str, Any]:
    """
    Format slide deck for UI presentation with collapsible preview.

    Args:
        slides_data: The slides data from create_slide_deck_content
        title: Presentation title
        include_metadata: Whether to include metadata

    Returns:
        Dictionary with ui_preview, ui_full_content, ui_metadata, and ui_tags
    """
    slides = slides_data.get("slides", [])

    # Create preview (first slide)
    preview = slides_data.get("preview", "")
    if not preview and slides:
        first_slide = slides[0]
        bullets_preview = first_slide.get("bullets", [])[:2]  # First 2 bullets
        preview = f"{first_slide.get('title', '')}\n• " + "\n• ".join(bullets_preview)

    # Create full content preview
    full_content = slides_data.get("formatted_content", "")

    # Create metadata
    metadata = {}
    if include_metadata:
        total_bullets = sum(len(s.get("bullets", [])) for s in slides)
        metadata = {
            "total_slides": len(slides),
            "total_bullets": total_bullets,
        }
        if slides_data.get("compliance_score"):
            metadata["compliance_score"] = slides_data["compliance_score"]

    # Create tags
    tags = ["presentation", f"{len(slides)} slides"]

    brief_data = slides_data.get("writing_brief")
    if brief_data:
        if isinstance(brief_data, dict):
            if brief_data.get("tone"):
                tags.append(brief_data["tone"])

    return {
        "ui_type": "slides",
        "ui_title": title,
        "ui_preview": preview,
        "ui_full_content": full_content,
        "ui_metadata": metadata,
        "ui_tags": tags,
        "ui_collapsible": True,
        "raw_data": slides_data
    }


def format_synthesis_for_ui(
    synthesis_data: Dict[str, Any],
    topic: str,
    include_metadata: bool = True
) -> Dict[str, Any]:
    """
    Format synthesized content for UI presentation.

    Args:
        synthesis_data: The synthesis data from synthesize_content
        topic: Topic/title
        include_metadata: Whether to include metadata

    Returns:
        Dictionary with ui_preview, ui_full_content, ui_metadata, and ui_tags
    """
    content = synthesis_data.get("synthesized_content", "")

    # Create preview (first paragraph or 2 sentences)
    sentences = content.split(". ")
    preview = ". ".join(sentences[:2]) + "." if len(sentences) > 1 else content[:200]

    # Create metadata
    metadata = {}
    if include_metadata:
        metadata = {
            "word_count": synthesis_data.get("word_count", 0),
            "sources_used": synthesis_data.get("source_count", 0),
            "themes": len(synthesis_data.get("themes_identified", [])),
        }
        if synthesis_data.get("compliance_score"):
            metadata["compliance_score"] = synthesis_data["compliance_score"]

    # Create tags
    tags = ["synthesis"]
    if synthesis_data.get("source_count"):
        tags.append(f"{synthesis_data['source_count']} sources")

    return {
        "ui_type": "synthesis",
        "ui_title": topic,
        "ui_preview": preview,
        "ui_full_content": content,
        "ui_metadata": metadata,
        "ui_tags": tags,
        "ui_collapsible": True,
        "raw_data": synthesis_data
    }


def format_quick_summary_for_ui(
    summary_data: Dict[str, Any],
    topic: str
) -> Dict[str, Any]:
    """
    Format quick summary for UI presentation (no collapsing - it's already short).

    Args:
        summary_data: The summary data from create_quick_summary
        topic: Topic

    Returns:
        Dictionary with ui_content and ui_tags
    """
    summary = summary_data.get("summary", "")

    # Quick summaries are already short, no need to collapse
    tags = [summary_data.get("tone", "conversational")]

    return {
        "ui_type": "quick_summary",
        "ui_title": topic,
        "ui_content": summary,
        "ui_tags": tags,
        "ui_collapsible": False,  # Already short, no collapse needed
        "raw_data": summary_data
    }


def format_email_for_ui(
    email_data: Dict[str, Any],
    include_metadata: bool = True
) -> Dict[str, Any]:
    """
    Format email for UI presentation with collapsible preview.

    Args:
        email_data: The email data from compose_professional_email
        include_metadata: Whether to include metadata

    Returns:
        Dictionary with ui_preview, ui_full_content, ui_metadata, and ui_tags
    """
    subject = email_data.get("email_subject", "")
    body = email_data.get("email_body", "")

    # Preview is subject + first 2 sentences of body
    body_sentences = body.split(". ")
    preview = f"Subject: {subject}\n\n" + ". ".join(body_sentences[:2]) + "..."

    # Create metadata
    metadata = {}
    if include_metadata:
        metadata = {
            "word_count": email_data.get("word_count", 0),
            "tone": email_data.get("tone", "professional"),
            "recipient": email_data.get("recipient", ""),
        }

    # Create tags
    tags = ["email", email_data.get("tone", "professional")]

    return {
        "ui_type": "email",
        "ui_title": subject,
        "ui_preview": preview,
        "ui_full_content": f"Subject: {subject}\n\n{body}",
        "ui_metadata": metadata,
        "ui_tags": tags,
        "ui_collapsible": True,
        "raw_data": email_data
    }


def format_writing_output(
    writing_data: Dict[str, Any],
    output_type: str,
    title: Optional[str] = None,
    include_metadata: bool = True
) -> Dict[str, Any]:
    """
    Universal formatter for any writing agent output.

    Args:
        writing_data: Output from any writing agent tool
        output_type: Type of output (report, slides, synthesis, quick_summary, email)
        title: Optional title override
        include_metadata: Whether to include metadata

    Returns:
        Formatted UI dictionary
    """
    formatters = {
        "report": lambda: format_report_for_ui(
            writing_data,
            title or writing_data.get("title", "Report"),
            include_metadata
        ),
        "slides": lambda: format_slides_for_ui(
            writing_data,
            title or writing_data.get("title", "Presentation"),
            include_metadata
        ),
        "synthesis": lambda: format_synthesis_for_ui(
            writing_data,
            title or "Synthesis",
            include_metadata
        ),
        "quick_summary": lambda: format_quick_summary_for_ui(
            writing_data,
            title or "Summary"
        ),
        "email": lambda: format_email_for_ui(
            writing_data,
            include_metadata
        ),
    }

    formatter = formatters.get(output_type)
    if formatter:
        return formatter()
    else:
        logger.warning(f"[WRITING UI] Unknown output_type: {output_type}")
        # Fallback: return raw data
        return {
            "ui_type": "unknown",
            "ui_title": title or "Output",
            "ui_content": str(writing_data),
            "ui_tags": [],
            "ui_collapsible": False,
            "raw_data": writing_data
        }
