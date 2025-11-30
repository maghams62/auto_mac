"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Download } from "lucide-react";

import { RepoConfigTable } from "@/components/projects/repo-config-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { describeMode } from "@/lib/mode";
import { selectProjectById, useDashboardStore } from "@/lib/state/dashboard-store";

export default function ProjectConfigurationPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const exportConfig = useDashboardStore((state) => state.exportConfig);
  const exportSnapshot = useDashboardStore((state) => state.exportSnapshot);
  const liveStatus = useDashboardStore((state) => state.liveStatus);
  const projectSelector = useMemo(() => selectProjectById(projectId), [projectId]);
  const project = useDashboardStore(projectSelector);

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
  const datasetRefs = useMemo(() => {
    if (!project?.datasetRefs) return [];
    return Object.entries(project.datasetRefs)
      .filter(([, value]) => Boolean(value))
      .map(([key, value]) => ({
        key,
        value: value as string,
      }));
  }, [project]);
  const snapshot = project ? exportSnapshot(project.id) : undefined;
  const sourceCounts = useMemo(() => {
    if (!project) return null;
    const counts = {
      git: 0,
      docs: 0,
      slack: 0,
      tickets: 0,
      support: 0,
    };
    project.components.forEach((component) => {
      component.sourceEvents.forEach((event) => {
        counts[event.source] += 1;
      });
    });
    return counts;
  }, [project]);
  const liveIssueCount = project ? project.docIssues.filter((issue) => issue.id.startsWith("live_issue")).length : 0;
  const highDriftComponents = project
    ? project.components.filter((component) => component.graphSignals.drift.score >= 60).length
    : 0;
  const [datasetStatus, setDatasetStatus] = useState<Record<string, string>>({});
  const datasetActivity = useMemo(() => {
    const classify = (key: keyof typeof sourceCounts): { state: "active" | "quiet" | "error"; label: string } => {
      const count = sourceCounts?.[key] ?? 0;
      const status = datasetStatus[key];
      if (status && status !== "ok") {
        return { state: "error", label: status };
      }
      if (count > 0) {
        return { state: "active", label: `active (${count})` };
      }
      return { state: "quiet", label: "quiet (0)" };
    };
    return {
      git: classify("git"),
      slack: classify("slack"),
      tickets: classify("tickets"),
      support: classify("support"),
    };
  }, [datasetStatus, sourceCounts]);

  useEffect(() => {
    let cancelled = false;

    const updateStatus = async () => {
      await Promise.resolve();
      if (!datasetRefs.length) {
        if (!cancelled) {
          setDatasetStatus({});
        }
        return;
      }

      const entries = await Promise.all(
        datasetRefs.map(async (entry) => {
          try {
            const response = await fetch(entry.value, { method: "HEAD" });
            return [entry.key, response.ok ? "ok" : `HTTP ${response.status}`] as const;
          } catch (error) {
            console.warn("Failed to probe dataset", entry.value, error);
            return [entry.key, "error"] as const;
          }
        })
      );
      if (!cancelled) {
        setDatasetStatus(Object.fromEntries(entries));
      }
    };

    updateStatus();

    return () => {
      cancelled = true;
    };
  }, [datasetRefs]);

  const handleCopySnapshot = () => {
    if (!snapshot) return;
    navigator.clipboard.writeText(JSON.stringify(snapshot, null, 2)).catch(() => {
      console.warn("Failed to copy snapshot to clipboard");
    });
  };

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
            <Metadata label="Mode" value={describeMode(project.mode ?? liveStatus.mode)} />
        </CardContent>
      </Card>

      {project ? (
        <Card id="live-ingest-inspector">
          <CardHeader>
            <CardTitle>Live ingest inspector</CardTitle>
            <CardDescription>Quick health indicators for the latest snapshot.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
            <Metadata label="Live drift issues" value={`${liveIssueCount}`} />
            <Metadata label="High-drift components" value={`${highDriftComponents}`} />
            <Metadata label="Git signals" value={`${sourceCounts?.git ?? 0}`} />
            <Metadata label="Slack signals" value={`${sourceCounts?.slack ?? 0}`} />
            <Metadata label="Ticket signals" value={`${sourceCounts?.tickets ?? 0}`} />
            <Metadata label="Support signals" value={`${sourceCounts?.support ?? 0}`} />
          </CardContent>
          <CardContent className="pt-0">
            <p className="text-xs text-muted-foreground">
              Last snapshot {liveStatus.lastUpdated ? `captured ${liveStatus.lastUpdated}` : "pending"}.
            </p>
          </CardContent>
        </Card>
      ) : null}

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

      <Card>
        <CardHeader>
          <CardTitle>Dataset references & snapshot</CardTitle>
          <CardDescription>Where the synthetic signals live plus an inline JSON snapshot for Cerebros.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {datasetRefs.length ? (
            <div className="grid gap-3 md:grid-cols-2">
              {datasetRefs.map((entry) => (
                <div key={entry.key} className="rounded-2xl border border-border/50 p-4 text-sm">
                  <div className="flex items-center justify-between text-xs uppercase tracking-wide text-muted-foreground">
                    <span>{entry.key}</span>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className={`rounded-full border-border/40 ${
                          datasetStatus[entry.key] === "ok" ? "text-emerald-300" : "text-amber-200"
                        }`}
                      >
                        {datasetStatus[entry.key] ?? "checking..."}
                      </Badge>
                      {datasetActivity[entry.key as keyof typeof datasetActivity] ? (
                        <Badge
                          variant="outline"
                          className={`rounded-full border-border/40 text-[10px] ${
                            datasetActivity[entry.key as keyof typeof datasetActivity].state === "active"
                              ? "text-emerald-200"
                              : datasetActivity[entry.key as keyof typeof datasetActivity].state === "quiet"
                              ? "text-muted-foreground"
                              : "text-amber-200"
                          }`}
                        >
                          {datasetActivity[entry.key as keyof typeof datasetActivity].label}
                        </Badge>
                      ) : null}
                    </div>
                  </div>
                  <a href={entry.value} className="text-primary underline-offset-2 hover:underline" target="_blank" rel="noreferrer">
                    {entry.value}
                  </a>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">No external dataset references provided.</div>
          )}

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-foreground">Project snapshot preview</p>
              <Button variant="outline" className="rounded-full text-xs" onClick={handleCopySnapshot} disabled={!snapshot}>
                Copy JSON
              </Button>
            </div>
            <ScrollArea className="max-h-64 rounded-2xl border border-border/60 bg-muted/10 p-3 text-xs text-muted-foreground">
              {snapshot ? <pre className="whitespace-pre-wrap">{JSON.stringify(snapshot, null, 2)}</pre> : "Snapshot unavailable."}
            </ScrollArea>
          </div>
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

