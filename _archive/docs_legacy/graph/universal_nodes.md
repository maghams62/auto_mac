# Universal Graph Nodes

Phase 0 introduces a single, modality-agnostic representation of indexed context so both the upcoming 3D “Cosmograph brain” and 2D “query trace” views can hydrate directly from Neo4j. Every chunk that lands in Qdrant now produces:

```
(:Source { id, source_type, source_id, parent_id, display_name, path, workspace_id })
(:Chunk  { id, source_type, entity_id, start_offset, end_offset, url, text_preview, workspace_id })
(:Chunk)-[:BELONGS_TO]->(:Source)
```

## Lifecycle
1. Modality ingestors (Slack, Git, Files, Git, YouTube) convert raw data into the canonical `ContextChunk`.
2. Each handler calls `UniversalNodeWriter.ingest_chunks(chunks)` after vector indexing succeeds.
3. The writer `MERGE`s the corresponding `Source` node (channel, repo file, YouTube video, etc.), `MERGE`s the `Chunk`, and links them with `BELONGS_TO`.

## Why Two Node Types?
* `Source` nodes give the brain views a single place to hang metadata like repo hierarchy, channel affiliation, or video/channel relationships.
* `Chunk` nodes keep search-grade granularity (offsets, snippets, tags) without polluting the source itself. They can be clustered for 3D scatter plots or filtered for 2D path views.

## Consuming the Graph
* **3D view**: query `MATCH (c:Chunk {workspace_id:$id})-[:BELONGS_TO]->(s:Source)` and feed chunk embeddings + source metadata into the Cosmograph renderer.
* **2D query trace**: hydrate from `/api/brain/trace/:query_id` to know which `chunk_id`s were retrieved, then `MATCH (chunk:Chunk {id:$chunk_id})-[:BELONGS_TO]->(source)` to render the path from question → chunk → source.

## Future Extensions
* Add higher-level nodes (Workspace, Repo, Concept) and connect them to `Source` nodes for cross-modality reasoning.
* Attach ingestion timestamps and modality scores as edge attributes so temporal filters (“show me the freshest chunks per source”) are trivial.

