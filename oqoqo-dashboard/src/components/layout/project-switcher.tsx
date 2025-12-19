"use client";

import { useRouter } from "next/navigation";
import { Layers, Sparkles } from "lucide-react";
import { useDashboardStore } from "@/lib/state/dashboard-store";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

export function ProjectSwitcher({ compact = false }: { compact?: boolean }) {
  const router = useRouter();
  const projects = useDashboardStore((state) => state.projects);
  const selectedProjectId = useDashboardStore((state) => state.selectedProjectId);
  const selectProject = useDashboardStore((state) => state.selectProject);

  const handleChange = (projectId: string) => {
    selectProject(projectId);
    router.push(`/projects/${projectId}`);
  };

  const selectedProject = projects.find((project) => project.id === selectedProjectId);

  return (
    <div className={cn("flex flex-col gap-2", compact && "gap-1")}>
      {!compact && (
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Current project</div>
      )}
      <Select value={selectedProjectId} onValueChange={handleChange}>
        <SelectTrigger className="h-11 rounded-2xl border-border/60 bg-muted/20 text-left text-sm font-semibold">
          <SelectValue
            placeholder={
              <span className="flex items-center gap-2 text-muted-foreground">
                <Layers className="h-4 w-4" />
                Select project
              </span>
            }
          >
            {selectedProject ? (
              <span className="flex flex-1 items-center justify-between gap-2">
                <span className="flex items-center gap-2 truncate">
                  <Sparkles className="h-4 w-4 text-primary" />
                  <span className="truncate">{selectedProject.name}</span>
                </span>
                <span className="rounded-full bg-primary/15 px-2 text-xs font-medium text-primary">
                  {selectedProject.horizon.toUpperCase()}
                </span>
              </span>
            ) : null}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {projects.map((project) => (
            <SelectItem key={project.id} value={project.id} className="rounded-xl">
              <div className="flex flex-col">
                <span className="font-medium">{project.name}</span>
                <span className="text-xs text-muted-foreground">
                  {project.repos.length} source{project.repos.length === 1 ? "" : "s"} monitored
                </span>
              </div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

