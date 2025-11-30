import { X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { IssueFilters, IssueStatus, Severity, SignalSource } from "@/lib/types";
import { severityTokens, signalSourceTokens, statusTokens } from "@/lib/ui/tokens";

const statusOrder: IssueStatus[] = ["open", "triage", "in_progress", "resolved"];
const severityOrder: Severity[] = ["critical", "high", "medium", "low"];
const sourceOrder: SignalSource[] = ["git", "docs", "slack", "tickets", "support"];
const timeRanges: IssueFilters["timeRange"][] = ["24h", "7d", "30d", "90d"];

interface IssueFiltersProps {
  filters: IssueFilters;
  onChange: (filters: Partial<IssueFilters>) => void;
  onReset: () => void;
  components?: { id: string; name: string }[];
}

export function IssueFilters({ filters, onChange, onReset, components }: IssueFiltersProps) {
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

  const toggleSource = (source: SignalSource) => {
    const next = filters.sources.includes(source)
      ? filters.sources.filter((item) => item !== source)
      : [...filters.sources, source];
    onChange({ sources: next });
  };

  const handleTimeRange = (range: IssueFilters["timeRange"]) => {
    onChange({ timeRange: range });
  };

  const toggleComponent = (componentId: string) => {
    const next = filters.componentIds.includes(componentId)
      ? filters.componentIds.filter((id) => id !== componentId)
      : [...filters.componentIds, componentId];
    onChange({ componentIds: next });
  };

  const toggleLiveOnly = () => {
    onChange({ onlyLive: !filters.onlyLive });
  };

  const setSort = (sort: IssueFilters["sort"]) => {
    onChange({ sort });
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
      <div className="flex flex-wrap gap-2">
        <Badge
          onClick={toggleLiveOnly}
          className={`cursor-pointer border text-[11px] ${
            filters.onlyLive ? "border-emerald-400/60 bg-emerald-500/10 text-emerald-100" : "border-border/60 text-muted-foreground"
          }`}
        >
          Live issues only
        </Badge>
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

      {components?.length ? (
        <div className="flex flex-col gap-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Components</div>
          <div className="flex flex-wrap gap-2">
            <Badge
              onClick={() => onChange({ componentIds: [] })}
              className={`cursor-pointer border border-border/60 text-[11px] ${filters.componentIds.length === 0 ? "" : "opacity-50"}`}
            >
              All components
            </Badge>
            {components.slice(0, 8).map((component) => (
              <Badge
                key={component.id}
                onClick={() => toggleComponent(component.id)}
                className={`cursor-pointer border border-border/60 text-[11px] ${
                  filters.componentIds.includes(component.id) ? "bg-primary/15 text-primary" : "opacity-60"
                }`}
              >
                {component.name}
              </Badge>
            ))}
          </div>
        </div>
      ) : null}

      <div className="flex flex-col gap-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Sources</div>
        <div className="flex flex-wrap gap-2">
          <Badge
            onClick={() => onChange({ sources: [] })}
            className={`cursor-pointer border border-border/60 text-[11px] ${filters.sources.length === 0 ? "" : "opacity-50"}`}
          >
            All sources
          </Badge>
          {sourceOrder.map((source) => {
            const token = signalSourceTokens[source];
            const active = filters.sources.includes(source);
            return (
              <Badge
                key={source}
                onClick={() => toggleSource(source)}
                className={`cursor-pointer border ${token.color} ${active ? "" : "opacity-40"}`}
              >
                {token.label}
              </Badge>
            );
          })}
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Time range</div>
        <div className="flex flex-wrap gap-2">
          {timeRanges.map((range) => (
            <Badge
              key={range}
              onClick={() => handleTimeRange(range)}
              className={`cursor-pointer border border-border/60 text-[11px] ${
                filters.timeRange === range ? "bg-primary/15 text-primary" : "opacity-60"
              }`}
            >
              {range}
            </Badge>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Sort by</div>
        <div className="flex flex-wrap gap-2">
          <Badge
            onClick={() => setSort("recent")}
            className={`cursor-pointer border border-border/60 text-[11px] ${
              filters.sort === "recent" ? "bg-primary/15 text-primary" : "opacity-60"
            }`}
          >
            Most recent
          </Badge>
          <Badge
            onClick={() => setSort("severity")}
            className={`cursor-pointer border border-border/60 text-[11px] ${
              filters.sort === "severity" ? "bg-primary/15 text-primary" : "opacity-60"
            }`}
          >
            Severity
          </Badge>
        </div>
      </div>
    </div>
  );
}

