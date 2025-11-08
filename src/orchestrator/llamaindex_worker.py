"""
LlamaIndex worker for atomic tasks and RAG operations.
"""

import logging
import json
from typing import Dict, Any
from llama_index.core import VectorStoreIndex, ServiceContext, StorageContext
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.llms.openai import OpenAI as LlamaIndexOpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.response_synthesizers import get_response_synthesizer

from ..documents import DocumentIndexer
from .prompts import LLAMAINDEX_WORKER_PROMPT

logger = logging.getLogger(__name__)


class LlamaIndexWorker:
    """
    Worker that uses LlamaIndex for complex atomic tasks requiring RAG.
    """

    def __init__(self, config: Dict[str, Any], document_indexer: DocumentIndexer):
        """
        Initialize the LlamaIndex worker.

        Args:
            config: Configuration dictionary
            document_indexer: Existing document indexer with FAISS index
        """
        self.config = config
        self.document_indexer = document_indexer

        # Initialize LlamaIndex LLM
        self.llm = LlamaIndexOpenAI(
            model=config.get("openai", {}).get("model", "gpt-4o"),
            temperature=0.7,
            api_key=config.get("openai", {}).get("api_key")
        )

        # Initialize embeddings (matching the indexer's embedding model)
        self.embeddings = OpenAIEmbedding(
            model=config.get("openai", {}).get("embedding_model", "text-embedding-3-small"),
            api_key=config.get("openai", {}).get("api_key")
        )

        logger.info("LlamaIndex worker initialized")

    def execute(
        self,
        task: str,
        context: Dict[str, Any],
        artifacts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute an atomic task using LlamaIndex.

        Args:
            task: Task description
            context: Workflow context
            artifacts: Available artifacts from previous steps

        Returns:
            Result dictionary with ok, artifacts, notes, and usage
        """
        logger.info(f"LlamaIndex worker executing task: {task}")

        try:
            # Build the prompt
            prompt = LLAMAINDEX_WORKER_PROMPT.format(
                task=task,
                context=json.dumps(context, indent=2),
                artifacts=json.dumps(artifacts, indent=2)
            )

            # Determine if this task needs RAG
            needs_rag = self._task_needs_rag(task)

            if needs_rag:
                result = self._execute_with_rag(prompt, task)
            else:
                result = self._execute_direct(prompt, task)

            # Parse and validate result
            return self._parse_result(result)

        except Exception as e:
            logger.error(f"LlamaIndex worker error: {e}", exc_info=True)
            return {
                "ok": False,
                "artifacts": {},
                "notes": [f"Worker error: {str(e)}"],
                "usage": {"tokens": 0, "calls": 0}
            }

    def _task_needs_rag(self, task: str) -> bool:
        """
        Determine if a task requires RAG from the document index.

        Args:
            task: Task description

        Returns:
            True if RAG is needed
        """
        rag_keywords = [
            "search", "find", "document", "analyze", "extract", "summarize",
            "information", "content", "page", "section", "text"
        ]

        task_lower = task.lower()
        return any(keyword in task_lower for keyword in rag_keywords)

    def _execute_with_rag(self, prompt: str, task: str) -> str:
        """
        Execute task with RAG using the document index.

        Args:
            prompt: Full prompt
            task: Task description

        Returns:
            LLM response
        """
        logger.info("Executing with RAG")

        try:
            # Use the existing FAISS index for retrieval
            # Query the index semantically
            search_results = self.document_indexer.search(task, top_k=5)

            if not search_results:
                logger.warning("No relevant documents found for RAG")
                return self._execute_direct(prompt, task)

            # Build context from search results
            rag_context = self._build_rag_context(search_results)

            # Augment prompt with RAG context
            augmented_prompt = f"{prompt}\n\nRelevant Documents:\n{rag_context}"

            # Call LLM with augmented context
            response = self.llm.complete(augmented_prompt)

            return response.text

        except Exception as e:
            logger.error(f"RAG execution error: {e}")
            # Fallback to direct execution
            return self._execute_direct(prompt, task)

    def _execute_direct(self, prompt: str, task: str) -> str:
        """
        Execute task directly without RAG.

        Args:
            prompt: Full prompt
            task: Task description

        Returns:
            LLM response
        """
        logger.info("Executing direct (no RAG)")

        response = self.llm.complete(prompt)
        return response.text

    def _build_rag_context(self, search_results: list) -> str:
        """
        Build RAG context from search results.

        Args:
            search_results: List of search results

        Returns:
            Formatted context string
        """
        lines = []

        for i, result in enumerate(search_results, 1):
            lines.append(f"\n--- Document {i} ---")
            lines.append(f"File: {result.get('file_name', 'Unknown')}")
            lines.append(f"Relevance: {result.get('score', 0.0):.3f}")
            lines.append(f"Content: {result.get('content', '')[:500]}...")  # First 500 chars

        return "\n".join(lines)

    def _parse_result(self, result_text: str) -> Dict[str, Any]:
        """
        Parse and validate worker result.

        Args:
            result_text: Raw LLM response

        Returns:
            Validated result dictionary
        """
        try:
            # Try to extract JSON from the response
            json_start = result_text.find("{")
            json_end = result_text.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = result_text[json_start:json_end]
                result = json.loads(json_str)

                # Validate required fields
                if "ok" not in result:
                    result["ok"] = True  # Assume success if not specified

                if "artifacts" not in result:
                    result["artifacts"] = {}

                if "notes" not in result:
                    result["notes"] = []

                if "usage" not in result:
                    # Estimate usage (rough)
                    result["usage"] = {
                        "tokens": len(result_text) // 4,  # Rough estimate
                        "calls": 1
                    }

                return result
            else:
                # No JSON found, treat entire response as artifact
                return {
                    "ok": True,
                    "artifacts": {"response": result_text},
                    "notes": ["Response was not in JSON format, wrapped as artifact"],
                    "usage": {"tokens": len(result_text) // 4, "calls": 1}
                }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse worker result: {e}")
            return {
                "ok": False,
                "artifacts": {"raw_response": result_text},
                "notes": [f"Failed to parse JSON: {str(e)}"],
                "usage": {"tokens": 0, "calls": 1}
            }


def create_llamaindex_worker(config: Dict[str, Any], document_indexer: DocumentIndexer) -> LlamaIndexWorker:
    """
    Factory function to create a LlamaIndex worker.

    Args:
        config: Configuration dictionary
        document_indexer: Document indexer instance

    Returns:
        LlamaIndexWorker instance
    """
    return LlamaIndexWorker(config, document_indexer)
