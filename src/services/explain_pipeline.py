"""
Explain Pipeline Service - RAG-based document explanation system.

Provides a reusable pipeline for explain/summarize commands that:
1. Extracts topics from natural language queries
2. Searches for semantically similar documents
3. Extracts relevant content sections
4. Synthesizes explanations with rich telemetry

Used by both slash commands (/explain, /files explain) and natural language detection.
"""

import logging
import re
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class ExplainPipeline:
    """
    RAG pipeline for document explanation and summarization.

    Orchestrates the full pipeline: topic extraction → document search → content extraction → synthesis.
    Provides rich telemetry about the process and results.
    """

    def __init__(self, agent_registry):
        """
        Initialize the explain pipeline.

        Args:
            agent_registry: AgentRegistry instance for tool execution
        """
        self.registry = agent_registry
        logger.info("[EXPLAIN PIPELINE] Initialized")

    def execute(
        self,
        task: str,
        session_id: Optional[str] = None,
        synthesis_style: Optional[str] = None,
        max_search_results: int = 1
    ) -> Dict[str, Any]:
        """
        Execute the complete explain pipeline.

        Args:
            task: Natural language task (e.g., "explain Edgar Allan Poe", "summarize the Tesla report")
            session_id: Optional session ID for context
            synthesis_style: Optional synthesis style override ("concise", "comprehensive", "comparative", "chronological")
            max_search_results: Maximum number of documents to consider (default: 1 for explain, can be higher for summarize)

        Returns:
            Dictionary with results and telemetry:
            {
                "success": bool,
                "summary": str,  # The synthesized explanation/summary
                "doc_title": str,
                "doc_path": str,
                "word_count": int,
                "telemetry": {
                    "topic_extracted": str,
                    "search_results_count": int,
                    "selected_file": str,
                    "similarity_score": float,
                    "synthesis_style": str,
                    "pipeline_steps": ["search", "extract", "synthesize"],
                    "failure_step": str or None,  # If failed, which step
                    "error_details": dict or None
                }
            }
        """
        logger.info(f"[EXPLAIN PIPELINE] Executing pipeline for: {task}")

        # Initialize telemetry
        telemetry = {
            "topic_extracted": None,
            "search_results_count": 0,
            "selected_file": None,
            "similarity_score": 0.0,
            "synthesis_style": synthesis_style or "concise",
            "pipeline_steps": [],
            "failure_step": None,
            "error_details": None
        }

        try:
            # Step 1: Extract topic
            topic = self._extract_topic(task)
            telemetry["topic_extracted"] = topic
            telemetry["pipeline_steps"].append("topic_extraction")

            if not topic:
                telemetry["failure_step"] = "topic_extraction"
                telemetry["error_details"] = {"reason": "Could not extract meaningful topic from query"}
                return self._create_error_response(
                    "Could not understand what to explain. Please be more specific.",
                    telemetry
                )

            # Step 2: Search for documents and images
            search_result = self._search_documents(topic, task, session_id, max_search_results)
            telemetry["pipeline_steps"].append("search")
            results = search_result.get("results", [])
            telemetry["search_results_count"] = len(results)

            if search_result.get("error"):
                telemetry["failure_step"] = "search"
                telemetry["error_details"] = search_result
                error_msg = search_result.get("error_message", f"No documents or images found matching '{topic}'")
                return self._create_error_response(error_msg, telemetry)

            if not results:
                telemetry["failure_step"] = "search"
                telemetry["error_details"] = {"reason": "No search results returned"}
                return self._create_error_response(f"No documents or images found matching '{topic}'", telemetry)

            best_result = results[0]
            doc_path = best_result.get("doc_path")
            result_type = best_result.get("result_type", "document")
            telemetry["selected_file"] = doc_path
            telemetry["similarity_score"] = best_result.get("relevance_score", 0.0)
            telemetry["result_type"] = result_type

            if not doc_path:
                telemetry["failure_step"] = "search"
                telemetry["error_details"] = {"reason": "Best result missing doc_path"}
                return self._create_error_response("Search completed but no valid document or image found", telemetry)

            # Step 3: Extract content (skip for images, use caption instead)
            if result_type == "image":
                # For images, use the caption/preview as the content
                extracted_text = best_result.get("content_preview", best_result.get("caption", ""))
                telemetry["pipeline_steps"].append("extract_image")
                logger.info(f"[EXPLAIN PIPELINE] Using image caption for explanation: {extracted_text[:100]}")
            else:
                # For documents, extract content normally
                extract_result = self._extract_content(doc_path, session_id)
                telemetry["pipeline_steps"].append("extract")

                if extract_result.get("error"):
                    # Try to use content preview from search as fallback
                    content_preview = best_result.get("content_preview", "")
                    if content_preview:
                        logger.warning(f"[EXPLAIN PIPELINE] Extraction failed, using content preview fallback")
                        extracted_text = content_preview
                    else:
                        telemetry["failure_step"] = "extract"
                        telemetry["error_details"] = extract_result
                        error_msg = extract_result.get("error_message", "Failed to extract document content")
                        return self._create_error_response(error_msg, telemetry)
                else:
                    extracted_text = extract_result.get("extracted_text", "")
                    if not extracted_text:
                        telemetry["failure_step"] = "extract"
                        telemetry["error_details"] = {"reason": "Extraction returned empty content"}
                        return self._create_error_response("Document extraction completed but no content returned", telemetry)

            # Step 4: Synthesize content
            if not synthesis_style:
                synthesis_style = self._determine_synthesis_style(task)
            telemetry["synthesis_style"] = synthesis_style

            synth_result = self._synthesize_content(
                extracted_text, topic, task, synthesis_style, session_id
            )
            telemetry["pipeline_steps"].append("synthesize")

            if synth_result.get("error"):
                telemetry["failure_step"] = "synthesize"
                telemetry["error_details"] = synth_result
                error_msg = synth_result.get("error_message", "Failed to synthesize explanation")
                return self._create_error_response(error_msg, telemetry)

            synthesized_content = synth_result.get("synthesized_content", "")
            if not synthesized_content:
                telemetry["failure_step"] = "synthesize"
                telemetry["error_details"] = {"reason": "Synthesis returned empty content"}
                return self._create_error_response("Content synthesis completed but no explanation returned", telemetry)

            # Success!
            telemetry["pipeline_steps"].append("complete")

            # Build response with image metadata if applicable
            response = {
                "success": True,
                "summary": synthesized_content,
                "doc_title": best_result.get("doc_title", "Unknown Document"),
                "doc_path": doc_path,
                "word_count": synth_result.get("word_count", 0),
                "telemetry": telemetry,
                "rag_pipeline": True,  # For compatibility with existing code
                "message": synthesized_content,  # For reply_to_user compatibility
                "result_type": result_type
            }

            # Add image-specific metadata
            if result_type == "image":
                response["thumbnail_url"] = best_result.get("thumbnail_url")
                response["preview_url"] = best_result.get("preview_url")
                response["file_type"] = best_result.get("metadata", {}).get("file_type", "image")
                
                # Add files array for UI display
                response["files"] = [{
                    "file_path": doc_path,
                    "file_name": best_result.get("doc_title", "Unknown Image"),
                    "file_type": best_result.get("metadata", {}).get("file_type", "image"),
                    "thumbnail_url": best_result.get("thumbnail_url"),
                    "preview_url": best_result.get("preview_url")
                }]

            return response

        except Exception as e:
            logger.error(f"[EXPLAIN PIPELINE] Unexpected error: {e}", exc_info=True)
            telemetry["failure_step"] = "unexpected_error"
            telemetry["error_details"] = {"exception": str(e)}
            return self._create_error_response(f"Unexpected error during explanation: {str(e)}", telemetry)

    def _extract_topic(self, task: str) -> str:
        """
        Extract the topic to explain from the task string.

        Removes common keywords and extracts the core subject.
        """
        # Remove summarize/explain keywords
        rag_keywords_pattern = r'\b(summarize|summarise|summary|explain|describe|what is|tell me about)\b'
        topic = re.sub(rag_keywords_pattern, '', task, flags=re.IGNORECASE).strip()

        # Remove common filler words, but preserve articles at the start of what's left
        # (e.g., "explain the machine" -> "the machine", not "")
        words = topic.split()
        if words:
            # Keep the first word if it's an article (the, a, an)
            first_word = words[0].lower()
            if first_word in ['the', 'a', 'an']:
                # Remove other filler words but keep the article
                filtered_words = [words[0]]  # Keep the article
                for word in words[1:]:
                    if word.lower() not in ['my', 'this', 'that', 'these', 'those', 'files', 'docs', 'documents', 'file', 'doc']:
                        filtered_words.append(word)
                topic = ' '.join(filtered_words)
            else:
                # Remove all filler words including articles
                filler_words = r'\b(the|my|a|an|this|that|these|those|files?|docs?|documents?)\b'
                topic = re.sub(filler_words, '', topic, flags=re.IGNORECASE).strip()

        # Clean up extra whitespace
        topic = re.sub(r'\s+', ' ', topic).strip()

        return topic if topic else task  # Fallback to original task if extraction fails

    def _search_documents(self, topic: str, original_task: str, session_id: str, max_results: int) -> Dict[str, Any]:
        """Search for documents matching the topic."""
        return self.registry.execute_tool(
            "search_documents",
            {
                "query": topic,
                "user_request": original_task,
                "max_results": max_results
            },
            session_id=session_id
        )

    def _extract_content(self, doc_path: str, session_id: str) -> Dict[str, Any]:
        """Extract content from the selected document."""
        return self.registry.execute_tool(
            "extract_section",
            {"doc_path": doc_path, "section": "all"},
            session_id=session_id
        )

    def _determine_synthesis_style(self, task: str) -> str:
        """Determine the appropriate synthesis style based on task keywords."""
        task_lower = task.lower()

        # Check for bullet formatting first
        if any(word in task_lower for word in ["bullet", "bullets", "list"]):
            return "concise"  # Bullets are a concise format

        # Check for comprehensive requests
        comprehensive_keywords = ["detailed", "comprehensive", "thorough", "deep", "extensive"]
        if any(word in task_lower for word in comprehensive_keywords) or "in detail" in task_lower or "in depth" in task_lower:
            return "comprehensive"

        # Check for other specific styles
        if any(word in task_lower for word in ["compare", "contrast", "versus", "vs"]):
            return "comparative"
        elif any(word in task_lower for word in ["chronological", "timeline", "sequence", "history"]):
            return "chronological"

        # Default to concise for explain/summarize
        return "concise"

    def _synthesize_content(
        self,
        content: str,
        topic: str,
        original_task: str,
        style: str,
        session_id: str
    ) -> Dict[str, Any]:
        """Synthesize the extracted content into a coherent explanation."""
        # Determine topic based on task type and format
        task_lower = original_task.lower()

        if "summar" in task_lower:
            synth_topic = f"{topic} Summary"
        else:
            synth_topic = f"{topic} Explanation"

        # Add bullet formatting instruction if requested
        if any(word in task_lower for word in ["bullet", "bullets", "list"]):
            synth_topic += " (format as bullet points)"

        return self.registry.execute_tool(
            "synthesize_content",
            {
                "source_contents": [content],
                "topic": synth_topic,
                "synthesis_style": style
            },
            session_id=session_id
        )

    def _create_error_response(self, message: str, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """Create a standardized error response with telemetry."""
        return {
            "success": False,
            "error": True,
            "error_type": "PipelineError",
            "error_message": message,
            "telemetry": telemetry,
            "rag_pipeline": True
        }
