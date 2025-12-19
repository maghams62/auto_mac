"use client";

import { useMemo } from "react";
import { useParams } from "next/navigation";

import { ComponentDocIssuesList } from "@/components/activity/component-doc-issues-list";
import { ComponentSummaryCard } from "@/components/activity/component-summary-card";
import { ComponentTimeline } from "@/components/activity/component-timeline";
import { SystemMapGraph } from "@/components/activity/system-map-graph";
import { Badge } from "@/components/ui/badge";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useActivityDriftView } from "@/lib/hooks/use-activity-drift-view";
import { selectProjectById, useDashboardStore } from "@/lib/state/dashboard-store";

export default function ProjectActivityPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const projectSelector = useMemo(() => selectProjectById(projectId), [projectId]);
  const project = useDashboardStore(projectSelector);
  const modePreference = useDashboardStore((state) => state.modePreference);
  const setModePreference = useDashboardStore((state) => state.setModePreference);
  const {
    components,
    graphNodes,
    graphLinks,
    timelineBuckets,
    timeCursorIndex,
    setTimeCursorIndex,
    loading,
    error,
    providerMeta,
    selectedComponent,
    selectedComponentId,
    setSelectedComponentId,
  } = useActivityDriftView(projectId);
  const selectedIssues = selectedComponent?.docIssues ?? [];

  if (!project) {
    return <div className="text-sm text-destructive">Project not found.</div>;
  }

  return (
    <div className="space-y-6">
      <header className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.5em] text-muted-foreground">Activity</p>
        <div className="flex w-full flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold text-foreground">{project.name} documentation drift</h1>
          <Badge variant="outline" className="rounded-full border-border/60 text-xs uppercase tracking-wide">
            {project.mode === "atlas" ? "Live" : "Synthetic"} mode
          </Badge>
          <div className="flex-1" />
          <Tabs
            value={modePreference === "synthetic" ? "synthetic" : "atlas"}
            onValueChange={(next) => setModePreference(next === "synthetic" ? "synthetic" : "atlas")}
            className="min-w-[260px]"
          >
            <TabsList>
              <TabsTrigger value="atlas">Live data</TabsTrigger>
              <TabsTrigger value="synthetic">Synthetic dataset</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
        <p className="text-sm text-muted-foreground">
          Follow the story from hot components to the precise doc issues they surfaced. Start with the system map, then drill down
          into the focused component and replay how signals built up.
        </p>
      </header>

      <SystemMapGraph
        nodes={graphNodes}
        links={graphLinks}
        loading={loading && !components.length}
        error={error}
        providerMeta={providerMeta}
        selectedId={selectedComponentId}
        onSelect={setSelectedComponentId}
      />

      <div className="grid gap-6 lg:grid-cols-[2fr,1fr]">
        <ComponentSummaryCard component={selectedComponent} />
        <ComponentDocIssuesList issues={selectedIssues} projectId={projectId} componentId={selectedComponent?.id} />
      </div>

      <ComponentTimeline timeline={timelineBuckets} cursor={timeCursorIndex} onCursorChange={setTimeCursorIndex} />

      <Card className="border-dashed border-border/60">
        <CardHeader>
          <CardTitle>Need a deeper dive?</CardTitle>
          <CardDescription>
            Use the system map to focus a component, then open Graph Explorer or the Issues view for a full investigation.
          </CardDescription>
        </CardHeader>
      </Card>
    </div>
  );
}


