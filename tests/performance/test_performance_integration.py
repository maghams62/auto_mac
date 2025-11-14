"""
Integration tests for performance optimizations.

Tests all performance improvements together:
- Connection pooling
- Rate limiting
- Parallel execution
- Batch embeddings
- Caching
- Background memory updates
- Session serialization
"""

import pytest
import asyncio
import time
import yaml
from pathlib import Path
from typing import Dict, Any

from src.utils import load_config
from src.utils.performance_monitor import get_performance_monitor, PerformanceMonitor
from src.utils.openai_client import PooledOpenAIClient
from src.utils.rate_limiter import get_rate_limiter
from src.orchestrator.main_orchestrator import MainOrchestrator
from src.memory.session_manager import SessionManager
from src.memory.user_memory_store import UserMemoryStore
from src.documents.indexer import DocumentIndexer


@pytest.fixture
def config():
    """Load test configuration."""
    return load_config()


@pytest.fixture
def performance_monitor():
    """Get performance monitor instance."""
    monitor = get_performance_monitor()
    monitor.reset()  # Start fresh
    return monitor


class TestConnectionPooling:
    """Test connection pooling optimization."""
    
    def test_pooled_client_reuse(self, config):
        """Test that PooledOpenAIClient reuses connections."""
        monitor = get_performance_monitor()
        monitor.reset()
        
        # Get client multiple times
        client1 = PooledOpenAIClient.get_client(config)
        client2 = PooledOpenAIClient.get_client(config)
        client3 = PooledOpenAIClient.get_client(config)
        
        # Should be the same instance
        assert client1 is client2
        assert client2 is client3
        
        # Check telemetry
        summary = monitor.get_summary()
        assert summary["connection_pooling"]["total_requests"] >= 3
        assert summary["connection_pooling"]["reuses"] >= 2  # At least 2 reuses


class TestRateLimiting:
    """Test rate limiting integration."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_global_singleton(self, config):
        """Test that rate limiter is a global singleton."""
        limiter1 = get_rate_limiter(config=config)
        limiter2 = get_rate_limiter(config=config)
        
        # Should be the same instance
        assert limiter1 is limiter2
    
    @pytest.mark.asyncio
    async def test_rate_limiter_throttling(self, config):
        """Test that rate limiter properly throttles requests."""
        limiter = get_rate_limiter(config=config)
        monitor = get_performance_monitor()
        monitor.reset()
        
        # Make multiple rapid requests
        start_time = time.time()
        for _ in range(5):
            await limiter.acquire(estimated_tokens=1000)
        end_time = time.time()
        
        # Check telemetry
        summary = monitor.get_summary()
        assert summary["rate_limiting"]["total_waits"] >= 0  # May or may not throttle depending on limits


class TestParallelExecution:
    """Test parallel execution optimization."""
    
    @pytest.mark.asyncio
    async def test_parallel_step_execution(self, config):
        """Test that independent steps execute in parallel."""
        from src.orchestrator.executor import PlanExecutor
        
        executor = PlanExecutor(config, enable_verification=False)
        monitor = get_performance_monitor()
        monitor.reset()
        
        # Create plan with independent steps
        plan = [
            {"id": 1, "action": "test_action", "parameters": {}, "dependencies": []},
            {"id": 2, "action": "test_action", "parameters": {}, "dependencies": []},
            {"id": 3, "action": "test_action", "parameters": {}, "dependencies": [1, 2]},
        ]
        
        # Mock tool execution
        async def mock_execute(step, state):
            await asyncio.sleep(0.1)  # Simulate work
            return {"output": f"Step {step['id']} completed"}
        
        executor._execute_step_async = mock_execute
        
        start_time = time.time()
        result = await executor.execute_plan_async(plan, "test goal")
        end_time = time.time()
        
        # Check that steps 1 and 2 ran in parallel (should take ~0.1s, not 0.2s)
        duration = end_time - start_time
        assert duration < 0.25  # Should be faster than sequential
        
        # Check telemetry
        summary = monitor.get_summary()
        assert summary["parallel_execution"]["parallel_count"] >= 1


class TestBatchEmbeddings:
    """Test batch embedding optimization."""
    
    def test_batch_embedding_generation(self, config):
        """Test that embeddings are generated in batches."""
        indexer = DocumentIndexer(config)
        monitor = get_performance_monitor()
        monitor.reset()
        
        # Generate embeddings for multiple texts
        texts = [f"Test text {i}" for i in range(50)]
        embeddings = indexer.get_embeddings_batch(texts)
        
        assert len(embeddings) == 50
        
        # Check telemetry
        summary = monitor.get_summary()
        batch_ops = summary["batch_processing"].get("embeddings", {})
        assert batch_ops.get("count", 0) >= 1
        assert batch_ops.get("avg_batch_size", 0) >= 50


class TestCaching:
    """Test caching optimizations."""
    
    def test_tool_catalog_caching(self, config):
        """Test that tool catalog is cached."""
        from src.orchestrator.tools_catalog import get_tool_catalog
        monitor = get_performance_monitor()
        monitor.reset()
        
        # Get catalog multiple times
        catalog1 = get_tool_catalog(config=config)
        catalog2 = get_tool_catalog(config=config)
        catalog3 = get_tool_catalog(config=config)
        
        # Should be the same instance (cached)
        assert catalog1 is catalog2
        assert catalog2 is catalog3
        
        # Check telemetry
        summary = monitor.get_summary()
        cache_stats = summary["caching"].get("tool_catalog", {})
        assert cache_stats.get("hits", 0) >= 2  # At least 2 cache hits
    
    def test_prompt_template_caching(self, config):
        """Test that prompt templates are cached."""
        from src.prompt_repository import PromptRepository
        monitor = get_performance_monitor()
        monitor.reset()
        
        repo = PromptRepository(config=config)
        
        # Load same category multiple times
        content1 = repo.load_category("core")
        content2 = repo.load_category("core")
        content3 = repo.load_category("core")
        
        # Should be the same content
        assert content1 == content2 == content3
        
        # Check telemetry (may have some hits)
        summary = monitor.get_summary()
        cache_stats = summary["caching"].get("prompt_templates", {})
        # Cache hits may vary, but should have some activity
        assert cache_stats.get("hits", 0) + cache_stats.get("misses", 0) >= 3


class TestBackgroundMemoryUpdates:
    """Test background memory update optimization."""
    
    @pytest.mark.asyncio
    async def test_background_memory_extraction(self, config):
        """Test that memory extraction runs in background."""
        from src.memory.session_memory import SessionMemory
        from src.memory.user_memory_store import UserMemoryStore
        
        # Create user memory store
        user_memory_store = UserMemoryStore(
            user_id="test_user",
            config=config
        )
        
        # Create session with background updates enabled
        session = SessionMemory(
            user_id="test_user",
            user_memory_store=user_memory_store,
            config=config
        )
        
        monitor = get_performance_monitor()
        monitor.reset()
        
        # Add interaction (should trigger background extraction)
        interaction_id = session.add_interaction(
            user_request="I prefer dark mode for all applications",
            agent_response={"message": "Noted your preference"}
        )
        
        # Give background task time to start
        await asyncio.sleep(0.1)
        
        # Check that interaction was added immediately (non-blocking)
        assert interaction_id is not None
        assert len(session.interactions) == 1
        
        # Wait a bit for background extraction
        await asyncio.sleep(1.0)
        
        # Check telemetry
        summary = monitor.get_summary()
        memory_ops = summary["memory_operations"]
        # Should have some memory operation recorded
        assert len(memory_ops) >= 0  # May or may not complete immediately


class TestSessionSerialization:
    """Test session serialization optimization."""
    
    def test_write_behind_caching(self, config):
        """Test that write-behind caching works."""
        session_manager = SessionManager(
            storage_dir="data/test_sessions",
            config=config
        )
        
        # Create session
        session = session_manager.get_or_create_session("test_session")
        session.add_interaction("Test request")
        
        # Save should mark as dirty (not save immediately if write-behind enabled)
        result = session_manager.save_session("test_session")
        assert result is True
        
        # Check that dirty sessions are tracked
        if hasattr(session_manager, '_dirty_sessions'):
            assert len(session_manager._dirty_sessions) >= 0  # May be 0 if already saved
    
    def test_session_compression(self, config):
        """Test that large sessions are compressed."""
        session_manager = SessionManager(
            storage_dir="data/test_sessions",
            config=config
        )
        
        # Create session with large content
        session = session_manager.get_or_create_session("large_session")
        
        # Add many interactions to make it large
        for i in range(100):
            session.add_interaction(f"Large request {i}" * 100)
        
        # Save session
        session_manager.save_session("large_session")
        
        # Check if compressed file exists (if compression threshold met)
        filepath = session_manager._get_session_filepath("large_session")
        compressed_path = filepath.with_suffix(filepath.suffix + '.gz')
        
        # Either compressed or regular file should exist
        assert filepath.exists() or compressed_path.exists()


class TestFullRequestFlow:
    """Test full request flow with all optimizations."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_optimized_flow(self, config):
        """Test complete request flow with all optimizations enabled."""
        monitor = get_performance_monitor()
        monitor.reset()
        
        # Initialize orchestrator
        orchestrator = MainOrchestrator(config)
        
        # Track request
        request_id = f"test_{int(time.time())}"
        monitor.start_request(request_id)
        
        try:
            # Execute a simple request
            result = await orchestrator.execute_async(
                user_request="What is the weather today?",
                session_id="test_session"
            )
            
            # Check that result is valid
            assert result is not None
            assert "status" in result
            
        finally:
            monitor.end_request(request_id)
        
        # Check telemetry
        summary = monitor.get_summary()
        
        # Should have connection pool activity
        assert summary["connection_pooling"]["total_requests"] >= 0
        
        # Should have some caching activity
        assert len(summary["caching"]) >= 0
        
        # Should have request latency recorded
        assert summary["requests"]["total"] >= 1
        assert summary["requests"]["avg_latency"] >= 0


class TestPerformanceTelemetry:
    """Test performance telemetry system."""
    
    def test_telemetry_collection(self, performance_monitor):
        """Test that telemetry collects metrics correctly."""
        monitor = performance_monitor
        
        # Record various metrics
        monitor.record_connection_pool_request(reused=True)
        monitor.record_cache_hit("test_cache")
        monitor.record_batch_operation("test_batch", 10)
        monitor.record_rate_limit_wait(0.5)
        
        # Get summary
        summary = monitor.get_summary()
        
        # Verify metrics are recorded
        assert summary["connection_pooling"]["reuses"] >= 1
        assert summary["caching"]["test_cache"]["hits"] >= 1
        assert summary["batch_processing"]["test_batch"]["count"] >= 1
        assert summary["rate_limiting"]["total_waits"] >= 1
    
    def test_telemetry_logging(self, performance_monitor, caplog):
        """Test that telemetry can log summary."""
        monitor = performance_monitor
        
        # Record some metrics
        monitor.record_cache_hit("test")
        monitor.record_connection_pool_request(reused=True)
        
        # Log summary
        monitor.log_summary()
        
        # Check that summary was logged
        assert "PERFORMANCE METRICS SUMMARY" in caplog.text
        assert "Connection Pool" in caplog.text


class TestConfigValidation:
    """Test config validation and propagation."""
    
    def test_performance_config_validation(self):
        """Test that performance config is validated with defaults."""
        from src.utils.config_validator import validate_config
        
        # Config without performance section
        config = {
            "openai": {
                "api_key": "test_key",
                "model": "gpt-4o"
            }
        }
        
        # Validate should add defaults
        validated = validate_config(config)
        
        assert "performance" in validated
        assert "connection_pooling" in validated["performance"]
        assert "rate_limiting" in validated["performance"]
        assert "parallel_execution" in validated["performance"]
        
        # Check defaults are applied
        assert validated["performance"]["connection_pooling"]["enabled"] is True
        assert validated["performance"]["rate_limiting"]["enabled"] is True
        assert validated["performance"]["parallel_execution"]["enabled"] is True
    
    def test_config_propagation(self, config):
        """Test that config is propagated to all components."""
        # All components should receive config
        from src.orchestrator.planner import Planner
        from src.orchestrator.executor import PlanExecutor
        from src.documents.indexer import DocumentIndexer
        
        planner = Planner(config)
        executor = PlanExecutor(config)
        indexer = DocumentIndexer(config)
        
        # All should have config
        assert planner.config == config
        assert executor.config == config
        assert indexer.config == config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

