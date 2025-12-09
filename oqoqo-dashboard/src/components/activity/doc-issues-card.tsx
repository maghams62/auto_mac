"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, BookOpen, GitBranch, Loader2, MessageSquare } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { LinkChip } from "@/components/common/link-chip";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchApiEnvelope } from "@/lib/http/api-response";
import type { DocIssue, LiveMode } from "@/lib/types";
import { severityTokens } from "@/lib/ui/tokens";
import { cn, shortTime } from "@/lib/utils";

type DocIssuesResponse = {
  issues: DocIssue[];
  mode: LiveMode;
};

export function DocIssuesCard({ projectId }: { projectId?: string }) {
  const [issues, setIssues] = useState<DocIssue[]>([]);
  const [mode, setMode] = useState<LiveMode>("synthetic");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        params.set("limit", "6");
        if (projectId) {
          params.set("projectId", projectId);
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
          setError(err instanceof Error ? err.message : "Failed to load DocIssues");
          setIssues([]);
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
  }, [projectId]);

  return (
    <Card className="min-h-[360px] border border-border/70 bg-card/80">
      <CardHeader className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <CardTitle>Live DocIssues</CardTitle>
          <CardDescription>
            {statusMessage ?? "Real incidents emitted by the ImpactService."}
          </CardDescription>
        </div>
        <Badge variant="outline" className="rounded-full border-border/60 text-xs uppercase">
          {mode === "atlas" ? "Live" : "Synthetic"} mode
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <div className="flex items-center gap-2 rounded-2xl border border-dashed border-border/60 p-3 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Fetching doc issues…
          </div>
        ) : null}
        {error ? (
          <div className="flex items-center gap-2 rounded-2xl border border-amber-400/60 bg-amber-500/10 p-3 text-sm text-amber-100">
            <AlertTriangle className="h-4 w-4" />
            {error}
          </div>
        ) : null}
        {!loading && !error && issues.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/60 p-3 text-sm text-muted-foreground">
            No DocIssues surfaced yet. Trigger `/impact/git-change` or `/impact/slack-complaint` to populate the store.
          </div>
        ) : null}
        {issues.map((issue) => (
          <DocIssueRow key={issue.id} issue={issue} />
        ))}
      </CardContent>
    </Card>
  );
}

function describeDocIssuesStatus(fallbackReason?: string, errorMessage?: string) {
  if (!fallbackReason) {
    return errorMessage ?? null;
  }
  if (fallbackReason === "cerebros_unavailable") {
    return "Cerebros unavailable, showing fallback issues.";
  }
  if (fallbackReason === "synthetic_fallback") {
    return "Synthetic fixtures in use.";
  }
  return errorMessage ?? null;
}

function DocIssueRow({ issue }: { issue: DocIssue }) {
  const severity = severityTokens[issue.severity];
  return (
    <div className="space-y-3 rounded-2xl border border-border/60 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-foreground">{issue.title}</p>
          <p className="text-xs text-muted-foreground">
            {issue.componentId} • {issue.repoId}
          </p>
        </div>
        <Badge className={cn("border text-[10px]", severity.color)}>{severity.label}</Badge>
      </div>
      <p className="text-xs text-muted-foreground/90">
        {issue.summary || "Docs flagged by the latest impact analysis."}
      </p>
      <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
        <span>Updated {shortTime(issue.updatedAt)}</span>
        <span>Status • {issue.status}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        <LinkChip label="Git evidence" href={issue.githubUrl} icon={GitBranch} className="px-3 text-xs" />
        <LinkChip label="Slack thread" href={issue.slackUrl} icon={MessageSquare} className="px-3 text-xs" />
        <LinkChip label="View doc" href={issue.docUrl} icon={BookOpen} variant="ghost" className="px-3 text-xs" />
      </div>
    </div>
  );
}

