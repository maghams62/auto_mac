"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Activity, Filter } from "lucide-react";

import { ComponentGrid } from "@/components/activity/component-grid";
import { LiveRecency } from "@/components/live/live-recency";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { selectProjectById, useDashboardStore } from "@/lib/state/dashboard-store";

export default function ComponentsPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const projectSelector = useMemo(() => selectProjectById(projectId), [projectId]);
  const project = useDashboardStore(projectSelector);
  const [query, setQuery] = useState("");
  const [showAtRisk, setShowAtRisk] = useState(false);
  const [sortKey, setSortKey] = useState<"drift" | "activity" | "dissatisfaction">("drift");

  const filteredComponents = useMemo(() => {
    if (!project) return [];
    const text = query.toLowerCase();
    let components = [...project.components].filter((component) => {
      if (!text) return true;
      return (
        component.name.toLowerCase().includes(text) ||
        component.serviceType.toLowerCase().includes(text) ||
        component.tags.some((tag) => tag.toLowerCase().includes(text))
      );
    });

    if (showAtRisk) {
      components = components.filter(
        (component) => component.divergenceInsights.length > 0 || component.graphSignals.drift.score >= 60
      );
    }

    components.sort(
      (a, b) => b.graphSignals[sortKey].score - a.graphSignals[sortKey].score
    );

    return components;
  }, [project, query, showAtRisk, sortKey]);

  if (!project) {
    return <div className="text-sm text-destructive">Project not found.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.5em] text-muted-foreground">Activity graph</p>
        <h1 className="text-3xl font-semibold text-foreground">Component signals</h1>
        <p className="text-sm text-muted-foreground">
          Search components to compare activity, drift, and dissatisfaction signals before handing work to Cerebros.
        </p>
        <LiveRecency prefix="Live data" />
      </div>

      <div className="flex flex-col gap-3 rounded-3xl border border-border/60 bg-card/60 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-primary" />
            {filteredComponents.length} of {project.components.length} components
          </div>
          <div className="flex items-center gap-2 text-xs">
            Sort by
            <Select value={sortKey} onValueChange={(value: "drift" | "activity" | "dissatisfaction") => setSortKey(value)}>
              <SelectTrigger className="h-8 w-[140px] rounded-full border-border/60 text-xs">
                <SelectValue placeholder="Select metric" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="drift">Drift</SelectItem>
                <SelectItem value="activity">Activity</SelectItem>
                <SelectItem value="dissatisfaction">Dissatisfaction</SelectItem>
              </SelectContent>
            </Select>
            <Button
              variant={showAtRisk ? "default" : "outline"}
              size="sm"
              className="rounded-full text-xs"
              onClick={() => setShowAtRisk((prev) => !prev)}
            >
              {showAtRisk ? "Showing at-risk" : "At risk only"}
            </Button>
          </div>
        </div>
        <div className="flex w-full flex-col gap-2 md:flex-row md:items-center">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search components, APIs, tags..."
            className="rounded-2xl border-border/60"
          />
          <div className="hidden items-center gap-1 rounded-2xl border border-border/60 px-4 text-xs text-muted-foreground md:flex">
            <Filter className="h-3.5 w-3.5" />
            search tags, service types
          </div>
        </div>
      </div>

      <ComponentGrid projectId={project.id} components={filteredComponents} />
    </div>
  );
}

