"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { BookOpen, GitBranch, LifeBuoy, MessageSquare, Ticket } from "lucide-react";

import { ActivityGraphPanel } from "@/components/activity/activity-graph-panel";
import { IssueDetailSheet } from "@/components/issues/issue-detail";
import { ImpactAlertsPanel } from "@/components/impact/impact-alerts-panel";
import { LiveRecency } from "@/components/live/live-recency";
import { ManualRefreshButton } from "@/components/live/manual-refresh";
import { NewSignalToast } from "@/components/live/new-signal-toast";
import { Badge } from "@/components/ui/badge";
import { LinkChip } from "@/components/common/link-chip";
import { ModeBadge } from "@/components/common/mode-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { describeIssueSignals } from "@/lib/issues/descriptions";
import { describeMode, isLiveLike } from "@/lib/mode";
import { selectProjectById, useDashboardStore } from "@/lib/state/dashboard-store";
import { cn, shortTime } from "@/lib/utils";
import { severityTokens, signalSourceTokens } from "@/lib/ui/tokens";
import type { DocIssue, Severity, SourceEvent, LiveMode } from "@/lib/types";

const severityOrder: Severity[] = ["critical", "high", "medium", "low"];
const summarySeverities: Severity[] = ["critical", "high", "medium"];

const sourceIconMap = {
  git: GitBranch,
  docs: BookOpen,
  slack: MessageSquare,
  tickets: Ticket,
  support: LifeBuoy,
} as const;

type RecentSignal = SourceEvent & { componentName: string };

type LiveStatusSnapshot = {
  mode: LiveMode;
  lastUpdated: string | null;
  message?: string | null;
};

export default function ProjectTodayPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
  const projectSelector = useMemo(() => selectProjectById(projectId), [projectId]);
  const project = useDashboardStore(projectSelector);
  const liveStatus = useDashboardStore((state) => state.liveStatus);

  const [selectedIssue, setSelectedIssue] = useState<DocIssue | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  const severityCounts = useMemo(() => {
    if (!project) {
      return { critical: 0, high: 0, medium: 0, low: 0 } as Record<Severity, number>;
    }
    return project.docIssues.reduce<Record<Severity, number>>(
      (acc, issue) => {
        acc[issue.severity] += 1;
        return acc;
      },
      { critical: 0, high: 0, medium: 0, low: 0 }
    );
  }, [project]);

  const componentLookup = useMemo(() => {
    if (!project) return {};
    return project.components.reduce<Record<string, string>>((acc, component) => {
      acc[component.id] = component.name;
      return acc;
    }, {});
  }, [project]);

  const topIssues = useMemo(() => {
    if (!project) return [];
    return [...project.docIssues]
      .sort((a, b) => {
        const severityDelta = severityOrder.indexOf(a.severity) - severityOrder.indexOf(b.severity);
        if (severityDelta !== 0) return severityDelta;
        return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
      })
      .slice(0, 3);
  }, [project]);

  const recentSignals = useMemo(() => {
    if (!project) return [];
    const events: RecentSignal[] = project.components.flatMap((component) =>
      component.sourceEvents.map((event) => ({ ...event, componentName: component.name }))
    );
    return events
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .slice(0, 10);
  }, [project]);

  const openIssue = (issue: DocIssue) => {
    setSelectedIssue(issue);
    setSheetOpen(true);
  };

  if (!project) {
    return <div className="text-sm text-destructive">Project not found.</div>;
  }

  const currentMode: LiveMode = project?.mode ?? liveStatus.mode;

  return (
    <div className="space-y-8">
      <Card className="border border-border/70 bg-card/80" data-testid="today-hero">
        <CardHeader className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.4em] text-muted-foreground">{project.horizon} environment</p>
              <CardTitle className="text-3xl font-semibold text-foreground">{project.name}</CardTitle>
              <CardDescription className="text-sm text-muted-foreground">{project.description}</CardDescription>
            </div>
            <div className="flex flex-col items-end gap-2 text-right">
              <ModeBadge mode={project.mode ?? liveStatus.mode} />
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Doc health</p>
              <p className="text-5xl font-bold text-primary">{project.docHealthScore}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {summarySeverities.map((severity) => {
              const token = severityTokens[severity];
              return (
                <Badge key={severity} className={cn("border text-[11px]", token.color)}>
                  {token.label}: {severityCounts[severity] ?? 0}
                </Badge>
              );
            })}
          </div>
        </CardHeader>
        <CardContent>
          <LiveStatusSummary
            projectId={project.id}
            snapshot={{ mode: liveStatus.mode, lastUpdated: liveStatus.lastUpdated, message: liveStatus.message }}
          />
        </CardContent>
      </Card>

      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.35em] text-muted-foreground">Option 1 · documentation risk</p>
        <ActivityGraphPanel projectId={project.id} components={project.components} />
      </div>

      <section className="grid gap-6 lg:grid-cols-[2fr,1fr]">
        <Card className="border border-border/70 bg-card/80">
          <CardHeader>
            <CardTitle>Doc issues to fix now</CardTitle>
            <CardDescription>Highest severity + most recent drift signals.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4" data-testid="today-top-issues">
            {topIssues.length ? (
              topIssues.map((issue) => (
                <TopIssueRow
                  key={issue.id}
                  issue={issue}
                  componentName={componentLookup[issue.componentId] ?? issue.componentId}
                  onView={() => openIssue(issue)}
                />
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No open drift issues. Enjoy the calm.</p>
            )}
          </CardContent>
        </Card>

        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-[0.35em] text-muted-foreground">Live drift signals</p>
          <LatestSignalsRail signals={recentSignals} mode={currentMode} />
        </div>
      </section>

      <section className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.35em] text-muted-foreground">
          Option 2 · downstream documentation impact
        </p>
        <ImpactAlertsPanel projectId={project.id} />
      </section>

      {selectedIssue ? (
        <IssueDetailSheet issue={selectedIssue} project={project} open={sheetOpen} onOpenChange={setSheetOpen} />
      ) : null}
    </div>
  );
}

function LiveStatusSummary({
  projectId,
  snapshot,
}: {
  projectId: string;
  snapshot: LiveStatusSnapshot;
}) {
  const statusText = (() => {
    if (isLiveLike(snapshot.mode) && snapshot.lastUpdated) {
      return `Data fresh ${shortTime(snapshot.lastUpdated)}`;
    }
    if (snapshot.mode === "error") {
      return snapshot.message ? `Ingest error: ${snapshot.message}` : "Ingest error — check diagnostics";
    }
    return describeMode(snapshot.mode as Parameters<typeof describeMode>[0]);
  })();

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-border/60 bg-muted/10 px-4 py-3">
      <div className="text-sm font-semibold text-foreground">{statusText}</div>
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <LiveRecency />
        <NewSignalToast projectId={projectId} />
        <ManualRefreshButton />
      </div>
      <Button asChild variant="ghost" className="ml-auto h-auto px-0 text-xs font-semibold text-primary">
        <Link href={`/projects/${projectId}/configuration#live-inspector`}>View diagnostics</Link>
      </Button>
    </div>
  );
}

function TopIssueRow({
  issue,
  componentName,
  onView,
}: {
  issue: DocIssue;
  componentName: string;
  onView: () => void;
}) {
  const severity = severityTokens[issue.severity];
  const reason = describeIssueSignals(issue) || issue.summary;

  return (
    <div className="space-y-3 rounded-2xl border border-border/60 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-foreground">{issue.title}</p>
          <p className="text-xs text-muted-foreground">{componentName}</p>
          <p className="text-xs text-muted-foreground/90">{reason}</p>
        </div>
        <Badge className={cn("border text-[10px]", severity.color)}>{severity.label}</Badge>
      </div>
      <div className="flex flex-wrap gap-3">
        <Button variant="secondary" size="sm" className="rounded-full px-4" onClick={onView}>
          View issue
        </Button>
        {issue.brainTraceUrl ? (
          <Button asChild variant="default" size="sm" className="rounded-full px-4">
            <Link href={issue.brainTraceUrl} target="_blank" rel="noreferrer">
              View reasoning path
            </Link>
          </Button>
        ) : null}
        {issue.cerebrosUrl ? (
          <Button asChild variant="outline" size="sm" className="rounded-full px-4">
            <Link href={issue.cerebrosUrl} target="_blank" rel="noreferrer">
              Ask OQOQO / Cerebros
            </Link>
          </Button>
        ) : (
          <Button variant="outline" size="sm" className="rounded-full px-4" disabled>
            Ask OQOQO / Cerebros
          </Button>
        )}
      </div>
    </div>
  );
}

function LatestSignalsRail({ signals, mode }: { signals: RecentSignal[]; mode: LiveMode }) {
  if (!signals.length) {
    return (
      <div
        className="rounded-3xl border border-dashed border-border/60 bg-muted/5 p-4 text-sm text-muted-foreground"
        data-testid="today-signals-empty"
      >
        {mode === "atlas"
          ? "No live Slack/Git signals were reported in the last few hours."
          : "Synthetic demo data hides live signals — switch to Live data once ingest is configured."}
      </div>
    );
  }

  const latestTimestamp = signals[0]?.timestamp;

  return (
    <Card className="border border-border/70 bg-card/80" data-testid="today-signals">
      <CardHeader className="flex flex-col gap-1 pb-2">
        <div className="flex items-center gap-2">
          <CardTitle>Latest drift signals</CardTitle>
          <Badge variant="outline" className="rounded-full border-border/50 text-[10px] uppercase tracking-wide">
            {mode === "atlas" ? "Live ingest" : "Synthetic demo"}
          </Badge>
        </div>
        <CardDescription>Across Git, Slack, tickets, docs, and support.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-1 snap-x gap-3 overflow-x-auto pb-2">
            {signals.slice(0, 8).map((signal) => (
              <SignalChip key={signal.id} signal={signal} />
            ))}
          </div>
          <div className="text-xs text-muted-foreground">
            Updated {latestTimestamp ? shortTime(latestTimestamp) : "moments ago"}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function SignalChip({ signal }: { signal: RecentSignal }) {
  const token = signalSourceTokens[signal.source];
  const Icon = sourceIconMap[signal.source];

  return (
    <div className="flex min-w-[220px] flex-col gap-2 rounded-2xl border border-border/50 bg-muted/10 p-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className={cn("rounded-full border border-border/40 p-1", token.color)}>
          <Icon className="h-3.5 w-3.5" />
        </span>
        <span className="font-semibold capitalize text-foreground">{signal.source}</span>
        <span className="ml-auto text-[11px]">{shortTime(signal.timestamp)}</span>
      </div>
      <div>
        <p className="text-sm font-semibold text-foreground">{signal.title}</p>
        <p className="text-xs text-muted-foreground">{signal.componentName}</p>
      </div>
      {signal.description ? <p className="text-xs text-muted-foreground/80">{signal.description}</p> : null}
      <LinkChip label="View source" href={signal.link} variant="ghost" size="sm" className="h-auto px-0 text-[11px]" />
    </div>
  );
}
