import { ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { DocIssue } from "@/lib/types";
import { severityTokens, statusTokens } from "@/lib/ui/tokens";
import { cn, shortDate } from "@/lib/utils";

interface IssueListProps {
  issues: DocIssue[];
  onSelect: (issue: DocIssue) => void;
}

export function IssueList({ issues, onSelect }: IssueListProps) {
  if (!issues.length) {
    return <div className="rounded-2xl border border-dashed border-border/50 p-6 text-sm text-muted-foreground">No issues match the current filters.</div>;
  }

  return (
    <div className="space-y-3">
      {issues.map((issue) => {
        const severity = severityTokens[issue.severity];
        const status = statusTokens[issue.status];
        return (
          <div
            key={issue.id}
            className="flex flex-col gap-3 rounded-2xl border border-border/60 bg-card/60 p-4 transition hover:border-primary/40"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge className={cn("border text-xs", severity.color)}>{severity.label}</Badge>
              <Badge className={cn("border text-xs", status.color)}>{status.label}</Badge>
              <span className="text-xs text-muted-foreground">Updated {shortDate(issue.updatedAt)}</span>
            </div>
            <div>
              <div className="text-lg font-semibold text-foreground">{issue.title}</div>
              <p className="text-sm text-muted-foreground line-clamp-2">{issue.summary}</p>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <span>Component • {issue.componentId}</span>
              <span>Doc • {issue.docPath}</span>
              <span>Signals • churn {issue.signals.gitChurn}, tickets {issue.signals.ticketsMentioned}</span>
            </div>
            <div className="flex justify-end">
              <Button variant="ghost" className="rounded-full text-sm" onClick={() => onSelect(issue)}>
                View details
                <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

