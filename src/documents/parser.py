"""
Document parser for PDF, DOCX, and TXT files.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import PyPDF2
import pdfplumber
from docx import Document


logger = logging.getLogger(__name__)


class DocumentParser:
    """
    Parses various document formats and extracts text content.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the document parser.

        Args:
            config: Configuration dictionary
        """
        self.config = config

    def parse_document(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Parse a document and extract its content.

        Args:
            file_path: Path to the document

        Returns:
            Dictionary containing document metadata and content
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        file_ext = file_path.suffix.lower()

        try:
            if file_ext == '.pdf':
                return self._parse_pdf(file_path)
            elif file_ext == '.docx':
                return self._parse_docx(file_path)
            elif file_ext == '.txt':
                return self._parse_txt(file_path)
            else:
                logger.warning(f"Unsupported file type: {file_ext}")
                return None

        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return None

    def _parse_pdf(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse PDF document using pdfplumber (better text extraction).

        Args:
            file_path: Path to PDF file

        Returns:
            Parsed document dictionary
        """
        pages = {}
        full_content = []

        try:
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text()
                    if text:
                        pages[i] = text
                        full_content.append(text)

            return {
                'file_path': str(file_path),
                'file_name': file_path.name,
                'file_type': 'pdf',
                'content': '\n\n'.join(full_content),
                'pages': pages,
                'page_count': len(pages),
            }

        except Exception as e:
            # Fallback to PyPDF2 if pdfplumber fails
            logger.warning(f"pdfplumber failed, trying PyPDF2: {e}")
            return self._parse_pdf_fallback(file_path)

    def _parse_pdf_fallback(self, file_path: Path) -> Dict[str, Any]:
        """
        Fallback PDF parser using PyPDF2.

        Args:
            file_path: Path to PDF file

        Returns:
            Parsed document dictionary
        """
        pages = {}
        full_content = []

        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)

            for i, page in enumerate(reader.pages, start=1):
                text = page.extract_text()
                if text:
                    pages[i] = text
                    full_content.append(text)

        return {
            'file_path': str(file_path),
            'file_name': file_path.name,
            'file_type': 'pdf',
            'content': '\n\n'.join(full_content),
            'pages': pages,
            'page_count': len(pages),
        }

    def _parse_docx(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse DOCX document.

        Args:
            file_path: Path to DOCX file

        Returns:
            Parsed document dictionary
        """
        doc = Document(file_path)

        # Extract paragraphs
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        content = '\n\n'.join(paragraphs)

        # Try to identify sections (approximate pages)
        # DOCX doesn't have explicit pages, so we simulate them
        pages = {}
        chars_per_page = 3000  # Approximate
        for i, start in enumerate(range(0, len(content), chars_per_page), start=1):
            page_content = content[start:start + chars_per_page]
            if page_content.strip():
                pages[i] = page_content

        return {
            'file_path': str(file_path),
            'file_name': file_path.name,
            'file_type': 'docx',
            'content': content,
            'pages': pages,
            'page_count': len(pages),
        }

    def _parse_txt(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse TXT document.

        Args:
            file_path: Path to TXT file

        Returns:
            Parsed document dictionary
        """
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        return {
            'file_path': str(file_path),
            'file_name': file_path.name,
            'file_type': 'txt',
            'content': content,
            'pages': {},
            'page_count': 0,
        }

    def extract_section(
        self,
        file_path: str,
        extraction_plan: Dict[str, Any]
    ) -> str:
        """
        Extract a specific section from a document based on extraction plan.

        Args:
            file_path: Path to the document
            extraction_plan: Plan from LLM with extraction method and parameters

        Returns:
            Extracted content as string
        """
        parsed = self.parse_document(file_path)
        if not parsed:
            return ""

        method = extraction_plan.get('extraction_method', 'full_document')
        params = extraction_plan.get('parameters', {})

        if method == 'page_range':
            return self._extract_page_range(parsed, params)
        elif method == 'keyword_search':
            return self._extract_by_keywords(parsed, params)
        else:
            # Full document
            max_chars = params.get('max_chars')
            content = parsed['content']
            if max_chars and len(content) > max_chars:
                return content[:max_chars] + "\n\n[Content truncated...]"
            return content

    def _extract_page_range(
        self,
        parsed_doc: Dict[str, Any],
        params: Dict[str, Any]
    ) -> str:
        """Extract specific page range."""
        pages = parsed_doc.get('pages', {})
        start_page = params.get('start_page', 1)
        end_page = params.get('end_page', len(pages))

        extracted = []
        for page_num in range(start_page, end_page + 1):
            if page_num in pages:
                extracted.append(f"--- Page {page_num} ---\n{pages[page_num]}")

        return '\n\n'.join(extracted) if extracted else parsed_doc['content']

    def _extract_by_keywords(
        self,
        parsed_doc: Dict[str, Any],
        params: Dict[str, Any]
    ) -> str:
        """Extract sections containing keywords."""
        keywords = params.get('keywords', [])
        if not keywords:
            return parsed_doc['content']

        # Search through pages for keywords
        relevant_pages = []
        pages = parsed_doc.get('pages', {})

        for page_num, content in pages.items():
            content_lower = content.lower()
            if any(keyword.lower() in content_lower for keyword in keywords):
                relevant_pages.append((page_num, content))

        if relevant_pages:
            extracted = [
                f"--- Page {page_num} ---\n{content}"
                for page_num, content in relevant_pages
            ]
            return '\n\n'.join(extracted)
        else:
            # Fallback to full content if no keywords found
            return parsed_doc['content']
