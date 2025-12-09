"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";

import { ProjectCard } from "@/components/projects/project-card";
import { ProjectForm } from "@/components/projects/project-form";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useDashboardStore } from "@/lib/state/dashboard-store";
import type { IncidentRecord, Project, ProjectDraft, Severity } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ENABLE_PROTOTYPE_ADMIN } from "@/lib/feature-flags";

export default function ProjectsPage() {
  const projects = useDashboardStore((state) => state.projects);
  const addProject = useDashboardStore((state) => state.addProject);
  const updateProject = useDashboardStore((state) => state.updateProject);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const prototypeAdminEnabled = ENABLE_PROTOTYPE_ADMIN;

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
          <h1 className="text-3xl font-semibold text-foreground">Doc drift operations cockpit</h1>
          <p className="text-sm text-muted-foreground">
            Scan doc health at a glance, then open a project’s Today view to decide what to fix next.
          </p>
        </div>
        <div className="flex flex-col gap-2 text-right text-xs text-muted-foreground">
          {prototypeAdminEnabled ? (
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
                  <DialogDescription>Tell OQOQO which repos, doc paths, and linked systems to monitor.</DialogDescription>
                </DialogHeader>
                <ProjectForm onSubmit={handleCreate} submitLabel="Create project" />
              </DialogContent>
            </Dialog>
          ) : (
            <p>Project creation restricted in this demo.</p>
          )}
        </div>
      </div>

      <div className="grid gap-6">
        {projects.length ? (
          projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onEdit={() => prototypeAdminEnabled && setEditingProject(project)}
              showEditAction={prototypeAdminEnabled}
            />
          ))
        ) : (
          <div className="rounded-2xl border border-dashed border-border/60 p-8 text-center text-muted-foreground">
            No projects yet — add one to start monitoring doc drift.
          </div>
        )}
      </div>

      {prototypeAdminEnabled ? (
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
      ) : null}

      <IncidentsSection />
    </div>
  );
}

function IncidentsSection() {
  const [incidents, setIncidents] = useState<IncidentRecord[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        setStatus("loading");
        const response = await fetch("/api/incidents?limit=5", { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`Request failed (${response.status})`);
        }
        const payload = await response.json();
        if (!cancelled) {
          setIncidents(payload?.data?.incidents ?? []);
          setStatus("ready");
        }
      } catch (error) {
        console.error("Failed to load incidents", error);
        if (!cancelled) {
          setStatus("error");
        }
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="rounded-3xl border border-border/50 bg-background/70 p-6">
      <div className="flex flex-col gap-2 border-b border-border/40 pb-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.35em] text-muted-foreground">Incidents</p>
          <h2 className="text-xl font-semibold text-foreground">Latest multi-modal incidents</h2>
          <p className="text-sm text-muted-foreground">
            High-signal Cerebros runs promoted to incidents. Open each record to inspect blast radius, evidence, and
            linked nodes.
          </p>
        </div>
        <Button asChild variant="outline" size="sm" className="rounded-full text-xs">
          <Link href="/incidents">View all</Link>
        </Button>
      </div>

      {status === "loading" ? (
        <p className="pt-6 text-sm text-muted-foreground">Loading incidents…</p>
      ) : null}
      {status === "error" ? (
        <p className="pt-6 text-sm text-amber-500">Unable to load incidents right now.</p>
      ) : null}
      {status === "ready" && incidents.length === 0 ? (
        <p className="pt-6 text-sm text-muted-foreground">No incidents have been recorded yet.</p>
      ) : null}

      <div className="mt-4 space-y-3">
        {incidents.map((incident) => (
          <Link
            key={incident.id}
            href={`/incidents/${incident.id}`}
            className="block rounded-2xl border border-border/50 bg-background/70 p-4 transition hover:border-primary/60 hover:shadow-lg"
          >
            <IncidentRow incident={incident} />
          </Link>
        ))}
      </div>
    </section>
  );
}

const severityTone: Record<Severity, string> = {
  critical: "bg-red-500/15 text-red-100 border-red-500/30",
  high: "bg-orange-500/15 text-orange-100 border-orange-500/30",
  medium: "bg-amber-500/15 text-amber-100 border-amber-500/30",
  low: "bg-emerald-500/15 text-emerald-100 border-emerald-500/30",
};

const SIGNAL_LABELS: Record<string, { label: string; prefix: string }> = {
  git_events: { label: "Git", prefix: "🔥" },
  git_items: { label: "Git", prefix: "🔥" },
  slack_threads: { label: "Slack", prefix: "💬" },
  slack_conversations: { label: "Slack", prefix: "💬" },
  slack_complaints: { label: "Complaints", prefix: "😡" },
  support_complaints: { label: "Support", prefix: "😡" },
  doc_issues: { label: "Doc issues", prefix: "📄" },
  issues: { label: "Tickets", prefix: "📨" },
};

function IncidentRow({ incident }: { incident: IncidentRecord }) {
  const counts = incident.counts || {};
  const scopeSummary = [
    counts.components ? `${counts.components} components` : null,
    counts.docs ? `${counts.docs} docs` : null,
    counts.issues ? `${counts.issues} tickets` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  const rootCause =
    incident.rootCauseExplanation ||
    incident.answer ||
    incident.llmExplanation ||
    incident.summary;

  const impactLine = incident.impactSummary || scopeSummary || "Multi-modal signals detected";

  return (
    <div className="space-y-3" data-testid="incident-card">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-semibold text-foreground">{incident.summary}</p>
          <p className="text-xs text-muted-foreground" data-testid="incident-root-cause">
            {rootCause}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className={severityTone[incident.severity ?? "medium"]}>
            {incident.severity}
          </Badge>
          <Badge variant="outline" className="rounded-full border-border/60 text-[10px] uppercase">
            {incident.status}
          </Badge>
          {typeof incident.activityScore === "number" ? (
            <Badge variant="outline" className="rounded-full border-emerald-500/40 text-[10px] uppercase text-emerald-200">
              Activity {incident.activityScore.toFixed(1)}
            </Badge>
          ) : null}
          {typeof incident.dissatisfactionScore === "number" ? (
            <Badge variant="outline" className="rounded-full border-rose-500/40 text-[10px] uppercase text-rose-200">
              Diss {incident.dissatisfactionScore.toFixed(1)}
            </Badge>
          ) : null}
        </div>
      </div>

      <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
        <span>{impactLine}</span>
        <span>Detected {formatDate(incident.createdAt)}</span>
        {incident.recencyInfo?.hours_since !== undefined ? (
          <span>Last signal {incident.recencyInfo.hours_since}h ago</span>
        ) : null}
        {incident.blastRadiusScore !== undefined ? (
          <span>Blast radius • {Math.round(incident.blastRadiusScore)}</span>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-2">
        {renderSignalChips(incident.activitySignals, "activity")}
        {renderSignalChips(incident.dissatisfactionSignals, "dissatisfaction")}
      </div>
    </div>
  );
}

function renderSignalChips(
  signals: IncidentRecord["activitySignals"],
  variant: "activity" | "dissatisfaction",
) {
  if (!signals) return null;
  return Object.entries(signals)
    .filter(([, value]) => typeof value === "number" && value > 0)
    .map(([key, value]) => {
      const descriptor = SIGNAL_LABELS[key] || { label: key, prefix: variant === "activity" ? "🔥" : "😡" };
      return (
        <span
          key={`${variant}-${key}`}
          data-testid={`incident-${variant}-chip`}
          className={cn(
            "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold",
            variant === "activity"
              ? "border-emerald-500/40 text-emerald-200"
              : "border-rose-500/40 text-rose-200",
          )}
        >
          {descriptor.prefix} {descriptor.label}
          <span className="font-bold">{value}</span>
        </span>
      );
    });
}

function formatDate(value?: string) {
  if (!value) return "unknown time";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

