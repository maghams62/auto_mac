import type { IncidentEntity, IncidentRecord, InvestigationEvidence, SeveritySemanticPair } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useMemo } from "react";

type SourceBucketKey = "slack" | "git" | "doc" | "tickets" | "support" | "graph" | "other";

type SourceBucket = {
  key: SourceBucketKey;
  label: string;
  value: number;
  color: string;
};

type SeveritySlice = {
  key: string;
  label: string;
  value: number;
  color: string;
};

type DriftScoreSide = {
  leftRaw: number;
  rightRaw: number;
  left: number;
  right: number;
  entity: IncidentEntity;
  sourcesLabel: string;
};

type HeatmapCellState = "none" | "present" | "drift";

type HeatmapRow = {
  entity: IncidentEntity;
  cells: {
    docs: HeatmapCellState;
    slack: HeatmapCellState;
    git: HeatmapCellState;
    tickets: HeatmapCellState;
    support: HeatmapCellState;
  };
};

type TimelineBucket = {
  start: Date;
  count: number;
};

type GraphSummaryNode = {
  label: string;
  count: number;
};

type GraphSummaryEdge = {
  label: string;
  count: number;
};

type GraphSummary = {
  nodes: GraphSummaryNode[];
  edges: GraphSummaryEdge[];
};

interface IncidentVisualizationsProps {
  incident: IncidentRecord;
  evidenceItems: InvestigationEvidence[];
}

export default function IncidentVisualizations({ incident, evidenceItems }: IncidentVisualizationsProps) {
  const sourceBuckets = useMemo(() => buildSourceBuckets(incident, evidenceItems), [incident, evidenceItems]);
  const severitySlices = useMemo(() => buildSeveritySlices(incident), [incident]);
  const driftScore = useMemo(() => buildDriftScore(incident), [incident]);
  const heatmapRows = useMemo(() => buildHeatmapRows(incident), [incident]);
  const timelineBuckets = useMemo(() => buildTimelineBuckets(evidenceItems), [evidenceItems]);
  const graphSummary = useMemo(() => buildGraphSummary(incident), [incident]);

  const hasSource = sourceBuckets && sourceBuckets.length >= 2;
  const hasSeverity = severitySlices && severitySlices.length >= 2;
  const hasDrift = Boolean(driftScore);
  const hasHeatmap = heatmapRows && heatmapRows.length >= 2;
  const hasTimeline = timelineBuckets && timelineBuckets.length >= 3;
  const hasGraphSummary = Boolean(graphSummary && (graphSummary.nodes.length || graphSummary.edges.length));

  const hasAny =
    hasSource ||
    hasSeverity ||
    hasDrift ||
    hasHeatmap ||
    hasTimeline ||
    hasGraphSummary;

  if (!hasAny) {
    return null;
  }

  return (
    <section className="space-y-4 rounded-3xl border border-border/50 bg-background/70 p-5">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Visualizations</h2>
          <p className="text-xs text-muted-foreground">
            Quick visual read on sources, severity, doc drift, and entity-level signals.
          </p>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <SourceBreakdownCard buckets={sourceBuckets} />
        <SeverityMiniBarCard slices={severitySlices} />
        <GraphSliceSummaryCard summary={graphSummary} />
      </div>

      <DocDriftDivergingBarCard score={driftScore} />
      <DriftHeatmapCard rows={heatmapRows} />
      <TimelineSparklineCard buckets={timelineBuckets} />
    </section>
  );
}

function GraphSliceSummaryCard({ summary }: { summary: GraphSummary | null }) {
  if (!summary) {
    return null;
  }
  const hasNodes = summary.nodes.length > 0;
  const hasEdges = summary.edges.length > 0;
  if (!hasNodes && !hasEdges) {
    return null;
  }

  return (
    <div className="space-y-3 rounded-2xl border border-border/50 bg-background/70 p-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Graph scope for this incident</h3>
          <p className="text-xs text-muted-foreground">
            Approximate nodes and relationships touched by this incident&apos;s dependency walk.
          </p>
        </div>
      </div>
      <div className="space-y-2 text-xs">
        {hasNodes ? (
          <div>
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Nodes</p>
            <div className="flex flex-wrap gap-1.5">
              {summary.nodes.map((node) => (
                <span
                  key={node.label}
                  className="inline-flex items-center rounded-full border border-border/60 bg-background/60 px-2 py-0.5 text-[11px] text-foreground"
                >
                  <span className="mr-1 text-[10px] uppercase tracking-wide text-muted-foreground">{node.label}</span>
                  <span className="font-semibold">{node.count}</span>
                </span>
              ))}
            </div>
          </div>
        ) : null}
        {hasEdges ? (
          <div>
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Relationships
            </p>
            <div className="flex flex-wrap gap-1.5">
              {summary.edges.map((edge) => (
                <span
                  key={edge.label}
                  className="inline-flex items-center rounded-full border border-border/60 bg-background/60 px-2 py-0.5 text-[11px] text-foreground"
                >
                  <span className="mr-1 text-[10px] uppercase tracking-wide text-muted-foreground">{edge.label}</span>
                  <span className="font-semibold">{edge.count}</span>
                </span>
              ))}
            </div>
          </div>
        ) : null}
      </div>
      {hasNodes && hasEdges ? (
        <details className="mt-1 rounded-2xl border border-border/60 bg-background/60 p-2 text-[11px] text-muted-foreground">
          <summary className="cursor-pointer text-foreground">How we count this</summary>
          <p className="mt-1">
            Node counts come from the structured incident scope (components, docs, tickets, Slack threads, Git refs).
            Relationship counts are derived from dependency impact edges (components depending on components, docs, and
            services).
          </p>
        </details>
      ) : null}
    </div>
  );
}

function SourceBreakdownCard({ buckets }: { buckets: SourceBucket[] | null }) {
  if (!buckets || buckets.length < 2) {
    return null;
  }
  const total = buckets.reduce((sum, b) => sum + b.value, 0);
  if (!Number.isFinite(total) || total <= 0) {
    return null;
  }

  return (
    <div className="space-y-3 rounded-2xl border border-border/50 bg-background/70 p-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Source breakdown</h3>
          <p className="text-xs text-muted-foreground">Where the strongest evidence came from.</p>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <DonutChart buckets={buckets} />
        <div className="space-y-1 text-xs">
          {buckets.map((bucket) => {
            const pct = (bucket.value / total) * 100;
            return (
              <div key={bucket.key} className="flex items-center gap-2">
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ backgroundColor: bucket.color }}
                />
                <span className="text-muted-foreground">
                  {bucket.label}{" "}
                  <span className="font-semibold text-foreground">
                    {pct.toFixed(0)}%
                  </span>
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function DonutChart({ buckets }: { buckets: SourceBucket[] }) {
  const total = buckets.reduce((sum, b) => sum + b.value, 0);
  if (!Number.isFinite(total) || total <= 0 || buckets.length < 2) {
    return null;
  }
  const radius = 24;
  const strokeWidth = 10;
  const circumference = 2 * Math.PI * radius;

  let offset = 0;

  return (
    <svg
      width={72}
      height={72}
      viewBox="0 0 72 72"
      className="shrink-0"
    >
      <g transform="translate(36,36) rotate(-90)">
        {buckets.map((bucket) => {
          const fraction = bucket.value / total;
          const arcLength = circumference * fraction;
          const dashArray = `${arcLength} ${circumference - arcLength}`;
          const dashOffset = -offset;
          offset += arcLength;
          return (
            <circle
              key={bucket.key}
              r={radius}
              fill="transparent"
              stroke={bucket.color}
              strokeWidth={strokeWidth}
              strokeDasharray={dashArray}
              strokeDashoffset={dashOffset}
              strokeLinecap="butt"
            />
          );
        })}
      </g>
      <circle
        cx={36}
        cy={36}
        r={radius - strokeWidth}
        className="fill-background/90"
      />
    </svg>
  );
}

function SeverityMiniBarCard({ slices }: { slices: SeveritySlice[] | null }) {
  if (!slices || slices.length < 2) {
    return null;
  }
  const total = slices.reduce((sum, s) => sum + s.value, 0);
  if (!Number.isFinite(total) || total <= 0) {
    return null;
  }

  return (
    <div className="space-y-3 rounded-2xl border border-border/50 bg-background/70 p-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Severity by modality</h3>
          <p className="text-xs text-muted-foreground">Relative share of CRT severity by source family.</p>
        </div>
      </div>
      <div className="space-y-2">
        <div className="flex h-3 overflow-hidden rounded-full border border-border/50 bg-background/60">
          {slices.map((slice) => {
            const share = slice.value / total;
            if (!Number.isFinite(share) || share <= 0) return null;
            return (
              <div
                key={slice.key}
                className="h-full"
                style={{
                  width: `${share * 100}%`,
                  backgroundColor: slice.color,
                }}
              />
            );
          })}
        </div>
        <p className="text-[11px] text-muted-foreground">
          {slices
            .map((slice) => {
              const share = slice.value / total;
              if (!Number.isFinite(share) || share <= 0) return null;
              return `${slice.label} ${(share * 100).toFixed(0)}%`;
            })
            .filter(Boolean)
            .join(" · ")}
        </p>
      </div>
    </div>
  );
}

function DocDriftDivergingBarCard({ score }: { score: DriftScoreSide | null }) {
  if (!score || score.leftRaw <= 0 || score.rightRaw <= 0) {
    return null;
  }

  const leftWidth = `${(score.left * 100).toFixed(0)}%`;
  const rightWidth = `${(score.right * 100).toFixed(0)}%`;

  return (
    <div className="space-y-3 rounded-2xl border border-amber-500/40 bg-amber-500/5 p-4">
      <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Doc drift vs live signals</h3>
          <p className="text-xs text-amber-100/80">
            Strongest entity-level mismatch between outdated docs and live activity.
          </p>
        </div>
        <p className="text-xs text-amber-100/80">
          Focus:{" "}
          <span className="font-semibold text-amber-50">
            {score.entity.name}
          </span>
        </p>
      </div>

      <div className="relative mt-1 flex items-center justify-between gap-3 text-[11px] text-amber-50">
        <div className="w-1/2">
          <div className="flex items-center justify-end gap-2">
            <span className="truncate text-right">
              Outdated docs &amp; gaps ({score.entity.name})
            </span>
          </div>
        </div>
        <div className="w-px self-stretch bg-amber-500/40" />
        <div className="w-1/2">
          <div className="flex items-center gap-2">
            <span className="truncate">
              Live signals ({score.sourcesLabel})
            </span>
          </div>
        </div>
      </div>

      <div className="relative mt-1 h-6 rounded-full border border-amber-500/40 bg-background/60">
        <div className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-amber-500/60" />
        <div className="flex h-full">
          <div className="relative w-1/2">
            <div
              className="absolute right-1 top-1/2 h-3 -translate-y-1/2 rounded-full bg-amber-400/80"
              style={{ width: leftWidth }}
            />
          </div>
          <div className="relative w-1/2">
            <div
              className="absolute left-1 top-1/2 h-3 -translate-y-1/2 rounded-full bg-emerald-400/80"
              style={{ width: rightWidth }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function DriftHeatmapCard({ rows }: { rows: HeatmapRow[] | null }) {
  if (!rows || rows.length < 2) {
    return null;
  }

  const columns = ["Docs", "Slack", "Git", "Tickets", "Support"] as const;

  return (
    <div className="space-y-3 rounded-2xl border border-border/50 bg-background/70 p-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Drift & signals across entities</h3>
          <p className="text-xs text-muted-foreground">
            Where docs, Slack, Git, tickets, and support light up for each entity.
          </p>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-[520px] text-xs">
          <thead>
            <tr className="text-[10px] uppercase tracking-wide text-muted-foreground">
              <th className="py-1 pr-3 text-left">Entity</th>
              {columns.map((col) => (
                <th key={col} className="px-2 py-1 text-center">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.entity.id} className="border-t border-border/30 text-foreground">
                <td className="py-1.5 pr-3">
                  <div className="max-w-[180px] truncate text-xs font-medium">{row.entity.name}</div>
                </td>
                {columns.map((col) => {
                  const state = row.cells[col.toLowerCase() as keyof HeatmapRow["cells"]];
                  return (
                    <td key={col} className="px-2 py-1">
                      <HeatmapCell state={state} />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-[10px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="h-3 w-3 rounded border border-border/50 bg-background/60" /> Low / none
        </span>
        <span className="flex items-center gap-1">
          <span className="h-3 w-3 rounded bg-emerald-500/40" /> Present
        </span>
        <span className="flex items-center gap-1">
          <span className="h-3 w-3 rounded bg-amber-500/70" /> Drift / contradiction
        </span>
      </div>
    </div>
  );
}

function HeatmapCell({ state }: { state: HeatmapCellState }) {
  if (state === "none") {
    return <div className="h-4 w-4 rounded border border-border/50 bg-background/60" />;
  }
  if (state === "present") {
    return <div className="h-4 w-4 rounded bg-emerald-500/40" />;
  }
  return <div className="h-4 w-4 rounded bg-amber-500/70" />;
}

function TimelineSparklineCard({ buckets }: { buckets: TimelineBucket[] | null }) {
  if (!buckets || buckets.length < 3) {
    return null;
  }
  const total = buckets.reduce((sum, b) => sum + b.count, 0);
  if (!Number.isFinite(total) || total <= 0) {
    return null;
  }

  const spanMs = buckets[buckets.length - 1].start.getTime() - buckets[0].start.getTime();
  const mostRecent = buckets[buckets.length - 1].start;

  let caption: string | null = null;
  if (spanMs <= 48 * 60 * 60 * 1000) {
    caption = "Most activity in the last 48h window.";
  } else if (spanMs <= 7 * 24 * 60 * 60 * 1000) {
    caption = "Most activity clustered within the last week.";
  } else {
    caption = "Activity spread over a longer period.";
  }

  return (
    <div className="space-y-3 rounded-2xl border border-border/50 bg-background/70 p-4">
      <div>
        <h3 className="text-sm font-semibold text-foreground">Activity timeline</h3>
        <p className="text-xs text-muted-foreground">
          When evidence arrived for this incident.
        </p>
      </div>
      <Sparkline buckets={buckets} />
      <p className="text-[11px] text-muted-foreground">
        When activity clustered for this incident.{" "}
        <span className="text-foreground/90">{caption}</span>{" "}
        <span className="text-muted-foreground/80">
          Last event around {mostRecent.toLocaleString()}.
        </span>
      </p>
    </div>
  );
}

function Sparkline({ buckets }: { buckets: TimelineBucket[] }) {
  if (!buckets.length) return null;
  const width = 160;
  const height = 32;
  const maxCount = buckets.reduce((max, b) => (b.count > max ? b.count : max), 0);
  if (!Number.isFinite(maxCount) || maxCount <= 0) {
    return null;
  }

  const step = buckets.length > 1 ? width / (buckets.length - 1) : width;
  const points = buckets
    .map((bucket, index) => {
      const x = index * step;
      const y = height - (bucket.count / maxCount) * height;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="w-full max-w-xs"
    >
      <polyline
        fill="none"
        stroke="rgb(45, 212, 191)"
        strokeWidth="2"
        points={points}
      />
    </svg>
  );
}

function buildGraphSummary(incident: IncidentRecord): GraphSummary | null {
  const metadata = (incident.metadata ?? {}) as Record<string, unknown>;
  const candidate = (metadata.incident_candidate_snapshot ?? {}) as {
    incident_scope?: Record<string, unknown>;
    impacted_nodes?: Record<string, unknown>;
  };

  const scope =
    (incident.incidentScope as Record<string, unknown> | undefined) ??
    (candidate.incident_scope as Record<string, unknown> | undefined) ??
    (candidate.impacted_nodes as Record<string, unknown> | undefined) ??
    {};
  const dependency = incident.dependencyImpact;

  const components = Array.isArray(scope.components) ? scope.components.length : 0;
  const docs = Array.isArray(scope.doc_ids) ? scope.doc_ids.length : 0;
  const issues = Array.isArray(scope.issue_ids) ? scope.issue_ids.length : 0;
  const slackThreads = Array.isArray(scope.slack_threads) ? scope.slack_threads.length : 0;
  const gitRefs = Array.isArray(scope.git_refs) ? scope.git_refs.length : 0;

  const nodes: GraphSummaryNode[] = [];
  if (components > 0) nodes.push({ label: "Components", count: components });
  if (docs > 0) nodes.push({ label: "Docs", count: docs });
  if (issues > 0) nodes.push({ label: "Tickets", count: issues });
  if (slackThreads > 0) nodes.push({ label: "Slack threads", count: slackThreads });
  if (gitRefs > 0) nodes.push({ label: "Git refs", count: gitRefs });

  const edges: GraphSummaryEdge[] = [];
  const impacts = dependency?.impacts ?? [];
  if (Array.isArray(impacts) && impacts.length > 0) {
    let componentEdges = 0;
    let docEdges = 0;
    let serviceEdges = 0;
    let apiEdges = 0;

    for (const impact of impacts) {
      const dependents = impact.dependentComponents ?? [];
      const docsList = impact.docs ?? [];
      const servicesList = impact.services ?? [];
      const apisList = impact.exposedApis ?? [];
      if (dependents.length) componentEdges += dependents.length;
      if (docsList.length) docEdges += docsList.length;
      if (servicesList.length) serviceEdges += servicesList.length;
      if (apisList.length) apiEdges += apisList.length;
    }

    if (componentEdges > 0) {
      edges.push({ label: "Component → component", count: componentEdges });
    }
    if (docEdges > 0) {
      edges.push({ label: "Component → doc", count: docEdges });
    }
    if (serviceEdges > 0) {
      edges.push({ label: "Component → service", count: serviceEdges });
    }
    if (apiEdges > 0) {
      edges.push({ label: "Component → API", count: apiEdges });
    }
  }

  const hasNodes = nodes.length > 0;
  const hasEdges = edges.length > 0;
  if (!hasNodes && !hasEdges) {
    return null;
  }

  return { nodes, edges };
}

function buildSourceBuckets(incident: IncidentRecord, evidenceItems: InvestigationEvidence[]): SourceBucket[] | null {
  const colorByKey: Record<SourceBucketKey, string> = {
    slack: "rgb(59,130,246)", // blue-500
    git: "rgb(16,185,129)", // emerald-500
    doc: "rgb(245,158,11)", // amber-500
    tickets: "rgb(244,63,94)", // rose-500
    support: "rgb(56,189,248)", // sky-500
    graph: "rgb(147,51,234)", // purple-600
    other: "rgb(148,163,184)", // gray-400
  };

  const buckets: Map<SourceBucketKey, number> = new Map();
  const bump = (key: SourceBucketKey, delta = 1) => {
    const current = buckets.get(key) ?? 0;
    buckets.set(key, current + delta);
  };

  const normalizeSource = (raw?: string | null): SourceBucketKey => {
    if (!raw) return "other";
    const value = raw.toLowerCase();
    if (value.includes("slack")) return "slack";
    if (value.includes("git") || value.includes("github")) return "git";
    if (value.includes("doc")) return "doc";
    if (value.includes("issue") || value.includes("ticket") || value.includes("jira")) return "tickets";
    if (value.includes("support")) return "support";
    if (value.includes("graph")) return "graph";
    return "other";
  };

  if (Array.isArray(evidenceItems) && evidenceItems.length > 0) {
    for (const item of evidenceItems) {
      const key = normalizeSource(item.source ?? null);
      bump(key, 1);
    }
  } else {
    const scope = (incident.incidentScope ?? {}) as Record<string, unknown>;
    const slackThreads = scope.slack_threads as string[] | undefined;
    const gitRefs = scope.git_refs as string[] | undefined;
    const docIds = scope.doc_ids as string[] | undefined;
    const ticketIds = scope.issue_ids as string[] | undefined;

    if (Array.isArray(slackThreads)) bump("slack", slackThreads.length);
    if (Array.isArray(gitRefs)) bump("git", gitRefs.length);
    if (Array.isArray(docIds)) bump("doc", docIds.length);
    if (Array.isArray(ticketIds)) bump("tickets", ticketIds.length);
  }

  const entries: SourceBucket[] = Array.from(buckets.entries())
    .filter(([, value]) => typeof value === "number" && value > 0)
    .map(([key, value]) => ({
      key,
      value,
      label:
        key === "slack"
          ? "Slack"
          : key === "git"
            ? "Git"
            : key === "doc"
              ? "Docs"
              : key === "tickets"
                ? "Tickets"
                : key === "support"
                  ? "Support"
                  : key === "graph"
                    ? "Graph"
                    : "Other",
      color: colorByKey[key],
    }));

  if (entries.length < 2) {
    return null;
  }
  const total = entries.reduce((sum, b) => sum + b.value, 0);
  if (!Number.isFinite(total) || total <= 0) {
    return null;
  }

  return entries;
}

function buildSeveritySlices(incident: IncidentRecord): SeveritySlice[] | null {
  const metadata = (incident.metadata ?? {}) as Record<string, unknown>;
  const candidate = (metadata.incident_candidate_snapshot ?? {}) as {
    severity_breakdown?: Record<string, number>;
    severity_contributions?: Record<string, number>;
    severity_weights?: Record<string, number>;
    severity_semantic_pairs?: Record<string, SeveritySemanticPair>;
  };

  const breakdown = incident.severityBreakdown ?? candidate.severity_breakdown;
  const contributions = incident.severityContributions ?? candidate.severity_contributions;
  const weights = incident.severityWeights ?? candidate.severity_weights;

  const source = contributions ?? breakdown ?? null;
  if (!source) return null;

  const labelForKey: Record<string, string> = {
    slack: "Slack",
    git: "Git",
    doc: "Docs / doc issues",
    semantic: "Semantic",
    graph: "Graph",
  };

  const colorForKey: Record<string, string> = {
    slack: "rgb(59,130,246)", // blue-500
    git: "rgb(16,185,129)", // emerald-500
    doc: "rgb(245,158,11)", // amber-500
    semantic: "rgb(249,115,22)", // orange-500
    graph: "rgb(139,92,246)", // violet-500
  };

  const entries: SeveritySlice[] = Object.entries(source)
    .filter(([, value]) => typeof value === "number" && value > 0)
    .map(([key, value]) => ({
      key,
      value: value as number,
      label: labelForKey[key] ?? key,
      color: colorForKey[key] ?? "rgb(148,163,184)",
    }));

  if (entries.length < 2) {
    return null;
  }

  const total = entries.reduce((sum, s) => sum + s.value, 0);
  if (!Number.isFinite(total) || total <= 0) {
    return null;
  }

  return entries;
}

function buildDriftScore(incident: IncidentRecord): DriftScoreSide | null {
  const entities = incident.incidentEntities;
  if (!entities || entities.length === 0) {
    return null;
  }

  const severityWeight: Record<string, number> = {
    critical: 4,
    high: 3,
    medium: 2,
    low: 1,
  };

  const pickBestEntity = (): DriftScoreSide | null => {
    let best: DriftScoreSide | null = null;

    for (const entity of entities) {
      let leftRaw = 0;
      let rightRaw = 0;

      const severityKey = entity.docStatus?.severity?.toLowerCase() ?? "";
      if (severityKey && severityWeight[severityKey] !== undefined) {
        leftRaw += severityWeight[severityKey];
      }

      const allSignals: Array<["doc" | "live", string, number]> = [];
      for (const [key, value] of Object.entries(entity.activitySignals ?? {})) {
        if (typeof value === "number" && value > 0) {
          allSignals.push(["live", key, value]);
        }
      }
      for (const [key, value] of Object.entries(entity.dissatisfactionSignals ?? {})) {
        if (typeof value === "number" && value > 0) {
          allSignals.push(["live", key, value]);
        }
      }

      const sources = new Set<string>();

      for (const [, key, value] of allSignals) {
        const lowerKey = key.toLowerCase();
        if (lowerKey.includes("doc")) {
          leftRaw += value;
        }
        if (
          lowerKey.includes("slack") ||
          lowerKey.includes("git") ||
          lowerKey.includes("issue") ||
          lowerKey.includes("ticket") ||
          lowerKey.includes("support")
        ) {
          rightRaw += value;
          if (lowerKey.includes("slack")) sources.add("Slack");
          if (lowerKey.includes("git")) sources.add("Git");
          if (lowerKey.includes("issue") || lowerKey.includes("ticket")) sources.add("Tickets");
          if (lowerKey.includes("support")) sources.add("Support");
        }
      }

      if (leftRaw <= 0) {
        continue;
      }
      const total = leftRaw + rightRaw;
      if (!Number.isFinite(total) || total <= 0) {
        continue;
      }
      const left = leftRaw / total;
      const right = rightRaw / total;
      const sourcesLabel = Array.from(sources).join(", ") || "Signals";

      const candidate: DriftScoreSide = {
        leftRaw,
        rightRaw,
        left,
        right,
        entity,
        sourcesLabel,
      };

      if (!best) {
        best = candidate;
      } else {
        const bestScore = best.leftRaw;
        const candidateScore = candidate.leftRaw;
        if (
          candidateScore > bestScore ||
          (candidateScore === bestScore && candidate.leftRaw + candidate.rightRaw > best.leftRaw + best.rightRaw)
        ) {
          best = candidate;
        }
      }
    }

    return best;
  };

  const best = pickBestEntity();
  if (!best || best.leftRaw <= 0 || best.rightRaw <= 0) {
    return null;
  }

  return best;
}

function buildHeatmapRows(incident: IncidentRecord): HeatmapRow[] | null {
  const entities = incident.incidentEntities;
  if (!entities || entities.length < 2) {
    return null;
  }

  const pairs = incident.severitySemanticPairs ?? {};
  const hasDocVsSlackDrift = typeof pairs.doc_vs_slack?.drift === "number" && (pairs.doc_vs_slack?.drift ?? 0) > 0.3;
  const hasDocVsGitDrift = typeof pairs.doc_vs_git?.drift === "number" && (pairs.doc_vs_git?.drift ?? 0) > 0.3;

  const rows: HeatmapRow[] = [];

  for (const entity of entities.slice(0, 20)) {
    const activity = entity.activitySignals ?? {};
    const dissatisfaction = entity.dissatisfactionSignals ?? {};

    const docSignals = collectSignals(activity, dissatisfaction, (key) => key.includes("doc"));
    const slackSignals = collectSignals(activity, dissatisfaction, (key) => key.includes("slack"));
    const gitSignals = collectSignals(activity, dissatisfaction, (key) => key.includes("git"));
    const ticketSignals = collectSignals(activity, dissatisfaction, (key) => key.includes("issue") || key.includes("ticket"));
    const supportSignals = collectSignals(activity, dissatisfaction, (key) => key.includes("support"));

    const hasDocStatus = Boolean(entity.docStatus);
    const docSeverity = entity.docStatus?.severity?.toLowerCase();

    let docsState: HeatmapCellState = "none";
    if (!hasDocStatus && docSignals.total <= 0) {
      docsState = "none";
    } else if (
      docSeverity === "high" ||
      docSeverity === "critical" ||
      docSignals.total >= 2
    ) {
      docsState = "drift";
    } else {
      docsState = "present";
    }

    const slackState: HeatmapCellState =
      slackSignals.total > 0
        ? hasDocVsSlackDrift
          ? "drift"
          : "present"
        : "none";

    const gitState: HeatmapCellState =
      gitSignals.total > 0
        ? hasDocVsGitDrift
          ? "drift"
          : "present"
        : "none";

    const ticketsState: HeatmapCellState = ticketSignals.total > 0 ? "present" : "none";
    const supportState: HeatmapCellState = supportSignals.total > 0 ? "present" : "none";

    rows.push({
      entity,
      cells: {
        docs: docsState,
        slack: slackState,
        git: gitState,
        tickets: ticketsState,
        support: supportState,
      },
    });
  }

  const allEmptyCols = (() => {
    const agg = {
      docs: 0,
      slack: 0,
      git: 0,
      tickets: 0,
      support: 0,
    };
    for (const row of rows) {
      for (const col of Object.keys(agg) as Array<keyof typeof agg>) {
        if (row.cells[col] !== "none") {
          agg[col] += 1;
        }
      }
    }
    return agg;
  })();

  const nonEmptyCols = Object.values(allEmptyCols).filter((v) => v > 0).length;
  if (nonEmptyCols === 0) {
    return null;
  }

  return rows;
}

function collectSignals(
  activity: Record<string, number>,
  dissatisfaction: Record<string, number>,
  matcher: (key: string) => boolean,
): { total: number } {
  let total = 0;
  const addSignals = (signals: Record<string, number>) => {
    for (const [key, value] of Object.entries(signals ?? {})) {
      if (!matcher(key.toLowerCase())) continue;
      if (typeof value === "number" && value > 0) {
        total += value;
      }
    }
  };
  addSignals(activity ?? {});
  addSignals(dissatisfaction ?? {});
  return { total };
}

function buildTimelineBuckets(evidenceItems: InvestigationEvidence[]): TimelineBucket[] | null {
  if (!Array.isArray(evidenceItems) || evidenceItems.length === 0) {
    return null;
  }

  const timestamps: number[] = [];

  const pushIfValid = (value: unknown) => {
    if (typeof value === "string") {
      const date = new Date(value);
      if (!Number.isNaN(date.getTime())) {
        timestamps.push(date.getTime());
      }
    } else if (typeof value === "number") {
      const ms = value > 1e12 ? value : value * 1000;
      const date = new Date(ms);
      if (!Number.isNaN(date.getTime())) {
        timestamps.push(date.getTime());
      }
    }
  };

  for (const evidence of evidenceItems) {
    const metadata = evidence.metadata as Record<string, unknown> | undefined;
    if (!metadata) continue;
    if (metadata.timestamp) {
      pushIfValid(metadata.timestamp);
      continue;
    }
    if (metadata.iso_time) {
      pushIfValid(metadata.iso_time);
      continue;
    }
    if (metadata.ts) {
      pushIfValid(metadata.ts);
      continue;
    }
    for (const value of Object.values(metadata)) {
      pushIfValid(value);
    }
  }

  const unique = Array.from(new Set(timestamps)).sort((a, b) => a - b);
  if (unique.length < 3) {
    return null;
  }

  const min = unique[0];
  const max = unique[unique.length - 1];
  const spanMs = max - min;
  if (!Number.isFinite(spanMs) || spanMs <= 0) {
    return null;
  }

  const bucketBy =
    spanMs < 48 * 60 * 60 * 1000
      ? "hour"
      : "day";

  const buckets = new Map<string, TimelineBucket>();

  const makeBucketStart = (ms: number) => {
    const date = new Date(ms);
    if (bucketBy === "hour") {
      date.setMinutes(0, 0, 0);
    } else {
      date.setHours(0, 0, 0, 0);
    }
    return date;
  };

  for (const ms of unique) {
    const startDate = makeBucketStart(ms);
    const key = startDate.toISOString();
    const existing = buckets.get(key);
    if (existing) {
      existing.count += 1;
    } else {
      buckets.set(key, { start: startDate, count: 1 });
    }
  }

  const result = Array.from(buckets.values()).sort((a, b) => a.start.getTime() - b.start.getTime());
  if (result.length < 2) {
    return null;
  }

  const nonZeroBuckets = result.filter((b) => b.count > 0).length;
  if (nonZeroBuckets < 2) {
    return null;
  }

  return result;
}

