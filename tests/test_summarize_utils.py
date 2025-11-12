#!/usr/bin/env python3
"""
Shared utilities for comprehensive summarize command testing.

Provides functions to verify summary quality, LLM reasoning, and parameter extraction.
"""

import sys
import os
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.utils import load_config, get_temperature_for_model


def verify_summary_quality(summary: str, source_data: List[Dict[str, Any]], source_type: str = "generic") -> Dict[str, Any]:
    """
    Validates that a summary references actual source content and is coherent.
    
    Args:
        summary: The generated summary text
        source_data: List of source items (emails, posts, reminders, etc.)
        source_type: Type of source ("email", "bluesky", "reminder", "calendar", "news")
    
    Returns:
        Dictionary with validation results:
        {
            "is_relevant": bool,
            "is_coherent": bool,
            "mentions_source_entities": bool,
            "entity_coverage": float,  # 0.0-1.0
            "issues": List[str],
            "score": float  # Overall quality score 0.0-1.0
        }
    """
    if not summary or not source_data:
        return {
            "is_relevant": False,
            "is_coherent": False,
            "mentions_source_entities": False,
            "entity_coverage": 0.0,
            "issues": ["Empty summary or source data"],
            "score": 0.0
        }
    
    issues = []
    score = 1.0
    
    # Extract key entities from source data based on type
    source_entities = []
    if source_type == "email":
        for item in source_data:
            if item.get('sender'):
                source_entities.append(item['sender'].lower())
            if item.get('subject'):
                source_entities.append(item['subject'].lower())
    elif source_type == "bluesky":
        for item in source_data:
            if item.get('author_name'):
                source_entities.append(item['author_name'].lower())
            if item.get('text'):
                # Extract key words from post text
                words = item['text'].lower().split()[:5]  # First 5 words
                source_entities.extend(words)
    elif source_type == "reminder":
        for item in source_data:
            if item.get('title'):
                source_entities.append(item['title'].lower())
    elif source_type == "calendar":
        for item in source_data:
            if item.get('title'):
                source_entities.append(item['title'].lower())
            if item.get('location'):
                source_entities.append(item['location'].lower())
    elif source_type == "news":
        for item in source_data:
            if item.get('title'):
                source_entities.append(item['title'].lower())
    
    # Check if summary mentions source entities
    summary_lower = summary.lower()
    mentioned_entities = [e for e in source_entities if e in summary_lower]
    entity_coverage = len(mentioned_entities) / len(source_entities) if source_entities else 0.0
    
    if entity_coverage < 0.3:
        issues.append(f"Low entity coverage: {entity_coverage:.1%} (expected >= 30%)")
        score -= 0.3
    
    # Check for coherence indicators (not random text)
    coherence_indicators = [
        len(summary) > 50,  # Not too short
        not summary.lower().startswith("error"),
        "summary" not in summary_lower[:20] or "here" in summary_lower[:50],  # Not just "Here is a summary"
        any(char in summary for char in ['.', ':', '-']),  # Has structure
    ]
    
    is_coherent = all(coherence_indicators)
    if not is_coherent:
        issues.append("Summary appears incoherent or generic")
        score -= 0.3
    
    # Check for relevance (summary should relate to source)
    is_relevant = entity_coverage > 0.2 or len(summary) > 100
    
    return {
        "is_relevant": is_relevant,
        "is_coherent": is_coherent,
        "mentions_source_entities": entity_coverage > 0.2,
        "entity_coverage": entity_coverage,
        "issues": issues,
        "score": max(0.0, score)
    }


def verify_llm_reasoning(plan: List[Dict[str, Any]], query: str, expected_patterns: List[str] = None) -> Dict[str, Any]:
    """
    Verifies that a plan uses LLM reasoning (no hardcoding) for parameter extraction.
    
    Args:
        plan: List of plan steps from orchestrator
        query: Original user query
        expected_patterns: List of patterns that should NOT be hardcoded (e.g., ["24", "7 days"])
    
    Returns:
        Dictionary with verification results:
        {
            "uses_llm_reasoning": bool,
            "hardcoded_values": List[str],
            "issues": List[str],
            "score": float
        }
    """
    issues = []
    hardcoded_values = []
    score = 1.0
    
    # Common hardcoded patterns to check
    if expected_patterns is None:
        expected_patterns = ["24", "7", "default", "hardcoded"]
    
    plan_str = json.dumps(plan, indent=2).lower()
    query_lower = query.lower()
    
    # Check if plan parameters match query (indicating LLM reasoning)
    # Extract numbers from query
    query_numbers = re.findall(r'\d+', query_lower)
    
    # Check if plan uses query-derived values
    uses_query_values = False
    for num in query_numbers:
        if num in plan_str:
            uses_query_values = True
            break
    
    # Check for hardcoded defaults that don't match query
    if "24" in plan_str and "24" not in query_lower and "hour" not in query_lower:
        hardcoded_values.append("24 (hours)")
        issues.append("Plan contains hardcoded 24-hour default not in query")
        score -= 0.2
    
    if "7" in plan_str and "7" not in query_lower and "week" not in query_lower and "day" not in query_lower:
        hardcoded_values.append("7 (days)")
        issues.append("Plan contains hardcoded 7-day default not in query")
        score -= 0.2
    
    # Check if parameters are extracted from query context
    uses_llm_reasoning = uses_query_values or len(hardcoded_values) == 0
    
    return {
        "uses_llm_reasoning": uses_llm_reasoning,
        "hardcoded_values": hardcoded_values,
        "issues": issues,
        "score": max(0.0, score)
    }


def verify_time_window_extraction(query: str, extracted_window: Optional[Dict[str, int]], expected_window: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """
    Verifies that time window extraction uses LLM reasoning.
    
    Args:
        query: User query containing time window
        extracted_window: Extracted time window dict (e.g., {"hours": 2})
        expected_window: Expected window if known
    
    Returns:
        Dictionary with verification results
    """
    issues = []
    score = 1.0
    
    if extracted_window is None:
        # Check if query actually contains time window
        has_time_keywords = any(kw in query.lower() for kw in ["hour", "day", "minute", "last", "past", "next"])
        if has_time_keywords:
            issues.append("Time window not extracted despite time keywords in query")
            score -= 0.5
        return {
            "extracted": False,
            "matches_query": False,
            "issues": issues,
            "score": max(0.0, score)
        }
    
    # Extract numbers from query
    query_numbers = re.findall(r'\d+', query.lower())
    
    # Check if extracted window matches query
    extracted_hours = extracted_window.get("hours", 0)
    extracted_minutes = extracted_window.get("minutes", 0)
    
    matches_query = False
    if extracted_hours > 0:
        matches_query = str(extracted_hours) in query_numbers
    elif extracted_minutes > 0:
        matches_query = str(extracted_minutes) in query_numbers
    
    if not matches_query and query_numbers:
        issues.append(f"Extracted window {extracted_window} doesn't match query numbers {query_numbers}")
        score -= 0.3
    
    # Check for common hardcoded defaults
    if extracted_hours == 24 and "24" not in query.lower() and "day" not in query.lower():
        issues.append("Using hardcoded 24-hour default")
        score -= 0.2
    
    if extracted_hours == 1 and "1" not in query.lower() and "hour" in query.lower():
        # This might be OK if query says "past hour" without number
        pass
    
    return {
        "extracted": True,
        "matches_query": matches_query,
        "window": extracted_window,
        "issues": issues,
        "score": max(0.0, score)
    }


def verify_workflow_correctness(plan: List[Dict[str, Any]], expected_workflow: List[str]) -> Dict[str, Any]:
    """
    Verifies that plan follows expected workflow pattern.
    
    Args:
        plan: List of plan steps
        expected_workflow: List of expected tool names in order (e.g., ["read_latest_emails", "summarize_emails", "reply_to_user"])
    
    Returns:
        Dictionary with verification results
    """
    actual_tools = [step.get("action") or step.get("tool", "") for step in plan]
    
    # Check if expected tools appear in order
    expected_idx = 0
    matches = []
    for tool in actual_tools:
        if expected_idx < len(expected_workflow) and expected_workflow[expected_idx] in tool:
            matches.append(expected_workflow[expected_idx])
            expected_idx += 1
    
    all_matched = len(matches) == len(expected_workflow)
    coverage = len(matches) / len(expected_workflow) if expected_workflow else 0.0
    
    issues = []
    if not all_matched:
        missing = [t for t in expected_workflow if t not in matches]
        issues.append(f"Missing expected tools in workflow: {missing}")
        issues.append(f"Expected: {expected_workflow}, Found: {actual_tools}")
    
    return {
        "correct_workflow": all_matched,
        "coverage": coverage,
        "expected_tools": expected_workflow,
        "actual_tools": actual_tools,
        "matched_tools": matches,
        "issues": issues,
        "score": coverage
    }


def verify_summary_relevance_with_llm(summary: str, source_data: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
    """
    Uses LLM to verify summary relevance and coherence.
    
    Args:
        summary: Generated summary
        source_data: Source data that was summarized
        query: Original user query
    
    Returns:
        Dictionary with LLM verification results
    """
    try:
        config = load_config()
        openai_config = config.get("openai", {})
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o-mini"),
            temperature=0.0,  # Deterministic for verification
            api_key=openai_config.get("api_key")
        )
        
        # Prepare source summary
        source_summary = f"Summarized {len(source_data)} items"
        if source_data:
            sample_items = source_data[:3]
            source_summary = json.dumps(sample_items, indent=2)[:500]
        
        prompt = f"""You are a quality assurance validator. Verify that a summary is relevant and coherent.

USER QUERY: {query}

SOURCE DATA (sample):
{source_summary}

GENERATED SUMMARY:
{summary}

Evaluate:
1. Does the summary accurately reflect the source data?
2. Is the summary coherent (not random/generic text)?
3. Does the summary address the user's query?
4. Are there any factual errors or hallucinations?

Respond with JSON:
{{
    "is_relevant": true/false,
    "is_coherent": true/false,
    "addresses_query": true/false,
    "has_errors": true/false,
    "score": 0.0-1.0,
    "issues": ["issue1", "issue2"]
}}
"""
        
        messages = [
            SystemMessage(content="You are a quality assurance validator for text summaries."),
            HumanMessage(content=prompt)
        ]
        
        response = llm.invoke(messages)
        response_text = response.content
        
        # Parse JSON response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start != -1 and json_end > 0:
            json_str = response_text[json_start:json_end]
            result = json.loads(json_str)
            return result
        
        return {
            "is_relevant": False,
            "is_coherent": False,
            "addresses_query": False,
            "has_errors": True,
            "score": 0.0,
            "issues": ["Failed to parse LLM verification response"]
        }
        
    except Exception as e:
        return {
            "is_relevant": False,
            "is_coherent": False,
            "addresses_query": False,
            "has_errors": True,
            "score": 0.0,
            "issues": [f"LLM verification error: {str(e)}"]
        }


def verify_calendar_summary_quality(summary: str, events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Verify calendar summary quality with calendar-specific checks.
    
    Args:
        summary: The generated summary text
        events: List of calendar event dictionaries
    
    Returns:
        Dictionary with validation results:
        {
            "has_event_titles": bool,
            "has_event_times": bool,
            "has_locations": bool,
            "has_attendees": bool,
            "is_chronological": bool,
            "event_coverage": float,  # 0.0-1.0
            "issues": List[str],
            "score": float  # Overall quality score 0.0-1.0
        }
    """
    if not summary or not events:
        return {
            "has_event_titles": False,
            "has_event_times": False,
            "has_locations": False,
            "has_attendees": False,
            "is_chronological": False,
            "event_coverage": 0.0,
            "issues": ["Empty summary or events"],
            "score": 0.0
        }
    
    issues = []
    score = 1.0
    summary_lower = summary.lower()
    
    # Check for event titles
    event_titles = [e.get('title', '').lower() for e in events[:5]]  # Check first 5 events
    mentioned_titles = [title for title in event_titles if title and title in summary_lower]
    has_event_titles = len(mentioned_titles) > 0
    title_coverage = len(mentioned_titles) / len([t for t in event_titles if t]) if event_titles else 0.0
    
    if not has_event_titles:
        issues.append("No event titles mentioned in summary")
        score -= 0.3
    
    # Check for event times
    has_event_times = False
    for event in events[:5]:
        start_time = event.get('start_time', '')
        if start_time:
            # Check for time patterns (HH:MM format or date references)
            time_patterns = [
                start_time.split('T')[1][:5] if 'T' in start_time else None,  # Extract HH:MM
                start_time.split('T')[0] if 'T' in start_time else None,  # Extract date
            ]
            if any(pattern and pattern in summary for pattern in time_patterns if pattern):
                has_event_times = True
                break
    
    if not has_event_times:
        issues.append("No event times mentioned in summary")
        score -= 0.2
    
    # Check for locations
    locations = [e.get('location', '').lower() for e in events if e.get('location')]
    mentioned_locations = [loc for loc in locations if loc and loc in summary_lower]
    has_locations = len(mentioned_locations) > 0
    
    # Check for attendees (for meeting events)
    meeting_events = [e for e in events if e.get('attendees') and len(e.get('attendees', [])) > 0]
    has_attendees = False
    if meeting_events:
        for event in meeting_events[:3]:
            attendees = [a.lower() for a in event.get('attendees', [])]
            if any(attendee.split('@')[0] in summary_lower for attendee in attendees[:2]):
                has_attendees = True
                break
    
    # Check chronological organization (look for date/time ordering)
    is_chronological = any(
        keyword in summary_lower for keyword in [
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
            'november', 'december', 'next week', 'this week', 'upcoming',
            'first', 'then', 'later', 'after', 'before'
        ]
    )
    
    # Calculate event coverage
    total_events = len(events)
    events_mentioned = sum(1 for event in events if event.get('title', '').lower() in summary_lower)
    event_coverage = events_mentioned / total_events if total_events > 0 else 0.0
    
    if event_coverage < 0.3:
        issues.append(f"Low event coverage: {event_coverage:.1%} (expected >= 30%)")
        score -= 0.2
    
    # Ensure minimum score
    score = max(0.0, score)
    
    return {
        "has_event_titles": has_event_titles,
        "has_event_times": has_event_times,
        "has_locations": has_locations,
        "has_attendees": has_attendees,
        "is_chronological": is_chronological,
        "event_coverage": event_coverage,
        "title_coverage": title_coverage,
        "issues": issues,
        "score": score
    }


def print_validation_results(results: Dict[str, Any], test_name: str):
    """Pretty print validation results."""
    print(f"\n{'='*80}")
    print(f"VALIDATION RESULTS: {test_name}")
    print(f"{'='*80}")
    
    score = results.get("score", 0.0)
    status = "✅ PASS" if score >= 0.7 else "⚠️  PARTIAL" if score >= 0.5 else "❌ FAIL"
    
    print(f"\n{status} (Score: {score:.1%})")
    
    if results.get("issues"):
        print(f"\nIssues Found:")
        for issue in results["issues"]:
            print(f"  • {issue}")
    
    # Print specific checks
    for key, value in results.items():
        if key not in ["score", "issues"] and isinstance(value, (bool, int, float, str)):
            check_status = "✅" if value else "❌"
            print(f"  {check_status} {key}: {value}")
    
    print()

