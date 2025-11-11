#!/usr/bin/env python3
"""
Comprehensive test script for BlueSky integration.
Tests all functionality including:
- Getting author feed (last N tweets)
- Summarizing tweets
- Sending tweets
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
project_root = Path(__file__).resolve().parent
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=False)

# Add project root to path
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.agent.bluesky_agent import (
    search_bluesky_posts,
    get_bluesky_author_feed,
    summarize_bluesky_posts,
    post_bluesky_update,
)
from src.integrations.bluesky_client import BlueskyAPIClient, BlueskyAPIError


def test_credentials():
    """Test that credentials are loaded."""
    print("=" * 60)
    print("TEST 1: Checking BlueSky credentials...")
    print("=" * 60)
    
    username = os.getenv("BLUESKY_USERNAME") or os.getenv("BLUESKY_IDENTIFIER")
    password = os.getenv("BLUESKY_PASSWORD")
    
    if not username:
        print("❌ ERROR: BLUESKY_USERNAME or BLUESKY_IDENTIFIER not set in .env file")
        return False
    
    if not password:
        print("❌ ERROR: BLUESKY_PASSWORD not set in .env file")
        return False
    
    print(f"✅ Username found: {username}")
    print(f"✅ Password found: {'*' * len(password)}")
    return True


def test_client_initialization():
    """Test that BlueskyAPIClient can be initialized."""
    print("\n" + "=" * 60)
    print("TEST 2: Testing BlueskyAPIClient initialization...")
    print("=" * 60)
    
    try:
        client = BlueskyAPIClient()
        print("✅ BlueskyAPIClient initialized successfully")
        print(f"✅ Authenticated as: {client.identifier}")
        print(f"✅ DID: {client.did}")
        return True, client
    except BlueskyAPIError as e:
        print(f"❌ ERROR: {e}")
        return False, None
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_get_author_feed(client):
    """Test getting author feed."""
    print("\n" + "=" * 60)
    print("TEST 3: Testing get_bluesky_author_feed tool...")
    print("=" * 60)
    
    try:
        result = get_bluesky_author_feed.invoke({"actor": None, "max_posts": 5})
        
        if result.get("error"):
            print(f"❌ ERROR: {result.get('error_message')}")
            return False
        
        print(f"✅ Successfully retrieved {result.get('count', 0)} posts")
        print(f"✅ Actor: {result.get('actor', 'unknown')}")
        
        posts = result.get("posts", [])
        if posts:
            print(f"\n📝 Sample post:")
            print(f"   Author: @{posts[0].get('author_handle', 'unknown')}")
            print(f"   Text: {posts[0].get('text', '')[:100]}...")
            print(f"   Created: {posts[0].get('created_at', 'unknown')}")
        
        return True
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_summarize_last_tweets():
    """Test summarizing last N tweets."""
    print("\n" + "=" * 60)
    print("TEST 4: Testing summarize_bluesky_posts with 'last 3 tweets' query...")
    print("=" * 60)
    
    try:
        result = summarize_bluesky_posts.invoke({
            "query": "last 3 tweets on BlueSky",
            "max_items": 3
        })
        
        if result.get("error"):
            print(f"❌ ERROR: {result.get('error_message')}")
            return False
        
        print("✅ Summary generated successfully")
        print(f"\n📊 Summary:")
        print(result.get("summary", "No summary available"))
        print(f"\n📝 Items: {len(result.get('items', []))}")
        
        return True
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_search_posts():
    """Test searching posts."""
    print("\n" + "=" * 60)
    print("TEST 5: Testing search_bluesky_posts...")
    print("=" * 60)
    
    try:
        result = search_bluesky_posts.invoke({
            "query": "AI agents",
            "max_posts": 3
        })
        
        if result.get("error"):
            print(f"❌ ERROR: {result.get('error_message')}")
            return False
        
        print(f"✅ Found {result.get('count', 0)} posts")
        posts = result.get("posts", [])
        if posts:
            print(f"\n📝 Sample post:")
            print(f"   Author: @{posts[0].get('author_handle', 'unknown')}")
            print(f"   Text: {posts[0].get('text', '')[:100]}...")
        
        return True
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_post_tweet():
    """Test posting a tweet."""
    print("\n" + "=" * 60)
    print("TEST 6: Testing post_bluesky_update...")
    print("=" * 60)
    
    import time
    test_message = f"Test tweet from Mac Automation Assistant at {time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    print(f"📝 Test message: {test_message}")
    # For automated testing, proceed without confirmation
    
    try:
        result = post_bluesky_update.invoke({
            "message": test_message
        })
        
        if result.get("error"):
            print(f"❌ ERROR: {result.get('error_message')}")
            return False
        
        print("✅ Tweet posted successfully!")
        print(f"✅ URI: {result.get('uri', 'N/A')}")
        print(f"✅ URL: {result.get('url', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("BLUESKY INTEGRATION TEST SUITE")
    print("=" * 60)
    
    results = []
    
    # Test 1: Credentials
    if not test_credentials():
        print("\n❌ CREDENTIALS NOT CONFIGURED. Please add BLUESKY_USERNAME and BLUESKY_PASSWORD to .env file")
        return 1
    results.append(("Credentials", True))
    
    # Test 2: Client initialization
    success, client = test_client_initialization()
    if not success:
        print("\n❌ CLIENT INITIALIZATION FAILED. Check credentials and network connection.")
        return 1
    results.append(("Client Initialization", True))
    
    # Test 3: Get author feed
    results.append(("Get Author Feed", test_get_author_feed(client)))
    
    # Test 4: Summarize last tweets
    results.append(("Summarize Last Tweets", test_summarize_last_tweets()))
    
    # Test 5: Search posts
    results.append(("Search Posts", test_search_posts()))
    
    # Test 6: Post tweet
    results.append(("Post Tweet", test_post_tweet()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

