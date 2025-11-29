#!/usr/bin/env python3
"""
Test script for the universal search API endpoint.
"""

import requests
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

def test_universal_search():
    """Test the universal search API endpoint"""

    base_url = "http://localhost:8000"

    print("🧪 Testing Universal Search API")
    print("=" * 40)

    # Test 1: Empty query (should return 400)
    print("\n1. Testing empty query...")
    try:
        response = requests.get(f"{base_url}/api/universal-search?q=")
        if response.status_code == 400:
            print("✅ Empty query correctly rejected")
        else:
            print(f"❌ Expected 400, got {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing empty query: {e}")

    # Test 2: Valid query (may return empty results if no documents indexed)
    print("\n2. Testing valid query...")
    try:
        response = requests.get(f"{base_url}/api/universal-search?q=photograph")
        if response.status_code == 200:
            data = response.json()
            print("✅ API responded successfully")
            print(f"   Query: {data.get('query')}")
            print(f"   Results count: {data.get('count')}")

            if data.get('results'):
                print("   Sample result:")
                result = data['results'][0]
                print(f"     File: {result.get('file_name')}")
                print(f"     Type: {result.get('file_type')}")
                print(f"     Score: {result.get('similarity_score')}")
                print(f"     Snippet: {result.get('snippet')[:100]}...")
        else:
            print(f"❌ API error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error testing valid query: {e}")

    # Test 3: Query with special characters
    print("\n3. Testing query with special characters...")
    try:
        response = requests.get(f"{base_url}/api/universal-search?q=hello%20world%21")
        if response.status_code == 200:
            print("✅ Special characters handled correctly")
        else:
            print(f"❌ Error with special characters: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing special characters: {e}")

    print("\n🏁 Testing complete!")


def test_image_search():
    """Test image search functionality"""
    base_url = "http://localhost:8000"

    print("\n🖼️ Testing Image Search")
    print("=" * 30)

    # Test 1: Search for mountain (should find the test image)
    print("\n1. Testing image search for 'mountain'...")
    try:
        response = requests.get(f"{base_url}/api/universal-search?q=mountain&types=image")
        if response.status_code == 200:
            data = response.json()
            print("✅ API responded successfully")
            print(f"   Query: {data.get('query')}")
            print(f"   Results count: {data.get('count')}")
            print(f"   Types searched: {data.get('types_searched')}")

            if data.get('results'):
                result = data['results'][0]
                print("   Image result:")
                print(f"     Type: {result.get('result_type')}")
                print(f"     File: {result.get('file_name')}")
                print(f"     Score: {result.get('similarity_score')}")
                print(f"     Snippet (caption): {result.get('snippet')}")
                print(f"     Has thumbnail URL: {'thumbnail_url' in result}")
                print(f"     Has metadata: {'metadata' in result}")

                # Test thumbnail endpoint
                if result.get('thumbnail_url'):
                    thumb_response = requests.get(f"{base_url}{result['thumbnail_url']}")
                    if thumb_response.status_code == 200:
                        print("     ✅ Thumbnail endpoint works")
                    else:
                        print(f"     ❌ Thumbnail endpoint failed: {thumb_response.status_code}")
            else:
                print("   No image results found (may need reindexing)")
        else:
            print(f"❌ API error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error testing image search: {e}")

    # Test 2: Search for both documents and images
    print("\n2. Testing mixed search for 'landscape'...")
    try:
        response = requests.get(f"{base_url}/api/universal-search?q=landscape")
        if response.status_code == 200:
            data = response.json()
            print("✅ Mixed search responded successfully")
            print(f"   Results count: {data.get('count')}")

            result_types = [r.get('result_type') for r in data.get('results', [])]
            print(f"   Result types: {result_types}")
        else:
            print(f"❌ Mixed search error: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing mixed search: {e}")

    print("\n🏔️ Image search testing complete!")


class TestUniversalSearch(unittest.TestCase):
    """Unit tests for universal search functionality"""

    def test_generate_highlighted_snippet(self):
        """Test the _generate_highlighted_snippet function"""
        # Import the function from api_server.py
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

        # Mock the required imports
        with patch('api_server.re') as mock_re, \
             patch('api_server.Path') as mock_path:

            # Import after patching
            from api_server import _generate_highlighted_snippet

            # Test case 1: Basic highlighting
            content = "This is a test document with machine learning content."
            query = "machine learning"

            mock_re.findall.return_value = ['machine', 'learning']
            mock_re.finditer.return_value = [
                MagicMock(start=lambda: 32, end=lambda: 39),  # "machine"
                MagicMock(start=lambda: 40, end=lambda: 48),  # "learning"
            ]

            snippet, offsets = _generate_highlighted_snippet(content, query, context_chars=50)

            self.assertIsInstance(snippet, str)
            self.assertIsInstance(offsets, list)
            self.assertTrue(len(snippet) > 0)
            # Should contain the highlighted terms
            self.assertIn("machine", snippet.lower())
            self.assertIn("learning", snippet.lower())

    def test_generate_highlighted_snippet_empty_content(self):
        """Test snippet generation with empty content"""
        from api_server import _generate_highlighted_snippet

        snippet, offsets = _generate_highlighted_snippet("", "test")

        self.assertEqual(snippet, "")
        self.assertEqual(offsets, [])

    def test_generate_highlighted_snippet_no_keywords(self):
        """Test snippet generation when no keywords match"""
        from api_server import _generate_highlighted_snippet

        content = "This is some content without the search terms."
        snippet, offsets = _generate_highlighted_snippet(content, "", context_chars=50)

        self.assertIsInstance(snippet, str)
        self.assertEqual(offsets, [])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "unit":
        # Run unit tests
        unittest.main(argv=[''], exit=False, verbosity=2)
    else:
        # Run integration tests
        test_universal_search()
        test_image_search()
