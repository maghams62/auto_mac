"use client";

import Link from "next/link";
import { AlertTriangle, BookOpen, GitBranch, MessageSquare } from "lucide-react";

import type { DocIssue } from "@/lib/types";
import { severityTokens } from "@/lib/ui/tokens";
import { cn, shortTime } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { LinkChip } from "@/components/common/link-chip";

interface ComponentDocIssuesListProps {
  issues: DocIssue[];
  projectId?: string;
  componentId?: string | null;
}

export function ComponentDocIssuesList({ issues, projectId, componentId }: ComponentDocIssuesListProps) {
  const severityRank: Record<DocIssue["severity"], number> = {
    critical: 0,
    high: 1,
    medium: 2,
    low: 3,
  };
  const ranked = [...issues].sort((a, b) => {
    const severityDelta = severityRank[a.severity] - severityRank[b.severity];
    if (severityDelta !== 0) return severityDelta;
    const aTime = Date.parse(a.updatedAt);
    const bTime = Date.parse(b.updatedAt);
    return Number.isNaN(bTime - aTime) ? 0 : bTime - aTime;
  });
  const list = ranked.slice(0, 3);
  const hasIssues = list.length > 0;
  const isHttpUrl = (value?: string | null) => Boolean(value && /^https?:\/\//i.test(value));

  return (
    <Card className="h-full">
      <CardHeader className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <CardTitle>Doc issues to fix</CardTitle>
          <CardDescription>Most recent problems linked to this component.</CardDescription>
        </div>
        <Button
          variant="outline"
          size="sm"
          asChild
          className="rounded-full text-xs"
          disabled={!projectId || !componentId}
        >
          <Link href={`/projects/${projectId}/issues?component=${componentId ?? ""}`}>View all</Link>
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {!hasIssues ? (
          <div className="flex items-center gap-2 rounded-2xl border border-dashed border-border/60 px-3 py-4 text-sm text-muted-foreground">
            <AlertTriangle className="h-4 w-4" />
            <span>No doc issues surfaced for this component yet.</span>
          </div>
        ) : (
          list.map((issue) => {
            const severity = severityTokens[issue.severity];
            return (
              <div
                key={issue.id}
                className="space-y-2 rounded-2xl border border-border/60 p-4"
                data-testid="doc-issue-card"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-foreground">{issue.title}</p>
                    <p className="text-xs text-muted-foreground">{issue.repoId}</p>
                  </div>
                  <Badge className={cn("border text-[10px]", severity.color)}>{severity.label}</Badge>
                </div>
                <p className="text-xs text-muted-foreground">{issue.summary ?? "Docs flagged by recent activity signals."}</p>
                <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
                  <span>Updated {shortTime(issue.updatedAt)}</span>
                  <span>Status · {issue.status}</span>
                </div>
                <div className="flex flex-wrap gap-2 text-xs">
                  {isHttpUrl(issue.githubUrl) ? (
                    <LinkChip label="Git evidence" href={issue.githubUrl} icon={GitBranch} className="px-3" />
                  ) : null}
                  {isHttpUrl(issue.slackUrl) ? (
                    <LinkChip label="Slack thread" href={issue.slackUrl} icon={MessageSquare} className="px-3" />
                  ) : null}
                  {issue.docUrl ? (
                    <LinkChip label="View doc" href={issue.docUrl} icon={BookOpen} variant="ghost" className="px-3" />
                  ) : null}
                </div>
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}

