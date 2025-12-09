/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck
'use client';

import dynamic from "next/dynamic";
import Link from "next/link";
import * as THREE from "three";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useParams } from "next/navigation";
import { Activity, AlertCircle, ArrowRight, Filter, Flame, GitBranch, Signal } from "lucide-react";
import type { ForceGraphMethods } from "react-force-graph-3d";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  GraphKpi,
  GraphMetrics,
  LiveGraphComponent,
  LiveGraphIssue,
  LiveGraphSignal,
  LiveGraphSnapshot,
} from "@/lib/graph/live-types";
import { selectProjectById, useDashboardStore } from "@/lib/state/dashboard-store";
import { shortDate } from "@/lib/utils";
import { logClientEvent } from "@/lib/logging";
import { isLiveLike } from "@/lib/mode";
import { buildInvestigationUrl } from "@/lib/cerebros";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const ForceGraph3D = dynamic(() => import("react-force-graph-3d"), { ssr: false });

const STREAM_BASE = process.env.NEXT_PUBLIC_CEREBROS_API_BASE?.replace(/\/\/$/, "") ?? null;
const SOURCE_COLORS: Record<"git" | "slack" | "tickets" | "support", string> = {
  git: "#22d3ee",
  slack: "#60a5fa",
  tickets: "#fb923c",
  support: "#c084fc",
};

interface GraphNodeBase {
  id: string;
  componentId?: string;
}

type GraphNode =
  | (GraphNodeBase & { kind: "component"; payload: LiveGraphComponent })
  | (GraphNodeBase & { kind: "issue"; payload: LiveGraphIssue; componentId: string })
  | (GraphNodeBase & { kind: "signal"; payload: LiveGraphSignal; componentId: string });

type GraphLink = {
  id: string;
  source: string;
  target: string;
  kind: "dependency" | "issue" | "signal";
  weight: number;
};

type SeverityFilter = "all" | "elevated" | "hot";
type NodeFilter = "components" | "issues";

type TracePath = {
  investigation_id: string;
  question?: string;
  created_at?: string;
  doc_issue_id?: string;
  doc_issue_title?: string;
  evidence: Array<{ id?: string; title?: string; source?: string; url?: string }>;
};

const severityThreshold: Record<SeverityFilter, number> = {
  all: 0,
  elevated: 40,
  hot: 60,
};

export default function ProjectGraphPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const projectSelector = useMemo(() => selectProjectById(projectId), [projectId]);
  const project = useDashboardStore(projectSelector);
  const liveStatus = useDashboardStore((state) => state.liveStatus.mode);
  const modePreference = useDashboardStore((state) => state.modePreference);

  const [snapshot, setSnapshot] = useState<LiveGraphSnapshot | null>(null);
  const [metrics, setMetrics] = useState<GraphMetrics | null>(null);
  const [providerMeta, setProviderMeta] = useState<{ provider: string; fallback?: boolean; updatedAt?: string } | null>(null);
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("all");
  const [nodeFilter, setNodeFilter] = useState<NodeFilter>("components");
  const [selectedComponentId, setSelectedComponentId] = useState<string | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(true);
  const [metricsLoading, setMetricsLoading] = useState(true);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);
  const [traceDialogOpen, setTraceDialogOpen] = useState(false);
  const [tracePaths, setTracePaths] = useState<TracePath[] | null>(null);
  const [traceLoading, setTraceLoading] = useState(false);
  const [traceError, setTraceError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    async function loadSnapshot() {
      setSnapshotLoading(true);
      setSnapshotError(null);
      try {
        const params = new URLSearchParams();
        if (projectId) params.set("projectId", projectId);
        if (modePreference) params.set("mode", modePreference);
        const response = await fetch(`/api/graph-snapshot?${params.toString()}`, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(response.statusText || "Graph snapshot failed");
        }
        const payload = await response.json();
        if (ignore) return;
        setSnapshot(payload.snapshot);
        setProviderMeta({ provider: payload.provider, fallback: payload.fallback, updatedAt: payload.snapshot?.generatedAt });
      } catch (error) {
        if (!ignore) {
          setSnapshot(null);
          setSnapshotError(error instanceof Error ? error.message : "Graph snapshot failed");
        }
      } finally {
        if (!ignore) {
          setSnapshotLoading(false);
        }
      }
    }
    loadSnapshot();
    return () => {
      ignore = true;
    };
  }, [projectId, modePreference]);

  useEffect(() => {
    let ignore = false;
    async function loadMetrics() {
      setMetricsLoading(true);
      try {
        const params = new URLSearchParams();
        if (modePreference) params.set("mode", modePreference);
        const response = await fetch(`/api/graph-metrics${params.size ? `?${params.toString()}` : ""}`, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(response.statusText || "Graph metrics failed");
        }
        const payload = await response.json();
        if (!ignore) {
          setMetrics(payload.metrics);
        }
      } catch (error) {
        if (!ignore) {
          console.error("[graph/page] metrics failed", error);
        }
      } finally {
        if (!ignore) {
          setMetricsLoading(false);
        }
      }
    }
    loadMetrics();
    return () => {
      ignore = true;
    };
  }, [modePreference]);

  useEffect(() => {
    if (!STREAM_BASE) return;
    const source = new EventSource(`${STREAM_BASE}/api/graph/stream`);
    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload?.type === "snapshot") {
          setSnapshot(payload.payload);
          setProviderMeta({ provider: "neo4j", fallback: false, updatedAt: payload.payload?.generatedAt });
        } else if (payload?.type === "metrics") {
          setMetrics(payload.payload);
        }
      } catch (error) {
        console.error("[graph/page] SSE parse error", error);
      }
    };
    source.onerror = () => {
      console.warn("[graph/page] SSE disconnected");
      source.close();
    };
    return () => source.close();
  }, []);

  useEffect(() => {
    if (!snapshot?.components.length) {
      setSelectedComponentId(null);
      return;
    }
    if (selectedComponentId && snapshot.components.some((component) => component.id === selectedComponentId)) {
      return;
    }
    setSelectedComponentId(snapshot.components[0].id);
  }, [snapshot, selectedComponentId]);

  useEffect(() => {
    if (!traceDialogOpen || !selectedComponentId) {
      return;
    }
    let ignore = false;
    async function loadTrace() {
      setTraceLoading(true);
      setTraceError(null);
      try {
        const response = await fetch(
          `/api/traceability/graph-trace?componentId=${encodeURIComponent(selectedComponentId)}&projectId=${projectId ?? ""}`,
          { cache: "no-store" },
        );
        if (!response.ok) {
          throw new Error(response.statusText || "Trace fetch failed");
        }
        const payload = (await response.json()) as { traces?: TracePath[] };
        if (!ignore) {
          setTracePaths(payload.traces ?? []);
        }
      } catch (error) {
        if (!ignore) {
          setTraceError(error instanceof Error ? error.message : "Failed to load trace");
          setTracePaths([]);
        }
      } finally {
        if (!ignore) {
          setTraceLoading(false);
        }
      }
    }
    loadTrace();
    return () => {
      ignore = true;
    };
  }, [traceDialogOpen, selectedComponentId, projectId]);

  const graphData = useMemo(() => buildGraphData(snapshot, severityFilter, nodeFilter), [snapshot, severityFilter, nodeFilter]);
  const selectedComponent = useMemo(
    () => snapshot?.components.find((component) => component.id === selectedComponentId) ?? null,
    [snapshot, selectedComponentId]
  );

  if (!project) {
    return (
      <div className="rounded-2xl border border-dashed border-border/50 p-6 text-sm text-muted-foreground">
        {snapshotLoading ? "Loading project…" : "Project not found."}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.35em] text-muted-foreground">Command center</p>
        <h1 className="text-3xl font-semibold text-foreground">{project.name} documentation drift</h1>
        <p className="text-sm text-muted-foreground">
          Live Neo4j snapshot combining Git, Slack, tickets, and doc issues. Filter down to find the components that are hurting the most.
        </p>
        <LiveModeBadge providerMeta={providerMeta} liveStatus={liveStatus} />
      </header>

      <KpiRow metrics={metrics} loading={metricsLoading} providerMeta={providerMeta} liveStatus={liveStatus} />

      <Card>
        <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle>3D dependency graph</CardTitle>
            <CardDescription>Color = drift, size = blast radius, halos = open doc issues.</CardDescription>
          </div>
          <GraphFilters
            severityFilter={severityFilter}
            nodeFilter={nodeFilter}
            snapshot={snapshot}
            snapshotError={snapshotError}
            onChangeSeverity={(value) => {
              setSeverityFilter(value);
              logClientEvent("graph.filter.severity", { projectId, value });
            }}
            onChangeNodeFilter={(value) => {
              setNodeFilter(value);
              logClientEvent("graph.filter.nodes", { projectId, value });
            }}
            nodeFilterDisabled={!graphData.nodes.length}
          />
        </CardHeader>
        <CardContent>
          {snapshotLoading ? (
            <GraphEmptyState icon="🌀" message="Pulling the live snapshot…" />
          ) : snapshotError ? (
            <GraphEmptyState icon="⚠️" message={snapshotError} />
          ) : graphData.nodes.length ? (
            <GraphCanvas data={graphData} selectedComponentId={selectedComponentId} onSelectComponent={setSelectedComponentId} />
            ) : (
              <GraphEmptyState
              icon="🧭"
                message={
                isLiveLike(liveStatus)
                  ? "No components meet the current filter. Soften the severity threshold."
                  : "Waiting for ingest to populate the graph. Refresh after the next run."
              }
            />
          )}
        </CardContent>
      </Card>

      {selectedComponent ? (
        <ComponentDetailPanel
          component={selectedComponent}
          metrics={metrics}
          projectId={project.id}
          onShowTrace={() => setTraceDialogOpen(true)}
          traceDisabled={!selectedComponentId || traceLoading}
        />
      ) : (
        <GraphEmptyState icon="📌" message="Choose a component to inspect its doc drift dossier." />
      )}

      <TraceDialog
        open={traceDialogOpen}
        onOpenChange={setTraceDialogOpen}
        componentName={selectedComponent?.name ?? selectedComponentId ?? ""}
        traces={tracePaths ?? []}
        loading={traceLoading}
        error={traceError}
        projectId={project.id}
      />

      <AnalyticsSection metrics={metrics} loading={metricsLoading} />
                  </div>
  );
}

function GraphFilters({
  severityFilter,
  nodeFilter,
  snapshot,
  snapshotError,
  onChangeSeverity,
  onChangeNodeFilter,
  nodeFilterDisabled,
}: {
  severityFilter: SeverityFilter;
  nodeFilter: NodeFilter;
  snapshot: LiveGraphSnapshot | null;
  snapshotError: string | null;
  onChangeSeverity: (value: SeverityFilter) => void;
  onChangeNodeFilter: (value: NodeFilter) => void;
  nodeFilterDisabled: boolean;
}) {
  return (
    <div className="flex flex-col gap-3 text-xs text-muted-foreground md:flex-row md:items-center md:justify-end">
      <div className="flex items-center gap-2">
        <Filter className="h-4 w-4 text-primary" />
        <span>
          {snapshotError ? "Graph unavailable" : snapshot ? `${snapshot.componentCount} components` : "Loading…"}
        </span>
                  </div>
      <Tabs value={severityFilter} onValueChange={(value) => onChangeSeverity(value as SeverityFilter)}>
        <TabsList className="grid grid-cols-3">
          <TabsTrigger value="all">All nodes</TabsTrigger>
          <TabsTrigger value="elevated">≥40 drift</TabsTrigger>
          <TabsTrigger value="hot">≥60 drift</TabsTrigger>
        </TabsList>
      </Tabs>
      <Tabs value={nodeFilter} onValueChange={(value) => onChangeNodeFilter(value as NodeFilter)}>
        <TabsList>
          <TabsTrigger value="components">Components</TabsTrigger>
          <TabsTrigger value="issues" disabled={nodeFilterDisabled}>
            Doc issues
          </TabsTrigger>
        </TabsList>
      </Tabs>
                  </div>
  );
}

function GraphCanvas({
  data,
  selectedComponentId,
  onSelectComponent,
}: {
  data: { nodes: GraphNode[]; links: GraphLink[] };
  selectedComponentId: string | null;
  onSelectComponent: (id: string) => void;
}) {
  const graphRef = useRef<ForceGraphMethods>();
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);

  return (
    <div className="relative h-[560px] w-full overflow-hidden rounded-2xl border border-border/50 bg-muted/20">
      <ForceGraph3D
        ref={graphRef}
        graphData={data}
        nodeRelSize={4}
        backgroundColor="#020617"
        enableNodeDrag={false}
        linkOpacity={0.35}
        linkWidth={(link: GraphLink) => (link.kind === "dependency" ? Math.min(4, link.weight * 0.8 + 1) : 1)}
        linkDirectionalParticles={(link: GraphLink) => (link.kind === "dependency" ? Math.min(3, Math.round(link.weight)) : 0)}
        linkDirectionalParticleSpeed={(link: GraphLink) => 0.002 + link.weight * 0.0005}
        nodeThreeObject={(node: GraphNode) => createNodeObject(node, selectedComponentId)}
        onNodeClick={(node) => {
          const typed = node as GraphNode;
          if (typed.kind === "component") {
            onSelectComponent(typed.payload.id);
            graphRef.current?.centerAt(node.x ?? 0, node.y ?? 0, node.z ?? 0, 600);
          }
        }}
        onNodeHover={(node) => setHoveredNode((node as GraphNode) ?? null)}
        showNavInfo={false}
      />
      {hoveredNode ? (
        <div className="pointer-events-none absolute left-4 top-4 max-w-xs rounded-xl border border-border/40 bg-background/95 p-3 text-xs shadow-lg">
          {hoveredNode.kind === "component" ? (
            <>
              <p className="text-sm font-semibold text-foreground">{hoveredNode.payload.name}</p>
              <p className="text-[11px] text-muted-foreground">
                Drift {hoveredNode.payload.driftScore} • Activity {hoveredNode.payload.activityScore}
                </p>
                <p className="text-[11px] text-muted-foreground">
                Blast radius {hoveredNode.payload.blastRadius} • Doc coverage {hoveredNode.payload.docCoverage.state}
              </p>
            </>
          ) : hoveredNode.kind === "issue" ? (
            <>
              <p className="text-sm font-semibold text-foreground">{hoveredNode.payload.docTitle ?? hoveredNode.payload.id}</p>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{hoveredNode.payload.severity}</p>
              <p className="text-[11px] text-muted-foreground">{hoveredNode.payload.summary ?? "Doc drift ticket"}</p>
            </>
          ) : (
            <>
              <p className="text-sm font-semibold text-foreground">{hoveredNode.payload.title ?? hoveredNode.payload.source}</p>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{hoveredNode.payload.source}</p>
              <p className="text-[11px] text-muted-foreground">Weight {hoveredNode.payload.weight.toFixed(2)}</p>
            </>
                    )}
                  </div>
      ) : null}
    </div>
  );
}

type DisplayKpi = {
  key: string;
  label: string;
  value: string | number;
  subtext?: string;
  icon: ReactNode;
};

const KPI_ICON_MAP: Record<string, ReactNode> = {
  doc_freshness: <Activity className="h-4 w-4 text-cyan-400" />,
  dependency_volatility: <GitBranch className="h-4 w-4 text-sky-400" />,
  sla_trend: <AlertCircle className="h-4 w-4 text-rose-400" />,
  support_pressure: <Flame className="h-4 w-4 text-amber-400" />,
};

function formatKpiValue(kpi: GraphKpi): string {
  if (kpi.unit === "%") {
    return `${kpi.value.toFixed(1)}%`;
  }
  if (kpi.unit === "avg_weight" || kpi.unit === "score") {
    return kpi.value.toFixed(2);
  }
  if (Number.isInteger(kpi.value)) {
    return `${kpi.value}`;
  }
  return kpi.value.toFixed(1);
}

function metaNumber(meta: Record<string, unknown> | undefined, key: string): number | undefined {
  if (!meta) return undefined;
  const value = meta[key];
  return typeof value === "number" ? value : undefined;
}

function metaString(meta: Record<string, unknown> | undefined, key: string): string | undefined {
  if (!meta) return undefined;
  const value = meta[key];
  return typeof value === "string" ? value : undefined;
}

function buildKpiSubtext(kpi: GraphKpi): string | undefined {
  const parts: string[] = [];
  if (kpi.key === "doc_freshness") {
    const fresh = metaNumber(kpi.meta, "freshComponents");
    const total = metaNumber(kpi.meta, "coveredComponents");
    if (typeof fresh === "number" && typeof total === "number" && total > 0) {
      parts.push(`${fresh}/${total} recent`);
    }
  } else if (kpi.key === "sla_trend") {
    const overdue = metaNumber(kpi.meta, "overdueComponents");
    if (typeof overdue === "number") {
      parts.push(`${overdue} overdue`);
    }
  } else if (kpi.key === "dependency_volatility") {
    const component = metaString(kpi.meta, "topComponentName");
    if (component) {
      parts.push(component);
    }
  } else if (kpi.key === "support_pressure") {
    const topSupport = metaString(kpi.meta, "topComponentName");
    if (topSupport) {
      parts.push(topSupport);
    }
  }

  if (typeof kpi.trend === "number") {
    const unitSuffix = kpi.unit === "%" ? "%" : "";
    const formatted = `${kpi.trend > 0 ? "+" : ""}${kpi.trend.toFixed(kpi.unit === "%" ? 1 : 2)}${unitSuffix}`;
    parts.push(`Δ ${formatted}`);
  }

  return parts.length ? parts.join(" · ") : undefined;
}

function buildFallbackKpis(loading: boolean, metrics: GraphMetrics | null): DisplayKpi[] {
  return [
    {
      key: "docDriftIndex",
      label: "Doc drift index",
      value: loading ? "…" : metrics ? `${metrics.docDriftIndex.toFixed(1)}/100` : "n/a",
      subtext: metrics?.docDriftChange != null ? `Δ ${metrics.docDriftChange.toFixed(1)}` : undefined,
      icon: <Activity className="h-4 w-4 text-cyan-400" />,
    },
    {
      key: "openDocIssues",
      label: "Open doc issues",
      value: loading ? "…" : metrics ? metrics.openDocIssues : "n/a",
      subtext: metrics ? `${metrics.criticalDocIssues} critical` : undefined,
      icon: <AlertCircle className="h-4 w-4 text-rose-400" />,
    },
    {
      key: "redZoneComponents",
      label: "Red-zone components",
      value: loading ? "…" : metrics ? metrics.redZoneComponents : "n/a",
      icon: <Flame className="h-4 w-4 text-amber-400" />,
    },
  ];
}

function KpiRow({
  metrics,
  loading,
  providerMeta,
  liveStatus,
}: {
  metrics: GraphMetrics | null;
  loading: boolean;
  providerMeta: { provider: string; fallback?: boolean; updatedAt?: string } | null;
  liveStatus: string;
}) {
  const liveKpis: DisplayKpi[] =
    !loading && metrics?.kpis?.length
      ? metrics.kpis.map((kpi) => ({
          key: kpi.key,
          label: kpi.label,
          value: formatKpiValue(kpi),
          subtext: buildKpiSubtext(kpi),
          icon: KPI_ICON_MAP[kpi.key] ?? <Activity className="h-4 w-4 text-cyan-400" />,
        }))
      : [];

  const cards: DisplayKpi[] = (liveKpis.length ? liveKpis : buildFallbackKpis(loading, metrics)).concat([
    {
      key: "live-feed",
      label: "Live feed",
      value:
        providerMeta
          ? `${providerMeta.provider}${providerMeta.fallback ? " (fallback)" : ""}`
          : isLiveLike(liveStatus)
          ? "streaming"
          : "synthetic",
      subtext: providerMeta?.updatedAt ? `Updated ${shortDate(providerMeta.updatedAt)}` : undefined,
      icon: <Signal className="h-4 w-4 text-emerald-300" />,
    },
  ]);

              return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
      {cards.map((card) => (
        <KpiCard key={card.key} label={card.label} value={card.value} subtext={card.subtext} icon={card.icon} />
      ))}
    </div>
  );
}

function KpiCard({ label, value, subtext, icon }: { label: string; value: string | number; subtext?: string; icon: ReactNode }) {
              return (
    <Card>
      <CardContent className="flex items-center justify-between gap-3 p-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
          <p className="text-2xl font-semibold text-foreground">{value}</p>
          {subtext ? <p className="text-xs text-muted-foreground">{subtext}</p> : null}
                  </div>
        <div className="rounded-full border border-border/40 bg-muted/30 p-3">{icon}</div>
        </CardContent>
      </Card>
  );
}

function LiveModeBadge({
  providerMeta,
  liveStatus,
}: {
  providerMeta: { provider: string; fallback?: boolean } | null;
  liveStatus: string;
}) {
  const provider = providerMeta?.provider ?? (isLiveLike(liveStatus as never) ? "neo4j" : "synthetic");
  const fallback = Boolean(providerMeta?.fallback);
  const tone =
    fallback && provider !== "neo4j"
      ? "border-amber-400/60 bg-amber-500/10 text-amber-200"
      : provider === "neo4j"
      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
      : "border-border/60 bg-muted/20 text-muted-foreground";
  const label = fallback
    ? "Fallback mode"
    : provider === "neo4j"
    ? "Live Atlas data"
    : "Synthetic dataset";

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${tone}`}
    >
      <Signal className="h-3 w-3" />
      {label}
    </span>
  );
}

function ComponentDetailPanel({
  component,
  metrics,
  projectId,
  onShowTrace,
  traceDisabled,
}: {
  component: LiveGraphComponent;
  metrics: GraphMetrics | null;
  projectId: string;
  onShowTrace?: () => void;
  traceDisabled?: boolean;
}) {
  const issues = component.issues ?? [];
  const signals = component.signals ?? [];
  const openIssues = issues.filter((issue) => issue.state === "open" || issue.state === "active");
  const primaryIssue = openIssues[0];

  return (
    <Card>
      <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div>
          <CardTitle className="flex items-center gap-2">
            {component.name}
            <Badge variant="secondary" className="uppercase">
              Drift {component.driftScore}
            </Badge>
            <Badge variant="outline" className="uppercase">
              Blast {component.blastRadius}
            </Badge>
          </CardTitle>
          <CardDescription className="text-xs">
            {component.tags.join(" · ") || "No tags"} • Dominant signal {component.dominantSignal ?? "n/a"}
          </CardDescription>
      </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <Button asChild size="sm" variant="secondary">
            <Link href={`/projects/${projectId}/components/${component.id}`} className="inline-flex items-center gap-1">
              Open detail
              <ArrowRight className="h-3 w-3" />
          </Link>
        </Button>
      </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" className="rounded-full text-xs" onClick={onShowTrace} disabled={traceDisabled}>
            Show trace
          </Button>
    </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-4 md:grid-cols-4">
          <DetailStat label="Drift score" value={component.driftScore} icon={<Flame className="h-4 w-4 text-amber-400" />} />
          <DetailStat label="Activity score" value={component.activityScore} icon={<GitBranch className="h-4 w-4 text-cyan-300" />} />
          <DetailStat label="Change velocity" value={component.changeVelocity} icon={<Activity className="h-4 w-4 text-sky-300" />} />
          <DetailStat label="Open issues" value={openIssues.length} icon={<AlertCircle className="h-4 w-4 text-rose-400" />} />
    </div>

        {primaryIssue ? (
          <div className="rounded-2xl border border-border/40 bg-muted/10 p-4 text-sm">
            <p className="text-xs uppercase text-muted-foreground">Primary doc issue</p>
            <p className="text-base font-semibold text-foreground">{primaryIssue.docTitle ?? primaryIssue.id}</p>
            <p className="text-xs text-muted-foreground">{primaryIssue.summary ?? "Doc drift issue"}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
              <Badge variant="outline">{primaryIssue.severity}</Badge>
              <span>{shortDate(primaryIssue.updatedAt ?? primaryIssue.createdAt ?? new Date().toISOString())}</span>
  </div>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">No open doc issues for this component.</p>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-border/40 bg-muted/5 p-4 text-sm">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Doc issues · {issues.length}</p>
            <div className="mt-2 space-y-2">
              {issues.slice(0, 4).map((issue) => (
                <div key={issue.id} className="rounded-xl border border-border/30 p-3">
                  <p className="text-xs uppercase text-muted-foreground">{issue.severity}</p>
                  <p className="text-sm font-semibold text-foreground">{issue.docTitle ?? issue.id}</p>
                  <p className="text-xs text-muted-foreground">{issue.summary ?? "Missing summary"}</p>
      </div>
              ))}
              {!issues.length ? <p className="text-xs text-muted-foreground">No doc tickets yet.</p> : null}
            </div>
          </div>
          <div className="rounded-2xl border border-border/40 bg-muted/5 p-4 text-sm">
            <p className="text-xs font-semibold uppercase text-muted-foreground">Signals · {signals.length}</p>
            <div className="mt-2 space-y-2">
              {signals.slice(0, 4).map((signal) => (
                <div key={signal.id} className="flex items-center justify-between rounded-xl border border-border/30 p-3">
                  <div>
                    <p className="text-sm font-semibold text-foreground">{signal.title ?? signal.source}</p>
                    <p className="text-xs text-muted-foreground">Weight {signal.weight.toFixed(2)}</p>
                  </div>
                  <Badge variant="outline" style={{ borderColor: SOURCE_COLORS[signal.source], color: SOURCE_COLORS[signal.source] }}>
                    {signal.source}
              </Badge>
        </div>
              ))}
              {!signals.length ? <p className="text-xs text-muted-foreground">No recent support signals.</p> : null}
    </div>
          </div>
        </div>

        {metrics ? (
          <p className="text-[11px] text-muted-foreground">
            Suggested next step: focus on {metrics.topRisks[0]?.componentName ?? component.name} to push the drift index below {metrics.docDriftIndex.toFixed(1)}.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function TraceDialog({
  open,
  onOpenChange,
  componentName,
  traces,
  loading,
  error,
  projectId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  componentName: string;
  traces: TracePath[];
  loading: boolean;
  error: string | null;
  projectId: string;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Trace path for {componentName}</DialogTitle>
          <DialogDescription>Investigation → Evidence → Doc Issue relationships stored in Neo4j.</DialogDescription>
        </DialogHeader>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading trace…</p>
        ) : error ? (
          <div className="rounded-2xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-100">{error}</div>
        ) : traces.length === 0 ? (
          <p className="text-sm text-muted-foreground">No traceable investigations connected to this component yet.</p>
        ) : (
          <div className="space-y-3">
            {traces.map((trace) => {
              const investigationUrl = buildInvestigationUrl(trace.investigation_id);
              return (
                <div key={trace.investigation_id} className="rounded-2xl border border-border/50 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-foreground">{trace.question ?? "Investigation"}</p>
      <p className="text-xs text-muted-foreground">
                      {trace.created_at ? `Created ${shortDate(trace.created_at)}` : "Created recently"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {trace.doc_issue_id ? (
                      <Button variant="ghost" size="sm" className="rounded-full text-xs" asChild>
                        <a href={`/projects/${projectId}/issues/${trace.doc_issue_id}`} className="flex items-center gap-1">
                          Open issue
                          <ArrowRight className="h-4 w-4" />
          </a>
        </Button>
      ) : null}
                    {investigationUrl ? (
                      <Button variant="outline" size="sm" className="rounded-full text-xs" asChild>
                        <a href={investigationUrl} target="_blank" rel="noreferrer">
                          View run
                        </a>
                      </Button>
                    ) : null}
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  Doc Issue: {trace.doc_issue_title ?? trace.doc_issue_id ?? "n/a"}
                </p>
                <div className="mt-3 space-y-1">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Evidence</p>
                  {trace.evidence.length ? (
                    <div className="flex flex-wrap gap-2">
                      {trace.evidence.map((ev) => (
                        <Badge key={ev.id ?? ev.url} variant="outline" className="rounded-full border-border/60">
                          {ev.title ?? ev.url ?? ev.source ?? "Evidence"}
                        </Badge>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">No evidence nodes recorded.</p>
                  )}
                </div>
                </div>
              );
            })}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function DetailStat({ label, value, icon }: { label: string; value: string | number; icon: ReactNode }) {
  return (
    <div className="rounded-2xl border border-border/40 bg-muted/5 p-4">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        {icon}
      </div>
      <p className="text-2xl font-semibold text-foreground">{value}</p>
    </div>
  );
}

function AnalyticsSection({ metrics, loading }: { metrics: GraphMetrics | null; loading: boolean }) {
  if (!metrics && !loading) {
    return <GraphEmptyState icon="📊" message="Metrics unavailable — is the backend running?" />;
  }

  const riskData = metrics?.riskQuadrant ?? [];
  const topRisks = metrics?.topRisks ?? [];
  const sourceMix = metrics
    ? Object.entries(metrics.sourceMix).map(([source, value]) => ({ source, value }))
    : [];
  const timeline = metrics?.issueTimeline ?? [];

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Risk quadrant</CardTitle>
          <CardDescription>Recent change velocity vs doc drift score.</CardDescription>
        </CardHeader>
        <CardContent className="h-[280px]">
          {loading ? (
            <GraphEmptyState icon="🌀" message="Loading metrics…" />
          ) : (
            <ResponsiveContainer>
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.25)" />
                <XAxis type="number" dataKey="changeVelocity" name="Change velocity" stroke="#94a3b8" />
                <YAxis type="number" dataKey="driftScore" name="Drift score" stroke="#94a3b8" />
                <RechartsTooltip cursor={{ strokeDasharray: "3 3" }} />
                <Scatter data={riskData} fill="#60a5fa" />
              </ScatterChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Top risky components</CardTitle>
          <CardDescription>Composite score combining drift, support load, and blast radius.</CardDescription>
        </CardHeader>
        <CardContent className="h-[280px]">
          {loading ? (
            <GraphEmptyState icon="🌀" message="Loading metrics…" />
          ) : (
            <ResponsiveContainer>
              <BarChart data={topRisks}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.25)" />
                <XAxis dataKey="componentName" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <RechartsTooltip cursor={{ fill: "rgba(148,163,184,0.1)" }} />
                <Bar dataKey="riskScore" fill="#fb7185" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Signal mix</CardTitle>
          <CardDescription>Where drift pressure is originating.</CardDescription>
        </CardHeader>
        <CardContent className="h-[280px]">
          {loading ? (
            <GraphEmptyState icon="🌀" message="Loading metrics…" />
          ) : (
            <ResponsiveContainer>
              <PieChart>
                <Pie data={sourceMix} dataKey="value" nameKey="source" innerRadius={60} outerRadius={90} paddingAngle={4}>
                  {sourceMix.map((entry) => (
                    <Cell key={entry.source} fill={SOURCE_COLORS[entry.source as keyof typeof SOURCE_COLORS] ?? "#94a3b8"} />
                  ))}
                </Pie>
                <RechartsTooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Doc issue cadence</CardTitle>
          <CardDescription>New vs resolved issues over the last two weeks.</CardDescription>
        </CardHeader>
        <CardContent className="h-[280px]">
          {loading ? (
            <GraphEmptyState icon="🌀" message="Loading metrics…" />
          ) : (
            <ResponsiveContainer>
              <AreaChart data={timeline}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.25)" />
                <XAxis dataKey="date" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <RechartsTooltip />
                <Area type="monotone" dataKey="opened" stroke="#fb923c" fill="rgba(251,146,60,0.35)" />
                <Area type="monotone" dataKey="resolved" stroke="#34d399" fill="rgba(52,211,153,0.35)" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function GraphEmptyState({ icon, message }: { icon: string; message: string }) {
  return (
    <div className="flex h-[220px] flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-border/50 bg-muted/10 text-sm text-muted-foreground">
      <span className="text-2xl">{icon}</span>
      <p className="text-center text-xs text-muted-foreground">{message}</p>
      </div>
  );
}

function buildGraphData(snapshot: LiveGraphSnapshot | null, severityFilter: SeverityFilter, nodeFilter: NodeFilter): {
  nodes: GraphNode[];
  links: GraphLink[];
} {
  if (!snapshot) {
    return { nodes: [], links: [] };
  }

  const minScore = severityThreshold[severityFilter];
  const nodes: GraphNode[] = [];
  const links: GraphLink[] = [];
  const componentIds = new Set<string>();

  snapshot.components
    .filter((component) => component.driftScore >= minScore)
    .forEach((component) => {
      nodes.push({ id: component.id, kind: "component", payload: component });
      componentIds.add(component.id);
    });

  (snapshot.dependencies ?? []).forEach((dependency) => {
    if (componentIds.has(dependency.source) && componentIds.has(dependency.target)) {
      links.push({
        id: dependency.id,
        source: dependency.source,
        target: dependency.target,
        kind: "dependency",
        weight: dependency.impactWeight ?? 1,
      });
    }
  });

  if (nodeFilter === "issues") {
    snapshot.components.forEach((component) => {
      if (!componentIds.has(component.id)) return;
      (component.issues ?? []).slice(0, 4).forEach((issue) => {
        nodes.push({ id: issue.id, kind: "issue", payload: issue, componentId: component.id });
        links.push({ id: `${issue.id}->${component.id}`, source: issue.id, target: component.id, kind: "issue", weight: 1 });
      });
      (component.signals ?? []).slice(0, 4).forEach((signal) => {
        const signalId = `${component.id}:${signal.id}`;
        nodes.push({ id: signalId, kind: "signal", payload: signal, componentId: component.id });
        links.push({
          id: `${signalId}->${component.id}`,
          source: signalId,
          target: component.id,
          kind: "signal",
          weight: Math.max(1, signal.weight),
        });
      });
    });
  }

  return { nodes, links };
}

function createNodeObject(node: GraphNode, selectedComponentId: string | null) {
  if (node.kind === "component") {
    const size = 6 + Math.min(12, node.payload.blastRadius * 2);
    const color = driftColor(node.payload.driftScore);
    const group = new THREE.Group();
    const sphere = new THREE.Mesh(new THREE.SphereGeometry(size, 24, 24), new THREE.MeshBasicMaterial({ color }));
    group.add(sphere);
    if (node.payload.openIssues > 0) {
      const halo = new THREE.Mesh(
        new THREE.SphereGeometry(size * 1.5, 24, 24),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: selectedComponentId === node.payload.id ? 0.35 : 0.15 })
      );
      group.add(halo);
    }
    return group;
  }

  if (node.kind === "issue") {
    const severityColor: Record<string, string> = {
      critical: "#f87171",
      high: "#fb923c",
      medium: "#facc15",
      low: "#34d399",
    };
    return new THREE.Mesh(
      new THREE.SphereGeometry(3.5, 16, 16),
      new THREE.MeshBasicMaterial({ color: severityColor[node.payload.severity] ?? "#e5e7eb" })
    );
  }

  return new THREE.Mesh(
    new THREE.BoxGeometry(3, 3, 3),
    new THREE.MeshBasicMaterial({ color: SOURCE_COLORS[node.payload.source] })
  );
}

function driftColor(score: number) {
  if (score >= 70) return "#f87171";
  if (score >= 50) return "#fb923c";
  if (score >= 40) return "#facc15";
  return "#22d3ee";
}
