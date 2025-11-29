"use client";

import { useMemo } from "react";
import { useParams } from "next/navigation";
import { Download } from "lucide-react";

import { RepoConfigTable } from "@/components/projects/repo-config-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useDashboardStore } from "@/lib/state/dashboard-store";

export default function ProjectConfigurationPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const projects = useDashboardStore((state) => state.projects);
  const exportConfig = useDashboardStore((state) => state.exportConfig);

  const project = projects.find((item) => item.id === projectId);

  const linkedSystems = useMemo(() => {
    if (!project) return [];
    return project.repos.flatMap((repo) => [
      repo.linkedSystems.linearProject && { label: "Linear", value: repo.linkedSystems.linearProject, repo: repo.name },
      repo.linkedSystems.jiraProject && { label: "Jira", value: repo.linkedSystems.jiraProject, repo: repo.name },
      repo.linkedSystems.slackChannels?.length
        ? { label: "Slack", value: repo.linkedSystems.slackChannels.join(", "), repo: repo.name }
        : null,
      repo.linkedSystems.supportTags?.length
        ? { label: "Support", value: repo.linkedSystems.supportTags.join(", "), repo: repo.name }
        : null,
    ]).filter(Boolean) as { label: string; value: string; repo: string }[];
  }, [project]);

  const handleExport = () => {
    if (!project) return;
    const config = exportConfig(project.id);
    if (!config) return;
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${project.name.replace(/\s+/g, "-").toLowerCase()}-oqoqo-config.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  if (!project) {
    return <div className="text-sm text-destructive">Project not found.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.5em] text-muted-foreground">Configuration</p>
          <h1 className="text-3xl font-semibold">{project.name}</h1>
          <p className="text-sm text-muted-foreground">Source of truth for Cerebros ingestion.</p>
        </div>
        <Button onClick={handleExport} className="rounded-full px-5">
          <Download className="mr-2 h-4 w-4" />
          Export JSON
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Project metadata</CardTitle>
          <CardDescription>How Cerebros identifies and deep-links into this workspace.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-3">
          <Metadata label="Project ID" value={project.id} />
          <Metadata label="Horizon" value={project.horizon.toUpperCase()} />
          <Metadata label="Tags" value={project.tags.join(", ")} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Repositories & branches</CardTitle>
          <CardDescription>Repos, doc locations, and linked systems that define drift watchlists.</CardDescription>
        </CardHeader>
        <CardContent>
          <RepoConfigTable repos={project.repos} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Linked systems</CardTitle>
          <CardDescription>Ticket queues, Slack channels, and support signals tied to this configuration.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          {linkedSystems.length ? (
            linkedSystems.map((system, index) => (
              <div key={`${system.label}-${system.repo}-${index}`} className="rounded-2xl border border-border/50 p-4">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="rounded-full border-border/60 text-xs">
                    {system.label}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    via <span className="font-semibold text-foreground">{system.repo}</span>
                  </span>
                </div>
                <div className="pt-2 text-sm font-medium">{system.value}</div>
              </div>
            ))
          ) : (
            <div className="text-sm text-muted-foreground">No linked systems configured yet.</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

const Metadata = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-xl border border-border/60 p-4">
    <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
    <div className="text-lg font-semibold text-foreground break-words">{value}</div>
  </div>
);

