"use client";

import React, {
  forwardRef,
  memo,
  useCallback,
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import type { GraphExplorerEdge, GraphExplorerNode } from "./types";
import { getColorForNode } from "./utils";

declare global {
  interface Window {
    __brainGraphLayout?: Array<{ id: string; x: number; y: number }>;
    __brainGraphViewState?: {
      allowPanZoom: boolean;
      layoutStyle: "radial" | "neo4j";
      nodeCount: number;
    };
  }
}

type PositionedNode = GraphExplorerNode & {
  layoutX: number;
  layoutY: number;
};

const MIN_SCALE = 0.6;
const MAX_SCALE = 4;
const DEFAULT_PADDING = 60;

const EDGE_TYPE_STYLES: Record<string, { color: string; width: number }> = {
  ABOUT_COMPONENT: { color: "rgba(248, 113, 38, 0.65)", width: 1.8 },
  HAS_COMPONENT: { color: "rgba(14, 165, 233, 0.65)", width: 1.7 },
  DOC_DOCUMENTS_COMPONENT: { color: "rgba(190, 242, 100, 0.65)", width: 1.6 },
  DESCRIBES_COMPONENT: { color: "rgba(196, 181, 253, 0.6)", width: 1.6 },
  TOUCHES_COMPONENT: { color: "rgba(248, 250, 252, 0.45)", width: 1.5 },
  MODIFIES_COMPONENT: { color: "rgba(249, 115, 22, 0.7)", width: 1.8 },
  EXPOSES_ENDPOINT: { color: "rgba(56, 189, 248, 0.65)", width: 1.6 },
};
const DEFAULT_EDGE_STYLE = { color: "rgba(94, 109, 126, 0.6)", width: 1.5 };
const EDGE_TOOLTIP_MAX_LINES = 5;

type GraphCanvasProps = {
  nodes: GraphExplorerNode[];
  edges: GraphExplorerEdge[];
  selectedNodeId?: string | null;
  hoveredNodeId?: string | null;
  labelFilter?: string | null;
  recentNodeHighlights?: Set<string>;
  recentEdgeHighlights?: Set<string>;
  onSelectNode: (node: GraphExplorerNode | null) => void;
  onHoverNode: (node: GraphExplorerNode | null) => void;
  focusNodeIds?: string[];
  allowPanZoom?: boolean;
  layoutStyle?: "radial" | "neo4j";
  autoFocus?: boolean;
  testHooksEnabled?: boolean;
};

export type GraphCanvasHandle = {
  focusNodes: (nodeIds?: string[]) => void;
  resetView: () => void;
};

type ViewState = {
  scale: number;
  panX: number;
  panY: number;
};

const defaultView: ViewState = { scale: 1, panX: 0, panY: 0 };

const GraphCanvasComponent = forwardRef<GraphCanvasHandle, GraphCanvasProps>(function GraphCanvasComponent(
  {
    nodes,
    edges,
    selectedNodeId,
    hoveredNodeId,
    labelFilter,
    recentNodeHighlights,
    recentEdgeHighlights,
    onSelectNode,
    onHoverNode,
    focusNodeIds,
    allowPanZoom = true,
    layoutStyle = "radial",
    autoFocus = true,
    testHooksEnabled = false,
  },
  ref,
) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({ width: 640, height: 520 });
  const [view, setView] = useState<ViewState>(defaultView);
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
  const viewRef = useRef(view);
  const pointerRef = useRef<{ dragging: boolean; lastX: number; lastY: number; moved: boolean }>({
    dragging: false,
    lastX: 0,
    lastY: 0,
    moved: false,
  });
  const previousLayoutMapRef = useRef<Map<string, PositionedNode> | null>(null);

  const recentNodeKey = useMemo(() => Array.from(recentNodeHighlights ?? []).join("|"), [recentNodeHighlights]);
  const recentEdgeKey = useMemo(() => Array.from(recentEdgeHighlights ?? []).join("|"), [recentEdgeHighlights]);

  const layoutMap = useMemo(
    () => (layoutStyle === "neo4j" ? buildNeo4jLayout(nodes) : buildDeterministicLayout(nodes)),
    [layoutStyle, nodes],
  );
  const neighborMap = useMemo(() => buildNeighborMap(edges), [edges]);

  const setViewState = useCallback((next: ViewState) => {
    viewRef.current = next;
    setView(next);
  }, []);

  const focusNodes = useCallback(
    (targetIds?: string[]) => {
      const entries = targetIds?.length
        ? targetIds.map((id) => layoutMap.get(id)).filter((entry): entry is PositionedNode => Boolean(entry))
        : Array.from(layoutMap.values());
      if (!entries.length) {
        setViewState(defaultView);
        return;
      }
      const bounds = computeBounds(entries);
      const padding = DEFAULT_PADDING;
      const width = Math.max(bounds.maxX - bounds.minX, 1);
      const height = Math.max(bounds.maxY - bounds.minY, 1);
      const scaleX = (size.width - padding) / width;
      const scaleY = (size.height - padding) / height;
      const nextScale = clamp(Math.min(scaleX, scaleY), MIN_SCALE, MAX_SCALE);
      const centerX = (bounds.minX + bounds.maxX) / 2;
      const centerY = (bounds.minY + bounds.maxY) / 2;
      setViewState({
        scale: Number.isFinite(nextScale) ? nextScale : 1,
        panX: -centerX,
        panY: -centerY,
      });
    },
    [layoutMap, setViewState, size.height, size.width],
  );

  const resetView = useCallback(() => {
    focusNodes();
  }, [focusNodes]);

  useImperativeHandle(
    ref,
    () => ({
      focusNodes,
      resetView,
    }),
    [focusNodes, resetView],
  );

  useLayoutEffect(() => {
    const updateSize = () => {
      const target = wrapperRef.current;
      if (!target) return;
      const rect = target.getBoundingClientRect();
      setSize({
        width: Math.max(300, rect.width),
        height: Math.max(320, rect.height),
      });
    };
    updateSize();
    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(() => updateSize());
      if (wrapperRef.current) {
        observer.observe(wrapperRef.current);
      }
      return () => observer.disconnect();
    }
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  useEffect(() => {
    if (!layoutMap.size) {
      return;
    }
    if (size.width <= 300 || size.height <= 320) {
      return;
    }
    // Lock viewport: only refit when the underlying layout map instance changes
    if (!autoFocus && layoutStyle === "neo4j") {
      if (previousLayoutMapRef.current === layoutMap) {
        return;
      }
      previousLayoutMapRef.current = layoutMap;
      focusNodes(focusNodeIds && focusNodeIds.length ? focusNodeIds : undefined);
      return;
    }
    // When autoFocus is true, fit whenever layout, focus, or size changes
    if (autoFocus) {
      focusNodes(focusNodeIds && focusNodeIds.length ? focusNodeIds : undefined);
    }
  }, [autoFocus, layoutStyle, focusNodeIds?.join("|"), layoutMap, size.height, size.width, focusNodes]);

  useEffect(() => {
    if (!testHooksEnabled || typeof window === "undefined") {
      return;
    }
    window.__brainGraphLayout = Array.from(layoutMap.values()).map((entry) => ({
      id: entry.id,
      x: entry.layoutX,
      y: entry.layoutY,
    }));
    window.__brainGraphViewState = {
      allowPanZoom,
      layoutStyle,
      nodeCount: layoutMap.size,
    };
    return () => {
      delete window.__brainGraphLayout;
      delete window.__brainGraphViewState;
    };
  }, [allowPanZoom, layoutMap, layoutStyle, testHooksEnabled]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
    canvas.width = size.width * dpr;
    canvas.height = size.height * dpr;
    canvas.style.width = `${size.width}px`;
    canvas.style.height = `${size.height}px`;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, size.width, size.height);
    ctx.fillStyle = "#1f2430";
    ctx.fillRect(0, 0, size.width, size.height);
    ctx.save();
    ctx.translate(size.width / 2, size.height / 2);
    ctx.scale(view.scale, view.scale);
    ctx.translate(view.panX, view.panY);
    drawGraph(ctx, {
      layoutMap,
      edges,
      neighborMap,
      selectedNodeId,
      hoveredNodeId,
      hoveredEdgeId,
      labelFilter,
      recentNodeHighlights,
      recentNodeKey,
      recentEdgeHighlights,
      recentEdgeKey,
    });
    ctx.restore();
  }, [
    layoutMap,
    edges,
    neighborMap,
    selectedNodeId,
    hoveredNodeId,
    hoveredEdgeId,
    labelFilter,
    recentNodeKey,
    recentEdgeKey,
    size.height,
    size.width,
    view.panX,
    view.panY,
    view.scale,
  ]);

  const toWorldPoint = useCallback(
    (clientX: number, clientY: number) => {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) {
        return { x: 0, y: 0 };
      }
      const localX = clientX - rect.left - size.width / 2;
      const localY = clientY - rect.top - size.height / 2;
      const worldX = localX / viewRef.current.scale - viewRef.current.panX;
      const worldY = localY / viewRef.current.scale - viewRef.current.panY;
      return { x: worldX, y: worldY };
    },
    [size.height, size.width],
  );

  const pickNodeId = useCallback(
    (clientX: number, clientY: number) => {
      const pt = toWorldPoint(clientX, clientY);
      let winner: string | null = null;
      let minDistance = 18;
      layoutMap.forEach((entry) => {
        const dist = Math.hypot(entry.layoutX - pt.x, entry.layoutY - pt.y);
        if (dist < minDistance) {
          winner = entry.id;
          minDistance = dist;
        }
      });
      return winner;
    },
    [layoutMap, toWorldPoint],
  );

  const pickEdgeId = useCallback(
    (clientX: number, clientY: number) => {
      const { x, y } = toWorldPoint(clientX, clientY);
      let winner: string | null = null;
      let minDistance = 14;
      edges.forEach((edge) => {
        const source = layoutMap.get(edge.source);
        const target = layoutMap.get(edge.target);
        if (!source || !target) return;
        const dx = target.layoutX - source.layoutX;
        const dy = target.layoutY - source.layoutY;
        const lengthSq = dx * dx + dy * dy;
        if (lengthSq === 0) return;
        const t = Math.max(0, Math.min(1, ((x - source.layoutX) * dx + (y - source.layoutY) * dy) / lengthSq));
        const projX = source.layoutX + t * dx;
        const projY = source.layoutY + t * dy;
        const dist = Math.hypot(x - projX, y - projY);
        if (dist < minDistance) {
          minDistance = dist;
          winner = edge.id;
        }
      });
      return winner;
    },
    [edges, layoutMap, toWorldPoint],
  );

  const handlePointerDown = useCallback((event: React.PointerEvent<HTMLCanvasElement>) => {
    if (event.button !== 0) return;
    event.preventDefault();
    pointerRef.current = { dragging: true, lastX: event.clientX, lastY: event.clientY, moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  }, []);

  const handlePointerMove = useCallback(
    (event: React.PointerEvent<HTMLCanvasElement>) => {
      const state = pointerRef.current;
      if (state.dragging) {
        event.preventDefault();
        const dx = event.clientX - state.lastX;
        const dy = event.clientY - state.lastY;
        state.lastX = event.clientX;
        state.lastY = event.clientY;
        if (allowPanZoom) {
        if (Math.abs(dx) > 1 || Math.abs(dy) > 1) {
          state.moved = true;
        }
        setViewState((prev) => ({
          ...prev,
          panX: prev.panX + dx / prev.scale,
          panY: prev.panY + dy / prev.scale,
        }));
        } else {
          state.moved = false;
        }
      } else {
        const nodeId = pickNodeId(event.clientX, event.clientY);
        onHoverNode(nodeId ? layoutMap.get(nodeId) ?? null : null);
        const edgeId = pickEdgeId(event.clientX, event.clientY);
        setHoveredEdgeId(edgeId);
      }
    },
    [allowPanZoom, layoutMap, onHoverNode, pickEdgeId, pickNodeId, setViewState],
  );

  const handlePointerUp = useCallback(
    (event: React.PointerEvent<HTMLCanvasElement>) => {
      const state = pointerRef.current;
      if (state.dragging && !state.moved) {
        const nodeId = pickNodeId(event.clientX, event.clientY);
        onSelectNode(nodeId ? layoutMap.get(nodeId) ?? null : null);
      }
      state.dragging = false;
      state.moved = false;
      event.currentTarget.releasePointerCapture(event.pointerId);
    },
    [layoutMap, onSelectNode, pickNodeId],
  );

  const handlePointerLeave = useCallback(() => {
    pointerRef.current.dragging = false;
    pointerRef.current.moved = false;
    onHoverNode(null);
    setHoveredEdgeId(null);
  }, [onHoverNode]);

  const handleWheel = useCallback(
    (event: React.WheelEvent<HTMLCanvasElement>) => {
      if (!allowPanZoom) {
        return;
      }
      event.preventDefault();
      const scaleFactor = Math.exp(-event.deltaY * 0.001);
      setViewState((prev) => {
        const nextScale = clamp(prev.scale * scaleFactor, MIN_SCALE, MAX_SCALE);
        if (nextScale === prev.scale) {
          return prev;
        }
        const rect = canvasRef.current?.getBoundingClientRect();
        if (!rect) {
          return { ...prev, scale: nextScale };
        }
        const cursorX = event.clientX - rect.left - size.width / 2;
        const cursorY = event.clientY - rect.top - size.height / 2;
        const worldX = cursorX / prev.scale - prev.panX;
        const worldY = cursorY / prev.scale - prev.panY;
        const nextPanX = cursorX / nextScale - worldX;
        const nextPanY = cursorY / nextScale - worldY;
        return { scale: nextScale, panX: nextPanX, panY: nextPanY };
      });
    },
    [allowPanZoom, setViewState, size.height, size.width],
  );

  if (!nodes.length) {
    return (
      <div className="flex h-full w-full items-center justify-center rounded-2xl bg-slate-950 text-sm text-slate-400">Loading graph…</div>
    );
  }

  return (
    <div
      ref={wrapperRef}
      className="relative h-full w-full overflow-hidden rounded-2xl border border-slate-800 bg-slate-950"
      data-testid="graph-canvas"
      data-layout-style={layoutStyle}
      data-allow-pan-zoom={allowPanZoom ? "true" : "false"}
    >
      <canvas
        ref={canvasRef}
        className={`h-full w-full ${allowPanZoom ? "cursor-grab" : "cursor-default"}`}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerLeave}
        onWheel={allowPanZoom ? handleWheel : undefined}
      />
    </div>
  );
});

function edgeStyleFor(type?: string | null) {
  if (type) {
    const normalized = type.trim().toUpperCase();
    if (EDGE_TYPE_STYLES[normalized]) {
      return EDGE_TYPE_STYLES[normalized];
    }
  }
  return DEFAULT_EDGE_STYLE;
}

function drawRoundedRect(ctx: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, radius: number) {
  const effectiveRadius = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + effectiveRadius, y);
  ctx.lineTo(x + width - effectiveRadius, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + effectiveRadius);
  ctx.lineTo(x + width, y + height - effectiveRadius);
  ctx.quadraticCurveTo(x + width, y + height, x + width - effectiveRadius, y + height);
  ctx.lineTo(x + effectiveRadius, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - effectiveRadius);
  ctx.lineTo(x, y + effectiveRadius);
  ctx.quadraticCurveTo(x, y, x + effectiveRadius, y);
  ctx.closePath();
}

function drawGraph(
  ctx: CanvasRenderingContext2D,
  opts: {
    layoutMap: Map<string, PositionedNode>;
    edges: GraphExplorerEdge[];
    neighborMap: Map<string, Set<string>>;
    selectedNodeId?: string | null;
    hoveredNodeId?: string | null;
    hoveredEdgeId?: string | null;
    labelFilter?: string | null;
    recentNodeHighlights?: Set<string>;
    recentNodeKey: string;
    recentEdgeHighlights?: Set<string>;
    recentEdgeKey: string;
  },
) {
  const {
    layoutMap,
    edges,
    neighborMap,
    selectedNodeId,
    hoveredNodeId,
    hoveredEdgeId,
    labelFilter,
    recentNodeHighlights,
    recentEdgeHighlights,
  } = opts;
  const anchorId = hoveredNodeId || selectedNodeId || null;
  const anchorNeighbors = anchorId ? neighborMap.get(anchorId) : undefined;

  const anchorTooltipLines: string[] = [];
  let hoveredEdgeEntry: { edge: GraphExplorerEdge; midX: number; midY: number; sourceTitle: string; targetTitle: string } | null = null;
  const anchorEntry = anchorId ? layoutMap.get(anchorId) : null;

  edges.forEach((edge) => {
    const source = layoutMap.get(edge.source);
    const target = layoutMap.get(edge.target);
    if (!source || !target) return;
    const highlight =
      anchorId &&
      (edge.source === anchorId ||
        edge.target === anchorId ||
        anchorNeighbors?.has(edge.source) ||
        anchorNeighbors?.has(edge.target));
    const recent = recentEdgeHighlights?.has(edge.id);
    const baseStyle = edgeStyleFor(edge.type);
    const isHovered = hoveredEdgeId && edge.id === hoveredEdgeId;
    const edgeColor = recent
      ? "rgba(248, 250, 252, 0.95)"
      : isHovered
        ? "rgba(248, 250, 252, 0.8)"
        : highlight
          ? "rgba(248, 113, 38, 0.65)"
          : baseStyle.color;
    const widthBoost = highlight ? 0.35 : 0;
    const edgeWidth = recent
      ? baseStyle.width + 1
      : isHovered
        ? baseStyle.width + 0.9
        : baseStyle.width + widthBoost;
    ctx.beginPath();
    ctx.moveTo(source.layoutX, source.layoutY);
    ctx.lineTo(target.layoutX, target.layoutY);
    ctx.strokeStyle = edgeColor;
    ctx.lineWidth = edgeWidth;
    ctx.stroke();

    const midX = (source.layoutX + target.layoutX) / 2;
    const midY = (source.layoutY + target.layoutY) / 2;
    if (edge.type) {
      ctx.save();
      ctx.font = "9px Inter, system-ui, -apple-system, sans-serif";
      ctx.fillStyle = "rgba(148, 163, 184, 0.8)";
      ctx.textAlign = "center";
      ctx.fillText(edge.type, midX, midY - 4);
      ctx.restore();
    }

    if (isHovered) {
      hoveredEdgeEntry = {
        edge,
        midX,
        midY,
        sourceTitle: source.title ?? source.id,
        targetTitle: target.title ?? target.id,
      };
    }

    if (anchorId && anchorTooltipLines.length < EDGE_TOOLTIP_MAX_LINES) {
      if (edge.source === anchorId || edge.target === anchorId) {
        const neighborId = edge.source === anchorId ? edge.target : edge.source;
        const neighborNode = layoutMap.get(neighborId);
        const neighborTitle = neighborNode?.title ?? neighborId;
        anchorTooltipLines.push(`${edge.type ?? "RELATED"} → ${neighborTitle}`);
      }
    }
  });

  layoutMap.forEach((entry) => {
    const dimmed =
      (labelFilter && entry.label !== labelFilter) ||
      (anchorId && entry.id !== anchorId && !(anchorNeighbors?.has(entry.id) ?? false));
    const color = getColorForNode(entry.label, entry.modality);
    const degree = neighborMap.get(entry.id)?.size ?? 0;
    const radius = 7 + Math.min(4, Math.sqrt(degree));
    ctx.save();
    ctx.globalAlpha = dimmed ? 0.25 : 1;
    ctx.beginPath();
    ctx.fillStyle = color;
    ctx.arc(entry.layoutX, entry.layoutY, radius, 0, Math.PI * 2, false);
    ctx.fill();
    ctx.globalAlpha = 1;

    if (recentNodeHighlights?.has(entry.id)) {
      ctx.beginPath();
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = "rgba(248, 250, 252, 0.9)";
      ctx.arc(entry.layoutX, entry.layoutY, radius + 3, 0, Math.PI * 2, false);
      ctx.stroke();
    }

    if (selectedNodeId && entry.id === selectedNodeId) {
      ctx.beginPath();
      ctx.lineWidth = 2.4;
      ctx.strokeStyle = "#f97316";
      ctx.arc(entry.layoutX, entry.layoutY, radius + 4, 0, Math.PI * 2, false);
      ctx.stroke();
    }

    if (hoveredNodeId && entry.id === hoveredNodeId) {
      ctx.beginPath();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "rgba(226, 232, 240, 0.9)";
      ctx.arc(entry.layoutX, entry.layoutY, radius + 3, 0, Math.PI * 2, false);
      ctx.stroke();
    }

    if ((entry.id === hoveredNodeId || entry.id === selectedNodeId) && entry.title) {
      const label = entry.title.length > 32 ? `${entry.title.slice(0, 32)}…` : entry.title;
      ctx.font = "11px Inter, system-ui, -apple-system, sans-serif";
      ctx.fillStyle = "rgba(226, 232, 240, 0.95)";
      ctx.strokeStyle = "rgba(15, 23, 42, 0.75)";
      ctx.lineWidth = 3;
      ctx.strokeText(label, entry.layoutX + radius + 6, entry.layoutY - radius - 4);
      ctx.fillText(label, entry.layoutX + radius + 6, entry.layoutY - radius - 4);
    }
    ctx.restore();
  });

  if (anchorEntry && anchorTooltipLines.length) {
    const paddingX = 8;
    const paddingY = 6;
    const lineHeight = 12;
    const tooltipX = anchorEntry.layoutX + 18;
    const tooltipY = anchorEntry.layoutY - (anchorTooltipLines.length * lineHeight + paddingY * 2);
    ctx.save();
    ctx.font = "10px Inter, system-ui, -apple-system, sans-serif";
    const maxLineWidth = Math.max(...anchorTooltipLines.map((line) => ctx.measureText(line).width), 80);
    ctx.fillStyle = "rgba(15, 23, 42, 0.92)";
    ctx.strokeStyle = "rgba(148, 163, 184, 0.6)";
    const boxWidth = maxLineWidth + paddingX * 2;
    const boxHeight = anchorTooltipLines.length * lineHeight + paddingY * 2;
    drawRoundedRect(ctx, tooltipX, tooltipY, boxWidth, boxHeight, 6);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "rgba(226, 232, 240, 0.92)";
    anchorTooltipLines.forEach((line, index) => {
      ctx.fillText(line, tooltipX + paddingX, tooltipY + paddingY + lineHeight * (index + 0.8));
    });
    ctx.restore();
  }

  if (hoveredEdgeEntry) {
    const { edge, midX, midY, sourceTitle, targetTitle } = hoveredEdgeEntry;
    const paddingX = 8;
    const paddingY = 6;
    const lineHeight = 12;
    const lines = [`${sourceTitle}`, `${edge.type ?? "RELATED"} → ${targetTitle}`];
    ctx.save();
    ctx.font = "10px Inter, system-ui, -apple-system, sans-serif";
    const maxLineWidth = Math.max(...lines.map((line) => ctx.measureText(line).width), 80);
    ctx.fillStyle = "rgba(15, 23, 42, 0.92)";
    ctx.strokeStyle = "rgba(148, 163, 184, 0.6)";
    const boxWidth = maxLineWidth + paddingX * 2;
    const boxHeight = lines.length * lineHeight + paddingY * 2;
    const tooltipX = midX + 12;
    const tooltipY = midY - (boxHeight + 4);
    drawRoundedRect(ctx, tooltipX, tooltipY, boxWidth, boxHeight, 6);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "rgba(226, 232, 240, 0.92)";
    lines.forEach((line, index) => {
      ctx.fillText(line, tooltipX + paddingX, tooltipY + paddingY + lineHeight * (index + 0.8));
    });
    ctx.restore();
  }
}

function computeBounds(nodes: PositionedNode[]) {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  nodes.forEach((node) => {
    minX = Math.min(minX, node.layoutX);
    minY = Math.min(minY, node.layoutY);
    maxX = Math.max(maxX, node.layoutX);
    maxY = Math.max(maxY, node.layoutY);
  });
  return { minX, minY, maxX, maxY };
}

function buildDeterministicLayout(nodes: GraphExplorerNode[]) {
  const centerNodes: GraphExplorerNode[] = [];
  const peripheralGroups = new Map<string, GraphExplorerNode[]>();

  nodes.forEach((node) => {
    const isComponent = node.label === "Component" || node.modality === "component";
    if (isComponent) {
      centerNodes.push(node);
      return;
    }
    const key = node.modality ?? node.label ?? "Other";
    if (!peripheralGroups.has(key)) {
      peripheralGroups.set(key, []);
    }
    peripheralGroups.get(key)!.push(node);
  });

  const map = new Map<string, PositionedNode>();

  // Place components in the center in a tiny ring (or exact center if only one).
  const sortedCenter = centerNodes.slice().sort((a, b) => a.id.localeCompare(b.id));
  const centerRadius = sortedCenter.length > 1 ? 40 : 0;
  sortedCenter.forEach((node, idx) => {
    const angle = sortedCenter.length > 1 ? (idx / sortedCenter.length) * Math.PI * 2 : 0;
    const layoutX = centerRadius ? Math.cos(angle) * centerRadius : 0;
    const layoutY = centerRadius ? Math.sin(angle) * centerRadius : 0;
    map.set(node.id, { ...node, layoutX, layoutY });
  });

  // Arrange Slack/Git/other events in concentric rings around the components.
  const sortedGroups = Array.from(peripheralGroups.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  sortedGroups.forEach(([key, group], groupIndex) => {
    const baseRadius = 140;
    const radius = baseRadius + groupIndex * 90;
    const sortedNodes = group.slice().sort((a, b) => a.id.localeCompare(b.id));
    sortedNodes.forEach((node, idx) => {
      const angle = sortedNodes.length > 0 ? (idx / sortedNodes.length) * Math.PI * 2 : 0;
      const jitter = 0.08 * Math.sin(idx); // small deterministic offset to avoid perfect circles
      const finalAngle = angle + jitter;
      const layoutX = Math.cos(finalAngle) * radius;
      const layoutY = Math.sin(finalAngle) * radius;
      map.set(node.id, { ...node, layoutX, layoutY });
    });
  });

  // Fallback: if we had no labeled components, still avoid collapsing to origin.
  if (map.size === 0 && nodes.length) {
    const radius = 120;
    const sortedNodes = nodes.slice().sort((a, b) => a.id.localeCompare(b.id));
    sortedNodes.forEach((node, idx) => {
      const angle = sortedNodes.length > 0 ? (idx / sortedNodes.length) * Math.PI * 2 : 0;
      const layoutX = Math.cos(angle) * radius;
      const layoutY = Math.sin(angle) * radius;
      map.set(node.id, { ...node, layoutX, layoutY });
    });
  }

  return map;
}

function buildNeo4jLayout(nodes: GraphExplorerNode[]) {
  const columnOrder = [
    "issue",
    "supportcase",
    "slackevent",
    "slackthread",
    "gitevent",
    "pr",
    "repository",
    "codeartifact",
    "source",
    "chunk",
    "transcriptchunk",
    "component",
    "service",
    "apiendpoint",
    "doc",
    "activitysignal",
    "impactevent",
    "channel",
    "playlist",
    "video",
  ];
  const aliasMap: Record<string, string> = {
    slack: "slackevent",
    support: "supportcase",
    git: "gitevent",
    repo: "repository",
    repositories: "repository",
    api: "apiendpoint",
    endpoint: "apiendpoint",
    docs: "doc",
    document: "doc",
    documents: "doc",
    component: "component",
    components: "component",
    service: "service",
    services: "service",
    transcript: "transcriptchunk",
    transcription: "transcriptchunk",
  };
  const columnMap = new Map<string, number>();
  columnOrder.forEach((label, idx) => columnMap.set(label, idx));

  const groupedNodes = new Map<string, GraphExplorerNode[]>();
  nodes.forEach((node) => {
    const rawLabel = (node.label || "").toLowerCase();
    const rawModality = (node.modality || "").toLowerCase();
    const alias = aliasMap[rawModality] ?? aliasMap[rawLabel];
    const preferredKey =
      (rawModality && columnMap.has(rawModality) && rawModality) ||
      (alias && columnMap.has(alias) && alias) ||
      (rawLabel && columnMap.has(rawLabel) && rawLabel) ||
      "other";
    if (!groupedNodes.has(preferredKey)) {
      groupedNodes.set(preferredKey, []);
    }
    groupedNodes.get(preferredKey)!.push(node);
  });

  const orderedColumns = columnOrder.filter((label) => groupedNodes.has(label));
  const extraColumns = Array.from(groupedNodes.keys()).filter((key) => !columnMap.has(key));
  extraColumns.sort((a, b) => a.localeCompare(b));
  const fullColumnOrder = orderedColumns.concat(extraColumns);

  const rowSpacing = 70; // Vertical distance between nodes within a column
  const columnSpacing = 120; // Horizontal distance between label groups (columns)
  const baseOffset = (fullColumnOrder.length - 1) / 2;

  const map = new Map<string, PositionedNode>();
  fullColumnOrder.forEach((key, columnIdx) => {
    const group = groupedNodes.get(key);
    if (!group) {
      return;
    }
    const sorted = group.slice().sort((a, b) => (a.id || "").localeCompare(b.id || ""));
    const columnX = (columnIdx - baseOffset) * columnSpacing;
    const startY = -((sorted.length - 1) / 2) * rowSpacing;
    sorted.forEach((node, idx) => {
      const jitterX = deterministicJitter(`${node.id}:x`, 14);
      const jitterY = deterministicJitter(`${node.id}:y`, 14);
      const layoutX = columnX + jitterX; // column position
      const layoutY = startY + idx * rowSpacing + jitterY; // spread vertically within column
      map.set(node.id, { ...node, layoutX, layoutY });
    });
  });

  return map;
}

function buildNeighborMap(edges: GraphExplorerEdge[]) {
  const map = new Map<string, Set<string>>();
  edges.forEach((edge) => {
    if (!map.has(edge.source)) {
      map.set(edge.source, new Set());
    }
    if (!map.has(edge.target)) {
      map.set(edge.target, new Set());
    }
    map.get(edge.source)?.add(edge.target);
    map.get(edge.target)?.add(edge.source);
  });
  return map;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function deterministicJitter(key: string, spread: number) {
  let hash = 0;
  for (let idx = 0; idx < key.length; idx += 1) {
    hash = (hash * 31 + key.charCodeAt(idx)) & 0xffffffff;
  }
  const normalized = (hash % 1000) / 1000 - 0.5;
  return normalized * spread;
}

export const GraphCanvas = memo(GraphCanvasComponent);

