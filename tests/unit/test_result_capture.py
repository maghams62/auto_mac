"""
Unit tests for ResultCapture class.

Tests thread-safe result capture mechanism that allows agent.run()
to return as soon as finalize() sets the result, even if graph.invoke()
continues running in the background.
"""

import pytest
import threading
import time
from src.agent.agent import ResultCapture


class TestResultCapture:
    """Test ResultCapture thread-safety and behavior."""

    def test_result_capture_basic(self):
        """Test basic set/get functionality."""
        capture = ResultCapture()
        
        assert not capture.is_captured()
        assert capture.get() is None
        
        result = {"status": "success", "message": "Test"}
        capture.set(result)
        
        assert capture.is_captured()
        assert capture.get() == result

    def test_result_capture_wait(self):
        """Test wait() method returns immediately when result is already set."""
        capture = ResultCapture()
        result = {"status": "success", "message": "Test"}
        capture.set(result)
        
        # Should return immediately
        retrieved = capture.wait(timeout=1.0)
        assert retrieved == result

    def test_result_capture_wait_timeout(self):
        """Test wait() times out when result is never set."""
        capture = ResultCapture()
        
        # Should timeout after 0.1 seconds
        retrieved = capture.wait(timeout=0.1)
        assert retrieved is None

    def test_result_capture_concurrent_set(self):
        """Test that concurrent set() calls are safe."""
        capture = ResultCapture()
        result1 = {"status": "success", "message": "Test1"}
        result2 = {"status": "error", "message": "Test2"}
        
        # Set from multiple threads simultaneously
        def set_result(result):
            capture.set(result)
        
        t1 = threading.Thread(target=set_result, args=(result1,))
        t2 = threading.Thread(target=set_result, args=(result2,))
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        # Should have captured one of them (first one wins)
        assert capture.is_captured()
        captured = capture.get()
        assert captured in [result1, result2]

    def test_result_capture_concurrent_wait(self):
        """Test that multiple threads waiting return the same result."""
        capture = ResultCapture()
        result = {"status": "success", "message": "Test"}
        
        retrieved_results = []
        
        def wait_for_result():
            retrieved = capture.wait(timeout=2.0)
            retrieved_results.append(retrieved)
        
        # Start multiple threads waiting
        threads = [threading.Thread(target=wait_for_result) for _ in range(5)]
        for t in threads:
            t.start()
        
        # Give threads time to start waiting
        time.sleep(0.1)
        
        # Set the result
        capture.set(result)
        
        # Wait for all threads to finish
        for t in threads:
            t.join(timeout=3.0)
        
        # All threads should have retrieved the same result
        assert len(retrieved_results) == 5
        assert all(r == result for r in retrieved_results)

    def test_result_capture_wait_then_set(self):
        """Test wait() blocks until result is set."""
        capture = ResultCapture()
        result = {"status": "success", "message": "Test"}
        
        retrieved_result = None
        
        def wait_thread():
            nonlocal retrieved_result
            retrieved_result = capture.wait(timeout=5.0)
        
        # Start thread waiting
        wait_t = threading.Thread(target=wait_thread)
        wait_t.start()
        
        # Give thread time to start waiting
        time.sleep(0.1)
        
        # Verify it's still waiting
        assert retrieved_result is None
        
        # Set the result
        capture.set(result)
        
        # Wait for thread to finish
        wait_t.join(timeout=6.0)
        
        # Should have retrieved the result
        assert retrieved_result == result

    def test_result_capture_multiple_set_ignored(self):
        """Test that setting result multiple times only captures first."""
        capture = ResultCapture()
        result1 = {"status": "success", "message": "First"}
        result2 = {"status": "error", "message": "Second"}
        
        capture.set(result1)
        assert capture.get() == result1
        
        # Second set should be ignored
        capture.set(result2)
        assert capture.get() == result1  # Still first result

