import Link from "next/link";
import { ExternalLink, GitCommit, MessageSquare, Ticket } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import type { DocIssue, Project } from "@/lib/types";
import { cn, shortDate } from "@/lib/utils";
import { severityTokens, statusTokens } from "@/lib/ui/tokens";
import { Button } from "@/components/ui/button";

interface IssueDetailBodyProps {
  issue: DocIssue;
  project: Project;
}

export function IssueDetailBody({ issue, project }: IssueDetailBodyProps) {
  const component = project.components.find((item) => item.id === issue.componentId);
  const repo = project.repos.find((item) => item.id === issue.repoId);

  const severity = severityTokens[issue.severity];
  const status = statusTokens[issue.status];

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge className={cn("border text-xs", severity.color)}>{severity.label}</Badge>
          <Badge className={cn("border text-xs", status.color)}>{status.label}</Badge>
          <span className="text-xs text-muted-foreground">Detected {shortDate(issue.detectedAt)}</span>
        </div>
        <h2 className="text-xl font-semibold text-foreground">{issue.title}</h2>
        <p className="text-sm text-muted-foreground">{issue.summary}</p>
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
            <a href={repo?.repoUrl} target="_blank" className="text-primary">
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </DetailCard>
        <DetailCard label="Doc path" value={issue.docPath} />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Signal metric="Git churn" value={issue.signals.gitChurn} icon={GitCommit} />
        <Signal metric="Tickets referenced" value={issue.signals.ticketsMentioned} icon={Ticket} />
        <Signal metric="Slack mentions" value={issue.signals.slackMentions} icon={MessageSquare} />
      </div>

      <div className="space-y-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Suggested fixes</h3>
        <ul className="list-disc space-y-2 pl-4 text-sm text-foreground/90">
          {issue.suggestedFixes.map((fix) => (
            <li key={fix}>{fix}</li>
          ))}
        </ul>
      </div>

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

      <Button asChild variant="outline" className="rounded-full">
        <Link href={`/projects/${project.id}/issues/${issue.id}`}>Open dedicated issue view</Link>
      </Button>
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

