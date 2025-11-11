#!/usr/bin/env python3
"""
Fix test file paths after reorganization.
Updates Path(__file__).parent to Path(__file__).parent.parent
for files now in tests/ directory.
"""

import re
from pathlib import Path

# Get project root
project_root = Path(__file__).parent.parent
tests_dir = project_root / "tests"

# Patterns to fix
patterns = [
    (r'sys\.path\.insert\(0,\s*str\(Path\(__file__\)\.parent\)\)', 
     r'sys.path.insert(0, str(Path(__file__).parent.parent))'),
    (r'sys\.path\.insert\(0,\s*str\(Path\(__file__\)\.parent\s*/\s*"src"\)\)',
     r'sys.path.insert(0, str(Path(__file__).parent.parent))'),
    (r'# Add src to path',
     r'# Add project root to path'),
    (r'# Add.*path',
     r'# Add project root to path'),
]

def fix_file(file_path):
    """Fix path references in a test file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)
        
        # Also fix any direct Path(__file__).parent that's used for project_root
        if 'project_root' not in content and 'Path(__file__).parent' in content:
            # Add project_root variable if not present
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'sys.path.insert' in line and 'Path(__file__).parent.parent' in line:
                    # Check if project_root is defined above
                    if i > 0 and 'project_root' not in lines[i-1]:
                        # Add project_root definition before sys.path.insert
                        indent = len(line) - len(line.lstrip())
                        lines.insert(i, ' ' * indent + 'project_root = Path(__file__).parent.parent')
                        break
            content = '\n'.join(lines)
        
        if content != original:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
    
    return False

def main():
    """Fix all test files."""
    test_files = list(tests_dir.glob("*.py"))
    fixed_count = 0
    
    for test_file in test_files:
        if fix_file(test_file):
            print(f"Fixed: {test_file.name}")
            fixed_count += 1
    
    print(f"\nFixed {fixed_count} files")

if __name__ == "__main__":
    main()

