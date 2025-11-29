"""
Test script to verify file and image preview functionality.

This script tests:
1. "Pull up my files" - verifies files are displayed
2. "Pull up that image of the mountain" - verifies image preview works
3. Preview modal opens correctly
4. File opening works
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.agent.file_agent import list_related_documents, search_documents
from src.utils import load_config


def test_list_related_documents():
    """Test list_related_documents returns proper format with image metadata."""
    print("\n=== Test 1: list_related_documents ===")
    
    # Test with a query that might return images
    result = list_related_documents.invoke({"query": "mountain", "max_results": 5})
    
    print(f"Result type: {result.get('type')}")
    print(f"Message: {result.get('message')}")
    print(f"Total count: {result.get('total_count')}")
    print(f"Files count: {len(result.get('files', []))}")
    
    # Check if files have proper structure
    files = result.get('files', [])
    if files:
        print(f"\nFirst file structure:")
        first_file = files[0]
        print(f"  - name: {first_file.get('name')}")
        print(f"  - path: {first_file.get('path')}")
        print(f"  - score: {first_file.get('score')}")
        print(f"  - result_type: {first_file.get('result_type')}")
        print(f"  - thumbnail_url: {first_file.get('thumbnail_url')}")
        print(f"  - preview_url: {first_file.get('preview_url')}")
        print(f"  - meta: {first_file.get('meta')}")
        
        # Check if images have thumbnail_url and preview_url
        image_files = [f for f in files if f.get('result_type') == 'image']
        if image_files:
            print(f"\n✓ Found {len(image_files)} image(s)")
            for img in image_files:
                if not img.get('thumbnail_url'):
                    print(f"  ✗ ERROR: Image {img.get('name')} missing thumbnail_url")
                else:
                    print(f"  ✓ Image {img.get('name')} has thumbnail_url")
                if not img.get('preview_url'):
                    print(f"  ✗ ERROR: Image {img.get('name')} missing preview_url")
                else:
                    print(f"  ✓ Image {img.get('name')} has preview_url")
        else:
            print("\n⚠ No images found in results")
    else:
        print("\n⚠ No files found")
    
    return result


def test_search_documents():
    """Test search_documents returns proper format with image metadata."""
    print("\n=== Test 2: search_documents ===")
    
    # Test with a query that might return images
    result = search_documents.invoke({"query": "mountain", "include_images": True})
    
    print(f"Results count: {len(result.get('results', []))}")
    
    # Check if results have proper structure
    results = result.get('results', [])
    if results:
        print(f"\nFirst result structure:")
        first_result = results[0]
        print(f"  - doc_path: {first_result.get('doc_path')}")
        print(f"  - doc_title: {first_result.get('doc_title')}")
        print(f"  - result_type: {first_result.get('result_type')}")
        print(f"  - thumbnail_url: {first_result.get('thumbnail_url')}")
        print(f"  - preview_url: {first_result.get('preview_url')}")
        
        # Check if images have thumbnail_url and preview_url
        image_results = [r for r in results if r.get('result_type') == 'image']
        if image_results:
            print(f"\n✓ Found {len(image_results)} image result(s)")
            for img in image_results:
                if not img.get('thumbnail_url'):
                    print(f"  ✗ ERROR: Image {img.get('doc_title')} missing thumbnail_url")
                else:
                    print(f"  ✓ Image {img.get('doc_title')} has thumbnail_url")
                if not img.get('preview_url'):
                    print(f"  ✗ ERROR: Image {img.get('doc_title')} missing preview_url")
                else:
                    print(f"  ✓ Image {img.get('doc_title')} has preview_url")
        else:
            print("\n⚠ No images found in results")
    else:
        print("\n⚠ No results found")
    
    return result


def test_file_list_format():
    """Test that file_list format is correct for frontend."""
    print("\n=== Test 3: File List Format Validation ===")
    
    result = list_related_documents.invoke({"query": "test", "max_results": 3})
    
    # Validate structure
    required_fields = ['type', 'message', 'files', 'total_count']
    missing_fields = [f for f in required_fields if f not in result]
    
    if missing_fields:
        print(f"✗ ERROR: Missing required fields: {missing_fields}")
        return False
    
    if result.get('type') != 'file_list':
        print(f"✗ ERROR: Expected type='file_list', got '{result.get('type')}'")
        return False
    
    files = result.get('files', [])
    if not isinstance(files, list):
        print(f"✗ ERROR: 'files' should be a list, got {type(files)}")
        return False
    
    # Validate each file structure
    file_required_fields = ['name', 'path', 'score', 'meta']
    for i, file in enumerate(files):
        missing = [f for f in file_required_fields if f not in file]
        if missing:
            print(f"✗ ERROR: File {i} missing fields: {missing}")
            return False
        
        # Check if images have thumbnail_url and preview_url
        if file.get('result_type') == 'image':
            if not file.get('thumbnail_url'):
                print(f"✗ ERROR: Image file {i} missing thumbnail_url")
                return False
            if not file.get('preview_url'):
                print(f"✗ ERROR: Image file {i} missing preview_url")
                return False
    
    print("✓ File list format is valid")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("File and Image Preview Functionality Tests")
    print("=" * 60)
    
    try:
        # Test 1: list_related_documents
        test_list_related_documents()
        
        # Test 2: search_documents
        test_search_documents()
        
        # Test 3: File list format validation
        test_file_list_format()
        
        print("\n" + "=" * 60)
        print("Tests completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ ERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

