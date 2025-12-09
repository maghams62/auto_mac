"use client";

import React, { useMemo, useState } from "react";

import type { GraphExplorerEdge, GraphExplorerNode, GraphExplorerResponse } from "@brain-graph-ui/types";

import { SimpleRelationshipGraph } from "@/components/SimpleRelationshipGraph";
import { useRelationshipsSnapshot } from "@/hooks/useRelationshipsSnapshot";
import { getApiBaseDiagnostics } from "@/lib/apiConfig";

type SourceFilter = "slack" | "git" | "doc";

const DEFAULT_LIMIT = 150;
const SOURCE_FILTERS: { id: SourceFilter; label: string }[] = [
  { id: "slack", label: "Slack" },
  { id: "git", label: "Git" },
  { id: "doc", label: "Doc issues" },
];

function buildEndpoint(baseUrl: string | undefined, sources: SourceFilter[], refreshKey: number): string | null {
  if (!baseUrl) {
    return null;
  }
  try {
    const url = new URL("/api/brain/universe/default", baseUrl);
    url.searchParams.set("limit", String(DEFAULT_LIMIT));
    sources.forEach((value) => url.searchParams.append("modalities", value));
    url.searchParams.set("_refresh", String(refreshKey));
    return url.toString();
  } catch {
    return null;
  }
}

function SnapshotMeta({ data }: { data: GraphExplorerResponse }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 text-xs text-slate-300">
      <div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Snapshot</div>
      <div className="mt-1">Nodes {data.nodes.length} · Edges {data.edges.length}</div>
      <div className="text-slate-500">{data.generatedAt ? new Date(data.generatedAt).toLocaleString() : "—"}</div>
    </div>
  );
}

export default function BrainUniverseView() {
  const apiDiagnostics = useMemo(() => getApiBaseDiagnostics(), []);
  const [selectedSources, setSelectedSources] = useState<SourceFilter[]>(SOURCE_FILTERS.map((option) => option.id));
  const [refreshCounter, setRefreshCounter] = useState(0);

  const endpoint = useMemo(
    () => buildEndpoint(apiDiagnostics.baseUrl, selectedSources, refreshCounter),
    [apiDiagnostics.baseUrl, selectedSources, refreshCounter],
  );
  const { loading, data, error } = useRelationshipsSnapshot(endpoint ?? "", undefined);

  if (process.env.NODE_ENV !== "production" && data) {
    // eslint-disable-next-line no-console
    console.debug("[BrainUniverseView] graph payload", {
      nodes: data.nodes.length,
      edges: data.edges.length,
      sample: data.nodes.slice(0, 3).map((n) => ({ id: n.id, label: n.label })),
      target: endpoint,
    });
  }

  const toggleSource = (sourceId: SourceFilter) => {
    setSelectedSources((prev) => {
      if (prev.includes(sourceId)) {
        const next = prev.filter((entry) => entry !== sourceId);
        return next.length ? next : SOURCE_FILTERS.map((option) => option.id);
      }
      return [...prev, sourceId];
    });
  };

  return (
    <div className="flex flex-col gap-4 p-6">
      <div>
        <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Brain Explorer</p>
        <h1 className="text-2xl font-semibold text-white">Relationships view</h1>
        <p className="text-sm text-slate-400">
          Neo4j snapshot highlighting Slack, Git, and Doc-issue activity across components, repos, and services.
        </p>
      </div>

      {!endpoint ? (
        <div className="rounded-2xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-200">
          Unable to determine API base URL. Confirm NEXT_PUBLIC_API_URL is configured.
        </div>
      ) : null}

      {loading ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-6 text-sm text-slate-300">Loading relationships…</div>
      ) : null}

      {!loading && error ? (
        <div className="rounded-2xl border border-amber-400/40 bg-amber-500/10 p-4 text-sm text-amber-200">Failed to load graph: {error}</div>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        {SOURCE_FILTERS.map((option) => (
          <button
            key={option.id}
            type="button"
            onClick={() => toggleSource(option.id)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
              selectedSources.includes(option.id)
                ? "border-slate-200 bg-slate-200/10 text-slate-50"
                : "border-slate-700 text-slate-300 hover:border-slate-500"
            }`}
          >
            {option.label}
          </button>
        ))}
        <button
          type="button"
          onClick={() => setRefreshCounter((counter) => counter + 1)}
          className="ml-auto rounded-md border border-slate-600 px-3 py-1 text-xs text-slate-200 hover:border-slate-400"
        >
          Refresh
        </button>
      </div>

      {data ? (
        <div className="flex flex-col gap-6 lg:flex-row">
          <div className="flex-1 space-y-4">
            <SimpleRelationshipGraph nodes={data.nodes} edges={data.edges} />
            <SnapshotMeta data={data} />
          </div>
          <RelationshipsOverview nodes={data.nodes} edges={data.edges} />
        </div>
      ) : null}
    </div>
  );
}

function countBy<T>(items: T[], getKey: (item: T) => string): Record<string, number> {
  return items.reduce<Record<string, number>>((acc, item) => {
    const key = getKey(item) || "Unknown";
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});
}

function RelationshipsOverview({ nodes, edges }: { nodes: GraphExplorerNode[]; edges: GraphExplorerEdge[] }) {
  const labelCounts = useMemo(() => countBy(nodes, (node) => node.label ?? "Node"), [nodes]);
  const relCounts = useMemo(() => countBy(edges, (edge) => edge.type ?? "RELATED"), [edges]);

  return (
    <section className="w-full rounded-2xl border border-slate-800 bg-slate-950/70 p-4 text-xs text-slate-200 lg:w-72">
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-500">Overview</h2>
      <div className="mt-4 space-y-4">
        <div>
          <p className="text-[11px] font-semibold text-slate-400">Node labels</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {Object.entries(labelCounts).map(([label, count]) => (
              <span key={label} className="rounded-full bg-slate-800 px-3 py-1 text-[11px]">
                {label} ({count})
              </span>
            ))}
          </div>
        </div>
        <div>
          <p className="text-[11px] font-semibold text-slate-400">Relationship types</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {Object.entries(relCounts).map(([label, count]) => (
              <span key={label} className="rounded-full border border-slate-700 px-3 py-1 text-[11px] text-slate-100">
                {label} ({count})
              </span>
            ))}
          </div>
        </div>
        <div className="text-[11px] text-slate-400">
          Displaying {nodes.length} nodes, {edges.length} relationships.
        </div>
      </div>
    </section>
  );
}


