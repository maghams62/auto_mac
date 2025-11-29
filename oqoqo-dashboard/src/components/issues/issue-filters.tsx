import { X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { IssueFilters, IssueStatus, Severity } from "@/lib/types";
import { severityTokens, statusTokens } from "@/lib/ui/tokens";

const statusOrder: IssueStatus[] = ["open", "triage", "in_progress", "resolved"];
const severityOrder: Severity[] = ["critical", "high", "medium", "low"];

interface IssueFiltersProps {
  filters: IssueFilters;
  onChange: (filters: Partial<IssueFilters>) => void;
  onReset: () => void;
}

export function IssueFilters({ filters, onChange, onReset }: IssueFiltersProps) {
  const toggleSeverity = (severity: Severity) => {
    const next = filters.severities.includes(severity)
      ? filters.severities.filter((item) => item !== severity)
      : [...filters.severities, severity];
    onChange({ severities: next });
  };

  const toggleStatus = (status: IssueStatus) => {
    const next = filters.statuses.includes(status)
      ? filters.statuses.filter((item) => item !== status)
      : [...filters.statuses, status];
    onChange({ statuses: next });
  };

  return (
    <div className="space-y-4 rounded-2xl border border-border/60 bg-card/60 p-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <Input
          placeholder="Search by component, doc path, summary..."
          value={filters.search}
          onChange={(event) => onChange({ search: event.target.value })}
          className="rounded-2xl border-border/60"
        />
        <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={onReset}>
          <X className="mr-1 h-4 w-4" />
          Clear filters
        </Button>
      </div>

      <div className="flex flex-col gap-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Severity</div>
        <div className="flex flex-wrap gap-2">
          {severityOrder.map((severity) => {
            const token = severityTokens[severity];
            const active = filters.severities.length === 0 || filters.severities.includes(severity);
            return (
              <Badge
                key={severity}
                onClick={() => toggleSeverity(severity)}
                className={`cursor-pointer border ${token.color} ${active ? "" : "opacity-40"}`}
              >
                {token.label}
              </Badge>
            );
          })}
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Status</div>
        <div className="flex flex-wrap gap-2">
          {statusOrder.map((status) => {
            const token = statusTokens[status];
            const active = filters.statuses.length === 0 || filters.statuses.includes(status);
            return (
              <Badge
                key={status}
                onClick={() => toggleStatus(status)}
                className={`cursor-pointer border ${token.color} ${active ? "" : "opacity-40"}`}
              >
                {token.label}
              </Badge>
            );
          })}
        </div>
      </div>
    </div>
  );
}

