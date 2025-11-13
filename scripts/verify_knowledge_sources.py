"""
Quick verification test for the Knowledge Sources functionality.

Tests Wikipedia API endpoint and cache creation.
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.utils import load_config
from src.knowledge_providers.wiki import lookup_wikipedia


def test_wikipedia_endpoint():
    """Test Wikipedia API endpoint connectivity and response."""
    print("\n" + "="*80)
    print("VERIFICATION TEST - Wikipedia Endpoint")
    print("="*80)

    config = load_config()

    # Test with a well-known Wikipedia page
    print("\nTesting Wikipedia lookup for 'Python (programming language)'...")

    try:
        result = lookup_wikipedia("Python (programming language)", config)

        if result.error:
            print(f"❌ FAILED: {result.error_message}")
            return False

        print("✅ SUCCESS: Wikipedia API responded")
        print(f"  Title: {result.title}")
        print(f"  Summary: {result.summary[:100]}...")
        print(f"  URL: {result.url}")
        print(f"  Confidence: {result.confidence}")

        # Verify expected fields
        if not result.title or not result.summary or not result.url:
            print("❌ FAILED: Missing expected fields in response")
            return False

        if result.confidence != 1.0:
            print(f"❌ FAILED: Expected confidence 1.0, got {result.confidence}")
            return False

        return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cache_creation():
    """Test that cache files are created correctly."""
    print("\n" + "="*80)
    print("VERIFICATION TEST - Cache Creation")
    print("="*80)

    config = load_config()
    cache_dir = config.get("knowledge_providers", {}).get("wiki_lookup", {}).get("cache_dir", "data/cache/knowledge")

    print(f"\nCache directory: {cache_dir}")

    # Check if cache directory exists or can be created
    try:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        print("✅ Cache directory exists/created")
    except Exception as e:
        print(f"❌ FAILED to create cache directory: {e}")
        return False

    # Test a lookup that should create a cache file
    print("\nTesting cache file creation...")

    try:
        result = lookup_wikipedia("Machine learning", config)

        if result.error:
            print(f"❌ FAILED lookup: {result.error_message}")
            return False

        # Check if cache file was created
        from src.knowledge_providers.wiki import _get_cache_path
        cache_path = _get_cache_path(cache_dir, "Machine learning")

        if os.path.exists(cache_path):
            print("✅ Cache file created")
            print(f"  Path: {cache_path}")

            # Verify cache content
            import json
            with open(cache_path, 'r') as f:
                cached_data = json.load(f)

            if cached_data.get("title") and cached_data.get("summary"):
                print("✅ Cache file contains valid data")
                return True
            else:
                print("❌ Cache file missing expected data")
                return False
        else:
            print("❌ Cache file was not created")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_validation():
    """Test that configuration is properly loaded."""
    print("\n" + "="*80)
    print("VERIFICATION TEST - Configuration")
    print("="*80)

    config = load_config()

    knowledge_config = config.get("knowledge_providers", {})
    if not knowledge_config:
        print("❌ FAILED: knowledge_providers not found in config")
        return False

    wiki_config = knowledge_config.get("wiki_lookup", {})
    if not wiki_config:
        print("❌ FAILED: wiki_lookup not found in knowledge_providers")
        return False

    print("✅ Knowledge providers config found")

    # Check required fields
    required_fields = ["enabled", "cache_dir", "cache_ttl_hours", "timeout_seconds", "max_retries"]
    for field in required_fields:
        if field not in wiki_config:
            print(f"❌ FAILED: Missing required config field: {field}")
            return False

    print("✅ All required config fields present")
    print(f"  enabled: {wiki_config['enabled']}")
    print(f"  cache_dir: {wiki_config['cache_dir']}")
    print(f"  cache_ttl_hours: {wiki_config['cache_ttl_hours']}")
    print(f"  timeout_seconds: {wiki_config['timeout_seconds']}")
    print(f"  max_retries: {wiki_config['max_retries']}")

    return True


if __name__ == "__main__":
    print("KNOWLEDGE SOURCES VERIFICATION")
    print("="*80)

    tests = [
        ("Configuration Validation", test_config_validation),
        ("Wikipedia Endpoint Test", test_wikipedia_endpoint),
        ("Cache Creation Test", test_cache_creation),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")

    print("\n" + "="*80)
    print(f"VERIFICATION RESULTS: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 ALL TESTS PASSED - Knowledge sources are working correctly!")
        print("\nUsage documentation:")
        print("- Use 'wiki_lookup' tool in the agent for factual information")
        print("- Cache files are stored in data/cache/knowledge/")
        print("- Configuration can be toggled in config.yaml")
    else:
        print("❌ Some tests failed - check the output above")

    print("="*80 + "\n")
