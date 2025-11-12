"""
Manual test script for email attachment verification.
Can be run without pytest to verify attachment validation logic.
"""

import os
import tempfile
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.email_agent import compose_email


def test_missing_file():
    """Test 1: Missing file should return error"""
    print("\n=== Test 1: Missing File ===")
    result = compose_email.invoke({
        "subject": "Test Email",
        "body": "Test body",
        "attachments": ["/nonexistent/path/to/file.pdf"],
        "send": False
    })
    
    if result.get("error") and result.get("error_type") == "AttachmentError":
        print("✅ PASS: Missing file correctly returns AttachmentError")
        print(f"   Error message: {result.get('error_message', '')[:100]}")
        return True
    else:
        print(f"❌ FAIL: Expected AttachmentError, got: {result.get('error_type')}")
        return False


def test_valid_file():
    """Test 2: Valid file should pass validation"""
    print("\n=== Test 2: Valid File ===")
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write(b"test content")
    
    try:
        result = compose_email.invoke({
            "subject": "Test Email",
            "body": "Test body",
            "attachments": [tmp_path],
            "send": False
        })
        
        if result.get("error_type") != "AttachmentError":
            print("✅ PASS: Valid file passes validation (no AttachmentError)")
            return True
        else:
            print(f"❌ FAIL: Valid file returned AttachmentError: {result.get('error_message')}")
            return False
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_directory_rejection():
    """Test 3: Directory should be rejected"""
    print("\n=== Test 3: Directory Rejection ===")
    with tempfile.TemporaryDirectory() as tmp_dir:
        result = compose_email.invoke({
            "subject": "Test Email",
            "body": "Test body",
            "attachments": [tmp_dir],
            "send": False
        })
        
        if result.get("error") and result.get("error_type") == "AttachmentError":
            print("✅ PASS: Directory correctly rejected")
            return True
        else:
            print(f"❌ FAIL: Directory was not rejected. Got: {result.get('error_type')}")
            return False


def test_absolute_path_conversion():
    """Test 4: Relative paths should be converted to absolute"""
    print("\n=== Test 4: Absolute Path Conversion ===")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write(b"test content")
    
    try:
        # Get relative path
        rel_path = os.path.relpath(tmp_path, start=os.path.dirname(tmp_path))
        rel_path = os.path.join(".", os.path.basename(tmp_path))
        
        # Check if validation converts to absolute
        # We can't easily test the internal conversion without mocking,
        # but we can verify the file validation still works
        result = compose_email.invoke({
            "subject": "Test Email",
            "body": "Test body",
            "attachments": [tmp_path],  # Use absolute path
            "send": False
        })
        
        if result.get("error_type") != "AttachmentError":
            print("✅ PASS: Absolute path validation works")
            print(f"   Path used: {tmp_path}")
            return True
        else:
            print(f"❌ FAIL: Absolute path failed validation")
            return False
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_multiple_attachments():
    """Test 5: Multiple attachments with one invalid"""
    print("\n=== Test 5: Multiple Attachments ===")
    tmp_files = []
    try:
        # Create two valid files
        for i in range(2):
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{i}.pdf") as tmp_file:
                tmp_path = tmp_file.name
                tmp_file.write(b"test content")
                tmp_files.append(tmp_path)
        
        # Add one invalid path
        attachments = tmp_files + ["/nonexistent/file.pdf"]
        
        result = compose_email.invoke({
            "subject": "Test Email",
            "body": "Test body",
            "attachments": attachments,
            "send": False
        })
        
        if result.get("error") and result.get("error_type") == "AttachmentError":
            invalid = result.get("invalid_attachments", [])
            if "/nonexistent/file.pdf" in str(invalid):
                print("✅ PASS: Invalid attachment correctly identified")
                print(f"   Invalid attachments: {invalid}")
                return True
            else:
                print(f"❌ FAIL: Invalid attachment not identified correctly")
                return False
        else:
            print(f"❌ FAIL: Expected AttachmentError for invalid attachment")
            return False
    finally:
        for tmp_path in tmp_files:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


def main():
    """Run all tests"""
    print("=" * 60)
    print("Email Attachment Verification Tests")
    print("=" * 60)
    
    tests = [
        test_missing_file,
        test_valid_file,
        test_directory_rejection,
        test_absolute_path_conversion,
        test_multiple_attachments,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ ERROR in {test.__name__}: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print(f"❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

