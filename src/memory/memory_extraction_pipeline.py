"""
MemoryExtractionPipeline - Extracts and stores salient memories from conversations.

This module implements MemGPT-style memory extraction that runs after each
interaction to identify preferences, facts, and goals worth remembering.
Uses LLM classification and cosine similarity deduplication.
"""

import json
import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from threading import Lock

try:
    import faiss
    from openai import OpenAI
    from sklearn.metrics.pairwise import cosine_similarity
    from src.utils.openai_client import PooledOpenAIClient
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    OpenAI = None
    PooledOpenAIClient = None
    logger = logging.getLogger(__name__)
    logger.warning("[MEMORY EXTRACTION] OpenAI/FAISS not available - LLM classification disabled")

from .user_memory_store import UserMemoryStore, MemoryEntry

logger = logging.getLogger(__name__)


@dataclass
class ExtractedMemory:
    """Raw extracted memory before deduplication and scoring."""
    content: str
    category: str
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.0  # 0.0-1.0, how confident the extraction is
    source_interaction_id: Optional[str] = None
    reasoning: Optional[str] = None  # Why this was extracted

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "category": self.category,
            "tags": self.tags,
            "confidence": self.confidence,
            "source_interaction_id": self.source_interaction_id,
            "reasoning": self.reasoning
        }


@dataclass
class ExtractionResult:
    """Result of memory extraction process."""
    extracted_memories: List[ExtractedMemory] = field(default_factory=list)
    duplicates_skipped: List[Tuple[ExtractedMemory, MemoryEntry, float]] = field(default_factory=list)
    stored_memories: List[MemoryEntry] = field(default_factory=list)
    processing_stats: Dict[str, Any] = field(default_factory=dict)


class MemoryExtractionPipeline:
    """
    Pipeline for extracting and storing salient memories from conversations.

    Uses LLM classification to identify worth-remembering content, then
    deduplicates using cosine similarity before storing in UserMemoryStore.
    """

    def __init__(
        self,
        user_memory_store: UserMemoryStore,
        openai_client: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
        similarity_threshold: float = 0.87,
        min_confidence: float = 0.7,
        max_memories_per_interaction: int = 3
    ):
        """
        Initialize memory extraction pipeline.

        Args:
            user_memory_store: UserMemoryStore instance to store memories
            openai_client: OpenAI client for LLM classification
            config: Optional configuration dictionary for pooled client
            similarity_threshold: Cosine similarity threshold for deduplication (0.87 = very similar)
            min_confidence: Minimum confidence score to store memory
            max_memories_per_interaction: Maximum memories to extract per interaction
        """
        self.user_memory_store = user_memory_store
        self.config = config
        
        # Use pooled client if config provided, otherwise use provided client or create new one
        if openai_client:
            # Use provided client (backward compatibility)
            self.openai_client = openai_client
        elif config and PooledOpenAIClient:
            # Use pooled client for connection reuse (20-40% faster)
            self.openai_client = PooledOpenAIClient.get_client(config)
            logger.info("[MEMORY EXTRACTION] Using pooled OpenAI client for connection reuse")
        else:
            # Fallback to direct client
            self.openai_client = OpenAI() if OpenAI else None
        
        # Global rate limiter for LLM calls
        if config:
            from src.utils.rate_limiter import get_rate_limiter
            self.rate_limiter = get_rate_limiter(config=config)
        else:
            self.rate_limiter = None
        
        self.similarity_threshold = similarity_threshold
        self.min_confidence = min_confidence
        self.max_memories_per_interaction = max_memories_per_interaction

        self._lock = Lock()

        # Classification prompt for LLM
        self.classification_prompt = """
You are an expert at identifying important information worth remembering from conversations.

Analyze the following user-agent interaction and extract any salient facts, preferences, goals, or patterns that would be valuable to remember for future interactions.

Focus on:
- User preferences and habits
- Important facts or background information
- Goals, commitments, or recurring tasks
- Technical preferences (tools, workflows, settings)
- Personal information relevant to automation

For each piece of information you extract, provide:
1. The content to remember
2. Category: "preferences", "facts", "goals", "commitments", or "patterns"
3. Relevant tags (2-3 keywords)
4. Confidence score (0.0-1.0) - how certain you are this is worth remembering
5. Brief reasoning for why this should be remembered

Only extract information that would genuinely help in future interactions. Skip transient requests, casual conversation, and obvious one-time tasks.

Return your response as a JSON array of objects with keys: "content", "category", "tags", "confidence", "reasoning"

If no memorable information is found, return an empty array: []

Interaction to analyze:
User: {user_request}
Agent: {agent_response}
"""

    def extract_and_store(
        self,
        user_request: str,
        agent_response: Optional[Dict[str, Any]],
        interaction_id: Optional[str] = None
    ) -> ExtractionResult:
        """
        Extract memories from an interaction and store them.

        Args:
            user_request: The user's message/request
            agent_response: The agent's response (can be None)
            interaction_id: Unique identifier for this interaction

        Returns:
            ExtractionResult with details of what was processed
        """
        if not LLM_AVAILABLE:
            logger.debug("[MEMORY EXTRACTION] LLM not available, skipping extraction")
            return ExtractionResult()

        with self._lock:
            result = ExtractionResult()
            result.processing_stats["interaction_id"] = interaction_id
            result.processing_stats["timestamp"] = datetime.now().isoformat()

            try:
                # Step 1: Extract candidate memories using LLM
                extracted_memories = self._extract_memories_llm(user_request, agent_response)
                result.extracted_memories = extracted_memories
                result.processing_stats["extracted_count"] = len(extracted_memories)

                # Step 2: Deduplicate against existing memories
                deduped_memories, duplicates = self._deduplicate_memories(extracted_memories)
                result.duplicates_skipped = duplicates
                result.processing_stats["duplicates_skipped"] = len(duplicates)

                # Step 3: Score and store accepted memories
                stored_memories = self._store_memories(deduped_memories, interaction_id)
                result.stored_memories = stored_memories
                result.processing_stats["stored_count"] = len(stored_memories)

                logger.debug(f"[MEMORY EXTRACTION] Processed interaction {interaction_id}: extracted={len(extracted_memories)}, skipped={len(duplicates)}, stored={len(stored_memories)}")

            except Exception as e:
                logger.error(f"[MEMORY EXTRACTION] Failed to process interaction: {e}", exc_info=True)
                result.processing_stats["error"] = str(e)

            return result

    async def extract_and_store_async(
        self,
        user_request: str,
        agent_response: Optional[Dict[str, Any]],
        interaction_id: Optional[str] = None
    ) -> ExtractionResult:
        """
        Async version of extract_and_store for background operations.
        
        Args:
            user_request: The user's message/request
            agent_response: The agent's response (can be None)
            interaction_id: Unique identifier for this interaction

        Returns:
            ExtractionResult with details of what was processed
        """
        # Run synchronous version in thread pool to avoid blocking
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.extract_and_store,
            user_request,
            agent_response,
            interaction_id
        )

    def _extract_memories_llm(
        self,
        user_request: str,
        agent_response: Optional[Dict[str, Any]]
    ) -> List[ExtractedMemory]:
        """Use LLM to extract candidate memories from interaction."""
        try:
            # Format agent response
            agent_response_text = ""
            if agent_response:
                if isinstance(agent_response, dict):
                    # Extract message from structured response
                    agent_response_text = agent_response.get("message", "")
                    if not agent_response_text and "steps" in agent_response:
                        # For multi-step responses, summarize the key actions
                        steps = agent_response.get("steps", [])
                        if steps:
                            actions = [s.get("description", "") for s in steps if s.get("description")]
                            agent_response_text = f"Executed: {'; '.join(actions[:3])}"
                else:
                    agent_response_text = str(agent_response)

            # Prepare prompt
            prompt = self.classification_prompt.format(
                user_request=user_request,
                agent_response=agent_response_text
            )

            # Acquire rate limit slot if rate limiter is available
            if self.rate_limiter:
                import asyncio
                # Estimate tokens: prompt + response (conservative estimate)
                estimated_tokens = len(prompt.split()) * 1.3 + 1000  # ~1.3 tokens per word + response
                try:
                    # Run async rate limiter in sync context
                    asyncio.run(self.rate_limiter.acquire(estimated_tokens=int(estimated_tokens)))
                except RuntimeError:
                    # If event loop is already running, create a new one
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.rate_limiter.acquire(estimated_tokens=int(estimated_tokens)))
                    loop.close()

            # Call LLM
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # Use reasoning model for classification
                messages=[
                    {"role": "system", "content": "You are a memory extraction specialist. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for consistency
                max_tokens=1000,
                response_format={"type": "json_object"}  # Ensure JSON response
            )
            
            # Record actual usage if rate limiter is available
            if self.rate_limiter and hasattr(response, 'usage') and hasattr(response.usage, 'total_tokens'):
                actual_tokens = response.usage.total_tokens
                self.rate_limiter.record_usage(actual_tokens=actual_tokens)

            # Parse response
            content = response.choices[0].message.content
            if not content:
                return []

            # Parse JSON - expect array of memory objects
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    memories_data = data
                elif isinstance(data, dict) and "memories" in data:
                    memories_data = data["memories"]
                else:
                    logger.warning(f"[MEMORY EXTRACTION] Unexpected LLM response format: {content[:200]}")
                    return []

                # Convert to ExtractedMemory objects
                memories = []
                for item in memories_data:
                    if isinstance(item, dict) and "content" in item:
                        memory = ExtractedMemory(
                            content=item["content"],
                            category=item.get("category", "general"),
                            tags=item.get("tags", []),
                            confidence=float(item.get("confidence", 0.5)),
                            reasoning=item.get("reasoning", "")
                        )
                        memories.append(memory)

                # Filter by confidence and limit count
                memories = [m for m in memories if m.confidence >= self.min_confidence]
                memories = sorted(memories, key=lambda m: m.confidence, reverse=True)
                memories = memories[:self.max_memories_per_interaction]

                return memories

            except json.JSONDecodeError as e:
                logger.error(f"[MEMORY EXTRACTION] Failed to parse LLM response as JSON: {e}")
                logger.debug(f"[MEMORY EXTRACTION] Raw response: {content}")
                return []

        except Exception as e:
            logger.error(f"[MEMORY EXTRACTION] LLM extraction failed: {e}")
            return []

    def _deduplicate_memories(
        self,
        extracted_memories: List[ExtractedMemory]
    ) -> Tuple[List[ExtractedMemory], List[Tuple[ExtractedMemory, MemoryEntry, float]]]:
        """Deduplicate extracted memories against existing ones using cosine similarity."""
        if not extracted_memories:
            return [], []

        accepted = []
        duplicates = []

        try:
            # Get embeddings for extracted memories
            contents = [m.content for m in extracted_memories]
            embeddings = []

            for content in contents:
                embedding = self.user_memory_store._get_embedding(content)
                embeddings.append(embedding)

            # Check each extracted memory against existing ones
            for i, (memory, embedding) in enumerate(zip(extracted_memories, embeddings)):
                if embedding is None:
                    # No embedding available, assume it's unique
                    accepted.append(memory)
                    continue

                # Query existing memories for similar content
                similar_memories = self.user_memory_store.query_memories(
                    text=memory.content,
                    top_k=3,  # Check top 3 most similar
                    min_score=0.5  # Lower threshold for deduplication check
                )

                # Check if any existing memory is too similar
                is_duplicate = False
                duplicate_info = None

                for existing_memory, score in similar_memories:
                    if score >= self.similarity_threshold:
                        is_duplicate = True
                        duplicate_info = (memory, existing_memory, score)
                        break

                if is_duplicate:
                    duplicates.append(duplicate_info)
                    logger.debug(f"[MEMORY EXTRACTION] Skipped duplicate memory (similarity={duplicate_info[2]:.2f}): {memory.content[:100]}")
                else:
                    accepted.append(memory)

        except Exception as e:
            logger.error(f"[MEMORY EXTRACTION] Deduplication failed: {e}")
            # On failure, accept all memories to avoid losing potentially valuable information
            accepted = extracted_memories

        return accepted, duplicates

    def _store_memories(
        self,
        memories: List[ExtractedMemory],
        interaction_id: Optional[str]
    ) -> List[MemoryEntry]:
        """Store accepted memories in the user memory store."""
        stored = []

        for memory in memories:
            try:
                # Convert to MemoryEntry
                entry = self.user_memory_store.add_memory(
                    content=memory.content,
                    category=memory.category,
                    tags=memory.tags,
                    salience_score=memory.confidence,  # Use confidence as initial salience
                    source_interaction_id=interaction_id
                )
                stored.append(entry)

            except Exception as e:
                logger.error(f"[MEMORY EXTRACTION] Failed to store memory: {e}")

        return stored

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        return {
            "llm_available": LLM_AVAILABLE,
            "similarity_threshold": self.similarity_threshold,
            "min_confidence": self.min_confidence,
            "max_memories_per_interaction": self.max_memories_per_interaction
        }
