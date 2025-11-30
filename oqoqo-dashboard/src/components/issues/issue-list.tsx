import Link from "next/link";
import { ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { describeIssueSignals } from "@/lib/issues/descriptions";
import type { DocIssue, SourceEvent } from "@/lib/types";
import { severityTokens, signalSourceTokens, statusTokens } from "@/lib/ui/tokens";
import { cn, shortDate } from "@/lib/utils";

interface IssueListProps {
  issues: DocIssue[];
  onSelect: (issue: DocIssue) => void;
  componentLookup?: Record<string, string>;
  componentEvents?: Record<string, SourceEvent[]>;
  projectId?: string;
}

export function IssueList({ issues, onSelect, componentLookup, componentEvents, projectId }: IssueListProps) {
  if (!issues.length) {
    return <div className="rounded-2xl border border-dashed border-border/50 p-6 text-sm text-muted-foreground">No issues match the current filters.</div>;
  }

  return (
    <div className="space-y-3">
      {issues.map((issue) => {
        const severity = severityTokens[issue.severity];
        const status = statusTokens[issue.status];
        const isLive = issue.id.startsWith("live_issue");
        const signalSummary = describeIssueSignals(issue);
        const eventLinks =
          componentEvents?.[issue.componentId]
            ?.filter((event) => Boolean(event.link))
            .reduce<Record<string, SourceEvent>>((acc, event) => {
              if (event.link && !acc[event.source]) {
                acc[event.source] = event;
              }
              return acc;
            }, {}) ?? undefined;
        return (
          <div
            key={issue.id}
            className={cn(
              "flex flex-col gap-3 rounded-2xl border border-border/60 bg-card/60 p-4 transition hover:border-primary/40",
              isLive && "border-primary/40 bg-primary/5"
            )}
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge className={cn("border text-xs", severity.color)}>{severity.label}</Badge>
              <Badge className={cn("border text-xs", status.color)}>{status.label}</Badge>
              {isLive ? (
                <Badge className="border border-emerald-400/60 bg-emerald-500/15 text-[10px] text-emerald-100">Live drift</Badge>
              ) : null}
              <span className="text-xs text-muted-foreground">Detected {shortDate(issue.detectedAt)}</span>
              <span className="text-xs text-muted-foreground">Updated {shortDate(issue.updatedAt)}</span>
            </div>
            <div>
              <div className="text-lg font-semibold text-foreground">{issue.title}</div>
              <p className="text-sm text-muted-foreground line-clamp-2">{issue.summary}</p>
              <p className="text-xs text-muted-foreground">{signalSummary}</p>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <span>Component • {componentLookup?.[issue.componentId] ?? issue.componentId}</span>
              <span>Doc • {issue.docPath}</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {issue.divergenceSources.map((source) => {
                const token = signalSourceTokens[source];
                return (
                  <Badge key={`${issue.id}-${source}`} className={cn("border text-[10px]", token.color)}>
                    {token.label}
                  </Badge>
                );
              })}
              {eventLinks
                ? Object.values(eventLinks).map((event) => {
                    const token = signalSourceTokens[event.source];
                    return (
                      <Badge key={event.id} variant="outline" className={`border text-[10px] ${token.color}`}>
                        <a href={event.link} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline">
                          {token.label} link
                        </a>
                      </Badge>
                    );
                  })
                : null}
            </div>
            <details className="rounded-2xl border border-border/40 bg-background/50 p-3 text-xs text-muted-foreground [&_summary::-webkit-details-marker]:hidden">
              <summary className="flex cursor-pointer items-center justify-between text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Signals breakdown
                <span className="text-[10px] text-muted-foreground/80">tap to expand</span>
              </summary>
              <div className="mt-2 grid gap-2 text-[11px] text-muted-foreground sm:grid-cols-2">
                <span>Git churn • {issue.signals.gitChurn}</span>
                <span>Slack mentions • {issue.signals.slackMentions}</span>
                <span>Tickets referenced • {issue.signals.ticketsMentioned}</span>
                <span>Support references • {issue.signals.supportMentions ?? 0}</span>
              </div>
            </details>
            <div className="flex flex-wrap justify-end gap-2">
              <Button variant="ghost" className="rounded-full text-sm" onClick={() => onSelect(issue)}>
                View details
                <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
              {projectId ? (
                <Button variant="ghost" className="rounded-full text-sm" asChild>
                  <Link href={`/projects/${projectId}/issues/${issue.id}`}>
                    Open page
                    <ChevronRight className="ml-1 h-4 w-4" />
                  </Link>
                </Button>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}

