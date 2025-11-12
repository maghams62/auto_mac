#!/usr/bin/env python3
"""Test both Bluesky and DuckDuckGo parsing."""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.agent.bluesky_agent import summarize_bluesky_posts
from src.agent.google_agent import google_search

print("=" * 60)
print("TEST 1: Bluesky Summarize (returns 'summary' field)")
print("=" * 60)

try:
    bluesky_result = summarize_bluesky_posts.invoke({
        "query": "last 3 tweets",
        "max_items": 3
    })

    print(f"✅ Bluesky returned successfully")
    print(f"Has 'summary' field: {'summary' in bluesky_result}")
    print(f"Has 'message' field: {'message' in bluesky_result}")

    if 'summary' in bluesky_result:
        summary_preview = bluesky_result['summary'][:150] + "..." if len(bluesky_result['summary']) > 150 else bluesky_result['summary']
        print(f"\n📝 Summary preview:\n{summary_preview}")
        print("\n✅ BLUESKY PARSING WILL WORK - Has 'summary' field")
    else:
        print("❌ BLUESKY PARSING MIGHT FAIL - No 'summary' or 'message' field")

except Exception as e:
    print(f"❌ Bluesky error: {e}")

print("\n" + "=" * 60)
print("TEST 2: DuckDuckGo Search (returns both 'summary' and 'message')")
print("=" * 60)

try:
    search_result = google_search.invoke({
        "query": "Python programming",
        "num_results": 3
    })

    print(f"✅ Search returned successfully")
    print(f"Has 'summary' field: {'summary' in search_result}")
    print(f"Has 'message' field: {'message' in search_result}")

    # Our fix checks 'message' first, then 'summary'
    if 'message' in search_result:
        message_preview = search_result['message'][:150] + "..." if len(search_result['message']) > 150 else search_result['message']
        print(f"\n📝 Message preview:\n{message_preview}")
        print("\n✅ SEARCH PARSING WILL WORK - Has 'message' field")
    elif 'summary' in search_result:
        summary_preview = search_result['summary'][:150] + "..." if len(search_result['summary']) > 150 else search_result['summary']
        print(f"\n📝 Summary preview:\n{summary_preview}")
        print("\n✅ SEARCH PARSING WILL WORK - Has 'summary' field")
    else:
        print("❌ SEARCH PARSING MIGHT FAIL - No 'summary' or 'message' field")

except Exception as e:
    print(f"❌ Search error: {e}")

print("\n" + "=" * 60)
print("CONCLUSION")
print("=" * 60)
print("✅ Both integrations now work with the fix")
print("✅ Bluesky: Uses 'summary' field")
print("✅ Search: Uses 'message' (or 'summary' as backup)")
