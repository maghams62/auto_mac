"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import {
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { QuadrantPoint, LiveMode } from "@/lib/types";

type QuadrantResponse = {
  points: QuadrantPoint[];
  mode?: LiveMode;
  timeWindow?: string;
};

interface QuadrantCardProps {
  projectId?: string;
}

const ACTIVITY_THRESHOLD = 50;
const DISSATISFACTION_THRESHOLD = 50;

export function QuadrantCard({ projectId }: QuadrantCardProps) {
  const [points, setPoints] = useState<QuadrantPoint[]>([]);
  const [mode, setMode] = useState<LiveMode>("synthetic");
  const [timeWindow, setTimeWindow] = useState<string>("recent");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        setLoading(true);
        const params = new URLSearchParams();
        if (projectId) params.set("projectId", projectId);
        params.set("limit", "30");
        const response = await fetch(`/api/quadrant?${params.toString()}`, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`Quadrant request failed (${response.status})`);
        }
        const payload = (await response.json()) as QuadrantResponse;
        if (!cancelled) {
          setPoints(payload.points ?? []);
          setMode(payload.mode ?? "synthetic");
          setTimeWindow(payload.timeWindow ?? "recent");
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load quadrant data");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const dataset = useMemo(() => {
    return points.map((point) => ({
      ...point,
      quadrant: resolveQuadrant(point.activityScore, point.dissatisfactionScore),
    }));
  }, [points]);

  return (
    <Card className="min-h-[360px]">
      <CardHeader className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <CardTitle>Activity vs. dissatisfaction quadrant</CardTitle>
          <CardDescription>Plot components by Cerebros activity telemetry to highlight risky divergence.</CardDescription>
        </div>
        <Badge variant="outline" className="rounded-full border-border/60 text-xs">
          {mode === "atlas" ? "Live" : "Synthetic"} • {timeWindow}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <div className="rounded-2xl border border-dashed border-border/50 p-4 text-sm text-muted-foreground">
            Fetching quadrant…
          </div>
        ) : null}
        {error ? (
          <div className="flex items-center gap-2 rounded-2xl border border-amber-400/60 bg-amber-500/10 p-4 text-sm text-amber-100">
            <AlertTriangle className="h-4 w-4" />
            {error}
          </div>
        ) : null}
        {dataset.length ? (
          <div className="h-[320px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  dataKey="activityScore"
                  domain={[0, 100]}
                  label={{ value: "Activity score", position: "insideBottomRight", offset: 0 }}
                />
                <YAxis
                  type="number"
                  dataKey="dissatisfactionScore"
                  domain={[0, 100]}
                  label={{ value: "Dissatisfaction score", angle: -90, position: "insideLeft" }}
                />
                <ReferenceLine x={ACTIVITY_THRESHOLD} stroke="hsl(var(--border))" strokeDasharray="4 4" />
                <ReferenceLine y={DISSATISFACTION_THRESHOLD} stroke="hsl(var(--border))" strokeDasharray="4 4" />
                <Tooltip content={<QuadrantTooltip />} />
                <Scatter data={dataset} fill="hsl(var(--chart-1))" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        ) : !loading ? (
          <div className="rounded-2xl border border-dashed border-border/50 p-4 text-sm text-muted-foreground">
            No quadrant data available for this project yet.
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function QuadrantTooltip({ active, payload }: any) {
  if (!active || !payload?.length) {
    return null;
  }
  const point = payload[0].payload as QuadrantPoint & { quadrant: string };
  return (
    <div className="rounded-lg border border-border bg-background/90 p-3 text-sm shadow-lg backdrop-blur">
      <p className="font-semibold">{point.componentName}</p>
      <p className="text-xs text-muted-foreground">{point.repoName}</p>
      <div className="mt-2 space-y-1 text-xs">
        <p>Activity: {point.activityScore.toFixed(1)}</p>
        <p>Dissatisfaction: {point.dissatisfactionScore.toFixed(1)}</p>
        <p>Git events: {point.gitEvents}</p>
        <p>Slack complaints: {point.slackComplaints}</p>
        <p>Doc issues: {point.docIssues}</p>
      </div>
      <p className="mt-2 text-xs font-semibold text-foreground/80">{point.quadrant}</p>
    </div>
  );
}

function resolveQuadrant(activityScore: number, dissatisfactionScore: number) {
  const activityHigh = activityScore >= ACTIVITY_THRESHOLD;
  const dissatisfactionHigh = dissatisfactionScore >= DISSATISFACTION_THRESHOLD;
  if (activityHigh && dissatisfactionHigh) {
    return "Escalate: shipping fast while sentiment is negative.";
  }
  if (activityHigh && !dissatisfactionHigh) {
    return "Healthy velocity: monitor docs to stay ahead.";
  }
  if (!activityHigh && dissatisfactionHigh) {
    return "Stale docs: Slack noise without recent commits.";
  }
  return "Quiet zone: low activity and few complaints.";
}

