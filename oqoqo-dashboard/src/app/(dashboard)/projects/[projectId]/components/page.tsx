"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Activity, Filter } from "lucide-react";

import { ComponentGrid } from "@/components/activity/component-grid";
import { Input } from "@/components/ui/input";
import { useDashboardStore } from "@/lib/state/dashboard-store";

export default function ComponentsPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const projects = useDashboardStore((state) => state.projects);
  const project = projects.find((item) => item.id === projectId);
  const [query, setQuery] = useState("");

  const filteredComponents = useMemo(() => {
    if (!project) return [];
    if (!query.trim()) return project.components;
    const text = query.toLowerCase();
    return project.components.filter(
      (component) =>
        component.name.toLowerCase().includes(text) ||
        component.serviceType.toLowerCase().includes(text) ||
        component.tags.some((tag) => tag.toLowerCase().includes(text))
    );
  }, [project, query]);

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
      </div>

      <div className="flex flex-col gap-3 rounded-3xl border border-border/60 bg-card/60 p-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Activity className="h-4 w-4 text-primary" />
          {project.components.length} components wired into the activity graph.
        </div>
        <div className="flex w-full gap-2 md:w-auto">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter components..."
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

