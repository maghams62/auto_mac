#!/usr/bin/env python3
"""
Lightweight audit script to check for missing imports and common issues.
"""
import ast
import os
from pathlib import Path
from typing import Set, Dict, List, Tuple
import sys

def extract_imports(file_path):
    """Extract imported names from typing module"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            tree = ast.parse(content)

        typing_imports = set()
        used_typing_names = set()
        all_imports = set()

        # Find all imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    all_imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    all_imports.add(node.module.split('.')[0])

                    # Track typing imports specifically
                    if node.module == 'typing':
                        for alias in node.names:
                            if alias.name == '*':
                                typing_imports.add('*')
                            else:
                                typing_imports.add(alias.name)

        # Find type annotations that might use typing
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check return annotation
                if node.returns:
                    for name_node in ast.walk(node.returns):
                        if isinstance(name_node, ast.Name):
                            used_typing_names.add(name_node.id)

                # Check argument annotations
                for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                    if arg.annotation:
                        for name_node in ast.walk(arg.annotation):
                            if isinstance(name_node, ast.Name):
                                used_typing_names.add(name_node.id)

            # Check variable annotations
            if isinstance(node, ast.AnnAssign):
                if node.annotation:
                    for name_node in ast.walk(node.annotation):
                        if isinstance(name_node, ast.Name):
                            used_typing_names.add(name_node.id)

        # Common typing types
        common_typing = {'Any', 'Dict', 'List', 'Optional', 'Union', 'Tuple',
                        'Set', 'Callable', 'Iterable', 'Iterator', 'Sequence',
                        'Mapping', 'Type', 'TypeVar', 'Generic', 'Protocol',
                        'Literal', 'Final', 'ClassVar', 'Awaitable'}

        # Find potentially missing typing imports
        if '*' in typing_imports:
            missing = set()  # import * covers everything
        else:
            missing = (used_typing_names & common_typing) - typing_imports

        return typing_imports, used_typing_names, missing, all_imports
    except Exception as e:
        return None, None, None, None

def check_common_import_errors(file_path):
    """Check for common import-related issues"""
    issues = []
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        # Check for common patterns that might cause issues
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            # Check for bare 'from X import' without names
            if line.strip().startswith('from ') and line.strip().endswith('import'):
                issues.append((i, 'Incomplete import statement'))

    except Exception:
        pass

    return issues

def main():
    print("=" * 60)
    print("Import & Dependency Audit")
    print("=" * 60)
    print()

    # Scan Python files
    typing_issues = []
    import_errors = []
    syntax_errors = []

    src_dir = Path('src')
    all_files = list(src_dir.rglob('*.py'))

    print(f"Scanning {len(all_files)} Python files in src/...\n")

    for py_file in all_files:
        # Check typing imports
        typing_imports, used_names, missing, all_imports = extract_imports(py_file)
        if missing:
            typing_issues.append((str(py_file), missing))

        # Check for common import errors
        errors = check_common_import_errors(py_file)
        if errors:
            import_errors.append((str(py_file), errors))

        # Try to compile to catch syntax errors
        try:
            with open(py_file, 'r') as f:
                compile(f.read(), str(py_file), 'exec')
        except SyntaxError as e:
            syntax_errors.append((str(py_file), str(e)))

    # Report findings
    print("RESULTS:")
    print("-" * 60)

    if syntax_errors:
        print("\n❌ SYNTAX ERRORS:")
        for file, error in syntax_errors:
            print(f"\n{file}:")
            print(f"  {error}")

    if typing_issues:
        print("\n⚠️  POTENTIAL MISSING TYPING IMPORTS:")
        for file, missing in typing_issues:
            print(f"\n{file}:")
            missing_str = ', '.join(sorted(missing))
            print(f"  Missing: {missing_str}")

    if import_errors:
        print("\n⚠️  IMPORT STATEMENT ISSUES:")
        for file, errors in import_errors:
            print(f"\n{file}:")
            for line_no, issue in errors:
                print(f"  Line {line_no}: {issue}")

    if not syntax_errors and not typing_issues and not import_errors:
        print("\n✅ No issues found!")
        print("\nAll Python files:")
        print("  - Have correct syntax")
        print("  - Have proper typing imports")
        print("  - Have valid import statements")

    print("\n" + "=" * 60)

    # Try importing key modules
    print("\nTesting critical imports...")
    print("-" * 60)

    critical_modules = [
        'src.agent.agent',
        'src.memory.session_manager',
        'src.config_manager',
        'src.workflow',
    ]

    failed_imports = []
    for module in critical_modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except Exception as e:
            print(f"❌ {module}: {str(e)[:80]}")
            failed_imports.append((module, str(e)))

    print("\n" + "=" * 60)

    if failed_imports:
        print("\n❌ FAILED IMPORTS DETECTED")
        print("\nFailed modules:")
        for module, error in failed_imports:
            print(f"\n{module}:")
            print(f"  {error}")
        return 1
    else:
        print("\n✅ All critical modules import successfully!")
        return 0

if __name__ == '__main__':
    sys.exit(main())
