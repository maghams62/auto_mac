import Link from "next/link";
import { PenSquare } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Project, Severity } from "@/lib/types";
import { resolveProjectCerebrosUrl } from "@/lib/cerebros";
import { cn, shortTime } from "@/lib/utils";

interface ProjectCardProps {
  project: Project;
  onEdit: () => void;
  showEditAction?: boolean;
}

const severityRank: Record<Severity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

export function ProjectCard({ project, onEdit, showEditAction = true }: ProjectCardProps) {
  const severityCounts = project.docIssues.reduce<Record<Severity, number>>(
    (acc, issue) => {
      acc[issue.severity] += 1;
      return acc;
    },
    { critical: 0, high: 0, medium: 0, low: 0 }
  );

  const openIssuesTotal = project.pulse?.totalIssues ?? project.docIssues.length;
  const lastUpdatedLabel = project.pulse?.lastRefreshed ? shortTime(project.pulse.lastRefreshed) : null;

  const hottestIssue = project.docIssues
    .slice()
    .sort((a, b) => {
      const rankDiff = severityRank[a.severity] - severityRank[b.severity];
      if (rankDiff !== 0) return rankDiff;
      return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
    })[0];

  const hotComponent = hottestIssue
    ? project.components.find((component) => component.id === hottestIssue.componentId)
    : undefined;

  const hotComponentSummary = hotComponent
    ? `${hotComponent.name} · ${formatSeverity(hottestIssue?.severity)} drift`
    : null;

  const cerebrosProjectUrl = resolveProjectCerebrosUrl(project) ?? null;

  return (
    <Card className="border border-border/60 bg-card/80">
      <CardHeader className="flex flex-col gap-3">
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="text-2xl text-foreground">{project.name}</CardTitle>
            <CardDescription>{project.description}</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="rounded-full border-primary/40 text-primary">
              {project.horizon.toUpperCase()}
            </Badge>
            {showEditAction ? (
              <Button variant="ghost" size="icon" className="rounded-full" onClick={onEdit} aria-label="Edit project">
                <PenSquare className="h-4 w-4" />
              </Button>
            ) : null}
          </div>
        </div>
        <div className="flex flex-wrap items-end gap-6">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Doc health</p>
            <p className="text-4xl font-bold text-foreground">{project.docHealthScore}</p>
          </div>
          <div className="flex gap-3">
            <SummaryStat label="Critical" value={severityCounts.critical} emphasis="critical" />
            <SummaryStat label="Open issues" value={openIssuesTotal} />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-col gap-1 text-sm text-muted-foreground">
          {lastUpdatedLabel ? <span>Last updated {lastUpdatedLabel}</span> : null}
          <span>{project.repos.length} monitored sources</span>
        </div>

        {hotComponentSummary ? (
          <div className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-3">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Hot component</p>
            <p className="text-sm font-semibold text-foreground">{hotComponentSummary}</p>
            {hottestIssue?.updatedAt ? (
              <p className="text-xs text-muted-foreground">Last activity {shortTime(hottestIssue.updatedAt)}</p>
            ) : null}
          </div>
        ) : null}

        <div className="flex flex-wrap gap-3">
          <Button asChild className="rounded-full px-5 font-semibold">
            <Link href={`/projects/${project.id}`}>Open project</Link>
          </Button>
          {cerebrosProjectUrl ? (
            <Button asChild variant="outline" className="rounded-full px-5 font-semibold">
              <Link href={cerebrosProjectUrl} target="_blank" rel="noreferrer">
                Ask OQOQO / Cerebros
              </Link>
            </Button>
          ) : (
            <Button variant="outline" className="rounded-full px-5 font-semibold" disabled>
              Ask OQOQO / Cerebros
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

const SummaryStat = ({
  label,
  value,
  emphasis,
}: {
  label: string;
  value: number;
  emphasis?: "critical";
}) => (
  <div
    className={cn(
      "rounded-full border px-4 py-2 text-sm font-semibold",
      emphasis === "critical"
        ? "border-red-400/60 text-red-200"
        : "border-border/60 text-foreground"
    )}
  >
    {label}: {value}
  </div>
);

function formatSeverity(severity?: Severity) {
  if (!severity) return "";
  return severity.charAt(0).toUpperCase() + severity.slice(1);
}

