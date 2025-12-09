import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Flame } from "lucide-react";

import type { ComponentNode } from "@/lib/types";
import { fetchActivityGraphComponent, fetchActivityGraphHotspots, isActivityGraphAvailable, type ActivityGraphSnapshot } from "@/lib/api/activity-graph";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const DEFAULT_WINDOW = "7d";

interface ActivityGraphPanelProps {
  projectId: string;
  components: ComponentNode[];
}

export function ActivityGraphPanel({ projectId, components }: ActivityGraphPanelProps) {
  const supportedComponents = useMemo(
    () => components.filter((component) => Boolean(component.activityGraphId)),
    [components],
  );
  const hasMappings = supportedComponents.length > 0;
  const enabled = isActivityGraphAvailable() && hasMappings;
  const [selectedComponentId, setSelectedComponentId] = useState<string>(() => supportedComponents[0]?.id ?? "");
  const [snapshot, setSnapshot] = useState<ActivityGraphSnapshot | null>(null);
  const [hotspots, setHotspots] = useState<ActivityGraphSnapshot[]>([]);
  const [componentLoading, setComponentLoading] = useState(false);
  const [hotspotLoading, setHotspotLoading] = useState(false);
  const [componentError, setComponentError] = useState<string | null>(null);
  const [hotspotError, setHotspotError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    if (!selectedComponentId && supportedComponents[0]) {
      setSelectedComponentId(supportedComponents[0].id);
      return;
    }
    const selectionStillValid = supportedComponents.some((component) => component.id === selectedComponentId);
    if (!selectionStillValid && supportedComponents[0]) {
      setSelectedComponentId(supportedComponents[0].id);
    }
  }, [enabled, selectedComponentId, supportedComponents]);

  const selectedComponent = supportedComponents.find((component) => component.id === selectedComponentId);
  const activityGraphComponentId = selectedComponent?.activityGraphId;

  useEffect(() => {
    if (!enabled || !activityGraphComponentId) {
      setSnapshot(null);
      setComponentError(
        !enabled
          ? null
          : "Activity graph data is not available for this component in the current dataset.",
      );
      return;
    }
    let cancelled = false;
    setComponentLoading(true);
    setComponentError(null);
    fetchActivityGraphComponent(activityGraphComponentId, DEFAULT_WINDOW)
      .then((result) => {
        if (!cancelled) {
          setSnapshot(result);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setSnapshot(null);
          setComponentError(error instanceof Error ? error.message : "Failed to load activity graph.");
          console.error("[ActivityGraphPanel] Failed to load component snapshot", activityGraphComponentId, error);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setComponentLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activityGraphComponentId, enabled]);

  useEffect(() => {
    if (!enabled) {
      setHotspots([]);
      setHotspotError(null);
      return;
    }
    let cancelled = false;
    setHotspotLoading(true);
    setHotspotError(null);
    fetchActivityGraphHotspots({ limit: 3, window: DEFAULT_WINDOW })
      .then((payload) => {
        if (!cancelled) {
          setHotspots(payload.results);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setHotspots([]);
          setHotspotError(error instanceof Error ? error.message : "Failed to load hotspots.");
          console.error("[ActivityGraphPanel] Failed to load hotspots", error);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setHotspotLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  const componentOptions = useMemo(
    () => supportedComponents.map((component) => ({ id: component.id, name: component.name })),
    [supportedComponents],
  );

  if (!enabled || !componentOptions.length) {
    return null;
  }

  return (
    <Card className="border border-blue-200/30 bg-blue-950/30 shadow-lg shadow-blue-900/20">
      <CardHeader className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <CardTitle className="flex items-center gap-2 text-base text-blue-100">
            <Flame className="h-4 w-4 text-orange-300" />
            Activity graph
          </CardTitle>
          <CardDescription className="text-xs text-blue-200/80">
            Live Git + Slack signals aggregated over {snapshot?.timeWindowLabel ?? "the selected window"}.
          </CardDescription>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Select value={selectedComponentId} onValueChange={setSelectedComponentId}>
            <SelectTrigger className="w-48 bg-blue-950/60 text-xs text-blue-100">
              <SelectValue placeholder="Select component" />
            </SelectTrigger>
            <SelectContent align="end" className="max-h-64">
              {componentOptions.map((component) => (
                <SelectItem key={component.id} value={component.id} className="text-xs">
                  {component.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Badge variant="outline" className="rounded-full border-blue-500/40 text-[10px] text-blue-100">
            Window • {DEFAULT_WINDOW}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <MetricTile
            label="Activity score"
            value={snapshot?.activityScore.toFixed(2)}
            loading={componentLoading}
            tone="info"
          />
          <MetricTile label="Dissatisfaction" value={snapshot?.dissatisfactionScore.toFixed(2)} loading={componentLoading} tone="warn" />
          <MetricTile label="Git events" value={snapshot?.gitEvents} loading={componentLoading} />
          <MetricTile label="Slack complaints" value={snapshot?.slackComplaints} loading={componentLoading} />
          <MetricTile
            label="Slack conversations"
            value={snapshot?.slackConversations}
            loading={componentLoading}
            className="sm:col-span-2 lg:col-span-1"
          />
          <MetricTile label="Open doc issues" value={snapshot?.openDocIssues} loading={componentLoading} />
        </div>
        {!componentLoading && !snapshot ? (
          <p className="text-sm text-blue-200/70">No recent activity detected for this component.</p>
        ) : null}
        {componentError ? <p className="text-sm text-destructive">{componentError}</p> : null}

        <div className="rounded-2xl border border-blue-200/20 bg-blue-950/40 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-blue-100">Hotspots</p>
              <p className="text-xs text-blue-200/70">Components with the highest dissatisfaction score</p>
            </div>
            <Badge variant="outline" className="rounded-full border-blue-500/40 text-[10px] text-blue-100">
              Top {hotspots.length || 3}
            </Badge>
          </div>
          <div className="mt-4 space-y-3">
            {hotspotLoading ? (
              <Skeleton className="h-16 w-full rounded-xl bg-blue-900/40" />
            ) : hotspotError ? (
              <p className="text-sm text-destructive">{hotspotError}</p>
            ) : hotspots.length ? (
              hotspots.map((item) => (
                <div key={item.componentId} className="flex items-center justify-between rounded-2xl border border-blue-300/20 p-3">
                  <div>
                    <p className="text-sm font-semibold text-blue-100">{item.componentName}</p>
                    <p className="text-xs text-blue-200/70">Open doc issues • {item.openDocIssues}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className="rounded-full border border-amber-500/30 bg-amber-400/10 text-xs text-amber-200">
                      {item.dissatisfactionScore.toFixed(2)}
                    </Badge>
                    <Button asChild variant="ghost" className="text-xs text-blue-200 hover:text-white">
                      <Link href={`/projects/${projectId}/components/${item.componentId}`}>Inspect</Link>
                    </Button>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm text-blue-200/70">No dissatisfied components detected for this window.</p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function MetricTile({
  label,
  value,
  loading,
  tone = "muted",
  className,
}: {
  label: string;
  value?: string | number;
  loading: boolean;
  tone?: "info" | "warn" | "muted";
  className?: string;
}) {
  if (loading) {
    return <Skeleton className={cn("h-20 rounded-2xl bg-blue-900/40", className)} />;
  }
  const toneClasses =
    tone === "warn"
      ? "text-amber-200"
      : tone === "info"
      ? "text-blue-100"
      : "text-blue-200";
  return (
    <div className={cn("rounded-2xl border border-blue-200/20 bg-blue-950/40 p-3 text-xs text-blue-200", className)}>
      <p className="text-[11px] uppercase tracking-wide text-blue-400/80">{label}</p>
      <p className={cn("pt-1 text-xl font-semibold", toneClasses)}>{value ?? "—"}</p>
    </div>
  );
}

