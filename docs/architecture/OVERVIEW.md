# Architecture Overview - Web UI

## System Diagram

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                      USER'S BROWSER                        ┃
┃  ┌──────────────────────────────────────────────────┐     ┃
┃  │  http://localhost:3000                            │     ┃
┃  │                                                   │     ┃
┃  │  ┌─────────────────────────────────────────┐     │     ┃
┃  │  │  Frontend (Next.js 14)                  │     │     ┃
┃  │  │  • React Components                     │     │     ┃
┃  │  │  • Tailwind CSS (glassmorphic theme)    │     │     ┃
┃  │  │  • Framer Motion (animations)           │     │     ┃
┃  │  │  • WebSocket client                     │     │     ┃
┃  │  └─────────────────────────────────────────┘     │     ┃
┃  │                                                   │     ┃
┃  │  Components:                                      │     ┃
┃  │  ├─ ChatInterface.tsx (main UI)                  │     ┃
┃  │  ├─ MessageBubble.tsx (messages)                 │     ┃
┃  │  ├─ InputArea.tsx (user input)                   │     ┃
┃  │  ├─ Header.tsx (navigation)                      │     ┃
┃  │  └─ TypingIndicator.tsx (loading)                │     ┃
┃  │                                                   │     ┃
┃  │  Hooks:                                           │     ┃
┃  │  └─ useWebSocket.ts (connection logic)           │     ┃
┃  └──────────────────────────────────────────────────┘     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                         │
                         │ WebSocket Connection
                         │ ws://localhost:8000/ws/chat
                         │
┏━━━━━━━━━━━━━━━━━━━━━━━▼━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃              BACKEND API SERVER (NEW)                      ┃
┃  ┌──────────────────────────────────────────────────┐     ┃
┃  │  api_server.py (FastAPI + Uvicorn)               │     ┃
┃  │                                                   │     ┃
┃  │  Endpoints:                                       │     ┃
┃  │  ├─ WS /ws/chat (real-time chat)                │     ┃
┃  │  ├─ GET /api/stats (system info)                │     ┃
┃  │  ├─ GET /api/agents (agent list)                │     ┃
┃  │  ├─ POST /api/chat (sync chat)                  │     ┃
┃  │  └─ POST /api/reindex (reindex docs)            │     ┃
┃  │                                                   │     ┃
┃  │  Features:                                        │     ┃
┃  │  • Connection manager                            │     ┃
┃  │  • Multiple clients support                      │     ┃
┃  │  • Async execution                               │     ┃
┃  │  • Error handling                                │     ┃
┃  │  • CORS configuration                            │     ┃
┃  └──────────────────────────────────────────────────┘     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                         │
                         │ Python Function Calls
                         │ agent.run(message)
                         │
┏━━━━━━━━━━━━━━━━━━━━━━━▼━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃           EXISTING MAC AUTOMATION SYSTEM                   ┃
┃  ┌──────────────────────────────────────────────────┐     ┃
┃  │  AutomationAgent (src/agent/agent.py)            │     ┃
┃  │                                                   │     ┃
┃  │  ┌────────────────────────────────────────┐      │     ┃
┃  │  │  LangGraph Orchestrator                │      │     ┃
┃  │  │  • Planning node                       │      │     ┃
┃  │  │  • Validation node                     │      │     ┃
┃  │  │  • Execution node                      │      │     ┃
┃  │  │  • Synthesis node                      │      │     ┃
┃  │  └────────────────────────────────────────┘      │     ┃
┃  │                                                   │     ┃
┃  │  ┌────────────────────────────────────────┐      │     ┃
┃  │  │  Agent Registry (12+ agents)           │      │     ┃
┃  │  │  ├─ FileAgent                          │      │     ┃
┃  │  │  ├─ BrowserAgent                       │      │     ┃
┃  │  │  ├─ StockAgent                         │      │     ┃
┃  │  │  ├─ MapsAgent                          │      │     ┃
┃  │  │  ├─ PresentationAgent                  │      │     ┃
┃  │  │  ├─ EmailAgent                         │      │     ┃
┃  │  │  ├─ WritingAgent                       │      │     ┃
┃  │  │  ├─ iMessageAgent                      │      │     ┃
┃  │  │  ├─ ScreenAgent                        │      │     ┃
┃  │  │  ├─ GoogleFinanceAgent                 │      │     ┃
┃  │  │  ├─ DiscordAgent                       │      │     ┃
┃  │  │  └─ RedditAgent                        │      │     ┃
┃  │  └────────────────────────────────────────┘      │     ┃
┃  │                                                   │     ┃
┃  │  ┌────────────────────────────────────────┐      │     ┃
┃  │  │  Document Processing (RAG)             │      │     ┃
┃  │  │  • FAISS vector search                 │      │     ┃
┃  │  │  • OpenAI embeddings                   │      │     ┃
┃  │  │  • PDF/DOCX extraction                 │      │     ┃
┃  │  └────────────────────────────────────────┘      │     ┃
┃  └──────────────────────────────────────────────────┘     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

---

## Message Flow

```
1. USER TYPES MESSAGE
   ├─ "Create a Keynote presentation about Tesla"
   └─ InputArea.tsx captures input

2. FRONTEND SENDS VIA WEBSOCKET
   ├─ useWebSocket.ts hook
   ├─ ws.send({message: "Create a..."})
   └─ Adds user message to UI immediately

3. BACKEND RECEIVES
   ├─ api_server.py /ws/chat endpoint
   ├─ Validates message
   ├─ Sends acknowledgment: {type: "status", status: "processing"}
   └─ Calls: result = agent.run(message)

4. AUTOMATION AGENT PROCESSES
   ├─ LangGraph Orchestrator
   │   ├─ Planning: LLM creates step-by-step plan
   │   ├─ Validation: Checks plan feasibility
   │   ├─ Execution: Runs each step
   │   └─ Synthesis: Combines results
   │
   └─ Agent Registry routes to:
       ├─ FileAgent: search_documents("Tesla")
       └─ PresentationAgent: create_keynote(content)

5. BACKEND SENDS RESULT
   ├─ ws.send({type: "response", message: "Created at /path/...", status: "completed"})
   └─ WebSocket streams result to frontend

6. FRONTEND DISPLAYS
   ├─ useWebSocket.ts receives message
   ├─ Adds assistant message to messages array
   ├─ MessageBubble.tsx renders result
   └─ Auto-scrolls to show new message
```

---

## Component Hierarchy

```
App (page.tsx)
│
├─── Header.tsx
│    └─── ConnectionStatus (inline)
│
└─── ChatInterface.tsx
     ├─── useWebSocket() hook
     │
     ├─── Welcome Screen (when no messages)
     │    └─── Feature Cards (4 cards)
     │
     ├─── Messages Area
     │    ├─── MessageBubble.tsx (for each message)
     │    │    ├─── User messages (right-aligned, cyan border)
     │    │    ├─── Assistant messages (left-aligned, white border)
     │    │    ├─── System messages (lime border)
     │    │    └─── Error messages (red border)
     │    │
     │    └─── TypingIndicator.tsx (when processing)
     │
     └─── InputArea.tsx
          ├─── Textarea (auto-resize)
          ├─── Send button (icon)
          └─── Example prompts (3 buttons)
```

---

## Data Flow

```
┌─────────────────┐
│  User Action    │
│  (type message) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  InputArea      │
│  onSend(msg)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  useWebSocket   │
│  sendMessage()  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐    ┌──────────────┐
│  WebSocket      │───▶│  Backend API │
│  Client         │◀───│  Server      │
└─────────────────┘    └──────┬───────┘
         │                     │
         │                     ▼
         │            ┌──────────────────┐
         │            │ AutomationAgent  │
         │            │ • Plans task     │
         │            │ • Executes steps │
         │            │ • Returns result │
         │            └──────────────────┘
         │
         ▼
┌─────────────────┐
│  ChatInterface  │
│  messages[]     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  MessageBubble  │
│  (displays msg) │
└─────────────────┘
```

---

## State Management

```
┌─────────────────────────────────────┐
│  Frontend State                     │
├─────────────────────────────────────┤
│  • messages: Message[]              │
│    ├─ type: user|assistant|system   │
│    ├─ message: string               │
│    ├─ timestamp: string             │
│    └─ status?: string               │
│                                     │
│  • isConnected: boolean             │
│  • wsRef: WebSocket                 │
│  • reconnectAttempts: number        │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  Backend State                      │
├─────────────────────────────────────┤
│  • active_connections: WebSocket[]  │
│  • agent: AutomationAgent           │
│  • config: Config                   │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  Agent State (existing)             │
├─────────────────────────────────────┤
│  • user_request: string             │
│  • goal: string                     │
│  • steps: List[Dict]                │
│  • current_step: int                │
│  • step_results: Dict               │
│  • final_result: Dict               │
│  • status: str                      │
└─────────────────────────────────────┘
```

---

## File Organization

```
auto_mac/
│
├── Backend (NEW)
│   └── api_server.py                 # FastAPI server
│
├── Frontend (NEW)
│   └── frontend/
│       ├── app/                      # Next.js pages
│       │   ├── page.tsx              # Main page
│       │   ├── layout.tsx            # Root layout
│       │   └── globals.css           # Global styles
│       │
│       ├── components/               # React components
│       │   ├── ChatInterface.tsx     # Main UI
│       │   ├── MessageBubble.tsx     # Messages
│       │   ├── InputArea.tsx         # Input
│       │   ├── Header.tsx            # Header
│       │   └── TypingIndicator.tsx   # Loading
│       │
│       ├── lib/                      # Utilities
│       │   ├── useWebSocket.ts       # WebSocket hook
│       │   └── utils.ts              # Helpers
│       │
│       └── [config files]            # TS, Tailwind, etc.
│
├── Existing System (UNCHANGED)
│   ├── src/
│   │   ├── agent/                    # All agents
│   │   │   ├── agent.py              # AutomationAgent
│   │   │   ├── agent_registry.py     # Registry
│   │   │   ├── file_agent.py         # File ops
│   │   │   ├── browser_agent.py      # Web ops
│   │   │   └── ... (10+ more)
│   │   │
│   │   ├── orchestrator/             # Planning
│   │   │   ├── planner.py            # Task planning
│   │   │   ├── executor.py           # Execution
│   │   │   └── orchestrator.py       # LangGraph
│   │   │
│   │   └── documents/                # RAG
│   │       └── indexer.py            # Document search
│   │
│   └── config.yaml                   # Configuration
│
└── Documentation (NEW)
    ├── START_HERE.md                 # Main entry
    ├── QUICK_START.md                # Quick guide
    ├── UI_README.md                  # User docs
    ├── NEW_UI_OVERVIEW.md            # Technical
    ├── IMPLEMENTATION_SUMMARY.md     # Details
    ├── FILES_CREATED.md              # File list
    ├── ARCHITECTURE.md               # This file
    └── DONE.md                       # Completion
```

---

## Technology Stack

```
┌─────────────────────────────────────────┐
│  FRONTEND                                │
├─────────────────────────────────────────┤
│  Framework:   Next.js 14                │
│  Library:     React 18                  │
│  Language:    TypeScript                │
│  Styling:     Tailwind CSS              │
│  Animations:  Framer Motion             │
│  Real-time:   WebSocket API             │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  BACKEND                                 │
├─────────────────────────────────────────┤
│  Framework:   FastAPI                   │
│  Server:      Uvicorn (ASGI)            │
│  Language:    Python 3.10+              │
│  Real-time:   WebSockets                │
│  Async:       asyncio                   │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  EXISTING SYSTEM                         │
├─────────────────────────────────────────┤
│  LLM:         OpenAI GPT-4o             │
│  Orchestr:    LangGraph                 │
│  Embeddings:  OpenAI + FAISS            │
│  Docs:        PyPDF2, pdfplumber        │
│  Browser:     Playwright                │
│  macOS:       AppleScript, pyobjc       │
└─────────────────────────────────────────┘
```

---

## Network Protocol

```
CLIENT                          SERVER
  │                               │
  │  WS: ws://localhost:8000/ws/chat
  │  ─────────────────────────►   │
  │                               │
  │  {type: "connect"}            │
  │  ◄─────────────────────────   │
  │  {type: "system", message: "Connected"}
  │                               │
  │  {message: "Your request"}    │
  │  ─────────────────────────►   │
  │                               │
  │  {type: "status", status: "processing"}
  │  ◄─────────────────────────   │
  │                               │
  │         [Processing...]       │
  │                               │
  │  {type: "response", message: "Result", status: "completed"}
  │  ◄─────────────────────────   │
  │                               │
  │  [Connection maintained]      │
  │  ◄────────────────────────►   │
  │                               │
```

---

## Error Handling

```
┌─────────────────────────────────────────┐
│  Error Handling Layers                  │
├─────────────────────────────────────────┤
│                                         │
│  1. Frontend (useWebSocket.ts)          │
│     ├─ Connection errors                │
│     ├─ Auto-reconnect (exp backoff)     │
│     ├─ Message parsing errors           │
│     └─ Display error messages           │
│                                         │
│  2. Backend (api_server.py)             │
│     ├─ WebSocket errors                 │
│     ├─ Message validation               │
│     ├─ Agent execution errors           │
│     └─ Send error to client             │
│                                         │
│  3. Agent (existing)                    │
│     ├─ Plan validation                  │
│     ├─ Step-level try-catch             │
│     ├─ Replanning on failure            │
│     └─ User feedback                    │
│                                         │
└─────────────────────────────────────────┘
```

---

## Summary

This architecture provides:

✅ **Clean separation** - UI, API, and business logic separated
✅ **Real-time communication** - WebSocket for instant feedback
✅ **Scalable** - Can handle multiple clients
✅ **Maintainable** - Each layer has clear responsibilities
✅ **Extensible** - Easy to add features
✅ **Backwards compatible** - No changes to existing system

The UI is a **pure addition** on top of your existing system!
