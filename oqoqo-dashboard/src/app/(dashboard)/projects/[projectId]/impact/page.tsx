"use client";

import { useMemo } from "react";
import { useParams } from "next/navigation";

import { DependencyMap } from "@/components/impact/dependency-map";
import { ImpactAlertsPanel } from "@/components/impact/impact-alerts-panel";
import { LiveRecency } from "@/components/live/live-recency";
import { ModeBadge } from "@/components/common/mode-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { selectProjectById, useDashboardStore } from "@/lib/state/dashboard-store";
import { isLiveLike } from "@/lib/mode";

export default function ImpactPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const projectSelector = useMemo(() => selectProjectById(projectId), [projectId]);
  const project = useDashboardStore(projectSelector);
  const liveStatus = useDashboardStore((state) => state.liveStatus);
  const resolvedMode = project?.mode ?? liveStatus.mode;

  const crossRepoRows = useMemo(() => {
    if (!project) return [];
    return project.dependencies.map((dependency) => {
      const source = project.components.find((component) => component.id === dependency.sourceComponentId);
      const target = project.components.find((component) => component.id === dependency.targetComponentId);
      const driftCount = project.docIssues.filter((issue) => issue.componentId === dependency.targetComponentId).length;
      return {
        id: dependency.id,
        source: source?.name ?? dependency.sourceComponentId,
        target: target?.name ?? dependency.targetComponentId,
        surface: dependency.surface,
        contracts: dependency.contracts,
        driftCount,
      };
    });
  }, [project]);

  if (!project) {
    return <div className="text-sm text-destructive">Project not found.</div>;
  }

  const syntheticData = !isLiveLike(resolvedMode);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.5em] text-muted-foreground">Cross-system impact</p>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold text-foreground">Dependency awareness</h1>
          <ModeBadge mode={resolvedMode} />
        </div>
        <p className="text-sm text-muted-foreground">
          Option 2 lens: track upstream API changes and the downstream docs/services they impact before Cerebros automation kicks in.
        </p>
        <LiveRecency prefix="Live snapshot" />
      </div>

      <Card className="border-border/60">
        <CardHeader>
          <CardTitle>Dependency graph overview</CardTitle>
          <CardDescription>Edges are captured from repo metadata + toy scenario seeds.</CardDescription>
          {syntheticData ? (
            <Badge variant="outline" className="rounded-full border-border/50 text-[10px] uppercase tracking-wide">
              Synthetic dataset
            </Badge>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-2xl border border-border/60 bg-muted/10 p-3 text-sm text-muted-foreground">
            {project.dependencies.length} edges detected •{" "}
            {new Set(project.dependencies.map((edge) => edge.sourceComponentId)).size} upstream components
          </div>
          <DependencyMap dependencies={project.dependencies} components={project.components} />
        </CardContent>
      </Card>

      <ImpactAlertsPanel projectId={project.id} />

      <Card className="border-border/60">
        <CardHeader>
          <CardTitle>Cross-repo impact table</CardTitle>
          <CardDescription>Map dependencies to docs/issues to schedule remediations.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {crossRepoRows.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Upstream</TableHead>
                  <TableHead>Downstream</TableHead>
                  <TableHead>Surface</TableHead>
                  <TableHead>Contracts</TableHead>
                  <TableHead>Open doc issues</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {crossRepoRows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="font-semibold">{row.source}</TableCell>
                    <TableCell>{row.target}</TableCell>
                    <TableCell className="uppercase text-xs text-muted-foreground">{row.surface}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{row.contracts.join(", ")}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="rounded-full border-border/40 text-[11px]">
                        {row.driftCount}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-sm text-muted-foreground">No dependencies mapped yet.</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

