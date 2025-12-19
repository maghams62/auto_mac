"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { IssueDetailSheet } from "@/components/issues/issue-detail";
import { IssueFilters } from "@/components/issues/issue-filters";
import { IssueList } from "@/components/issues/issue-list";
import { LiveRecency } from "@/components/live/live-recency";
import { ModeBadge } from "@/components/common/mode-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { filterIssuesWithContext } from "@/lib/issues/utils";
import { isLiveLike } from "@/lib/mode";
import { selectProjectById, useDashboardStore } from "@/lib/state/dashboard-store";
import { shortDate } from "@/lib/utils";
import type { DocIssue } from "@/lib/types";

export default function ProjectIssuesPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const filters = useDashboardStore((state) => state.issueFilters);
  const setFilters = useDashboardStore((state) => state.setIssueFilters);
  const resetFilters = useDashboardStore((state) => state.resetIssueFilters);
  const projectSelector = useMemo(() => selectProjectById(projectId), [projectId]);
  const project = useDashboardStore(projectSelector);
  const liveStatus = useDashboardStore((state) => state.liveStatus);
  const referenceTime = liveStatus.lastUpdated ? new Date(liveStatus.lastUpdated).getTime() : null;
  const [selectedIssue, setSelectedIssue] = useState<DocIssue | null>(null);
  const issueMode = project?.mode ?? liveStatus.mode;
  const issueError = liveStatus.mode === "error" ? liveStatus.message : undefined;

  const componentLookup = useMemo(() => {
    if (!project) return {};
    return project.components.reduce<Record<string, { name: string; ownerTeam?: string }>>((acc, component) => {
      acc[component.id] = { name: component.name, ownerTeam: component.ownerTeam };
      return acc;
    }, {});
  }, [project]);
  const componentOptions = useMemo(
    () => project?.components.map((component) => ({ id: component.id, name: component.name })) ?? [],
    [project]
  );
  const filteredIssues = useMemo(() => {
    if (!project) return [];
    return filterIssuesWithContext(project, filters, referenceTime);
  }, [project, filters, referenceTime]);

  if (!project) {
    return <div className="text-sm text-destructive">Project not found.</div>;
  }

  const liveIssues = project.docIssues.filter((issue) => issue.id.startsWith("live_issue"));

  return (
    <div className="space-y-6">
      <LiveRecency prefix="Issues refreshed" />

      <Card className="border-border/60 bg-card/70">
        <CardHeader>
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle>Live drift inbox</CardTitle>
            <ModeBadge mode={project.mode ?? liveStatus.mode} />
          </div>
          <CardDescription>
            {isLiveLike(liveStatus.mode)
              ? "Active DocIssues across Git, Slack, Tickets, and Support."
              : liveStatus.mode === "error"
              ? "Live ingest unavailable — showing last known data."
              : "Running in synthetic mode until live ingest succeeds."}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-4 text-sm">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Total issues</p>
            <div className="text-2xl font-semibold text-foreground">{filteredIssues.length}</div>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Live drift</p>
            <div className="text-2xl font-semibold text-foreground">{liveIssues.length}</div>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Last update</p>
            <div className="text-base text-foreground">
              {liveStatus.lastUpdated ? shortDate(liveStatus.lastUpdated) : "Waiting for live data"}
            </div>
          </div>
          {filters.onlyLive ? (
            <Badge variant="outline" className="rounded-full border-emerald-400/60 text-xs text-emerald-100">
              Showing live issues
            </Badge>
          ) : null}
        </CardContent>
      </Card>

      <IssueFilters
        filters={filters}
        onChange={setFilters}
        onReset={resetFilters}
        components={componentOptions}
      />

      <Card className="border-border/60">
        <CardHeader>
          <CardTitle>Docs + activity issues</CardTitle>
          <CardDescription>Sort by severity or freshness, then drill into the live story.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <IssueList
            issues={filteredIssues}
            onSelect={setSelectedIssue}
            componentLookup={componentLookup}
            errorMessage={issueError}
            mode={issueMode}
          />
        </CardContent>
      </Card>

      {selectedIssue ? (
        <IssueDetailSheet
          issue={selectedIssue}
          project={project}
          open={Boolean(selectedIssue)}
          onOpenChange={(open) => !open && setSelectedIssue(null)}
        />
      ) : null}
    </div>
  );
}

