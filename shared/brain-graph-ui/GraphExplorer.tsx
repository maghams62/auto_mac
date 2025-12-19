"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { GraphCanvas, GraphCanvasHandle } from "./GraphCanvas";
import { GraphRequestStatus } from "./GraphRequestStatus";
import { GraphFilterBar } from "./GraphFilterBar";
import { DatabaseInfoPanel } from "./DatabaseInfoPanel";
import { NodeDetailsPanel } from "./NodeDetailsPanel";
import type {
  ExplorerFilters,
  GraphExplorerNode,
  GraphExplorerProps,
  GraphExplorerResponse,
  GraphRequestInfo,
} from "./types";
import { formatTimestamp, getColorForNode, resolveApiUrl } from "./utils";

const DEFAULT_MODALITIES = ["issue", "support", "git", "slack", "doc", "component", "service", "signal", "impact", "api", "repo"];
const TEST_HOOKS_ENABLED = process.env.NEXT_PUBLIC_GRAPH_TEST_HOOKS === "1";

function humanizeLabel(label: string) {
  if (!label) return label;
  const spaced = label.replace(/_/g, " ").replace(/([a-z])([A-Z])/g, "$1 $2");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

const DEFAULT_ENDPOINT = "/api/brain/universe";

function resolveNodeEnv() {
  if (typeof globalThis === "undefined") {
    return "production";
  }
  const env = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env;
  return env?.NODE_ENV ?? "production";
}

const isDevEnv = resolveNodeEnv() !== "production";

type GraphRequestConfig = {
  mode: "universe" | "issue" | "neo4j_default";
  rootNodeId?: string;
  depth: number;
  projectId?: string;
  filters: ExplorerFilters;
  apiBaseUrl?: string;
  endpointPath: string;
  refreshKey: number;
};

class GraphSnapshotHttpError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "GraphSnapshotHttpError";
    this.status = status;
  }
}

function toIso(timestamp: number) {
  return new Date(timestamp).toISOString();
}

function buildGraphRequestTarget({
  mode,
  rootNodeId,
  depth,
  projectId,
  filters,
  apiBaseUrl,
  endpointPath,
}: GraphRequestConfig) {
        const query = new URLSearchParams();
        query.set("mode", mode);
        query.set("depth", String(depth));
        query.set("limit", String(filters.limit));
        if (rootNodeId) {
          query.set("rootId", rootNodeId);
        }
        if (projectId) {
          query.set("projectId", projectId);
        }
        if (filters.modalities?.length) {
          filters.modalities.forEach((modality) => query.append("modalities", modality));
        }
        if (filters.snapshotAt) {
          query.set("snapshotAt", filters.snapshotAt);
        }
        const target = resolveApiUrl(apiBaseUrl, endpointPath, query);
  return { target, query };
}

type NormalizedGraphError = {
  message: string;
  kind: GraphRequestInfo["errorKind"];
  httpStatus?: number;
};

function normalizeGraphError(err: unknown, target: string): NormalizedGraphError {
  if (err instanceof GraphSnapshotHttpError) {
    return { message: err.message, kind: "http", httpStatus: err.status };
  }
  if (err instanceof DOMException && err.name === "AbortError") {
    return { message: "Request aborted", kind: "aborted" };
  }
  if (err instanceof TypeError) {
    const base = err.message || "Failed to fetch";
    const friendly = base.includes("Failed to fetch")
      ? `Browser could not reach ${target} (Failed to fetch). Confirm the backend is running and not blocked by extensions or corporate proxies.`
      : base;
    return { message: friendly, kind: "network" };
  }
  if (err instanceof Error) {
    return { message: err.message, kind: "unknown" };
  }
  return { message: "Unknown graph error", kind: "unknown" };
}

function useGraphSnapshot({
  mode,
  rootNodeId,
  depth,
  projectId,
  filters,
  apiBaseUrl,
  endpointPath,
  refreshKey,
}: GraphRequestConfig) {
  const [data, setData] = useState<GraphExplorerResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [requestInfo, setRequestInfo] = useState<GraphRequestInfo | null>(null);
  const modalitiesKey = useMemo(() => JSON.stringify(filters.modalities ?? null), [filters.modalities]);

  useEffect(() => {
    const controller = new AbortController();
    async function fetchSnapshot() {
      setLoading(true);
      setError(null);
      const { target } = buildGraphRequestTarget({
        mode,
        rootNodeId,
        depth,
        projectId,
        filters,
        apiBaseUrl,
        endpointPath,
        refreshKey,
      });
      const startedAt = Date.now();
      const startedAtIso = toIso(startedAt);
      setRequestInfo({
        target,
        status: "pending",
        startedAt: startedAtIso,
      });
      if (isDevEnv) {
        console.info(`[brain-graph] fetching ${target}`);
      }
      try {
        const response = await fetch(target, { signal: controller.signal });
        if (!response.ok) {
          throw new GraphSnapshotHttpError(response.status, `Snapshot request failed (${response.status})`);
        }
        const payload = (await response.json()) as GraphExplorerResponse;
        if (!controller.signal.aborted) {
          setData(payload);
          const completedAt = Date.now();
          const duration = completedAt - startedAt;
          const completedAtIso = toIso(completedAt);
          setRequestInfo({
            target,
            status: "success",
            startedAt: startedAtIso,
            completedAt: completedAtIso,
            durationMs: duration,
            httpStatus: response.status,
          });
          if (isDevEnv) {
            console.info(`[brain-graph] GET ${target} ${response.status} (${duration}ms)`);
          }
        }
      } catch (err) {
        if (controller.signal.aborted) {
          return;
        }
        const normalized = normalizeGraphError(err, target);
        if (normalized.kind === "aborted") {
          return;
        }
        const completedAt = Date.now();
        const duration = completedAt - startedAt;
        const completedAtIso = toIso(completedAt);
        setError(normalized.message);
          setData(null);
        setRequestInfo({
          target,
          status: "error",
          startedAt: startedAtIso,
          completedAt: completedAtIso,
          durationMs: duration,
          errorMessage: normalized.message,
          errorKind: normalized.kind,
          httpStatus: normalized.httpStatus,
        });
        if (isDevEnv) {
          console.error(`[brain-graph] GET ${target} failed (${normalized.kind}) – ${normalized.message}`);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }
    fetchSnapshot();
    return () => controller.abort();
  }, [mode, rootNodeId, depth, projectId, filters.limit, filters.snapshotAt, modalitiesKey, apiBaseUrl, endpointPath, refreshKey]);

  return { data, loading, error, requestInfo };
}

export function GraphExplorer({
  mode = "universe",
  rootNodeId,
  depth = 2,
  projectId,
  apiBaseUrl,
  apiDiagnostics,
  endpointPath = DEFAULT_ENDPOINT,
  initialFilters,
  hideDatabasePanel = false,
  className = "",
  title,
  enableTimeControls,
  lockViewport = false,
  layoutStyle = "radial",
  variant = "default",
}: GraphExplorerProps) {
  const isNeo4jVariant = variant === "neo4j";
  const [filters, setFilters] = useState<ExplorerFilters>({
    modalities: initialFilters?.modalities ?? null,
    limit: initialFilters?.limit ?? 600,
    snapshotAt: initialFilters?.snapshotAt,
  });
  const [selectedNode, setSelectedNode] = useState<GraphExplorerNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<GraphExplorerNode | null>(null);
  const [labelFilter, setLabelFilter] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [isReplaying, setIsReplaying] = useState(false);
  const [recentHighlights, setRecentHighlights] = useState<{ nodes: Set<string>; edges: Set<string> }>({
    nodes: new Set(),
    edges: new Set(),
  });
  const graphCanvasRef = useRef<GraphCanvasHandle>(null);
  const seenModalitiesRef = useRef(new Set(DEFAULT_MODALITIES));

  const previousSnapshot = useRef<GraphExplorerResponse | null>(null);

  const { data, loading, error, requestInfo } = useGraphSnapshot({
    mode,
    rootNodeId,
    depth,
    projectId,
    filters,
    apiBaseUrl,
    endpointPath,
    refreshKey,
  });
  useEffect(() => {
    if (!isDevEnv) return;
    if (!data) return;
    // eslint-disable-next-line no-console
    console.info("[brain-graph][dev] snapshot received", {
      nodes: data.nodes.length,
      edges: data.edges.length,
      labels: data.meta?.nodeLabelCounts,
    });
  }, [data]);

  const requestPreviewTarget = useMemo(
    () =>
      buildGraphRequestTarget({
        mode,
        rootNodeId,
        depth,
        projectId,
        filters,
        apiBaseUrl,
        endpointPath,
        refreshKey,
      }).target,
    [mode, rootNodeId, depth, projectId, filters, apiBaseUrl, endpointPath, refreshKey],
  );

  useEffect(() => {
    if (!data) {
      return;
    }
    if (selectedNode) {
      const stillExists = data.nodes.some((node) => node.id === selectedNode.id);
      if (!stillExists) {
        setSelectedNode(null);
      }
    }

    const previous = previousSnapshot.current;
    previousSnapshot.current = data;
    if (!previous) {
      return;
    }
    const prevNodes = new Set(previous.nodes.map((node) => node.id));
    const prevEdges = new Set(previous.edges.map((edge) => edge.id));
    const newNodes = data.nodes.filter((node) => !prevNodes.has(node.id)).map((node) => node.id);
    const newEdges = data.edges.filter((edge) => !prevEdges.has(edge.id)).map((edge) => edge.id);
    if (newNodes.length || newEdges.length) {
      const nodeHighlightSet = new Set(newNodes);
      const edgeHighlightSet = new Set(newEdges);
      setRecentHighlights({ nodes: nodeHighlightSet, edges: edgeHighlightSet });
      const timeout = setTimeout(() => {
        setRecentHighlights({ nodes: new Set(), edges: new Set() });
      }, 1800);
      return () => clearTimeout(timeout);
    }
    return;
  }, [data, selectedNode]);

  const defaultTimeControls = mode !== "issue" && !lockViewport;
  const timeControlsEnabled = enableTimeControls ?? defaultTimeControls;

  const timeBounds = useMemo(() => {
    if (!data?.meta?.minTimestamp || !data?.meta?.maxTimestamp) {
      return null;
    }
    const min = Date.parse(data.meta.minTimestamp);
    const max = Date.parse(data.meta.maxTimestamp);
    if (Number.isNaN(min) || Number.isNaN(max) || min === max) {
      return null;
    }
    return { min, max };
  }, [data?.meta?.minTimestamp, data?.meta?.maxTimestamp]);

  useEffect(() => {
    if (!timeControlsEnabled) {
      setIsReplaying(false);
      return;
    }
    if (!isReplaying || !timeBounds) {
      return;
    }
    const steps = 16;
    const stepSize = Math.max(1, Math.round((timeBounds.max - timeBounds.min) / steps));
    let currentValue = filters.snapshotAt ? Date.parse(filters.snapshotAt) : timeBounds.min;
    if (Number.isNaN(currentValue)) {
      currentValue = timeBounds.min;
    }
    const interval = setInterval(() => {
      currentValue = Math.min(currentValue + stepSize, timeBounds.max);
      setFilters((prev) => ({ ...prev, snapshotAt: new Date(currentValue).toISOString() }));
      if (currentValue >= timeBounds.max) {
        setIsReplaying(false);
        clearInterval(interval);
      }
    }, 1200);
    return () => clearInterval(interval);
  }, [isReplaying, timeBounds, filters.snapshotAt, timeControlsEnabled]);

  const modalityOptions = useMemo(() => {
    const counts = data?.meta?.modalityCounts ?? {};
    Object.keys(counts).forEach((key) => seenModalitiesRef.current.add(key));
    const allIds = Array.from(seenModalitiesRef.current);
    if (allIds.length === 0) {
      return [];
    }
    return allIds
      .map((label) => ({
        id: label,
        label: humanizeLabel(label),
        count: counts[label] ?? 0,
        color: getColorForNode(label, label),
      }))
      .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
  }, [data?.meta?.modalityCounts]);

  const toggleModality = useCallback(
    (modalityId: string) => {
      setFilters((prev) => {
        const current = prev.modalities && prev.modalities.length === 1 ? prev.modalities[0] : null;
        const nextModalities = current === modalityId ? null : [modalityId];
        return { ...prev, modalities: nextModalities };
      });
      setIsReplaying(false);
    },
    [],
  );

  const handleSnapshotChange = useCallback(
    (iso?: string) => {
      setFilters((prev) => ({ ...prev, snapshotAt: iso }));
      setIsReplaying(false);
    },
    [],
  );

  const graphNodes = data?.nodes ?? [];
  const graphEdges = data?.edges ?? [];
  const showRequestStatus = !loading && graphNodes.length === 0;
  const devDebugNodes = isDevEnv && graphNodes.length > 0 ? graphNodes.slice(0, 5).map((node) => node.id) : [];
  const metaLabelCounts = data?.meta?.nodeLabelCounts || {};
  const metaRelCounts = data?.meta?.relTypeCounts || {};
  const metaProps = data?.meta?.propertyKeys || [];
  const overviewLabelEntries = useMemo(() => Object.entries(metaLabelCounts).sort((a, b) => b[1] - a[1]), [metaLabelCounts]);
  const overviewRelEntries = useMemo(() => Object.entries(metaRelCounts).sort((a, b) => b[1] - a[1]), [metaRelCounts]);
  const focusNodeIds = useMemo(() => {
    if (!graphNodes.length) {
      return [];
    }
    if (!filters.modalities || filters.modalities.length === 0) {
      return graphNodes.map((node) => node.id);
    }
    const target = new Set(filters.modalities);
    const subset = graphNodes.filter((node) => (node.modality ? target.has(node.modality) : target.has(node.label))).map((node) => node.id);
    return subset.length ? subset : graphNodes.map((node) => node.id);
  }, [graphNodes, filters.modalities]);

  const snapshotRangeLabel = useMemo(() => {
    if (!data?.meta?.minTimestamp || !data?.meta?.maxTimestamp) {
      return "— → —";
    }
    return `${formatTimestamp(data.meta.minTimestamp)} → ${formatTimestamp(data.meta.maxTimestamp)}`;
  }, [data?.meta?.minTimestamp, data?.meta?.maxTimestamp]);
  const generatedAtLabel = data?.generatedAt ? formatTimestamp(data.generatedAt) : "—";

  return (
    <div className={`flex flex-col gap-4 ${className}`}>
      {!isNeo4jVariant ? (
      <div>
        <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Brain Explorer</p>
        <h1 className="text-2xl font-semibold text-white">{title ?? (mode === "issue" ? "Issue graph" : "Brain Universe")}</h1>
        <p className="text-sm text-slate-400">
          Pan, zoom, and select nodes to follow live evidence across Slack, Git, docs, APIs, and services. Use the time slider to replay the
          graph as new signals land.
        </p>
      </div>
      ) : title ? (
        <div>
          <h2 className="text-lg font-semibold text-white">{title}</h2>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Neo4j view</p>
        </div>
      ) : null}

      {!isNeo4jVariant ? (
      <GraphFilterBar
        modalities={modalityOptions}
        selectedModalities={filters.modalities}
        onToggleModality={toggleModality}
        limit={filters.limit}
        onLimitChange={(value) => setFilters((prev) => ({ ...prev, limit: value }))}
        snapshotAt={filters.snapshotAt}
        timeBounds={timeBounds ?? undefined}
        onSnapshotChange={handleSnapshotChange}
        isReplaying={isReplaying}
        onReplayToggle={() => setIsReplaying((prev) => !prev)}
        showTimeControls={timeControlsEnabled}
      />
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-950/80 px-4 py-3 text-sm text-slate-200">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Snapshot range</p>
            <p className="text-slate-100">{snapshotRangeLabel}</p>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
            <span data-testid="snapshot-counts-value">Nodes {graphNodes.length} · Edges {graphEdges.length}</span>
            <span>Generated {generatedAtLabel}</span>
            <button
              type="button"
              onClick={() => {
                setRefreshKey((prev) => prev + 1);
                setIsReplaying(false);
              }}
              className="rounded-md border border-slate-600 px-3 py-1 text-xs text-slate-200 hover:border-slate-400"
            >
              Refresh
            </button>
          </div>
        </div>
      )}
      {!lockViewport ? (
      <div className="flex flex-wrap items-center justify-end gap-2 text-xs text-slate-400">
        <button
          type="button"
          data-testid="reset-view-button"
          onClick={() => graphCanvasRef.current?.resetView()}
          className="rounded-md border border-slate-600 px-3 py-1 text-xs text-slate-200 hover:border-slate-400"
        >
          Reset view
        </button>
      </div>
      ) : null}

      <div className="flex gap-4">
        {/* Left sidebar */}
        <div className="w-72 shrink-0 rounded-2xl border border-slate-800 bg-slate-900/80 p-4 shadow-inner shadow-slate-900/40">
          {!hideDatabasePanel ? (
            <DatabaseInfoPanel meta={data?.meta} activeLabel={labelFilter} onSelectLabel={(label) => setLabelFilter(label)} />
          ) : (
            <div className="space-y-4 text-sm text-slate-200">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Node labels</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {Object.entries(metaLabelCounts).map(([label, count]) => (
                    <button
                      key={label}
                      type="button"
                      onClick={() => setLabelFilter(labelFilter === label ? null : label)}
                      className={`rounded-full border px-2 py-1 text-xs ${
                        labelFilter === label ? "border-cyan-400 text-cyan-200" : "border-slate-700 text-slate-300"
                      }`}
                    >
                      {label} ({count})
                    </button>
                  ))}
                  {!Object.keys(metaLabelCounts).length ? <span className="text-slate-500">No labels</span> : null}
                </div>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Relationship types</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {Object.entries(metaRelCounts).map(([rel, count]) => (
                    <span key={rel} className="rounded-full border border-slate-700 px-2 py-1 text-xs text-slate-300">
                      {rel} ({count})
                    </span>
                  ))}
                  {!Object.keys(metaRelCounts).length ? <span className="text-slate-500">No relationships</span> : null}
                </div>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Property keys</p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {metaProps.slice(0, 30).map((prop) => (
                    <span key={prop} className="rounded border border-slate-800 bg-slate-900 px-2 py-0.5 text-[11px] text-slate-300">
                      {prop}
                    </span>
                  ))}
                  {metaProps.length > 30 ? (
                    <span className="text-[11px] text-slate-500">+{metaProps.length - 30} more</span>
                  ) : null}
                  {!metaProps.length ? <span className="text-slate-500">No properties</span> : null}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Center graph area */}
        <div
          className={`relative ${isNeo4jVariant ? "min-h-[620px] max-h-[620px]" : "min-h-[540px]"} flex-1 overflow-hidden rounded-2xl border border-slate-800 bg-slate-950`}
          style={isNeo4jVariant ? { height: "620px" } : undefined}
        >
          {graphNodes.length > 0 ? (
            <GraphCanvas
              ref={graphCanvasRef}
              nodes={graphNodes}
              edges={graphEdges}
              selectedNodeId={selectedNode?.id}
              hoveredNodeId={hoveredNode?.id}
              labelFilter={labelFilter}
              recentNodeHighlights={recentHighlights.nodes}
              recentEdgeHighlights={recentHighlights.edges}
              onSelectNode={(node) => setSelectedNode(node)}
              onHoverNode={(node) => setHoveredNode(node)}
              focusNodeIds={focusNodeIds}
              allowPanZoom={!lockViewport}
              layoutStyle={layoutStyle}
              autoFocus={!lockViewport}
              testHooksEnabled={TEST_HOOKS_ENABLED}
            />
          ) : null}
          {devDebugNodes.length > 0 && (
            <div className="pointer-events-none absolute left-4 top-4 z-10 rounded-md bg-slate-900/80 px-3 py-2 text-[11px] text-slate-200">
              <div>DEV: nodes {graphNodes.length}, edges {graphEdges.length}</div>
              <div className="mt-1 text-slate-400">Sample IDs:</div>
              <ul className="list-disc pl-4">
                {devDebugNodes.map((id) => (
                  <li key={id}>{id}</li>
                ))}
              </ul>
            </div>
          )}
          {showRequestStatus ? (
            <div data-testid="graph-request-status">
              <GraphRequestStatus
                requestInfo={requestInfo}
                error={error}
                fallbackTarget={requestPreviewTarget}
                apiDiagnostics={apiDiagnostics}
                onRetry={() => {
                  setRefreshKey((prev) => prev + 1);
                  setIsReplaying(false);
                }}
              />
            </div>
          ) : null}
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-slate-950/60 text-sm text-slate-200">Loading graph…</div>
          )}
        </div>

        {/* Right sidebar */}
        <div className="w-80 shrink-0 space-y-4 rounded-2xl border border-slate-800 bg-slate-900/80 p-4 shadow-inner shadow-slate-900/40">
          <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-200" data-testid="overview-panel">
            <div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Overview</div>
            <div className="mt-2 space-y-3">
              <div>
                <p className="text-[11px] font-semibold text-slate-400">Node labels</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  {overviewLabelEntries.length ? (
                    overviewLabelEntries.map(([label, count]) => (
                      <span
                        key={label}
                        className="flex items-center gap-2 rounded-full border border-slate-700 bg-slate-800/80 px-2 py-1 text-[11px]"
                      >
                        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: getColorForNode(label, label.toLowerCase()) }} />
                        <span className="font-semibold text-slate-100">{label}</span>
                        <span className="text-slate-400">{count}</span>
                      </span>
                    ))
                  ) : (
                    <span className="text-[11px] text-slate-500">No labels</span>
                  )}
                </div>
              </div>
              <div>
                <p className="text-[11px] font-semibold text-slate-400">Relationship types</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  {overviewRelEntries.length ? (
                    overviewRelEntries.map(([rel, count]) => (
                      <span
                        key={rel}
                        className="rounded-full border border-slate-700 bg-slate-800/80 px-2 py-1 text-[11px] font-medium text-slate-100"
                      >
                        {rel} ({count})
                      </span>
                    ))
                  ) : (
                    <span className="text-[11px] text-slate-500">No relationships</span>
                  )}
                </div>
              </div>
            </div>
          </section>

          <NodeDetailsPanel node={selectedNode} />

          <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-3 text-xs text-slate-300" data-testid="snapshot-counts">
            <div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Snapshot</div>
            <div className="mt-1" data-testid="snapshot-counts-value">
              Nodes {graphNodes.length} · Edges {graphEdges.length}
            </div>
            <div className="text-slate-500">{data?.generatedAt ? new Date(data.generatedAt).toLocaleString() : "—"}</div>
          </div>
        </div>
      </div>

      {!isNeo4jVariant ? (
      <div className="flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-2 text-xs text-slate-400">
        <span>
            Snapshot generated {generatedAtLabel} · {graphNodes.length} nodes · {graphEdges.length} edges
        </span>
        <button
          type="button"
          onClick={() => {
            setRefreshKey((prev) => prev + 1);
            setIsReplaying(false);
          }}
          className="rounded-md border border-slate-600 px-3 py-1 text-xs text-slate-200 hover:border-slate-400"
        >
          Refresh
        </button>
      </div>
      ) : null}

      {TEST_HOOKS_ENABLED ? (
        <div className="fixed bottom-4 right-4 z-50 flex flex-wrap gap-2" data-testid="graph-node-test-hooks">
          {graphNodes.map((node) => (
            <button
              type="button"
              key={node.id}
              data-testid={`graph-node-hook-${node.id}`}
              className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"
              onClick={() => setSelectedNode(node)}
            >
              {node.title ?? node.id}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}


