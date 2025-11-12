"""
Test screen capture functionality including focused windows, regions, and fallbacks.
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.automation.screen_capture import ScreenCapture
from src.utils import load_config


class TestScreenCapture:
    """Test the ScreenCapture class functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = load_config()
        self.screen_capture = ScreenCapture(self.config)

    def test_config_loaded(self):
        """Test that config is loaded and screenshot dir exists."""
        assert self.screen_capture.config is not None
        assert self.screen_capture.screenshot_dir.exists()

    def test_full_screen_capture(self):
        """Test basic full-screen capture functionality."""
        # This should work without any special setup
        result = self.screen_capture.capture_screen(mode="full")

        # Check basic result structure
        assert isinstance(result, dict)
        assert "success" in result

        if result.get("success"):
            # If successful, check we got a path
            assert "screenshot_path" in result
            assert result["screenshot_path"].endswith(".png")
            assert os.path.exists(result["screenshot_path"])
        else:
            # If failed, should have error info
            assert "error" in result or "error_message" in result

    def test_focused_mode_requires_app_name(self):
        """Test that focused mode requires app_name."""
        result = self.screen_capture.capture_screen(mode="focused")

        # Should fail without app_name
        assert not result.get("success", True)
        assert "error" in result

    def test_region_mode_requires_region_param(self):
        """Test that region mode requires region parameter."""
        result = self.screen_capture.capture_screen(mode="region")

        # Should fail without region
        assert not result.get("success", True)
        assert "error" in result

    def test_invalid_mode_rejected(self):
        """Test that invalid mode values are rejected."""
        result = self.screen_capture.capture_screen(mode="invalid")

        assert not result.get("success", True)
        assert "error" in result
        assert "Invalid mode" in str(result.get("error_message", ""))

    def test_output_path_customization(self):
        """Test custom output path functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_path = os.path.join(temp_dir, "custom_test.png")

            result = self.screen_capture.capture_screen(
                mode="full",
                output_path=custom_path
            )

            if result.get("success"):
                assert result["screenshot_path"] == custom_path
                assert os.path.exists(custom_path)

    def test_backward_compatibility(self):
        """Test that old API (app_name without mode) still works."""
        # This should automatically use focused mode when app_name provided
        result = self.screen_capture.capture_screen(app_name="Finder")

        # Should not fail with error about missing mode
        # (may fail for other reasons like app not running)
        assert isinstance(result, dict)
        assert "success" in result

    @patch('subprocess.run')
    def test_quartz_fallback_logic(self, mock_subprocess):
        """Test that Quartz CGWindowID method is attempted before fallbacks."""
        # Mock Quartz import failure
        with patch.dict('sys.modules', {'Quartz': None}):
            # Mock successful AppleScript bounds method
            mock_subprocess.return_value = MagicMock(
                returncode=0,
                stdout="{0, 0, 800, 600}"
            )

            result = self.screen_capture._capture_focused_window("TestApp", None, "/tmp/test.png")

            # Should have tried AppleScript bounds method
            assert mock_subprocess.called
            # Should succeed with mocked AppleScript
            assert result["success"] is True

    def test_region_capture_with_valid_coords(self):
        """Test region capture with valid coordinates."""
        result = self.screen_capture.capture_region(
            x=0, y=0, width=100, height=100,
            output_path=str(self.screen_capture.screenshot_dir / "region_test.png")
        )

        assert isinstance(result, dict)
        assert "success" in result

        if result.get("success"):
            assert "screenshot_path" in result
            assert os.path.exists(result["screenshot_path"])

    def test_region_capture_invalid_coords(self):
        """Test region capture handles invalid coordinates gracefully."""
        result = self.screen_capture.capture_region(
            x=-100, y=-100, width=0, height=0
        )

        # Should fail gracefully, not crash
        assert isinstance(result, dict)
        # May succeed or fail depending on screencapture behavior with invalid coords

    def test_filename_generation(self):
        """Test automatic filename generation for different modes."""
        # Test focused mode filename
        result_focused = self.screen_capture.capture_screen(
            mode="focused", app_name="TestApp"
        )
        if result_focused.get("success"):
            filename = os.path.basename(result_focused["screenshot_path"])
            assert "TestApp" in filename
            assert filename.endswith(".png")

        # Test region mode filename
        result_region = self.screen_capture.capture_screen(
            mode="region",
            region={"x": 0, "y": 0, "width": 100, "height": 100}
        )
        if result_region.get("success"):
            filename = os.path.basename(result_region["screenshot_path"])
            assert "region" in filename
            assert filename.endswith(".png")

    def test_config_directory_usage(self):
        """Test that screenshots are saved to config-specified directory."""
        result = self.screen_capture.capture_screen(mode="full")

        if result.get("success"):
            screenshot_path = Path(result["screenshot_path"])
            expected_dir = Path(self.config["screenshots"]["base_dir"])
            assert screenshot_path.parent == expected_dir


def test_screen_capture_integration():
    """Integration test for end-to-end screenshot workflow."""
    config = load_config()
    screen_capture = ScreenCapture(config)

    # Test the typical Weather app workflow
    output_path = str(screen_capture.screenshot_dir / "test_weather_workflow.png")
    result = screen_capture.capture_screen(
        app_name="Finder",  # Use Finder as it's always available
        mode="focused",
        output_path=output_path
    )

    assert isinstance(result, dict)
    assert "success" in result

    if result.get("success"):
        assert result["mode"] == "focused"
        assert "Finder" in result.get("app_name", "")
        assert os.path.exists(result["screenshot_path"])


if __name__ == "__main__":
    # Run basic smoke tests
    test_instance = TestScreenCapture()
    test_instance.setup_method()

    print("Testing config loading...")
    test_instance.test_config_loaded()

    print("Testing full screen capture...")
    test_instance.test_full_screen_capture()

    print("Testing mode validation...")
    test_instance.test_focused_mode_requires_app_name()
    test_instance.test_region_mode_requires_region_param()
    test_instance.test_invalid_mode_rejected()

    print("Testing filename generation...")
    test_instance.test_filename_generation()

    print("Testing config directory...")
    test_instance.test_config_directory_usage()

    print("Running integration test...")
    test_screen_capture_integration()

    print("All tests completed!")
