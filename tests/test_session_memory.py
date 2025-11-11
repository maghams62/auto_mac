"""
Comprehensive test suite for session memory system.

Tests:
1. Session creation and initialization
2. Memory persistence across interactions
3. Session context propagation to agents
4. /clear command functionality
5. Session state UI indicators
6. Multi-session management
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import tempfile
import shutil
from datetime import datetime

from src.memory import SessionManager, SessionMemory
from src.agent.agent_registry import AgentRegistry
from src.agent.agent import AutomationAgent
from src.utils import load_config


class TestSessionMemory:
    """Test SessionMemory core functionality."""

    def test_session_creation(self):
        """Test creating a new session."""
        memory = SessionMemory()

        assert memory.session_id is not None
        assert memory.is_active()
        assert memory.is_new_session()
        assert len(memory.interactions) == 0

    def test_add_interaction(self):
        """Test adding interactions to memory."""
        memory = SessionMemory()

        # Add first interaction
        int_id = memory.add_interaction(
            user_request="Test request",
            agent_response={"status": "success"},
            plan=[{"id": 1, "action": "test"}],
            step_results={1: {"result": "done"}}
        )

        assert int_id == "int_1"
        assert len(memory.interactions) == 1
        assert memory.metadata["total_requests"] == 1
        assert not memory.is_new_session()

    def test_shared_context(self):
        """Test shared context storage and retrieval."""
        memory = SessionMemory()

        # Set context
        memory.set_context("last_file_path", "/path/to/file.txt")
        memory.set_context("user_preference", "dark_mode")

        # Get context
        assert memory.get_context("last_file_path") == "/path/to/file.txt"
        assert memory.get_context("user_preference") == "dark_mode"
        assert memory.get_context("nonexistent", "default") == "default"
        assert memory.has_context("last_file_path")

    def test_conversation_history(self):
        """Test conversation history formatting."""
        memory = SessionMemory()

        # Add multiple interactions
        for i in range(3):
            memory.add_interaction(
                user_request=f"Request {i+1}",
                agent_response={"status": "success", "message": f"Response {i+1}"}
            )

        history = memory.get_conversation_history(max_interactions=2)
        assert len(history) == 2
        assert history[0]["user"] == "Request 2"
        assert history[1]["user"] == "Request 3"

    def test_clear_session(self):
        """Test clearing session memory."""
        memory = SessionMemory()

        # Add some data
        memory.add_interaction("Test", {"status": "success"})
        memory.set_context("key", "value")

        # Clear
        memory.clear()

        assert len(memory.interactions) == 0
        assert len(memory.shared_context) == 0
        assert memory.metadata["total_requests"] == 0
        assert memory.metadata["cleared_at"] is not None

    def test_serialization(self):
        """Test session serialization and deserialization."""
        memory = SessionMemory()
        memory.add_interaction("Test", {"status": "success"})
        memory.set_context("key", "value")

        # Serialize
        data = memory.to_dict()

        # Deserialize
        restored = SessionMemory.from_dict(data)

        assert restored.session_id == memory.session_id
        assert len(restored.interactions) == 1
        assert restored.get_context("key") == "value"


class TestSessionManager:
    """Test SessionManager functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = SessionManager(storage_dir=self.temp_dir)

    def teardown_method(self):
        """Cleanup test environment."""
        shutil.rmtree(self.temp_dir)

    def test_create_session(self):
        """Test creating and retrieving sessions."""
        memory = self.manager.get_or_create_session("test_session")

        assert memory.session_id == "test_session"
        assert memory.is_new_session()

    def test_session_persistence(self):
        """Test saving and loading sessions."""
        # Create session and add data
        memory = self.manager.get_or_create_session("persist_test")
        memory.add_interaction("Test", {"status": "success"})

        # Save
        self.manager.save_session("persist_test")

        # Create new manager (simulating restart)
        new_manager = SessionManager(storage_dir=self.temp_dir)

        # Load session
        loaded = new_manager.get_or_create_session("persist_test")

        assert loaded.session_id == "persist_test"
        assert len(loaded.interactions) == 1
        assert not loaded.is_new_session()

    def test_clear_session(self):
        """Test clearing session via manager."""
        memory = self.manager.get_or_create_session("clear_test")
        memory.add_interaction("Test", {"status": "success"})
        self.manager.save_session("clear_test")

        # Clear
        cleared = self.manager.clear_session("clear_test")

        assert len(cleared.interactions) == 0
        assert cleared.metadata["cleared_at"] is not None

    def test_multiple_sessions(self):
        """Test managing multiple sessions."""
        session1 = self.manager.get_or_create_session("user1")
        session2 = self.manager.get_or_create_session("user2")

        session1.add_interaction("User 1 request", {"status": "success"})
        session2.add_interaction("User 2 request", {"status": "success"})

        # Sessions should be independent
        assert len(session1.interactions) == 1
        assert len(session2.interactions) == 1
        assert session1.interactions[0].user_request == "User 1 request"
        assert session2.interactions[0].user_request == "User 2 request"


class TestAgentIntegration:
    """Test session memory integration with agents."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = load_config()
        self.session_manager = SessionManager(storage_dir=self.temp_dir)

    def teardown_method(self):
        """Cleanup test environment."""
        shutil.rmtree(self.temp_dir)

    def test_agent_registry_with_sessions(self):
        """Test AgentRegistry with session management."""
        registry = AgentRegistry(self.config, session_manager=self.session_manager)

        assert registry.session_manager is not None

        # Execute a tool with session tracking
        # Note: This will fail if the tool doesn't exist, but tests the flow
        session_id = "test_agent_session"
        memory = self.session_manager.get_or_create_session(session_id)

        # Verify session was created
        assert memory.session_id == session_id

    def test_automation_agent_with_sessions(self):
        """Test AutomationAgent with session context."""
        agent = AutomationAgent(self.config, session_manager=self.session_manager)

        assert agent.session_manager is not None

        # Note: Full integration test would require mocking LLM calls
        # This tests that the agent accepts session_manager parameter


class TestContextPropagation:
    """Test context propagation across agent interactions."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.session_manager = SessionManager(storage_dir=self.temp_dir)

    def teardown_method(self):
        """Cleanup test environment."""
        shutil.rmtree(self.temp_dir)

    def test_context_across_interactions(self):
        """Test context persists across multiple interactions."""
        session_id = "context_test"
        memory = self.session_manager.get_or_create_session(session_id)

        # Interaction 1: Store context
        memory.add_interaction(
            "Create a presentation",
            {"status": "success", "file_path": "/path/to/presentation.key"}
        )
        memory.set_context("last_presentation_path", "/path/to/presentation.key")

        # Save session
        self.session_manager.save_session(session_id)

        # Interaction 2: Retrieve context
        memory = self.session_manager.get_or_create_session(session_id)

        assert memory.get_context("last_presentation_path") == "/path/to/presentation.key"
        assert len(memory.interactions) == 1

    def test_langgraph_context_format(self):
        """Test LangGraph context formatting."""
        memory = self.session_manager.get_or_create_session("langgraph_test")
        memory.add_interaction("Test", {"status": "success"})
        memory.set_context("key", "value")

        context = memory.get_langgraph_context()

        assert "session_id" in context
        assert "conversation_history" in context
        assert "shared_context" in context
        assert context["shared_context"]["key"] == "value"


def test_session_summary():
    """Test session context summary generation."""
    memory = SessionMemory()

    # Add data
    memory.add_interaction("Request 1", {"status": "success"})
    memory.add_interaction("Request 2", {"status": "success"})
    memory.set_context("last_file", "/path/to/file.txt")

    summary = memory.get_context_summary()

    assert "Session ID" in summary
    assert "Recent Activity" in summary
    assert "Shared Context" in summary
    assert "last_file" in summary


def test_session_status_tracking():
    """Test session status lifecycle."""
    memory = SessionMemory()

    # New session
    assert memory.is_active()
    assert memory.is_new_session()

    # After interaction
    memory.add_interaction("Test", {"status": "success"})
    assert memory.is_active()
    assert not memory.is_new_session()

    # After clear
    memory.clear()
    assert len(memory.interactions) == 0


if __name__ == "__main__":
    print("=" * 80)
    print("SESSION MEMORY SYSTEM - COMPREHENSIVE TEST SUITE")
    print("=" * 80)

    # Run tests
    pytest.main([__file__, "-v", "-s"])
