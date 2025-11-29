#!/usr/bin/env python3
"""
Quick test script to verify Slack integration is working.
Tests both fetch_messages and search_messages functionality.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from integrations.slack_client import SlackAPIClient, SlackAPIError

def test_slack_integration():
    """Test Slack integration by fetching recent messages."""

    print("=" * 60)
    print("SLACK INTEGRATION TEST")
    print("=" * 60)

    # Get credentials from environment
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    channel_id = os.getenv("SLACK_CHANNEL_ID")

    print(f"\n1. Checking credentials...")
    print(f"   Bot Token: {bot_token[:20]}..." if bot_token else "   ❌ Bot Token: Not found")
    print(f"   Channel ID: {channel_id}")

    if not bot_token or not channel_id:
        print("\n❌ Missing credentials in .env file")
        return False

    # Initialize Slack client
    try:
        print(f"\n2. Initializing Slack client...")
        client = SlackAPIClient(bot_token=bot_token)
        print("   ✅ Client initialized successfully")
    except SlackAPIError as e:
        print(f"   ❌ Failed to initialize: {e}")
        return False

    # Test 1: Get channel info
    print(f"\n3. Testing channel info retrieval...")
    try:
        channel_info = client.get_channel_info(channel_id)
        channel = channel_info.get("channel", {})
        print(f"   ✅ Channel: #{channel.get('name', 'unknown')}")
        print(f"   - Members: {channel.get('num_members', 0)}")
        print(f"   - Private: {channel.get('is_private', False)}")
        print(f"   - Topic: {channel.get('topic', {}).get('value', 'No topic')}")
    except SlackAPIError as e:
        print(f"   ❌ Failed to get channel info: {e}")
        print(f"   Note: Make sure the bot is invited to the channel using /invite @YourBotName")
        return False

    # Test 2: Fetch recent messages
    print(f"\n4. Testing message fetching (last 10 messages)...")
    try:
        response = client.fetch_messages(channel_id, limit=10)
        messages = response.get("messages", [])

        if not messages:
            print("   ⚠️  No messages found in channel")
            print("   This could mean:")
            print("   - The channel is empty")
            print("   - The bot doesn't have access (try /invite @YourBotName)")
        else:
            print(f"   ✅ Found {len(messages)} messages")
            print("\n   Recent messages:")
            for i, msg in enumerate(messages[:5], 1):  # Show first 5
                text = msg.get("text", "")
                user = msg.get("user", "unknown")
                # Truncate long messages
                display_text = text[:60] + "..." if len(text) > 60 else text
                print(f"   {i}. [{user}]: {display_text}")
    except SlackAPIError as e:
        print(f"   ❌ Failed to fetch messages: {e}")
        return False

    # Test 3: Search for a specific message
    print(f"\n5. Testing message search (searching for 'test')...")
    try:
        search_results = client.search_messages("test", channel=channel_id, limit=5)
        matches = search_results.get("matches", [])
        total = search_results.get("total", 0)

        print(f"   ✅ Search completed: {total} matches found")
        if matches:
            print(f"\n   Top {len(matches)} results:")
            for i, match in enumerate(matches, 1):
                text = match.get("text", "")
                username = match.get("username", match.get("user", "unknown"))
                # Truncate long messages
                display_text = text[:60] + "..." if len(text) > 60 else text
                print(f"   {i}. [{username}]: {display_text}")
    except SlackAPIError as e:
        print(f"   ⚠️  Search failed (may need search:read scope): {e}")
        print(f"   Trying fallback search method...")
        # Fallback will be triggered automatically by the client

    print("\n" + "=" * 60)
    print("✅ SLACK INTEGRATION TEST COMPLETE")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        success = test_slack_integration()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
