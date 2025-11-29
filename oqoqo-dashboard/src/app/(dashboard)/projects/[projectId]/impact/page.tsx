"use client";

import { useParams } from "next/navigation";
import { GitBranch } from "lucide-react";

import { DependencyMap } from "@/components/impact/dependency-map";
import { ChangeImpactCards } from "@/components/impact/change-impact-cards";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useDashboardStore } from "@/lib/state/dashboard-store";

export default function ImpactPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const projects = useDashboardStore((state) => state.projects);
  const project = projects.find((item) => item.id === projectId);

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
          <CardTitle>Monitoring readiness</CardTitle>
          <CardDescription>Signals Cerebros will ingest for cross-system reasoning.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <ReadinessPill label="Repos with dependency metadata" value={`${project.repos.length}`} />
          <ReadinessPill label="Components with drift edges" value={`${project.dependencies.length}`} />
          <ReadinessPill label="Open cross-service drift issues" value={`${project.changeImpacts.length}`} />
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

