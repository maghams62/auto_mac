"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, BookOpen, GitBranch, MessageSquare } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { LinkChip } from "@/components/common/link-chip";
import { fetchApiEnvelope } from "@/lib/http/api-response";
import type { DocIssue, LiveMode, Project } from "@/lib/types";
import { useDashboardStore } from "@/lib/state/dashboard-store";
import { severityTokens } from "@/lib/ui/tokens";
import { shortTime } from "@/lib/utils";

type OptionTwoCardProps = {
  project: Project;
};

type DocIssuesResponse = {
  issues: DocIssue[];
  mode: LiveMode;
};

export function SetupOptionTwoCard({ project }: OptionTwoCardProps) {
  const [issues, setIssues] = useState<DocIssue[]>([]);
  const [mode, setMode] = useState<LiveMode>("synthetic");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const modePreference = useDashboardStore((state) => state.modePreference);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        params.set("limit", "3");
        params.set("projectId", project.id);
        if (modePreference) {
          params.set("mode", modePreference);
        }
        const payload = await fetchApiEnvelope<DocIssuesResponse>(`/api/doc-issues?${params.toString()}`, {
          cache: "no-store",
        });
        if (!cancelled) {
          const data = payload.data;
          if (!data?.issues) {
            throw new Error(payload.error?.message ?? "DocIssues unavailable");
          }
          setIssues(data.issues);
          setMode(data.mode ?? payload.mode ?? "synthetic");
          setStatusMessage(
            payload.status === "OK"
              ? null
              : describeDocIssuesStatus(payload.fallbackReason, payload.error?.message),
          );
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load impact data");
          setIssues(project.docIssues.slice(0, 3));
          setStatusMessage(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [project, modePreference]);

  const summarySentence = useMemo(() => buildImpactSummary(project, issues), [project, issues]);
  const modeLabel = mode === "atlas" ? "Live" : mode === "synthetic" ? "Synthetic" : mode;

  return (
    <Card className="border-border/70 bg-card/80">
      <CardHeader>
        <CardTitle>Option 2 · Impact / DocIssues</CardTitle>
        <CardDescription>{summarySentence}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="text-xs text-muted-foreground">
          Impact analysis mode: <span className="font-medium text-foreground">{modeLabel}</span>
          {statusMessage ? <span className="ml-2 text-amber-200">{statusMessage}</span> : null}
        </div>
        {loading ? <p className="text-muted-foreground">Pulling top doc issues…</p> : null}
        {error ? (
          <div className="flex items-center gap-2 text-amber-200">
            <AlertTriangle className="h-4 w-4" />
            {error}
          </div>
        ) : null}
        <div className="space-y-3">
          {issues.slice(0, 3).map((issue) => (
            <IssueSnippet key={issue.id} project={project} issue={issue} />
          ))}
          {!issues.length && !loading ? <p className="text-muted-foreground">No live doc issues are open right now.</p> : null}
        </div>
      </CardContent>
    </Card>
  );
}

function describeDocIssuesStatus(fallbackReason?: string, errorMessage?: string) {
  if (!fallbackReason) {
    return errorMessage ?? null;
  }
  if (fallbackReason === "cerebros_unavailable") {
    return "Cerebros unavailable";
  }
  if (fallbackReason === "synthetic_fallback") {
    return "Synthetic fixtures in use";
  }
  return errorMessage ?? null;
}

function buildImpactSummary(project: Project, issues: DocIssue[]) {
  const services = project.components.length;
  const repos = project.repos.length;
  const openCount = issues.length;
  const impactEnabled = Boolean(project.dependencies.length || openCount);

  if (!impactEnabled) {
    return `Impact analysis is standing by for ${services} services (${repos} repos). No doc issues currently need attention.`;
  }

  return `Impact analysis is active for ${services} services (${repos} repos) and tracking ${openCount} open documentation issues.`;
}

function IssueSnippet({ issue, project }: { issue: DocIssue; project: Project }) {
  const severity = severityTokens[issue.severity];
  const componentName = project.components.find((component) => component.id === issue.componentId)?.name ?? issue.componentId;
  return (
    <div className="space-y-2 rounded-2xl border border-border/60 p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="font-semibold text-foreground">{componentName}</p>
          <p className="text-xs text-muted-foreground">{issue.title}</p>
        </div>
        <Badge className={severity.color}>{severity.label}</Badge>
      </div>
      <p className="text-xs text-muted-foreground/90">{issue.summary || "Docs flagged by impact analysis."}</p>
      <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
        <span>Updated {shortTime(issue.updatedAt)}</span>
        <LinkChips issue={issue} />
      </div>
    </div>
  );
}

function LinkChips({ issue }: { issue: DocIssue }) {
  const chips = [
    { label: "Doc", url: issue.docUrl, icon: BookOpen, variant: "ghost" as const },
    { label: "PR/commit", url: issue.githubUrl, icon: GitBranch, variant: "ghost" as const },
    { label: "Slack", url: issue.slackUrl, icon: MessageSquare, variant: "ghost" as const },
  ];

  if (!chips.some((chip) => chip.url)) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {chips.map((chip) => (
        <LinkChip
          key={chip.label}
          label={chip.label}
          href={chip.url}
          icon={chip.icon}
          variant={chip.variant}
          size="sm"
          className="h-auto rounded-full px-3 text-xs"
        />
      ))}
    </div>
  );
}


