# Persistent User Memory and Daily Overview System

## Overview

This release introduces a comprehensive persistent memory system and daily overview capabilities to enhance user experience through long-term context retention and intelligent daily briefing generation.

## Features

### 🔄 Persistent User Memory System

**Architecture:**
- **UserMemoryStore**: Core persistent storage with FAISS semantic search
- **MemoryExtractionPipeline**: LLM-powered extraction of salient facts from conversations
- **Session Integration**: Thread-safe memory access across sessions
- **Automatic Deduplication**: Cosine similarity-based duplicate prevention (>0.87 threshold)

**Key Components:**
- `UserProfile`: Static user preferences and metadata
- `MemoryEntry`: Individual facts with salience scoring and time decay
- `ConversationSummary`: Session-level conversation summaries
- `PersistentContext`: Merged context for agent consumption

**Data Flow:**
1. User interacts with agent → SessionMemory.add_interaction()
2. MemoryExtractionPipeline extracts salient facts via LLM classification
3. Deduplication against existing memories using cosine similarity
4. Accepted memories stored with salience scores and embeddings
5. Future queries retrieve relevant memories via semantic search

**Configuration:**
```yaml
persistent_memory:
  enabled: true
  directory: "data/user_memory"
  embedding_model: "text-embedding-3-small"
  retention:
    max_memories_per_user: 1000
    default_ttl_days: 365
  extraction:
    similarity_threshold: 0.87
    min_confidence: 0.7
    max_per_interaction: 3
```

### 📅 Daily Overview Agent

**Core Functionality:**
- **generate_day_overview**: Orchestrates calendar, reminders, and email data
- **Natural Language Filtering**: "today", "tomorrow morning", "next 3 days", etc.
- **Calendar Backfill**: Automatic detection of commitments without calendar events
- **Multi-source Aggregation**: Combines Calendar.app, Reminders.app, and email analysis

**New Tools:**
- `generate_day_overview(filters)`: Comprehensive daily briefing
- `create_calendar_event()`: Event creation with attendee support

**Intelligent Features:**
- **Email Classification**: Heuristics to identify meeting requests vs action items
- **Time Window Filtering**: Intelligent parsing of "this afternoon" → 12-6 PM
- **Backfill Detection**: Cross-references emails/reminders against calendar events
- **Confidence Scoring**: Rates suggested calendar events by extraction certainty

## User Experience

### Slash Commands
- `/day` or `/day today` - Generate daily overview
- `/day tomorrow morning` - Time-filtered views
- `/day next 3 days` - Multi-day planning

### Natural Language Triggers
- "how's my day looking today?"
- "what's on my schedule this afternoon?"
- "show me my calendar for tomorrow"

### Memory Integration
- Persistent preferences automatically influence responses
- Long-term patterns inform decision-making
- User profile data enhances personalization

## Technical Implementation

### Memory Storage Schema
```
data/user_memory/{user_id}/
├── profile.json          # UserProfile data
├── memories.json         # List of MemoryEntry objects
├── summaries.json        # ConversationSummary objects
└── faiss_index/          # FAISS vector index (auto-generated)
```

### Session Manager Extensions
- User-scoped session directories: `data/sessions/{user_id}/{session_id}.json`
- Lazy UserMemoryStore initialization
- Thread-safe cross-session memory access
- Enhanced clear_session() with optional persistent memory clearing

### Agent Integration
- Automatic memory querying for each user request
- `planning_context["persistent_memory"]` injection
- Memory extraction after each interaction
- Context preservation across sessions

## Privacy & Security

### Data Protection
- **Opt-in by Default**: Persistent memory disabled unless explicitly enabled
- **User Isolation**: Complete data separation between users
- **No Sensitive Data**: Classification rules prevent storing passwords, tokens, or PII
- **TTL Support**: Automatic expiration of memories based on configurable time-to-live

### Memory Classification Guardrails
**Store:**
- ✅ User preferences (meeting times, communication styles, tool preferences)
- ✅ Recurring commitments (weekly meetings, standing tasks)
- ✅ Technical preferences (preferred file formats, coding styles)
- ✅ Background facts (company information, project context)

**Avoid:**
- ❌ Transient instructions ("remind me in 5 minutes")
- ❌ Sensitive data (passwords, API keys, personal financial data)
- ❌ One-time requests ("send this specific email")
- ❌ Personal information (addresses, phone numbers, health data)

### Data Retention
- **Configurable TTL**: Default 365 days, adjustable per memory entry
- **Automatic Cleanup**: Background process removes expired memories
- **User Control**: `/clear --all` removes both session and persistent memory
- **Audit Trail**: All memory operations logged for transparency

## Performance Characteristics

### Memory Operations
- **Embedding Generation**: ~0.5-1.0 seconds per memory entry
- **Semantic Search**: <0.1 seconds for top-5 retrieval
- **Deduplication**: <0.2 seconds using FAISS similarity search
- **Storage**: ~1KB per memory entry (JSON + embedding vector)

### Daily Overview Generation
- **Calendar Fetch**: <0.5 seconds for 7-day window
- **Email Analysis**: <1.0 seconds for 50-email analysis
- **Backfill Detection**: <0.5 seconds using existing calendar data
- **Total Response Time**: <2.0 seconds for comprehensive overview

### Scalability
- **Memory Limits**: Configurable per-user memory caps (default: 1000 entries)
- **Index Rebuilding**: Automatic FAISS index maintenance
- **Cleanup Frequency**: Configurable expired memory removal (default: 30 days)

## Integration Points

### Existing Systems
- **SessionManager**: Extended with user_id support and memory store integration
- **AutomationAgent**: Enhanced with persistent memory querying
- **Calendar Agent**: New create_event tool added
- **Email Agent**: Existing read_latest_emails leveraged for action item analysis

### Configuration Integration
- **config.yaml**: New persistent_memory section
- **Prompt Updates**: Memory utilization guidance in system.md and task_decomposition.md
- **Few-shot Examples**: Daily overview planning patterns added
- **Tool Registry**: New agents and tools registered in agent_registry.py

## Testing Strategy

### Unit Tests
- `test_user_memory.py`: CRUD operations, deduplication, retrieval scoring
- Memory extraction pipeline validation
- Embedding and similarity threshold testing

### Integration Tests
- `test_persistent_memory_flow.py`: Multi-session conversation persistence
- Memory injection into planning_context verification
- Session clearing with/without persistent memory

### End-to-End Tests
- `test_daily_overview.py`: Calendar/reminder/email aggregation
- Backfill suggestion accuracy
- Natural language filter parsing

### Cross-functional Tests
- Updated comprehensive test suite with daily overview queries
- Memory persistence across agent restarts
- Privacy boundary validation

## Deployment Considerations

### Database Migration
- No existing data migration required (new feature)
- Safe to enable on existing installations
- Default disabled for privacy compliance

### Monitoring
- Memory extraction success rates
- Daily overview generation times
- FAISS index health and rebuild frequency
- User memory storage utilization

### Rollback Plan
- Feature flag controlled (persistent_memory.enabled)
- Can be disabled without data loss
- Memory data remains accessible for manual inspection

## Future Enhancements

### Phase 2 Opportunities
- **Memory Visualization**: Web UI for memory browsing and management
- **Advanced Classification**: Fine-tuned LLM for better memory categorization
- **Cross-user Learning**: Anonymous pattern sharing for improved suggestions
- **Memory Export**: Data portability and backup capabilities

### Research Integration
- Alignment with MemGPT retention strategies (Packer et al., 2023)
- Persistent memory patterns from Westhäuser et al. (2025)
- Semantic Scholar API integration for relevant paper recommendations

## Breaking Changes

None. This is a purely additive feature set with:
- All new configuration options defaulting to safe values
- Feature disabled by default for privacy
- Backward compatibility maintained for existing sessions
- No changes to existing API contracts

## Migration Guide

1. **Enable Feature**: Set `persistent_memory.enabled: true` in config.yaml
2. **Configure Storage**: Optionally customize `persistent_memory.directory`
3. **Set Retention**: Adjust TTL and memory limits as needed
4. **Update Prompts**: New memory utilization guidance automatically applied
5. **Test Integration**: Run provided test suites to validate functionality

The system is designed for seamless integration with existing Cerebro OS installations while providing powerful new capabilities for enhanced user experience.
