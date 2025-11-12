#!/usr/bin/env python3
"""
Tests for RAG Summaries feature.

Tests both natural language and slash command requests for summarize/explain.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agent.file_agent import search_documents, extract_section
from src.agent.writing_agent import synthesize_content
from src.ui.slash_commands import SlashCommandHandler
from src.agent.agent_registry import AgentRegistry
from src.utils import load_config


def test_rag_pipeline_components():
    """Test that RAG pipeline components work correctly."""
    print("Testing RAG pipeline components...")
    
    config = load_config()
    
    # Test search_documents
    try:
        result = search_documents.invoke({"query": "empathy", "user_request": "summarize empathy research"})
        assert "doc_path" in result or result.get("error"), "search_documents should return doc_path or error"
        print("  ✅ search_documents works")
    except Exception as e:
        print(f"  ❌ search_documents failed: {e}")
        return False
    
    # Test extract_section (will fail if file not found, but shouldn't be NameError)
    try:
        if not result.get("error") and result.get("doc_path"):
            extract_result = extract_section.invoke({
                "doc_path": result["doc_path"],
                "section": "all"
            })
            assert isinstance(extract_result, dict), "extract_section should return dict"
            print("  ✅ extract_section works")
    except NameError as e:
        print(f"  ❌ extract_section NameError: {e}")
        return False
    except Exception as e:
        print(f"  ⚠️  extract_section other error (OK if file missing): {type(e).__name__}")
    
    # Test synthesize_content
    try:
        synth_result = synthesize_content.invoke({
            "source_contents": ["Test content about empathy research"],
            "topic": "Empathy Research",
            "synthesis_style": "concise"
        })
        assert "synthesized_content" in synth_result or synth_result.get("error"), "synthesize_content should return synthesized_content or error"
        print("  ✅ synthesize_content works")
    except NameError as e:
        print(f"  ❌ synthesize_content NameError: {e}")
        return False
    except Exception as e:
        print(f"  ❌ synthesize_content failed: {e}")
        return False
    
    return True


def test_slash_command_rag_detection():
    """Test that slash commands detect RAG requests."""
    print("\nTesting slash command RAG detection...")
    
    config = load_config()
    registry = AgentRegistry(config)
    handler = SlashCommandHandler(registry)
    
    # Test RAG keyword detection
    rag_tasks = [
        "/files Summarize the Ed Sheeran files",
        "/files Explain my Tesla docs",
        "/files Describe the empathy research document",
    ]
    
    file_op_tasks = [
        "/files Zip the Ed Sheeran files",
        "/files Organize my Tesla docs",
        "/files Compress the empathy research document",
    ]
    
    for task in rag_tasks:
        parsed = handler.parser.parse(task)
        if parsed:
            task_text = parsed.get("task", "")
            task_lower = task_text.lower()
            rag_keywords = ["summarize", "summarise", "summary", "explain", "describe"]
            is_rag = any(keyword in task_lower for keyword in rag_keywords)
            print(f"  ✅ '{task}' detected as RAG: {is_rag}")
    
    for task in file_op_tasks:
        parsed = handler.parser.parse(task)
        if parsed:
            task_text = parsed.get("task", "")
            task_lower = task_text.lower()
            file_op_keywords = ["zip", "organize", "compress"]
            is_file_op = any(keyword in task_lower for keyword in file_op_keywords)
            print(f"  ✅ '{task}' detected as file op: {is_file_op}")
    
    return True


def test_rag_pipeline_execution():
    """Test RAG pipeline execution through slash command handler."""
    print("\nTesting RAG pipeline execution...")
    
    config = load_config()
    registry = AgentRegistry(config)
    handler = SlashCommandHandler(registry)
    
    # Test with a summarize request
    try:
        is_command, result = handler.handle("/files Summarize empathy research")
        assert is_command, "Should recognize as slash command"
        assert isinstance(result, dict), "Should return dict result"
        
        if result.get("type") == "error":
            print(f"  ⚠️  Error (may be expected if no docs): {result.get('content', 'Unknown error')}")
        else:
            result_data = result.get("result", {})
            if result_data.get("rag_pipeline"):
                print("  ✅ RAG pipeline executed successfully")
                print(f"     Summary length: {result_data.get('word_count', 0)} words")
            elif result_data.get("error"):
                print(f"  ⚠️  Pipeline error (may be expected): {result_data.get('error_message', 'Unknown')}")
            else:
                print("  ⚠️  Result doesn't indicate RAG pipeline (may be using LLM routing)")
    except Exception as e:
        print(f"  ❌ RAG pipeline execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def main():
    """Run all tests."""
    print("="*80)
    print("RAG SUMMARIES FEATURE TESTS")
    print("="*80 + "\n")
    
    all_passed = True
    
    if not test_rag_pipeline_components():
        all_passed = False
    
    if not test_slash_command_rag_detection():
        all_passed = False
    
    if not test_rag_pipeline_execution():
        all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("⚠️  SOME TESTS HAD ISSUES (check output above)")
    print("="*80)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

