"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowRight, Database, Plus, ShieldCheck, Slack } from "lucide-react";

import { ProjectCard } from "@/components/projects/project-card";
import { ProjectForm } from "@/components/projects/project-form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useDashboardStore } from "@/lib/state/dashboard-store";
import type { Project, ProjectDraft, Severity } from "@/lib/types";

export default function ProjectsPage() {
  const projects = useDashboardStore((state) => state.projects);
  const addProject = useDashboardStore((state) => state.addProject);
  const updateProject = useDashboardStore((state) => state.updateProject);
  const [focusedProjectId, setFocusedProjectId] = useState(projects[0]?.id ?? null);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const focusedProject = useMemo(
    () => projects.find((project) => project.id === focusedProjectId) ?? projects[0],
    [focusedProjectId, projects]
  );

  const severityCounts = useMemo(() => {
    if (!focusedProject) {
      return { critical: 0, high: 0, medium: 0, low: 0 } as Record<Severity, number>;
    }
    return focusedProject.docIssues.reduce<Record<Severity, number>>(
      (acc, issue) => {
        acc[issue.severity] += 1;
        return acc;
      },
      { critical: 0, high: 0, medium: 0, low: 0 }
    );
  }, [focusedProject]);

  const linkedSystemsCount = useMemo(() => {
    if (!focusedProject) return 0;
    return focusedProject.repos.reduce((count, repo) => count + (repo.linkedSystems.slackChannels?.length ?? 0), 0);
  }, [focusedProject]);

  const heroMetrics = useMemo(() => {
    if (!focusedProject) {
      return [];
    }
    return [
      { label: "Doc health", value: `${focusedProject.docHealthScore}/100` },
      { label: "Open drift issues", value: `${focusedProject.pulse.totalIssues}`, detail: "Across components" },
      { label: "Critical issues", value: `${severityCounts.critical}`, detail: "Immediate escalation" },
      { label: "Linked signals", value: `${linkedSystemsCount}`, detail: "Slack + tickets" },
    ];
  }, [focusedProject, severityCounts, linkedSystemsCount]);

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

      {focusedProject ? (
        <Card className="border border-border/60 bg-card/80">
          <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-2">
              <CardTitle className="flex flex-col gap-1 text-2xl">
                <span>Projects command center</span>
                <span className="text-sm font-normal text-muted-foreground">
                  Drift + activity overview for {focusedProject.name}
                </span>
              </CardTitle>
              <CardDescription>Select a project to preview metrics and jump into drift response.</CardDescription>
            </div>
            <div className="w-full max-w-xs">
              <Select value={focusedProject.id} onValueChange={setFocusedProjectId}>
                <SelectTrigger className="rounded-2xl border-border/60">
                  <SelectValue placeholder="Choose project" />
                </SelectTrigger>
                <SelectContent>
                  {projects.map((project) => (
                    <SelectItem key={project.id} value={project.id}>
                      {project.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <HeroMetricsRow metrics={heroMetrics} />
            <ContextPills repos={focusedProject.repos} slackCount={linkedSystemsCount} />
            <PrimaryActions projectId={focusedProject.id} />
          </CardContent>
        </Card>
      ) : null}

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

const HeroMetricsRow = ({ metrics }: { metrics: Array<{ label: string; value: string; detail?: string }> }) => (
  <div className="grid gap-4 md:grid-cols-4">
    {metrics.map((metric) => (
      <div key={metric.label} className="rounded-2xl border border-border/60 p-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{metric.label}</div>
        <div className="text-3xl font-bold text-foreground">{metric.value}</div>
        {metric.detail ? <div className="text-xs text-muted-foreground">{metric.detail}</div> : null}
      </div>
    ))}
  </div>
);

const ContextPills = ({ repos, slackCount }: { repos: Project["repos"]; slackCount: number }) => (
  <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
    {repos.map((repo) => (
      <Badge key={repo.id} variant="outline" className="rounded-full border-border/40">
        {repo.name}
      </Badge>
    ))}
    <div className="flex items-center gap-2 rounded-full border border-border/60 px-4 py-2">
      <Slack className="h-4 w-4 text-primary" />
      {slackCount} monitored Slack signals
    </div>
  </div>
);

const PrimaryActions = ({ projectId }: { projectId: string }) => (
  <div className="flex flex-wrap gap-3">
    <Button asChild className="rounded-full px-5">
      <Link href={`/projects/${projectId}`}>
        Go to drift overview
        <ArrowRight className="ml-2 h-4 w-4" />
      </Link>
    </Button>
    <Button asChild variant="ghost" className="rounded-full">
      <Link href={`/projects/${projectId}/impact`}>
        View cross-system impact
        <Database className="ml-2 h-4 w-4" />
      </Link>
    </Button>
    <Button asChild variant="ghost" className="rounded-full">
      <Link href={`/projects/${projectId}/components`}>
        Inspect components
        <ShieldCheck className="ml-2 h-4 w-4" />
      </Link>
    </Button>
  </div>
);

