import Link from "next/link";
import { AlertTriangle, MapPinned, NotebookPen, Settings2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Project, Severity } from "@/lib/types";

interface ProjectCardProps {
  project: Project;
  onEdit: () => void;
}

export function ProjectCard({ project, onEdit }: ProjectCardProps) {
  const severityCounts = project.docIssues.reduce<Record<Severity, number>>(
    (acc, issue) => {
      acc[issue.severity] += 1;
      return acc;
    },
    { critical: 0, high: 0, medium: 0, low: 0 }
  );

  return (
    <Card className="bg-card/80">
      <CardHeader className="flex flex-row items-start justify-between">
        <div>
          <CardTitle className="text-xl text-foreground">{project.name}</CardTitle>
          <CardDescription>{project.description}</CardDescription>
        </div>
        <Badge variant="outline" className="rounded-full border-primary/40 text-primary">
          {project.horizon.toUpperCase()}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-4">
          <Metric label="Doc health" value={`${project.docHealthScore}/100`} />
          <Metric label="Repos" value={`${project.repos.length}`} description="Monitored sources" />
          <Metric label="Components impacted" value={`${project.pulse.impactedComponents}`} description="Graph nodes" />
          <Metric label="Open drift issues" value={`${project.pulse.totalIssues}`} description="Across components" />
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs font-semibold text-muted-foreground">
          <AlertTriangle className="h-4 w-4 text-amber-400" />
          <span>
            <span className="text-red-300">{severityCounts.critical}</span> critical •{" "}
            <span className="text-orange-300">{severityCounts.high}</span> high •{" "}
            <span className="text-yellow-200">{severityCounts.medium}</span> medium
          </span>
        </div>

        <div className="flex flex-wrap gap-2">
          {project.tags.map((tag) => (
            <Badge key={tag} variant="outline" className="border-border/50 bg-muted/10">
              {tag}
            </Badge>
          ))}
        </div>

        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
          {project.repos.map((repo) => (
            <Badge key={repo.id} variant="outline" className="rounded-full border-border/40 text-[11px]">
              {repo.name}
            </Badge>
          ))}
        </div>

        <div className="flex flex-wrap gap-3">
          <Button asChild className="rounded-full px-4">
            <Link href={`/projects/${project.id}`}>
              <NotebookPen className="mr-2 h-4 w-4" />
              View overview
            </Link>
          </Button>
          <Button asChild variant="outline" className="rounded-full px-4">
            <Link href={`/projects/${project.id}/configuration`}>
              <Settings2 className="mr-2 h-4 w-4" />
              Configure sources
            </Link>
          </Button>
          <Button variant="ghost" className="rounded-full px-4" onClick={onEdit}>
            <MapPinned className="mr-2 h-4 w-4" />
            Edit project
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

const Metric = ({
  label,
  value,
  description,
}: {
  label: string;
  value: string;
  description?: string;
}) => (
  <div className="rounded-2xl border border-border/60 p-4">
    <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</div>
    <div className="text-2xl font-bold text-foreground">{value}</div>
    {description ? <p className="text-xs text-muted-foreground">{description}</p> : null}
  </div>
);

