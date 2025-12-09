import Link from "next/link";
import { BookOpen, GitBranch, MessageSquare, Sparkles, Ticket } from "lucide-react";

import { DeepLinkButtons } from "@/components/common/deep-link-buttons";
import { LinkChip } from "@/components/common/link-chip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { describeIssueSignals } from "@/lib/issues/descriptions";
import type { DocIssue, LiveMode, SourceLink } from "@/lib/types";
import { severityTokens, statusTokens } from "@/lib/ui/tokens";
import { cn, shortDate, shortTime } from "@/lib/utils";
import { isValidUrl } from "@/lib/utils/url-validation";

type ComponentMeta = { name: string; ownerTeam?: string };

interface IssueListProps {
  issues: DocIssue[];
  onSelect: (issue: DocIssue) => void;
  componentLookup?: Record<string, ComponentMeta>;
  errorMessage?: string;
  mode?: LiveMode;
}

const sourceLinkIcons: Record<SourceLink["type"], React.ComponentType<{ className?: string }>> = {
  slack: MessageSquare,
  git: GitBranch,
  ticket: Ticket,
  doc: BookOpen,
};

export function IssueList({ issues, onSelect, componentLookup, errorMessage, mode }: IssueListProps) {
  const syntheticNotice =
    mode === "synthetic"
      ? "Showing synthetic DocIssues until the live provider succeeds."
      : null;

  return (
    <div className="space-y-3">
      {errorMessage ? (
        <div className="rounded-2xl border border-amber-400/60 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          {errorMessage}
        </div>
      ) : null}
      {syntheticNotice ? (
        <div className="rounded-2xl border border-slate-600/60 bg-slate-800/40 px-4 py-3 text-xs text-slate-100">
          {syntheticNotice}
        </div>
      ) : null}
      {!issues.length ? (
        <div className="rounded-2xl border border-dashed border-border/50 p-6 text-sm text-muted-foreground">
          No issues match the current filters.
        </div>
      ) : null}
      {issues.map((issue) => {
        const severity = severityTokens[issue.severity];
        const status = statusTokens[issue.status];
        const componentMeta = componentLookup?.[issue.componentId];
        const signalSummary = formatSignalSummary(issue);
        const lastActivity = shortTime(issue.updatedAt);
        const sourceLinks = issue.sourceLinks?.slice(0, 3) ?? [];
        const cerebrosUrl = isValidUrl(issue.cerebrosUrl) ? issue.cerebrosUrl : null;
        const brainTraceUrl = issue.brainTraceUrl;
        const traceIsInternal = brainTraceUrl?.startsWith("/");
        const reason = describeIssueSignals(issue);
        return (
          <div
            key={issue.id}
            className="space-y-3 rounded-2xl border border-border/60 bg-card/60 p-4 transition hover:border-primary/40"
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="text-lg font-semibold text-foreground">{issue.title}</div>
                <p className="text-xs text-muted-foreground">
                  {componentMeta?.name ?? issue.componentId}
                  {componentMeta?.ownerTeam ? ` • ${componentMeta.ownerTeam}` : null}
                </p>
                <p className="text-sm text-muted-foreground line-clamp-2">{issue.summary}</p>
                {reason ? <p className="text-xs text-muted-foreground/80">{reason}</p> : null}
              </div>
              <div className="flex flex-col items-end gap-2">
                <Badge className={cn("border text-xs", severity.color)}>{severity.label}</Badge>
                <Badge className={cn("border text-xs", status.color)}>{status.label}</Badge>
                <span className="text-[11px] text-muted-foreground">Detected {shortDate(issue.detectedAt)}</span>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <span>Last activity {lastActivity}</span>
              <span>{signalSummary}</span>
              <span>Doc • {issue.docPath}</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {brainTraceUrl ? (
                <Button asChild variant="default" size="sm" className="rounded-full px-3">
                  {traceIsInternal ? (
                    <Link href={brainTraceUrl} target="_blank" rel="noreferrer">
                      View reasoning path
                    </Link>
                  ) : (
                    <a href={brainTraceUrl} target="_blank" rel="noreferrer">
                      View reasoning path
                    </a>
                  )}
                </Button>
              ) : null}
              {cerebrosUrl ? (
                <Button asChild variant="secondary" size="sm" className="rounded-full px-3">
                  <a href={cerebrosUrl} target="_blank" rel="noreferrer">
                    <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                    Open in Cerebros
                  </a>
                </Button>
              ) : null}
              {sourceLinks.map((link) => {
                const Icon = sourceLinkIcons[link.type];
                return (
                  <LinkChip
                    key={`${issue.id}-${link.label}`}
                    label={link.label}
                    href={link.url}
                    icon={Icon}
                    size="sm"
                    className="px-3 text-xs"
                  />
                );
              })}
            </div>
            <DeepLinkButtons
              githubUrl={issue.githubUrl}
              slackUrl={issue.slackUrl}
              docUrl={issue.docUrl}
              className="pt-1"
            />
            <div className="flex justify-end">
              <Button variant="ghost" size="sm" className="rounded-full px-4" onClick={() => onSelect(issue)}>
                View issue
              </Button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function formatSignalSummary(issue: DocIssue) {
  const parts = [
    issue.signals.slackMentions ? `${issue.signals.slackMentions} Slack` : null,
    issue.signals.gitChurn ? `${issue.signals.gitChurn} Git` : null,
    issue.signals.ticketsMentioned ? `${issue.signals.ticketsMentioned} Tickets` : null,
    issue.signals.supportMentions ? `${issue.signals.supportMentions} Support` : null,
  ].filter(Boolean);

  return parts.length ? parts.join(" · ") : "No live signal spikes yet";
}

