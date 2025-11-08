"""
Presentation Agent - Handles all presentation creation.

This agent is responsible for:
- Creating Keynote presentations from text
- Creating Keynote presentations with images
- Creating Pages documents

Acts as a mini-orchestrator for presentation-related operations.
"""

from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)


@tool
def create_keynote(
    title: str,
    content: str,
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a Keynote presentation from content.

    PRESENTATION AGENT - LEVEL 1: Text-based Presentations
    Use this to create presentations from text content.

    Args:
        title: Presentation title
        content: Source content to transform into slides
        output_path: Save location (None = default)

    Returns:
        Dictionary with keynote_path and slide_count
    """
    logger.info(f"[PRESENTATION AGENT] Tool: create_keynote(title='{title}')")

    try:
        from ..automation import KeynoteComposer
        from ..utils import load_config

        config = load_config()
        keynote_composer = KeynoteComposer(config)

        # Convert content string to slides format
        slides = []

        # Split content into paragraphs or use as single slide
        if len(content) < 500:
            # Short content - single slide
            slides.append({
                "title": "Overview",
                "content": content
            })
        else:
            # Longer content - split into multiple slides
            paragraphs = content.split('\n\n')
            for i, para in enumerate(paragraphs[:10], 1):  # Max 10 slides
                if para.strip():
                    slides.append({
                        "title": f"Slide {i}",
                        "content": para.strip()
                    })

        # Call the actual keynote composer with slides
        success = keynote_composer.create_presentation(
            title=title,
            slides=slides,
            output_path=output_path
        )

        if success:
            # Construct the path if not provided
            if output_path:
                final_path = output_path
            else:
                import os
                final_path = os.path.expanduser(f"~/Documents/{title}.key")

            return {
                "keynote_path": final_path,
                "slide_count": len(slides) + 1,  # +1 for title slide
                "message": "Keynote presentation created successfully"
            }
        else:
            return {
                "error": True,
                "error_type": "KeynoteError",
                "error_message": "Failed to create Keynote presentation",
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"[PRESENTATION AGENT] Error in create_keynote: {e}")
        return {
            "error": True,
            "error_type": "KeynoteError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def create_keynote_with_images(
    title: str,
    image_paths: List[str],
    content: Optional[str] = None,
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a Keynote presentation with images (screenshots) and optional text content.

    PRESENTATION AGENT - LEVEL 2: Image-based Presentations
    Use this to create presentations from screenshots or images with accompanying text.

    Args:
        title: Presentation title
        image_paths: List of image file paths to add as slides
        content: Optional text content to include in the presentation (formatted slide content)
        output_path: Save location (None = default)

    Returns:
        Dictionary with keynote_path and slide_count
    """
    logger.info(f"[PRESENTATION AGENT] Tool: create_keynote_with_images(title='{title}', images={len(image_paths)}, has_content={content is not None})")

    try:
        from ..automation import KeynoteComposer
        from ..utils import load_config

        config = load_config()
        keynote_composer = KeynoteComposer(config)

        # Create slides with images and optional content
        slides = []

        # If content is provided, parse it and integrate with images
        if content:
            # Parse the formatted content into slides
            content_slides = content.split('\n\n\n')

            # Add content slides (text with bullets)
            for i, content_slide in enumerate(content_slides):
                if content_slide.strip():
                    lines = content_slide.strip().split('\n')
                    slide_title = lines[0] if lines else f"Slide {i+1}"
                    slide_bullets = [line.lstrip('• ').strip() for line in lines[1:] if line.strip()]

                    # Convert bullets to content string for Keynote
                    if slide_bullets:
                        slide_content = '\n'.join([f'• {bullet}' for bullet in slide_bullets])
                    else:
                        slide_content = ''

                    slides.append({
                        "title": slide_title,
                        "content": slide_content
                    })

            # Add image slides separately (Keynote doesn't support text + image on same slide easily)
            import os
            for i, image_path in enumerate(image_paths, 1):
                # Convert to absolute path if relative
                abs_image_path = os.path.abspath(image_path)
                slides.append({
                    "title": f"Supporting Image {i}",
                    "image_path": abs_image_path
                })
        else:
            # No content provided - just create slides with images
            import os
            for i, image_path in enumerate(image_paths, 1):
                # Convert to absolute path if relative
                abs_image_path = os.path.abspath(image_path)
                slides.append({
                    "title": f"Image {i}",
                    "image_path": abs_image_path
                })

        # Determine output path - generate default if not provided
        if not output_path:
            import os
            output_path = os.path.expanduser(f"~/Documents/{title}.key")

        # Call the actual keynote composer with slides
        success = keynote_composer.create_presentation(
            title=title,
            slides=slides,
            output_path=output_path
        )

        if success:
            # Verify the file actually exists
            import os
            if os.path.exists(output_path):
                return {
                    "keynote_path": output_path,
                    "slide_count": len(slides) + 1,  # +1 for title slide
                    "message": f"Keynote presentation created with {len(slides)} image slides"
                }
            else:
                logger.error(f"[PRESENTATION AGENT] Keynote reported success but file not found: {output_path}")
                return {
                    "error": True,
                    "error_type": "KeynoteError",
                    "error_message": f"Keynote file not saved to {output_path}",
                    "retry_possible": False
                }
        else:
            return {
                "error": True,
                "error_type": "KeynoteError",
                "error_message": "Failed to create Keynote presentation with images",
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"[PRESENTATION AGENT] Error in create_keynote_with_images: {e}")
        return {
            "error": True,
            "error_type": "KeynoteError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def create_pages_doc(
    title: str,
    content: str,
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a Pages document from content.

    PRESENTATION AGENT - LEVEL 3: Document Creation
    Use this to create formatted documents.

    Args:
        title: Document title
        content: Source content to format
        output_path: Save location (None = default)

    Returns:
        Dictionary with pages_path and page_count
    """
    logger.info(f"[PRESENTATION AGENT] Tool: create_pages_doc(title='{title}')")

    try:
        from ..automation import PagesComposer
        from ..utils import load_config

        config = load_config()
        pages_composer = PagesComposer(config)

        # Convert string content to sections format expected by PagesComposer
        # Split content into sections based on double newlines or headers
        sections = []

        # Try to parse content intelligently
        if '\n\n' in content:
            # Content has paragraph breaks
            paragraphs = content.split('\n\n')

            for para in paragraphs:
                if para.strip():
                    lines = para.strip().split('\n')
                    # First line could be a heading if it's short and not ending with punctuation
                    if len(lines) > 1 and len(lines[0]) < 60 and not lines[0].endswith(('.', '!', '?')):
                        sections.append({
                            'heading': lines[0],
                            'content': '\n'.join(lines[1:])
                        })
                    else:
                        # Treat whole paragraph as content
                        sections.append({
                            'heading': '',
                            'content': para.strip()
                        })
        else:
            # Single block of content - create one section
            sections.append({
                'heading': '',
                'content': content
            })

        result = pages_composer.create_document(
            title=title,
            sections=sections,
            output_path=output_path
        )

        if result:
            return {
                "pages_path": result.get("file_path", "Unknown"),
                "message": "Pages document created successfully"
            }
        else:
            return {
                "error": True,
                "error_type": "PagesError",
                "error_message": "Failed to create Pages document",
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"[PRESENTATION AGENT] Error in create_pages_doc: {e}")
        return {
            "error": True,
            "error_type": "PagesError",
            "error_message": str(e),
            "retry_possible": False
        }


# Presentation Agent Tool Registry
PRESENTATION_AGENT_TOOLS = [
    create_keynote,
    create_keynote_with_images,
    create_pages_doc,
]


# Presentation Agent Hierarchy
PRESENTATION_AGENT_HIERARCHY = """
Presentation Agent Hierarchy:
============================

LEVEL 1: Text-based Presentations
└─ create_keynote → Create Keynote from text content

LEVEL 2: Image-based Presentations
└─ create_keynote_with_images → Create Keynote from screenshots/images

LEVEL 3: Document Creation
└─ create_pages_doc → Create Pages documents

Typical Workflow:
1. [Text content] → create_keynote(title, content)
2. [Screenshots] → create_keynote_with_images(title, images)
3. [Long-form content] → create_pages_doc(title, content)
"""


class PresentationAgent:
    """
    Presentation Agent - Mini-orchestrator for presentation creation.

    Responsibilities:
    - Creating Keynote presentations from text
    - Creating Keynote presentations from images
    - Creating Pages documents

    This agent acts as a sub-orchestrator that handles all presentation-related tasks.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in PRESENTATION_AGENT_TOOLS}
        logger.info(f"[PRESENTATION AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        """Get all presentation agent tools."""
        return PRESENTATION_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get presentation agent hierarchy documentation."""
        return PRESENTATION_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a presentation agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Presentation agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[PRESENTATION AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[PRESENTATION AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }
