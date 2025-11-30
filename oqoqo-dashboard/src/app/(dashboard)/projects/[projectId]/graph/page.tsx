"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowRight, ExternalLink, Info } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { describeIssueSignals } from "@/lib/issues/descriptions";
import type { GraphSnapshot, GraphSnapshotEdge, GraphSnapshotNode } from "@/lib/graph/snapshot";
import type { GraphProviderName, GraphProviderResult } from "@/lib/graph/providers";
import { requestContextSnippets } from "@/lib/context/client";
import { logClientEvent } from "@/lib/logging";
import { isLiveLike } from "@/lib/mode";
import { selectProjectById, useDashboardStore } from "@/lib/state/dashboard-store";
import { signalSourceTokens } from "@/lib/ui/tokens";
import type { ComponentNode, DocIssue, Severity, SourceEvent } from "@/lib/types";
import { shortDate } from "@/lib/utils";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

type SeverityFilter = "all" | "elevated" | "hot";
type SignalNodeType = Extract<GraphSnapshotNode, { type: "signal" }>["signalType"];
const severityThreshold: Record<SeverityFilter, number> = {
  all: 0,
  elevated: 40,
  hot: 60,
};

const filterTokens: Record<SeverityFilter, { label: string; description: string }> = {
  all: { label: "All nodes", description: "Show every component" },
  elevated: { label: "≥40 drift", description: "Elevated nodes" },
  hot: { label: "≥60 drift", description: "Critical nodes" },
};
const issueSeverityScore: Record<Severity, number> = {
  critical: 80,
  high: 60,
  medium: 40,
  low: 20,
};
const severityWeight: Record<Severity, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
};
const signalNodeTokens: Record<SignalNodeType, { label: string; shortLabel: string; fill: string; stroke: string }> = {
  tickets: { label: "Ticket", shortLabel: "Tk", fill: "#fb923c", stroke: "#fdba74" },
  support: { label: "Support", shortLabel: "Su", fill: "#c084fc", stroke: "#e9d5ff" },
  slack: { label: "Slack", shortLabel: "Sl", fill: "#60a5fa", stroke: "#bfdbfe" },
};
const SIGNAL_OFFSET = 28;
const MAX_SIGNALS_PER_COMPONENT = 2;
const MAX_GRAPH_NODES = 150;

type GraphSnapshotResponse = GraphProviderResult & {
  fallback?: boolean;
  fallbackProvider?: GraphProviderName | string;
};

export default function ProjectGraphPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const projectSelector = useMemo(() => selectProjectById(projectId), [projectId]);
  const project = useDashboardStore(projectSelector);
  const hasProjects = useDashboardStore((state) => state.projects.length > 0);
  const liveStatus = useDashboardStore((state) => state.liveStatus);
  const [graphResult, setGraphResult] = useState<GraphSnapshotResponse | null>(null);
  const [graphLoading, setGraphLoading] = useState(true);
  const [graphError, setGraphError] = useState<string | null>(null);
  const snapshot = useMemo<GraphSnapshot | null>(() => {
    if (!graphResult) {
      return null;
    }
    const nodes = graphResult.snapshot.nodes;
    if (nodes.length <= MAX_GRAPH_NODES) {
      return graphResult.snapshot;
    }
    const allowedIds = new Set(nodes.slice(0, MAX_GRAPH_NODES).map((node) => node.id));
    return {
      nodes: nodes.slice(0, MAX_GRAPH_NODES),
      edges: graphResult.snapshot.edges.filter(
        (edge) => allowedIds.has(edge.source) && allowedIds.has(edge.target)
      ),
    };
  }, [graphResult]);
  const nodeOverflow = graphResult ? graphResult.snapshot.nodes.length > MAX_GRAPH_NODES : false;
  useEffect(() => {
    let cancelled = false;
    const loadSnapshot = async () => {
      setGraphLoading(true);
      setGraphError(null);
      try {
        const response = await fetch(`/api/graph-snapshot?projectId=${projectId}`, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(response.statusText || "Failed to load graph snapshot");
        }
        const payload = (await response.json()) as GraphSnapshotResponse;
        if (!cancelled) {
          setGraphResult(payload);
        }
      } catch (error) {
        if (!cancelled) {
          setGraphResult(null);
          setGraphError(error instanceof Error ? error.message : "Failed to load graph snapshot");
        }
      } finally {
        if (!cancelled) {
          setGraphLoading(false);
        }
      }
    };
    loadSnapshot();
    return () => {
      cancelled = true;
    };
  }, [projectId]);
  const componentEventsById = useMemo(() => {
    if (!project) return {};
    return project.components.reduce<Record<string, SourceEvent[]>>((acc, component) => {
      acc[component.id] = component.sourceEvents;
      return acc;
    }, {});
  }, [project]);
  const repoLookup = useMemo(() => {
    if (!project) return new Map<string, { name: string; url: string }>();
    return new Map(project.repos.map((repo) => [repo.id, { name: repo.name, url: repo.repoUrl }]));
  }, [project]);
  const componentNodes = useMemo(
    () => (snapshot ? snapshot.nodes.filter(isComponentGraphNode) : []),
    [snapshot]
  );
  const issueNodes = useMemo(() => (snapshot ? snapshot.nodes.filter(isIssueGraphNode) : []), [snapshot]);
  const signalNodes = useMemo(() => (snapshot ? snapshot.nodes.filter(isSignalGraphNode) : []), [snapshot]);
  const [nodeTypeFilter, setNodeTypeFilter] = useState<"components" | "issues">("components");
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("all");
  const handleNodeTypeChange = (type: "components" | "issues") => {
    setNodeTypeFilter(type);
    logClientEvent("graph.node-type", { projectId, type });
  };
  const handleSeverityChange = (filter: SeverityFilter) => {
    setSeverityFilter(filter);
    logClientEvent("graph.severity-filter", { projectId, filter });
  };
  const filteredComponentNodes = useMemo(
    () =>
      componentNodes.filter(
        (node) => node.component.graphSignals.drift.score >= severityThreshold[severityFilter]
      ),
    [componentNodes, severityFilter]
  );
  const filteredIssueNodes = useMemo(
    () =>
      issueNodes
        .filter((node) => node.issue.status !== "resolved")
        .filter((node) => issueSeverityScore[node.issue.severity] >= severityThreshold[severityFilter]),
    [issueNodes, severityFilter]
  );
  const dependencyEdges = useMemo(() => (snapshot ? snapshot.edges.filter(isDependencyEdge) : []), [snapshot]);
  const positionedNodes = useMemo(() => {
    const count = filteredComponentNodes.length || 1;
    const radius = 80;
    const center = 100;
    return filteredComponentNodes.map((node, index) => {
      const angle = (2 * Math.PI * index) / count;
      return {
        id: node.id,
        name: node.label,
        drift: node.component.graphSignals.drift.score,
        x: center + radius * Math.cos(angle),
        y: center + radius * Math.sin(angle),
        node: node.component,
      };
    });
  }, [filteredComponentNodes]);
  const nodeLookup = useMemo(() => {
    return positionedNodes.reduce<Record<string, (typeof positionedNodes)[number]>>((acc, node) => {
      acc[node.id] = node;
      return acc;
    }, {});
  }, [positionedNodes]);
  const signalNodesByComponent = useMemo(() => {
    return signalNodes.reduce<Record<string, Extract<GraphSnapshotNode, { type: "signal" }>[]>((acc, node) => {
      acc[node.componentId] = acc[node.componentId] ?? [];
      acc[node.componentId].push(node);
      acc[node.componentId].sort(
        (a, b) => new Date(b.event.timestamp).getTime() - new Date(a.event.timestamp).getTime()
      );
      return acc;
    }, {});
  }, [signalNodes]);
  const positionedSignals = useMemo(() => {
    return Object.entries(signalNodesByComponent).flatMap(([componentId, signals]) => {
      const anchor = nodeLookup[componentId];
      if (!anchor) {
        return [];
      }
      const limited = signals.slice(0, MAX_SIGNALS_PER_COMPONENT);
      return limited.map((signal, index) => {
        const angle = (2 * Math.PI * (index + 1)) / (limited.length + 1);
        const x = anchor.x + SIGNAL_OFFSET * Math.cos(angle);
        const y = anchor.y + SIGNAL_OFFSET * Math.sin(angle);
        return {
          id: signal.id,
          x,
          y,
          targetX: anchor.x,
          targetY: anchor.y,
          node: signal,
        };
      });
    });
  }, [nodeLookup, signalNodesByComponent]);
  const [selectedComponentId, setSelectedComponentId] = useState<string | null>(null);
  const handleSelectComponent = (componentId: string) => {
    setSelectedComponentId(componentId);
    logClientEvent("graph.focus-component", { projectId, componentId });
  };
  const resolvedComponentId = useMemo(() => {
    if (!filteredComponentNodes.length) {
      return null;
    }
    if (selectedComponentId && filteredComponentNodes.some((node) => node.id === selectedComponentId)) {
      return selectedComponentId;
    }
    return filteredComponentNodes[0].id;
  }, [filteredComponentNodes, selectedComponentId]);
  const selectedComponent = useMemo(() => {
    if (!resolvedComponentId) return null;
    return filteredComponentNodes.find((node) => node.id === resolvedComponentId) ?? null;
  }, [filteredComponentNodes, resolvedComponentId]);
  const selectedEventSamples = useMemo(() => {
    if (!selectedComponent) return [];
    return (componentEventsById[selectedComponent.component.id] ?? []).slice(0, 3);
  }, [componentEventsById, selectedComponent]);
  const [contextHint, setContextHint] = useState<string | null>(null);
  const [contextHintLoading, setContextHintLoading] = useState(false);
  useEffect(() => {
    if (resolvedComponentId) {
      logClientEvent("graph.component-selected", { projectId, componentId: resolvedComponentId });
    }
  }, [projectId, resolvedComponentId]);
  useEffect(() => {
    if (!resolvedComponentId) {
      setContextHint(null);
      return;
    }
    let cancelled = false;
    setContextHintLoading(true);
    requestContextSnippets({ projectId, componentId: resolvedComponentId })
      .then((response) => {
        if (!cancelled) {
          setContextHint(response.snippets[0]?.summary ?? null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setContextHint(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setContextHintLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, resolvedComponentId]);
  const highlightedComponentIds = useMemo(() => {
    if (!resolvedComponentId) return null;
    const ids = new Set<string>([resolvedComponentId]);
    dependencyEdges.forEach((edge) => {
      if (edge.source === resolvedComponentId) {
        ids.add(edge.target);
      }
      if (edge.target === resolvedComponentId) {
        ids.add(edge.source);
      }
    });
    return ids;
  }, [dependencyEdges, resolvedComponentId]);

  const relatedIssues = useMemo(() => {
    if (!snapshot || !resolvedComponentId) return [];
    const issues = snapshot.edges
      .filter(isIssueEdge)
      .filter((edge) => edge.target === resolvedComponentId)
      .map((edge) => snapshot.nodes.find((node) => node.id === edge.source))
      .filter(
        (node): node is Extract<GraphSnapshotNode, { type: "issue" }> =>
          Boolean(node) && node.type === "issue"
      );
    return issues.sort((a, b) => {
      const severityDelta = severityWeight[b.issue.severity] - severityWeight[a.issue.severity];
      if (severityDelta !== 0) {
        return severityDelta;
      }
      return new Date(b.issue.updatedAt).getTime() - new Date(a.issue.updatedAt).getTime();
    });
  }, [snapshot, resolvedComponentId]);
  const relatedSignals = useMemo(() => {
    if (!resolvedComponentId) return [];
    return (signalNodesByComponent[resolvedComponentId] ?? []).slice(0, 4);
  }, [resolvedComponentId, signalNodesByComponent]);
  const primaryIssueSummary = relatedIssues.length ? describeIssueSignals(relatedIssues[0].issue) : null;

  useEffect(() => {
    if (!filteredComponentNodes.length) {
      setSelectedComponentId(null);
      return;
    }
    if (!selectedComponentId) {
      setSelectedComponentId(filteredComponentNodes[0].id);
      return;
    }
    if (!filteredComponentNodes.some((node) => node.id === selectedComponentId)) {
      setSelectedComponentId(filteredComponentNodes[0].id);
    }
  }, [filteredComponentNodes, selectedComponentId]);

  if (!project) {
    if (!hasProjects) {
      return <div className="rounded-2xl border border-dashed border-border/60 p-6 text-sm text-muted-foreground">Loading project graph…</div>;
    }
    return <div className="text-sm text-destructive">Project not found.</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.4em] text-muted-foreground">Graph</p>
        <h1 className="text-3xl font-semibold text-foreground">Live topology preview</h1>
        <p className="text-sm text-muted-foreground">
          Quick visualization of the mocked activity graph so Cerebros can drop in Neo4j snapshots later.
        </p>
      </div>

      <Card>
        <CardHeader className="flex flex-col gap-4">
          <div>
            <CardTitle>Component graph</CardTitle>
            <CardDescription>Nodes encode drift severity, edges encode dependencies.</CardDescription>
          </div>
          <GraphToolbar
            graphResult={graphResult}
            graphError={graphError}
            nodeOverflow={nodeOverflow}
            nodeTypeFilter={nodeTypeFilter}
            severityFilter={severityFilter}
            onNodeTypeChange={handleNodeTypeChange}
            onSeverityChange={handleSeverityChange}
          />
        </CardHeader>
        <CardContent>
          {graphLoading ? (
            <GraphEmptyState icon="🌀" message="Loading graph snapshot…" />
          ) : graphError ? (
            <GraphEmptyState icon="⚠️" message="Unable to load graph snapshot. Try refreshing." />
          ) : !snapshot ? (
            <GraphEmptyState icon="🗺️" message="Graph snapshot not ready yet. Run a refresh to populate it." />
          ) : nodeTypeFilter === "components" ? (
            positionedNodes.length ? (
              <div className="relative mx-auto max-w-xl">
                <svg viewBox="0 0 200 200" className="h-full w-full">
                  {dependencyEdges.map((edge) => {
                    const source = nodeLookup[edge.source];
                    const target = nodeLookup[edge.target];
                    if (!source || !target) return null;
                    const isHighlighted =
                      !highlightedComponentIds ||
                      (highlightedComponentIds.has(edge.source) && highlightedComponentIds.has(edge.target));
                    return (
                      <line
                        key={edge.id}
                        x1={source.x}
                        y1={source.y}
                        x2={target.x}
                        y2={target.y}
                        stroke="rgba(147, 197, 253, 0.8)"
                        strokeOpacity={isHighlighted ? 0.9 : 0.2}
                        strokeWidth={2}
                      />
                    );
                  })}
                  {positionedSignals.map((signal) => {
                    const token = signalNodeTokens[signal.node.signalType];
                    const isActive = !resolvedComponentId || signal.node.componentId === resolvedComponentId;
                    return (
                      <g key={signal.id} style={{ opacity: isActive ? 1 : 0.2 }}>
                        <title>
                          {token.label} • {shortDate(signal.node.event.timestamp)}
                        </title>
                        <line
                          x1={signal.x}
                          y1={signal.y}
                          x2={signal.targetX}
                          y2={signal.targetY}
                          stroke={`${token.stroke}55`}
                          strokeDasharray="3 2"
                          strokeWidth={1}
                        />
                        <circle
                          cx={signal.x}
                          cy={signal.y}
                          r={7}
                          fill={token.fill}
                          stroke={token.stroke}
                          strokeWidth={2}
                        />
                        <text
                          x={signal.x}
                          y={signal.y + 3}
                          textAnchor="middle"
                          fill="#0f172a"
                          fontSize="7"
                          fontWeight={600}
                        >
                          {token.shortLabel}
                        </text>
                      </g>
                    );
                  })}
                  {positionedNodes.map((node) => {
                    const isSelected = node.id === resolvedComponentId;
                    const isNeighbor = !highlightedComponentIds || highlightedComponentIds.has(node.id);
                    return (
                      <g
                        key={node.id}
                        className="cursor-pointer transition"
                        style={{ opacity: isNeighbor ? 1 : 0.35 }}
                        onClick={() => handleSelectComponent(node.id)}
                      >
                        <title>
                          {node.name} • Drift {node.drift}
                        </title>
                        <circle
                          cx={node.x}
                          cy={node.y}
                          r={16}
                          fill="url(#grad-primary)"
                          stroke={node.drift >= 60 ? "#f87171" : node.drift >= 40 ? "#facc15" : "#38bdf8"}
                          strokeWidth={isSelected ? 4 : 2}
                          opacity={isSelected ? 1 : 0.8}
                        />
                        <text x={node.x} y={node.y + 24} textAnchor="middle" fill="#e2e8f0" fontSize="10" fontWeight={600}>
                          {node.name}
                        </text>
                      </g>
                    );
                  })}
                  <defs>
                    <radialGradient id="grad-primary" cx="50%" cy="50%" r="50%">
                      <stop offset="0%" style={{ stopColor: "#0f172a", stopOpacity: 0.9 }} />
                      <stop offset="100%" style={{ stopColor: "#1e293b", stopOpacity: 0.7 }} />
                    </radialGradient>
                  </defs>
                </svg>
              </div>
            ) : (
              <GraphEmptyState
                icon={isLiveLike(liveStatus.mode) ? "🔍" : "🧪"}
                message={
                  isLiveLike(liveStatus.mode)
                    ? "No components meet the current filter."
                    : "Graph waiting for live snapshot — expand filters or refresh once ingest succeeds."
                }
              />
            )
          ) : filteredIssueNodes.length ? (
            <div className="space-y-3">
              {filteredIssueNodes.map((issueNode) => (
                <GraphIssueRow
                  key={issueNode.issue.id}
                  issue={issueNode.issue}
                  projectId={project.id}
                  sourceEvents={componentEventsById[issueNode.issue.componentId]}
                />
              ))}
            </div>
          ) : (
            <GraphEmptyState icon="📭" message="No issues meet the current filter." />
          )}
        </CardContent>
      </Card>

      {selectedComponent ? (
        <Card>
          <CardHeader className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>{selectedComponent.component.name}</CardTitle>
              <CardDescription>Drift {selectedComponent.component.graphSignals.drift.score} • Owner {selectedComponent.component.ownerTeam}</CardDescription>
            </div>
            <Button variant="ghost" className="rounded-full" asChild>
              <Link href={`/projects/${project.id}/components/${selectedComponent.component.id}`}>Open component</Link>
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3 text-sm text-muted-foreground">
              <div>
                <p className="text-xs uppercase">Activity</p>
                <p className="text-lg font-semibold text-foreground">{selectedComponent.component.graphSignals.activity.score}</p>
              </div>
              <div>
                <p className="text-xs uppercase">Drift</p>
                <p className="text-lg font-semibold text-foreground">{selectedComponent.component.graphSignals.drift.score}</p>
              </div>
              <div>
                <p className="text-xs uppercase">Dissatisfaction</p>
                <p className="text-lg font-semibold text-foreground">{selectedComponent.component.graphSignals.dissatisfaction.score}</p>
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              {primaryIssueSummary
                ? `Why this fired: ${primaryIssueSummary}`
                : "No live DocIssues matched the current filters."}
            </p>
            <p className="text-[11px] text-muted-foreground">
              {contextHintLoading
                ? "Context: loading…"
                : contextHint
                ? `Context: ${contextHint}`
                : "Context: no linked snippets yet."}
            </p>
            <Button variant="link" size="sm" className="h-auto p-0 text-[11px]" asChild>
              <Link href={`/projects/${project.id}/components/${selectedComponent.component.id}#context`}>
                Open context tab
              </Link>
            </Button>
            <div className="space-y-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Recent signals</p>
              <div className="flex flex-wrap gap-2">
                {selectedEventSamples.length ? (
                  selectedEventSamples.map((event) => <SourceEventChip key={event.id} event={event} />)
                ) : (
                  <p className="text-xs text-muted-foreground">No Git, Slack, Ticket, or Support events recorded.</p>
                )}
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Linked doc issues</p>
              {relatedIssues.length ? (
                relatedIssues.map((issueNode) => (
                  <GraphIssueRow
                    key={issueNode.issue.id}
                    issue={issueNode.issue}
                    projectId={project.id}
                    sourceEvents={componentEventsById[issueNode.issue.componentId]}
                  />
                ))
              ) : (
                <p className="text-xs text-muted-foreground">No open issues attached to this component.</p>
              )}
            </div>
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Tickets &amp; support</p>
              {relatedSignals.length ? (
                relatedSignals.map((signal) => <GraphSignalRow key={signal.id} signal={signal} />)
              ) : (
                <p className="text-xs text-muted-foreground">No ticket or support chatter linked to this component.</p>
              )}
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Graph nodes</CardTitle>
          <CardDescription>Fast access to each component’s underlying drift metrics.</CardDescription>
        </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            {componentNodes.map((node) => {
              const repoUrl =
                node.component.repoIds
                  .map((repoId) => repoLookup.get(repoId)?.url)
                  .find((url) => Boolean(url)) ?? undefined;
              return (
            <NodeSummary
              key={node.id}
              component={node.component}
              projectId={project.id}
                  isFocused={node.id === resolvedComponentId}
              onInspect={() => handleSelectComponent(node.id)}
                  repoUrl={repoUrl}
            />
              );
            })}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Dependencies</CardTitle>
          <CardDescription>Contracts represented on the graph view.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {project.dependencies.length ? (
            project.dependencies.map((dependency) => {
              const source = project.components.find((item) => item.id === dependency.sourceComponentId);
              const target = project.components.find((item) => item.id === dependency.targetComponentId);
              return (
                <div key={dependency.id} className="rounded-2xl border border-border/50 p-4 text-sm">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <Badge variant="outline" className="rounded-full border-border/60 text-[10px]">
                      {dependency.surface}
                    </Badge>
                    <span className="font-semibold text-foreground">{source?.name}</span>
                    <ArrowRight className="h-3 w-3" />
                    <span className="font-semibold text-foreground">{target?.name}</span>
                  </div>
                  <p className="pt-2 text-xs text-muted-foreground">{dependency.description}</p>
                </div>
              );
            })
          ) : (
            <p className="text-sm text-muted-foreground">No dependencies mapped for this project.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

const NodeSummary = ({
  component,
  projectId,
  isFocused,
  onInspect,
  repoUrl,
}: {
  component: ComponentNode;
  projectId: string;
  isFocused: boolean;
  onInspect: () => void;
  repoUrl?: string;
}) => (
  <div className={`rounded-2xl border p-4 ${isFocused ? "border-primary/50 bg-primary/5" : "border-border/60"}`}>
    <div className="flex items-center justify-between gap-3">
      <div>
        <div className="text-sm font-semibold text-foreground">{component.name}</div>
        <p className="text-xs text-muted-foreground">{component.serviceType}</p>
      </div>
      <div className="flex gap-2">
        {repoUrl ? (
          <Button variant="ghost" size="sm" className="rounded-full text-xs" asChild>
            <a href={repoUrl} target="_blank" rel="noreferrer">
              Repo
              <ExternalLink className="ml-1 h-4 w-4" />
            </a>
          </Button>
        ) : null}
        <Button variant="ghost" size="sm" className="rounded-full text-xs" onClick={onInspect}>
          Focus
        </Button>
        <Button variant="ghost" className="rounded-full text-xs" asChild>
          <Link href={`/projects/${projectId}/components/${component.id}`}>
            Inspect
            <ArrowRight className="ml-1 h-4 w-4" />
          </Link>
        </Button>
      </div>
    </div>
    <div className="flex items-center gap-3 pt-3 text-xs text-muted-foreground">
      <span>Drift • {component.graphSignals.drift.score}</span>
      <span>Activity • {component.graphSignals.activity.score}</span>
      <span>Dissatisfaction • {component.graphSignals.dissatisfaction.score}</span>
    </div>
  </div>
);

const GraphIssueRow = ({ issue, projectId, sourceEvents }: { issue: DocIssue; projectId: string; sourceEvents?: SourceEvent[] }) => {
  const eventLinks =
    sourceEvents
      ?.filter((event) => issue.divergenceSources.includes(event.source) && event.link)
      .reduce<Record<string, SourceEvent>>((acc, event) => {
        if (event.link && !acc[event.source]) {
          acc[event.source] = event;
        }
        return acc;
      }, {}) ?? undefined;

  return (
    <div className="rounded-2xl border border-border/60 p-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-foreground">{issue.title}</span>
        <Badge variant="outline" className="rounded-full border-border/60 text-[10px] uppercase">
          {issue.severity}
        </Badge>
      </div>
      <p className="text-xs text-muted-foreground">{describeIssueSignals(issue)}</p>
      {eventLinks ? (
        <div className="flex flex-wrap gap-2 py-1 text-xs">
          {Object.values(eventLinks).map((event) => {
            const token = signalSourceTokens[event.source];
            return (
              <Badge key={event.id} variant="outline" className={`border text-[10px] ${token.color}`}>
                <a href={event.link} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline">
                  Open {token.label}
                </a>
              </Badge>
            );
          })}
        </div>
      ) : null}
      <Button variant="link" size="sm" className="h-auto p-0 text-[11px]" asChild>
        <Link href={`/projects/${projectId}/issues/${issue.id}`}>Open issue</Link>
      </Button>
    </div>
  );
};

const GraphSignalRow = ({ signal }: { signal: Extract<GraphSnapshotNode, { type: "signal" }> }) => {
  const badgeClass =
    signal.signalType === "tickets" ? "border-amber-300/60 text-amber-100" : "border-fuchsia-300/60 text-fuchsia-100";
  return (
    <div className="rounded-2xl border border-border/60 p-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-foreground">{signal.label}</span>
        <Badge variant="outline" className={`rounded-full border-border/60 text-[10px] uppercase ${badgeClass}`}>
          {signalNodeTokens[signal.signalType].label}
        </Badge>
      </div>
      <p className="text-xs text-muted-foreground">
        Logged {shortDate(signal.event.timestamp)}
        {signal.event.metadata?.status ? ` • ${signal.event.metadata.status}` : ""}
      </p>
      {signal.event.link ? (
        <Button variant="link" size="sm" className="h-auto p-0 text-[11px]" asChild>
          <a href={signal.event.link} target="_blank" rel="noreferrer">
            Open source
          </a>
        </Button>
      ) : null}
    </div>
  );
};

const SourceEventChip = ({ event }: { event: SourceEvent }) => {
  const token = signalSourceTokens[event.source];
  const content = event.link ? (
    <a href={event.link} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline">
      {event.title}
    </a>
  ) : (
    event.title
  );

  return (
    <Badge
      variant="outline"
      className={`rounded-full border px-3 py-1 text-[11px] ${token ? token.color : "text-muted-foreground"}`}
    >
      {content}
    </Badge>
  );
};

function GraphToolbar({
  graphResult,
  graphError,
  nodeOverflow,
  nodeTypeFilter,
  severityFilter,
  onNodeTypeChange,
  onSeverityChange,
}: {
  graphResult: GraphSnapshotResponse | null;
  graphError: string | null;
  nodeOverflow: boolean;
  nodeTypeFilter: "components" | "issues";
  severityFilter: SeverityFilter;
  onNodeTypeChange: (next: "components" | "issues") => void;
  onSeverityChange: (next: SeverityFilter) => void;
}) {
  const severityOptions = Object.keys(filterTokens) as SeverityFilter[];

  return (
    <div className="flex flex-col gap-3">
      {graphResult ? (
        <GraphSourceBanner result={graphResult} nodeOverflow={nodeOverflow} />
      ) : (
        <Badge
          variant="outline"
          className="w-fit rounded-full border-border/60 text-[10px] uppercase tracking-wide text-muted-foreground"
        >
          {graphError ? "Graph source • unavailable" : "Graph source • loading"}
        </Badge>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Tabs value={nodeTypeFilter} onValueChange={(value) => onNodeTypeChange(value as "components" | "issues")}>
          <TabsList>
            <TabsTrigger value="components">Component nodes</TabsTrigger>
            <TabsTrigger value="issues">Doc issues</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="flex flex-wrap gap-2">
          {severityOptions.map((option) => (
            <Button
              key={option}
              variant="outline"
              size="sm"
              className={cn(
                "rounded-full border-border/60 text-[11px]",
                severityFilter === option ? "bg-primary/15 text-primary" : "text-muted-foreground"
              )}
              onClick={() => onSeverityChange(option)}
            >
              {filterTokens[option].label}
            </Button>
          ))}
        </div>
        <GraphLegend />
      </div>
    </div>
  );
}

const GraphLegend = () => (
  <Popover>
    <PopoverTrigger asChild>
      <Button
        variant="ghost"
        size="sm"
        className="rounded-full border border-border/60 px-3 text-[11px] text-muted-foreground hover:text-foreground"
      >
        <Info className="mr-1.5 h-3.5 w-3.5" />
        Legend
      </Button>
    </PopoverTrigger>
    <PopoverContent>
      <div className="space-y-2 text-[11px] text-muted-foreground">
        <LegendSwatch color="#f87171" label="Component drift ≥ 60" />
        <LegendSwatch color="#facc15" label="Component drift ≥ 40" />
        <LegendSwatch color="#38bdf8" label="Component drift < 40" />
        <LegendSwatch color={signalNodeTokens.tickets.fill} label="Ticket signal" />
        <LegendSwatch color={signalNodeTokens.support.fill} label="Support signal" />
        <LegendSwatch color={signalNodeTokens.slack.fill} label="Slack signal" />
      </div>
    </PopoverContent>
  </Popover>
);

const GraphSourceBanner = ({
  result,
  nodeOverflow,
}: {
  result: GraphSnapshotResponse;
  nodeOverflow: boolean;
}) => {
  const providerLabel = result.provider === "neo4j" ? "Neo4j live" : "synthetic demo";
  const badgeText = result.fallback
    ? `Graph source • ${providerLabel} (fallback)`
    : `Graph source • ${providerLabel}`;

  return (
    <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
      <Badge variant="outline" className="rounded-full border-border/60 px-3 py-1 text-[10px] uppercase tracking-wide">
        {badgeText}
      </Badge>
      <span>
        {result.counts.components} components • {result.counts.issues} issues
      </span>
      <span>Updated {shortDate(result.updatedAt)}</span>
      {nodeOverflow ? (
        <span className="rounded-full border border-dashed border-border/60 px-2 py-0.5 text-[10px] text-muted-foreground">
          Showing first {MAX_GRAPH_NODES} of {result.counts.nodes} nodes
        </span>
      ) : null}
    </div>
  );
};

const GraphEmptyState = ({ icon, message }: { icon: string; message: string }) => (
  <div className="flex items-center gap-2 rounded-2xl border border-dashed border-border/60 p-4 text-sm text-muted-foreground">
    <span aria-hidden="true">{icon}</span>
    <span>{message}</span>
  </div>
);

const LegendSwatch = ({ color, label }: { color: string; label: string }) => (
  <span className="flex items-center gap-1" title={label}>
    <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
    {label}
  </span>
);

function isComponentGraphNode(node: GraphSnapshotNode): node is Extract<GraphSnapshotNode, { type: "component" }> {
  return node.type === "component";
}

function isSignalGraphNode(node: GraphSnapshotNode): node is Extract<GraphSnapshotNode, { type: "signal" }> {
  return node.type === "signal";
}

function isIssueGraphNode(node: GraphSnapshotNode): node is Extract<GraphSnapshotNode, { type: "issue" }> {
  return node.type === "issue";
}

function isIssueEdge(edge: GraphSnapshotEdge): edge is Extract<GraphSnapshotEdge, { kind: "issue" }> {
  return edge.kind === "issue";
}

function isDependencyEdge(edge: GraphSnapshotEdge): edge is Extract<GraphSnapshotEdge, { kind: "dependency" }> {
  return edge.kind === "dependency";
}


