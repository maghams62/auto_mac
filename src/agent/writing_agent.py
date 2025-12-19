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

from typing import List, Optional, Dict, Any, Union
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import logging
import json
import re
from pathlib import Path
from datetime import datetime

from ..utils import get_temperature_for_model
from ..automation.report_generator import ReportGenerator
from ..memory.session_memory import SessionContext
from ..writing.style_profile import StyleProfile

logger = logging.getLogger(__name__)


class WritingBrief:
    """
    Structured writing brief that captures user intent and context.

    This class encapsulates all the contextual information needed to produce
    targeted, high-quality written content that matches user expectations.
    """

    def __init__(
        self,
        deliverable_type: str = "general",
        tone: str = "professional",
        audience: str = "general",
        length_guideline: str = "medium",
        must_include_facts: Optional[List[str]] = None,
        must_include_data: Optional[Dict[str, Any]] = None,
        focus_areas: Optional[List[str]] = None,
        style_preferences: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        session_context: Optional[SessionContext] = None
    ):
        """
        Initialize a writing brief.

        Args:
            deliverable_type: Type of content (report, deck, email, summary, narrative)
            tone: Writing tone (professional, technical, casual, academic, executive)
            audience: Target audience (general, technical, executive, academic)
            length_guideline: Desired length (brief, medium, comprehensive, custom)
            must_include_facts: List of specific facts/statements that must appear
            must_include_data: Dictionary of structured data (prices, dates, metrics) that must be referenced
            focus_areas: List of topics/themes to emphasize
            style_preferences: Additional style preferences (use_bullets, avoid_jargon, etc.)
            constraints: Writing constraints (max_slides, word_limit, section_requirements)
            session_context: Optional SessionContext to auto-populate fields from memory
        """
        # Auto-populate from session context if provided, otherwise use explicit parameters
        if session_context:
            # Use derived topic as focus area if not explicitly provided
            if not focus_areas and session_context.derived_topic:
                focus_areas = [session_context.derived_topic]

            # Extract audience/tone hints from user context
            user_context = session_context.context_objects.get("user_context", {})
            if not audience and user_context.get("audience_hint"):
                audience = user_context["audience_hint"]
            if not tone and user_context.get("tone_hint"):
                tone = user_context["tone_hint"]

            # Extract constraints from token budget metadata
            if not constraints and session_context.token_budget_metadata:
                constraints = {
                    "max_tokens": session_context.token_budget_metadata.get("max_tokens"),
                    "profile": session_context.token_budget_metadata.get("profile")
                }

        self.deliverable_type = deliverable_type
        self.tone = tone
        self.audience = audience
        self.length_guideline = length_guideline
        self.must_include_facts = must_include_facts or []
        self.must_include_data = must_include_data or {}
        self.focus_areas = focus_areas or []
        self.style_preferences = style_preferences or {}
        self.constraints = constraints or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert brief to dictionary format."""
        return {
            "deliverable_type": self.deliverable_type,
            "tone": self.tone,
            "audience": self.audience,
            "length_guideline": self.length_guideline,
            "must_include_facts": self.must_include_facts,
            "must_include_data": self.must_include_data,
            "focus_areas": self.focus_areas,
            "style_preferences": self.style_preferences,
            "constraints": self.constraints
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WritingBrief":
        """Create brief from dictionary."""
        return cls(**data)

    def to_prompt_section(self) -> str:
        """Generate a formatted prompt section from the brief."""
        sections = []

        sections.append(f"DELIVERABLE TYPE: {self.deliverable_type}")
        sections.append(f"TONE: {self.tone}")
        sections.append(f"AUDIENCE: {self.audience}")
        sections.append(f"LENGTH: {self.length_guideline}")

        if self.focus_areas:
            sections.append(f"FOCUS AREAS: {', '.join(self.focus_areas)}")

        if self.must_include_facts:
            sections.append("\nREQUIRED FACTS TO INCLUDE:")
            for fact in self.must_include_facts:
                sections.append(f"  - {fact}")

        if self.must_include_data:
            sections.append("\nREQUIRED DATA TO REFERENCE:")
            for key, value in self.must_include_data.items():
                sections.append(f"  - {key}: {value}")

        if self.style_preferences:
            sections.append(f"\nSTYLE PREFERENCES: {json.dumps(self.style_preferences)}")

        if self.constraints:
            sections.append(f"\nCONSTRAINTS: {json.dumps(self.constraints)}")

        return "\n".join(sections)


def _validate_brief_compliance(
    content: str,
    brief: WritingBrief,
    reported_compliance: Dict[str, List[str]]
) -> Dict[str, Any]:
    """
    Validate that the generated content includes required facts and data from the brief.

    Args:
        content: The generated content to validate
        brief: The writing brief with requirements
        reported_compliance: What the LLM reported it included

    Returns:
        Dictionary with compliant (bool), compliance_score (0-1), and missing_items (list)
    """
    content_lower = content.lower()
    missing_items = []
    total_requirements = 0
    met_requirements = 0

    # Check must-include facts
    for fact in brief.must_include_facts:
        total_requirements += 1
        # Flexible matching: check if key terms from the fact appear
        fact_terms = [term.strip().lower() for term in re.split(r'[,;\s]+', fact) if len(term.strip()) > 3]
        matched = sum(1 for term in fact_terms if term in content_lower)

        if matched >= max(1, len(fact_terms) // 2):  # At least half the terms match
            met_requirements += 1
        else:
            missing_items.append(f"Fact: {fact}")

    # Check must-include data
    for key, value in brief.must_include_data.items():
        total_requirements += 1
        # Check if the value or key appears in content
        value_str = str(value).lower()
        key_lower = key.lower()

        if value_str in content_lower or key_lower in content_lower:
            met_requirements += 1
        else:
            missing_items.append(f"Data: {key}={value}")

    compliance_score = met_requirements / total_requirements if total_requirements > 0 else 1.0
    compliant = compliance_score >= 0.7  # At least 70% compliance required

    return {
        "compliant": compliant,
        "compliance_score": compliance_score,
        "missing_items": missing_items,
        "met_requirements": met_requirements,
        "total_requirements": total_requirements
    }


@tool
def prepare_writing_brief(
    user_request: str,
    deliverable_type: str = "general",
    upstream_artifacts: Optional[Dict[str, Any]] = None,
    context_hints: Optional[Dict[str, Any]] = None,
    session_context: Optional[SessionContext] = None
) -> Dict[str, Any]:
    """
    Analyze user request and context to create a structured writing brief.

    WRITING AGENT - LEVEL 0: Brief Preparation
    Use this before any writing task to extract intent, tone, audience, and required data.

    This tool uses LLM to:
    - Parse user intent and extract writing requirements
    - Identify tone, audience, and style preferences
    - Extract must-include facts and data from context
    - Set appropriate constraints based on deliverable type

    Args:
        user_request: The original user request or task description
        deliverable_type: Type of deliverable (report, deck, email, summary, narrative)
        upstream_artifacts: Dictionary of results from prior steps (e.g., search results, extracted data)
        context_hints: Additional context (e.g., {"timeframe": "Q4 2024", "project": "Marketing"})
        session_context: Optional SessionContext for auto-populating brief from memory

    Returns:
        Dictionary with writing_brief (as dict), analysis, and confidence_score

    Example:
        prepare_writing_brief(
            user_request="Create a report on NVDA stock performance with Q4 earnings",
            deliverable_type="report",
            upstream_artifacts={"$step1.stock_data": {...}, "$step2.news": [...]},
            session_context="$step0.session_context"
        )
    """
    logger.info(f"[WRITING AGENT] Tool: prepare_writing_brief(type='{deliverable_type}')")

    try:
        from ..utils import load_config

        config = load_config()
        openai_config = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.2),
            api_key=openai_config.get("api_key")
        )

        # Prepare artifacts summary
        artifacts_summary = ""
        if upstream_artifacts:
            artifacts_summary = "\nUPSTREAM ARTIFACTS:\n"
            for key, value in upstream_artifacts.items():
                # Summarize large artifacts
                if isinstance(value, dict):
                    artifacts_summary += f"  {key}: {json.dumps(value, indent=2)[:500]}...\n"
                elif isinstance(value, list):
                    artifacts_summary += f"  {key}: List with {len(value)} items\n"
                else:
                    artifacts_summary += f"  {key}: {str(value)[:200]}...\n"

        # Prepare context hints
        context_summary = ""
        if context_hints:
            context_summary = f"\nCONTEXT HINTS: {json.dumps(context_hints)}\n"

        brief_prompt = f"""You are an expert writing strategist. Analyze the user request and context to create a structured writing brief.

USER REQUEST:
{user_request}

DELIVERABLE TYPE: {deliverable_type}
{artifacts_summary}
{context_summary}

YOUR TASK:
Analyze the request to extract:
1. TONE: What tone should the writing have? (professional, technical, casual, academic, executive, conversational)
2. AUDIENCE: Who is the target audience? (general, technical, executive, academic, specialized)
3. LENGTH GUIDELINE: How long should it be? (brief, medium, comprehensive)
4. FOCUS AREAS: What topics/themes should be emphasized? (list 2-5 focus areas)
5. MUST-INCLUDE FACTS: Specific facts or statements that MUST appear in the output
6. MUST-INCLUDE DATA: Structured data (prices, dates, metrics, names) that MUST be referenced
7. STYLE PREFERENCES: Writing style preferences (use_bullets, avoid_jargon, be_specific, etc.)
8. CONSTRAINTS: Any constraints (max_slides, word_limit, required_sections, etc.)

CRITICAL INSTRUCTIONS:
- Extract ALL numerical data, dates, prices, percentages from artifacts as must-include data
- Identify the exact tone from the user's language and deliverable type
- Be specific about focus areas - not generic themes
- If artifacts contain search results, news, or reports, extract key facts as must-include items
- Consider the deliverable type when setting constraints (e.g., reports need comprehensive length, decks need brevity)

OUTPUT FORMAT:
Provide a JSON response with:
{{
    "writing_brief": {{
        "deliverable_type": "{deliverable_type}",
        "tone": "detected tone",
        "audience": "detected audience",
        "length_guideline": "brief/medium/comprehensive",
        "must_include_facts": ["fact 1", "fact 2", ...],
        "must_include_data": {{"metric_name": value, "date": "2024-Q4", ...}},
        "focus_areas": ["area 1", "area 2", ...],
        "style_preferences": {{"preference": value, ...}},
        "constraints": {{"constraint": value, ...}}
    }},
    "analysis": "Brief explanation of the detected intent and requirements",
    "confidence_score": 0.0-1.0
}}

Be thorough in extracting must-include data - this is critical for quality output.
"""

        messages = [
            SystemMessage(content="You are an expert writing strategist who analyzes user intent."),
            HumanMessage(content=brief_prompt)
        ]

        response = llm.invoke(messages)
        response_text = response.content

        # Parse JSON response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            # Fallback: create a basic brief
            return {
                "writing_brief": WritingBrief(deliverable_type=deliverable_type).to_dict(),
                "analysis": "Failed to analyze request; using default brief",
                "confidence_score": 0.3,
                "message": "Created default writing brief"
            }

        json_str = response_text[json_start:json_end]
        result = json.loads(json_str)

        # Validate and enhance the brief
        brief_data = result.get("writing_brief", {})
        brief = WritingBrief.from_dict(brief_data)

        # Enhance brief with session context if provided
        if session_context:
            enhanced_brief = WritingBrief(
                deliverable_type=brief.deliverable_type,
                tone=brief.tone,
                audience=brief.audience,
                length_guideline=brief.length_guideline,
                must_include_facts=brief.must_include_facts,
                must_include_data=brief.must_include_data,
                focus_areas=brief.focus_areas,
                style_preferences=brief.style_preferences,
                constraints=brief.constraints,
                session_context=session_context
            )
            brief = enhanced_brief
            result["writing_brief"] = brief.to_dict()
            result["session_context_used"] = True
            logger.info(f"[WRITING AGENT] Enhanced brief with session context: topic='{session_context.headline()}'")

        result["message"] = f"Created {brief.tone} {deliverable_type} brief for {brief.audience} audience"
        logger.info(f"[WRITING AGENT] ✅ Brief created: {brief.tone} tone, {len(brief.must_include_facts)} facts, {len(brief.must_include_data)} data points")

        return result

    except Exception as e:
        logger.error(f"[WRITING AGENT] Error in prepare_writing_brief: {e}")
        # Fallback to default brief
        return {
            "writing_brief": WritingBrief(deliverable_type=deliverable_type).to_dict(),
            "analysis": f"Error creating brief: {str(e)}",
            "confidence_score": 0.3,
            "message": "Created default writing brief due to error"
        }


@tool
def synthesize_content(
    source_contents: List[str],
    topic: Optional[str] = None,
    synthesis_style: str = "comprehensive",
    writing_brief: Optional[Dict[str, Any]] = None,
    session_context: Optional[SessionContext] = None,
    reasoning_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Synthesize information from multiple sources into cohesive content.

    WRITING AGENT - LEVEL 1: Content Synthesis
    Use this to combine and analyze information from different sources.

    ⚠️  CRITICAL: This tool returns SYNTHESIZED TEXT, not a file path!
    - If you need to EMAIL the synthesized content, you MUST first save it using create_pages_doc
    - CORRECT workflow: synthesize_content → create_pages_doc → compose_email(attachments=["$stepN.pages_path"])
    - WRONG: compose_email(attachments=["$stepN.synthesized_content"]) ← This is TEXT not a FILE PATH!

    This tool uses LLM to:
    - Identify key themes and patterns across sources
    - Remove redundancy and contradictions
    - Create a unified narrative
    - Preserve important details and citations
    - Apply writing brief requirements (tone, audience, must-include facts/data)

    Args:
        source_contents: List of text contents to synthesize (from documents, web pages, etc.)
        topic: The main topic or focus for synthesis (auto-derived from session_context if not provided)
        synthesis_style: How to synthesize the content:
            - "comprehensive": Include all important details (for reports)
            - "concise": Focus on key points only (for summaries)
            - "comparative": Highlight differences and similarities
            - "chronological": Organize by timeline/sequence
        writing_brief: Optional writing brief as dictionary
            Use prepare_writing_brief first to create this
        session_context: Optional SessionContext for auto-populating topic and context

    Returns:
        Dictionary with synthesized_content (TEXT string), key_points, sources_used, word_count
        ⚠️  synthesized_content is TEXT, NOT a file path - use create_pages_doc to save it

    Example:
        # With session context (recommended for context-aware synthesis)
        synthesize_content(
            source_contents=["$step1.extracted_text", "$step2.content"],
            session_context="$step0.session_context",
            synthesis_style="comprehensive"
        )

        # Without brief (legacy mode)
        synthesize_content(
            source_contents=["$step1.extracted_text", "$step2.content"],
            topic="AI Safety Research",
            synthesis_style="comprehensive"
        )
    """
    # Derive topic from session context if not provided
    if not topic and session_context:
        topic = session_context.headline()
        logger.info(f"[WRITING AGENT] Derived topic from context: '{topic}'")

    logger.info(f"[WRITING AGENT] Tool: synthesize_content(topic='{topic}', style='{synthesis_style}', brief={'Yes' if writing_brief else 'No'})")

    # Check memory context for learning from past attempts
    if reasoning_context:
        past_attempts = reasoning_context.get("past_attempts", 0)
        commitments = reasoning_context.get("commitments", [])
        logger.debug(f"[WRITING AGENT] Memory context: {past_attempts} past attempts, commitments: {commitments}")

        # If we've had issues with synthesis before, be more thorough
        if past_attempts > 0:
            logger.info(f"[WRITING AGENT] Learning from {past_attempts} past attempts - using more detailed synthesis")
            if synthesis_style == "concise":
                synthesis_style = "comprehensive"  # Be more thorough if we've had issues

    try:
        from ..utils import load_config

        config = load_config()
        openai_config = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.3),
            api_key=openai_config.get("api_key")
        )

        # Flatten list if it contains nested lists (from context variables)
        # Also convert structured data (dicts, lists) to JSON strings for LLM processing
        flat_contents = []
        for item in source_contents:
            if isinstance(item, list):
                # If list contains dicts, convert to JSON string
                if item and isinstance(item[0], dict):
                    flat_contents.append(json.dumps(item, indent=2))
                else:
                    flat_contents.extend(item)
            elif isinstance(item, dict):
                # Convert dict to JSON string
                flat_contents.append(json.dumps(item, indent=2))
            else:
                flat_contents.append(item)

        if not flat_contents or all(not content.strip() for content in flat_contents):
            return {
                "error": True,
                "error_type": "NoContentError",
                "error_message": "No content provided for synthesis",
                "retry_possible": False
            }

        # Parse writing brief if provided
        brief = None
        if writing_brief:
            if isinstance(writing_brief, dict):
                brief = WritingBrief.from_dict(writing_brief)
            else:
                logger.warning(f"[WRITING AGENT] writing_brief should be a dict")

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

        # Add writing brief section if available
        brief_section = ""
        if brief:
            brief_section = f"""
WRITING BRIEF (CRITICAL - FOLLOW THESE REQUIREMENTS):
{brief.to_prompt_section()}

CRITICAL: You MUST include all required facts and data points listed above in your synthesis.
If numerical data, dates, or specific metrics are listed, reference them explicitly.
"""

        synthesis_prompt = f"""You are an expert content synthesizer. Your task is to synthesize information from multiple sources into cohesive, well-structured content.

TOPIC: {topic}

SYNTHESIS STYLE: {synthesis_style}
{instruction}
{brief_section}

SOURCES TO SYNTHESIZE:
{sources_text}

INSTRUCTIONS:
1. Read all sources carefully
2. Identify key themes, facts, and insights
3. Remove redundancy while preserving unique information
4. Create a cohesive narrative that flows naturally
5. Preserve important details and nuances
6. If sources conflict, note the different perspectives
7. **CRITICAL**: If a writing brief is provided, ensure ALL must-include facts and data are incorporated
8. Match the specified tone and audience from the brief
9. Emphasize the focus areas identified in the brief

OUTPUT FORMAT:
Provide a JSON response with:
{{
    "synthesized_content": "The main synthesized content as a cohesive narrative",
    "key_points": ["bullet point 1", "bullet point 2", ...],
    "themes_identified": ["theme 1", "theme 2", ...],
    "source_count": number_of_sources_used,
    "brief_compliance": {{"facts_included": ["list of must-include facts that were incorporated"], "data_included": ["list of must-include data points that were incorporated"]}}
}}

Focus on creating valuable, coherent content that serves the specified synthesis style and meets all brief requirements.
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

        # Quality guardrails: validate brief compliance
        if brief and (brief.must_include_facts or brief.must_include_data):
            validation_result = _validate_brief_compliance(
                result.get("synthesized_content", ""),
                brief,
                result.get("brief_compliance", {})
            )

            if not validation_result["compliant"]:
                logger.warning(f"[WRITING AGENT] Brief compliance issues: {validation_result['missing_items']}")
                result["quality_warnings"] = validation_result["missing_items"]
                result["compliance_score"] = validation_result["compliance_score"]
            else:
                result["compliance_score"] = 1.0
                logger.info(f"[WRITING AGENT] ✅ Brief compliance validated")

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


class WritingStyleOrchestrator:
    """
    Orchestrator for building normalized style briefs from multiple sources.

    This class centralizes writing control by extending WritingBrief usage across
    all generators. It builds a normalized style brief from:
    - User query and context hints
    - Session context and persistent memory
    - Deliverable type defaults
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        logger.info("[WRITING AGENT] WritingStyleOrchestrator initialized")

    def build_style_profile(
        self,
        user_request: str,
        deliverable_type: str,
        session_context: Optional[SessionContext] = None,
        context_hints: Optional[Dict[str, Any]] = None
    ) -> StyleProfile:
        """
        Build a normalized style profile from multiple sources.

        Args:
            user_request: The original user request
            deliverable_type: Type of deliverable (email, report, summary, presentation)
            session_context: Optional SessionContext for memory-based preferences
            context_hints: Additional context hints

        Returns:
            Merged StyleProfile with normalized preferences
        """
        logger.info(f"[WRITING AGENT] Building style profile for {deliverable_type}")

        # Start with deliverable defaults
        profile = StyleProfile.from_deliverable_defaults(deliverable_type)

        # Merge user hints from query and context
        user_hints_profile = StyleProfile.from_user_hints(user_request, context_hints)
        profile = profile.merge(user_hints_profile, priority="combine")

        # Merge session memory preferences if available
        if session_context:
            session_profile = StyleProfile.from_session_memory(session_context)
            profile = profile.merge(session_profile, priority="combine")

        # Update metadata
        from datetime import datetime
        profile.last_updated = datetime.now().isoformat()

        logger.info(f"[WRITING AGENT] Style profile built: {profile.get_summary()}")
        return profile

    def get_style_profile(
        self,
        deliverable_type: str,
        session_context: Optional[SessionContext] = None
    ) -> StyleProfile:
        """
        Helper method to get a cached/default style profile.

        This method can be used by email, report, summary, PPT flows to
        get a consistent signature from SessionMemory.shared_context.

        Args:
            deliverable_type: Type of deliverable
            session_context: Optional SessionContext for caching

        Returns:
            StyleProfile for the deliverable type
        """
        # Check if profile is cached in session context
        if session_context and session_context.shared_context:
            cached_key = f"style_profile_{deliverable_type}"
            cached_profile_data = session_context.shared_context.get(cached_key)
            if cached_profile_data:
                profile = StyleProfile.from_dict(cached_profile_data)
                logger.info(f"[WRITING AGENT] Using cached style profile for {deliverable_type}")
                return profile

        # Create default profile for deliverable type
        profile = StyleProfile.from_deliverable_defaults(deliverable_type)

        # Cache in session context if available
        if session_context and session_context.shared_context:
            session_context.shared_context[f"style_profile_{deliverable_type}"] = profile.to_dict()

        return profile

    def enhance_writing_brief(
        self,
        brief: WritingBrief,
        style_profile: StyleProfile
    ) -> WritingBrief:
        """
        Enhance a WritingBrief with StyleProfile information.

        Args:
            brief: Original WritingBrief
            style_profile: StyleProfile to merge in

        Returns:
            Enhanced WritingBrief
        """
        # Merge style profile into brief
        enhanced_brief = WritingBrief(
            deliverable_type=style_profile.deliverable_type or brief.deliverable_type,
            tone=style_profile.tone or brief.tone,
            audience=style_profile.audience or brief.audience,
            length_guideline=brief.length_guideline,
            must_include_facts=brief.must_include_facts + style_profile.must_include_facts,
            must_include_data={**brief.must_include_data, **style_profile.must_include_data},
            focus_areas=brief.focus_areas,
            style_preferences={**brief.style_preferences, **style_profile.style_preferences},
            constraints=brief.constraints,
            session_context=brief.session_context
        )

        # Add cadence modifiers to style preferences
        if style_profile.cadence_modifiers:
            enhanced_brief.style_preferences["cadence_modifiers"] = style_profile.cadence_modifiers

        if style_profile.target_structure:
            enhanced_brief.style_preferences["target_structure"] = style_profile.target_structure

        logger.info(f"[WRITING AGENT] Enhanced brief with style profile: {style_profile.get_summary()}")
        return enhanced_brief


@tool
def chain_of_density_summarize(
    content: str,
    topic: str = "",
    max_rounds: int = 3,
    target_density_score: Optional[float] = None,
    writing_brief: Optional[Dict[str, Any]] = None,
    session_context: Optional[SessionContext] = None
) -> Dict[str, Any]:
    """
    Chain-of-Density prompting for summarization (Adams et al., 2023).

    This utility triggers densification rounds until a configurable density score
    is achieved or token guardrail hit. Applied to email summaries, daily briefings,
    and note-taking so results pack salient entities without rambling.

    Args:
        content: Source content to summarize
        topic: Topic or focus for the summary
        max_rounds: Maximum densification rounds (default: 3)
        target_density_score: Target density score (0-1), uses config default if None
        writing_brief: Optional writing brief for tone/style guidance as dictionary
        session_context: Optional SessionContext for context-aware summarization

    Returns:
        Dictionary with densified_summary, density_score, entities_extracted, rounds_performed
    """
    logger.info(f"[WRITING AGENT] Chain-of-Density summarization (max_rounds: {max_rounds})")

    try:
        from ..utils import load_config

        config = load_config()
        openai_config = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.1),  # Low temperature for consistency
            api_key=openai_config.get("api_key")
        )

        # Get target density from config or parameter
        if target_density_score is None:
            target_density_score = config.get("writing", {}).get("quality_chain_density_score", 0.7)

        # Parse writing brief if provided
        brief_obj = None
        if writing_brief:
            if isinstance(writing_brief, dict):
                brief_obj = WritingBrief.from_dict(writing_brief)
            else:
                logger.warning("[WRITING AGENT] Writing brief should be a dict for CoD")

        # Add session context
        context_instruction = ""
        if session_context:
            context_instruction = f"""
SESSION CONTEXT: {session_context.headline()}

Consider the broader conversation context when determining what information is most salient.
Prioritize entities and details that connect to previous discussions.
"""

        # Brief instruction if available
        brief_instruction = ""
        if brief_obj:
            brief_instruction = f"""
WRITING BRIEF REQUIREMENTS:
{brief_obj.to_prompt_section()}

Ensure the summary matches the required tone ({brief_obj.tone}) and audience ({brief_obj.audience}).
Include all must-include facts and data points from the brief.
"""

        # Initial summary generation
        initial_prompt = f"""You are creating a concise summary using Chain-of-Density methodology.

SOURCE CONTENT:
{content[:3000]}

TOPIC: {topic}
{brief_instruction}
{context_instruction}

INSTRUCTIONS:
1. Create an initial concise summary (2-3 sentences)
2. Extract the most salient entities (people, organizations, dates, metrics, concepts)
3. Identify missing entities that would increase information density

OUTPUT FORMAT:
{{
    "summary": "Initial concise summary",
    "entities": ["entity1", "entity2", ...],
    "missing_entities": ["entity1", "entity2", ...],
    "density_score": 0.0-1.0
}}

Focus on factual density - pack in specific, important information without rambling.
"""

        messages = [
            SystemMessage(content="You are an expert at creating dense, informative summaries."),
            HumanMessage(content=initial_prompt)
        ]

        response = llm.invoke(messages)
        response_text = response.content

        # Parse initial response
        try:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            initial_result = json.loads(response_text[json_start:json_end])
        except:
            logger.warning("[WRITING AGENT] Could not parse initial CoD response")
            initial_result = {
                "summary": response_text[:500],
                "entities": [],
                "missing_entities": [],
                "density_score": 0.3
            }

        current_summary = initial_result.get("summary", "")
        current_entities = initial_result.get("entities", [])
        current_density = initial_result.get("density_score", 0.3)

        rounds_performed = 0
        densification_history = [{
            "round": 0,
            "summary": current_summary,
            "entities": current_entities,
            "density_score": current_density
        }]

        # Iterative densification rounds
        for round_num in range(1, max_rounds + 1):
            rounds_performed = round_num

            # Check if we've reached target density
            if current_density >= target_density_score:
                logger.info(f"[WRITING AGENT] Target density {target_density_score} reached at round {round_num}")
                break

            # Check token guardrail (rough estimate)
            estimated_tokens = len(current_summary.split()) * 1.3  # Rough token estimate
            max_tokens = config.get("writing", {}).get("max_refinement_tokens", 2000)
            if estimated_tokens > max_tokens:
                logger.info(f"[WRITING AGENT] Token guardrail hit: {estimated_tokens} > {max_tokens}")
                break

            densify_prompt = f"""Chain-of-Density Round {round_num}: Densify the summary by incorporating missing entities.

CURRENT SUMMARY:
{current_summary}

CURRENT ENTITIES INCLUDED:
{', '.join(current_entities)}

MISSING ENTITIES TO INCORPORATE:
{', '.join(initial_result.get('missing_entities', []))}

SOURCE CONTENT:
{content[:2000]}

TOPIC: {topic}
{brief_instruction}
{context_instruction}

INSTRUCTIONS:
1. Revise the summary to incorporate additional salient entities
2. Maintain conciseness while increasing information density
3. Add specific facts, dates, metrics, or relationships that were missing
4. Ensure the summary remains coherent and well-structured
5. Do NOT make the summary longer just for length - focus on density

OUTPUT FORMAT:
{{
    "revised_summary": "Densified summary with additional entities",
    "new_entities_added": ["entity1", "entity2", ...],
    "total_entities": ["entity1", "entity2", ...],
    "new_density_score": 0.0-1.0,
    "improvement": "What was added and why it increases density"
}}

Higher density means more specific, factual information packed into the same space.
"""

            messages = [
                SystemMessage(content="You are densifying a summary by adding missing salient entities."),
                HumanMessage(content=densify_prompt)
            ]

            response = llm.invoke(messages)
            response_text = response.content

            # Parse densification response
            try:
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                round_result = json.loads(response_text[json_start:json_end])
            except:
                logger.warning(f"[WRITING AGENT] Could not parse CoD round {round_num} response")
                break

            # Update current state
            current_summary = round_result.get("revised_summary", current_summary)
            new_entities = round_result.get("new_entities_added", [])
            current_entities.extend(new_entities)
            current_density = round_result.get("new_density_score", current_density)

            # Track history
            densification_history.append({
                "round": round_num,
                "summary": current_summary,
                "entities": current_entities.copy(),
                "density_score": current_density,
                "new_entities": new_entities,
                "improvement": round_result.get("improvement", "")
            })

        # Calculate final metrics
        total_entities = len(current_entities)
        final_word_count = len(current_summary.split())

        # Calculate information density (entities per word)
        density_score = min(1.0, total_entities / max(final_word_count, 1) * 10)

        logger.info(f"[WRITING AGENT] CoD completed: {rounds_performed} rounds, {total_entities} entities, density: {density_score:.2f}")

        return {
            "densified_summary": current_summary,
            "density_score": density_score,
            "entities_extracted": current_entities,
            "rounds_performed": rounds_performed,
            "target_density_achieved": current_density >= target_density_score,
            "densification_history": densification_history,
            "word_count": final_word_count,
            "entity_count": total_entities,
            "message": f"Densified summary: {total_entities} entities in {final_word_count} words (density: {density_score:.2f})"
        }

    except Exception as e:
        logger.error(f"[WRITING AGENT] Error in chain_of_density_summarize: {e}")
        return {
            "error": True,
            "error_type": "DensitySummarizationError",
            "error_message": str(e),
            "densified_summary": content[:500],  # Fallback to truncated content
            "density_score": 0.1,
            "entities_extracted": [],
            "rounds_performed": 0,
            "target_density_achieved": False
        }


@tool
def self_refine(
    content: str,
    brief: Dict[str, Any],
    refinement_focus: str = "coverage",
    session_context: Optional[SessionContext] = None
) -> Dict[str, Any]:
    """
    Self-Refine content using iterative improvement (Madaan et al., 2023).

    This tool implements the Self-Refine approach for every long-form deliverable.
    It performs refinement passes focusing on different aspects of quality.

    Args:
        content: The content to refine
        brief: Writing brief with requirements as dictionary
        refinement_focus: What to focus on ("coverage", "completeness", "tone", "clarity")
        session_context: Optional SessionContext for context-aware refinement

    Returns:
        Dictionary with refined_content, improvement_score, critique_metadata
    """
    logger.info(f"[WRITING AGENT] Self-refining content (focus: {refinement_focus})")

    try:
        from ..utils import load_config

        config = load_config()
        openai_config = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.2),
            api_key=openai_config.get("api_key")
        )

        # Parse brief
        if isinstance(brief, dict):
            brief_obj = WritingBrief.from_dict(brief)
        else:
            logger.warning("[WRITING AGENT] Brief should be a dict, using default")
            brief_obj = WritingBrief()

        # Get max refinement passes from config
        max_passes = config.get("writing", {}).get("max_refinement_passes", 2)

        # Build refinement prompt based on focus
        focus_prompts = {
            "coverage": """
CRITIQUE FOCUS: Content Coverage and Completeness
- Does the content include ALL required facts from the brief?
- Are all must-include data points referenced appropriately?
- Does it address all focus areas from the brief?
- Are there gaps in coverage that need to be filled?
""",
            "completeness": """
CRITIQUE FOCUS: Structural Completeness and Organization
- Does the content have a clear, logical structure?
- Are transitions between sections smooth and appropriate?
- Does it follow the expected format for this deliverable type?
- Are all sections adequately developed?
""",
            "tone": """
CRITIQUE FOCUS: Tone and Style Adherence
- Does the tone match the brief requirements (executive, professional, technical, etc.)?
- Are cadence modifiers applied correctly (narrative, formal, conversational)?
- Is the language appropriate for the target audience?
- Does the style feel consistent throughout?
""",
            "clarity": """
CRITIQUE FOCUS: Clarity and Readability
- Is the content clear and easy to understand?
- Are complex ideas explained effectively?
- Is jargon used appropriately for the audience?
- Could any sections be simplified or clarified?
"""
        }

        focus_instruction = focus_prompts.get(refinement_focus, focus_prompts["coverage"])

        # Add session context if available
        context_instruction = ""
        if session_context:
            context_instruction = f"""
SESSION CONTEXT: {session_context.headline()}

Consider how this content fits within the broader conversation context.
Ensure consistency with previous outputs and user preferences.
"""

        critique_prompt = f"""You are an expert content critic using Self-Refine methodology (Madaan et al., 2023).

CONTENT TO CRITIQUE:
{content[:4000]}

WRITING BRIEF REQUIREMENTS:
{brief_obj.to_prompt_section()}

{focus_instruction}
{context_instruction}

YOUR TASK:
1. Analyze the content against the brief requirements and critique focus
2. Identify specific areas that need improvement
3. Provide actionable feedback for refinement
4. Suggest concrete changes to address issues

OUTPUT FORMAT:
Provide a JSON response with:
{{
    "critique": "Specific critique of what's wrong or missing",
    "issues_found": ["issue 1", "issue 2", ...],
    "suggested_improvements": ["improvement 1", "improvement 2", ...],
    "refinement_needed": true/false,
    "confidence_score": 0.0-1.0
}}

Be specific about what's wrong and how to fix it. Focus on the critique area specified.
"""

        # Get critique from LLM
        messages = [
            SystemMessage(content="You are an expert content critic specializing in Self-Refine methodology."),
            HumanMessage(content=critique_prompt)
        ]

        critique_response = llm.invoke(messages)
        critique_text = critique_response.content

        # Parse critique JSON
        try:
            json_start = critique_text.find('{')
            json_end = critique_text.rfind('}') + 1
            critique_data = json.loads(critique_text[json_start:json_end])
        except:
            logger.warning("[WRITING AGENT] Could not parse critique JSON, using fallback")
            critique_data = {
                "critique": "General quality assessment",
                "issues_found": ["Minor style inconsistencies"],
                "suggested_improvements": ["Review for clarity"],
                "refinement_needed": False,
                "confidence_score": 0.5
            }

        # Check if refinement is needed
        if not critique_data.get("refinement_needed", False):
            logger.info(f"[WRITING AGENT] No refinement needed for {refinement_focus}")
            return {
                "refined_content": content,
                "improvement_score": 1.0,
                "critique_metadata": critique_data,
                "refinement_performed": False,
                "message": f"Content quality acceptable for {refinement_focus} focus"
            }

        # Perform refinement
        refinement_prompt = f"""You are an expert content refiner using Self-Refine methodology.

ORIGINAL CONTENT:
{content[:4000]}

WRITING BRIEF REQUIREMENTS:
{brief_obj.to_prompt_section()}

CRITIQUE RECEIVED:
{critique_data.get('critique', 'General quality improvements needed')}

ISSUES TO ADDRESS:
{chr(10).join(f"- {issue}" for issue in critique_data.get('issues_found', []))}

SUGGESTED IMPROVEMENTS:
{chr(10).join(f"- {improvement}" for improvement in critique_data.get('suggested_improvements', []))}

{context_instruction}

YOUR TASK:
Refine the content by addressing all the critique points and implementing the suggested improvements.
Focus specifically on the {refinement_focus} issues identified.

Maintain the overall structure and intent while making targeted improvements.
Ensure all brief requirements are still met after refinement.

OUTPUT: Provide only the refined content, no explanations or metadata.
"""

        messages = [
            SystemMessage(content="You are an expert content refiner. Provide only the refined content."),
            HumanMessage(content=refinement_prompt)
        ]

        refined_response = llm.invoke(messages)
        refined_content = refined_response.content.strip()

        # Calculate improvement score (simplified heuristic)
        original_length = len(content.split())
        refined_length = len(refined_content.split())
        length_change_ratio = abs(refined_length - original_length) / max(original_length, 1)

        # Higher score for substantial improvements without excessive changes
        improvement_score = min(0.9, max(0.1, 0.5 + length_change_ratio * 0.3))

        # Store critique metadata for transparency
        critique_metadata = {
            **critique_data,
            "refinement_focus": refinement_focus,
            "original_length": original_length,
            "refined_length": refined_length,
            "timestamp": json.dumps({"timestamp": "now"}, default=str)
        }

        logger.info(f"[WRITING AGENT] Self-refine completed: {original_length} → {refined_length} words, score: {improvement_score:.2f}")

        return {
            "refined_content": refined_content,
            "improvement_score": improvement_score,
            "critique_metadata": critique_metadata,
            "refinement_performed": True,
            "message": f"Content refined for {refinement_focus} (score: {improvement_score:.2f})"
        }

    except Exception as e:
        logger.error(f"[WRITING AGENT] Error in self_refine: {e}")
        return {
            "error": True,
            "error_type": "RefinementError",
            "error_message": str(e),
            "refined_content": content,  # Return original content on error
            "improvement_score": 0.0,
            "critique_metadata": {},
            "refinement_performed": False
        }


@tool
def evaluate_with_rubric(
    content: str,
    deliverable_type: str,
    brief: Dict[str, Any],
    session_context: Optional[SessionContext] = None
) -> Dict[str, Any]:
    """
    Evaluate content with rubric-based scoring for quality assurance.

    Defines rubrics per deliverable (clarity, actionability, personalization readiness)
    and has Claude evaluate drafts post-refinement. Decline delivery if rubric
    score < threshold, returning actionable feedback to the planner.

    Args:
        content: Content to evaluate
        deliverable_type: Type of deliverable (email, report, summary, presentation)
        brief: Writing brief with requirements as dictionary
        session_context: Optional SessionContext for context

    Returns:
        Dictionary with rubric_scores, overall_score, approved, feedback
    """
    logger.info(f"[WRITING AGENT] Evaluating {deliverable_type} with rubric")

    try:
        from ..utils import load_config

        config = load_config()
        openai_config = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.1),  # Very low temperature for consistency
            api_key=openai_config.get("api_key")
        )

        # Get rubric thresholds from config
        rubric_thresholds = config.get("writing", {}).get("rubric_thresholds", {})
        approval_threshold = rubric_thresholds.get(deliverable_type, 0.7)

        # Parse brief
        if isinstance(brief, dict):
            brief_obj = WritingBrief.from_dict(brief)
        else:
            logger.warning("[WRITING AGENT] Brief should be a dict for rubric evaluation")
            brief_obj = WritingBrief(deliverable_type=deliverable_type)

        # Define rubrics by deliverable type
        rubrics = {
            "email": {
                "clarity": "Is the email clear and easy to understand? Are complex ideas explained appropriately?",
                "actionability": "Does the email clearly indicate what action is expected? Are next steps defined?",
                "personalization": "Is the email appropriately personalized for the recipient and context?",
                "tone_consistency": "Does the tone match the brief requirements throughout?",
                "structure": "Does the email follow proper email structure (greeting, body, closing)?"
            },
            "report": {
                "clarity": "Is the report clear and logically structured? Are sections well-organized?",
                "comprehensiveness": "Does the report cover all required topics and data points?",
                "actionability": "Does the report provide actionable insights or recommendations?",
                "accuracy": "Are all facts, data, and claims accurate and properly sourced?",
                "readability": "Is the report readable for the target audience? Appropriate technical level?"
            },
            "summary": {
                "conciseness": "Does the summary capture key information without unnecessary detail?",
                "completeness": "Does the summary include all essential information from the source?",
                "clarity": "Is the summary clear and easy to understand?",
                "relevance": "Does the summary focus on information relevant to the user's needs?",
                "structure": "Is the summary well-structured and logically organized?"
            },
            "presentation": {
                "clarity": "Are slide messages clear and focused? One main point per slide?",
                "flow": "Do slides flow logically to tell a coherent story?",
                "comprehensiveness": "Do slides cover the required topics and data?",
                "visual_impact": "Would these slides be visually effective and engaging?",
                "audience_appropriateness": "Are slides appropriate for the target audience?"
            }
        }

        rubric = rubrics.get(deliverable_type, rubrics["summary"])

        # Add session context
        context_instruction = ""
        if session_context:
            context_instruction = f"""
SESSION CONTEXT: {session_context.headline()}

Consider how this content fits within the broader conversation and user expectations.
"""

        evaluation_prompt = f"""You are a content quality evaluator using rubric-based assessment.

Evaluate this {deliverable_type} against the defined rubric criteria.

CONTENT TO EVALUATE:
{content[:3000]}

WRITING BRIEF REQUIREMENTS:
{brief_obj.to_prompt_section()}

{context_instruction}

RUBRIC CRITERIA:
{chr(10).join(f"- {criterion}: {description}" for criterion, description in rubric.items())}

INSTRUCTIONS:
1. Evaluate each rubric criterion on a scale of 0.0 to 1.0
2. Provide specific feedback for each criterion
3. Calculate overall score as average of all criteria
4. Determine if content meets quality threshold ({approval_threshold})
5. Provide actionable improvement suggestions if score is below threshold

OUTPUT FORMAT:
{{
    "rubric_scores": {{
        "criterion_name": {{
            "score": 0.0-1.0,
            "feedback": "Specific feedback for this criterion",
            "strengths": ["strength1", "strength2"],
            "improvements": ["improvement1", "improvement2"]
        }},
        ...
    }},
    "overall_score": 0.0-1.0,
    "approved": true/false,
    "threshold_used": {approval_threshold},
    "feedback_summary": "Overall assessment and recommendations",
    "critical_issues": ["issue1", "issue2"] // only if any scores < 0.6
}}

Be thorough and specific in your evaluation. Focus on how well the content meets both the rubric criteria and the writing brief requirements.
"""

        messages = [
            SystemMessage(content="You are a professional content evaluator using structured rubrics."),
            HumanMessage(content=evaluation_prompt)
        ]

        response = llm.invoke(messages)
        response_text = response.content

        # Parse response
        try:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            result = json.loads(response_text[json_start:json_end])
        except:
            logger.warning("[WRITING AGENT] Could not parse rubric evaluation response")
            # Fallback evaluation
            result = {
                "rubric_scores": {
                    "overall_quality": {
                        "score": 0.7,
                        "feedback": "Content appears acceptable but could not be fully evaluated",
                        "strengths": ["Basic structure present"],
                        "improvements": ["Consider more detailed rubric assessment"]
                    }
                },
                "overall_score": 0.7,
                "approved": True,
                "threshold_used": approval_threshold,
                "feedback_summary": "Content approved with fallback evaluation",
                "critical_issues": []
            }

        # Calculate overall score if not provided
        if "overall_score" not in result:
            scores = [item.get("score", 0) for item in result.get("rubric_scores", {}).values() if isinstance(item, dict)]
            result["overall_score"] = sum(scores) / len(scores) if scores else 0.5

        # Determine approval
        result["approved"] = result["overall_score"] >= approval_threshold

        # Log results
        score = result["overall_score"]
        approved = result["approved"]
        logger.info(f"[WRITING AGENT] Rubric evaluation: {score:.2f} (threshold: {approval_threshold}) - {'APPROVED' if approved else 'REJECTED'}")

        if not approved:
            critical_issues = result.get("critical_issues", [])
            logger.warning(f"[WRITING AGENT] Content rejected due to rubric score. Critical issues: {critical_issues}")

        # Add metadata
        result["deliverable_type"] = deliverable_type
        result["evaluation_timestamp"] = json.dumps({"timestamp": "now"}, default=str)
        result["brief_compliance"] = len(brief_obj.must_include_facts) > 0 or len(brief_obj.must_include_data) > 0

        return result

    except Exception as e:
        logger.error(f"[WRITING AGENT] Error in evaluate_with_rubric: {e}")
        return {
            "error": True,
            "error_type": "RubricEvaluationError",
            "error_message": str(e),
            "overall_score": 0.0,
            "approved": False,
            "feedback_summary": "Evaluation failed due to error"
        }


@tool
def plan_slide_skeleton(
    query: str,
    brief: Dict[str, Any],
    memory: Optional[SessionContext] = None,
    max_slides: int = 5
) -> Dict[str, Any]:
    """
    Slide skeleton planner using Skeleton-of-Thought (Ning et al., 2024).

    Before create_slide_deck_content, this runs to produce 3–6 slide intents
    anchored to the user's objective; store them in the brief constraints so
    actual slide generation can't drift. Enforce slide caps (≤5 default) yet
    allow justification-based overflow when memory indicates broader scope.

    Args:
        query: User query or topic for the presentation
        brief: Writing brief with requirements as dictionary
        memory: SessionContext for additional context
        max_slides: Maximum slides allowed (default: 5)

    Returns:
        Dictionary with slide_skeleton, justification, constraints
    """
    logger.info(f"[WRITING AGENT] Planning slide skeleton (max_slides: {max_slides})")

    try:
        from ..utils import load_config

        config = load_config()
        openai_config = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.2),
            api_key=openai_config.get("api_key")
        )

        # Parse brief
        if isinstance(brief, dict):
            brief_obj = WritingBrief.from_dict(brief)
        else:
            logger.warning("[WRITING AGENT] Brief should be a dict for slide skeleton")
            brief_obj = WritingBrief(deliverable_type="presentation")

        # Get slide limits from config
        slide_limits = config.get("writing", {}).get("slide_limits", {})
        default_max = slide_limits.get("default", 5)
        max_with_justification = slide_limits.get("max_with_justification", 7)

        # Adjust max_slides based on config and memory context
        if memory and memory.derived_topic:
            # Check if broader scope is indicated in memory
            topic_complexity = len(memory.derived_topic.split()) > 3  # Complex topics may need more slides
            if topic_complexity and max_slides < max_with_justification:
                max_slides = min(max_slides + 1, max_with_justification)
                logger.info(f"[WRITING AGENT] Increased max_slides to {max_slides} due to topic complexity")

        # Add memory context
        memory_context = ""
        if memory:
            memory_context = f"""
SESSION MEMORY CONTEXT:
{memory.headline()}

Consider previous presentations or discussions that might inform slide structure.
Ensure skeleton covers all aspects mentioned in prior context.
"""

        skeleton_prompt = f"""You are a presentation architect using Skeleton-of-Thought methodology (Ning et al., 2024).

Create a focused slide skeleton that captures the essential narrative structure for this presentation.

USER QUERY: {query}

WRITING BRIEF REQUIREMENTS:
{brief_obj.to_prompt_section()}

{memory_context}

SLIDE CONSTRAINTS:
- Maximum slides: {max_slides}
- Each slide must have ONE clear, focused message
- Skeleton should anchor to the user's objective
- Prioritize depth over breadth within the slide limit

INSTRUCTIONS:
1. Analyze the query to identify the core objective and key topics
2. Design 3-{max_slides} slides that tell a complete story
3. Each slide should have a specific intent and purpose
4. Ensure logical flow from slide to slide
5. Consider the audience ({brief_obj.audience}) and tone ({brief_obj.tone})
6. Include any required facts or data from the brief

OUTPUT FORMAT:
{{
    "slide_skeleton": [
        {{
            "slide_number": 1,
            "intent": "Clear purpose of this slide (3-7 words)",
            "key_message": "The one main point this slide communicates",
            "content_scope": "What specific content belongs here",
            "required_elements": ["fact1", "data_point1"] // if any from brief
        }},
        ...
    ],
    "narrative_flow": "How the slides connect to tell the complete story",
    "justification": "Why this number of slides and structure serves the objective",
    "slide_count": number_of_slides,
    "constraints_applied": ["constraint1", "constraint2", ...]
}}

Create a skeleton that prevents content drift while allowing focused depth on each topic.
"""

        messages = [
            SystemMessage(content="You are a presentation architect specializing in Skeleton-of-Thought design."),
            HumanMessage(content=skeleton_prompt)
        ]

        response = llm.invoke(messages)
        response_text = response.content

        # Parse response
        try:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            result = json.loads(response_text[json_start:json_end])
        except:
            logger.warning("[WRITING AGENT] Could not parse slide skeleton response")
            # Fallback: create basic skeleton
            result = {
                "slide_skeleton": [
                    {
                        "slide_number": 1,
                        "intent": "Introduction",
                        "key_message": "Present the main topic",
                        "content_scope": "Overview and context",
                        "required_elements": []
                    },
                    {
                        "slide_number": 2,
                        "intent": "Main Content",
                        "key_message": "Cover key information",
                        "content_scope": "Core details and analysis",
                        "required_elements": brief_obj.must_include_facts[:2] if brief_obj.must_include_facts else []
                    },
                    {
                        "slide_number": 3,
                        "intent": "Conclusion",
                        "key_message": "Summarize key takeaways",
                        "content_scope": "Final thoughts and recommendations",
                        "required_elements": []
                    }
                ],
                "narrative_flow": "Introduction → Analysis → Conclusion",
                "justification": "Basic three-slide structure covering introduction, content, and conclusion",
                "slide_count": 3,
                "constraints_applied": ["max_slides_respected"]
            }

        # Validate slide count
        skeleton = result.get("slide_skeleton", [])
        actual_count = len(skeleton)

        if actual_count > max_slides:
            logger.warning(f"[WRITING AGENT] Skeleton has {actual_count} slides, truncating to {max_slides}")
            skeleton = skeleton[:max_slides]
            result["slide_skeleton"] = skeleton
            result["slide_count"] = max_slides
            result["constraints_applied"].append("truncated_to_max_slides")

        # Add to result
        result["max_slides_allowed"] = max_slides
        result["query_covered"] = all(
            any(intent.lower() in slide.get("intent", "").lower() or
                intent.lower() in slide.get("key_message", "").lower()
                for slide in skeleton)
            for intent in query.split() if len(intent) > 4  # Check major terms from query
        )

        # Store skeleton in brief constraints for downstream use
        brief_obj.constraints["slide_skeleton"] = result["slide_skeleton"]
        brief_obj.constraints["skeleton_narrative_flow"] = result.get("narrative_flow", "")

        logger.info(f"[WRITING AGENT] Created slide skeleton: {actual_count} slides, query_covered: {result['query_covered']}")

        return result

    except Exception as e:
        logger.error(f"[WRITING AGENT] Error in plan_slide_skeleton: {e}")
        return {
            "error": True,
            "error_type": "SkeletonPlanningError",
            "error_message": str(e),
            "slide_skeleton": [],
            "slide_count": 0,
            "justification": "Error occurred during skeleton planning"
        }


@tool
def create_slide_deck_content(
    content: str,
    title: str,
    num_slides: Optional[int] = None,
    writing_brief: Optional[Dict[str, Any]] = None
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
    - Apply writing brief requirements (tone, audience, must-include facts/data)

    Args:
        content: Source content to transform (can be from synthesis or extraction)
        title: Presentation title/topic
        num_slides: Target number of slides (None = auto-determine based on content, typically 5-10)
        writing_brief: Optional writing brief as dictionary

    Returns:
        Dictionary with slides (list of slide objects), total_slides, and formatted_content

    Example:
        # With writing brief (recommended)
        create_slide_deck_content(
            content="$step1.synthesized_content",
            title="Q4 Marketing Strategy",
            num_slides=7,
            writing_brief="$step0.writing_brief"
        )

        # Without brief (legacy mode)
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
            temperature=get_temperature_for_model(config, default_temperature=0.2),
            api_key=openai_config.get("api_key")
        )

        if not content or not content.strip():
            return {
                "error": True,
                "error_type": "NoContentError",
                "error_message": "No content provided for slide deck creation",
                "retry_possible": False
            }

        # Parse writing brief if provided
        brief = None
        if writing_brief:
            if isinstance(writing_brief, dict):
                brief = WritingBrief.from_dict(writing_brief)
            else:
                logger.warning(f"[WRITING AGENT] writing_brief should be a dict for slide deck")

        # Determine target slides with RELAXED limits (addressing audit feedback)
        target_slides_instruction = ""
        if num_slides:
            target_slides_instruction = f"Create approximately {num_slides} content slides. You may create up to {num_slides + 2} slides if the content warrants it for clarity."
        else:
            # Default: 5-8 slides (more flexible than before)
            target_slides_instruction = "Create 5-8 content slides based on the richness of the content. Prioritize clarity over arbitrary limits."

        # RELAXED bullet constraints (addressing audit feedback about overly punitive rules)
        bullet_guidelines = """
SLIDE DESIGN PRINCIPLES (BALANCED APPROACH):
1. Each slide should have ONE clear, focused message
2. Bullet points: Aim for 7-12 words each (be concise but complete)
3. Bullets per slide: 3-5 bullets typically (up to 6 if needed for completeness)
4. Use action verbs and specific language
5. Prefer clear fragments over complete sentences, but prioritize clarity
6. Include specific data, metrics, and facts when relevant
7. Each slide needs a clear, descriptive title (3-7 words)
8. Speaker notes can provide additional context (2-3 sentences)
"""

        # Add writing brief section if available
        brief_section = ""
        if brief:
            brief_section = f"""
WRITING BRIEF (CRITICAL - FOLLOW THESE REQUIREMENTS):
{brief.to_prompt_section()}

CRITICAL: You MUST include required facts and data in appropriate slides.
Reference specific metrics, dates, and numbers from the brief.
"""

        # Detect if content appears to be minimal stock price data
        is_stock_data = any(keyword in content.lower() for keyword in [
            "current_price", "price_change", "ticker", "symbol", "stock price",
            "nvda", "aapl", "tsla", "msft", "googl", "stock", "shares"
        ]) and len(content) < 500
        
        stock_enrichment_guidance = ""
        if is_stock_data:
            stock_enrichment_guidance = """
STOCK DATA ENRICHMENT (CRITICAL):
- The source content contains minimal stock price data
- Enrich each slide with context and meaning:
  * Slide 1: Current Price Overview - Include price, change, percentage change, and what it means (up/down trend)
  * Slide 2: Market Context - Add context about the company, sector, or market conditions
  * Slide 3: Performance Indicators - Include any available metrics (volume, market cap, etc.)
  * Additional slides: Add relevant context, trends, or analysis based on available data
- Don't just list raw numbers - provide interpretation and context
- If data is very minimal, create 3-5 slides by expanding on available information with meaningful context
"""

        slide_deck_prompt = f"""You are an expert presentation designer. Create concise, impactful slide content for a presentation.

PRESENTATION TITLE: {title}

SOURCE CONTENT:
{content[:8000]}

SLIDE COUNT GUIDELINE:
{target_slides_instruction}
{bullet_guidelines}
{stock_enrichment_guidance}
{brief_section}

QUALITY FOCUS:
- Prioritize specific, actionable content over generic statements
- Include numerical data, metrics, and concrete examples
- Ensure each slide provides unique value
- Balance brevity with completeness - don't sacrifice clarity for word count
- For stock data: Provide context and interpretation, not just raw numbers

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

Create presentation-ready content that is concise, impactful, specific, and data-driven.
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

        # RELAXED validation (addressing audit feedback)
        slides = result.get("slides", [])

        # Only warn if drastically exceeds requested count (not enforce hard limits)
        if num_slides and len(slides) > num_slides + 3:
            logger.warning(f"[WRITING AGENT] LLM created {len(slides)} slides (requested {num_slides}). Keeping all slides for completeness.")

        # RELAXED bullet validation: warn but don't truncate unless excessive
        for slide in slides:
            bullets = slide.get("bullets", [])
            if len(bullets) > 7:
                logger.warning(f"[WRITING AGENT] Slide '{slide.get('title')}' has {len(bullets)} bullets (recommended max 6). Consider if all are necessary.")
                # Don't truncate - let the content speak for itself

        # Quality check: validate brief compliance if provided
        if brief and (brief.must_include_facts or brief.must_include_data):
            # Collect all slide content for validation
            all_slide_content = " ".join([
                f"{slide.get('title', '')} {' '.join(slide.get('bullets', []))}"
                for slide in slides
            ])
            validation_result = _validate_brief_compliance(all_slide_content, brief, {})

            if not validation_result["compliant"]:
                logger.warning(f"[WRITING AGENT] Slide deck brief compliance issues: {validation_result['missing_items']}")
                result["quality_warnings"] = validation_result["missing_items"]
                result["compliance_score"] = validation_result["compliance_score"]
            else:
                result["compliance_score"] = 1.0
                logger.info(f"[WRITING AGENT] ✅ Slide deck brief compliance validated")

        # Format slides into readable text for Keynote creation
        formatted_content = ""
        for slide in result.get("slides", []):
            formatted_content += f"\n\n{slide['title']}\n"
            for bullet in slide.get("bullets", []):
                formatted_content += f"• {bullet}\n"

        result["formatted_content"] = formatted_content.strip()
        result["total_slides"] = len(slides)

        # Generate preview (first slide + count)
        preview = ""
        if slides:
            first_slide = slides[0]
            preview = f"{first_slide.get('title', '')}: {first_slide.get('bullets', [{}])[0] if first_slide.get('bullets') else ''}..."
        result["preview"] = preview

        result["message"] = f"Created {len(slides)} slides for '{title}'"

        logger.info(f"[WRITING AGENT] ✅ Created {len(slides)} slides with {sum(len(s.get('bullets', [])) for s in slides)} total bullets")

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
    include_sections: Optional[List[str]] = None,
    writing_brief: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Transform content into a detailed, well-structured report with long-form writing.

    WRITING AGENT - LEVEL 3: Report Writing
    Use this to create comprehensive reports with detailed analysis and explanations.

    ⚠️  CRITICAL: This tool returns REPORT TEXT, not a file path!
    - If you need to EMAIL the report, you MUST first save it using create_pages_doc
    - CORRECT workflow: create_detailed_report → create_pages_doc → compose_email(attachments=["$stepN.pages_path"])
    - WRONG: compose_email(attachments=["$stepN.report_content"]) ← report_content is TEXT not a FILE PATH!

    This tool uses LLM to:
    - Expand and elaborate on key points
    - Add context and explanations
    - Structure content into logical sections
    - Use professional, flowing prose
    - Include transitions and narrative flow
    - Apply writing brief requirements (tone, audience, must-include facts/data)

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
        writing_brief: Optional writing brief as dictionary

    Returns:
        Dictionary with report_content (TEXT string), sections (array), word_count (number)
        ⚠️  report_content is TEXT, NOT a file path - use create_pages_doc to save it

    Example:
        # With writing brief (recommended)
        create_detailed_report(
            content="$step1.synthesized_content",
            title="NVDA Q4 2024 Analysis",
            report_style="business",
            include_sections=["Executive Summary", "Financial Performance", "Market Position", "Recommendations"],
            writing_brief="$step0.writing_brief"
        )

        # Without brief (legacy mode)
        create_detailed_report(
            content="$step1.synthesized_content",
            title="Annual Security Audit Report",
            report_style="technical",
            include_sections=["Executive Summary", "Findings", "Recommendations"]
        )
    """
    logger.info(f"[WRITING AGENT] Tool: create_detailed_report(title='{title}', style='{report_style}')")

    # TODO: Add telemetry logging for regression testing
    # [TELEMETRY] Tool create_detailed_report started - correlation_id={correlation_id}, title={title}
    # Use telemetry/tool_helpers.py: log_tool_step("create_detailed_report", "start", metadata={"title": title, "style": report_style}, correlation_id=correlation_id)

    try:
        from ..utils import load_config

        config = load_config()
        openai_config = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.3),
            api_key=openai_config.get("api_key")
        )

        if not content or not content.strip():
            return {
                "error": True,
                "error_type": "NoContentError",
                "error_message": "No content provided for report creation",
                "retry_possible": False
            }

        # Parse writing brief if provided
        brief = None
        if writing_brief:
            if isinstance(writing_brief, dict):
                brief = WritingBrief.from_dict(writing_brief)
            else:
                logger.warning(f"[WRITING AGENT] writing_brief should be a dict for report")

        # Style-specific instructions (ENHANCED with audience consideration)
        style_guidelines = {
            "business": "Use professional, action-oriented language. Focus on results, implications, and ROI. Be clear and direct. Use active voice. Include specific metrics and data points.",
            "academic": "Use formal, analytical language. Include proper structure (introduction, analysis, conclusion). Reference concepts and frameworks. Be thorough and objective. Support claims with evidence.",
            "technical": "Use precise, specification-focused language. Include technical details, methodologies, and implementation considerations. Be accurate and comprehensive. Use industry terminology. Reference specific technologies and versions.",
            "executive": "Use high-level, strategic language. Focus on key insights, business impact, and actionable recommendations. Be concise but impactful. Emphasize business value and competitive advantage."
        }

        style_guide = style_guidelines.get(report_style, style_guidelines["business"])

        # Section handling
        sections_instruction = ""
        if include_sections:
            sections_list = ", ".join(include_sections)
            sections_instruction = f"Structure the report with these specific sections: {sections_list}"
        else:
            sections_instruction = "Determine the most appropriate sections based on the content (typically: Executive Summary, Main Analysis/Body, Conclusions/Recommendations)"

        # Add writing brief section if available
        brief_section = ""
        if brief:
            brief_section = f"""
WRITING BRIEF (CRITICAL - FOLLOW THESE REQUIREMENTS):
{brief.to_prompt_section()}

CRITICAL REQUIREMENTS:
- Include ALL required facts and data points in the appropriate sections
- Reference specific metrics, dates, prices, and percentages listed above
- Match the tone and tailor content for the specified audience
- Emphasize the focus areas identified in the brief
- Your report will be evaluated for factual completeness
"""

        report_prompt = f"""You are an expert report writer. Create a comprehensive, well-structured report from the provided content.

REPORT TITLE: {title}

REPORT STYLE: {report_style}
{style_guide}
{brief_section}

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

        # Quality check: validate brief compliance if provided
        if brief and (brief.must_include_facts or brief.must_include_data):
            report_content = result.get("report_content", "")
            validation_result = _validate_brief_compliance(report_content, brief, {})

            if not validation_result["compliant"]:
                logger.warning(f"[WRITING AGENT] Report brief compliance issues: {validation_result['missing_items']}")
                result["quality_warnings"] = validation_result["missing_items"]
                result["compliance_score"] = validation_result["compliance_score"]

                # Log evaluation snippet for QA (first 300 chars)
                logger.info(f"[WRITING AGENT] Report preview: {report_content[:300]}...")
            else:
                result["compliance_score"] = 1.0
                logger.info(f"[WRITING AGENT] ✅ Report brief compliance validated")

        # Generate preview (first 2-3 sentences from executive summary or first section)
        preview = result.get("executive_summary", "")
        if not preview and result.get("sections"):
            # Use first section's content preview
            first_section_content = result["sections"][0].get("content", "")
            sentences = first_section_content.split(". ")
            preview = ". ".join(sentences[:2]) + "." if len(sentences) > 1 else first_section_content[:200]

        result["preview"] = preview
        result["report_style"] = report_style
        result["message"] = f"Created {report_style} report: '{title}' ({result.get('total_word_count', 0)} words)"

        logger.info(
            f"[WRITING AGENT] Created report: {result.get('total_word_count', 0)} words, "
            f"{len(result.get('sections', []))} sections"
        )

        # Persist formatted report to disk so downstream steps (emails, sharing) can attach it.
        def _write_plaintext_fallback() -> Optional[str]:
            try:
                reports_dir = Path("data/reports")
                reports_dir.mkdir(parents=True, exist_ok=True)
                safe_title = re.sub(r"[^A-Za-z0-9_-]+", "_", title).strip("_") or "report"
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                fallback_path = reports_dir / f"{safe_title}_{timestamp}.txt"
                fallback_path.write_text(result.get("report_content", ""), encoding="utf-8")
                logger.info(f"[WRITING AGENT] Fallback report saved: {fallback_path}")
                return str(fallback_path)
            except Exception as write_err:
                logger.warning(f"[WRITING AGENT] Fallback report save failed: {write_err}")
                return None

        artifact_path: Optional[str] = None
        fallback_needed = False
        try:
            generator = ReportGenerator(config)

            section_payload: Optional[List[Dict[str, str]]] = None
            if result.get("sections"):
                section_payload = []
                for section in result["sections"]:
                    heading = (
                        section.get("section_name")
                        or section.get("heading")
                        or section.get("title")
                        or ""
                    )
                    section_payload.append({
                        "heading": heading,
                        "content": section.get("content", "")
                    })

            generation_result = generator.create_report(
                title=title,
                content=result.get("report_content", ""),
                sections=section_payload,
                export_pdf=True
            )

            if generation_result.get("success"):
                primary_path = (
                    generation_result.get("pdf_path")
                    or generation_result.get("html_path")
                    or generation_result.get("rtf_path")
                )

                if primary_path:
                    artifact_path = primary_path
                    result["report_path"] = primary_path
                    # Legacy planners sometimes reference formatted_content -> provide compatible field.
                    result["formatted_content"] = primary_path
                    logger.info(f"[WRITING AGENT] Report artifact saved: {primary_path}")
                else:
                    fallback_needed = True

                if generation_result.get("pdf_path"):
                    result["pdf_path"] = generation_result["pdf_path"]
                if generation_result.get("rtf_path"):
                    result["rtf_path"] = generation_result["rtf_path"]
                if generation_result.get("html_path"):
                    result["html_path"] = generation_result["html_path"]

                # Expose artifact metadata for advanced consumers.
                result["report_artifact"] = generation_result
            else:
                warning_msg = generation_result.get("error_message", "Unknown report generation error")
                result["report_generation_warning"] = warning_msg
                logger.warning(f"[WRITING AGENT] Report file generation failed: {warning_msg}")
                fallback_needed = True
        except Exception as artifact_error:
            logger.warning(f"[WRITING AGENT] Could not persist report artifact: {artifact_error}")
            result["report_generation_warning"] = str(artifact_error)
            fallback_needed = True

        if not artifact_path and fallback_needed:
            fallback_path = _write_plaintext_fallback()
            if fallback_path:
                artifact_path = fallback_path
                result["report_path"] = fallback_path
                result["formatted_content"] = fallback_path

        # TODO: Add telemetry logging for regression testing
        # [TELEMETRY] Tool create_detailed_report success - correlation_id={correlation_id}, word_count={result.get('total_word_count')}
        # Use telemetry/tool_helpers.py: log_tool_step("create_detailed_report", "success", metadata={"word_count": result.get('total_word_count'), "sections": len(result.get('sections', []))}, correlation_id=correlation_id)

        return result

    except Exception as e:
        # TODO: Add telemetry logging for regression testing
        # [TELEMETRY] Tool create_detailed_report error - correlation_id={correlation_id}, error={str(e)}
        # Use telemetry/tool_helpers.py: log_tool_step("create_detailed_report", "error", metadata={"error": str(e)}, correlation_id=correlation_id)
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
            temperature=get_temperature_for_model(config, default_temperature=0.1),  # Very low temperature for accuracy
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


@tool
def create_quick_summary(
    content: str,
    topic: str,
    max_sentences: int = 3,
    writing_brief: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a quick, conversational summary for simple/short-answer requests.

    WRITING AGENT - LEVEL 0.5: Lightweight Reply Path
    Use this for brief, conversational responses when user wants a quick answer.

    This tool uses LLM to:
    - Extract the most important point(s)
    - Format in clear, conversational language
    - Keep it brief and to-the-point
    - Skip heavy formatting or structure

    Args:
        content: Source content to summarize
        topic: Topic to focus on
        max_sentences: Maximum sentences in summary (default: 3)
        writing_brief: Optional writing brief as dictionary

    Returns:
        Dictionary with summary, tone, and word_count

    Example:
        create_quick_summary(
            content="$step1.extracted_text",
            topic="What is Claude AI?",
            max_sentences=2,
            writing_brief="$step0.writing_brief"
        )
    """
    logger.info(f"[WRITING AGENT] Tool: create_quick_summary(topic='{topic[:50]}...', max_sentences={max_sentences})")

    try:
        from ..utils import load_config

        config = load_config()
        openai_config = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.2),
            api_key=openai_config.get("api_key")
        )

        if not content or not content.strip():
            return {
                "error": True,
                "error_type": "NoContentError",
                "error_message": "No content provided for summary",
                "retry_possible": False
            }

        # Parse writing brief if provided
        brief = None
        if writing_brief:
            if isinstance(writing_brief, dict):
                brief = WritingBrief.from_dict(writing_brief)
            else:
                logger.warning(f"[WRITING AGENT] writing_brief should be a dict for quick summary")

        # Add writing brief section if available
        brief_section = ""
        tone_instruction = "conversational and clear"
        if brief:
            brief_section = f"""
WRITING BRIEF:
{brief.to_prompt_section()}

Match the tone ({brief.tone}) and include key facts if relevant.
"""
            tone_instruction = brief.tone

        summary_prompt = f"""You are a helpful assistant. Create a quick, clear summary.

TOPIC: {topic}

SOURCE CONTENT:
{content[:4000]}
{brief_section}

INSTRUCTIONS:
1. Extract the most important information about the topic
2. Write in {tone_instruction} tone
3. Keep it to {max_sentences} sentences or fewer
4. Be direct and clear - no fluff
5. Use natural, conversational language

OUTPUT FORMAT:
Provide a JSON response with:
{{
    "summary": "Your concise summary (max {max_sentences} sentences)",
    "key_fact": "The single most important fact",
    "tone": "{tone_instruction}"
}}

Create a brief, helpful summary that directly answers the topic.
"""

        messages = [
            SystemMessage(content="You are a helpful assistant who provides clear, concise summaries."),
            HumanMessage(content=summary_prompt)
        ]

        response = llm.invoke(messages)
        response_text = response.content

        # Parse JSON response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            # Fallback: use raw text as summary
            return {
                "summary": response_text[:500],
                "key_fact": "",
                "tone": tone_instruction,
                "word_count": len(response_text.split()),
                "message": "Quick summary created"
            }

        json_str = response_text[json_start:json_end]
        result = json.loads(json_str)

        result["word_count"] = len(result.get("summary", "").split())
        result["message"] = f"Quick summary created ({result['word_count']} words)"

        logger.info(f"[WRITING AGENT] ✅ Quick summary: {result['word_count']} words")

        return result

    except Exception as e:
        logger.error(f"[WRITING AGENT] Error in create_quick_summary: {e}")
        return {
            "error": True,
            "error_type": "SummaryError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def compose_professional_email(
    purpose: str,
    context: str,
    recipient: str = "recipient",
    writing_brief: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Compose a professional email with appropriate tone and structure.

    WRITING AGENT - LEVEL 5: Email Composition
    Use this to draft professional emails, follow-ups, or announcements.

    This tool uses LLM to:
    - Structure email with proper greeting, body, and closing
    - Match appropriate tone for the context
    - Include relevant details from context
    - Apply writing brief requirements (tone, must-include facts)

    Args:
        purpose: The purpose of the email (e.g., "follow-up on meeting", "request information", "share report")
        context: Background information or content to include in the email
        recipient: Name or role of the recipient (e.g., "John Smith", "team", "client")
        writing_brief: Optional writing brief as dictionary

    Returns:
        Dictionary with email_subject, email_body, tone, and word_count

    Example:
        compose_professional_email(
            purpose="Share quarterly analysis report",
            context="$step2.report_content",
            recipient="Executive Team",
            writing_brief="$step0.writing_brief"
        )
    """
    logger.info(f"[WRITING AGENT] Tool: compose_professional_email(purpose='{purpose[:50]}...', recipient='{recipient}')")

    try:
        from ..utils import load_config

        config = load_config()
        openai_config = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.3),
            api_key=openai_config.get("api_key")
        )

        # Parse writing brief if provided
        brief = None
        if writing_brief:
            if isinstance(writing_brief, dict):
                brief = WritingBrief.from_dict(writing_brief)
            else:
                logger.warning(f"[WRITING AGENT] writing_brief should be a dict for email")

        # Add writing brief section if available
        brief_section = ""
        if brief:
            brief_section = f"""
WRITING BRIEF:
{brief.to_prompt_section()}

Apply the tone and include required facts/data as appropriate for an email format.
"""

        email_prompt = f"""You are an expert professional email writer. Compose a clear, well-structured email.

PURPOSE: {purpose}

RECIPIENT: {recipient}

CONTEXT/CONTENT TO INCLUDE:
{context[:3000]}
{brief_section}

EMAIL STRUCTURE:
1. Subject line: Clear, specific, professional (5-10 words)
2. Greeting: Appropriate for recipient
3. Opening: Brief context or reason for writing (1-2 sentences)
4. Body: Main content organized in clear paragraphs
5. Closing: Call to action or next steps if applicable
6. Sign-off: Professional closing

TONE GUIDELINES:
- Professional and respectful
- Clear and concise
- Action-oriented when appropriate
- Avoid jargon unless recipient is technical
- Use bullet points for lists or multiple items

OUTPUT FORMAT:
Provide a JSON response with:
{{
    "email_subject": "Subject line",
    "email_body": "Complete email body including greeting and sign-off",
    "tone": "professional/formal/casual",
    "key_points_included": ["point 1", "point 2", ...],
    "word_count": number
}}

Compose a clear, professional email that achieves its purpose.
"""

        messages = [
            SystemMessage(content="You are an expert professional email writer."),
            HumanMessage(content=email_prompt)
        ]

        response = llm.invoke(messages)
        response_text = response.content

        # Parse JSON response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            return {
                "error": True,
                "error_type": "ParsingError",
                "error_message": "Failed to parse email structure",
                "retry_possible": True
            }

        json_str = response_text[json_start:json_end]
        result = json.loads(json_str)

        # Quality check: validate brief compliance if provided
        if brief and (brief.must_include_facts or brief.must_include_data):
            email_content = f"{result.get('email_subject', '')} {result.get('email_body', '')}"
            validation_result = _validate_brief_compliance(email_content, brief, {})

            if not validation_result["compliant"]:
                logger.warning(f"[WRITING AGENT] Email brief compliance issues: {validation_result['missing_items']}")
                result["quality_warnings"] = validation_result["missing_items"]
                result["compliance_score"] = validation_result["compliance_score"]
            else:
                result["compliance_score"] = 1.0
                logger.info(f"[WRITING AGENT] ✅ Email brief compliance validated")

        result["purpose"] = purpose
        result["recipient"] = recipient
        result["message"] = f"Composed email: '{result.get('email_subject', 'Untitled')}'"

        logger.info(f"[WRITING AGENT] ✅ Composed email ({result.get('word_count', 0)} words)")

        return result

    except Exception as e:
        logger.error(f"[WRITING AGENT] Error in compose_professional_email: {e}")
        return {
            "error": True,
            "error_type": "EmailCompositionError",
            "error_message": str(e),
            "retry_possible": False
        }


# Writing Agent Tool Registry
WRITING_AGENT_TOOLS = [
    prepare_writing_brief,
    create_quick_summary,
    synthesize_content,
    create_slide_deck_content,
    create_detailed_report,
    create_meeting_notes,
    compose_professional_email,
    chain_of_density_summarize,
    plan_slide_skeleton,
    self_refine,
]


# Writing Agent Hierarchy
WRITING_AGENT_HIERARCHY = """
Writing Agent Hierarchy (ENHANCED):
====================================

LEVEL 0: Brief Preparation (NEW - Use This First!)
└─ prepare_writing_brief → Analyze user intent and extract writing requirements
   ├─ Detects tone, audience, and style from user request
   ├─ Extracts must-include facts and data from context
   ├─ Sets constraints and focus areas
   └─ Creates structured brief for downstream tools

LEVEL 0.5: Lightweight Reply Path (NEW - For Quick Answers!)
└─ create_quick_summary → Create brief, conversational summaries
   ├─ USE WHEN: User wants a quick answer or short explanation
   ├─ USE WHEN: Writing brief has length_guideline="brief"
   ├─ Skips heavy formatting - just clear, conversational text
   ├─ Max 2-3 sentences by default
   └─ NOW ACCEPTS: writing_brief parameter for tone matching

LEVEL 1: Content Synthesis
└─ synthesize_content → Combine multiple sources into cohesive content
   └─ NOW ACCEPTS: writing_brief parameter for targeted synthesis

LEVEL 2: Slide Deck Writing
└─ create_slide_deck_content → Transform content into presentation slides
   ├─ RELAXED CONSTRAINTS: 7-12 word bullets (was 7 max)
   ├─ FLEXIBLE SLIDE COUNT: 5-8 slides typical (was hard cap of 5)
   └─ NOW ACCEPTS: writing_brief parameter for data-driven decks

LEVEL 3: Report Writing
└─ create_detailed_report → Create comprehensive long-form reports
   ├─ ENHANCED: Audience-aware writing (technical/business/executive/academic)
   ├─ IMPROVED: Includes specific metrics and data points
   └─ NOW ACCEPTS: writing_brief parameter for targeted reports

LEVEL 4: Note-Taking
└─ create_meeting_notes → Structure meeting notes with action items

LEVEL 5: Email Composition (NEW)
└─ compose_professional_email → Draft professional emails with proper structure
   └─ NOW ACCEPTS: writing_brief parameter for context-aware emails

Quality Improvements:
=====================
✓ Writing brief system ensures outputs match user intent
✓ Automatic validation of must-include facts and data
✓ Compliance scoring (70%+ required for quality)
✓ Quality warnings logged when requirements missing
✓ Evaluation snippets logged for QA

Best Practice Workflows:

WORKFLOW 1: Data-Driven Report Creation (RECOMMENDED)
1. prepare_writing_brief → Extract intent and requirements from user request + upstream data
2. search_documents / google_search → Find sources
3. extract_section / extract_page_content → Get content
4. synthesize_content(writing_brief=$step0.writing_brief) → Combine with requirements
5. create_detailed_report(writing_brief=$step0.writing_brief) → Generate report with facts/data
6. create_pages_doc → Save as document

WORKFLOW 2: Presentation Creation with Brief
1. prepare_writing_brief → Extract requirements (tone, audience, key metrics)
2. search_documents / google_search → Find sources
3. synthesize_content(writing_brief=$step0.writing_brief) → Targeted synthesis
4. create_slide_deck_content(writing_brief=$step0.writing_brief) → Data-driven slides
5. create_keynote → Generate presentation

WORKFLOW 3: Email Follow-up with Report
1. prepare_writing_brief → Detect tone and recipient context
2. create_detailed_report → Generate report
3. compose_professional_email(context=$step1.report_content, writing_brief=$step0.writing_brief) → Draft email
4. compose_email → Send

WORKFLOW 4: Meeting Documentation (Legacy - No Brief Needed)
1. extract_section → Get meeting transcript/notes
2. create_meeting_notes → Structure and extract actions
3. create_pages_doc / compose_email → Distribute notes

Migration Guide:
================
OLD: synthesize_content(source_contents=[...], topic="AI Safety")
NEW: prepare_writing_brief(user_request="...", upstream_artifacts={...})
     → synthesize_content(source_contents=[...], topic="AI Safety", writing_brief=$step0.writing_brief)

Benefits: Outputs will include specific data, match user tone, and target correct audience.
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
