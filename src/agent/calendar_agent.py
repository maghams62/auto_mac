"""
Calendar Agent - Handles calendar event reading and meeting preparation.

This agent is responsible for:
- Reading upcoming calendar events
- Getting event details
- Generating meeting briefs by searching indexed documents

Acts as a mini-orchestrator for calendar-related operations.
"""

from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
import logging
from datetime import datetime, timedelta
import json
import os

from src.config import get_config_context
from src.utils import get_temperature_for_model

logger = logging.getLogger(__name__)


def _load_calendar_runtime():
    """
    Load config and calendar automation for calendar operations.

    Returns:
        Tuple of (config, calendar_automation)
    """
    context = get_config_context()
    config = context.data
    
    from ..automation.calendar_automation import CalendarAutomation
    calendar_automation = CalendarAutomation(config)
    
    return config, calendar_automation


@tool
def list_calendar_events(
    days_ahead: int = 7
) -> Dict[str, Any]:
    """
    List upcoming calendar events.

    CALENDAR AGENT - LEVEL 1: Event Reading
    Use this to retrieve upcoming calendar events.

    Args:
        days_ahead: Number of days to look ahead (default: 7, max: 30)

    Returns:
        Dictionary with:
        - events: List of event dictionaries (title, start_time, end_time, location, notes, attendees, calendar_name)
        - count: Number of events found
        - days_ahead: Number of days queried
    """
    logger.info(f"[CALENDAR AGENT] Tool: list_calendar_events(days_ahead={days_ahead})")

    try:
        config, calendar_automation = _load_calendar_runtime()
        
        # Limit days_ahead to reasonable maximum
        days_ahead = min(max(1, days_ahead), 30)
        
        events = calendar_automation.list_events(days_ahead=days_ahead)
        
        return {
            "events": events,
            "count": len(events),
            "days_ahead": days_ahead
        }

    except Exception as e:
        logger.error(f"[CALENDAR AGENT] Error in list_calendar_events: {e}")
        return {
            "error": True,
            "error_type": "CalendarReadError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def get_calendar_event_details(
    event_title: str,
    start_time_window: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get details for a specific calendar event by title.

    CALENDAR AGENT - LEVEL 1: Event Details
    Use this to retrieve detailed information about a specific event.

    Args:
        event_title: Title/summary of the event to find (partial match supported)
        start_time_window: Optional ISO format datetime string to narrow search window
                          (e.g., "2024-12-20T14:00:00"). If provided, searches within 24 hours of this time.

    Returns:
        Dictionary with:
        - event: Event dictionary (title, start_time, end_time, location, notes, attendees, calendar_name, event_id)
        - found: Boolean indicating if event was found
    """
    logger.info(f"[CALENDAR AGENT] Tool: get_calendar_event_details(event_title='{event_title}', start_time_window={start_time_window})")

    try:
        config, calendar_automation = _load_calendar_runtime()
        
        # Parse start_time_window if provided
        time_window_dt = None
        if start_time_window:
            try:
                time_window_dt = datetime.fromisoformat(start_time_window.replace('Z', '+00:00'))
            except Exception as e:
                logger.warning(f"Could not parse start_time_window '{start_time_window}': {e}")
        
        event = calendar_automation.get_event_details(
            event_title=event_title,
            start_time_window=time_window_dt
        )
        
        if event:
            return {
                "event": event,
                "found": True
            }
        else:
            return {
                "event": {},
                "found": False,
                "message": f"Event '{event_title}' not found"
            }

    except Exception as e:
        logger.error(f"[CALENDAR AGENT] Error in get_calendar_event_details: {e}")
        return {
            "error": True,
            "error_type": "CalendarReadError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def prepare_meeting_brief(
    event_title: str,
    start_time_window: Optional[str] = None,
    save_to_note: bool = False
) -> Dict[str, Any]:
    """
    Generate a meeting brief by searching indexed documents for relevant information.

    CALENDAR AGENT - LEVEL 2: Meeting Preparation
    Use this to prepare for a meeting by finding relevant documents and generating a brief.

    This tool:
    1. Fetches event details (title, notes, attendees, location)
    2. Uses LLM to generate semantic search queries from event metadata
    3. Searches indexed documents using those queries
    4. Synthesizes a meeting brief with relevant documents and talking points
    5. Optionally saves the brief to Apple Notes

    Args:
        event_title: Title/summary of the event to prepare for
        start_time_window: Optional ISO format datetime string to narrow event search
        save_to_note: If True, save the brief to Apple Notes (default: False)

    Returns:
        Dictionary with:
        - brief: Generated meeting brief text
        - event: Event details dictionary
        - relevant_docs: List of relevant documents found (file_path, file_name, similarity)
        - talking_points: List of key talking points extracted from documents
        - note_saved: Boolean indicating if brief was saved to note
        - search_queries: List of search queries used
    """
    logger.info(f"[CALENDAR AGENT] Tool: prepare_meeting_brief(event_title='{event_title}', save_to_note={save_to_note})")

    try:
        from openai import OpenAI
        from ..documents.indexer import DocumentIndexer
        from ..documents.search import SemanticSearch

        config, calendar_automation = _load_calendar_runtime()

        # Step 1: Get event details
        time_window_dt = None
        if start_time_window:
            try:
                time_window_dt = datetime.fromisoformat(start_time_window.replace('Z', '+00:00'))
            except Exception:
                pass

        event = calendar_automation.get_event_details(
            event_title=event_title,
            start_time_window=time_window_dt
        )

        if not event:
            return {
                "error": True,
                "error_type": "EventNotFound",
                "error_message": f"Event '{event_title}' not found",
                "retry_possible": False
            }

        # Step 2: Export event context for LLM
        event_context = calendar_automation.export_event_context(event)

        # Step 3: Generate search queries using LLM
        openai_config = config.get("openai", {})
        client = OpenAI(api_key=openai_config.get("api_key"))

        query_prompt = f"""Given this calendar event, generate 3-5 semantic search queries to find relevant documents for preparing a meeting brief.

Event Details:
- Title: {event_context.get('title', '')}
- Notes: {event_context.get('notes', '')}
- Attendees: {', '.join(event_context.get('attendees', []))}
- Location: {event_context.get('location', '')}
- Time: {event_context.get('start_time', '')}

Generate search queries that would help find:
- Documents related to the meeting topic
- Background information about attendees or projects mentioned
- Relevant reports, notes, or materials for this meeting

Return ONLY a JSON array of query strings, no other text.
Example: ["Q4 revenue report", "marketing strategy 2024", "quarterly financials"]
"""

        query_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates semantic search queries from calendar event information."},
                {"role": "user", "content": query_prompt}
            ],
            temperature=get_temperature_for_model(config, default_temperature=0.3),
            max_tokens=200
        )

        query_text = query_response.choices[0].message.content.strip()
        # Extract JSON array from response
        try:
            # Remove markdown code blocks if present
            if "```" in query_text:
                query_text = query_text.split("```")[1]
                if query_text.startswith("json"):
                    query_text = query_text[4:]
                query_text = query_text.strip()
            
            search_queries = json.loads(query_text)
            if not isinstance(search_queries, list):
                search_queries = [str(search_queries)]
        except Exception as e:
            logger.warning(f"Could not parse LLM query response as JSON: {e}. Using fallback queries.")
            # Fallback: extract queries from text
            search_queries = [event_context.get('title', ''), event_context.get('notes', '')]
            search_queries = [q for q in search_queries if q]

        logger.info(f"[CALENDAR AGENT] Generated {len(search_queries)} search queries: {search_queries}")

        # Step 4: Search documents using SemanticSearch
        try:
            indexer = DocumentIndexer(config)
            
            # Ensure index has content
            if indexer.index is None or getattr(indexer.index, "ntotal", 0) == 0:
                logger.info("[CALENDAR AGENT] Document index empty – indexing configured folders")
                indexed_files = indexer.index_documents()
                if indexed_files == 0:
                    return {
                        "error": True,
                        "error_type": "NoDocumentsIndexed",
                        "error_message": "No documents are indexed. Please index documents first.",
                        "retry_possible": False
                    }

            search_engine = SemanticSearch(indexer, config)
            
            # Search with each query and aggregate results
            all_results = []
            seen_files = set()
            
            for query in search_queries:
                if not query or not query.strip():
                    continue
                    
                results = search_engine.search(query, top_k=5)
                for result in results:
                    file_path = result.get('file_path', '')
                    if file_path and file_path not in seen_files:
                        seen_files.add(file_path)
                        all_results.append(result)
            
            # Sort by similarity score
            all_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
            
            # Take top 10 unique documents
            relevant_docs = all_results[:10]
            
        except Exception as e:
            logger.error(f"[CALENDAR AGENT] Error searching documents: {e}")
            relevant_docs = []

        # Step 5: Generate brief using Writing Agent or direct LLM call
        try:
            # Try to use Writing Agent's synthesize_content
            from .writing_agent import synthesize_content
            
            # Prepare source contents from relevant documents
            source_contents = []
            for doc in relevant_docs[:5]:  # Use top 5 docs for synthesis
                content_preview = doc.get('content_preview', '')
                file_name = doc.get('file_name', '')
                source_contents.append(f"Document: {file_name}\n{content_preview}")
            
            if source_contents:
                synthesis_result = synthesize_content.invoke({
                    "source_contents": source_contents,
                    "topic": f"Meeting brief for: {event_context.get('title', '')}",
                    "synthesis_style": "brief"
                })
                brief_text = synthesis_result.get("synthesized_content", "")
            else:
                brief_text = f"Meeting: {event_context.get('title', '')}\n\nNo relevant documents found in indexed files."
        except Exception as e:
            logger.warning(f"[CALENDAR AGENT] Could not use Writing Agent, using direct LLM call: {e}")
            # Fallback: Direct LLM call
            brief_prompt = f"""Create a concise meeting brief for this calendar event:

Event: {event_context.get('title', '')}
Time: {event_context.get('start_time', '')}
Location: {event_context.get('location', '')}
Attendees: {', '.join(event_context.get('attendees', []))}
Notes: {event_context.get('notes', '')}

Relevant Documents Found:
{chr(10).join([f"- {doc.get('file_name', '')} (relevance: {doc.get('similarity', 0):.2f})" for doc in relevant_docs[:5]])}

Create a brief that includes:
1. Meeting overview
2. Key talking points based on relevant documents
3. Recommended pre-reading (list document names)
4. Action items or questions to discuss

Keep it concise and actionable."""

            brief_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates meeting briefs."},
                    {"role": "user", "content": brief_prompt}
                ],
                temperature=get_temperature_for_model(config, default_temperature=0.3),
                max_tokens=1000
            )
            brief_text = brief_response.choices[0].message.content.strip()

        # Extract talking points (simple extraction from brief)
        talking_points = []
        for line in brief_text.split('\n'):
            line = line.strip()
            if line and (line.startswith('-') or line.startswith('•') or line.startswith('*')):
                talking_points.append(line.lstrip('-•* ').strip())

        # Step 6: Optionally save to note
        note_saved = False
        if save_to_note:
            try:
                from .notes_agent import create_note
                note_result = create_note.invoke({
                    "title": f"Meeting Brief: {event_context.get('title', '')}",
                    "body": brief_text,
                    "folder": "Notes"
                })
                note_saved = note_result.get("success", False)
            except Exception as e:
                logger.warning(f"[CALENDAR AGENT] Could not save to note: {e}")

        return {
            "brief": brief_text,
            "event": event,
            "relevant_docs": [
                {
                    "file_path": doc.get('file_path', ''),
                    "file_name": doc.get('file_name', ''),
                    "similarity": doc.get('similarity', 0)
                }
                for doc in relevant_docs
            ],
            "talking_points": talking_points[:10],  # Limit to top 10
            "note_saved": note_saved,
            "search_queries": search_queries
        }

    except Exception as e:
        logger.error(f"[CALENDAR AGENT] Error in prepare_meeting_brief: {e}")
        return {
            "error": True,
            "error_type": "BriefGenerationError",
            "error_message": str(e),
            "retry_possible": False
        }


# Calendar Agent Tool Registry
CALENDAR_AGENT_TOOLS = [
    list_calendar_events,
    get_calendar_event_details,
    prepare_meeting_brief,
]


# Calendar Agent Hierarchy
CALENDAR_AGENT_HIERARCHY = """
Calendar Agent Hierarchy:
=========================

LEVEL 1: Event Reading
├─ list_calendar_events → Retrieve upcoming calendar events
└─ get_calendar_event_details → Get details for a specific event

LEVEL 2: Meeting Preparation
└─ prepare_meeting_brief → Generate meeting brief by searching indexed documents
   ├─ Fetches event details from Calendar.app
   ├─ Uses LLM to generate semantic search queries from event metadata
   ├─ Searches indexed documents using DocumentIndexer/SemanticSearch
   ├─ Synthesizes brief using Writing Agent or direct LLM call
   └─ Optionally saves brief to Apple Notes

Domain: Calendar event reading and meeting preparation via macOS Calendar.app

Typical Workflows:

1. List upcoming events:
   list_calendar_events(days_ahead=7)
   Example: "show my upcoming events"

2. Get event details:
   get_calendar_event_details(event_title="Q4 Review")
   Example: "get details for Q4 Review meeting"

3. Prepare meeting brief:
   prepare_meeting_brief(event_title="Q4 Review", save_to_note=True)
   Example: "prepare a brief for Q4 Review meeting"
   Example: "/calendar prep for Team Standup"

Integration Patterns:
- Uses CalendarAutomation for reading events via AppleScript
- Uses DocumentIndexer/SemanticSearch for finding relevant documents
- Uses Writing Agent for brief synthesis
- Can save briefs to Notes Agent for persistence
- LLM-driven query generation (no hard-coded keywords)
"""


class CalendarAgent:
    """
    Calendar Agent - Mini-orchestrator for calendar operations.

    Responsibilities:
    - Reading calendar events
    - Getting event details
    - Generating meeting briefs
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in CALENDAR_AGENT_TOOLS}
        logger.info(f"[CALENDAR AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        """Get all calendar agent tools."""
        return CALENDAR_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get calendar agent hierarchy documentation."""
        return CALENDAR_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a calendar agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Calendar agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[CALENDAR AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[CALENDAR AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }

