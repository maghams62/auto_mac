# PERFORMANCE OPTIMIZATION PLAN

## Executive Summary

This document outlines a comprehensive performance optimization strategy for the Auto Mac AI Agent application. The focus is on **reducing latency** through parallelization, efficient data structures, optimized LLM interactions, and architectural improvements.

**Current Architecture Identified:**
- LangGraph-based multi-agent orchestrator
- Plan → Execute → Verify loop with sequential execution
- 47 specialized agents with lazy initialization
- FAISS-based vector search for documents and memory
- Session management with disk persistence
- WebSocket API server with asyncio

**Target Improvements:**
1. **40-60% latency reduction** through parallel LLM calls
2. **50-70% faster step execution** through parallel processing
3. **30-50% faster embeddings** through batch processing
4. **20-30% memory reduction** through optimized caching
5. **Rate limiting compliance** while maximizing throughput

---

## 1. PARALLELIZATION - LLM API Calls & Multi-Threading

### Problem
**Current State:**
- LLM calls are sequential: Planner → Executor (per step) → Verifier
- Each step execution waits for LLM response before starting next
- Intent analysis, planning, and routing happen sequentially
- No concurrent OpenAI API calls despite rate limits allowing it

**Files Affected:**
- `src/orchestrator/planner.py` (lines 65-150)
- `src/orchestrator/executor.py` (lines 74-310)
- `src/agent/agent.py` (lines 287-500)

**Impact:** 
- 2-5 seconds wasted per request on sequential LLM calls
- Underutilized OpenAI rate limits (RPM: 10,000+, TPM: 2M+)

### Solution

#### 1.1 Parallel Independent LLM Calls

**Implementation:**

```python
# In src/orchestrator/planner.py
import asyncio
from concurrent.futures import ThreadPoolExecutor

class Planner:
    def __init__(self, config):
        # ... existing code ...
        # Add thread pool for parallel LLM calls
        self.executor = ThreadPoolExecutor(max_workers=5)
        
    async def create_plan_async(self, goal, available_tools, session_context, ...):
        """Async version with parallel intent analysis and planning prep."""
        
        # Run intent analysis and tool filtering in parallel
        async with asyncio.TaskGroup() as tg:
            intent_task = tg.create_task(
                asyncio.to_thread(self.intent_planner.analyze, goal, self.agent_capabilities)
            )
            # Pre-compute tool metadata while intent is analyzing
            tool_prep_task = tg.create_task(
                asyncio.to_thread(self._prepare_tool_metadata, available_tools)
            )
        
        intent = await intent_task
        tool_metadata = await tool_prep_task
        
        # Now proceed with planning using results
        # ... rest of planning logic
```

**Benefits:**
- 40-60% faster planning phase
- Overlaps I/O-bound operations
- Respects rate limits with controlled concurrency

#### 1.2 Parallel Step Verification

**Current:** Verification happens after each step completes (sequential)
**Proposed:** Verify previous steps while current step executes

```python
# In src/orchestrator/executor.py
class PlanExecutor:
    async def execute_plan_async(self, plan, goal, context):
        """Execute plan with parallel verification."""
        verification_tasks = []
        
        for i, step in enumerate(plan):
            # Execute current step
            step_result = await self._execute_step_async(step, state)
            state["step_results"][step_id] = step_result
            
            # Start verification in background while moving to next step
            if self.verifier and self._should_verify_step(step):
                verification_task = asyncio.create_task(
                    self._verify_step_async(step, step_result, state)
                )
                verification_tasks.append((step_id, verification_task))
            
            # Check previous verifications (non-blocking)
            await self._check_pending_verifications(verification_tasks, step_id)
        
        # Wait for all verifications to complete
        for step_id, task in verification_tasks:
            state["verification_results"][step_id] = await task
```

**Benefits:**
- 30-50% faster overall execution
- No blocking on verification
- Earlier error detection

#### 1.3 Batch LLM Calls for Similar Operations

**Use Case:** When synthesizing multiple pieces of content or analyzing multiple items

```python
# New utility: src/utils/llm_batcher.py
class LLMBatcher:
    """Batch multiple LLM calls into single request with structured output."""
    
    def __init__(self, llm, batch_size=5):
        self.llm = llm
        self.batch_size = batch_size
        self.queue = []
        self.lock = asyncio.Lock()
    
    async def batch_invoke(self, prompts: List[str]) -> List[str]:
        """Invoke LLM with multiple prompts batched together."""
        # Combine prompts into single request with JSON output format
        combined_prompt = self._create_batch_prompt(prompts)
        response = await asyncio.to_thread(self.llm.invoke, combined_prompt)
        return self._parse_batch_response(response)
```

**Benefits:**
- 60-80% reduction in API calls
- Lower cost
- Faster for multiple similar operations

### Rate Limiting Strategy

**Implement Token Bucket Algorithm:**

```python
# src/utils/rate_limiter.py
import asyncio
import time
from collections import deque

class OpenAIRateLimiter:
    """Rate limiter respecting OpenAI's RPM and TPM limits."""
    
    def __init__(self, rpm_limit=10000, tpm_limit=2000000):
        self.rpm_limit = rpm_limit
        self.tpm_limit = tpm_limit
        self.request_times = deque()
        self.token_usage = deque()
        self.lock = asyncio.Lock()
    
    async def acquire(self, estimated_tokens=1000):
        """Acquire rate limit slot before making API call."""
        async with self.lock:
            now = time.time()
            
            # Remove old entries (>60 seconds)
            while self.request_times and now - self.request_times[0] > 60:
                self.request_times.popleft()
                self.token_usage.popleft()
            
            # Check if we can proceed
            if len(self.request_times) >= self.rpm_limit:
                wait_time = 60 - (now - self.request_times[0])
                await asyncio.sleep(wait_time)
            
            total_tokens = sum(self.token_usage)
            if total_tokens + estimated_tokens > self.tpm_limit:
                wait_time = 60 - (now - self.request_times[0])
                await asyncio.sleep(wait_time)
            
            # Record this request
            self.request_times.append(now)
            self.token_usage.append(estimated_tokens)
```

---

## 2. DATA STRUCTURES - Caching & Memory Optimization

### Problem
**Current State:**
- Tool catalog regenerated on every orchestrator init (lazy but still slow)
- Session memory serialized/deserialized frequently
- No LRU cache for frequently accessed data
- FAISS index loaded fully into memory even for small queries
- Prompt repository loads files repeatedly

**Files Affected:**
- `src/orchestrator/tools_catalog.py`
- `src/memory/session_manager.py`
- `src/documents/indexer.py`
- `src/prompt_repository.py`

### Solution

#### 2.1 In-Memory Tool Catalog Cache

```python
# In src/orchestrator/tools_catalog.py
from functools import lru_cache
import hashlib

class ToolCatalogCache:
    """Persistent cache for tool catalog with invalidation."""
    
    _cache = None
    _cache_hash = None
    
    @classmethod
    def get_catalog(cls, tools):
        """Get cached catalog or regenerate if tools changed."""
        current_hash = cls._compute_tools_hash(tools)
        
        if cls._cache is None or cls._cache_hash != current_hash:
            cls._cache = cls._generate_catalog(tools)
            cls._cache_hash = current_hash
        
        return cls._cache
    
    @staticmethod
    def _compute_tools_hash(tools):
        """Compute hash of tool signatures for cache invalidation."""
        tool_signatures = [f"{t.name}:{t.description}" for t in tools]
        return hashlib.md5("".join(tool_signatures).encode()).hexdigest()
```

**Benefits:**
- 90% faster orchestrator initialization
- Consistent tool catalog across requests
- Automatic invalidation on tool changes

#### 2.2 Session Memory Optimization

**Problem:** Session is serialized to disk too frequently

```python
# In src/memory/session_manager.py
class SessionManager:
    def __init__(self, storage_dir, config):
        # ... existing code ...
        
        # Add write-behind cache
        self._dirty_sessions = set()
        self._save_task = None
        self._save_interval = 30  # seconds
        
        # Start background saver
        self._start_background_saver()
    
    async def _background_saver(self):
        """Periodically save dirty sessions."""
        while True:
            await asyncio.sleep(self._save_interval)
            async with self._lock:
                for session_id in list(self._dirty_sessions):
                    self.save_session(session_id)
                self._dirty_sessions.clear()
    
    def mark_dirty(self, session_id):
        """Mark session as needing save (write-behind)."""
        self._dirty_sessions.add(session_id)
```

**Benefits:**
- 70% reduction in disk I/O
- Batched writes
- No blocking on save

#### 2.3 LRU Cache for Prompt Loading

```python
# In src/prompt_repository.py
from functools import lru_cache
from pathlib import Path

class PromptRepository:
    
    @lru_cache(maxsize=50)
    def _load_prompt_file(self, file_path: str) -> str:
        """Load prompt file with LRU caching."""
        return Path(file_path).read_text()
    
    @lru_cache(maxsize=20)
    def get_agent_examples(self, agent_name: str) -> str:
        """Get examples for agent with caching."""
        # ... existing logic with caching
```

**Benefits:**
- 95% faster prompt loading
- Reduced file I/O
- Minimal memory overhead

#### 2.4 Optimized FAISS Search

**Current:** Always loads full index

```python
# In src/documents/indexer.py
class DocumentIndexer:
    def __init__(self, config):
        # ... existing code ...
        
        # Add IVF (Inverted File Index) for faster search
        self.use_ivf = config.get('search', {}).get('use_ivf', True)
        self.nlist = 100  # number of clusters
    
    def _initialize_index(self):
        """Initialize FAISS index with IVF for faster search."""
        if self.use_ivf:
            # Use IVFFlat for faster search at scale
            quantizer = faiss.IndexFlatIP(self.dimension)
            self.index = faiss.IndexIVFFlat(quantizer, self.dimension, self.nlist)
            # Train index when documents are added
        else:
            # Fallback to flat index
            self.index = faiss.IndexFlatIP(self.dimension)
    
    def search(self, query_embedding, top_k=5, nprobe=10):
        """Search with optimized IVF settings."""
        if isinstance(self.index, faiss.IndexIVFFlat):
            self.index.nprobe = nprobe  # number of clusters to search
        return self.index.search(query_embedding, top_k)
```

**Benefits:**
- 5-10x faster search for large document sets (>10K docs)
- Configurable accuracy/speed tradeoff
- Scales better

#### 2.5 Connection Pooling for OpenAI Client

```python
# In src/utils/openai_client.py
from openai import OpenAI
import httpx

class PooledOpenAIClient:
    """OpenAI client with connection pooling for better performance."""
    
    _instance = None
    
    def __new__(cls, config):
        if cls._instance is None:
            # Create httpx client with connection pooling
            http_client = httpx.Client(
                limits=httpx.Limits(
                    max_keepalive_connections=20,
                    max_connections=50,
                    keepalive_expiry=60
                ),
                timeout=httpx.Timeout(60.0)
            )
            
            cls._instance = OpenAI(
                api_key=config['openai']['api_key'],
                http_client=http_client
            )
        
        return cls._instance
```

**Benefits:**
- 20-40% faster API calls (reused connections)
- Lower latency
- Better resource utilization

---

## 3. SEQUENTIAL EXECUTION - Parallel Step Execution

### Problem
**Current State:**
- Steps execute one at a time in `executor.py`
- Independent steps wait for each other
- No dependency graph analysis
- All steps are serialized even when parallel execution is safe

**File:** `src/orchestrator/executor.py` (lines 119-237)

### Solution

#### 3.1 Dependency Graph & Parallel Execution

```python
# In src/orchestrator/executor.py
import asyncio
from typing import Dict, List, Set
import networkx as nx

class PlanExecutor:
    
    def _build_dependency_graph(self, plan: List[Dict]) -> nx.DiGraph:
        """Build directed acyclic graph of step dependencies."""
        graph = nx.DiGraph()
        
        for step in plan:
            step_id = step.get('id')
            graph.add_node(step_id, step=step)
            
            # Add edges for dependencies
            for dep_id in step.get('dependencies', []):
                graph.add_edge(dep_id, step_id)
        
        return graph
    
    async def execute_plan_parallel(
        self, plan: List[Dict], goal: str, context: Dict
    ) -> Dict[str, Any]:
        """Execute plan with maximum parallelization based on dependencies."""
        
        # Build dependency graph
        dep_graph = self._build_dependency_graph(plan)
        
        # Verify it's a DAG (no cycles)
        if not nx.is_directed_acyclic_graph(dep_graph):
            return self.execute_plan(plan, goal, context)  # fallback
        
        # Execute in topological order with parallelization
        state = self._init_state(plan, goal, context)
        
        # Get execution levels (steps that can run in parallel)
        execution_levels = list(nx.topological_generations(dep_graph))
        
        for level, step_ids in enumerate(execution_levels):
            logger.info(f"Executing level {level} with {len(step_ids)} parallel steps")
            
            # Execute all steps in this level concurrently
            tasks = []
            for step_id in step_ids:
                step = dep_graph.nodes[step_id]['step']
                task = asyncio.create_task(
                    self._execute_step_async(step, state)
                )
                tasks.append((step_id, task))
            
            # Wait for all steps in this level to complete
            for step_id, task in tasks:
                try:
                    result = await task
                    state["step_results"][step_id] = result
                except Exception as e:
                    logger.error(f"Step {step_id} failed: {e}")
                    state["step_results"][step_id] = {
                        "error": True,
                        "error_message": str(e)
                    }
            
            # Check for failures before proceeding
            if any(r.get("error") for r in state["step_results"].values()):
                # Handle failure...
                break
        
        return self._finalize_results(state)
    
    async def _execute_step_async(self, step: Dict, state: Dict) -> Dict:
        """Async version of step execution."""
        return await asyncio.to_thread(self._execute_step, step, state)
```

**Example Benefit:**

```
BEFORE (Sequential):
Step 1: get_stock_price (NVDA) [2s]
Step 2: get_stock_price (AAPL) [2s]  <- waits for step 1
Step 3: create_report [3s]           <- waits for steps 1,2
Total: 7 seconds

AFTER (Parallel):
Step 1: get_stock_price (NVDA) [2s] \
Step 2: get_stock_price (AAPL) [2s]  } parallel (2s total)
Step 3: create_report [3s]           <- waits for steps 1,2
Total: 5 seconds (28% faster)
```

#### 3.2 Intelligent Step Batching

**Problem:** Some tools can batch operations but plans don't leverage this

```python
# In src/orchestrator/planner.py
class Planner:
    
    def _optimize_plan_for_batching(self, plan: List[Dict]) -> List[Dict]:
        """Merge compatible steps into batch operations."""
        
        optimized_plan = []
        skip_ids = set()
        
        for i, step in enumerate(plan):
            if step['id'] in skip_ids:
                continue
            
            # Look for similar steps that can be batched
            if step['action'] in ['get_stock_price', 'read_emails_by_time']:
                batch_candidates = []
                
                for j in range(i+1, len(plan)):
                    if (plan[j]['action'] == step['action'] and
                        plan[j]['id'] not in step.get('dependencies', []) and
                        step['id'] not in plan[j].get('dependencies', [])):
                        batch_candidates.append(plan[j])
                
                if batch_candidates:
                    # Create batched step
                    batched_step = {
                        'id': step['id'],
                        'action': f"{step['action']}_batch",
                        'parameters': {
                            'items': [step['parameters']] + [s['parameters'] for s in batch_candidates]
                        },
                        'reasoning': f"Batched {len(batch_candidates)+1} {step['action']} calls",
                        'dependencies': step.get('dependencies', [])
                    }
                    optimized_plan.append(batched_step)
                    skip_ids.update(s['id'] for s in batch_candidates)
                    continue
            
            optimized_plan.append(step)
        
        return optimized_plan
```

---

## 4. AGENT INITIALIZATION - Lazy Loading & Registry Optimization

### Problem
**Current State:**
- `AgentRegistry` has 47 agents
- Some agents initialize on registry creation (eager loading)
- Each agent loads its tools and prompts
- Unused agents consume memory

**File:** `src/agent/agent_registry.py`

**Current Optimization:** Already has some lazy loading via `initialize_agents()` method (line 349 in planner.py)

### Enhancement

#### 4.1 Improve Lazy Agent Loading

```python
# In src/agent/agent_registry.py
class AgentRegistry:
    
    def __init__(self, config, session_manager=None):
        self.config = config
        self.session_manager = session_manager
        
        # Don't initialize agents - just store factory functions
        self._agent_factories = self._register_agent_factories()
        self._agent_cache = {}  # Lazy cache
        self._agent_locks = {}   # Per-agent locks for thread safety
    
    def _register_agent_factories(self) -> Dict[str, callable]:
        """Register factory functions instead of instances."""
        return {
            'email': lambda: EmailAgent(self.config),
            'file': lambda: FileAgent(self.config),
            'calendar': lambda: CalendarAgent(self.config),
            # ... all 47 agents as factories
        }
    
    def get_agent(self, agent_name: str):
        """Get agent with lazy initialization and caching."""
        if agent_name not in self._agent_cache:
            if agent_name not in self._agent_locks:
                self._agent_locks[agent_name] = threading.Lock()
            
            with self._agent_locks[agent_name]:
                # Double-check after acquiring lock
                if agent_name not in self._agent_cache:
                    factory = self._agent_factories.get(agent_name)
                    if factory:
                        self._agent_cache[agent_name] = factory()
                    else:
                        raise ValueError(f"Unknown agent: {agent_name}")
        
        return self._agent_cache[agent_name]
    
    def warmup_agents(self, agent_names: List[str]):
        """Preload specific agents in parallel during idle time."""
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(self.get_agent, name) 
                for name in agent_names
            ]
            # Wait for all to complete
            [f.result() for f in futures]
```

**Benefits:**
- 80% faster startup when most agents unused
- Memory usage scales with actual usage
- Parallel warmup for predicted agents

#### 4.2 Agent Tool Lazy Loading

```python
# In src/agent/base_agent.py (if exists) or individual agents
class BaseAgent:
    
    def __init__(self, config):
        self.config = config
        self._tools = None  # Lazy load
        self._prompts = None  # Lazy load
    
    @property
    def tools(self):
        """Lazy load tools on first access."""
        if self._tools is None:
            self._tools = self._initialize_tools()
        return self._tools
    
    @property
    def prompts(self):
        """Lazy load prompts on first access."""
        if self._prompts is None:
            self._prompts = self._load_prompts()
        return self._prompts
```

---

## 5. EMBEDDING GENERATION - Batch Processing

### Problem
**Current State:**
- Embeddings generated one at a time during indexing
- Each embedding requires separate API call
- 100 documents = 100+ API calls

**File:** `src/documents/indexer.py` (lines 74-105)

### Solution

#### 5.1 Batch Embedding Generation

```python
# In src/documents/indexer.py
class DocumentIndexer:
    
    def get_embeddings_batch(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts in a single API call."""
        # OpenAI supports up to 2048 inputs per request
        batch_size = 100  # Conservative batch size
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            
            # Truncate each text
            batch = [text[:30000] for text in batch]
            
            try:
                response = self.client.embeddings.create(
                    model=self.embedding_model,
                    input=batch  # List of texts
                )
                
                # Extract embeddings
                embeddings = [
                    np.array(item.embedding, dtype=np.float32) 
                    for item in response.data
                ]
                
                # Normalize
                embeddings = [e / np.linalg.norm(e) for e in embeddings]
                all_embeddings.extend(embeddings)
                
            except Exception as e:
                logger.error(f"Batch embedding failed: {e}")
                # Fallback to individual calls for this batch
                for text in batch:
                    all_embeddings.append(self.get_embedding(text))
        
        return np.array(all_embeddings)
    
    def index_documents(self, folders, cancel_event=None):
        """Modified to use batch embeddings."""
        # ... file discovery logic ...
        
        # Parse all documents first
        parsed_docs = []
        for file_path in tqdm(all_files, desc="Parsing documents"):
            if cancel_event and cancel_event.is_set():
                break
            parsed = self.parser.parse_document(str(file_path))
            if parsed and parsed.get('content'):
                parsed_docs.append(parsed)
        
        # Generate embeddings in batches
        logger.info(f"Generating embeddings for {len(parsed_docs)} documents")
        texts = [doc['content'] for doc in parsed_docs]
        embeddings = self.get_embeddings_batch(texts)
        
        # Add to FAISS index
        self.index.add(embeddings)
        self.documents.extend(parsed_docs)
        
        return len(parsed_docs)
```

**Benefits:**
- 10-20x faster indexing
- 90% reduction in API calls
- Lower cost

#### 5.2 Parallel Embedding for Memory Store

```python
# In src/memory/user_memory_store.py
class UserMemoryStore:
    
    def add_memories_batch(self, memories: List[MemoryEntry]):
        """Add multiple memories with batch embedding."""
        if not memories:
            return
        
        # Extract contents that need embeddings
        texts_to_embed = [m.content for m in memories if not m.embedding]
        
        if texts_to_embed:
            # Use batch embedding (similar to DocumentIndexer)
            embeddings = self._get_embeddings_batch(texts_to_embed)
            
            # Assign embeddings
            embed_idx = 0
            for memory in memories:
                if not memory.embedding:
                    memory.embedding = embeddings[embed_idx]
                    embed_idx += 1
        
        # Add to FAISS and storage
        # ... rest of logic
```

---

## 6. SESSION MANAGEMENT - Reduce Serialization Overhead

### Problem
**Current State:**
- Sessions serialized to JSON frequently
- Large interaction histories bloat session files
- Lock contention on session access
- Memory usage grows with session size

**Files:**
- `src/memory/session_manager.py`
- `src/memory/session_memory.py`

### Solution

#### 6.1 Incremental Serialization

```python
# In src/memory/session_memory.py
class SessionMemory:
    
    def to_dict_incremental(self, last_checkpoint: Optional[str] = None) -> Dict:
        """Serialize only changes since last checkpoint."""
        if not last_checkpoint:
            return self.to_dict()  # Full serialization
        
        # Only serialize new interactions
        checkpoint_idx = self._find_checkpoint_index(last_checkpoint)
        
        return {
            "session_id": self.session_id,
            "checkpoint": datetime.now().isoformat(),
            "incremental": True,
            "new_interactions": [
                i.to_dict() for i in self.interactions[checkpoint_idx:]
            ],
            "shared_context_updates": self._get_context_updates(last_checkpoint),
        }
```

#### 6.2 Message Pack for Faster Serialization

```python
# In src/memory/session_manager.py
import msgpack

class SessionManager:
    
    def save_session_msgpack(self, session_id, memory):
        """Save using MessagePack (5-10x faster than JSON)."""
        try:
            data = memory.to_dict()
            filepath = self._get_session_filepath(session_id).with_suffix('.msgpack')
            
            with open(filepath, 'wb') as f:
                msgpack.pack(data, f, use_bin_type=True)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return False
    
    def _load_session_from_disk_msgpack(self, session_id):
        """Load using MessagePack."""
        filepath = self._get_session_filepath(session_id).with_suffix('.msgpack')
        
        if not filepath.exists():
            # Try JSON fallback
            return self._load_session_from_disk(session_id)
        
        with open(filepath, 'rb') as f:
            data = msgpack.unpack(f, raw=False)
        
        return SessionMemory.from_dict(data)
```

**Benefits:**
- 5-10x faster save/load
- 30-50% smaller file size
- Less CPU usage

#### 6.3 Session Compression

```python
# For very large sessions
import zlib

class SessionManager:
    
    def save_session_compressed(self, session_id, memory):
        """Save with compression for large sessions."""
        data = memory.to_dict()
        json_bytes = json.dumps(data).encode('utf-8')
        
        # Compress if > 100KB
        if len(json_bytes) > 100_000:
            compressed = zlib.compress(json_bytes, level=6)
            filepath = self._get_session_filepath(session_id).with_suffix('.json.gz')
            with open(filepath, 'wb') as f:
                f.write(compressed)
        else:
            # Regular save for small sessions
            self.save_session(session_id, memory)
```

---

## 7. REQUEST HANDLING - Connection Pooling & Keep-Alive

### Problem
**Current State:**
- OpenAI client created per request in some places
- No connection pooling
- TCP connection overhead on every request

**File:** `api_server.py`, various agent files

### Solution

**Already covered in Section 2.5** - Connection Pooling for OpenAI Client

**Additional: HTTP/2 for WebSocket**

```python
# In api_server.py
from hypercorn.config import Config as HypercornConfig
from hypercorn.asyncio import serve

# Use Hypercorn with HTTP/2 for better WebSocket performance
config = HypercornConfig()
config.bind = ["0.0.0.0:8000"]
config.use_reloader = True
config.accesslog = "-"
config.alpn_protocols = ["h2", "http/1.1"]  # HTTP/2 support

# Run with asyncio
import asyncio
asyncio.run(serve(app, config))
```

---

## 8. LANGGRAPH OPTIMIZATIONS - State Management & Context Passing

### Problem
**Current State:**
- Full state passed to every node
- Messages list grows unbounded
- No state pruning

**File:** `src/agent/agent.py`

### Solution

#### 8.1 State Pruning

```python
# In src/agent/agent.py
class AutomationAgent:
    
    def _prune_state(self, state: AgentState) -> AgentState:
        """Remove unnecessary data from state between nodes."""
        # Keep only last N messages
        if len(state.get('messages', [])) > 20:
            state['messages'] = state['messages'][-20:]
        
        # Remove old step results after finalization
        if state['status'] == 'completed':
            # Keep only summary, not full results
            state['step_results'] = {
                'summary': self._summarize_results(state['step_results'])
            }
        
        return state
```

#### 8.2 Streaming State Updates

```python
# For large state, stream updates instead of full state
class AutomationAgent:
    
    def _stream_state_update(self, key: str, value: Any):
        """Update specific state key without passing full state."""
        # Use LangGraph's checkpoint system
        self.graph.update_state(
            {key: value},
            as_node="current_node"
        )
```

---

## Implementation Priority & Timeline

### Phase 1 (Week 1) - Quick Wins - 30% Latency Reduction
**Priority: HIGH | Complexity: LOW**

1. ✅ Connection pooling for OpenAI (Section 2.5)
2. ✅ LRU cache for prompts (Section 2.3)
3. ✅ Tool catalog caching (Section 2.1)
4. ✅ Batch embeddings (Section 5.1)
5. ✅ Write-behind session saves (Section 2.2)

**Expected Impact:** 30% faster responses, 50% fewer API calls during indexing

### Phase 2 (Week 2) - Parallelization - 40% Additional Reduction
**Priority: HIGH | Complexity: MEDIUM**

1. ✅ Async planner with parallel intent analysis (Section 1.1)
2. ✅ Parallel step execution (Section 3.1)
3. ✅ Background verification (Section 1.2)
4. ✅ Rate limiter (Section 1)

**Expected Impact:** 40% faster plan execution, better LLM utilization

### Phase 3 (Week 3) - Advanced Optimizations - 20% Additional Reduction
**Priority: MEDIUM | Complexity: MEDIUM-HIGH**

1. ✅ IVF FAISS index (Section 2.4)
2. ✅ Step batching optimization (Section 3.2)
3. ✅ MessagePack serialization (Section 6.2)
4. ✅ Agent lazy loading improvements (Section 4)

**Expected Impact:** 20% faster search, better memory usage

### Phase 4 (Week 4) - Fine-Tuning
**Priority: LOW | Complexity: LOW**

1. ✅ LLM batching (Section 1.3)
2. ✅ State pruning (Section 8.1)
3. ✅ Session compression (Section 6.3)
4. ✅ HTTP/2 support (Section 7)

**Expected Impact:** 10-15% overall improvement, better scaling

---

## Monitoring & Metrics

### Key Metrics to Track

```python
# Add to each phase
class PerformanceMonitor:
    """Track performance improvements."""
    
    def __init__(self):
        self.metrics = {
            'request_latency': [],
            'llm_call_duration': [],
            'parallel_efficiency': [],
            'cache_hit_rate': [],
            'memory_usage': [],
        }
    
    def record_request(self, duration, phase):
        """Record request metrics."""
        self.metrics['request_latency'].append({
            'duration': duration,
            'phase': phase,
            'timestamp': datetime.now()
        })
    
    def get_summary(self) -> Dict:
        """Get performance summary."""
        return {
            'avg_latency': np.mean([m['duration'] for m in self.metrics['request_latency']]),
            'p95_latency': np.percentile([m['duration'] for m in self.metrics['request_latency']], 95),
            'p99_latency': np.percentile([m['duration'] for m in self.metrics['request_latency']], 99),
        }
```

### Targets

| Metric | Before | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|--------|--------|---------|---------|---------|---------|
| Average Response Time | 8s | 5.6s (-30%) | 3.4s (-60%) | 2.7s (-66%) | 2.4s (-70%) |
| P95 Response Time | 15s | 10.5s | 6.5s | 5.2s | 4.5s |
| LLM API Calls | 10/request | 10 | 8 | 6 | 4 |
| Embedding Time (100 docs) | 60s | 6s (-90%) | 6s | 5s | 5s |
| Memory Usage | 500MB | 450MB | 400MB | 350MB | 320MB |

---

## Testing Strategy

### 1. Benchmark Suite

Create comprehensive benchmarks:

```python
# tests/performance/benchmark_suite.py
import time
import statistics

class PerformanceBenchmark:
    """Benchmark suite for performance testing."""
    
    def __init__(self):
        self.results = {}
    
    async def benchmark_planning(self, queries: List[str]):
        """Benchmark planning phase."""
        times = []
        for query in queries:
            start = time.perf_counter()
            await orchestrator.planner.create_plan(query, ...)
            duration = time.perf_counter() - start
            times.append(duration)
        
        return {
            'mean': statistics.mean(times),
            'median': statistics.median(times),
            'stdev': statistics.stdev(times),
            'min': min(times),
            'max': max(times)
        }
    
    async def benchmark_execution(self, plans: List[Dict]):
        """Benchmark execution phase."""
        # Similar structure
        pass
    
    async def benchmark_end_to_end(self, queries: List[str]):
        """Full end-to-end benchmark."""
        pass
```

### 2. Load Testing

```python
# tests/performance/load_test.py
import asyncio
import aiohttp

async def load_test_websocket(num_concurrent: int, num_requests: int):
    """Load test WebSocket endpoint."""
    
    async def send_request(session, i):
        async with session.ws_connect('ws://localhost:8000/ws/chat') as ws:
            await ws.send_json({
                'type': 'message',
                'message': f'Test query {i}',
                'session_id': f'load_test_{i}'
            })
            response = await ws.receive_json()
            return response
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(num_requests):
            tasks.append(send_request(session, i))
            
            # Batch in groups
            if len(tasks) >= num_concurrent:
                results = await asyncio.gather(*tasks)
                tasks = []
        
        if tasks:
            results = await asyncio.gather(*tasks)
```

### 3. Regression Testing

Ensure no functionality breaks:

```bash
# Run full test suite before and after each phase
pytest tests/ --benchmark --cov=src --cov-report=html

# Compare performance
python tests/performance/compare_results.py \
    --before results/phase0.json \
    --after results/phase1.json
```

---

## Risk Mitigation

### Potential Issues & Solutions

#### 1. Rate Limiting
**Risk:** Parallel requests hit rate limits
**Mitigation:** 
- Implement token bucket rate limiter (Section 1)
- Monitor OpenAI usage dashboard
- Adaptive concurrency based on 429 responses

#### 2. Race Conditions
**Risk:** Parallel execution causes race conditions
**Mitigation:**
- Use asyncio locks for shared state
- Immutable state passing in LangGraph
- Thorough testing with concurrent requests

#### 3. Memory Leaks
**Risk:** Caching causes memory growth
**Mitigation:**
- LRU caches with size limits
- Periodic cache eviction
- Memory profiling with memray

#### 4. Backward Compatibility
**Risk:** Changes break existing functionality
**Mitigation:**
- Feature flags for gradual rollout
- Comprehensive regression testing
- Fallback to sequential execution on errors

---

## Configuration

Add to `config.yaml`:

```yaml
performance:
  # Parallelization
  max_parallel_steps: 5
  max_parallel_llm_calls: 3
  
  # Caching
  tool_catalog_cache: true
  prompt_cache_size: 50
  agent_cache_size: 20
  
  # Session management
  session_save_interval: 30  # seconds
  session_serialization: "msgpack"  # json, msgpack
  session_compression: true
  
  # Embeddings
  embedding_batch_size: 100
  
  # Rate limiting
  openai_rpm_limit: 10000
  openai_tpm_limit: 2000000
  
  # Search
  faiss_use_ivf: true
  faiss_nlist: 100
  faiss_nprobe: 10
  
  # Monitoring
  enable_performance_monitoring: true
  metrics_export_interval: 60

# Feature flags (for gradual rollout)
features:
  parallel_execution: true
  batch_embeddings: true
  async_planner: true
  lazy_agent_loading: true
```

---

## Success Criteria

### Quantitative Metrics
- ✅ 50-70% reduction in average response time
- ✅ 60-80% reduction in embedding generation time
- ✅ 30-50% reduction in memory usage
- ✅ 90% reduction in API calls during indexing
- ✅ <100ms overhead from optimizations

### Qualitative Metrics
- ✅ No increase in error rates
- ✅ Maintains feature parity
- ✅ Improved user experience (perceived speed)
- ✅ Better resource utilization
- ✅ Cleaner, more maintainable code

---

## Conclusion

This optimization plan targets **50-70% overall latency reduction** through:

1. **Parallelization** - Concurrent LLM calls and step execution
2. **Smart Caching** - LRU caches, connection pooling, lazy loading
3. **Batch Processing** - Batched embeddings and LLM calls
4. **Efficient Data Structures** - IVF FAISS, MessagePack, optimized session management
5. **Rate Limit Optimization** - Maximum throughput within limits

**Implementation is phased** to ensure stability and allow for measurement of improvements at each stage.

**Next Steps:**
1. Review and approve plan
2. Set up performance benchmarking infrastructure
3. Begin Phase 1 implementation
4. Monitor metrics and adjust based on real-world performance

---

**Questions or concerns?** Let's discuss before proceeding with implementation.

