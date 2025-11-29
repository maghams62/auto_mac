"use client";

import { useState } from "react";
import { Plus } from "lucide-react";

import { ProjectCard } from "@/components/projects/project-card";
import { ProjectForm } from "@/components/projects/project-form";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useDashboardStore } from "@/lib/state/dashboard-store";
import type { Project, ProjectDraft } from "@/lib/types";

export default function ProjectsPage() {
  const projects = useDashboardStore((state) => state.projects);
  const addProject = useDashboardStore((state) => state.addProject);
  const updateProject = useDashboardStore((state) => state.updateProject);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const handleCreate = async (draft: ProjectDraft) => {
    await addProject(draft);
    setCreateOpen(false);
  };

  const handleEdit = async (draft: ProjectDraft) => {
    if (!draft.id) return;
    updateProject(draft.id, (project) => ({
      ...project,
      name: draft.name,
      description: draft.description,
      horizon: draft.horizon,
      tags: draft.tags,
      repos: draft.repos,
      pulse: {
        ...project.pulse,
        lastRefreshed: new Date().toISOString(),
      },
    }));
    setEditingProject(null);
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.4em] text-muted-foreground">Projects</p>
          <h1 className="text-3xl font-semibold text-foreground">Monitored doc drift workspaces</h1>
          <p className="text-sm text-muted-foreground">
            Configure repos, branches, and linked signals that Cerebros will ingest later.
          </p>
        </div>
        <div className="flex gap-3">
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button className="rounded-full px-5">
                <Plus className="mr-2 h-4 w-4" />
                Add project
              </Button>
            </DialogTrigger>
            <DialogContent className="max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Add project</DialogTitle>
                <DialogDescription>Tell Oqoqo which repos, doc paths, and linked systems to monitor.</DialogDescription>
              </DialogHeader>
              <ProjectForm onSubmit={handleCreate} submitLabel="Create project" />
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <div className="grid gap-6">
        {projects.map((project) => (
          <ProjectCard key={project.id} project={project} onEdit={() => setEditingProject(project)} />
        ))}
      </div>

      <Dialog open={Boolean(editingProject)} onOpenChange={(open) => !open && setEditingProject(null)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit {editingProject?.name}</DialogTitle>
            <DialogDescription>Adjust metadata or monitored sources any time.</DialogDescription>
          </DialogHeader>
          {editingProject ? (
            <ProjectForm project={editingProject} onSubmit={handleEdit} submitLabel="Save changes" />
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}

