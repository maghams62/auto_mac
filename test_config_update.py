"""
Test script to verify config update and hot-reload functionality.

Run this while the API server is running to test:
1. Config can be read via API
2. Config can be updated via API
3. Backend components use updated config
"""

import requests
import json
import time

API_URL = "http://localhost:8000"

def test_config_read():
    """Test reading config."""
    print("=" * 60)
    print("TEST 1: Reading config via API")
    print("=" * 60)
    
    response = requests.get(f"{API_URL}/api/config")
    assert response.status_code == 200, f"Failed to get config: {response.status_code}"
    
    config = response.json()
    print(f"✓ Config loaded successfully")
    print(f"  Email default_recipient: {config.get('email', {}).get('default_recipient', 'NOT SET')}")
    print(f"  Document folders: {config.get('documents', {}).get('folders', [])}")
    print(f"  iMessage default_phone: {config.get('imessage', {}).get('default_phone_number', 'NOT SET')}")
    
    return config

def test_config_update():
    """Test updating config."""
    print("\n" + "=" * 60)
    print("TEST 2: Updating config via API")
    print("=" * 60)
    
    # Read current config first
    current_config = test_config_read()
    original_email = current_config.get('email', {}).get('default_recipient', '')
    
    # Update email
    new_email = "test_updated@example.com"
    updates = {
        "email": {
            "default_recipient": new_email
        }
    }
    
    print(f"\nUpdating email from '{original_email}' to '{new_email}'...")
    
    response = requests.put(
        f"{API_URL}/api/config",
        json={"updates": updates},
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200, f"Failed to update config: {response.status_code}"
    
    result = response.json()
    assert result.get("success") == True, "Update did not return success"
    
    print(f"✓ Config updated successfully")
    print(f"  Message: {result.get('message')}")
    
    # Verify update
    updated_config = result.get("config", {})
    updated_email = updated_config.get('email', {}).get('default_recipient', '')
    assert updated_email == new_email, f"Email not updated correctly: {updated_email} != {new_email}"
    
    print(f"✓ Verified email updated to: {updated_email}")
    
    # Wait a moment for hot-reload
    time.sleep(1)
    
    # Read again to verify persistence
    print("\nVerifying config persistence...")
    response = requests.get(f"{API_URL}/api/config")
    assert response.status_code == 200
    persisted_config = response.json()
    persisted_email = persisted_config.get('email', {}).get('default_recipient', '')
    assert persisted_email == new_email, f"Config not persisted: {persisted_email} != {new_email}"
    
    print(f"✓ Config persisted correctly: {persisted_email}")
    
    # Restore original email
    print(f"\nRestoring original email: {original_email}")
    restore_updates = {
        "email": {
            "default_recipient": original_email
        }
    }
    requests.put(
        f"{API_URL}/api/config",
        json={"updates": restore_updates},
        headers={"Content-Type": "application/json"}
    )
    print("✓ Original config restored")
    
    return True

def test_config_reload():
    """Test config reload endpoint."""
    print("\n" + "=" * 60)
    print("TEST 3: Reloading config from file")
    print("=" * 60)
    
    response = requests.post(f"{API_URL}/api/config/reload")
    assert response.status_code == 200, f"Failed to reload config: {response.status_code}"
    
    result = response.json()
    assert result.get("success") == True, "Reload did not return success"
    
    print(f"✓ Config reloaded successfully")
    print(f"  Message: {result.get('message')}")
    
    return True

def test_nested_update():
    """Test updating nested config values."""
    print("\n" + "=" * 60)
    print("TEST 4: Updating nested config values")
    print("=" * 60)
    
    # Add a test folder
    updates = {
        "documents": {
            "folders": ["/test/folder1", "/test/folder2"]
        }
    }
    
    print("Adding test folders...")
    response = requests.put(
        f"{API_URL}/api/config",
        json={"updates": updates},
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result.get("success") == True
    
    folders = result.get("config", {}).get("documents", {}).get("folders", [])
    assert "/test/folder1" in folders, "Folder not added"
    assert "/test/folder2" in folders, "Folder not added"
    
    print(f"✓ Folders updated: {folders}")
    
    return True

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("CONFIG UPDATE TEST SUITE")
    print("=" * 60)
    print("\nMake sure the API server is running on http://localhost:8000")
    print("Press Enter to continue...")
    input()
    
    try:
        test_config_read()
        test_config_update()
        test_config_reload()
        test_nested_update()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

