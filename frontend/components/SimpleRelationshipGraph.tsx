"use client";

import React, { useMemo } from "react";

import type { GraphExplorerEdge, GraphExplorerNode } from "@brain-graph-ui/types";

type PositionedNode = {
  node: GraphExplorerNode;
  x: number;
  y: number;
  color: string;
};

type PositionedLink = {
  edge: GraphExplorerEdge;
  source: PositionedNode;
  target: PositionedNode;
};

type SimpleRelationshipGraphProps = {
  nodes: GraphExplorerNode[];
  edges: GraphExplorerEdge[];
  className?: string;
};

const LABEL_COLORS: Record<string, string> = {
  component: "#0ea5e9",
  slackevent: "#facc15",
  slackthread: "#facc15",
};
const DEFAULT_EVENT_COLOR = "#fbbf24";

function getNodeColor(node: GraphExplorerNode): string {
  const raw = (node.modality ?? node.label ?? "").toLowerCase();
  if (!raw) {
    return DEFAULT_EVENT_COLOR;
  }
  return LABEL_COLORS[raw] ?? DEFAULT_EVENT_COLOR;
}

function truncateLabel(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 1)}…`;
}

function isComponent(node: GraphExplorerNode): boolean {
  return (node.label ?? "").toLowerCase() === "component" || (node.modality ?? "").toLowerCase() === "component";
}

export function SimpleRelationshipGraph({ nodes, edges, className = "" }: SimpleRelationshipGraphProps) {
  const nodeMap = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);

  const layout = useMemo(() => {
    if (!nodes.length) {
      return { positioned: new Map<string, PositionedNode>(), links: [] as PositionedLink[] };
    }

    const positioned = new Map<string, PositionedNode>();
    const links: PositionedLink[] = [];

    const componentNodes = nodes.filter(isComponent);
    const componentAngles = new Map<string, number>();
    const eventNodes = nodes.filter((node) => !isComponent(node));
    const componentCount = Math.max(componentNodes.length, 1);

    const innerRadius = componentCount > 1 ? 60 : 0;
    componentNodes.forEach((node, index) => {
      const angle = componentCount > 1 ? (index / componentCount) * Math.PI * 2 : 0;
      const x = innerRadius ? Math.cos(angle) * innerRadius : 0;
      const y = innerRadius ? Math.sin(angle) * innerRadius : 0;
      positioned.set(node.id, { node, x, y, color: getNodeColor(node) });
      componentAngles.set(node.id, angle);
    });

    const componentSet = new Set(componentNodes.map((node) => node.id));
    const groupedEvents = new Map<string, GraphExplorerNode[]>();
    const assignedEvents = new Set<string>();

    edges.forEach((edge) => {
      const source = nodeMap.get(edge.source);
      const target = nodeMap.get(edge.target);
      if (!source || !target) {
        return;
      }
      const sourceIsComponent = componentSet.has(source.id);
      const targetIsComponent = componentSet.has(target.id);
      if (sourceIsComponent === targetIsComponent) {
        return;
      }
      const componentId = sourceIsComponent ? source.id : target.id;
      const eventNode = sourceIsComponent ? target : source;
      if (assignedEvents.has(eventNode.id)) {
        return;
      }
      assignedEvents.add(eventNode.id);
      if (!groupedEvents.has(componentId)) {
        groupedEvents.set(componentId, []);
      }
      groupedEvents.get(componentId)!.push(eventNode);
    });

    const outerRadius = 160;
    groupedEvents.forEach((bucket, componentId) => {
      const component = positioned.get(componentId);
      const baseAngle = componentAngles.get(componentId) ?? 0;
      if (!component) {
        return;
      }
      const wedge = componentCount > 1 ? Math.PI / componentCount : Math.PI * 2;
      bucket.forEach((eventNode, index) => {
        const t = bucket.length > 0 ? (index + 0.5) / bucket.length - 0.5 : 0;
        const angle = baseAngle + wedge * t;
        const x = component.x + Math.cos(angle) * outerRadius;
        const y = component.y + Math.sin(angle) * outerRadius;
        positioned.set(eventNode.id, { node: eventNode, x, y, color: getNodeColor(eventNode) });
      });
    });

    const remainingEvents = eventNodes.filter((node) => !positioned.has(node.id));
    if (remainingEvents.length) {
      remainingEvents.forEach((node, index) => {
        const angle = (index / remainingEvents.length) * Math.PI * 2;
        const x = Math.cos(angle) * outerRadius;
        const y = Math.sin(angle) * outerRadius;
        positioned.set(node.id, { node, x, y, color: getNodeColor(node) });
      });
    }

    edges.forEach((edge) => {
      const source = positioned.get(edge.source);
      const target = positioned.get(edge.target);
      if (source && target) {
        links.push({ edge, source, target });
      }
    });

    return { positioned, links };
  }, [edges, nodeMap, nodes]);

  if (!nodes.length) {
    return (
      <div className={`flex h-64 items-center justify-center rounded-2xl border border-slate-800 bg-slate-900/40 text-sm text-slate-400 ${className}`}>
        No relationships available for this slice.
      </div>
    );
  }

  const width = 640;
  const height = 480;
  const viewPadding = 240;

  return (
    <div className={`rounded-2xl border border-slate-800 bg-slate-950/70 p-4 ${className}`}>
      <svg viewBox={`${-viewPadding} ${-viewPadding} ${viewPadding * 2} ${viewPadding * 2}`} width={width} height={height} className="w-full">
        <defs>
          <marker id="arrowhead" markerWidth="6" markerHeight="6" refX="6" refY="3" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L6,3 L0,6 Z" fill="#1e293b" />
          </marker>
        </defs>
        {layout.links.map((link, index) => {
          const midX = (link.source.x + link.target.x) / 2;
          const midY = (link.source.y + link.target.y) / 2;
          return (
            <g key={`${link.edge.id}-${index}`}>
              <line
                x1={link.source.x}
                y1={link.source.y}
                x2={link.target.x}
                y2={link.target.y}
                stroke="#1e293b"
                strokeWidth={1}
                opacity={0.6}
                markerEnd="url(#arrowhead)"
              >
                <title>{link.edge.type ?? "RELATED"}</title>
              </line>
              {link.edge.type ? (
                <text x={midX} y={midY} fontSize={9} fill="#94a3b8" textAnchor="middle" opacity={0.8}>
                  {link.edge.type}
                </text>
              ) : null}
            </g>
          );
        })}
        {Array.from(layout.positioned.values()).map((entry) => {
          const title = entry.node.title ?? entry.node.id;
          const maxLength = isComponent(entry.node) ? 16 : 10;
          const label = truncateLabel(title, maxLength);
          const textOffset = isComponent(entry.node) ? 20 : 16;
          return (
            <g key={entry.node.id}>
              <circle cx={entry.x} cy={entry.y} r={isComponent(entry.node) ? 12 : 7} fill={entry.color} stroke="#0f172a" strokeWidth={1.5} />
              <text x={entry.x} y={entry.y + textOffset} textAnchor="middle" fontSize={isComponent(entry.node) ? 12 : 10} fill="#e2e8f0">
                {label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

