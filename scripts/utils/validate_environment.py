#!/usr/bin/env python3
"""
Environment Validation Script

Validates that all dependencies, API keys, and macOS permissions are properly configured
for Cerebro OS to function correctly.

Run this script to check your environment setup before using Cerebro OS.
"""

import sys
import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class EnvironmentValidator:
    """Validates environment setup for Cerebro OS."""

    def __init__(self):
        self.issues: List[Tuple[str, str, str]] = []  # (category, severity, message)
        self.warnings: List[Tuple[str, str]] = []  # (category, message)

    def check_python_dependencies(self) -> bool:
        """Check if all required Python packages are installed."""
        logger.info("Checking Python dependencies...")
        
        required_packages = {
            "faiss-cpu": "faiss",
            "Pillow": "PIL",
            "pypdf": "pypdf",
            "pydub": "pydub",
            "openai": "openai",
            "fastapi": "fastapi",
            "websockets": "websockets",
            "numpy": "numpy",
            "langchain": "langchain",
            "langchain-openai": "langchain_openai",
            "langgraph": "langgraph",
        }

        missing = []
        for package_name, import_name in required_packages.items():
            try:
                __import__(import_name)
                logger.info(f"  ✅ {package_name}")
            except ImportError:
                missing.append(package_name)
                self.issues.append(("dependencies", "error", f"Missing package: {package_name}"))
                logger.error(f"  ❌ {package_name} - NOT INSTALLED")

        # Special check for faiss on ARM Macs
        try:
            import faiss
            logger.info("  ✅ faiss-cpu (or faiss)")
        except ImportError:
            # Check if we're on ARM Mac
            import platform
            if platform.machine() == "arm64":
                self.warnings.append(("dependencies", "On ARM Macs, you may need to install faiss-cpu specifically"))
                logger.warning("  ⚠️  faiss-cpu - May need special installation on ARM Mac")

        return len(missing) == 0

    def check_openai_api_key(self) -> bool:
        """Check if OpenAI API key is configured."""
        logger.info("Checking OpenAI API key...")
        
        # Check environment variable
        api_key = os.getenv("OPENAI_API_KEY")
        
        # Also check .env file
        env_file = Path(".env")
        if env_file.exists():
            try:
                with open(env_file, "r") as f:
                    for line in f:
                        if line.startswith("OPENAI_API_KEY="):
                            api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception as e:
                logger.warning(f"  ⚠️  Could not read .env file: {e}")

        if not api_key or api_key == "" or not api_key.startswith("sk-"):
            self.issues.append(("api_key", "error", "OPENAI_API_KEY not set or invalid"))
            logger.error("  ❌ OPENAI_API_KEY not set or invalid")
            logger.error("     Set it with: export OPENAI_API_KEY='sk-your-key-here'")
            logger.error("     Or add it to .env file: OPENAI_API_KEY=sk-your-key-here")
            return False
        else:
            # Validate key format (basic check)
            if len(api_key) < 20:
                self.issues.append(("api_key", "error", "OPENAI_API_KEY appears to be invalid (too short)"))
                logger.error("  ❌ OPENAI_API_KEY appears to be invalid")
                return False
            else:
                logger.info("  ✅ OPENAI_API_KEY is set")
                return True

    def check_macos_permissions(self) -> bool:
        """Check macOS automation permissions."""
        logger.info("Checking macOS automation permissions...")
        
        apps_to_test = {
            "Mail.app": 'tell application "Mail" to get name of every mail account',
            "Reminders.app": 'tell application "Reminders" to get name of every list',
            "Calendar.app": 'tell application "Calendar" to get name of every calendar',
            "Finder": 'tell application "Finder" to get name of home'
        }

        all_passed = True
        for app_name, script in apps_to_test.items():
            try:
                result = subprocess.run(
                    ['osascript', '-e', script],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    logger.info(f"  ✅ {app_name} - Permission granted")
                else:
                    error_msg = result.stderr.strip()
                    self.issues.append(("permissions", "error", f"{app_name}: {error_msg}"))
                    logger.error(f"  ❌ {app_name} - Permission denied or not configured")
                    logger.error(f"     Error: {error_msg}")
                    all_passed = False
            except subprocess.TimeoutExpired:
                self.issues.append(("permissions", "error", f"{app_name}: Script timeout"))
                logger.error(f"  ❌ {app_name} - Script timeout")
                all_passed = False
            except Exception as e:
                self.issues.append(("permissions", "error", f"{app_name}: {str(e)}"))
                logger.error(f"  ❌ {app_name} - Error: {str(e)}")
                all_passed = False

        return all_passed

    def check_config_file(self) -> bool:
        """Check if config.yaml exists and is valid."""
        logger.info("Checking configuration file...")
        
        config_file = Path("config.yaml")
        if not config_file.exists():
            self.issues.append(("config", "error", "config.yaml not found"))
            logger.error("  ❌ config.yaml not found")
            logger.error("     Create config.yaml with your document folders and settings")
            return False

        try:
            import yaml
            with open(config_file, "r") as f:
                config = yaml.safe_load(f)
            
            # Check for required sections
            if "documents" not in config:
                self.warnings.append(("config", "config.yaml missing 'documents' section"))
                logger.warning("  ⚠️  config.yaml missing 'documents' section")
            
            if "openai" not in config:
                self.warnings.append(("config", "config.yaml missing 'openai' section"))
                logger.warning("  ⚠️  config.yaml missing 'openai' section")
            
            logger.info("  ✅ config.yaml exists and is readable")
            return True
        except Exception as e:
            self.issues.append(("config", "error", f"config.yaml invalid: {str(e)}"))
            logger.error(f"  ❌ config.yaml invalid: {str(e)}")
            return False

    def check_data_directories(self) -> bool:
        """Check if data directories exist and are writable."""
        logger.info("Checking data directories...")
        
        required_dirs = [
            "data",
            "data/embeddings",
            "data/cache",
            "data/sessions",
            "data/logs"
        ]

        all_exist = True
        for dir_path in required_dirs:
            path = Path(dir_path)
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"  ✅ Created {dir_path}")
                except Exception as e:
                    self.issues.append(("directories", "error", f"Cannot create {dir_path}: {str(e)}"))
                    logger.error(f"  ❌ Cannot create {dir_path}: {str(e)}")
                    all_exist = False
            else:
                # Check if writable
                if os.access(path, os.W_OK):
                    logger.info(f"  ✅ {dir_path} exists and is writable")
                else:
                    self.issues.append(("directories", "error", f"{dir_path} is not writable"))
                    logger.error(f"  ❌ {dir_path} is not writable")
                    all_exist = False

        return all_exist

    def run_all_checks(self) -> Dict[str, Any]:
        """Run all validation checks."""
        logger.info("🔍 Starting environment validation...")
        logger.info("=" * 60)

        results = {
            "python_dependencies": self.check_python_dependencies(),
            "openai_api_key": self.check_openai_api_key(),
            "macos_permissions": self.check_macos_permissions(),
            "config_file": self.check_config_file(),
            "data_directories": self.check_data_directories()
        }

        logger.info("=" * 60)
        return results

    def print_summary(self, results: Dict[str, Any]):
        """Print a summary of validation results."""
        total_checks = len(results)
        passed_checks = sum(1 for v in results.values() if v)
        
        print(f"\n📊 VALIDATION SUMMARY: {passed_checks}/{total_checks} checks passed")
        print("=" * 60)

        if len(self.issues) == 0:
            print("🎉 ALL CHECKS PASSED!")
            print("✅ Your environment is properly configured for Cerebro OS.")
        else:
            print("⚠️  SOME ISSUES FOUND:")
            print()
            
            # Group issues by category
            by_category = {}
            for category, severity, message in self.issues:
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append((severity, message))

            for category, items in by_category.items():
                print(f"📁 {category.upper()}:")
                for severity, message in items:
                    icon = "❌" if severity == "error" else "⚠️"
                    print(f"   {icon} {message}")
                print()

        if self.warnings:
            print("💡 WARNINGS:")
            for category, message in self.warnings:
                print(f"   ⚠️  [{category}] {message}")
            print()

        if len(self.issues) > 0:
            print("🔧 NEXT STEPS:")
            print("1. Fix the issues listed above")
            print("2. Run this script again to verify")
            print("3. See README.md for detailed setup instructions")
            print()

        print("=" * 60)

def main():
    """Main entry point."""
    print("🤖 Cerebro OS - Environment Validator")
    print("This script checks your environment setup for Cerebro OS.")
    print()

    validator = EnvironmentValidator()
    results = validator.run_all_checks()
    validator.print_summary(results)

    # Return exit code based on results
    if len(validator.issues) == 0:
        sys.exit(0)  # Success
    else:
        sys.exit(1)  # Issues found

if __name__ == "__main__":
    main()
