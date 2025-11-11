"""
Writing Agent - Handles all content synthesis and writing operations.

This agent is responsible for:
- Synthesizing information from multiple sources
- Creating concise bullet-point summaries for slide decks
- Generating detailed reports and long-form content
- Note-taking and content assembly
- Adaptive writing styles (academic, business, casual, technical)

Acts as a mini-orchestrator for writing-related operations.
"""

from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import logging

logger = logging.getLogger(__name__)


@tool
def synthesize_content(
    source_contents: List[str],
    topic: str,
    synthesis_style: str = "comprehensive"
) -> Dict[str, Any]:
    """
    Synthesize information from multiple sources into cohesive content.

    WRITING AGENT - LEVEL 1: Content Synthesis
    Use this to combine and analyze information from different sources.

    This tool uses LLM to:
    - Identify key themes and patterns across sources
    - Remove redundancy and contradictions
    - Create a unified narrative
    - Preserve important details and citations

    Args:
        source_contents: List of text contents to synthesize (from documents, web pages, etc.)
        topic: The main topic or focus for synthesis
        synthesis_style: How to synthesize the content:
            - "comprehensive": Include all important details (for reports)
            - "concise": Focus on key points only (for summaries)
            - "comparative": Highlight differences and similarities
            - "chronological": Organize by timeline/sequence

    Returns:
        Dictionary with synthesized_content, key_points, sources_used, and word_count

    Example:
        synthesize_content(
            source_contents=["$step1.extracted_text", "$step2.content"],
            topic="AI Safety Research",
            synthesis_style="comprehensive"
        )
    """
    logger.info(f"[WRITING AGENT] Tool: synthesize_content(topic='{topic}', style='{synthesis_style}')")

    try:
        from ..utils import load_config

        config = load_config()
        openai_config = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=0.3,  # Slightly creative for better synthesis
            api_key=openai_config.get("api_key")
        )

        # Flatten list if it contains nested lists (from context variables)
        flat_contents = []
        for item in source_contents:
            if isinstance(item, list):
                flat_contents.extend(item)
            else:
                flat_contents.append(item)

        if not flat_contents or all(not content.strip() for content in flat_contents):
            return {
                "error": True,
                "error_type": "NoContentError",
                "error_message": "No content provided for synthesis",
                "retry_possible": False
            }

        # Build synthesis prompt based on style
        style_instructions = {
            "comprehensive": "Create a comprehensive synthesis that includes all important details, findings, and insights. Maintain depth and nuance.",
            "concise": "Extract and synthesize only the most critical points. Be brief and focused.",
            "comparative": "Compare and contrast information across sources. Highlight agreements, disagreements, and unique perspectives.",
            "chronological": "Organize information in chronological or sequential order. Show progression and development."
        }

        instruction = style_instructions.get(synthesis_style, style_instructions["comprehensive"])

        # Create prompt
        sources_text = "\n\n---SOURCE SEPARATOR---\n\n".join([
            f"SOURCE {i+1}:\n{content[:5000]}"  # Limit each source to 5000 chars
            for i, content in enumerate(flat_contents) if content.strip()
        ])

        synthesis_prompt = f"""You are an expert content synthesizer. Your task is to synthesize information from multiple sources into cohesive, well-structured content.

TOPIC: {topic}

SYNTHESIS STYLE: {synthesis_style}
{instruction}

SOURCES TO SYNTHESIZE:
{sources_text}

INSTRUCTIONS:
1. Read all sources carefully
2. Identify key themes, facts, and insights
3. Remove redundancy while preserving unique information
4. Create a cohesive narrative that flows naturally
5. Preserve important details and nuances
6. If sources conflict, note the different perspectives

OUTPUT FORMAT:
Provide a JSON response with:
{{
    "synthesized_content": "The main synthesized content as a cohesive narrative",
    "key_points": ["bullet point 1", "bullet point 2", ...],
    "themes_identified": ["theme 1", "theme 2", ...],
    "source_count": number_of_sources_used
}}

Focus on creating valuable, coherent content that serves the specified synthesis style.
"""

        messages = [
            SystemMessage(content="You are an expert content synthesizer."),
            HumanMessage(content=synthesis_prompt)
        ]

        response = llm.invoke(messages)
        response_text = response.content

        # Parse JSON response
        import json
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            # Fallback if no JSON found
            return {
                "synthesized_content": response_text,
                "key_points": [],
                "themes_identified": [],
                "source_count": len(flat_contents),
                "word_count": len(response_text.split()),
                "message": "Content synthesized successfully"
            }

        json_str = response_text[json_start:json_end]
        result = json.loads(json_str)

        # Add metadata
        result["word_count"] = len(result.get("synthesized_content", "").split())
        result["message"] = f"Synthesized {len(flat_contents)} sources into {result['word_count']} words"

        logger.info(f"[WRITING AGENT] Synthesized {len(flat_contents)} sources → {result['word_count']} words")

        return result

    except Exception as e:
        logger.error(f"[WRITING AGENT] Error in synthesize_content: {e}")
        return {
            "error": True,
            "error_type": "SynthesisError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def create_slide_deck_content(
    content: str,
    title: str,
    num_slides: Optional[int] = None
) -> Dict[str, Any]:
    """
    Transform content into concise, bullet-point format optimized for slide decks.

    WRITING AGENT - LEVEL 2: Slide Deck Writing
    Use this to create presentation-ready content with concise bullets.

    This tool uses LLM to:
    - Extract key messages and talking points
    - Format content as concise bullet points
    - Organize into logical slides
    - Remove verbose language and focus on impact
    - Ensure each slide has a clear message

    Args:
        content: Source content to transform (can be from synthesis or extraction)
        title: Presentation title/topic
        num_slides: Target number of slides (None = auto-determine based on content)

    Returns:
        Dictionary with slides (list of slide objects), total_slides, and formatted_content

    Example:
        create_slide_deck_content(
            content="$step1.synthesized_content",
            title="Q4 Marketing Strategy",
            num_slides=5
        )
    """
    logger.info(f"[WRITING AGENT] Tool: create_slide_deck_content(title='{title}', num_slides={num_slides})")

    try:
        from ..utils import load_config

        config = load_config()
        openai_config = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=0.2,
            api_key=openai_config.get("api_key")
        )

        if not content or not content.strip():
            return {
                "error": True,
                "error_type": "NoContentError",
                "error_message": "No content provided for slide deck creation",
                "retry_possible": False
            }

        # Determine target slides
        target_slides_instruction = ""
        if num_slides:
            target_slides_instruction = f"Create EXACTLY {num_slides} content slides (plus title slide)."
        else:
            target_slides_instruction = "Determine the optimal number of slides based on content (typically 5-10)."

        slide_deck_prompt = f"""You are an expert presentation designer. Create concise, impactful slide content for a presentation.

PRESENTATION TITLE: {title}

SOURCE CONTENT:
{content[:8000]}

INSTRUCTIONS:
{target_slides_instruction}

SLIDE DESIGN PRINCIPLES:
1. Each slide should have ONE clear message
2. Use short, punchy bullet points (max 5-7 words per bullet)
3. Maximum 3-5 bullets per slide
4. Use action verbs and concrete language
5. Avoid complete sentences - use fragments
6. Focus on "what matters" not explanatory text
7. Each slide needs a clear, descriptive title

OUTPUT FORMAT:
Provide a JSON response with:
{{
    "slides": [
        {{
            "slide_number": 1,
            "title": "Slide title",
            "bullets": ["Bullet 1", "Bullet 2", "Bullet 3"],
            "notes": "Optional speaker notes"
        }},
        ...
    ],
    "total_slides": number_of_content_slides
}}

Create presentation-ready content that is concise, impactful, and visual-friendly.
"""

        messages = [
            SystemMessage(content="You are an expert presentation designer specializing in concise, impactful slides."),
            HumanMessage(content=slide_deck_prompt)
        ]

        response = llm.invoke(messages)
        response_text = response.content

        # Parse JSON response
        import json
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            return {
                "error": True,
                "error_type": "ParsingError",
                "error_message": "Failed to parse slide deck structure",
                "retry_possible": True
            }

        json_str = response_text[json_start:json_end]
        result = json.loads(json_str)

        # Format slides into readable text for Keynote creation
        formatted_content = ""
        for slide in result.get("slides", []):
            formatted_content += f"\n\n{slide['title']}\n"
            for bullet in slide.get("bullets", []):
                formatted_content += f"• {bullet}\n"

        result["formatted_content"] = formatted_content.strip()
        result["message"] = f"Created {result.get('total_slides', 0)} slides for '{title}'"

        logger.info(f"[WRITING AGENT] Created {result.get('total_slides', 0)} slides")

        return result

    except Exception as e:
        logger.error(f"[WRITING AGENT] Error in create_slide_deck_content: {e}")
        return {
            "error": True,
            "error_type": "SlideCreationError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def create_detailed_report(
    content: str,
    title: str,
    report_style: str = "business",
    include_sections: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Transform content into a detailed, well-structured report with long-form writing.

    WRITING AGENT - LEVEL 3: Report Writing
    Use this to create comprehensive reports with detailed analysis and explanations.

    This tool uses LLM to:
    - Expand and elaborate on key points
    - Add context and explanations
    - Structure content into logical sections
    - Use professional, flowing prose
    - Include transitions and narrative flow

    Args:
        content: Source content to transform into a report
        title: Report title
        report_style: Writing style for the report:
            - "business": Professional, action-oriented (default)
            - "academic": Formal, analytical, citation-focused
            - "technical": Detailed, precise, specification-focused
            - "executive": High-level, strategic, concise
        include_sections: Optional list of sections to include
            (e.g., ["Executive Summary", "Analysis", "Recommendations"])
            If None, sections are auto-generated based on content

    Returns:
        Dictionary with report_content, sections, word_count, and structure

    Example:
        create_detailed_report(
            content="$step1.synthesized_content",
            title="Annual Security Audit Report",
            report_style="technical",
            include_sections=["Executive Summary", "Findings", "Recommendations"]
        )
    """
    logger.info(f"[WRITING AGENT] Tool: create_detailed_report(title='{title}', style='{report_style}')")

    try:
        from ..utils import load_config

        config = load_config()
        openai_config = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=0.3,
            api_key=openai_config.get("api_key")
        )

        if not content or not content.strip():
            return {
                "error": True,
                "error_type": "NoContentError",
                "error_message": "No content provided for report creation",
                "retry_possible": False
            }

        # Style-specific instructions
        style_guidelines = {
            "business": "Use professional, action-oriented language. Focus on results and implications. Be clear and direct. Use active voice.",
            "academic": "Use formal, analytical language. Include proper structure (introduction, analysis, conclusion). Reference concepts and frameworks. Be thorough and objective.",
            "technical": "Use precise, specification-focused language. Include technical details and methodologies. Be accurate and comprehensive. Use industry terminology.",
            "executive": "Use high-level, strategic language. Focus on key insights and recommendations. Be concise but impactful. Emphasize business value."
        }

        style_guide = style_guidelines.get(report_style, style_guidelines["business"])

        # Section handling
        sections_instruction = ""
        if include_sections:
            sections_list = ", ".join(include_sections)
            sections_instruction = f"Structure the report with these specific sections: {sections_list}"
        else:
            sections_instruction = "Determine the most appropriate sections based on the content (typically: Executive Summary, Main Analysis/Body, Conclusions/Recommendations)"

        report_prompt = f"""You are an expert report writer. Create a comprehensive, well-structured report from the provided content.

REPORT TITLE: {title}

REPORT STYLE: {report_style}
{style_guide}

SOURCE CONTENT:
{content[:10000]}

INSTRUCTIONS:
1. {sections_instruction}
2. Expand bullet points into flowing, detailed prose
3. Add context, explanations, and transitions
4. Use proper paragraph structure
5. Include an introduction and conclusion
6. Ensure logical flow between sections
7. Maintain consistent tone and style throughout

OUTPUT FORMAT:
Provide a JSON response with:
{{
    "report_content": "The complete formatted report as a single text with section headers",
    "sections": [
        {{
            "section_name": "Section Title",
            "content": "Section content",
            "word_count": number
        }},
        ...
    ],
    "executive_summary": "Brief overview of the report (2-3 sentences)",
    "total_word_count": total_words_in_report
}}

Create a professional, detailed report with strong narrative flow.
"""

        messages = [
            SystemMessage(content="You are an expert report writer with extensive experience in professional documentation."),
            HumanMessage(content=report_prompt)
        ]

        response = llm.invoke(messages)
        response_text = response.content

        # Parse JSON response
        import json
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            return {
                "error": True,
                "error_type": "ParsingError",
                "error_message": "Failed to parse report structure",
                "retry_possible": True
            }

        json_str = response_text[json_start:json_end]
        result = json.loads(json_str)

        result["report_style"] = report_style
        result["message"] = f"Created {report_style} report: '{title}' ({result.get('total_word_count', 0)} words)"

        logger.info(f"[WRITING AGENT] Created report: {result.get('total_word_count', 0)} words, {len(result.get('sections', []))} sections")

        return result

    except Exception as e:
        logger.error(f"[WRITING AGENT] Error in create_detailed_report: {e}")
        return {
            "error": True,
            "error_type": "ReportCreationError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def create_meeting_notes(
    content: str,
    meeting_title: str,
    attendees: Optional[List[str]] = None,
    include_action_items: bool = True
) -> Dict[str, Any]:
    """
    Transform content into structured meeting notes with action items.

    WRITING AGENT - LEVEL 4: Note-Taking
    Use this to create organized meeting notes from transcripts or rough notes.

    This tool uses LLM to:
    - Extract key discussion points
    - Identify decisions made
    - Extract action items and owners
    - Organize chronologically or by topic
    - Format in professional note-taking structure

    Args:
        content: Source content (meeting transcript, rough notes, etc.)
        meeting_title: Title/topic of the meeting
        attendees: Optional list of attendee names
        include_action_items: Whether to extract and highlight action items (default: True)

    Returns:
        Dictionary with formatted_notes, discussion_points, decisions, action_items

    Example:
        create_meeting_notes(
            content="$step1.extracted_text",
            meeting_title="Q1 Planning Meeting",
            attendees=["Alice", "Bob", "Charlie"],
            include_action_items=True
        )
    """
    logger.info(f"[WRITING AGENT] Tool: create_meeting_notes(title='{meeting_title}')")

    try:
        from ..utils import load_config

        config = load_config()
        openai_config = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=0.1,  # Very low temperature for accuracy
            api_key=openai_config.get("api_key")
        )

        if not content or not content.strip():
            return {
                "error": True,
                "error_type": "NoContentError",
                "error_message": "No content provided for note creation",
                "retry_possible": False
            }

        # Attendees handling
        attendees_text = ""
        if attendees:
            attendees_text = f"ATTENDEES: {', '.join(attendees)}\n"

        # Action items instruction
        action_items_instruction = ""
        if include_action_items:
            action_items_instruction = """
ACTION ITEMS:
- Extract all action items, tasks, and next steps
- Assign owners when mentioned
- Include deadlines if specified
- Format as: "Action item (Owner - Deadline)" or "Action item (Owner)" if no deadline
"""

        notes_prompt = f"""You are an expert note-taker. Create structured, professional meeting notes from the provided content.

MEETING: {meeting_title}
{attendees_text}

SOURCE CONTENT:
{content[:8000]}

INSTRUCTIONS:
1. Extract key discussion points and topics covered
2. Identify decisions that were made
3. {action_items_instruction if include_action_items else "Focus on discussion summary"}
4. Organize chronologically or by topic
5. Use clear, concise language
6. Preserve important details and context

OUTPUT FORMAT:
Provide a JSON response with:
{{
    "formatted_notes": "Complete formatted meeting notes as text",
    "discussion_points": ["Point 1", "Point 2", ...],
    "decisions": ["Decision 1", "Decision 2", ...],
    "action_items": [
        {{"item": "Action description", "owner": "Person name or null", "deadline": "Date or null"}},
        ...
    ],
    "key_takeaways": ["Takeaway 1", "Takeaway 2", ...]
}}

Create clear, actionable meeting notes that capture the essential information.
"""

        messages = [
            SystemMessage(content="You are an expert note-taker specializing in meeting documentation."),
            HumanMessage(content=notes_prompt)
        ]

        response = llm.invoke(messages)
        response_text = response.content

        # Parse JSON response
        import json
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            return {
                "error": True,
                "error_type": "ParsingError",
                "error_message": "Failed to parse notes structure",
                "retry_possible": True
            }

        json_str = response_text[json_start:json_end]
        result = json.loads(json_str)

        result["meeting_title"] = meeting_title
        result["attendees"] = attendees or []
        result["message"] = f"Created notes for '{meeting_title}' with {len(result.get('action_items', []))} action items"

        logger.info(f"[WRITING AGENT] Created notes: {len(result.get('discussion_points', []))} points, {len(result.get('action_items', []))} actions")

        return result

    except Exception as e:
        logger.error(f"[WRITING AGENT] Error in create_meeting_notes: {e}")
        return {
            "error": True,
            "error_type": "NoteCreationError",
            "error_message": str(e),
            "retry_possible": False
        }


# Writing Agent Tool Registry
WRITING_AGENT_TOOLS = [
    synthesize_content,
    create_slide_deck_content,
    create_detailed_report,
    create_meeting_notes,
]


# Writing Agent Hierarchy
WRITING_AGENT_HIERARCHY = """
Writing Agent Hierarchy:
=======================

LEVEL 1: Content Synthesis
└─ synthesize_content → Combine multiple sources into cohesive content

LEVEL 2: Slide Deck Writing
└─ create_slide_deck_content → Transform content into concise bullets for presentations

LEVEL 3: Report Writing
└─ create_detailed_report → Create comprehensive long-form reports

LEVEL 4: Note-Taking
└─ create_meeting_notes → Structure meeting notes with action items

Typical Workflows:

WORKFLOW 1: Research Report Creation
1. search_documents / google_search → Find sources
2. extract_section / extract_page_content → Get content
3. synthesize_content → Combine sources
4. create_detailed_report → Generate final report
5. create_pages_doc → Save as document

WORKFLOW 2: Presentation Creation
1. search_documents / google_search → Find sources
2. extract_section / extract_page_content → Get content
3. synthesize_content → Combine sources
4. create_slide_deck_content → Format for slides
5. create_keynote → Generate presentation

WORKFLOW 3: Meeting Documentation
1. extract_section → Get meeting transcript/notes
2. create_meeting_notes → Structure and extract actions
3. create_pages_doc / compose_email → Distribute notes
"""


class WritingAgent:
    """
    Writing Agent - Mini-orchestrator for content synthesis and writing.

    Responsibilities:
    - Synthesizing information from multiple sources
    - Creating concise slide deck content
    - Generating detailed reports
    - Structuring meeting notes
    - Adapting writing style to context

    This agent acts as a sub-orchestrator that handles all writing-related tasks.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in WRITING_AGENT_TOOLS}
        logger.info(f"[WRITING AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        """Get all writing agent tools."""
        return WRITING_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get writing agent hierarchy documentation."""
        return WRITING_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a writing agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Writing agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[WRITING AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[WRITING AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }
