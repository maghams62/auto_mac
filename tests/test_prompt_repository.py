"""
Tests for PromptRepository atomic loading functionality.

These tests ensure that the prompt loading system:
1. Loads examples atomically based on task characteristics
2. Respects token budgets
3. Falls back gracefully when atomic loading fails
4. Provides proper metadata extraction
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path

from src.prompt_repository import PromptRepository


class TestPromptRepository:
    """Test suite for PromptRepository atomic loading."""

    @pytest.fixture
    def repo(self):
        """Create a PromptRepository instance for testing."""
        return PromptRepository()

    def test_load_atomic_examples_email_summarization(self, repo):
        """Test loading atomic examples for email summarization tasks."""
        task_chars = {'task_type': 'email_summarization', 'domain': 'email'}

        examples = repo.load_atomic_examples(task_chars, max_tokens=2000)

        # Should load email-related examples within token budget
        assert isinstance(examples, str)
        assert len(examples) > 0

        tokens = repo._estimate_tokens(examples)
        assert tokens <= 2000

    def test_load_atomic_examples_web_search(self, repo):
        """Test loading atomic examples for web search tasks."""
        task_chars = {'task_type': 'web_search', 'domain': 'web'}

        examples = repo.load_atomic_examples(task_chars, max_tokens=1500)

        assert isinstance(examples, str)
        tokens = repo._estimate_tokens(examples)
        assert tokens <= 1500

    def test_token_budget_enforcement(self, repo):
        """Test that token budgets are strictly enforced."""
        task_chars = {'task_type': 'email_summarization', 'domain': 'email'}

        # Test with very small budget
        examples_small = repo.load_atomic_examples(task_chars, max_tokens=100)
        tokens_small = repo._estimate_tokens(examples_small)
        assert tokens_small <= 100

        # Test with larger budget
        examples_large = repo.load_atomic_examples(task_chars, max_tokens=5000)
        tokens_large = repo._estimate_tokens(examples_large)
        assert tokens_large <= 5000

        # Smaller budget should result in fewer tokens
        assert tokens_small <= tokens_large

    def test_fallback_behavior(self, repo):
        """Test fallback to category loading when task type not found."""
        # Use a task type that doesn't exist
        task_chars = {'task_type': 'nonexistent_task', 'domain': 'email'}

        examples = repo.load_atomic_examples(task_chars, max_tokens=2000)

        # Should fall back to domain-based loading
        assert isinstance(examples, str)
        assert len(examples) > 0

    def test_metadata_extraction(self, repo):
        """Test that metadata is properly extracted from examples."""
        # Test a known example
        metadata = repo.get_example_metadata('email', '08_example_summarize_last_n_emails.md')

        assert 'task_type' in metadata
        assert 'domain' in metadata
        assert 'title' in metadata
        assert metadata['task_type'] == 'email_summarization'
        assert metadata['domain'] == 'email'

    def test_find_examples_by_task_type(self, repo):
        """Test finding examples by task type."""
        matches = repo.find_examples_by_task_type('email_summarization', limit=5)

        assert isinstance(matches, list)
        for category, filename, metadata in matches:
            assert metadata.get('task_type') == 'email_summarization'
            assert isinstance(metadata, dict)

    def test_load_single_example(self, repo):
        """Test loading individual examples."""
        content = repo.load_single_example('email', '08_example_summarize_last_n_emails.md')

        assert isinstance(content, str)
        assert len(content) > 0
        assert '## Example 28:' in content

    def test_estimate_tokens(self, repo):
        """Test token estimation accuracy."""
        text = "This is a test string with some words."
        tokens = repo._estimate_tokens(text)

        # Should be roughly 1.3 * word count
        expected_words = len(text.split())
        expected_tokens = int(expected_words * 1.3)

        assert tokens == expected_tokens

    @patch('src.prompt_repository.PromptRepository.load_category')
    def test_atomic_loading_error_handling(self, mock_load_category, repo):
        """Test error handling in atomic loading."""
        # Make load_category raise an exception
        mock_load_category.side_effect = Exception("Test error")

        task_chars = {'task_type': 'nonexistent_task', 'domain': 'nonexistent_domain'}

        # Should not raise exception, should return empty string
        examples = repo.load_atomic_examples(task_chars, max_tokens=1000)
        assert examples == ""

    def test_extract_task_metadata_from_content(self, repo):
        """Test metadata extraction from raw content."""
        sample_content = '''
        ## Example 1: Test Task

        ### User Request
        "Test request"

        ### Decomposition
        ```json
        {
          "task_type": "test_task",
          "complexity": "simple"
        }
        ```
        '''

        metadata = repo.extract_task_metadata(sample_content)

        assert metadata['title'] == 'Test Task'
        assert metadata['user_request'] == 'Test request'
        assert metadata['task_type'] == 'test_task'
        assert metadata['complexity'] == 'simple'


class TestAtomicPromptIntegration:
    """Integration tests for atomic prompt loading in the agent."""

    def test_agent_task_characteristics_extraction(self):
        """Test that agent correctly extracts task characteristics."""
        from src.agent.agent import Agent

        # Mock agent with minimal config
        config = MagicMock()
        config.get.return_value = {'max_tokens': 2000}

        agent = Agent.__new__(Agent)  # Create without __init__
        agent.config = config

        # Test various request types
        test_cases = [
            ("summarize my emails", {'domain': 'email', 'task_type': 'email_summarization'}),
            ("search for python tutorials", {'domain': 'web', 'task_type': 'web_search'}),
            ("find all PDF files", {'domain': 'file', 'task_type': 'file_search'}),
            ("take a screenshot", {'domain': 'screen', 'task_type': 'screen_capture'}),
        ]

        for request, expected_chars in test_cases:
            characteristics = agent._extract_task_characteristics(request)

            # Check that expected characteristics are present
            for key, value in expected_chars.items():
                assert characteristics.get(key) == value, f"Failed for request: {request}"

    @patch('src.prompt_repository.PromptRepository')
    def test_agent_atomic_loading_integration(self, mock_repo_class):
        """Test integration between agent and PromptRepository."""
        from src.agent.agent import Agent

        # Mock repository
        mock_repo = MagicMock()
        mock_repo.load_atomic_examples.return_value = "Test examples"
        mock_repo._estimate_tokens.return_value = 500
        mock_repo_class.return_value = mock_repo

        # Mock agent
        config = MagicMock()
        config.get.return_value = {'enabled': True, 'max_tokens': 2000}
        agent = Agent.__new__(Agent)
        agent.config = config

        # Test atomic loading
        examples = agent._load_atomic_examples_for_request("test request")

        assert examples == "Test examples"
        mock_repo.load_atomic_examples.assert_called_once()

    def test_configuration_integration(self):
        """Test that configuration properly controls atomic loading."""
        from src.agent.agent import Agent

        # Test with atomic prompts disabled
        config_disabled = MagicMock()
        config_disabled.get.return_value = {'enabled': False}
        agent_disabled = Agent.__new__(Agent)
        agent_disabled.config = config_disabled
        agent_disabled.prompts = {'few_shot_examples': 'fallback_content'}

        result = agent_disabled._load_atomic_examples_for_request("test")
        assert result == 'fallback_content'

        # Test with atomic prompts enabled
        config_enabled = MagicMock()
        config_enabled.get.return_value = {'enabled': True, 'max_tokens': 1000}
        agent_enabled = Agent.__new__(Agent)
        agent_enabled.config = config_enabled

        # Should attempt atomic loading (would fail in this test but shows the path)
        with patch('src.prompt_repository.PromptRepository') as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.load_atomic_examples.return_value = ""
            mock_repo_class.return_value = mock_repo

            result = agent_enabled._load_atomic_examples_for_request("test")
            assert result == 'fallback_content'  # Empty atomic result triggers fallback
