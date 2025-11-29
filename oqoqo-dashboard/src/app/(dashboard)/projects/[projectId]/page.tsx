"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { AlertTriangle, Component, Shield } from "lucide-react";

import { IssueDetailSheet } from "@/components/issues/issue-detail";
import { IssueFilters } from "@/components/issues/issue-filters";
import { IssueList } from "@/components/issues/issue-list";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useDashboardStore } from "@/lib/state/dashboard-store";
import type { DocIssue } from "@/lib/types";

export default function ProjectOverviewPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const projects = useDashboardStore((state) => state.projects);
  const filters = useDashboardStore((state) => state.issueFilters);
  const setFilters = useDashboardStore((state) => state.setIssueFilters);
  const resetFilters = useDashboardStore((state) => state.resetIssueFilters);
  const project = projects.find((item) => item.id === projectId);

  const [selectedIssue, setSelectedIssue] = useState<DocIssue | null>(null);

  const filteredIssues = useMemo(() => {
    if (!project) return [];
    return project.docIssues.filter((issue) => {
      if (filters.severities.length && !filters.severities.includes(issue.severity)) {
        return false;
      }
      if (filters.statuses.length && !filters.statuses.includes(issue.status)) {
        return false;
      }
      if (filters.search.trim().length) {
        const text = filters.search.toLowerCase();
        const component = project.components.find((comp) => comp.id === issue.componentId)?.name ?? "";
        const haystack = `${issue.title} ${issue.summary} ${issue.docPath} ${component}`.toLowerCase();
        return haystack.includes(text);
      }
      return true;
    });
  }, [project, filters]);

  const topComponents = useMemo(() => {
    if (!project) return [];
    return [...project.components]
      .sort((a, b) => b.graphSignals.drift.score - a.graphSignals.drift.score)
      .slice(0, 3);
  }, [project]);

  if (!project) {
    return <div className="text-sm text-destructive">Project not found.</div>;
  }

  const openIssues = project.docIssues.filter((issue) => issue.status !== "resolved");
  const criticalIssues = project.docIssues.filter((issue) => issue.severity === "critical");

  return (
    <div className="space-y-6">
      <section className="grid gap-4 lg:grid-cols-3">
        <MetricCard
          icon={Shield}
          label="Doc health score"
          value={`${project.docHealthScore}/100`}
          description="Based on drift + dissatisfaction signals."
        />
        <MetricCard
          icon={AlertTriangle}
          label="Open drift issues"
          value={`${openIssues.length}`}
          description={`${criticalIssues.length} critical, ${openIssues.length - criticalIssues.length} other`}
        />
        <MetricCard
          icon={Component}
          label="Impacted components"
          value={`${project.pulse.impactedComponents}`}
          description="Components with unresolved drift."
        />
      </section>

      <Card>
        <CardHeader>
          <CardTitle>At-risk components</CardTitle>
          <CardDescription>Activity graph nodes with highest drift scores.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          {topComponents.map((component) => (
            <div key={component.id} className="rounded-2xl border border-border/60 p-4">
              <div className="text-sm font-semibold text-foreground">{component.name}</div>
              <p className="text-xs text-muted-foreground">{component.serviceType}</p>
              <div className="flex items-baseline gap-2 pt-3">
                <span className="text-2xl font-bold text-primary">{component.graphSignals.drift.score}</span>
                <span className="text-xs text-muted-foreground">drift</span>
              </div>
              <p className="text-xs text-muted-foreground">{component.graphSignals.drift.summary}</p>
              <Badge variant="outline" className="mt-2 rounded-full border-border/60 text-xs">
                Activity {component.graphSignals.activity.score}
              </Badge>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Documentation drift issues</CardTitle>
          <CardDescription>Pivot across severity, status, and search to prioritize fixes.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <IssueFilters
            filters={filters}
            onChange={setFilters}
            onReset={() => {
              resetFilters();
            }}
          />
          <IssueList issues={filteredIssues} onSelect={(issue) => setSelectedIssue(issue)} />
        </CardContent>
      </Card>

      {selectedIssue ? (
        <IssueDetailSheet issue={selectedIssue} project={project} open={Boolean(selectedIssue)} onOpenChange={(open) => !open && setSelectedIssue(null)} />
      ) : null}
    </div>
  );
}

const MetricCard = ({
  icon: Icon,
  label,
  value,
  description,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  description: string;
}) => (
  <div className="rounded-3xl border border-border/60 bg-card/60 p-5 shadow-inner">
    <div className="flex items-center gap-3">
      <div className="rounded-2xl bg-primary/15 p-2 text-primary">
        <Icon className="h-4 w-4" />
      </div>
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</div>
    </div>
    <div className="text-3xl font-bold text-foreground">{value}</div>
    <p className="text-xs text-muted-foreground">{description}</p>
  </div>
);

