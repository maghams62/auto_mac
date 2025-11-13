"""
Email Content Verifier - LLM-based verification for email composition.

This module ensures that when users request to email something (links, files, content),
the compose_email parameters actually include what was requested.

Problem: Users say "send the links to my email" but the email body doesn't contain the links.
Solution: LLM analyzes user intent and verifies email parameters before execution.
"""

from typing import Dict, Any, List, Optional
import logging
import json
from openai import OpenAI
import os

logger = logging.getLogger(__name__)


class EmailContentVerifier:
    """
    LLM-based verifier that ensures email content matches user's delivery request.
    
    This verifier:
    1. Analyzes the original user request to understand what should be emailed
    2. Inspects the compose_email parameters (body, attachments) 
    3. Checks if the parameters contain the requested content
    4. Returns verification result with corrective actions if needed
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
    def verify_email_content(
        self,
        user_request: str,
        compose_email_params: Dict[str, Any],
        step_results: Dict[int, Any],
        current_step_id: str,
        reasoning_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Verify that compose_email parameters contain what the user requested.
        
        Uses LLM-based verification with optional reasoning trace context for learning.
        
        Args:
            user_request: Original user request (e.g., "plan a trip and send the links to my email")
            compose_email_params: Parameters for compose_email step (body, attachments, etc.)
            step_results: Results from previous steps that might contain required content
            current_step_id: ID of the current compose_email step
            reasoning_context: Optional context from reasoning trace for learning (commitments, past attempts)
            
        Returns:
            Dict with:
            - verified: bool - True if email contains requested content
            - missing_items: List[str] - What's missing from the email
            - suggestions: Dict[str, Any] - Suggested corrections to parameters
            - reasoning: str - LLM's reasoning about verification
        """
        logger.info(f"[EMAIL VERIFIER] Verifying compose_email parameters for step {current_step_id}")
        logger.debug(f"[EMAIL VERIFIER] User request: {user_request}")
        logger.debug(f"[EMAIL VERIFIER] Email params: {compose_email_params}")
        if reasoning_context:
            logger.debug(f"[EMAIL VERIFIER] Reasoning context: {reasoning_context}")
        
        # Build context about available content from previous steps
        available_content = self._extract_available_content(step_results)
        
        # Create verification prompt
        prompt = self._build_verification_prompt(
            user_request=user_request,
            email_params=compose_email_params,
            available_content=available_content
        )
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an email content verification expert. Your job is to ensure that when users request to email something (links, files, content, reports, etc.), the email actually contains what they requested.

Analyze:
1. What the user asked to be emailed (links, attachments, specific content)
2. What's actually in the email body and attachments
3. What content is available from previous steps but missing from the email

Be strict: If the user asks to "send the links", the email MUST contain the actual links in the body or as attachments.
If the user asks to "email the report", the report MUST be attached or in the body.

CRITICAL RULES FOR SUGGESTIONS:
1. Only suggest corrections for what's actually MISSING
2. If attachments are already correct, DO NOT include "attachments" in suggestions
3. If body is already correct, DO NOT include "body" in suggestions
4. When suggesting attachment corrections, INCLUDE existing correct attachments + add missing ones
5. NEVER suggest an empty attachments array if files should be attached

Return your analysis as JSON with:
{
  "verified": true/false,
  "missing_items": ["list", "of", "missing", "items"],
  "suggestions": {
    "body": "corrected email body with missing items" (ONLY if body is actually incomplete),
    "attachments": ["list", "of", "attachments"] (ONLY if attachments are actually incomplete or missing)
  },
  "reasoning": "explanation of what's missing and why"
}

Examples:
- If attachments are correct, suggestions = {} (no changes needed)
- If body needs link added, suggestions = {"body": "new body with link"}
- If attachment exists but another is missing, suggestions = {"attachments": ["existing.key", "missing.pdf"]}"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            if result.get("verified"):
                logger.info(f"[EMAIL VERIFIER] ✅ Email content verified - contains requested items")
            else:
                logger.warning(f"[EMAIL VERIFIER] ⚠️  Email content verification FAILED")
                logger.warning(f"[EMAIL VERIFIER] Missing items: {result.get('missing_items', [])}")
                logger.info(f"[EMAIL VERIFIER] Suggestions: {result.get('suggestions', {})}")
            
            return result
            
        except Exception as e:
            logger.error(f"[EMAIL VERIFIER] Error during verification: {e}")
            # On error, allow email to proceed (fail open)
            return {
                "verified": True,
                "missing_items": [],
                "suggestions": {},
                "reasoning": f"Verification failed with error: {e}. Allowing email to proceed.",
                "error": True
            }
    
    def _extract_available_content(self, step_results: Dict[int, Any]) -> Dict[str, Any]:
        """
        Extract relevant content from previous step results.
        
        Looks for:
        - URLs (maps_url, url, link fields)
        - File paths (file_path, pages_path, keynote_path, pdf_path fields)
        - Content (summary, message, report_content fields)
        """
        available = {
            "urls": [],
            "file_paths": [],
            "content_snippets": []
        }
        
        for step_id, result in step_results.items():
            if not isinstance(result, dict):
                continue
                
            # Extract URLs
            for url_field in ["maps_url", "url", "link", "display_url"]:
                if url_field in result and result[url_field]:
                    available["urls"].append({
                        "step": step_id,
                        "field": url_field,
                        "value": result[url_field]
                    })
            
            # Extract file paths
            for path_field in ["file_path", "pages_path", "keynote_path", "pdf_path", "presentation_path", "doc_path"]:
                if path_field in result and result[path_field]:
                    available["file_paths"].append({
                        "step": step_id,
                        "field": path_field,
                        "value": result[path_field]
                    })
            
            # Extract content
            for content_field in ["summary", "message", "report_content", "synthesized_content"]:
                if content_field in result and result[content_field]:
                    content_str = str(result[content_field])
                    # Only include first 200 chars to keep prompt manageable
                    available["content_snippets"].append({
                        "step": step_id,
                        "field": content_field,
                        "preview": content_str[:200] + ("..." if len(content_str) > 200 else "")
                    })
        
        return available
    
    def _build_verification_prompt(
        self,
        user_request: str,
        email_params: Dict[str, Any],
        available_content: Dict[str, Any]
    ) -> str:
        """Build the verification prompt for the LLM."""
        
        prompt = f"""# Email Content Verification

## User's Original Request:
"{user_request}"

## Current Email Parameters:
```json
{{
  "subject": "{email_params.get('subject', '')}",
  "body": "{email_params.get('body', '')}",
  "attachments": {json.dumps(email_params.get('attachments', []))},
  "recipient": "{email_params.get('recipient', '')}",
  "send": {email_params.get('send', False)}
}}
```

## Available Content from Previous Steps:
```json
{json.dumps(available_content, indent=2)}
```

## Your Task:
Analyze if the email body and attachments contain what the user requested to be emailed.

Common issues to check:
1. User says "send the links" but email body doesn't contain any URLs
2. User says "email the report" but no attachment and no report content in body
3. User says "send the file" but attachments list is empty
4. User says "email the presentation" but no .key/.ppt file attached

If content is available in previous steps but missing from email, suggest corrections.
Be specific about which field from which step should be included.

Return your analysis as JSON."""
        
        return prompt


def verify_compose_email_content(
    user_request: str,
    compose_email_params: Dict[str, Any],
    step_results: Dict[int, Any],
    current_step_id: str,
    reasoning_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function to verify compose_email parameters.
    
    This is the main entry point for email content verification.
    Optionally uses reasoning trace context for learning from past attempts.
    
    Args:
        user_request: Original user request
        compose_email_params: Email parameters to verify
        step_results: Results from previous steps
        current_step_id: Current step ID
        reasoning_context: Optional reasoning trace context (commitments, past attempts)
    
    Returns:
        Verification result with verified flag and suggestions
    """
    verifier = EmailContentVerifier()
    return verifier.verify_email_content(
        user_request=user_request,
        compose_email_params=compose_email_params,
        step_results=step_results,
        current_step_id=current_step_id,
        reasoning_context=reasoning_context
    )

