"""
LLM batcher for parallel and batched LLM calls.

Enables efficient parallel execution of multiple LLM calls while respecting
rate limits.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
import json

logger = logging.getLogger(__name__)


class LLMBatcher:
    """
    Batch and parallelize LLM calls for better throughput.
    
    Features:
    - Parallel execution of independent LLM calls
    - Automatic batching of similar operations
    - Rate limit aware
    - Error handling and retry
    
    Usage:
        batcher = LLMBatcher(llm, max_parallel=5)
        
        # Parallel execution
        results = await batcher.execute_parallel([
            ("prompt1", {"arg": "val1"}),
            ("prompt2", {"arg": "val2"}),
        ])
    """
    
    def __init__(
        self,
        llm,
        max_parallel: int = 5,
        rate_limiter: Optional[Any] = None
    ):
        """
        Initialize LLM batcher.
        
        Args:
            llm: LangChain LLM instance
            max_parallel: Maximum parallel calls
            rate_limiter: Optional rate limiter instance
        """
        self.llm = llm
        self.max_parallel = max_parallel
        self.rate_limiter = rate_limiter
        self.executor = ThreadPoolExecutor(max_workers=max_parallel)
        
        logger.info(f"[LLM BATCHER] Initialized with max_parallel={max_parallel}")
    
    async def execute_parallel(
        self,
        prompts: List[str],
        callback: Optional[Callable] = None
    ) -> List[str]:
        """
        Execute multiple prompts in parallel.
        
        Args:
            prompts: List of prompt strings
            callback: Optional callback for each result
            
        Returns:
            List of responses in same order as prompts
        """
        if not prompts:
            return []
        
        logger.info(f"[LLM BATCHER] Executing {len(prompts)} prompts in parallel")
        
        # Create tasks
        tasks = []
        for i, prompt in enumerate(prompts):
            task = self._execute_single(prompt, index=i, callback=callback)
            tasks.append(task)
        
        # Execute with semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.max_parallel)
        
        async def bounded_task(task):
            async with semaphore:
                return await task
        
        # Run all tasks
        results = await asyncio.gather(
            *[bounded_task(task) for task in tasks],
            return_exceptions=True
        )
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[LLM BATCHER] Prompt {i} failed: {result}")
                processed_results.append(f"Error: {str(result)}")
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _execute_single(
        self,
        prompt: str,
        index: int,
        callback: Optional[Callable] = None
    ) -> str:
        """Execute a single LLM call."""
        # Acquire rate limit if available
        if self.rate_limiter:
            await self.rate_limiter.acquire(estimated_tokens=len(prompt.split()) * 2)
        
        # Execute in thread pool (LangChain is synchronous)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.executor,
            self._invoke_llm,
            prompt
        )
        
        # Callback if provided
        if callback:
            try:
                callback(index, result)
            except Exception as e:
                logger.error(f"[LLM BATCHER] Callback failed: {e}")
        
        return result
    
    def _invoke_llm(self, prompt: str) -> str:
        """Invoke LLM synchronously (runs in thread pool)."""
        try:
            from langchain_core.messages import HumanMessage
            
            response = self.llm.invoke([HumanMessage(content=prompt)])
            return response.content
        except Exception as e:
            logger.error(f"[LLM BATCHER] LLM invocation failed: {e}")
            raise
    
    async def batch_invoke(
        self,
        items: List[Dict[str, Any]],
        prompt_template: str,
        parse_json: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Batch multiple similar operations into a single LLM call.
        
        Useful for operations like: "summarize these 5 emails",
        "analyze these 3 stocks", etc.
        
        Args:
            items: List of items to process
            prompt_template: Template with {items} placeholder
            parse_json: Whether to parse response as JSON
            
        Returns:
            List of processed results
        """
        if not items:
            return []
        
        # Format items for prompt
        items_str = json.dumps(items, indent=2)
        
        # Create batch prompt
        batch_prompt = prompt_template.format(items=items_str)
        
        logger.info(f"[LLM BATCHER] Batching {len(items)} items into single call")
        
        # Execute
        if self.rate_limiter:
            await self.rate_limiter.acquire(
                estimated_tokens=len(batch_prompt.split()) * 2
            )
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            self.executor,
            self._invoke_llm,
            batch_prompt
        )
        
        # Parse response
        if parse_json:
            try:
                # Extract JSON from response
                json_start = response.find('[')
                json_end = response.rfind(']') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    results = json.loads(json_str)
                    return results
                else:
                    logger.warning("[LLM BATCHER] No JSON array found in response")
                    return [{"error": "Failed to parse response", "raw": response}]
            except json.JSONDecodeError as e:
                logger.error(f"[LLM BATCHER] JSON parse error: {e}")
                return [{"error": str(e), "raw": response}]
        
        return [{"response": response}]
    
    def close(self):
        """Clean up executor."""
        self.executor.shutdown(wait=False)


class ParallelIntentAnalyzer:
    """
    Specialized batcher for parallel intent analysis and tool filtering.
    
    Used in the planner to run intent analysis and tool preparation in parallel.
    """
    
    def __init__(self, llm, rate_limiter: Optional[Any] = None):
        """
        Initialize parallel intent analyzer.
        
        Args:
            llm: LangChain LLM instance
            rate_limiter: Optional rate limiter
        """
        self.llm = llm
        self.rate_limiter = rate_limiter
        self.executor = ThreadPoolExecutor(max_workers=3)
    
    async def analyze_with_prep(
        self,
        goal: str,
        intent_analyzer: Callable,
        tool_preparer: Callable,
        available_tools: List[Any]
    ) -> tuple:
        """
        Run intent analysis and tool prep in parallel.
        
        Args:
            goal: User's goal
            intent_analyzer: Function to analyze intent
            tool_preparer: Function to prepare tools
            available_tools: List of available tools
            
        Returns:
            Tuple of (intent_result, prepared_tools)
        """
        logger.info("[PARALLEL ANALYZER] Running intent analysis and tool prep in parallel")
        
        # Create tasks
        intent_task = asyncio.create_task(
            asyncio.to_thread(intent_analyzer, goal)
        )
        
        tool_task = asyncio.create_task(
            asyncio.to_thread(tool_preparer, available_tools)
        )
        
        # Run in parallel
        intent_result, prepared_tools = await asyncio.gather(
            intent_task,
            tool_task,
            return_exceptions=False
        )
        
        logger.info("[PARALLEL ANALYZER] Parallel analysis complete")
        
        return intent_result, prepared_tools
    
    def close(self):
        """Clean up executor."""
        self.executor.shutdown(wait=False)

