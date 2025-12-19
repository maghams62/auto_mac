"use client";

import React from "react";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";

import { getApiBaseUrl } from "@/lib/apiConfig";
import { formatModalityLabel, getColorForSourceType } from "@/lib/modalityColors";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

type TraceChunk = {
  chunk_id?: string;
  source_type?: string;
  source_id?: string;
  modality?: string;
  title?: string;
  text?: string;
  url?: string;
  metadata?: Record<string, unknown>;
};

type TraceGraphNode = {
  id: string;
  type: string;
  source_type?: string;
  display_name?: string;
  text_preview?: string;
  url?: string;
  color?: string;
};

type TraceGraph = {
  nodes: TraceGraphNode[];
  edges: Array<{ id: string; from: string; to: string; type: string }>;
};

type TraceResponse = {
  query_id: string;
  question: string;
  created_at: string;
  modalities_used: string[];
  retrieved_chunks: TraceChunk[];
  chosen_chunks: TraceChunk[];
  graph: TraceGraph;
};

function useBrainTrace(queryId: string) {
  const [data, setData] = useState<TraceResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const apiBaseUrl = useMemo(() => getApiBaseUrl(), []);

  useEffect(() => {
    if (!queryId) return;
    const controller = new AbortController();
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const url = new URL(`/api/brain/trace/${encodeURIComponent(queryId)}`, apiBaseUrl);
        const response = await fetch(url.toString(), { signal: controller.signal });
        if (!response.ok) {
          if (response.status === 404) {
            throw new Error("No trace found for this query.");
          }
          throw new Error(`Failed to load trace (HTTP ${response.status}).`);
        }
        const payload = (await response.json()) as TraceResponse;
        if (!controller.signal.aborted) {
          setData(payload);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : "Unknown error");
          setData(null);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }
    load();
    return () => controller.abort();
  }, [queryId, apiBaseUrl]);

  return { data, loading, error };
}

type Props = {
  queryId: string;
};

export default function BrainTraceView({ queryId }: Props) {
  const { data, loading, error } = useBrainTrace(queryId);
  const [focusedChunkId, setFocusedChunkId] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setFocusedChunkId(data.retrieved_chunks[0]?.chunk_id ?? null);
    }
  }, [data?.query_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const graphData = useMemo(() => {
    if (!data?.graph) {
      return { nodes: [] as TraceGraphNode[], links: [] as TraceGraph["edges"] };
    }
    return {
      nodes: data.graph.nodes.map((node) => {
        if (node.type === "query") {
          return { ...node, color: "#f472b6" };
        }
        const modality = node.source_type ?? node.type;
        return { ...node, color: getColorForSourceType(modality) };
      }),
      links: data.graph.edges.map((edge) => ({
        id: edge.id,
        source: edge.from,
        target: edge.to,
        type: edge.type,
      })),
    };
  }, [data?.graph]);

  const selectedChunk = useMemo(() => {
    if (!focusedChunkId) return null;
    return data?.retrieved_chunks.find((chunk) => chunk.chunk_id === focusedChunkId) ?? null;
  }, [data?.retrieved_chunks, focusedChunkId]);

  const chunks = data?.retrieved_chunks ?? [];
  const modalityBadges = data?.modalities_used ?? [];
  const hasChunks = chunks.length > 0;
  const chunkEmptyCopy = error
    ? error
    : loading
    ? "Loading retrieved evidence…"
    : "No retrieved chunks were stored for this query.";

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex flex-col gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Brain Trace</p>
        <h1 className="text-2xl font-semibold text-white">{data?.question ?? (error ?? "Loading query…")}</h1>
        {modalityBadges.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {modalityBadges.map((modality) => (
              <span
                key={modality}
                className="rounded-full bg-slate-800/80 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-100"
              >
                {formatModalityLabel(modality)}
              </span>
            ))}
          </div>
        )}
      </div>

      <section className="flex flex-col gap-6 lg:flex-row">
        <div className="relative min-h-[460px] flex-1 rounded-xl border border-slate-800 bg-black/90">
          {graphData.nodes.length > 0 && (
            <ForceGraph2D
              graphData={graphData}
              nodeLabel={(node: TraceGraphNode) => {
                if (node.type === "query") return "Query";
                if (node.type === "chunk") {
                  return node.text_preview ?? node.id;
                }
                return node.display_name ?? node.id;
              }}
              nodeColor={(node: TraceGraphNode) => node.color || getColorForSourceType(node.source_type ?? node.type)}
              linkColor={() => "rgba(148, 163, 184, 0.4)"}
              onNodeClick={(node: { id: string }) => {
                if (typeof node.id === "string" && node.id.startsWith("chunk:")) {
                  setFocusedChunkId(node.id);
                }
              }}
              backgroundColor="#020617"
            />
          )}
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/60 text-sm text-slate-200">Loading…</div>
          )}
          {error && !loading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/70 text-center text-sm text-red-400">
              <p>{error}</p>
            </div>
          )}
          {!loading && !error && graphData.nodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/40 text-sm text-slate-400">
              No graph data available for this trace.
            </div>
          )}
        </div>

        <aside className="w-full rounded-xl border border-slate-800 bg-slate-900/60 p-4 lg:w-80">
          <h2 className="text-lg font-semibold text-white">Selected chunk</h2>
          {selectedChunk ? (
            <div className="mt-3 flex flex-col gap-2 text-sm text-slate-200">
              <div className="text-xs uppercase tracking-wide text-slate-500">Modality</div>
              <div className="font-medium capitalize">{selectedChunk.source_type ?? selectedChunk.modality ?? "chunk"}</div>
              {selectedChunk.title && (
                <>
                  <div className="text-xs uppercase tracking-wide text-slate-500">Title</div>
                  <div>{selectedChunk.title}</div>
                </>
              )}
              {selectedChunk.text && (
                <>
                  <div className="text-xs uppercase tracking-wide text-slate-500">Snippet</div>
                  <p className="rounded-md border border-slate-800 bg-slate-900 p-2 text-slate-100">{selectedChunk.text}</p>
                </>
              )}
              {selectedChunk.url && (
                <a
                  className="mt-2 inline-flex items-center justify-center rounded-md border border-slate-600 bg-slate-800 px-3 py-2 text-sm font-medium text-slate-100 hover:bg-slate-700"
                  href={selectedChunk.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open in source
                </a>
              )}
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-400">Click on a chunk node or select one from the list.</p>
          )}
        </aside>
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Retrieved chunks ({chunks.length})</h2>
          {data && (
            <a
              href="/brain/universe"
              className="text-sm font-medium text-blue-400 transition hover:text-blue-300"
              target="_blank"
              rel="noreferrer"
            >
              Explore in universe →
            </a>
          )}
        </div>
        {!hasChunks ? (
          <p className="mt-3 text-sm text-slate-400">{chunkEmptyCopy}</p>
        ) : (
          <ul className="mt-4 flex flex-col gap-3">
            {chunks.map((chunk) => (
              <li
                key={chunk.chunk_id ?? chunk.title ?? chunk.url}
                className={`cursor-pointer rounded-lg border px-3 py-2 text-sm transition ${
                  focusedChunkId === chunk.chunk_id ? "border-cyan-400 bg-cyan-400/10 text-white" : "border-slate-800 text-slate-200 hover:border-slate-600"
                }`}
                onClick={() => setFocusedChunkId(chunk.chunk_id ?? null)}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium">{chunk.title ?? chunk.chunk_id ?? "Chunk"}</span>
                  <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs uppercase tracking-wide text-slate-300">
                    {chunk.source_type ?? chunk.modality ?? "chunk"}
                  </span>
                </div>
                {chunk.text && <p className="mt-1 text-xs text-slate-400">{chunk.text.slice(0, 160)}{chunk.text.length > 160 ? "…" : ""}</p>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

