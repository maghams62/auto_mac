"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { AlertTriangle } from "lucide-react";

import { AskCerebrosButton } from "@/components/common/ask-cerebros-button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ActivitySummary, fetchTopComponents, isCerebrosApiConfigured } from "@/lib/api/activity";
import { selectProjectById, useDashboardStore } from "@/lib/state/dashboard-store";
import type { Project } from "@/lib/types";
import { longDateTime } from "@/lib/utils";

export default function ProjectActivityPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const projectSelector = useMemo(() => selectProjectById(projectId), [projectId]);
  const project = useDashboardStore(projectSelector);

  const [rows, setRows] = useState<ActivitySummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isCerebrosApiConfigured()) {
      return;
    }
    let cancelled = false;
    const load = async () => {
      try {
        setLoading(true);
        const data = await fetchTopComponents({ limit: 25 });
        if (!cancelled) {
          setRows(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load activity");
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

  const filteredRows = useMemo(() => {
    if (!project) return rows;
    const componentIds = new Set(project.components.map((component) => component.id));
    const scoped = rows.filter((row) => componentIds.has(row.componentId));
    return scoped.length ? scoped : rows;
  }, [project, rows]);
  const fallbackRows = useMemo<ActivitySummary[]>(() => {
    if (!project) return [];
    return project.components
      .map((component) => {
        const gitEvents = component.sourceEvents.filter((event) => event.source === "git").length;
        const slackEvents = component.sourceEvents.filter((event) => event.source === "slack").length;
        const docDriftEvents = component.divergenceInsights.length;
        const lastTimelinePoint = component.graphSignals.timeline[component.graphSignals.timeline.length - 1];
        return {
          componentId: component.id,
          activityScore: component.graphSignals.drift.score,
          gitEvents,
          slackEvents,
          docDriftEvents,
          lastEventAt: lastTimelinePoint?.timestamp ?? null,
        };
      })
      .sort((a, b) => b.activityScore - a.activityScore);
  }, [project]);

  const activityEnabled = isCerebrosApiConfigured();
  const slashCommand = project ? `/slack docdrift ${project.name}` : "/slack docdrift";
  const rowsToRender = (filteredRows.length ? filteredRows : fallbackRows).slice(0, 25);
  const usingFallback = !filteredRows.length && Boolean(fallbackRows.length);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.5em] text-muted-foreground">Activity</p>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold text-foreground">Doc drift prioritization</h1>
          <Badge variant="outline" className="rounded-full border-border/60 text-xs">
            Cerebros ActivityService
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          Rank components by doc-drift risk using Cerebros activity telemetry. Use this list to decide where to dive deeper or hand
          off to Cerebros slash commands.
        </p>
      </div>

      {!activityEnabled ? (
        <Card className="border-dashed border-border/50">
          <CardHeader>
            <CardTitle>Backend not configured</CardTitle>
            <CardDescription>Set NEXT_PUBLIC_CEREBROS_API_BASE to enable live activity rankings.</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Until the Cerebros ActivityService is reachable, this view will remain empty. Synthetic fixtures still power the rest of
            the dashboard.
          </CardContent>
        </Card>
      ) : null}

          {(activityEnabled || rowsToRender.length) ? (
        <Card>
          <CardHeader className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
                  <CardTitle>Top components by doc drift</CardTitle>
                  <CardDescription>
                    {usingFallback
                      ? "Cerebros feed unavailable — ranking based on current snapshot."
                      : "Sorted by Cerebros activity score."}
                  </CardDescription>
            </div>
                <AskCerebrosButton command={slashCommand} label="Copy /slack docdrift prompt" size="sm" />
          </CardHeader>
          <CardContent className="space-y-4">
                {loading ? (
                  <div className="rounded-2xl border border-dashed border-border/60 p-4 text-sm text-muted-foreground">
                    Fetching latest activity…
                  </div>
                ) : null}
                {error ? (
                  <div className="flex items-center gap-2 rounded-2xl border border-amber-400/60 bg-amber-500/10 p-4 text-sm text-amber-100">
                    <AlertTriangle className="h-4 w-4" />
                    {error}
                  </div>
                ) : null}
                {rowsToRender.length ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Component</TableHead>
                        <TableHead>Activity score</TableHead>
                        <TableHead>Doc drift</TableHead>
                        <TableHead>Slack events</TableHead>
                        <TableHead>Git events</TableHead>
                        <TableHead>Last event</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rowsToRender.map((row) => (
                        <TableRow key={row.componentId}>
                          <TableCell className="font-semibold">{resolveComponentName(row.componentId, project)}</TableCell>
                          <TableCell>
                            <Badge variant="outline" className={row.docDriftEvents ? "border-red-500/40 text-red-200" : "border-border/40"}>
                              {row.activityScore.toFixed(2)}
                            </Badge>
                          </TableCell>
                          <TableCell>{row.docDriftEvents}</TableCell>
                          <TableCell>{row.slackEvents}</TableCell>
                          <TableCell>{row.gitEvents}</TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {row.lastEventAt ? longDateTime(row.lastEventAt) : "N/A"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : !loading ? (
                  <div className="rounded-2xl border border-dashed border-border/60 p-4 text-sm text-muted-foreground">
                    No activity surfaced for this project yet.
                  </div>
                ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function resolveComponentName(componentId: string, project?: Project) {
  if (!project) return componentId;
  return project.components.find((component) => component.id === componentId)?.name ?? componentId;
}


