"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ChevronDown, Flame, Shield, Users } from "lucide-react";

import { IssueDetailSheet } from "@/components/issues/issue-detail";
import { IssueFilters } from "@/components/issues/issue-filters";
import { IssueList } from "@/components/issues/issue-list";
import { LiveRecency } from "@/components/live/live-recency";
import { ManualRefreshButton } from "@/components/live/manual-refresh";
import { NewSignalToast } from "@/components/live/new-signal-toast";
import { LiveModePill } from "@/components/live/live-mode-pill";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { describeIssueSignals } from "@/lib/issues/descriptions";
import { filterIssuesWithContext } from "@/lib/issues/utils";
import { describeMode, isLiveLike } from "@/lib/mode";
import { selectProjectById, useDashboardStore } from "@/lib/state/dashboard-store";
import { cn, shortDate } from "@/lib/utils";
import { signalSourceTokens } from "@/lib/ui/tokens";
import type { DocIssue, Severity, SourceEvent } from "@/lib/types";

const severityOrder: Severity[] = ["critical", "high", "medium", "low"];

export default function ProjectOverviewPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const filters = useDashboardStore((state) => state.issueFilters);
  const setFilters = useDashboardStore((state) => state.setIssueFilters);
  const resetFilters = useDashboardStore((state) => state.resetIssueFilters);
  const projectSelector = useMemo(() => selectProjectById(projectId), [projectId]);
  const project = useDashboardStore(projectSelector);

  const [selectedIssue, setSelectedIssue] = useState<DocIssue | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);

  const liveStatus = useDashboardStore((state) => state.liveStatus);
  const liveSnapshot = useDashboardStore((state) => state.liveSnapshot);
  const referenceTime = liveStatus.lastUpdated ? new Date(liveStatus.lastUpdated).getTime() : null;

  const filteredIssues = useMemo(() => {
    if (!project) return [];
    return filterIssuesWithContext(project, filters, referenceTime);
  }, [project, filters, referenceTime]);

  const componentLookup = useMemo(() => {
    if (!project) return {};
    return project.components.reduce<Record<string, string>>((acc, component) => {
      acc[component.id] = component.name;
      return acc;
    }, {});
  }, [project]);
  const componentEvents = useMemo(() => {
    if (!project) return {};
    return project.components.reduce<Record<string, SourceEvent[]>>((acc, component) => {
      acc[component.id] = component.sourceEvents;
      return acc;
    }, {});
  }, [project]);
  const componentOptions = useMemo(
    () => project?.components.map((component) => ({ id: component.id, name: component.name })) ?? [],
    [project]
  );
  const liveIssues = useMemo(() => {
    if (!project) return [];
    return project.docIssues.filter((issue) => issue.id.startsWith("live_issue"));
  }, [project]);
  const liveSeverityBuckets = useMemo(() => {
    return liveIssues.reduce(
      (acc, issue) => {
        acc[issue.severity] += 1;
        return acc;
      },
      { critical: 0, high: 0, medium: 0, low: 0 } as Record<Severity, number>
    );
  }, [liveIssues]);
  const latestLiveUpdate = useMemo(() => {
    if (!liveIssues.length) return null;
    return liveIssues.reduce((latest, issue) => {
      const ts = new Date(issue.updatedAt).getTime();
      return ts > latest ? ts : latest;
    }, 0);
  }, [liveIssues]);
  const liveImpactedComponents = useMemo(() => {
    const ids = Array.from(new Set(liveIssues.map((issue) => issue.componentId)));
    return {
      ids,
      names: ids
        .map((id) => componentLookup[id] ?? id)
        .filter(Boolean),
    };
  }, [componentLookup, liveIssues]);
  const liveSignalTotals = useMemo(() => {
    return liveIssues.reduce(
      (acc, issue) => {
        acc.git += issue.signals.gitChurn;
        acc.slack += issue.signals.slackMentions;
        acc.tickets += issue.signals.ticketsMentioned;
        acc.support += issue.signals.supportMentions ?? 0;
        return acc;
      },
      { git: 0, slack: 0, tickets: 0, support: 0 }
    );
  }, [liveIssues]);
  const topLiveIssues = useMemo(() => {
    return [...liveIssues]
      .sort((a, b) => {
        const severityDelta = severityOrder.indexOf(a.severity) - severityOrder.indexOf(b.severity);
        if (severityDelta !== 0) return severityDelta;
        return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
      })
      .slice(0, 3);
  }, [liveIssues]);
  const triageIssues = useMemo(() => {
    const source = liveIssues.length ? liveIssues : filteredIssues;
    return [...source]
      .sort((a, b) => {
        const severityDelta = severityOrder.indexOf(a.severity) - severityOrder.indexOf(b.severity);
        if (severityDelta !== 0) return severityDelta;
        return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
      })
      .slice(0, 6);
  }, [filteredIssues, liveIssues]);
  const ingestCounts = useMemo(() => {
    return {
      git: liveSnapshot?.git.length ?? 0,
      slack: liveSnapshot?.slack.length ?? 0,
      tickets: liveSnapshot?.tickets?.length ?? 0,
      support: liveSnapshot?.support?.length ?? 0,
    };
  }, [liveSnapshot]);
  const ingestWarnings = useMemo(() => {
    const warnings: string[] = [];
    if (!liveSnapshot) {
      warnings.push("Live snapshot unavailable. Falling back to mock data.");
    } else if (!ingestCounts.git && !ingestCounts.slack && !ingestCounts.tickets && !ingestCounts.support) {
      warnings.push("Live snapshot returned zero signals; verify dataset wiring.");
    }
    if (liveStatus.mode === "error" && liveStatus.message) {
      warnings.push(liveStatus.message);
    }
    return warnings;
  }, [ingestCounts, liveSnapshot, liveStatus.message, liveStatus.mode]);
  const divergenceAlerts = useMemo(() => {
    if (!project) return [];
    const severityWeights: Record<Severity, number> = {
      critical: 4,
      high: 3,
      medium: 2,
      low: 1,
    };
    return project.components
      .flatMap((component) =>
        component.divergenceInsights.map((insight) => ({
          ...insight,
          componentName: component.name,
        }))
      )
      .sort((a, b) => severityWeights[b.severity] - severityWeights[a.severity])
      .slice(0, 4);
  }, [project]);

  const severityFilterActive = (severity: Severity) => filters.severities.includes(severity);
  const toggleSeverityFilter = (severity: Severity) => {
    const next = severityFilterActive(severity)
      ? filters.severities.filter((value) => value !== severity)
      : [...filters.severities, severity];
    setFilters({ severities: next });
  };
  const toggleLiveOnly = () => {
    setFilters({ onlyLive: !filters.onlyLive });
  };

  if (!project) {
    return <div className="text-sm text-destructive">Project not found.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <LiveRecency />
        <div className="flex flex-wrap items-center gap-3">
          <LiveModePill />
          <NewSignalToast projectId={project.id} />
          <ManualRefreshButton />
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-[2fr,1fr]">
        <div className="space-y-6">
          <Card className="border border-primary/30 bg-gradient-to-br from-primary/10 via-background to-background">
            <CardHeader className="flex flex-wrap items-start justify-between gap-3 pb-0">
              <div>
                <CardDescription className="text-xs uppercase tracking-[0.4em] text-primary">Live doc drift</CardDescription>
                <CardTitle className="text-2xl font-semibold text-foreground">
                  Heuristic issues from Git, Slack, Tickets, Support
                </CardTitle>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="rounded-full border-border/60 text-[10px] uppercase text-muted-foreground">
                  {describeMode(project.mode ?? liveStatus.mode)}
                </Badge>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="rounded-full text-xs"
                  onClick={() => setDetailsOpen((open) => !open)}
                >
                  {detailsOpen ? "Hide signal detail" : "Show signal detail"}
                  <ChevronDown className={cn("ml-1 h-4 w-4 transition-transform", detailsOpen && "rotate-180")} />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 pt-4">
              {liveIssues.length ? (
                <div className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-3">
                    <HeroStat label="Live drift issues" value={liveIssues.length} />
                    <HeroStat label="Impacted components" value={liveImpactedComponents.ids.length} />
                    <HeroStat
                      label="Signals observed"
                      value={liveSignalTotals.git + liveSignalTotals.slack + liveSignalTotals.tickets + liveSignalTotals.support}
                    />
                  </div>
                  <div className="grid gap-6 lg:grid-cols-[1.4fr,1fr]">
                    <div className="space-y-3">
                      <p className="text-xs text-muted-foreground">
                        Updated {latestLiveUpdate ? shortDate(new Date(latestLiveUpdate).toISOString()) : "never"} •{" "}
                        {liveImpactedComponents.names.slice(0, 4).join(", ") || "No components yet"}
                        {liveImpactedComponents.ids.length > 4 ? ` (+${liveImpactedComponents.ids.length - 4} more)` : ""}
                      </p>
                      {detailsOpen ? (
                        <div className="space-y-4 rounded-2xl border border-border/40 bg-background/40 p-4">
                          <div className="flex flex-wrap gap-2">
                            {(Object.keys(liveSeverityBuckets) as Severity[])
                              .filter((severity) => liveSeverityBuckets[severity] > 0)
                              .map((severity) => (
                                <Badge key={severity} variant="outline" className="rounded-full border-border/60 text-xs uppercase">
                                  {severity}: {liveSeverityBuckets[severity]}
                                </Badge>
                              ))}
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {(severityOrder as Severity[]).map((severity) => (
                              <FilterChip
                                key={`chip-${severity}`}
                                label={severity}
                                active={severityFilterActive(severity)}
                                onClick={() => toggleSeverityFilter(severity)}
                              />
                            ))}
                            <FilterChip label="Live only" active={filters.onlyLive} onClick={toggleLiveOnly} />
                          </div>
                          {divergenceAlerts.length ? (
                            <div className="space-y-2">
                              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Divergence alerts</p>
                              {divergenceAlerts.map((alert) => (
                                <div key={alert.id} className="rounded-2xl border border-border/50 p-3 text-xs">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <Badge
                                      variant="outline"
                                      className={cn(
                                        "rounded-full border-border/60 text-[10px]",
                                        alert.severity === "critical"
                                          ? "bg-red-500/15 text-red-200 border-red-500/40"
                                          : alert.severity === "high"
                                          ? "bg-amber-500/15 text-amber-200 border-amber-500/40"
                                          : alert.severity === "medium"
                                          ? "bg-blue-500/15 text-blue-100 border-blue-500/40"
                                          : "bg-emerald-500/15 text-emerald-100 border-emerald-500/40"
                                      )}
                                    >
                                      {alert.severity.toUpperCase()}
                                    </Badge>
                                    <span className="font-semibold text-foreground">{alert.componentName}</span>
                                    <span className="text-muted-foreground">Detected {shortDate(alert.detectedAt)}</span>
                                  </div>
                                  <p className="pt-1 text-muted-foreground">{alert.summary}</p>
                                  <div className="flex flex-wrap gap-2 pt-2">
                                    {alert.sources.map((source) => {
                                      const token = signalSourceTokens[source];
                                      return (
                                        <Badge key={`${alert.id}-${source}`} className={`border text-[10px] ${token.color}`}>
                                          {token.label}
                                        </Badge>
                                      );
                                    })}
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                      {ingestWarnings.length ? (
                        <div className="space-y-1 text-[11px] text-amber-200">
                          {ingestWarnings.map((warning, index) => (
                            <p key={index}>{warning}</p>
                          ))}
                        </div>
                      ) : null}
                    </div>
                    <div className="space-y-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Top live issues</p>
                      {topLiveIssues.map((issue) => (
                        <LiveIssueSummary
                          key={issue.id}
                          issue={issue}
                          componentName={componentLookup[issue.componentId] ?? issue.componentId}
                          onSelect={() => setSelectedIssue(issue)}
                        />
                      ))}
                      {!topLiveIssues.length ? (
                        <p className="text-sm text-muted-foreground">Live issues detected but none ready to preview.</p>
                      ) : null}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  {isLiveLike(liveStatus.mode)
                    ? "No live drift signals detected in the latest snapshot."
                    : liveStatus.mode === "error"
                    ? "Live ingest is currently failing. Check tokens or try refreshing."
                    : "Snapshot warming up — synthetic data is visible until live ingest succeeds."}
                </p>
              )}
            </CardContent>
          </Card>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <MetricCard
              icon={Flame}
              label="Live drift issues"
              value={`${liveIssues.length}`}
              description={`${(liveSeverityBuckets.critical ?? 0) + (liveSeverityBuckets.high ?? 0)} high+ severity`}
            />
            <MetricCard
              icon={Users}
              label="Impacted components"
              value={`${liveImpactedComponents.ids.length}`}
              description={liveImpactedComponents.names.slice(0, 2).join(", ") || "No components yet"}
            />
            <MetricCard
              icon={Shield}
              label="Doc health score"
              value={`${project.docHealthScore}/100`}
              description="Based on drift + dissatisfaction signals."
            />
          </section>
          <IssueFilters
            filters={filters}
            onChange={setFilters}
            onReset={() => {
              resetFilters();
            }}
            components={componentOptions}
          />
        </div>

        <div className="space-y-6">
          <Card className="h-full border-dashed">
            <CardHeader>
              <CardTitle>Operator diagnostics</CardTitle>
              <CardDescription>Jump to dataset probes, ingest counts, and export config.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <p>Use this panel when you need to debug live ingest or share the config export with Cerebros.</p>
              <Button variant="outline" className="rounded-full text-xs" asChild>
                <Link href={`/projects/${project.id}/configuration#live-inspector`}>Open operator diagnostics</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Live triage queue</CardTitle>
          <CardDescription>Top DocIssues waiting for action right now.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {triageIssues.length ? (
            triageIssues.map((issue) => (
              <LiveIssueSummary
                key={`triage-${issue.id}`}
                issue={issue}
                componentName={componentLookup[issue.componentId] ?? issue.componentId}
                onSelect={() => setSelectedIssue(issue)}
              />
            ))
          ) : (
            <p className="text-sm text-muted-foreground">No heuristic DocIssues detected.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Documentation drift issues</CardTitle>
          <CardDescription>Pivot across severity, status, sources, and time to prioritize fixes.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <IssueList
            issues={filteredIssues}
            onSelect={(issue) => setSelectedIssue(issue)}
            componentLookup={componentLookup}
            componentEvents={componentEvents}
            projectId={project.id}
          />
        </CardContent>
      </Card>

      {selectedIssue ? (
        <IssueDetailSheet issue={selectedIssue} project={project} open={Boolean(selectedIssue)} onOpenChange={(open) => !open && setSelectedIssue(null)} />
      ) : null}
    </div>
  );
}

const MetricCard = ({
  icon: Icon,
  label,
  value,
  description,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  description: string;
}) => (
  <div className="rounded-3xl border border-border/60 bg-card/60 p-5 shadow-inner">
    <div className="flex items-center gap-3">
      <div className="rounded-2xl bg-primary/15 p-2 text-primary">
        <Icon className="h-4 w-4" />
      </div>
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</div>
    </div>
    <div className="text-3xl font-bold text-foreground">{value}</div>
    <p className="text-xs text-muted-foreground">{description}</p>
  </div>
);

const HeroStat = ({ label, value }: { label: string; value: number }) => (
  <div className="rounded-2xl border border-border/60 bg-card/70 p-4">
    <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
    <p className="text-3xl font-semibold text-foreground">{value}</p>
  </div>
);

const FilterChip = ({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) => (
  <button
    type="button"
    onClick={onClick}
    className={cn(
      "rounded-full border px-3 py-1 text-xs uppercase transition",
      active ? "border-primary/50 bg-primary/15 text-primary" : "border-border/50 text-muted-foreground hover:border-primary/40"
    )}
  >
    {label}
  </button>
);

const LiveIssueSummary = ({
  issue,
  componentName,
  onSelect,
}: {
  issue: DocIssue;
  componentName: string;
  onSelect: () => void;
}) => {
  const sourceTokens = issue.divergenceSources.map((source) => signalSourceTokens[source]);
  const [highlight, setHighlight] = useState(true);

  useEffect(() => {
    const frame = requestAnimationFrame(() => setHighlight(true));
    const timeout = setTimeout(() => setHighlight(false), 2000);
    return () => {
      cancelAnimationFrame(frame);
      clearTimeout(timeout);
    };
  }, [issue.id]);

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full rounded-2xl border border-border/60 bg-background/60 p-3 text-left transition hover:border-primary/40 hover:bg-primary/5",
        highlight && "ring-2 ring-primary/40"
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-foreground">{componentName}</span>
        <Badge variant="outline" className="rounded-full border-border/60 text-[10px] uppercase">
          {issue.severity}
        </Badge>
      </div>
      <p className="text-xs text-muted-foreground">{issue.title}</p>
      <p className="text-[11px] text-muted-foreground">{describeIssueSignals(issue)}</p>
      <div className="flex flex-wrap gap-2 pt-2">
        {sourceTokens.map((token, idx) => (
          <Badge key={`${issue.id}-${idx}`} className={`border text-[10px] ${token.color}`}>
            {token.label}
          </Badge>
        ))}
        <Badge variant="outline" className="rounded-full border-border/40 text-[10px] text-muted-foreground">
          Updated {shortDate(issue.updatedAt)}
        </Badge>
      </div>
    </button>
  );
};

