"""
LLM-based intent parser and action planner using GPT-4o.
"""

import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from .prompts import (
    SYSTEM_PROMPT,
    INTENT_PARSING_PROMPT,
    SECTION_EXTRACTION_PROMPT,
    EMAIL_COMPOSITION_PROMPT,
    PRESENTATION_GENERATION_PROMPT,
    DOCUMENT_GENERATION_PROMPT,
)


logger = logging.getLogger(__name__)


class LLMPlanner:
    """
    Uses GPT-4o to parse user intent and generate structured action plans.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the LLM planner.

        Args:
            config: Configuration dictionary with OpenAI settings
        """
        self.config = config
        self.client = OpenAI(api_key=config['openai']['api_key'])
        self.model = config['openai']['model']
        self.temperature = config['openai']['temperature']
        self.max_tokens = config['openai']['max_tokens']

    def parse_intent(self, user_input: str) -> Dict[str, Any]:
        """
        Parse user intent from natural language input.

        Args:
            user_input: Natural language request from user

        Returns:
            Dictionary containing parsed intent and parameters
        """
        logger.info(f"Parsing intent for: {user_input}")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": INTENT_PARSING_PROMPT.format(user_input=user_input),
                    },
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
            logger.info(f"Intent parsed successfully: {result['intent']}")
            return result

        except Exception as e:
            logger.error(f"Error parsing intent: {e}")
            return {
                "intent": "unknown",
                "parameters": {},
                "confidence": 0.0,
                "error": str(e),
            }

    def plan_section_extraction(
        self, document_metadata: Dict[str, Any], section_request: str
    ) -> Dict[str, Any]:
        """
        Plan how to extract a specific section from a document.

        Args:
            document_metadata: Metadata about the document
            section_request: User's section request (e.g., "summary", "page 10")

        Returns:
            Extraction plan with method and parameters
        """
        logger.info(f"Planning extraction for section: {section_request}")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": SECTION_EXTRACTION_PROMPT.format(
                            document_metadata=json.dumps(document_metadata, indent=2),
                            section_request=section_request,
                        ),
                    },
                ],
                temperature=0.3,  # Lower temperature for more deterministic extraction
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
            logger.info(f"Extraction plan: {result['extraction_method']}")
            return result

        except Exception as e:
            logger.error(f"Error planning extraction: {e}")
            return {
                "extraction_method": "full_document",
                "parameters": {},
                "explanation": f"Error: {str(e)}",
            }

    def compose_email(
        self, subject: str, content: str, instructions: str
    ) -> Dict[str, Any]:
        """
        Compose email content using extracted document content.

        Args:
            subject: Email subject
            content: Extracted document content
            instructions: Instructions for email composition

        Returns:
            Dictionary with final subject and body
        """
        logger.info("Composing email content")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": EMAIL_COMPOSITION_PROMPT.format(
                            subject=subject, content=content, instructions=instructions
                        ),
                    },
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
            logger.info("Email composed successfully")
            return result

        except Exception as e:
            logger.error(f"Error composing email: {e}")
            return {
                "subject": subject,
                "body": content,
                "summary": f"Error composing email: {str(e)}",
            }

    def refine_search_query(self, user_query: str) -> str:
        """
        Refine user query for better semantic search results.

        Args:
            user_query: Original user query

        Returns:
            Refined search query
        """
        logger.info(f"Refining search query: {user_query}")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"""Convert this user query into an optimized semantic search query.
Extract key concepts and expand with synonyms if helpful.

User query: "{user_query}"

Respond with ONLY the refined search query as plain text (no JSON, no explanation).""",
                    },
                ],
                temperature=0.3,
                max_tokens=100,
            )

            refined = response.choices[0].message.content.strip()
            logger.info(f"Refined query: {refined}")
            return refined

        except Exception as e:
            logger.error(f"Error refining query: {e}")
            return user_query  # Fall back to original query

    def generate_presentation(
        self, title: str, content: str
    ) -> Optional[Dict[str, Any]]:
        """
        Generate presentation structure from document content.

        Args:
            title: Document title
            content: Document content

        Returns:
            Dictionary with presentation structure or None on error
        """
        logger.info("Generating presentation structure")

        try:
            # Truncate content if too long
            max_content_length = 10000
            if len(content) > max_content_length:
                content = content[:max_content_length] + "..."

            prompt = PRESENTATION_GENERATION_PROMPT.format(
                title=title, content=content
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=2000,
            )

            result_text = response.choices[0].message.content.strip()
            presentation_data = json.loads(result_text)

            logger.info("Presentation structure generated successfully")
            return presentation_data

        except Exception as e:
            logger.error(f"Error generating presentation: {e}")
            return None

    def generate_document(
        self, title: str, content: str
    ) -> Optional[Dict[str, Any]]:
        """
        Generate document structure from content.

        Args:
            title: Source document title
            content: Document content

        Returns:
            Dictionary with document structure or None on error
        """
        logger.info("Generating document structure")

        try:
            # Truncate content if too long
            max_content_length = 10000
            if len(content) > max_content_length:
                content = content[:max_content_length] + "..."

            prompt = DOCUMENT_GENERATION_PROMPT.format(
                title=title, content=content
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=2000,
            )

            result_text = response.choices[0].message.content.strip()
            document_data = json.loads(result_text)

            logger.info("Document structure generated successfully")
            return document_data

        except Exception as e:
            logger.error(f"Error generating document: {e}")
            return None
