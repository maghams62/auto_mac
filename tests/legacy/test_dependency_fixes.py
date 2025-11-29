#!/usr/bin/env python3
"""
Comprehensive test to verify all dependency fixes are working.
Tests all imports and function calls that could cause NameError.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_all_imports():
    """Test that all critical modules can be imported."""
    print("Testing imports...")
    
    imports = [
        ('file_agent', 'from src.agent.file_agent import search_documents, extract_section'),
        ('writing_agent', 'from src.agent.writing_agent import synthesize_content'),
        ('section_interpreter', 'from src.agent.section_interpreter import SectionInterpreter'),
        ('parameter_resolver', 'from src.agent.parameter_resolver import ParameterResolver'),
        ('get_temperature_for_model', 'from src.utils import get_temperature_for_model'),
        ('load_config', 'from src.utils import load_config'),
    ]
    
    failed = []
    for name, import_stmt in imports:
        try:
            exec(import_stmt)
            print(f"  ✅ {name}")
        except (NameError, ImportError) as e:
            print(f"  ❌ {name}: {e}")
            failed.append(name)
    
    return len(failed) == 0

def test_function_execution():
    """Test that functions can execute without NameError."""
    print("\nTesting function execution...")
    
    from src.utils import load_config, get_temperature_for_model
    
    try:
        config = load_config()
        temp = get_temperature_for_model(config)
        print(f"  ✅ get_temperature_for_model: {temp}")
    except NameError as e:
        print(f"  ❌ get_temperature_for_model NameError: {e}")
        return False
    except Exception as e:
        print(f"  ⚠️  get_temperature_for_model other error: {e}")
    
    try:
        from src.agent.section_interpreter import SectionInterpreter
        interpreter = SectionInterpreter(config)
        print(f"  ✅ SectionInterpreter instantiation")
    except NameError as e:
        print(f"  ❌ SectionInterpreter NameError: {e}")
        return False
    except Exception as e:
        print(f"  ⚠️  SectionInterpreter other error: {e}")
    
    try:
        from src.agent.parameter_resolver import ParameterResolver
        resolver = ParameterResolver(config)
        print(f"  ✅ ParameterResolver instantiation")
    except NameError as e:
        print(f"  ❌ ParameterResolver NameError: {e}")
        return False
    except Exception as e:
        print(f"  ⚠️  ParameterResolver other error: {e}")
    
    return True

def test_tool_invocation():
    """Test that tools can be invoked without NameError."""
    print("\nTesting tool invocation...")
    
    from src.agent.file_agent import search_documents, extract_section
    from src.agent.writing_agent import synthesize_content
    
    tools = [
        ('search_documents', lambda: search_documents.invoke({'query': 'test'})),
        ('extract_section', lambda: extract_section.invoke({'doc_path': '/nonexistent.pdf', 'section': 'all'})),
        ('synthesize_content', lambda: synthesize_content.invoke({'source_contents': ['test'], 'topic': 'test', 'synthesis_style': 'concise'})),
    ]
    
    failed = []
    for name, func in tools:
        try:
            result = func()
            # Check if result contains NameError in error message
            if isinstance(result, dict) and result.get('error'):
                error_msg = str(result.get('error_message', ''))
                if 'NameError' in error_msg or 'is not defined' in error_msg:
                    print(f"  ❌ {name}: Dependency error in result - {error_msg}")
                    failed.append(name)
                else:
                    print(f"  ✅ {name}: No NameError (other errors OK)")
            else:
                print(f"  ✅ {name}: Success")
        except NameError as e:
            print(f"  ❌ {name}: NameError - {e}")
            failed.append(name)
        except Exception as e:
            if 'NameError' in str(type(e).__name__):
                print(f"  ❌ {name}: NameError - {e}")
                failed.append(name)
            else:
                print(f"  ✅ {name}: No NameError (other errors OK)")
    
    return len(failed) == 0

if __name__ == '__main__':
    print("="*80)
    print("DEPENDENCY FIX VERIFICATION TEST")
    print("="*80 + "\n")
    
    all_passed = True
    
    if not test_all_imports():
        all_passed = False
    
    if not test_function_execution():
        all_passed = False
    
    if not test_tool_invocation():
        all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL TESTS PASSED - NO DEPENDENCY ERRORS")
    else:
        print("❌ SOME TESTS FAILED - DEPENDENCY ERRORS DETECTED")
    print("="*80)
    
    sys.exit(0 if all_passed else 1)

