"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { GitBranch } from "lucide-react";

import { DependencyMap } from "@/components/impact/dependency-map";
import { ChangeImpactCards } from "@/components/impact/change-impact-cards";
import { LiveRecency } from "@/components/live/live-recency";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { selectProjectById, useDashboardStore } from "@/lib/state/dashboard-store";
import { longDateTime } from "@/lib/utils";

export default function ImpactPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const projectSelector = useMemo(() => selectProjectById(projectId), [projectId]);
  const project = useDashboardStore(projectSelector);
  const [selectedImpactId, setSelectedImpactId] = useState<string | null>(null);
  const defaultImpactId = project?.changeImpacts[0]?.id ?? null;
  const resolvedImpactId = selectedImpactId ?? defaultImpactId;
  const selectedImpact = useMemo(() => {
    if (!project || !project.changeImpacts.length || !resolvedImpactId) return null;
    return project.changeImpacts.find((impact) => impact.id === resolvedImpactId) ?? null;
  }, [project, resolvedImpactId]);

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

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.5em] text-muted-foreground">Cross-system impact</p>
        <h1 className="text-3xl font-semibold text-foreground">Dependency awareness</h1>
        <p className="text-sm text-muted-foreground">
          Track upstream API changes and downstream docs that must update across repos before Cerebros automation arrives.
        </p>
        <LiveRecency prefix="Live snapshot" />
      </div>

      <Card className="border-border/60">
        <CardHeader>
          <CardTitle>Dependency graph overview</CardTitle>
          <CardDescription>Edges are captured from repo metadata + toy scenario seeds.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-2xl border border-border/60 bg-muted/10 p-3 text-sm text-muted-foreground">
            {project.dependencies.length} edges detected •{" "}
            {new Set(project.dependencies.map((edge) => edge.sourceComponentId)).size} upstream components
          </div>
          <DependencyMap dependencies={project.dependencies} components={project.components} />
        </CardContent>
      </Card>

      <Card className="border-border/60">
        <CardHeader>
          <CardTitle>Change propagation</CardTitle>
          <CardDescription>Toy scenarios for how Service A API changes trigger documentation drift in Services B/C.</CardDescription>
        </CardHeader>
        <CardContent>
          <ChangeImpactCards projectId={project.id} impacts={project.changeImpacts} components={project.components} />
        </CardContent>
      </Card>

      <Card className="border-border/60">
        <CardHeader>
          <CardTitle>Scenario explorer</CardTitle>
          <CardDescription>Select a change to inspect downstream blast radius.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {project.changeImpacts.length ? (
            <>
              <Select value={resolvedImpactId ?? undefined} onValueChange={(value) => setSelectedImpactId(value)}>
                <SelectTrigger className="rounded-2xl border-border/60">
                  <SelectValue placeholder="Pick a change event" />
                </SelectTrigger>
                <SelectContent>
                  {project.changeImpacts.map((impact) => (
                    <SelectItem key={impact.id} value={impact.id}>
                      {impact.summary}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedImpact ? (
                <div className="space-y-3 rounded-2xl border border-border/60 p-4">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <Badge variant="outline" className="rounded-full border-border/40 text-[10px] uppercase">
                      {selectedImpact.changeType}
                    </Badge>
                    <span>{longDateTime(selectedImpact.changedAt)}</span>
                  </div>
                  <div className="text-sm font-semibold text-foreground">{selectedImpact.summary}</div>
                  <p className="text-xs text-muted-foreground">{selectedImpact.description}</p>
                  <div className="space-y-2">
                    {selectedImpact.downstream.map((node) => (
                      <div key={`${selectedImpact.id}-${node.componentId}`} className="rounded-2xl border border-border/40 p-3 text-sm">
                        <div className="flex items-center justify-between">
                          <span>{project.components.find((component) => component.id === node.componentId)?.name ?? node.componentId}</span>
                          <Badge variant="outline" className="rounded-full border-border/40 text-[10px] uppercase">
                            {node.risk} risk
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">{node.reason}</p>
                        <div className="flex flex-wrap gap-1 pt-1 text-[11px] text-muted-foreground">
                          {node.docPaths.map((doc) => (
                            <Badge key={doc} variant="outline" className="rounded-full border-border/30">
                              {doc}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </>
          ) : (
            <div className="text-sm text-muted-foreground">No change scenarios captured yet.</div>
          )}
        </CardContent>
      </Card>

      <Card className="border-border/60">
        <CardHeader>
          <CardTitle>Monitoring readiness</CardTitle>
          <CardDescription>Signals Cerebros will ingest for cross-system reasoning.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <ReadinessPill label="Repos with dependency metadata" value={`${project.repos.length}`} />
          <ReadinessPill label="Components with drift edges" value={`${project.dependencies.length}`} />
          <ReadinessPill label="Open cross-service drift issues" value={`${project.changeImpacts.length}`} />
        </CardContent>
      </Card>

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

const ReadinessPill = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-3xl border border-border/60 bg-card/70 p-4">
    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
      <GitBranch className="h-4 w-4 text-primary" />
      {label}
    </div>
    <div className="text-3xl font-bold text-foreground">{value}</div>
  </div>
);

