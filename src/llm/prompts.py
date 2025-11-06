"""
Prompt templates for the LLM planner.
"""

SYSTEM_PROMPT = """You are an intelligent automation assistant for macOS. Your job is to understand natural language requests and break them down into structured action plans.

You help users with tasks like:
- Finding documents based on semantic meaning
- Extracting specific sections from documents
- Taking screenshots of document pages
- Composing emails with extracted content or screenshots
- Creating Keynote presentations (slide decks) from document content
- Creating Pages documents from extracted content

When given a user request, analyze it and respond with a structured action plan in JSON format."""

INTENT_PARSING_PROMPT = """Analyze the following user request and extract the intent and parameters.

User Request: "{user_input}"

Respond with a JSON object containing:
{{
  "intent": "find_and_email_document" | "create_presentation" | "create_document",
  "parameters": {{
    "search_query": "what to search for (semantic query)",
    "document_section": "which section to extract (e.g., 'summary', 'page 10', 'introduction', 'all')",
    "screenshot_request": {{
      "enabled": true/false,
      "page_numbers": [list of page numbers] or null,
      "search_text": "text to find in pages" or null
    }},
    "email_action": {{
      "recipient": "email address if specified, otherwise null",
      "subject": "suggested email subject",
      "body_instructions": "how to format the email body"
    }},
    "presentation_action": {{
      "enabled": true/false,
      "title": "presentation title",
      "output_path": "optional save path or null"
    }},
    "document_action": {{
      "enabled": true/false,
      "title": "document title",
      "output_path": "optional save path or null"
    }}
  }},
  "confidence": 0.0-1.0
}}

Examples:

User: "Send me the doc about Tesla Autopilot — just the summary section."
Response:
{{
  "intent": "find_and_email_document",
  "parameters": {{
    "search_query": "Tesla Autopilot",
    "document_section": "summary",
    "screenshot_request": {{
      "enabled": false,
      "page_numbers": null,
      "search_text": null
    }},
    "email_action": {{
      "recipient": null,
      "subject": "Tesla Autopilot Summary",
      "body_instructions": "Include the summary section from the document"
    }}
  }},
  "confidence": 0.95
}}

User: "Find the Q3 earnings report and email page 5 to john@example.com"
Response:
{{
  "intent": "find_and_email_document",
  "parameters": {{
    "search_query": "Q3 earnings report",
    "document_section": "page 5",
    "screenshot_request": {{
      "enabled": false,
      "page_numbers": null,
      "search_text": null
    }},
    "email_action": {{
      "recipient": "john@example.com",
      "subject": "Q3 Earnings Report - Page 5",
      "body_instructions": "Include page 5 from the document"
    }}
  }},
  "confidence": 0.98
}}

User: "Take a screenshot of page 3 of the AI agents document and send it to me at test@example.com"
Response:
{{
  "intent": "find_and_email_document",
  "parameters": {{
    "search_query": "AI agents",
    "document_section": "page 3",
    "screenshot_request": {{
      "enabled": true,
      "page_numbers": [3],
      "search_text": null
    }},
    "email_action": {{
      "recipient": "test@example.com",
      "subject": "AI Agents Document - Page 3 Screenshot",
      "body_instructions": "Include screenshot of page 3"
    }}
  }},
  "confidence": 0.97
}}

User: "Screenshot the pages about customer service from the marketing report"
Response:
{{
  "intent": "find_and_email_document",
  "parameters": {{
    "search_query": "marketing report",
    "document_section": "customer service",
    "screenshot_request": {{
      "enabled": true,
      "page_numbers": null,
      "search_text": "customer service"
    }},
    "email_action": {{
      "recipient": null,
      "subject": "Marketing Report - Customer Service Pages",
      "body_instructions": "Include screenshots of pages containing customer service information"
    }},
    "presentation_action": {{
      "enabled": false,
      "title": null,
      "output_path": null
    }},
    "document_action": {{
      "enabled": false,
      "title": null,
      "output_path": null
    }}
  }},
  "confidence": 0.92
}}

User: "Create a Keynote presentation from the Tesla Autopilot document"
Response:
{{
  "intent": "create_presentation",
  "parameters": {{
    "search_query": "Tesla Autopilot",
    "document_section": "all",
    "screenshot_request": {{
      "enabled": false,
      "page_numbers": null,
      "search_text": null
    }},
    "email_action": {{
      "recipient": null,
      "subject": null,
      "body_instructions": null
    }},
    "presentation_action": {{
      "enabled": true,
      "title": "Tesla Autopilot Overview",
      "output_path": null
    }},
    "document_action": {{
      "enabled": false,
      "title": null,
      "output_path": null
    }}
  }},
  "confidence": 0.95
}}

User: "Make a slide deck based on the Q3 earnings report"
Response:
{{
  "intent": "create_presentation",
  "parameters": {{
    "search_query": "Q3 earnings report",
    "document_section": "all",
    "screenshot_request": {{
      "enabled": false,
      "page_numbers": null,
      "search_text": null
    }},
    "email_action": {{
      "recipient": null,
      "subject": null,
      "body_instructions": null
    }},
    "presentation_action": {{
      "enabled": true,
      "title": "Q3 Earnings Report",
      "output_path": null
    }},
    "document_action": {{
      "enabled": false,
      "title": null,
      "output_path": null
    }}
  }},
  "confidence": 0.93
}}

User: "Create a Pages document summarizing the AI research paper"
Response:
{{
  "intent": "create_document",
  "parameters": {{
    "search_query": "AI research paper",
    "document_section": "all",
    "screenshot_request": {{
      "enabled": false,
      "page_numbers": null,
      "search_text": null
    }},
    "email_action": {{
      "recipient": null,
      "subject": null,
      "body_instructions": null
    }},
    "presentation_action": {{
      "enabled": false,
      "title": null,
      "output_path": null
    }},
    "document_action": {{
      "enabled": true,
      "title": "AI Research Summary",
      "output_path": null
    }}
  }},
  "confidence": 0.94
}}

Now analyze the user's request and respond with ONLY the JSON object, no additional text.
"""

SECTION_EXTRACTION_PROMPT = """Given a document and a section request, determine the best way to extract the content.

Document metadata: {document_metadata}
User requested section: "{section_request}"

Analyze and respond with JSON:
{{
  "extraction_method": "page_range" | "keyword_search" | "full_document",
  "parameters": {{
    "start_page": int or null,
    "end_page": int or null,
    "keywords": [list of keywords] or null,
    "max_chars": int or null
  }},
  "explanation": "brief explanation of extraction strategy"
}}

Respond with ONLY the JSON object.
"""

EMAIL_COMPOSITION_PROMPT = """Compose a professional email based on the following information:

Subject: {subject}
Extracted Content: {content}
Instructions: {instructions}

Generate:
{{
  "subject": "final email subject",
  "body": "complete email body (markdown formatted)",
  "summary": "brief summary of what was done"
}}

Make the email concise, professional, and well-formatted. Respond with ONLY the JSON object.
"""

PRESENTATION_GENERATION_PROMPT = """Generate a Keynote presentation structure from the following document content:

Document Title: {title}
Content: {content}

Create a logical presentation structure with:
- A title slide
- 3-7 content slides covering key points
- Each slide should have a title and concise bullet points

Generate:
{{
  "title": "presentation title",
  "slides": [
    {{
      "title": "slide title",
      "content": "bullet points or content (use \\n for line breaks)"
    }},
    ...
  ]
}}

Keep slides focused and visually balanced. Respond with ONLY the JSON object.
"""

DOCUMENT_GENERATION_PROMPT = """Generate a Pages document structure from the following content:

Source Document: {title}
Content: {content}

Create a well-structured document with:
- Clear sections with headings
- Organized paragraphs
- Professional formatting

Generate:
{{
  "title": "document title",
  "sections": [
    {{
      "heading": "section heading",
      "content": "section content (can be multi-paragraph)"
    }},
    ...
  ]
}}

Make the document clear, well-organized, and professional. Respond with ONLY the JSON object.
"""
