"""
Test Bluesky tweet accuracy and success criteria.

Tests that:
1. "Last N tweets" returns exactly N tweets
2. Tweets are in chronological order (most recent first)
3. Tweets are from the correct user
4. No random or unrelated tweets
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, timezone

from src.agent.bluesky_agent import summarize_bluesky_posts, get_bluesky_author_feed


def test_last_n_tweets_exact_count():
    """Test that 'last N tweets' returns exactly N tweets."""
    # Mock the BlueskyAPIClient
    mock_posts = []
    for i in range(10):
        mock_posts.append({
            "post": {
                "uri": f"at://test.bsky.social/app.bsky.feed.post/{i}",
                "record": {
                    "text": f"Test tweet {i}",
                    "createdAt": (datetime.now(timezone.utc) - timedelta(hours=i)).isoformat().replace("+00:00", "Z")
                },
                "author": {
                    "handle": "test.bsky.social",
                    "displayName": "Test User"
                },
                "likeCount": 0,
                "repostCount": 0,
                "replyCount": 0,
                "quoteCount": 0
            }
        })
    
    with patch('src.agent.bluesky_agent.BlueskyAPIClient') as mock_client_class:
        mock_client = Mock()
        mock_client.get_author_feed.return_value = {"feed": mock_posts}
        mock_client_class.return_value = mock_client
        
        # Test "last 5 tweets"
        result = summarize_bluesky_posts.invoke({
            "query": "last 5 tweets",
            "max_items": 5
        })
        
        assert result.get("error") is not True
        assert result.get("count") == 5
        assert result.get("requested_count") == 5
        assert len(result.get("items", [])) == 5


def test_tweets_chronological_order():
    """Test that tweets are returned in chronological order (most recent first)."""
    # Create mock posts with different timestamps
    base_time = datetime.now(timezone.utc)
    mock_posts = []
    for i in range(5):
        mock_posts.append({
            "post": {
                "uri": f"at://test.bsky.social/app.bsky.feed.post/{i}",
                "record": {
                    "text": f"Test tweet {i}",
                    "createdAt": (base_time - timedelta(hours=i)).isoformat().replace("+00:00", "Z")
                },
                "author": {
                    "handle": "test.bsky.social",
                    "displayName": "Test User"
                },
                "likeCount": 0,
                "repostCount": 0,
                "replyCount": 0,
                "quoteCount": 0
            }
        })
    
    with patch('src.agent.bluesky_agent.BlueskyAPIClient') as mock_client_class:
        mock_client = Mock()
        mock_client.get_author_feed.return_value = {"feed": mock_posts}
        mock_client_class.return_value = mock_client
        
        result = summarize_bluesky_posts.invoke({
            "query": "last 5 tweets",
            "max_items": 5
        })
        
        items = result.get("items", [])
        if len(items) > 1:
            timestamps = [item.get("created_at", "") for item in items if item.get("created_at")]
            if len(timestamps) > 1:
                # Parse timestamps and check order
                parsed_times = [datetime.fromisoformat(ts.replace("Z", "+00:00")) for ts in timestamps]
                # Should be descending (most recent first)
                is_descending = all(parsed_times[i] >= parsed_times[i+1] for i in range(len(parsed_times)-1))
                assert is_descending, "Tweets should be in chronological order (most recent first)"


def test_tweets_correct_user():
    """Test that tweets are from the correct user."""
    mock_posts = []
    for i in range(5):
        mock_posts.append({
            "post": {
                "uri": f"at://test.bsky.social/app.bsky.feed.post/{i}",
                "record": {
                    "text": f"Test tweet {i}",
                    "createdAt": (datetime.now(timezone.utc) - timedelta(hours=i)).isoformat().replace("+00:00", "Z")
                },
                "author": {
                    "handle": "test.bsky.social",
                    "displayName": "Test User"
                },
                "likeCount": 0,
                "repostCount": 0,
                "replyCount": 0,
                "quoteCount": 0
            }
        })
    
    with patch('src.agent.bluesky_agent.BlueskyAPIClient') as mock_client_class:
        mock_client = Mock()
        mock_client.get_author_feed.return_value = {"feed": mock_posts}
        mock_client_class.return_value = mock_client
        
        result = summarize_bluesky_posts.invoke({
            "query": "last 5 tweets",
            "max_items": 5
        })
        
        items = result.get("items", [])
        for item in items:
            assert item.get("author_handle") == "test.bsky.social", "All tweets should be from the correct user"


def test_tweets_not_random():
    """Test that tweets are not random or unrelated."""
    mock_posts = []
    for i in range(5):
        mock_posts.append({
            "post": {
                "uri": f"at://test.bsky.social/app.bsky.feed.post/{i}",
                "record": {
                    "text": f"Test tweet {i}",
                    "createdAt": (datetime.now(timezone.utc) - timedelta(hours=i)).isoformat().replace("+00:00", "Z")
                },
                "author": {
                    "handle": "test.bsky.social",
                    "displayName": "Test User"
                },
                "likeCount": 0,
                "repostCount": 0,
                "replyCount": 0,
                "quoteCount": 0
            }
        })
    
    with patch('src.agent.bluesky_agent.BlueskyAPIClient') as mock_client_class:
        mock_client = Mock()
        mock_client.get_author_feed.return_value = {"feed": mock_posts}
        mock_client_class.return_value = mock_client
        
        result = summarize_bluesky_posts.invoke({
            "query": "last 5 tweets",
            "max_items": 5
        })
        
        items = result.get("items", [])
        # All items should have consistent structure
        for item in items:
            assert "text" in item, "Each tweet should have text"
            assert "author_handle" in item, "Each tweet should have author"
            assert "created_at" in item, "Each tweet should have timestamp"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

