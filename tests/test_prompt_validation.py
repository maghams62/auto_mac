"""
Test suite to validate prompts don't contain hardcoded values.

These tests prevent issues like the "test_data" bug where hardcoded values in prompt
examples caused the LLM to use incorrect folders/paths/emails.
"""

import re
import pytest
from pathlib import Path
from typing import List, Tuple


class TestPromptValidation:
    """Validate prompts for hardcoded values that could mislead the LLM."""

    PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

    # Patterns to detect hardcoded values (with exceptions)
    SUSPICIOUS_PATTERNS = {
        # Email addresses (allow example.com and company.com as they're generic placeholders)
        "hardcoded_email": (
            r'\b[a-zA-Z0-9._%+-]+@(?!example\.com)(?!company\.com)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
            "Real email addresses found (use example.com or $stepN references)"
        ),

        # Specific folder names that could be copied
        "hardcoded_folder": (
            r'"(?:test_data|test_doc|misc_folder|study_stuff)"(?!\s*[,:]?\s*//)',
            "Hardcoded folder names without clarifying comments"
        ),

        # Absolute paths with usernames
        "hardcoded_path": (
            r'(?:/Users/(?!example|placeholder)[a-zA-Z0-9_-]+|~/(?!example|placeholder)Documents)',
            "Hardcoded paths with specific usernames"
        ),

        # Phone numbers (basic pattern)
        "hardcoded_phone": (
            r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
            "Phone numbers found (use placeholders)"
        ),
    }

    # Files that are allowed to have specific values (config, tests, etc.)
    EXEMPTED_FILES = {
        "README.md",  # Documentation can show examples
        "folder_agent_policy.md",  # We already fixed this one and it has placeholders
    }

    # File-specific exceptions for values that are actually correct
    ALLOWED_EXCEPTIONS = {
        "config.yaml": ["spamstuff062@gmail.com"],  # User's actual config
        "task_decomposition.md": ["finance.yahoo.com", "bloomberg.com"],  # Reference to config
    }

    def get_prompt_files(self) -> List[Path]:
        """Get all markdown files in prompts directory."""
        if not self.PROMPTS_DIR.exists():
            pytest.skip(f"Prompts directory not found: {self.PROMPTS_DIR}")

        return list(self.PROMPTS_DIR.rglob("*.md"))

    def check_pattern(self, file_path: Path, pattern: str, description: str) -> List[Tuple[int, str]]:
        """Check a file for a suspicious pattern."""
        violations = []

        try:
            content = file_path.read_text()
            lines = content.split('\n')

            for line_num, line in enumerate(lines, 1):
                # Skip code blocks and comments that explain what NOT to do
                if line.strip().startswith('```') or line.strip().startswith('#'):
                    continue

                if re.search(pattern, line):
                    # Check if this is in allowed exceptions
                    if file_path.name in self.ALLOWED_EXCEPTIONS:
                        allowed = self.ALLOWED_EXCEPTIONS[file_path.name]
                        if any(exc in line for exc in allowed):
                            continue

                    violations.append((line_num, line.strip()))

        except Exception as e:
            pytest.fail(f"Error reading {file_path}: {e}")

        return violations

    def test_no_hardcoded_emails(self):
        """Ensure no real email addresses are hardcoded in prompts."""
        pattern, description = self.SUSPICIOUS_PATTERNS["hardcoded_email"]
        failures = []

        for file_path in self.get_prompt_files():
            if file_path.name in self.EXEMPTED_FILES:
                continue

            violations = self.check_pattern(file_path, pattern, description)
            if violations:
                failures.append((file_path, violations))

        if failures:
            msg = [f"\n{description}:"]
            for file_path, violations in failures:
                msg.append(f"\n  {file_path.relative_to(self.PROMPTS_DIR.parent)}:")
                for line_num, line in violations:
                    msg.append(f"    Line {line_num}: {line[:80]}...")

            pytest.fail(''.join(msg))

    def test_no_hardcoded_folders(self):
        """Ensure specific folder names have clarifying comments."""
        pattern, description = self.SUSPICIOUS_PATTERNS["hardcoded_folder"]
        failures = []

        for file_path in self.get_prompt_files():
            if file_path.name in self.EXEMPTED_FILES:
                continue

            violations = self.check_pattern(file_path, pattern, description)
            if violations:
                # Filter out violations that have comments on same line OR file has disclaimer
                content = file_path.read_text()
                has_file_disclaimer = bool(re.search(r'⚠️.*Important Note', content))

                filtered = [(ln, line) for ln, line in violations
                           if '//' not in line and not has_file_disclaimer]
                if filtered:
                    failures.append((file_path, filtered))

        if failures:
            msg = [f"\n{description}:"]
            msg.append("\nAdd a comment like: // Use user-specified folder name")
            for file_path, violations in failures:
                msg.append(f"\n  {file_path.relative_to(self.PROMPTS_DIR.parent)}:")
                for line_num, line in violations:
                    msg.append(f"    Line {line_num}: {line[:80]}...")

            pytest.fail(''.join(msg))

    def test_no_hardcoded_paths(self):
        """Ensure no absolute paths with specific usernames."""
        pattern, description = self.SUSPICIOUS_PATTERNS["hardcoded_path"]
        failures = []

        for file_path in self.get_prompt_files():
            if file_path.name in self.EXEMPTED_FILES:
                continue

            violations = self.check_pattern(file_path, pattern, description)
            if violations:
                failures.append((file_path, violations))

        if failures:
            msg = [f"\n{description}:"]
            msg.append("\nUse $stepN.field references or [placeholder] syntax instead")
            for file_path, violations in failures:
                msg.append(f"\n  {file_path.relative_to(self.PROMPTS_DIR.parent)}:")
                for line_num, line in violations:
                    msg.append(f"    Line {line_num}: {line[:80]}...")

            pytest.fail(''.join(msg))

    def test_no_hardcoded_phones(self):
        """Ensure no phone numbers are hardcoded."""
        pattern, description = self.SUSPICIOUS_PATTERNS["hardcoded_phone"]
        failures = []

        for file_path in self.get_prompt_files():
            if file_path.name in self.EXEMPTED_FILES:
                continue

            # Skip config.yaml as it contains user's actual phone
            if file_path.name == "config.yaml":
                continue

            violations = self.check_pattern(file_path, pattern, description)
            if violations:
                failures.append((file_path, violations))

        if failures:
            msg = [f"\n{description}:"]
            for file_path, violations in failures:
                msg.append(f"\n  {file_path.relative_to(self.PROMPTS_DIR.parent)}:")
                for line_num, line in violations:
                    msg.append(f"    Line {line_num}: {line[:80]}...")

            pytest.fail(''.join(msg))

    def test_examples_have_disclaimers(self):
        """Ensure example files with specific values include disclaimers."""
        examples_dir = self.PROMPTS_DIR / "examples"

        if not examples_dir.exists():
            pytest.skip("Examples directory not found")

        # Patterns that should have disclaimers
        NEEDS_DISCLAIMER = [
            (r'"(?:study_stuff|misc_folder|test_doc)"', "folder names"),
            (r'"The Night We Met|Tesla Autopilot|Q3 earnings"', "document names"),
        ]

        failures = []

        for file_path in examples_dir.rglob("*.md"):
            content = file_path.read_text()

            # Check if file has any patterns that need disclaimers
            needs_disclaimer = False
            patterns_found = []

            for pattern, desc in NEEDS_DISCLAIMER:
                if re.search(pattern, content):
                    needs_disclaimer = True
                    patterns_found.append(desc)

            if needs_disclaimer:
                # Check if disclaimer exists (look for warning emoji or "Note:" or "Important")
                has_disclaimer = bool(re.search(r'(?:⚠️|🚨|⚠|Note:|Important:|WARNING)', content, re.IGNORECASE))

                if not has_disclaimer:
                    failures.append((file_path, patterns_found))

        if failures:
            msg = ["\nExample files with specific values need disclaimers:"]
            msg.append("\nAdd a note like: **⚠️ Important Note:** Values in this example are from the user's request")
            for file_path, patterns in failures:
                msg.append(f"\n  {file_path.relative_to(self.PROMPTS_DIR.parent)}:")
                msg.append(f"    Contains: {', '.join(patterns)}")

            pytest.fail(''.join(msg))

    def test_tool_definitions_use_step_references(self):
        """Ensure tool_definitions.md examples use $stepN references for paths."""
        tool_defs = self.PROMPTS_DIR / "tool_definitions.md"

        if not tool_defs.exists():
            pytest.skip("tool_definitions.md not found")

        content = tool_defs.read_text()

        # Look for doc_path or attachments with hardcoded paths
        violations = []
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            # Skip if already using $step reference
            if '$step' in line:
                continue

            # Check for hardcoded paths in common fields
            if re.search(r'"(?:doc_path|attachments)":\s*(?:\[)?"[/~]', line):
                violations.append((i, line.strip()))

        if violations:
            msg = ["\ntool_definitions.md should use $stepN references for file paths:"]
            for line_num, line in violations[:5]:  # Show first 5
                msg.append(f"\n  Line {line_num}: {line[:80]}...")
            if len(violations) > 5:
                msg.append(f"\n  ... and {len(violations) - 5} more")

            pytest.fail(''.join(msg))


class TestPromptConsistency:
    """Test for consistency across prompt files."""

    PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

    def test_tool_selection_not_duplicated(self):
        """Ensure tool selection rules don't appear in multiple files without cross-reference."""
        # This is a softer test - just flag potential duplications for manual review

        files_to_check = [
            self.PROMPTS_DIR / "system.md",
            self.PROMPTS_DIR / "task_decomposition.md",
            self.PROMPTS_DIR / "examples" / "core" / "02_critical_planning_rules_read_first.md",
        ]

        # Look for google_search usage rules as an example
        google_search_mentions = []

        for file_path in files_to_check:
            if not file_path.exists():
                continue

            content = file_path.read_text()
            if "google_search" in content and "results[0].snippet" in content:
                google_search_mentions.append(file_path.name)

        # It's OK to mention google_search, but if detailed extraction rules appear
        # in multiple places, that's a concern
        if len(google_search_mentions) > 2:
            pytest.fail(
                f"\nDetailed google_search extraction rules found in {len(google_search_mentions)} files: "
                f"{', '.join(google_search_mentions)}\n"
                f"Consider consolidating into tool_definitions.md"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
