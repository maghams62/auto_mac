# Command-K Universal Search Implementation Plan

## Overview
Implement a Raycast-inspired Command-K universal search feature for semantic document search with inline preview and open-in-app functionality.

## Scope & UX Goals

### Command Palette Features
- **Activation**: ⌘K (macOS) / Ctrl+K (Windows) global shortcut
- **Search Scope**: Limited to indexed folders from `config.yaml` (MVP: `tests/data/test_docs`)
- **Live Results**: Streaming semantic search results while typing
- **Result Display**: Highlight best match, show similarity score, file type, and preview snippet
- **Modal Design**: Glassmorphism overlay with scale+fade entrance, per-result hover/selection glow
- **Keyboard Navigation**: ↑/↓ arrow keys, Enter to open, Esc to close

### Preview & Open Functionality
- **Inline Preview**: Space key or click toggles Quick Look panel with document rendering
- **Open in App**: Enter key loads full document in chat side panel (reuse existing viewer)
- **Secondary Action**: ⌘↩ to open in system default app (Finder/Desktop)
- **Highlighting**: Live word highlighting as query changes (Raycast-style)

## Backend Enhancements

### New API Endpoint: `/api/universal-search`
```python
@app.get("/api/universal-search")
async def universal_search(q: str, limit: int = 10):
    """Universal semantic search with snippets and highlights"""
```

**Request Parameters:**
- `q`: Search query string (required)
- `limit`: Maximum results (optional, default: 10)

**Response Format:**
```json
{
  "query": "machine learning",
  "count": 5,
  "results": [
    {
      "file_path": "/path/to/document.pdf",
      "file_name": "ML_Algorithms.pdf",
      "file_type": "pdf",
      "page_number": 3,
      "total_pages": 25,
      "similarity_score": 0.87,
      "snippet": "Machine learning algorithms can be...",
      "highlight_offsets": [[10, 25], [45, 58]], // character offsets for highlighting
      "breadcrumb": "Research/ML_Algorithms.pdf"
    }
  ]
}
```

### Backend Implementation Details

#### Search Logic
- Reuse existing `SemanticSearch.search_and_group()` method
- Add snippet extraction with query term highlighting
- Include character offset ranges for frontend highlighting
- Support multi-page documents with page-specific results

#### Performance Optimizations
- **Pre-load FAISS Index**: Load index on startup for <150ms response times
- **Query Memoization**: Cache frequent queries with TTL
- **Debounced Requests**: 200ms debounce on frontend prevents excessive API calls
- **Background Indexing**: Auto-refresh index based on `config.yaml` `refresh_interval`

#### Security & Validation
- Reject empty queries with 400 status
- Rate limiting: Max 10 requests/second per client
- Path validation: Only return results from whitelisted `documents.folders`
- Input sanitization: Strip HTML/script tags from queries

#### Highlighting Strategy
- Backend extracts relevant text chunks with query terms
- Returns character offset ranges for semantic matches
- Fallback to LLM entity extraction when confidence < threshold
- Multi-page support: Include page numbers in results

## Frontend Architecture

### New Component: `CommandPalette.tsx`
**Location**: `frontend/components/CommandPalette.tsx`

**State Management:**
```typescript
interface CommandPaletteState {
  isOpen: boolean;
  query: string;
  results: SearchResult[];
  selectedIndex: number;
  isLoading: boolean;
  previewMode: 'closed' | 'loading' | 'previewing';
  previewData: PreviewData | null;
}
```

**Key Features:**
- Controlled modal with internal state management
- SWR/react-query integration with 200ms debounce
- Framer Motion animations for entrance/exit
- Keyboard event handling with focus trap

### Global Keyboard Handler
**Integration Point**: `frontend/app/layout.tsx` or global context

```typescript
useEffect(() => {
  const handleGlobalKeyDown = (e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      setCommandPaletteOpen(true);
    }
  };

  document.addEventListener('keydown', handleGlobalKeyDown);
  return () => document.removeEventListener('keydown', handleGlobalKeyDown);
}, []);
```

### Search Result Item Component
**Features:**
- File type icon (PDF/doc/txt)
- Title with breadcrumb path
- Short snippet with `<mark>` highlighting
- Similarity score badge
- Page number indicator for multi-page docs
- Hover and selection states with glow effects

### Document Preview Integration
**Reuse Strategy**: Extend existing `DocumentPreviewModal` or create `DocumentViewerContext`

**Preview States:**
1. **Closed**: Standard result list
2. **Loading**: Spinner while fetching preview
3. **Previewing**: Side panel with rendered document

**Quick Preview Toggle:**
- Space key: Toggle preview panel
- Click result: Open preview
- Maintain keyboard navigation in both modes

### Highlighting Implementation
**Live Updates**: As query changes, re-highlight existing results
**Mark Elements**: Wrap matched spans in `<mark>` with animated underline
**Preview Sync**: Same highlighting data applied to preview panel

## Semantic Highlighting Strategy

### Backend Snippet Generation
```python
def generate_highlighted_snippet(content: str, query: str) -> tuple[str, list[list[int]]]:
    """Generate snippet with highlight offsets"""
    # Extract relevant chunk containing query terms
    # Return (snippet_text, [[start, end], ...])
```

### Frontend Highlighting
```typescript
function HighlightedText({
  text,
  highlights
}: {
  text: string;
  highlights: [number, number][]
}) {
  // Split text and wrap highlighted ranges in <mark>
}
```

### Multi-Page Support
- Show "Page X" badges in results
- Allow stepping through matches with keyboard shortcuts
- Scroll to highlighted section in preview

## Testing & Telemetry

### Backend Unit Tests (`tests/test_universal_search.py`)
```python
def test_universal_search_empty_query():
    # Should return 400 status

def test_universal_search_single_result():
    # Verify result structure and highlighting

def test_universal_search_semantic_fuzzy():
    # Test fuzzy matching and scoring
```

### Frontend Tests (`frontend/components/__tests__/CommandPalette.test.tsx`)
```typescript
describe('CommandPalette', () => {
  it('opens on Cmd+K', () => { ... });
  it('navigates with arrow keys', () => { ... });
  it('selects result on Enter', () => { ... });
  it('highlights query terms', () => { ... });
});
```

### E2E Tests (Cypress)
```typescript
describe('Universal Search', () => {
  it('searches and previews document', () => {
    cy.pressCmdK();
    cy.typeQuery('machine learning');
    cy.verifyResults();
    cy.pressEnter();
    cy.verifyPreviewOpens();
  });
});
```

### Analytics Instrumentation
```typescript
// Track search interactions
analytics.track('universal_search_query', {
  query: query,
  result_count: results.length,
  selected_index: selectedIndex,
  latency_ms: responseTime
});

// Track result selections
analytics.track('universal_search_select', {
  query: query,
  selected_file: result.file_path,
  rank: selectedIndex + 1
});
```

## Animations & UX Polish

### Modal Entrance Animation
```typescript
const modalVariants = {
  hidden: { opacity: 0, scale: 0.96, y: 20 },
  visible: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: {
      duration: 0.2,
      ease: [0.25, 0.1, 0.25, 1]
    }
  },
  exit: {
    opacity: 0,
    scale: 0.96,
    y: 20,
    transition: { duration: 0.15 }
  }
};
```

### Result List Animations
- Staggered fade/slide for first 5 results
- Pulse border on selection
- Smooth hover transitions with backdrop blur

### Loading States
- Shimmer effect for results while loading
- Optimistic UI updates
- Smooth transitions between states

### Accessibility
- ARIA roles: `role="dialog"` for modal
- Focus trap implementation
- Screen reader announcements for result navigation
- High contrast mode support

## Rollout Steps

### Phase 1: Backend Foundation
1. Add `/api/universal-search` endpoint
2. Implement snippet generation with highlighting
3. Add rate limiting and security guards
4. Write backend unit tests
5. Update config validation

### Phase 2: Frontend Core
1. Create `CommandPalette` component skeleton
2. Implement global keyboard handler
3. Add basic search API integration
4. Implement keyboard navigation
5. Add loading states and error handling

### Phase 3: Preview Integration
1. Wire document preview panel
2. Implement highlighting system
3. Add Space key quick preview
4. Integrate with existing document viewer
5. Test multi-page document support

### Phase 4: UX Polish & Testing
1. Add framer-motion animations
2. Implement accessibility features
3. Write comprehensive test suite
4. Performance optimization
5. Telemetry implementation

### Phase 5: Production Rollout
1. QA with real indexed documents
2. Config documentation updates
3. User acceptance testing
4. Production deployment
5. Monitor analytics and performance

## Documentation & Config

### Config Updates (`config.yaml`)
```yaml
universal_search:
  enabled: true  # Feature flag
  max_results: 10  # Default result limit
  debounce_ms: 200  # Frontend debounce delay
  highlight_context: 100  # Characters around highlights
  security:
    rate_limit_per_second: 10
    allowed_paths_only: true
```

### Documentation Updates
**File**: `docs/MASTER_AGENT_GUIDE.md`
```
## Universal Search (⌘K)

Press ⌘K (Ctrl+K on Windows) to open universal search. Search through all indexed documents using natural language queries.

**Features:**
- Semantic search with fuzzy matching
- Live preview with highlighting
- Open documents directly in the app
- Keyboard navigation and shortcuts

**Indexed Folders:** Configured in `config.yaml` under `documents.folders`
```

### Troubleshooting Section
**File**: `docs/troubleshooting.md`
```
## Universal Search Issues

### No search results
- Check that documents are indexed: Run `/reindex` command
- Verify folder permissions in `config.yaml`
- Check FAISS index exists in `data/embeddings/`

### Slow search performance
- Increase `refresh_interval` in config
- Check system resources (RAM for FAISS index)
- Verify embedding model is loaded

### Highlighting not working
- Backend may not be returning highlight offsets
- Check for LLM fallback in logs
- Verify document text extraction is working
```

## Claude Implementation Instructions

### Component Structure Guidelines
```
CommandPalette/
├── CommandPalette.tsx          # Main modal component
├── SearchResult.tsx           # Individual result item
├── SearchInput.tsx            # Search input with highlighting
├── PreviewPanel.tsx           # Side preview panel
└── hooks/
    ├── useCommandPalette.ts   # State management hook
    └── useSearch.ts          # Search API hook
```

### Key Implementation Notes
1. **Always supply both list and preview states** - Keep result list visible when preview is open
2. **Highlight query substring in results** - Use `<mark>` elements for semantic matches
3. **Sync highlighting between list and preview** - Same highlight data applied to both
4. **Hook Enter key to load in app viewer** - Dispatch to DocumentViewerContext
5. **Expose Open Externally as secondary action** - ⌘↩ to open in system default
6. **Maintain keyboard focus trap** - Users should navigate without leaving modal
7. **Handle loading states gracefully** - Show optimistic results while searching

### State Machine Pattern
```typescript
type PaletteState =
  | { mode: 'searching' }
  | { mode: 'previewing'; result: SearchResult }
  | { mode: 'opening'; result: SearchResult };

const [state, setState] = useState<PaletteState>({ mode: 'searching' });
```

### API Integration Pattern
```typescript
const { data, error, isLoading } = useSWR(
  query ? `/api/universal-search?q=${encodeURIComponent(query)}` : null,
  fetcher,
  {
    dedupingInterval: 200, // Debounce
    revalidateOnFocus: false
  }
);
```

This implementation plan provides a comprehensive roadmap for building a production-ready universal search feature that matches Raycast's functionality while integrating seamlessly with the existing Cerebro OS architecture.
