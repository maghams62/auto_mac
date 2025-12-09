"use client";

import Link from "next/link";
import { ExternalLink, FileText, GitCommit, LifeBuoy, MessageSquare, Ticket } from "lucide-react";

// Import removed to avoid Next alias issue

import { DeepLinkButtons } from "@/components/common/deep-link-buttons";
import { AskCerebrosButton, AskCerebrosCopyButton } from "@/components/common/ask-cerebros-button";
import { LinkChip } from "@/components/common/link-chip";
import { Badge } from "@/components/ui/badge";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { describeIssueSignals } from "@/lib/issues/descriptions";
import type { DocIssue, Project, SignalSource } from "@/lib/types";
import { cn, shortDate } from "@/lib/utils";
import { isValidUrl } from "@/lib/utils/url-validation";
import { severityTokens, signalSourceTokens, statusTokens } from "@/lib/ui/tokens";
import { Button } from "@/components/ui/button";
import { buildInvestigationUrl, resolveProjectSlug } from "@/lib/cerebros";

const cerebrosApiBase = process.env.NEXT_PUBLIC_CEREBROS_API_BASE?.replace(/\/$/, "");

interface IssueDetailBodyProps {
  issue: DocIssue;
  project: Project;
  showDeepLinkButton?: boolean;
}

export function IssueDetailBody({ issue, project, showDeepLinkButton = true }: IssueDetailBodyProps) {
  const component = project.components.find((item) => item.id === issue.componentId);
  const repo = project.repos.find((item) => item.id === issue.repoId);
  const relevantEvents =
    component?.sourceEvents
      .filter((event) => issue.divergenceSources.includes(event.source))
      .slice(0, 4) ?? [];

  const severity = severityTokens[issue.severity];
  const status = statusTokens[issue.status];
  const repoUrl = repo?.repoUrl && isValidUrl(repo.repoUrl) ? repo.repoUrl : null;
  const investigationUrl = buildInvestigationUrl(issue.originInvestigationId);
  const safeInvestigationUrl = isValidUrl(investigationUrl) ? investigationUrl : null;
  const projectSlug = resolveProjectSlug(project);
  const evidenceLinkEntries = issue.sourceLinks ?? [];
  const MAX_EVIDENCE_LINKS = 6;
  const evidenceDisplay = evidenceLinkEntries.slice(0, MAX_EVIDENCE_LINKS);
  const evidenceOverflow = Math.max(0, evidenceLinkEntries.length - MAX_EVIDENCE_LINKS);
  const hasEvidence =
    evidenceLinkEntries.length > 0 || (issue.evidenceIds && issue.evidenceIds.length > 0);

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge className={cn("border text-xs", severity.color)}>{severity.label}</Badge>
          <Badge className={cn("border text-xs", status.color)}>{status.label}</Badge>
          <span className="text-xs text-muted-foreground">Detected {shortDate(issue.detectedAt)}</span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <AskCerebrosButton
            projectId={project.id}
            projectSlug={projectSlug}
            componentId={component?.id ?? issue.componentId}
            issueId={issue.id}
            query={`Investigate documentation drift for "${issue.title}"`}
            size="sm"
            buttonClassName="rounded-full"
          />
          <AskCerebrosCopyButton
            command={`/slack docdrift ${component?.name ?? issue.componentId}`}
            label="Copy /slack docdrift"
            size="sm"
            variant="link"
            className="px-0 text-xs font-medium text-primary underline-offset-4 hover:underline"
          />
        </div>
        <h2 className="text-xl font-semibold text-foreground">{issue.title}</h2>
        <p className="text-sm text-muted-foreground">{issue.summary}</p>
        <p className="text-xs text-muted-foreground">{describeIssueSignals(issue)}</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <DetailCard label="Component" value={component?.name ?? "Unknown"}>
          {component ? (
            <Link href={`/projects/${project.id}/components/${component.id}`} className="text-xs text-primary">
              View component activity
            </Link>
          ) : null}
        </DetailCard>
        <DetailCard label="Repo" value={repo?.name ?? "Unknown"}>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>{repo?.branch}</span>
            {repoUrl ? (
              <a href={repoUrl} target="_blank" rel="noreferrer" className="text-primary">
                <ExternalLink className="h-3 w-3" />
              </a>
            ) : null}
          </div>
        </DetailCard>
        <DetailCard label="Doc path" value={issue.docPath} />
      </div>

      {issue.githubUrl || issue.slackUrl || issue.docUrl || investigationUrl ? (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Quick links</h3>
          <DeepLinkButtons
            githubUrl={issue.githubUrl}
            slackUrl={issue.slackUrl}
            docUrl={issue.docUrl}
            cerebrosUrl={issue.cerebrosUrl}
            size="md"
          />
          {safeInvestigationUrl ? (
            <Button variant="outline" size="sm" asChild>
              <a href={safeInvestigationUrl} target="_blank" rel="noreferrer">
                View investigation in Cerebros
              </a>
            </Button>
          ) : issue.originInvestigationId ? (
            <p className="text-xs text-muted-foreground">
              Investigation {issue.originInvestigationId} exists, but Cerebros base URL is not configured.
            </p>
          ) : null}
        </div>
      ) : null}

      {cerebrosApiBase ? (
        <div className="rounded-2xl border border-border/60 bg-background/70 p-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Graph context</h3>
            <span className="text-xs text-muted-foreground">Live Neo4j slice</span>
          </div>
          <div className="mt-3">
            <GraphExplorer
              mode="issue"
              rootNodeId={issue.id}
              depth={2}
              apiBaseUrl={cerebrosApiBase}
              hideDatabasePanel
              enableTimeControls={false}
              title={`Doc issue · ${issue.id}`}
              className="bg-slate-950/40 p-2"
            />
          </div>
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-4">
        <Signal metric="Git churn" value={issue.signals.gitChurn} icon={GitCommit} />
        <Signal metric="Tickets referenced" value={issue.signals.ticketsMentioned} icon={Ticket} />
        <Signal metric="Slack mentions" value={issue.signals.slackMentions} icon={MessageSquare} />
        <Signal metric="Support mentions" value={issue.signals.supportMentions ?? 0} icon={LifeBuoy} />
      </div>

      <div className="space-y-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Cross-system divergence</h3>
        <div className="flex flex-wrap gap-2">
          {issue.divergenceSources.map((source) => {
            const token = signalSourceTokens[source];
            return (
              <Badge key={`${issue.id}-${source}`} className={cn("border text-[10px]", token.color)}>
                {token.label}
              </Badge>
            );
          })}
        </div>
      </div>

      <div className="space-y-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Suggested fixes</h3>
        <ul className="list-disc space-y-2 pl-4 text-sm text-foreground/90">
          {issue.suggestedFixes.map((fix) => (
            <li key={fix}>{fix}</li>
          ))}
        </ul>
      </div>

      {hasEvidence ? (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Evidence</h3>
          <div className="flex flex-wrap gap-2">
            {evidenceDisplay.map((link, index) =>
              link?.url ? (
                <Button variant="outline" size="sm" asChild key={`${issue.id}-evidence-link-${index}`}>
                  <a href={link.url} target="_blank" rel="noreferrer">
                    {link.label ?? link.type ?? link.url}
                  </a>
                </Button>
              ) : null,
            )}
            {evidenceOverflow > 0 ? (
              <Badge variant="outline" className="rounded-full border-border/50 text-[10px]">
                +{evidenceOverflow} more
              </Badge>
            ) : null}
            {issue.evidenceIds?.slice(0, MAX_EVIDENCE_LINKS).map((eid) => (
              <Badge key={`${issue.id}-evidence-${eid}`} variant="secondary" className="rounded-full text-[10px]">
                {eid}
              </Badge>
            ))}
          </div>
        </div>
      ) : null}

      <div className="space-y-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Linked files</h3>
        <div className="flex flex-wrap gap-2">
          {issue.linkedCode.map((file) => (
            <Badge key={file} variant="outline" className="rounded-full border-border/50 text-xs">
              {file}
            </Badge>
          ))}
        </div>
      </div>

      {relevantEvents.length ? (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Signals powering this issue</h3>
          <div className="space-y-3">
            {relevantEvents.map((event) => {
              const Icon = detailSourceIconMap[event.source];
              const token = signalSourceTokens[event.source];
              return (
                <div key={event.id} className="rounded-2xl border border-border/50 p-4">
                  <div className="flex items-start gap-3">
                    <Icon className="mt-1 h-4 w-4 text-primary" />
                    <div>
                      <div className="text-sm font-semibold text-foreground">{event.title}</div>
                      <p className="text-xs text-muted-foreground">{event.description}</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-2 pt-2 text-xs text-muted-foreground">
                    <span>{shortDate(event.timestamp)}</span>
                    <div className="flex items-center gap-2">
                      <Badge className={cn("border text-[10px]", token.color)}>{token.label}</Badge>
                      <LinkChip
                        label="Open source"
                        href={event.link}
                        variant="ghost"
                        size="sm"
                        className="h-auto p-0 text-[11px]"
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      {showDeepLinkButton ? (
        <Button asChild variant="outline" className="rounded-full">
          <Link href={`/projects/${project.id}/issues/${issue.id}`}>Open dedicated issue view</Link>
        </Button>
      ) : null}
    </div>
  );
}

interface IssueSheetProps extends IssueDetailBodyProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function IssueDetailSheet({ issue, project, open, onOpenChange }: IssueSheetProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="max-w-xl border-border/60 bg-background/95">
        <IssueDetailBody issue={issue} project={project} />
      </SheetContent>
    </Sheet>
  );
}

const DetailCard = ({
  label,
  value,
  children,
}: {
  label: string;
  value: string;
  children?: React.ReactNode;
}) => (
  <div className="rounded-2xl border border-border/60 p-4">
    <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</div>
    <div className="text-sm font-medium text-foreground">{value}</div>
    {children}
  </div>
);

const Signal = ({
  metric,
  value,
  icon: Icon,
}: {
  metric: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
}) => (
  <div className="rounded-2xl border border-border/60 p-4">
    <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{metric}</div>
    <div className="flex items-center gap-2 text-2xl font-bold">
      <Icon className="h-4 w-4 text-primary" />
      {value}
    </div>
  </div>
);

const detailSourceIconMap: Record<SignalSource, React.ComponentType<{ className?: string }>> = {
  git: GitCommit,
  docs: FileText,
  slack: MessageSquare,
  tickets: Ticket,
  support: LifeBuoy,
};

