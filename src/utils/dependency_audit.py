#!/usr/bin/env python3
"""
Comprehensive dependency and parameter audit script.
Checks for missing/unused packages, type issues, and parameter mismatches.
"""
import ast
import os
import sys
from pathlib import Path
from typing import Set, Dict, List, Tuple, Optional
import subprocess
import importlib.metadata
import pkg_resources
import re

def extract_imports_from_file(file_path: str) -> Set[str]:
    """Extract all imported module names from a Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content)
        imports = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # Get the root module name
                    module_name = alias.name.split('.')[0]
                    imports.add(module_name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]
                    imports.add(module_name)

        return imports
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return set()

def extract_imports_from_directory(dir_path: str) -> Dict[str, Set[str]]:
    """Extract imports from all Python files in a directory."""
    imports_by_file = {}

    for py_file in Path(dir_path).rglob('*.py'):
        if 'test_' in py_file.name or '__pycache__' in str(py_file):
            continue
        imports = extract_imports_from_file(str(py_file))
        if imports:
            imports_by_file[str(py_file)] = imports

    return imports_by_file

def parse_requirements_txt(file_path: str) -> Set[str]:
    """Parse requirements.txt and extract package names."""
    packages = set()

    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Extract package name (before any version specifiers)
                    package_name = re.split(r'[>=<~]', line)[0].strip()
                    packages.add(package_name)
    except Exception as e:
        print(f"Error parsing requirements.txt: {e}")

    return packages

def get_installed_packages() -> Set[str]:
    """Get set of currently installed packages."""
    try:
        installed = set()
        for dist in pkg_resources.working_set:
            installed.add(dist.project_name.lower().replace('-', '_'))
        return installed
    except Exception as e:
        print(f"Error getting installed packages: {e}")
        return set()

def find_missing_dependencies(imports: Set[str], requirements: Set[str], installed: Set[str]) -> Tuple[Set[str], Set[str]]:
    """Find missing dependencies and potentially unused packages."""
    # Normalize package names (common variations)
    normalize_map = {
        'PIL': 'pillow',
        'cv2': 'opencv-python',
        'sklearn': 'scikit-learn',
        'yaml': 'pyyaml',
        'dotenv': 'python-dotenv',
        'dateutil': 'python-dateutil',
        'OpenAI': 'openai',
        'faiss': 'faiss-cpu',
        'PyPDF2': 'pypdf2',
        'fitz': 'pymupdf',
        'quartz': 'pyobjc-framework-quartz',
        'langchain_openai': 'langchain-openai',
        'llama_index': 'llama-index',
        'requests_oauthlib': 'requests-oauthlib',
    }

    # Local modules within src/ that should not be treated as external dependencies
    local_modules = {
        'agent', 'automation', 'config', 'config_manager', 'config_validator',
        'documents', 'integrations', 'llm', 'memory', 'orchestrator', 'prompts',
        'ui', 'utils', 'src', 'context', 'context_bus', 'validator', 'verifier',
        'planner', 'executor', 'critic_agent', 'feasibility_checker', 'parameter_resolver',
        'reasoning_trace', 'retry_context_manager', 'retry_logger', 'session_manager',
        'session_memory', 'state', 'help_models', 'help_registry', 'tools_catalog',
        'parser', 'json_parser', 'indexer', 'search', 'nodes', 'reply_tool',
        'logger', 'error_analyzer', 'intent_planner', 'section_interpreter',
        'writing_ui_formatter', 'micro_actions_agent', 'screen_agent', 'screen_capture',
        'vision_agent', 'voice_agent', 'weather_agent', 'maps_agent', 'maps_automation',
        'spotify_agent', 'spotify_api', 'spotify_automation', 'song_disambiguator',
        'discord_agent', 'twitter_agent', 'bluesky_agent', 'reddit_agent',
        'whatsapp_agent', 'imessage_agent', 'email_agent', 'notes_agent',
        'reminders_agent', 'calendar_agent', 'calendar_automation', 'file_agent',
        'folder_agent', 'presentation_agent', 'report_agent', 'writing_agent',
        'enriched_stock_agent', 'stock_agent', 'google_agent', 'google_finance_agent',
        'browser_agent', 'celebration_agent', 'celebration_automation', 'notifications_agent',
        'base64', 'dataclasses', 'importlib', 'uuid', 'zoneinfo', 'urllib3',
        'pkg_resources', 'ruamel', 'googlesearch', 'quartz', 'pandas', 'reportlab',
        'llamaindex_worker', 'langchain_core', 'langextract', 'docx', 'bs4',
        'agent_capabilities', 'agent_registry', 'agent_router', 'chat', 'keynote_composer',
        'mail_composer', 'mail_reader', 'pages_composer', 'screenshot'
    }

    # Standard library modules
    stdlib_modules = {
        'os', 'sys', 'json', 're', 'datetime', 'time', 'pathlib', 'typing',
        'collections', 'itertools', 'functools', 'operator', 'math', 'random',
        'string', 'urllib', 'http', 'xml', 'html', 'email', 'logging', 'threading',
        'multiprocessing', 'subprocess', 'tempfile', 'shutil', 'glob', 'fnmatch',
        'linecache', 'pickle', 'copyreg', 'copy', 'pprint', 'reprlib', 'enum',
        'numbers', 'cmath', 'decimal', 'fractions', 'statistics', 'ast', 'inspect',
        'site', 'warnings', 'contextlib', 'abc', 'atexit', 'traceback', '__future__',
        'keyword', 'ast', 'token', 'tokenize', 'tabnanny', 'pyclbr', 'py_compile',
        'compileall', 'dis', 'pickletools', 'platform', 'errno', 'ctypes',
        'msvcrt', 'winreg', 'winsound', 'posix', 'pwd', 'spwd', 'grp', 'crypt',
        'termios', 'tty', 'pty', 'fcntl', 'pipes', 'resource', 'nis', 'syslog',
        'optparse', 'argparse', 'optparse', 'getopt', 'readline', 'rlcompleter',
        'sqlite3', 'zlib', 'gzip', 'bz2', 'lzma', 'zipfile', 'tarfile', 'csv',
        'configparser', 'netrc', 'xdrlib', 'plistlib', 'hashlib', 'hmac', 'secrets',
        'ssl', 'socket', 'mmap', 'contextvars', 'concurrent', 'asyncio', 'queue',
        'sched', '_thread', 'dummy_thread', 'io', 'codecs', 'unicodedata',
        'stringprep', 're', 'difflib', 'textwrap', 'locale', 'gettext', 'argparse',
        'optparse', 'getopt', 'readline', 'rlcompleter', 'sqlite3', 'zlib',
        'gzip', 'bz2', 'lzma', 'zipfile', 'tarfile', 'csv', 'configparser',
        'netrc', 'xdrlib', 'plistlib', 'hashlib', 'hmac', 'secrets', 'ssl',
        'socket', 'mmap', 'contextvars', 'concurrent', 'asyncio', 'queue',
        'sched', '_thread', 'dummy_thread', 'io', 'codecs', 'unicodedata',
        'stringprep', 're', 'difflib', 'textwrap', 'locale', 'gettext'
    }

    # Filter out local and stdlib modules
    external_imports = imports - local_modules - stdlib_modules

    normalized_imports = set()
    for imp in external_imports:
        normalized_imports.add(normalize_map.get(imp, imp.lower()))

    normalized_requirements = set(pkg.lower() for pkg in requirements)
    normalized_installed = set(pkg.lower().replace('-', '_') for pkg in installed)

    # Find potentially missing packages (imported but not in requirements)
    potentially_missing = normalized_imports - normalized_requirements

    # Find potentially unused packages (in requirements but not imported)
    potentially_unused = normalized_requirements - normalized_imports

    return potentially_missing, potentially_unused

def run_mypy_check(src_dir: str) -> Tuple[bool, str]:
    """Run mypy type checking if available."""
    try:
        result = subprocess.run(
            ['mypy', src_dir, '--ignore-missing-imports', '--no-error-summary'],
            capture_output=True, text=True, timeout=300
        )
        return result.returncode == 0, result.stdout + result.stderr
    except FileNotFoundError:
        return False, "mypy not installed"
    except subprocess.TimeoutExpired:
        return False, "mypy check timed out"
    except Exception as e:
        return False, f"Error running mypy: {e}"

def check_function_signatures(src_dir: str) -> List[Tuple[str, str]]:
    """Check for potential function signature mismatches."""
    issues = []

    for py_file in Path(src_dir).rglob('*.py'):
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Check for common parameter issues
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id

                        # Look for suspicious patterns
                        if len(node.args) > 10:  # Too many positional args
                            issues.append((str(py_file), f"Function '{func_name}' called with {len(node.args)} positional arguments - consider using keyword arguments"))

                        # Check for specific problematic patterns
                        if func_name in ['json.loads', 'json.dumps'] and len(node.args) > 1:
                            issues.append((str(py_file), f"Function '{func_name}' called with positional arguments - should use keyword arguments for clarity"))

                        # Check for subprocess calls without proper argument handling
                        if func_name in ['subprocess.run', 'subprocess.call', 'subprocess.Popen']:
                            if node.args and isinstance(node.args[0], ast.List):
                                # Check if shell=True is used with list arguments (dangerous)
                                has_shell = any(
                                    (isinstance(kw, ast.keyword) and kw.arg == 'shell' and
                                     isinstance(kw.value, ast.Constant) and kw.value.value is True)
                                    for kw in node.keywords
                                )
                                if has_shell:
                                    issues.append((str(py_file), f"subprocess call with shell=True - security risk"))

                    # Check for attribute calls that might have issues
                    elif isinstance(node.func, ast.Attribute):
                        if isinstance(node.func.value, ast.Name):
                            module_name = node.func.value.id
                            attr_name = node.func.attr

                            # Check for problematic API calls
                            if module_name == 'requests' and attr_name in ['get', 'post', 'put', 'delete']:
                                # Check if timeout is missing
                                has_timeout = any(
                                    isinstance(kw, ast.keyword) and kw.arg == 'timeout'
                                    for kw in node.keywords
                                )
                                if not has_timeout:
                                    issues.append((str(py_file), f"requests.{attr_name} call without timeout parameter"))

        except Exception as e:
            issues.append((str(py_file), f"Error parsing: {e}"))

    return issues

def run_pytest_suites(test_dirs: List[str]) -> Tuple[bool, str]:
    """Run pytest on specified directories."""
    all_passed = True
    output = ""

    for test_dir in test_dirs:
        if not Path(test_dir).exists():
            continue

        try:
            result = subprocess.run(
                ['python', '-m', 'pytest', test_dir, '-v', '--tb=short'],
                capture_output=True, text=True, timeout=600
            )
            output += f"\n=== Pytest Results for {test_dir} ===\n"
            output += result.stdout
            if result.stderr:
                output += f"STDERR:\n{result.stderr}"

            if result.returncode != 0:
                all_passed = False
        except subprocess.TimeoutExpired:
            output += f"\n=== Pytest timed out for {test_dir} ===\n"
            all_passed = False
        except Exception as e:
            output += f"\n=== Error running pytest for {test_dir}: {e} ===\n"
            all_passed = False

    return all_passed, output

def main():
    print("=" * 80)
    print("Comprehensive Dependency & Parameter Audit")
    print("=" * 80)

    src_dir = "src"
    tests_dir = "tests"
    requirements_file = "requirements.txt"

    # 1. Extract imports from source and test files
    print("\n1. Analyzing imports...")
    src_imports = extract_imports_from_directory(src_dir)
    test_imports = extract_imports_from_directory(tests_dir)

    all_imports = set()
    for imports in src_imports.values():
        all_imports.update(imports)
    for imports in test_imports.values():
        all_imports.update(imports)

    print(f"   Found {len(all_imports)} unique imported modules")

    # 2. Parse requirements.txt
    print("\n2. Parsing requirements.txt...")
    requirements = parse_requirements_txt(requirements_file)
    print(f"   Found {len(requirements)} declared dependencies")

    # 3. Get installed packages
    print("\n3. Checking installed packages...")
    installed = get_installed_packages()
    print(f"   Found {len(installed)} installed packages")

    # 4. Find missing/unused dependencies
    print("\n4. Analyzing dependency health...")
    missing, unused = find_missing_dependencies(all_imports, requirements, installed)

    if missing:
        print(f"   ⚠️  Potentially missing dependencies: {', '.join(sorted(missing))}")
    else:
        print("   ✅ No missing dependencies detected")

    if unused:
        print(f"   ⚠️  Potentially unused dependencies: {', '.join(sorted(unused))}")
    else:
        print("   ✅ No unused dependencies detected")

    # 5. Run type checking
    print("\n5. Running type checking...")
    mypy_passed, mypy_output = run_mypy_check(src_dir)
    if mypy_passed:
        print("   ✅ Type checking passed")
    else:
        print("   ❌ Type checking found issues")
        print(mypy_output[:1000] + "..." if len(mypy_output) > 1000 else mypy_output)

    # 6. Check function signatures
    print("\n6. Checking function signatures...")
    signature_issues = check_function_signatures(src_dir)
    if signature_issues:
        print(f"   ⚠️  Found {len(signature_issues)} potential signature issues:")
        for file_path, issue in signature_issues[:10]:  # Show first 10
            print(f"      {file_path}: {issue}")
        if len(signature_issues) > 10:
            print(f"      ... and {len(signature_issues) - 10} more")
    else:
        print("   ✅ No signature issues detected")

    # 7. Run pytest suites
    print("\n7. Running targeted tests...")
    test_dirs = ["tests/agent", "tests/automation"]
    pytest_passed, pytest_output = run_pytest_suites(test_dirs)

    if pytest_passed:
        print("   ✅ All targeted tests passed")
    else:
        print("   ❌ Some tests failed")
        print(pytest_output[:2000] + "..." if len(pytest_output) > 2000 else pytest_output)

    # Summary
    print("\n" + "=" * 80)
    print("AUDIT SUMMARY")
    print("=" * 80)

    issues_found = bool(missing or unused or not mypy_passed or signature_issues or not pytest_passed)

    if issues_found:
        print("❌ ISSUES FOUND:")
        if missing:
            print(f"   - {len(missing)} potentially missing dependencies")
        if unused:
            print(f"   - {len(unused)} potentially unused dependencies")
        if not mypy_passed:
            print("   - Type checking failures")
        if signature_issues:
            print(f"   - {len(signature_issues)} function signature issues")
        if not pytest_passed:
            print("   - Test failures")
        print("\n🔧 RECOMMENDATIONS:")
        print("   - Review potentially missing dependencies and add to requirements.txt if needed")
        print("   - Remove unused dependencies from requirements.txt")
        print("   - Fix type checking errors or configure mypy properly")
        print("   - Review function calls for parameter mismatches")
        print("   - Fix failing tests")
        return 1
    else:
        print("✅ NO ISSUES FOUND")
        print("   All dependencies are properly declared and used")
        print("   Type checking passed")
        print("   Function signatures appear correct")
        print("   All targeted tests passed")
        return 0

if __name__ == '__main__':
    sys.exit(main())
