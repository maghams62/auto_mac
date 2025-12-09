"use client";

import dynamic from "next/dynamic";
import { memo, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";
import type { ForceGraphMethods } from "react-force-graph";

import { Button } from "@/components/ui/button";
import type { SystemGraphLink, SystemGraphNode } from "@/lib/hooks/use-activity-drift-view";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => <div className="flex h-[320px] items-center justify-center text-sm text-muted-foreground">Loading system map…</div>,
});

const MEDIUM_COLORS: Record<string, string> = {
  doc: "#f87171",
  git: "#fbbf24",
  slack: "#60a5fa",
  tickets: "#fb923c",
  support: "#c084fc",
};

type ProviderMeta = {
  provider: string;
  fallback?: boolean;
  updatedAt?: string;
};

interface SystemMapGraphProps {
  nodes: SystemGraphNode[];
  links: SystemGraphLink[];
  loading?: boolean;
  error?: string | null;
  providerMeta?: ProviderMeta | null;
  selectedId?: string | null;
  onSelect?: (id: string) => void;
}

export const SystemMapGraph = memo(function SystemMapGraph({
  nodes,
  links,
  loading,
  error,
  providerMeta,
  selectedId,
  onSelect,
}: SystemMapGraphProps) {
  const positionedNodes = useMemo(() => buildHorizontalLayout(nodes), [nodes]);
  const graphData = useMemo(() => ({ nodes: positionedNodes, links }), [positionedNodes, links]);
  const graphRef = useRef<ForceGraphMethods>();
  const [hoveredNode, setHoveredNode] = useState<ForceGraphNode | null>(null);
  const [hoveredLink, setHoveredLink] = useState<ForceGraphLink | null>(null);

  useEffect(() => {
    if (!graphRef.current) return;
    graphRef.current.zoomToFit(0, 120);
  }, [graphData.nodes.length, graphData.links.length]);

  useEffect(() => {
    if (!graphRef.current) return;
    const chargeForce = graphRef.current.d3Force?.("charge") as { strength?: (v: number) => void } | undefined;
    if (chargeForce?.strength) {
      chargeForce.strength(0);
    }
    const centerForce = graphRef.current.d3Force?.("center");
    if (centerForce) {
      graphRef.current.d3Force?.("center", null);
    }
    const linkForce = graphRef.current.d3Force?.("link") as { distance?: (v: number) => void; strength?: (v: number) => void } | undefined;
    if (linkForce?.distance) {
      linkForce.distance(200);
    }
    if (linkForce?.strength) {
      linkForce.strength(0.1);
    }
  }, [graphData.nodes.length]);

  return (
    <Card>
      <CardHeader className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <CardTitle>System map · what&apos;s heating up</CardTitle>
          <CardDescription>Nodes are components, edges are dependencies. Click a node to focus it.</CardDescription>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="rounded-full border-border/60 text-xs uppercase tracking-wide">
            {renderProviderLabel(providerMeta)}
          </Badge>
          <Button
            variant="ghost"
            size="sm"
            className="text-xs"
            onClick={() => {
              graphRef.current?.zoomToFit(400, 120);
            }}
          >
            Reset view
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <div className="flex h-[520px] flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-border/60 text-sm text-muted-foreground">
            <span>Loading graph snapshot…</span>
          </div>
        ) : error ? (
          <div className="flex h-[520px] flex-col items-center justify-center gap-2 rounded-2xl border border-amber-500/40 bg-amber-500/10 text-sm text-amber-100">
            <AlertTriangle className="h-4 w-4" />
            <span>{error}</span>
          </div>
        ) : !nodes.length ? (
          <div className="flex h-[520px] flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-border/60 text-sm text-muted-foreground">
            <span>No components available for this project yet.</span>
          </div>
        ) : (
          <div className="relative h-[520px] bg-muted/5">
            <ForceGraph2D
              ref={graphRef}
              graphData={graphData}
              nodeRelSize={6}
              enableNodeDrag={false}
              autoPauseRedraw={false}
              warmupTicks={0}
              cooldownTicks={0}
              d3AlphaDecay={1}
              d3VelocityDecay={0.9}
              linkColor={(link: SystemGraphLink) => edgeColor(link)}
              linkWidth={(link: SystemGraphLink) => edgeWidth(link)}
              linkDirectionalParticles={(link: SystemGraphLink) => Math.min(3, Math.max(0, Math.round(edgeWidth(link) - 1)))}
              linkDirectionalParticleSpeed={(link: SystemGraphLink) => 0.004 + (link.weight ?? 1) * 0.0005}
              linkDirectionalParticleColor={(link: SystemGraphLink) => edgeColor(link)}
              nodeCanvasObjectMode={() => "before"}
              nodeCanvasObject={(node: GraphNodeObject, ctx, globalScale) => {
                drawNode(node, ctx, globalScale, selectedId);
              }}
              nodePointerAreaPaint={(node: GraphNodeObject, color, ctx) => {
                const size = 6 + Math.min(12, node.blastRadius);
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(node.x, node.y, size + 6, 0, 2 * Math.PI, false);
                ctx.fill();
              }}
              onNodeHover={(node) => {
                setHoveredNode((node as ForceGraphNode) ?? null);
                if (node) setHoveredLink(null);
              }}
              onLinkHover={(link) => {
                setHoveredLink((link as ForceGraphLink) ?? null);
                if (link) setHoveredNode(null);
              }}
              onNodeClick={(node) => {
                if (!onSelect) return;
                const typed = node as GraphNodeObject;
                onSelect(typed.id);
              }}
            />
            {(hoveredNode || hoveredLink) ? (
              <div className="pointer-events-none absolute left-4 top-4 max-w-xs rounded-xl border border-border/60 bg-background/95 p-3 text-xs shadow-xl">
                {hoveredNode ? <NodeTooltip node={hoveredNode} /> : null}
                {!hoveredNode && hoveredLink ? <LinkTooltip link={hoveredLink} /> : null}
              </div>
            ) : null}
          </div>
        )}
        <Legend />
      </CardContent>
    </Card>
  );
});

function renderProviderLabel(meta?: ProviderMeta | null) {
  if (!meta) return "Synthetic dataset";
  if (meta.fallback) return "Synthetic fallback";
  if (meta.provider === "neo4j") return "Live Atlas data";
  return meta.provider;
}

function driftColor(score: number) {
  if (score >= 70) return "#f87171";
  if (score >= 50) return "#fb923c";
  if (score >= 40) return "#facc15";
  return "#22d3ee";
}

function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-xl border border-border/50 bg-muted/20 px-4 py-3 text-xs text-muted-foreground">
      <LegendItem color="#f87171" label="Node color = drift score" />
      <LegendItem color="#94a3b8" label="Node size = blast radius" dashed />
      <LegendItem color="#fca5a5" label="Halo = open doc issues" halo />
       <LegendItem color="#60a5fa" label="Edge color/width = dominant medium" />
    </div>
  );
}

function LegendItem({ color, label, dashed, halo }: { color: string; label: string; dashed?: boolean; halo?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <span
        className="inline-flex h-4 w-4 items-center justify-center rounded-full"
        style={{
          background: halo ? "transparent" : color,
          border: halo ? `2px solid ${color}` : "none",
          borderStyle: dashed ? "dashed" : "solid",
        }}
      />
      <span>{label}</span>
      <Separator orientation="vertical" className="hidden h-4 lg:block" />
    </div>
  );
}

type ForceGraphNode = SystemGraphNode & {
  x: number;
  y: number;
};

type ForceGraphLink = SystemGraphLink & {
  source: ForceGraphNode | string;
  target: ForceGraphNode | string;
};

type GraphNodeObject = ForceGraphNode & { [key: string]: unknown };

function drawNode(node: ForceGraphNode, ctx: CanvasRenderingContext2D, globalScale: number, selectedId?: string | null) {
  const baseSize = 6 + Math.min(12, node.blastRadius ?? 1);
  const haloExtra = (node.docIssueCount ?? 0) * 0.6;
  const haloRadius = baseSize + Math.min(10, haloExtra);
  const fill = driftColor(node.driftScore);
  ctx.beginPath();
  ctx.fillStyle = fill;
  ctx.arc(node.x, node.y, baseSize, 0, 2 * Math.PI, false);
  ctx.fill();

  if (node.docIssueCount) {
    ctx.beginPath();
    ctx.strokeStyle = "rgba(248,113,113,0.7)";
    ctx.lineWidth = Math.max(1, node.docIssueCount * 0.25) / globalScale;
    ctx.arc(node.x, node.y, haloRadius, 0, 2 * Math.PI, false);
    ctx.stroke();
  }

  if (selectedId && node.id === selectedId) {
    ctx.beginPath();
    ctx.strokeStyle = "#fef3c7";
    ctx.lineWidth = 2 / globalScale;
    ctx.arc(node.x, node.y, haloRadius + 3, 0, 2 * Math.PI, false);
    ctx.stroke();
  }
}

function edgeColor(link: SystemGraphLink) {
  if (link.medium && MEDIUM_COLORS[link.medium]) {
    return MEDIUM_COLORS[link.medium];
  }
  return MEDIUM_COLORS.doc;
}

function edgeWidth(link: SystemGraphLink) {
  return Math.max(1, Math.min(5, (link.weight ?? 1) * 0.8));
}

function buildHorizontalLayout(nodes: SystemGraphNode[]): SystemGraphNode[] {
  if (!nodes.length) return nodes;
  const sorted = [...nodes].sort((a, b) => (b.driftScore ?? 0) - (a.driftScore ?? 0));
  const perRow = Math.max(3, Math.ceil(sorted.length / 2));
  const spacingX = 220;
  const spacingY = 160;
  const rows = Math.ceil(sorted.length / perRow);
  const offsetX = ((Math.min(perRow, sorted.length) - 1) * spacingX) / 2;
  const offsetY = ((rows - 1) * spacingY) / 2;
  const positioned = sorted.map((node, idx) => {
    const row = Math.floor(idx / perRow);
    const col = idx % perRow;
    const fx = col * spacingX - offsetX;
    const fy = row * spacingY - offsetY;
    return {
      ...node,
      fx,
      fy,
      x: fx,
      y: fy,
    };
  });
  const lookup = new Map(positioned.map((node) => [node.id, node]));
  return nodes.map((node) => lookup.get(node.id) ?? node);
}

function NodeTooltip({ node }: { node: SystemGraphNode }) {
  return (
    <div className="space-y-1">
      <p className="text-sm font-semibold text-foreground">{node.name}</p>
      <p className="text-[11px] text-muted-foreground">
        Drift {node.driftScore?.toFixed?.(1) ?? node.driftScore} · Activity {node.activityScore?.toFixed?.(1) ?? node.activityScore ?? "n/a"}
      </p>
      <div className="text-[11px] text-muted-foreground">
        <p>Open doc issues: {node.docIssueCount ?? 0}</p>
        <p>Signals · Git {node.gitCount ?? 0} · Slack {node.slackCount ?? 0} · Tickets {node.ticketCount ?? 0} · Support {node.supportCount ?? 0}</p>
      </div>
    </div>
  );
}

function LinkTooltip({ link }: { link: ForceGraphLink }) {
  const source = typeof link.source === "object" ? link.source.name ?? link.source.id : link.source;
  const target = typeof link.target === "object" ? link.target.name ?? link.target.id : link.target;
  return (
    <div className="space-y-1">
      <p className="text-sm font-semibold text-foreground">
        {source} → {target}
      </p>
      <p className="text-[11px] text-muted-foreground">
        Drifted doc issues: {link.docIssueCount ?? 0} · Dominant medium: {(link.medium ?? "doc").toUpperCase()}
      </p>
      <div className="text-[11px] text-muted-foreground">
        <p>Signals · Git {link.gitCount ?? 0} · Slack {link.slackCount ?? 0}</p>
        <p>Tickets {link.ticketCount ?? 0} · Support {link.supportCount ?? 0}</p>
      </div>
    </div>
  );
}

